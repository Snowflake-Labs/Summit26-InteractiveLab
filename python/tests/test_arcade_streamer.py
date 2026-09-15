from concurrent.futures import Future
import sys
import threading
import types

import arcade_streamer


def completed_future(error=None):
    future = Future()
    if error is None:
        future.set_result(None)
    else:
        future.set_exception(error)
    return future


class FakeChannel:
    channel_name = "ELASTIC"

    def __init__(self, future):
        self.future = future
        self.rows = []

    def append_rows_with_wait(self, rows, token):
        self.rows.append(rows)
        return self.future


class FakeClient:
    def __init__(self, future):
        self.channel = FakeChannel(future)

    def get_elastic_channel(self):
        return self.channel


class FakeIngestError(Exception):
    def __init__(self, status):
        self.http_status_code = status


def reset_globals(rows_target):
    arcade_streamer.STATS = arcade_streamer.Stats()
    arcade_streamer._STOP_EVENT.clear()
    arcade_streamer._WORKER_ERROR = None
    return arcade_streamer.RowBudget(rows_target)


def test_failed_acknowledgement_is_not_counted(monkeypatch):
    budget = reset_globals(5)
    failure = RuntimeError("SDK retries exhausted")
    client = FakeClient(completed_future(failure))
    monkeypatch.setattr(
        arcade_streamer, "generate_batch", lambda count: [{"id": index} for index in range(count)]
    )

    arcade_streamer.channel_worker(client, 0, budget, 25, 0)

    assert arcade_streamer.STATS.total_rows == 0
    assert arcade_streamer.STATS.total_errors == 5
    assert arcade_streamer._WORKER_ERROR is failure


def test_row_budget_trims_final_batch(monkeypatch):
    budget = reset_globals(37)
    generated = []

    def generate(count):
        generated.append(count)
        return [{"id": index} for index in range(count)]

    monkeypatch.setattr(arcade_streamer, "generate_batch", generate)
    client = FakeClient(completed_future())

    arcade_streamer.channel_worker(client, 0, budget, 25, 0)

    assert generated == [25, 12]
    assert arcade_streamer.STATS.total_rows == 37


def test_row_budget_is_shared_safely_by_multiple_producers():
    budget = arcade_streamer.RowBudget(37)
    reservations = []
    lock = threading.Lock()

    def reserve_until_empty():
        while True:
            rows = budget.reserve(25)
            if rows == 0:
                return
            with lock:
                reservations.append(rows)

    workers = [threading.Thread(target=reserve_until_empty) for _ in range(4)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert sum(reservations) == 37
    assert all(rows <= 25 for rows in reservations)


def test_synchronous_backpressure_retries_the_same_batch(monkeypatch):
    reset_globals(1)
    rows = [{"id": 1}]
    future = completed_future()
    calls = []

    class BackpressuredChannel:
        def append_rows_with_wait(self, received_rows, token):
            calls.append(received_rows)
            if len(calls) == 1:
                raise FakeIngestError(429)
            return future

    streaming_module = types.SimpleNamespace(StreamingIngestError=FakeIngestError)
    ingest_module = types.SimpleNamespace(streaming=streaming_module)
    snowflake_module = types.SimpleNamespace(ingest=ingest_module)
    monkeypatch.setitem(sys.modules, "snowflake", snowflake_module)
    monkeypatch.setitem(sys.modules, "snowflake.ingest", ingest_module)
    monkeypatch.setitem(sys.modules, "snowflake.ingest.streaming", streaming_module)
    monkeypatch.setattr(arcade_streamer, "BACKPRESSURE_WAIT_SECONDS", 0)

    returned = arcade_streamer._append_with_backpressure_wait(
        BackpressuredChannel(), rows, "batch-1"
    )

    assert returned is future
    assert calls == [rows, rows]
