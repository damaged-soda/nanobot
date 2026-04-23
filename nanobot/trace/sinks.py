"""Trace sinks: stdout / file / null. All synchronous, one-line-per-event JSONL."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from nanobot.trace.core import Event


class Sink(Protocol):
    def write(self, event: "Event") -> None: ...


class ConsoleSink:
    """JSONL to stderr. stderr is the conventional observability stream and
    does not clash with the CLI's rich-rendered stdout output."""

    def write(self, event: "Event") -> None:
        sys.stderr.write(event.to_json() + "\n")
        sys.stderr.flush()


class FileSink:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self._path, "a", encoding="utf-8")

    def write(self, event: "Event") -> None:
        self._f.write(event.to_json() + "\n")
        self._f.flush()

    def close(self) -> None:
        try:
            self._f.close()
        except Exception:
            pass


class NullSink:
    def write(self, event: "Event") -> None:
        return


def register_default_sinks(sinks: list[Sink]) -> None:
    """Register sinks from environment variables. No env vars → no sinks."""
    if os.environ.get("NANOBOT_TRACE"):
        sinks.append(ConsoleSink())
    file_path = os.environ.get("NANOBOT_TRACE_FILE")
    if file_path:
        sinks.append(FileSink(file_path))
