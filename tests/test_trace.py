"""Tests for nanobot.trace — event structure, emit, contextvar, sinks."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from nanobot.trace import context, emit, init_run
from nanobot.trace.core import Event, _reset_for_test, _sinks_for_test
from nanobot.trace.sinks import ConsoleSink, FileSink, NullSink


class ListSink:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def write(self, event: Event) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def _reset():
    _reset_for_test()
    yield
    _reset_for_test()


@pytest.fixture
def sink() -> ListSink:
    init_run("test-run")
    _sinks_for_test().clear()
    s = ListSink()
    _sinks_for_test().append(s)
    return s


def test_event_json_roundtrip():
    event = Event(
        ts="2026-04-22T12:00:00+00:00",
        run_id="r1",
        trace_id="t1",
        kind="channel.received",
        payload={"channel": "cli", "user_id": "u", "content_len": 3},
    )
    decoded = json.loads(event.to_json())
    assert decoded == {
        "ts": "2026-04-22T12:00:00+00:00",
        "run_id": "r1",
        "trace_id": "t1",
        "kind": "channel.received",
        "payload": {"channel": "cli", "user_id": "u", "content_len": 3},
    }


def test_emit_outside_context_has_null_trace_id(sink: ListSink):
    emit("boot.started", version="0.1")
    assert len(sink.events) == 1
    e = sink.events[0]
    assert e.run_id == "test-run"
    assert e.trace_id is None
    assert e.kind == "boot.started"
    assert e.payload == {"version": "0.1"}


def test_emit_auto_initializes_run_id(sink: ListSink):
    # _reset fixture wipes state; fixture re-initializes with "test-run"
    # so we explicitly wipe again to test auto-init.
    _reset_for_test()
    _sinks_for_test().clear()
    _sinks_for_test().append(sink)
    emit("boot.auto")
    assert sink.events[0].run_id  # some non-empty uuid


def test_context_binds_and_restores(sink: ListSink):
    with context(trace_id="abc"):
        emit("channel.received", channel="cli")
    emit("after.context")
    assert [e.trace_id for e in sink.events] == ["abc", None]


def test_context_generates_uuid_when_none(sink: ListSink):
    with context() as tid:
        assert tid
        emit("planner.entered")
    assert sink.events[0].trace_id == tid


def test_context_nested(sink: ListSink):
    with context(trace_id="outer"):
        emit("a")
        with context(trace_id="inner"):
            emit("b")
        emit("c")
    assert [(e.kind, e.trace_id) for e in sink.events] == [
        ("a", "outer"),
        ("b", "inner"),
        ("c", "outer"),
    ]


async def test_context_does_not_leak_across_async_tasks(sink: ListSink):
    """Concurrent tasks must each see their own trace_id."""

    async def work(label: str) -> None:
        with context(trace_id=label):
            await asyncio.sleep(0.01)
            emit("work.tick", label=label)

    await asyncio.gather(work("alpha"), work("beta"))
    by_label = {e.payload["label"]: e.trace_id for e in sink.events}
    assert by_label == {"alpha": "alpha", "beta": "beta"}


async def test_trace_id_propagates_via_message_field(sink: ListSink):
    """Producer binds trace_id and stashes it on a message; consumer in a separate
    task rebinds from the field. This is the pattern Phase 0 uses to cross the
    bus / agent-loop asyncio.Queue boundary (where contextvars don't propagate)."""
    from dataclasses import dataclass

    @dataclass
    class Msg:
        trace_id: str | None = None

    queue: asyncio.Queue[Msg] = asyncio.Queue()

    with context() as producer_tid:
        emit("channel.received")
        await queue.put(Msg(trace_id=producer_tid))

    async def consumer() -> None:
        msg = await queue.get()
        with context(trace_id=msg.trace_id):
            emit("planner.entered")

    await asyncio.create_task(consumer())

    assert [e.kind for e in sink.events] == ["channel.received", "planner.entered"]
    assert sink.events[0].trace_id == sink.events[1].trace_id
    assert sink.events[0].trace_id is not None


def test_file_sink_writes_jsonl(tmp_path: Path):
    path = tmp_path / "trace.jsonl"
    init_run("r-file")
    _sinks_for_test().clear()
    _sinks_for_test().append(FileSink(path))

    with context(trace_id="t1"):
        emit("channel.received", channel="cli")
        emit("channel.sent", channel="cli")

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    payloads = [json.loads(line) for line in lines]
    assert payloads[0]["kind"] == "channel.received"
    assert payloads[1]["kind"] == "channel.sent"
    assert all(p["trace_id"] == "t1" for p in payloads)
    assert all(p["run_id"] == "r-file" for p in payloads)


def test_null_sink_is_silent():
    init_run("r-null")
    _sinks_for_test().clear()
    _sinks_for_test().append(NullSink())
    emit("noop")  # must not raise


def test_console_sink_writes_to_stderr(capsys):
    init_run("r-console")
    _sinks_for_test().clear()
    _sinks_for_test().append(ConsoleSink())
    with context(trace_id="t"):
        emit("channel.received", channel="cli")
    captured = capsys.readouterr()
    assert captured.out == ""  # stdout must stay clean for CLI rendering
    payload = json.loads(captured.err.strip())
    assert payload["kind"] == "channel.received"
    assert payload["trace_id"] == "t"


def test_sink_exception_does_not_break_emit(sink: ListSink):
    class BadSink:
        def write(self, event: Event) -> None:
            raise RuntimeError("boom")

    _sinks_for_test().insert(0, BadSink())
    emit("still.works")
    assert len(sink.events) == 1


def test_env_enables_console_sink(monkeypatch, capsys):
    _reset_for_test()
    monkeypatch.setenv("NANOBOT_TRACE", "1")
    init_run("r-env")
    emit("env.on")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err.strip())["kind"] == "env.on"


def test_env_enables_file_sink(monkeypatch, tmp_path: Path):
    _reset_for_test()
    path = tmp_path / "out.jsonl"
    monkeypatch.setenv("NANOBOT_TRACE_FILE", str(path))
    init_run("r-env-file")
    emit("file.on")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["kind"] == "file.on"


def test_no_env_means_no_sinks():
    # _reset fixture wipes; no NANOBOT_TRACE_* env vars set for this test
    init_run("r-clean")
    assert _sinks_for_test() == []
    emit("silent")  # must not raise even with zero sinks
