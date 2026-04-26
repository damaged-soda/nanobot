"""Phase 1 Step 7 — SimulateJobRunTool 单测。

把 Step 4 (prompt builder) + Step 5 (recorder) + Step 6 (verify) 串起来，
测试覆盖：
- 错误路径：未知 job
- 无 active commitments：outputs 报但 verdicts 空
- 有 commitments + 有 output → 走 verify，pass / fail / 多条混合
- 有 commitments 但无 output → 跳过 verify 给出明确说明
- 走 MessageTool 的 outputs vs 走 final response 的 fallback
- trace 事件：job.simulated 一次 + verification.completed 每条 commitment 一次
- trace_id 通过 contextvar 串起整条链路
- prompt 构造与 build_cron_reminder_note 一致（live/simulate 同构的硬要求）
"""

from __future__ import annotations

from typing import Any

import pytest

from nanobot.agent.tools.simulate import SimulateJobRunTool
from nanobot.bus.events import OutboundMessage
from nanobot.cron.prompt import build_cron_reminder_note
from nanobot.cron.service import CronService
from nanobot.cron.types import (
    CronJob,
    CronJobState,
    CronPayload,
    CronSchedule,
    CronStore,
)
from nanobot.providers.base import LLMProvider, LLMResponse
from nanobot.simulate import current_recorder
from nanobot.trace import context as trace_context, init_run
from nanobot.trace.core import Event, _reset_for_test, _sinks_for_test


# -------- 测试器材 --------

class _ListSink:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def write(self, event: Event) -> None:
        self.events.append(event)


class _ScriptedProvider(LLMProvider):
    """按队列吐 LLMResponse；同时记录每次调用的 messages 便于断言。"""

    def __init__(self, responses: list[LLMResponse]) -> None:
        super().__init__()
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def chat(self, *args: Any, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        if not self._responses:
            return LLMResponse(content='{"passed": true, "detail": null}', tool_calls=[])
        return self._responses.pop(0)

    def get_default_model(self) -> str:
        return "test-model"


def _make_job(
    service: CronService,
    job_id: str = "j1",
    name: str = "Morning briefing",
    payload_msg: str = "Send morning briefing",
    commitments: list | None = None,
) -> CronJob:
    job = CronJob(
        id=job_id,
        name=name,
        schedule=CronSchedule(kind="every", every_ms=60_000),
        payload=CronPayload(kind="agent_turn", message=payload_msg),
        state=CronJobState(),
        commitments=list(commitments or []),
    )
    service._store = CronStore(jobs=[job])
    service._save_store()
    return job


@pytest.fixture(autouse=True)
def _reset_trace():
    _reset_for_test()
    init_run("test-run")
    yield
    _reset_for_test()


@pytest.fixture
def sink() -> _ListSink:
    _sinks_for_test().clear()
    s = _ListSink()
    _sinks_for_test().append(s)
    return s


@pytest.fixture
def service(tmp_path) -> CronService:
    return CronService(tmp_path / "cron" / "jobs.json")


def _make_process_direct(outputs: list[str] | None = None, response_content: str | None = None):
    """构造一个假的 process_direct：

    - 若给了 outputs，则在 simulate_scope 内向 current_recorder() 推 outbound
      （模拟 agent 调 MessageTool 发送的真实路径）。
    - response_content 模拟 agent 的最终回复内容（fallback evidence）。
    """
    captured_prompts: list[str] = []
    captured_kwargs: list[dict[str, Any]] = []

    async def fake(prompt: str, **kwargs: Any) -> OutboundMessage | None:
        captured_prompts.append(prompt)
        captured_kwargs.append(kwargs)
        if outputs:
            recorder = current_recorder()
            assert recorder is not None, "process_direct 应该在 simulate_scope 内被调"
            for out in outputs:
                recorder.record(OutboundMessage(channel="cli", chat_id="u1", content=out))
        if response_content is not None:
            return OutboundMessage(channel="cli", chat_id="u1", content=response_content)
        return None

    fake.captured_prompts = captured_prompts  # type: ignore[attr-defined]
    fake.captured_kwargs = captured_kwargs  # type: ignore[attr-defined]
    return fake


def _verify_response(passed: bool, detail: str | None = None) -> LLMResponse:
    import json
    return LLMResponse(
        content=json.dumps({"passed": passed, "detail": detail}),
        tool_calls=[],
    )


# -------- 测试 --------

async def test_unknown_job_returns_error(service, sink):
    tool = SimulateJobRunTool(
        cron_service=service,
        process_direct=_make_process_direct(),
        provider=_ScriptedProvider([]),
        model="m",
    )
    result = await tool.execute(job_id="ghost")
    assert result.startswith("Error")
    assert "ghost" in result


async def test_empty_job_id_returns_error(service, sink):
    tool = SimulateJobRunTool(
        cron_service=service,
        process_direct=_make_process_direct(),
        provider=_ScriptedProvider([]),
        model="m",
    )
    result = await tool.execute(job_id="")
    assert result.startswith("Error")


async def test_no_commitments_runs_but_no_verdicts(service, sink):
    _make_job(service)
    pd = _make_process_direct(outputs=["briefing text"])
    provider = _ScriptedProvider([])
    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=provider, model="m",
    )

    result = await tool.execute(job_id="j1")

    assert "Simulated job 'Morning briefing'" in result
    assert "briefing text" in result
    assert "no active commitments" in result
    # 没有 commitments，verify 不该被调
    assert provider.calls == []


