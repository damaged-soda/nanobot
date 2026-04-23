"""Trace scaffold: event structure + emit + contextvar-propagated run_id / trace_id.

Sinks are env-gated so importing this module is side-effect free for the CLI:
- ``NANOBOT_TRACE=1``         → JSONL to stderr (conventional observability stream)
- ``NANOBOT_TRACE_FILE=path`` → JSONL appended to *path*

Phase 0 contract: top-level event fields (``ts``, ``run_id``, ``trace_id``,
``kind``) are stable; ``payload`` is intentionally loose.
"""

from nanobot.trace.core import (
    Event,
    context,
    emit,
    get_run_id,
    get_trace_id,
    init_run,
)

__all__ = [
    "Event",
    "context",
    "emit",
    "get_run_id",
    "get_trace_id",
    "init_run",
]
