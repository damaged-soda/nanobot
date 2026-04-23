"""Event structure, emit API, and contextvar propagation."""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

from nanobot.trace.sinks import Sink, register_default_sinks

_run_id_var: ContextVar[str | None] = ContextVar("nanobot_trace_run_id", default=None)
_trace_id_var: ContextVar[str | None] = ContextVar("nanobot_trace_trace_id", default=None)

_sinks: list[Sink] = []
_initialized = False


@dataclass(slots=True, frozen=True)
class Event:
    ts: str
    run_id: str
    trace_id: str | None
    kind: str
    payload: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(
            {
                "ts": self.ts,
                "run_id": self.run_id,
                "trace_id": self.trace_id,
                "kind": self.kind,
                "payload": self.payload,
            },
            ensure_ascii=False,
            default=str,
        )


def init_run(run_id: str | None = None) -> str:
    """Initialize ``run_id`` for the process and register env-gated sinks.

    Idempotent: subsequent calls without *run_id* return the existing one.
    """
    global _initialized
    existing = _run_id_var.get()
    if existing is not None and run_id is None:
        if not _initialized:
            register_default_sinks(_sinks)
            _initialized = True
        return existing
    rid = run_id or uuid.uuid4().hex
    _run_id_var.set(rid)
    if not _initialized:
        register_default_sinks(_sinks)
        _initialized = True
    return rid


def get_run_id() -> str | None:
    return _run_id_var.get()


def get_trace_id() -> str | None:
    return _trace_id_var.get()


@contextmanager
def context(trace_id: str | None = None) -> Iterator[str]:
    """Bind *trace_id* (newly generated if None) for the duration of the block."""
    tid = trace_id or uuid.uuid4().hex
    token = _trace_id_var.set(tid)
    try:
        yield tid
    finally:
        _trace_id_var.reset(token)


def emit(kind: str, **payload: Any) -> None:
    """Emit a trace event with current run_id / trace_id bindings.

    Auto-initializes the run if emit is called before :func:`init_run`.
    Sink exceptions are swallowed — tracing must never break the observed process.
    """
    rid = _run_id_var.get()
    if rid is None:
        rid = init_run()
    event = Event(
        ts=datetime.now(timezone.utc).isoformat(),
        run_id=rid,
        trace_id=_trace_id_var.get(),
        kind=kind,
        payload=payload,
    )
    for sink in _sinks:
        try:
            sink.write(event)
        except Exception:
            pass


def _reset_for_test() -> None:
    """Wipe module state so tests don't leak across each other."""
    global _initialized
    _run_id_var.set(None)
    _trace_id_var.set(None)
    _sinks.clear()
    _initialized = False


def _sinks_for_test() -> list[Sink]:
    """Mutable sink list for tests to swap implementations."""
    return _sinks