async def test_passes_all_commitments(service, sink):
    job = _make_job(service)
    service.add_commitment("j1", text="不要包含神经科学")
    service.add_commitment("j1", text="控制在 300 字以内")

    pd = _make_process_direct(outputs=["safe briefing"])
    provider = _ScriptedProvider([
        _verify_response(True),
        _verify_response(True),
    ])
    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=provider, model="m",
    )

    result = await tool.execute(job_id="j1")

    assert "2/2 passed" in result
    assert "pass:" in result
    assert "fail:" not in result
    # verify 被调用两次（每条 commitment 一次）
    assert len(provider.calls) == 2
    # evidence 是捕获到的 outputs 拼接
    for call in provider.calls:
        assert "safe briefing" in call["messages"][0]["content"]


async def test_mixed_pass_fail_verdicts(service, sink):
    _make_job(service)
    service.add_commitment("j1", text="rule A")
    service.add_commitment("j1", text="rule B")

    pd = _make_process_direct(outputs=["some output"])
    provider = _ScriptedProvider([
        _verify_response(True),
        _verify_response(False, "violates B"),
    ])
    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=provider, model="m",
    )

    result = await tool.execute(job_id="j1")

    assert "1/2 passed" in result
    assert "fail:" in result
    assert "violates B" in result


async def test_revoked_commitments_excluded_from_verification(service, sink):
    _make_job(service)
    active_c = service.add_commitment("j1", text="active rule")
    revoked_c = service.add_commitment("j1", text="revoked rule")
    service.revoke_commitment("j1", revoked_c.id)

    pd = _make_process_direct(outputs=["output"])
    provider = _ScriptedProvider([_verify_response(True)])
    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=provider, model="m",
    )

    result = await tool.execute(job_id="j1")

    # 只对 active 的那一条 verify
    assert len(provider.calls) == 1
    assert "1/1 passed" in result
    # 输出里也只列 active，不出现 revoked rule 文本
    assert "active rule" in result
    assert "revoked rule" not in result


async def test_fallback_to_response_content_when_no_capture(service, sink):
    """agent 没走 MessageTool，但 process_direct 返回了 final response → 用它当 evidence。"""
    _make_job(service)
    service.add_commitment("j1", text="rule")

    pd = _make_process_direct(outputs=None, response_content="final response text")
    provider = _ScriptedProvider([_verify_response(True)])
    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=provider, model="m",
    )

    result = await tool.execute(job_id="j1")

    assert "final response text" in result
    # verify 被喂的 evidence 应是 fallback
    assert "final response text" in provider.calls[0]["messages"][0]["content"]


async def test_no_output_skips_verification(service, sink):
    """既没走 MessageTool 又没 final response → verdicts 跳过，明确说明而不是默认 pass。"""
    _make_job(service)
    service.add_commitment("j1", text="rule")

    pd = _make_process_direct(outputs=None, response_content=None)
    provider = _ScriptedProvider([])
    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=provider, model="m",
    )

    result = await tool.execute(job_id="j1")

    assert "none captured" in result
    assert "skipped" in result
    # 不能 silently pass
    assert "passed" not in result.split("Verdicts")[1] if "Verdicts" in result else True
    assert provider.calls == []


