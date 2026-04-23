"""North-star acceptance test for Phase 0 observability scaffold.

Simulates the CLI → planner → outbound chain with a mocked LLM provider and
asserts the four key events (``channel.received`` / ``planner.entered`` /
``planner.exited`` / ``channel.sent``) land in the trace with a shared
``trace_id``.
"""

from __future__ import annotations

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.cron.service import CronService
from nanobot.cron.types import CronJob, CronJobState, CronPayload, CronSchedule
from nanobot.providers.base import LLMProvider, LLMResponse
from nanobot.trace import context, emit, init_run
from nanobot.trace.core import Event, _reset_for_test, _sinks_for_test


class _MockProvider(LLMProvider):
    """Smallest viable provider: returns a fixed string with no tool calls."""

    def __init__(self, response_text: str = "ok") -> None:
        super().__init__()
        self._response_text = response_text

    def get_default_model(self) -> str:
        return "mock-model"

    async def chat(self, messages, tools=None, model=None, max_tokens=4096,
                   temperature=0.7, reasoning_effort=None, tool_choice=None):
        return LLMResponse(
            content=self._response_text,
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


class _ListSink:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def write(self, event: Event) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def _reset():
    _reset_for_test()
    yield
    _reset_for_test()


async def test_north_star_cli_chain_shares_trace_id(tmp_path):
    init_run("test-run")
    sink = _ListSink()
    _sinks_for_test().clear()
    _sinks_for_test().append(sink)

    bus = MessageBus()
    provider = _MockProvider(response_text="ok")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        model="mock-model",
        max_iterations=3,
    )

    # --- Producer side (CLI) ---
    with context() as producer_trace_id:
        emit("channel.received", channel="cli", content_len=len("hi"))
        msg = InboundMessage(
            channel="cli",
            sender_id="user",
            chat_id="direct",
            content="hi",
            trace_id=producer_trace_id,
        )

    # --- AgentLoop consumer side ---
    # Simulates one iteration of AgentLoop.run() pulling the msg + dispatching.
    await agent._dispatch(msg)

    # --- Outbound consumer side (channel.sent) ---
    # Mirrors cli/commands.py:_consume_outbound: rebind trace_context from
    # msg.trace_id, emit channel.sent for user-facing messages (skip progress).
    while not bus.outbound.empty():
        out_msg = bus.outbound.get_nowait()
        if out_msg.metadata.get("_progress"):
            continue
        with context(trace_id=out_msg.trace_id):
            emit(
                "channel.sent",
                channel=out_msg.channel,
                chat_id=out_msg.chat_id,
                content_len=len(out_msg.content or ""),
            )

    # --- Assertions ---
    kinds = [e.kind for e in sink.events]
    required = {"channel.received", "planner.entered", "planner.exited", "channel.sent"}
    missing = required - set(kinds)
    assert not missing, f"missing event kinds: {missing}; got: {kinds}"

    trace_ids = {
        e.trace_id
        for e in sink.events
        if e.kind in required
    }
    assert trace_ids == {producer_trace_id}, (
        f"events in the required set have split trace_ids: {trace_ids} "
        f"(expected only {producer_trace_id}); events: {[(e.kind, e.trace_id) for e in sink.events]}"
    )


async def test_cron_fired_propagates_trace_id_to_planner(tmp_path):
    """Cron path: ``cron.fired`` + downstream ``planner.*`` events share the
    trace_id auto-generated inside ``CronService._execute_job``. Covers the
    contextvar-inheritance path (no ``_dispatch`` rebinding here — cron calls
    ``agent.process_direct`` directly)."""
    init_run("test-run")
    sink = _ListSink()
    _sinks_for_test().clear()
    _sinks_for_test().append(sink)

    bus = MessageBus()
    provider = _MockProvider(response_text="cron-ok")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        model="mock-model",
        max_iterations=3,
    )

    cron = CronService(store_path=tmp_path / "cron.json")

    async def on_job(job: CronJob) -> str | None:
        await agent.process_direct(
            f"Task '{job.name}' triggered",
            session_key=f"cron:{job.id}",
            channel="cli",
            chat_id="direct",
        )
        return None

    cron.on_job = on_job

    job = CronJob(
        id="test-job",
        name="test-reminder",
        enabled=True,
        schedule=CronSchedule(kind="every", every_ms=60_000),
        payload=CronPayload(kind="agent_turn", message="test"),
        state=CronJobState(),
    )

    # Manually populate the in-memory store so _execute_job's post-run
    # bookkeeping (one-shot cleanup / next_run recompute) has something to
    # work against. The cron scheduler itself isn't started here.
    from nanobot.cron.types import CronStore
    cron._store = CronStore(jobs=[job])

    await cron._execute_job(job)

    kinds = [e.kind for e in sink.events]
    required = {"cron.fired", "planner.entered", "planner.exited"}
    missing = required - set(kinds)
    assert not missing, f"missing event kinds: {missing}; got: {kinds}"

    trace_ids = {e.trace_id for e in sink.events if e.kind in required}
    assert len(trace_ids) == 1 and None not in trace_ids, (
        f"cron chain trace_ids diverged: {trace_ids}; "
        f"events: {[(e.kind, e.trace_id) for e in sink.events]}"
    )
