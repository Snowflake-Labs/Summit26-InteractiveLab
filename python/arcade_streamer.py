"""
Summit 2026 Interactive Lab – Arcade Streaming
Main script: streams arcade scores into Snowflake via Snowpipe Streaming SDK.

Usage:
    python arcade_streamer.py [--rows N] [--forever] [--channels N] [--rate N]

Options:
    --rows N        Stop after inserting N total rows (default: run until Ctrl-C)
    --forever       Run indefinitely (default behaviour, same as omitting --rows)
    --channels N    Number of parallel SDK channels (default: from config.py)
    --rate N        Target rows/sec across all channels (default: from config.py)
    --profile PATH  Path to profile.json (default: profile.json)
    --dry-run       Generate and print rows without connecting to Snowflake
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from typing import Any

# ── logging verbosity (set before SDK import) ──────────────────────────────
os.environ.setdefault("SS_LOG_LEVEL", "warn")

import config
from generator import generate_batch

# SDK imported lazily inside main() so --dry-run works without the package installed.


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


# ---------------------------------------------------------------------------
# Channel worker
# ---------------------------------------------------------------------------

def channel_worker(
    client: Any,
    channel_id: int,
    rows_target: int | None,
    rows_per_batch: int,
    sleep_per_batch: float,
) -> None:
    """
    Opens a single streaming channel and continuously inserts batches of
    arcade scores until _STOP_EVENT is set or rows_target is reached.
    """
    channel_name = f"ARCADE_CHANNEL_{channel_id}_{uuid.uuid4().hex[:8].upper()}"
    offset_token = 0

    with client.open_channel(channel_name)[0] as channel:
        print(f"  [channel-{channel_id}] opened: {channel.channel_name}")

        while not _STOP_EVENT.is_set():
            if rows_target is not None and STATS.total_rows >= rows_target:
                _STOP_EVENT.set()
                break

            batch = generate_batch(rows_per_batch)

            errors = 0
            for row in batch:
                try:
                    channel.append_row(row, str(offset_token))
                    offset_token += 1
                except Exception as exc:
                    errors += 1
                    print(
                        f"  [channel-{channel_id}] append_row error: {exc}",
                        file=sys.stderr,
                    )

            STATS.add(len(batch) - errors, errors)

            if sleep_per_batch > 0:
                _STOP_EVENT.wait(timeout=sleep_per_batch)

        print(f"  [channel-{channel_id}] closing.")


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
                   help=f"Parallel channels (default: {config.NUM_CHANNELS})")
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

    num_channels   = args.channels
    rows_target    = args.rows
    rows_per_batch = config.BATCH_SIZE

    # Compute per-channel sleep between batches to hit target throughput
    if args.rate > 0:
        rows_per_channel_per_sec = args.rate / num_channels
        sleep_per_batch = rows_per_batch / rows_per_channel_per_sec
    else:
        sleep_per_batch = 0.0

    print("=" * 60)
    print(" Summit 2026 – Arcade Scores Snowpipe Streamer")
    print("=" * 60)
    print(f"  Account   : {config.SNOWFLAKE_ACCOUNT}")
    print(f"  Database  : {config.SNOWFLAKE_DATABASE}.{config.SNOWFLAKE_SCHEMA}")
    print(f"  Pipe      : {config.SNOWFLAKE_PIPE}")
    print(f"  Channels  : {num_channels}")
    print(f"  Target    : {args.rate if args.rate > 0 else 'unlimited'} rows/sec")
    print(f"  Stop after: {rows_target if rows_target else 'Ctrl-C'} rows")
    print(f"  Profile   : {args.profile}")
    print("=" * 60)

    start_time = time.monotonic()

    with StreamingIngestClient(
        client_name  = f"ARCADE_CLIENT_{uuid.uuid4().hex[:8].upper()}",
        db_name      = config.SNOWFLAKE_DATABASE,
        schema_name  = config.SNOWFLAKE_SCHEMA,
        pipe_name    = config.SNOWFLAKE_PIPE,
        profile_json = args.profile,
    ) as client:
        print(f"\nConnected to Snowflake. Opening {num_channels} channel(s)...\n")

        # Start stats printer
        printer = threading.Thread(
            target=stats_printer,
            args=(config.STATS_INTERVAL_SEC, start_time),
            daemon=True,
        )
        printer.start()

        # Start channel workers
        workers: list[threading.Thread] = []
        for i in range(num_channels):
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
            print("\n\nCtrl-C received – shutting down channels...")
            _STOP_EVENT.set()
            for w in workers:
                w.join(timeout=10)

    elapsed = time.monotonic() - start_time
    print("\n" + "=" * 60)
    print(f"  Total rows ingested : {STATS.total_rows:,}")
    print(f"  Total errors        : {STATS.total_errors:,}")
    print(f"  Elapsed time        : {elapsed:.1f}s")
    print(f"  Average throughput  : {STATS.total_rows / elapsed:.1f} rows/sec")
    print("=" * 60)


if __name__ == "__main__":
    main()