async def test_emits_job_simulated_and_verification_completed_traces(service, sink):
    _make_job(service)
    c1 = service.add_commitment("j1", text="rule 1")
    c2 = service.add_commitment("j1", text="rule 2")

    pd = _make_process_direct(outputs=["output"])
    provider = _ScriptedProvider([
        _verify_response(True),
        _verify_response(False, "no good"),
    ])
    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=provider, model="m",
    )

    with trace_context(trace_id="trace-sim"):
        await tool.execute(job_id="j1")

    job_simulated = [e for e in sink.events if e.kind == "job.simulated"]
    assert len(job_simulated) == 1
    assert job_simulated[0].trace_id == "trace-sim"
    assert job_simulated[0].payload["job_id"] == "j1"
    assert job_simulated[0].payload["job_name"] == "Morning briefing"
    assert job_simulated[0].payload["commitments_count"] == 2

    verifications = [e for e in sink.events if e.kind == "verification.completed"]
    assert len(verifications) == 2
    assert all(e.trace_id == "trace-sim" for e in verifications)
    assert verifications[0].payload == {
        "commitment_id": c1.id,
        "run_kind": "simulate",
        "verdict": "pass",
        "has_detail": False,
    }
    assert verifications[1].payload == {
        "commitment_id": c2.id,
        "run_kind": "simulate",
        "verdict": "fail",
        "has_detail": True,
    }


async def test_prompt_matches_live_reminder_note(service, sink):
    """live cron 和 simulate 必须用同一份 prompt——这条断言不可妥协，
    任何偏移都让 simulate 的判决失去意义。"""
    job = _make_job(service)
    service.add_commitment("j1", text="some rule")

    pd = _make_process_direct(outputs=["output"])
    provider = _ScriptedProvider([_verify_response(True)])
    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=provider, model="m",
    )
    await tool.execute(job_id="j1")

    sent_prompt = pd.captured_prompts[0]  # type: ignore[attr-defined]
    expected = build_cron_reminder_note(service.get_job("j1"))
    assert sent_prompt == expected


async def test_session_key_isolates_simulate(service, sink):
    """simulate 必须用独立 session_key，避免污染 user / 真 cron 的会话。"""
    _make_job(service)
    pd = _make_process_direct(outputs=["x"])
    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=_ScriptedProvider([]), model="m",
    )
    await tool.execute(job_id="j1")

    kwargs = pd.captured_kwargs[0]  # type: ignore[attr-defined]
    assert kwargs["session_key"] == "simulate:j1"


async def test_channel_chat_id_match_payload(service, sink):
    """simulate 用 job.payload 的 channel/to，与 live cron 路径一致。"""
    job = CronJob(
        id="j2",
        name="WhatsApp briefing",
        schedule=CronSchedule(kind="every", every_ms=60_000),
        payload=CronPayload(kind="agent_turn", message="hi", channel="whatsapp", to="+12345"),
        state=CronJobState(),
    )
    service._store = CronStore(jobs=[job])
    service._save_store()

    pd = _make_process_direct(outputs=["x"])
    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=_ScriptedProvider([]), model="m",
    )
    await tool.execute(job_id="j2")

    kwargs = pd.captured_kwargs[0]  # type: ignore[attr-defined]
    assert kwargs["channel"] == "whatsapp"
    assert kwargs["chat_id"] == "+12345"


async def test_long_output_is_truncated_in_result_string(service, sink):
    _make_job(service)
    long_text = "x" * 1000
    pd = _make_process_direct(outputs=[long_text])
    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=_ScriptedProvider([]), model="m",
    )
    result = await tool.execute(job_id="j1")

    assert "(truncated)" in result
    # 不应把完整 1000 字塞进结果串
    assert "x" * 600 not in result


async def test_recorder_scope_is_active_during_process_direct(service, sink):
    """硬不变式：process_direct 调用时 simulate_scope 是激活的，
    退出后 current_recorder() 必须回到 None。"""
    _make_job(service)
    state: dict[str, Any] = {}

    async def pd(prompt: str, **kwargs: Any):
        state["recorder_inside"] = current_recorder()
        return None

    tool = SimulateJobRunTool(
        cron_service=service, process_direct=pd, provider=_ScriptedProvider([]), model="m",
    )
    await tool.execute(job_id="j1")

    assert state["recorder_inside"] is not None
    assert current_recorder() is None
