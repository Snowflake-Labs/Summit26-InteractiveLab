"""
Summit 2026 Interactive Lab – Arcade Streaming
Main script: streams arcade scores into Snowflake via Snowpipe Streaming SDK.

Usage:
    python arcade_streamer.py [--rows N] [--forever] [--channels N] [--rate N]

Options:
    --rows N        Stop after inserting N total rows (default: run until Ctrl-C)
    --forever       Run indefinitely (default behaviour, same as omitting --rows)
    --channels N    Number of parallel producers (default: from config.py)
    --rate N        Target rows/sec across all producers (default: from config.py)
    --profile PATH  Path to profile.json (default: profile.json)
    --dry-run       Generate and print rows without connecting to Snowflake
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

# ── logging verbosity (set before SDK import) ──────────────────────────────
os.environ.setdefault("SS_LOG_LEVEL", "warn")

import config
from generator import generate_batch

ACK_TIMEOUT_SECONDS = 120

# SDK imported lazily inside main() so --dry-run works without the package installed.


def _account_from_url(uri: str) -> tuple[str, str]:
    uri = uri.strip()
    if "://" not in uri:
        uri = "https://" + uri
    uri = uri.rstrip("/")
    host = uri.split("://", 1)[1].split("/", 1)[0]
    if ":" in host:
        host = host.split(":", 1)[0]
    account = host.removesuffix(".snowflakecomputing.com")
    if account.endswith(".privatelink"):
        account = account[: -len(".privatelink")]
    return uri, account


def _normalize_profile(profile_path: str) -> str:
    """Require a Snowsight Account URL in profile.json; derive account from that URL."""
    with open(profile_path, encoding="utf-8") as f:
        data = json.load(f)
    uri = data.get("url") if isinstance(data.get("url"), str) else ""
    if not uri.strip() or "PASTE_ACCOUNT_URL" in uri:
        raise SystemExit(
            "Set profile.json url to the Account URL from Snowsight: "
            "https://docs.snowflake.com/en/user-guide/ui-snowsight-gs#locate-your-snowflake-account-information-in-snowsight"
        )
    uri, account = _account_from_url(uri)
    data["url"] = uri
    data["account"] = account
    normalized = profile_path + ".normalized"
    with open(normalized, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        f.write("\n")
    return normalized


def _account_for_banner(profile_path: str) -> str:
    """Snowflake account URL for startup banner."""
    try:
        with open(profile_path, encoding="utf-8") as f:
            data = json.load(f)
        url = data.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()
        acc = data.get("account")
        if isinstance(acc, str) and acc.strip():
            return acc.strip()
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return config.SNOWFLAKE_ACCOUNT


# ---------------------------------------------------------------------------
# Stats tracker (shared across threads)
# ---------------------------------------------------------------------------

class Stats:
    def __init__(self) -> None:
        self._lock          = threading.Lock()
        self.total_rows     = 0
        self.total_errors   = 0
        self._window_rows   = 0
        self._window_start  = time.monotonic()

    def add(self, rows: int, errors: int = 0) -> None:
        with self._lock:
            self.total_rows   += rows
            self.total_errors += errors
            self._window_rows += rows

    def throughput(self) -> float:
        """Rows/sec in the current stats window; resets the window."""
        with self._lock:
            elapsed = time.monotonic() - self._window_start
            rps = self._window_rows / elapsed if elapsed > 0 else 0.0
            self._window_rows  = 0
            self._window_start = time.monotonic()
        return rps


STATS = Stats()
_STOP_EVENT = threading.Event()
_ACTIVE_CHANNELS: list[Any] = []
_CHANNELS_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Producer worker
# ---------------------------------------------------------------------------

def channel_worker(
    client: Any,
    worker_id: int,
    rows_target: int | None,
    rows_per_batch: int,
    sleep_per_batch: float,
) -> None:
    """
    Writes batches through the client's singleton elastic channel until
    _STOP_EVENT is set or rows_target is reached.
    """
    channel = client.get_elastic_channel()
    with _CHANNELS_LOCK:
        _ACTIVE_CHANNELS.append(channel)
    append_seq = 0

    try:
        print(f"  [producer-{worker_id}] opened elastic channel: {channel.channel_name}")

        while not _STOP_EVENT.is_set():
            if rows_target is not None and STATS.total_rows >= rows_target:
                _STOP_EVENT.set()
                break

            batch = generate_batch(rows_per_batch)
            append_seq += 1
            try:
                future = channel.append_rows_with_wait(
                    batch, f"arcade-{worker_id}-{append_seq}"
                )
                future.result(timeout=ACK_TIMEOUT_SECONDS)
                STATS.add(len(batch), 0)
            except Exception as exc:
                STATS.add(0, len(batch))
                print(
                    f"  [producer-{worker_id}] append_rows_with_wait error: {exc}",
                    file=sys.stderr,
                )

            if sleep_per_batch > 0:
                _STOP_EVENT.wait(timeout=sleep_per_batch)

        print(f"  [producer-{worker_id}] closing.")
    finally:
        with _CHANNELS_LOCK:
            if channel in _ACTIVE_CHANNELS:
                _ACTIVE_CHANNELS.remove(channel)


# ---------------------------------------------------------------------------
# Stats printer (runs in its own thread)
# ---------------------------------------------------------------------------

def stats_printer(interval: float, start_time: float) -> None:
    while not _STOP_EVENT.is_set():
        _STOP_EVENT.wait(timeout=interval)
        rps     = STATS.throughput()
        elapsed = time.monotonic() - start_time
        print(
            f"  [{datetime.now().strftime('%H:%M:%S')}]  "
            f"rows: {STATS.total_rows:>10,}  |  "
            f"{rps:>7.1f} rows/sec  |  "
            f"errors: {STATS.total_errors}  |  "
            f"elapsed: {elapsed:>6.0f}s"
        )


# ---------------------------------------------------------------------------
# Latency monitor (runs in its own thread)
# ---------------------------------------------------------------------------

def _latency_ms(lag: Any) -> float | None:
    if lag is None:
        return None
    if isinstance(lag, timedelta):
        return lag.total_seconds() * 1000
    return float(lag)


def latency_monitor(interval: float) -> None:
    """Polls elastic channel status and logs Snowflake-reported avg processing latency."""
    while not _STOP_EVENT.is_set():
        _STOP_EVENT.wait(timeout=interval)
        if _STOP_EVENT.is_set():
            break
        with _CHANNELS_LOCK:
            channels = list(_ACTIVE_CHANNELS)
        if not channels:
            continue
        for channel in channels:
            try:
                st = channel.get_channel_status()
                lag_ms = _latency_ms(st.server_avg_processing_latency)
                if lag_ms is not None:
                    print(
                        f"  [{datetime.now().strftime('%H:%M:%S')}]  "
                        f"[latency] {st.channel_name}: {lag_ms:.0f} ms avg"
                    )
            except Exception as exc:
                print(f"  [latency] status error: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Dry-run mode (no Snowflake connection)
# ---------------------------------------------------------------------------

def dry_run(rows_target: int | None, rows_per_batch: int) -> None:
    from generator import generate_score
    import json

    print("DRY-RUN MODE – no data will be sent to Snowflake\n")
    count = 0
    while rows_target is None or count < rows_target:
        row = generate_score()
        display = {
            k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in row.items()
        }
        print(json.dumps(display))
        count += 1
        if rows_target is None and count >= 20:
            print(f"\n... (stopping dry-run after 20 rows; pass --rows N to control) ...")
            break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Arcade Scores Snowpipe Streamer")
    p.add_argument("--rows",     type=int,   default=None,
                   help="Stop after N total rows (default: unlimited)")
    p.add_argument("--forever",  action="store_true",
                   help="Run indefinitely (default)")
    p.add_argument("--channels", type=int,   default=config.NUM_CHANNELS,
                   help=f"Parallel producers (default: {config.NUM_CHANNELS})")
    p.add_argument("--rate",     type=float, default=config.TARGET_ROWS_PER_SEC,
                   help=f"Target rows/sec (default: {config.TARGET_ROWS_PER_SEC}, 0 = unlimited)")
    p.add_argument("--profile",  default=config.PROFILE_JSON_PATH,
                   help=f"Path to profile.json (default: {config.PROFILE_JSON_PATH})")
    p.add_argument("--dry-run",  action="store_true",
                   help="Generate rows and print them; do not connect to Snowflake")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.dry_run:
        dry_run(args.rows, config.BATCH_SIZE)
        return

    # Lazy import so --dry-run works without the SDK installed
    try:
        from snowflake.ingest.streaming import StreamingIngestClient  # noqa: F401
    except ImportError:
        print(
            "ERROR: snowpipe-streaming package not found.\n"
            "Install it with:  pip install snowpipe-streaming",
            file=sys.stderr,
        )
        sys.exit(1)
    from snowflake.ingest.streaming import StreamingIngestClient

    num_producers  = args.channels
    rows_target    = args.rows
    rows_per_batch = config.BATCH_SIZE

    if args.rate > 0:
        rows_per_producer_per_sec = args.rate / num_producers
        sleep_per_batch = rows_per_batch / rows_per_producer_per_sec
    else:
        sleep_per_batch = 0.0

    print("=" * 60)
    print(" Summit 2026 – Arcade Scores Snowpipe Streamer")
    print("=" * 60)
    profile_for_sdk = _normalize_profile(args.profile)
    print(f"  Account   : {_account_for_banner(profile_for_sdk)}")
    print(f"  Database  : {config.SNOWFLAKE_DATABASE}.{config.SNOWFLAKE_SCHEMA}")
    print(f"  Pipe      : {config.SNOWFLAKE_PIPE}")
    print(f"  Producers : {num_producers}")
    print(f"  Target    : {args.rate if args.rate > 0 else 'unlimited'} rows/sec")
    print(f"  Stop after: {rows_target if rows_target else 'Ctrl-C'} rows")
    print(f"  Profile   : {args.profile}")
    print("=" * 60)

    start_time = time.monotonic()
    clients: list[Any] = []

    try:
        for i in range(num_producers):
            clients.append(
                StreamingIngestClient(
                    client_name  = f"ARCADE_CLIENT_{i}_{uuid.uuid4().hex[:8].upper()}",
                    db_name      = config.SNOWFLAKE_DATABASE,
                    schema_name  = config.SNOWFLAKE_SCHEMA,
                    pipe_name    = config.SNOWFLAKE_PIPE,
                    profile_json = profile_for_sdk,
                )
            )

        print(f"\nConnected to Snowflake. Opening {num_producers} elastic channel(s)...\n")

        printer = threading.Thread(
            target=stats_printer,
            args=(config.STATS_INTERVAL_SEC, start_time),
            daemon=True,
        )
        printer.start()

        monitor = threading.Thread(
            target=latency_monitor,
            args=(config.STATS_INTERVAL_SEC,),
            daemon=True,
        )
        monitor.start()

        workers: list[threading.Thread] = []
        for i, client in enumerate(clients):
            t = threading.Thread(
                target=channel_worker,
                args=(client, i, rows_target, rows_per_batch, sleep_per_batch),
                daemon=True,
            )
            t.start()
            workers.append(t)

        try:
            for w in workers:
                w.join()
        except KeyboardInterrupt:
            print("\n\nCtrl-C received – shutting down producers...")
            _STOP_EVENT.set()
            for w in workers:
                w.join(timeout=10)
    finally:
        for client in clients:
            try:
                client.close()
            except Exception:
                pass

    elapsed = time.monotonic() - start_time
    print("\n" + "=" * 60)
    print(f"  Total rows ingested : {STATS.total_rows:,}")
    print(f"  Total errors        : {STATS.total_errors:,}")
    print(f"  Elapsed time        : {elapsed:.1f}s")
    print(f"  Average throughput  : {STATS.total_rows / elapsed:.1f} rows/sec")
    print("=" * 60)


if __name__ == "__main__":
    main()
