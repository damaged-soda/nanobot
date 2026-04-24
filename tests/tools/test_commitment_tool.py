"""Phase 1 Step 3 的 commitment 工具测试：
create_commitment / revoke_commitment / list_commitments 三个 LLM tool。

重点覆盖：
- 成功路径的返回值和持久化效果
- 错误路径（空参、未知 job / commitment）
- trace 事件发射（kind、payload 字段、trace_id 贯穿）
"""

from __future__ import annotations

import pytest

from nanobot.agent.tools.commitment import (
    CreateCommitmentTool,
    ListCommitmentsTool,
    RevokeCommitmentTool,
)
from nanobot.cron.service import CronService
from nanobot.cron.types import (
    CronJob,
    CronJobState,
    CronPayload,
    CronSchedule,
    CronStore,
)
from nanobot.trace import context as trace_context, init_run
from nanobot.trace.core import Event, _reset_for_test, _sinks_for_test


class _ListSink:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def write(self, event: Event) -> None:
        self.events.append(event)


def _make_job(service: CronService, job_id: str = "j1") -> None:
    service._store = CronStore(jobs=[
        CronJob(
            id=job_id,
            name=f"job-{job_id}",
            schedule=CronSchedule(kind="every", every_ms=60_000),
            payload=CronPayload(kind="agent_turn", message="hi"),
            state=CronJobState(),
        ),
    ])
    service._save_store()


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
    svc = CronService(tmp_path / "cron" / "jobs.json")
    _make_job(svc)
    return svc


# -------- CreateCommitmentTool --------

async def test_create_commitment_success(service, sink):
    tool = CreateCommitmentTool(service)
    with trace_context(trace_id="trace-create"):
        result = await tool.execute(job_id="j1", text="未来不要神经科学")

    # 返回字符串应包含新生成的 id 和 job_id
    job = service.get_job("j1")
    assert len(job.commitments) == 1
    new_id = job.commitments[0].id
    assert new_id in result
    assert "j1" in result
    assert job.commitments[0].text == "未来不要神经科学"
    assert job.commitments[0].origin == "user_request"
    assert job.commitments[0].source_trace_id == "trace-create"
    assert job.commitments[0].status == "active"


async def test_create_commitment_emits_trace(service, sink):
    tool = CreateCommitmentTool(service)
    with trace_context(trace_id="trace-create"):
        await tool.execute(job_id="j1", text="X" * 42, origin="llm_inference")

    created = [e for e in sink.events if e.kind == "commitment.created"]
    assert len(created) == 1
    e = created[0]
    assert e.trace_id == "trace-create"
    assert e.payload["job_id"] == "j1"
    assert e.payload["origin"] == "llm_inference"
    assert e.payload["text_len"] == 42
    assert "commitment_id" in e.payload


async def test_create_commitment_trims_text(service, sink):
    tool = CreateCommitmentTool(service)
    await tool.execute(job_id="j1", text="   规则   \n")
    c = service.get_job("j1").commitments[0]
    assert c.text == "规则"


async def test_create_commitment_empty_text_rejected(service, sink):
    tool = CreateCommitmentTool(service)
    result = await tool.execute(job_id="j1", text="   ")
    assert result.startswith("Error:")
    assert service.get_job("j1").commitments == []


async def test_create_commitment_unknown_job(service, sink):
    tool = CreateCommitmentTool(service)
    result = await tool.execute(job_id="ghost", text="rule")
    assert "Error" in result
    assert "ghost" in result


async def test_create_commitment_invalid_origin(service, sink):
    tool = CreateCommitmentTool(service)
    result = await tool.execute(job_id="j1", text="rule", origin="bogus")
    assert result.startswith("Error")
    assert "bogus" in result


# -------- RevokeCommitmentTool --------

async def test_revoke_commitment_success(service, sink):
    created = service.add_commitment("j1", text="rule")
    tool = RevokeCommitmentTool(service)
    result = await tool.execute(job_id="j1", commitment_id=created.id, reason="不要了")

    assert created.id in result
    assert "revoked" in result
    reloaded = service.get_job("j1").commitments[0]
    assert reloaded.status == "revoked"
    assert reloaded.revoked_reason == "不要了"


async def test_revoke_commitment_emits_trace(service, sink):
    created = service.add_commitment("j1", text="rule")
    tool = RevokeCommitmentTool(service)
    with trace_context(trace_id="trace-revoke"):
        await tool.execute(job_id="j1", commitment_id=created.id, reason="reason")

    events = [e for e in sink.events if e.kind == "commitment.revoked"]
    assert len(events) == 1
    e = events[0]
    assert e.trace_id == "trace-revoke"
    assert e.payload["job_id"] == "j1"
    assert e.payload["commitment_id"] == created.id
    assert e.payload["status"] == "revoked"
    assert e.payload["has_reason"] is True


async def test_revoke_commitment_without_reason(service, sink):
    created = service.add_commitment("j1", text="rule")
    tool = RevokeCommitmentTool(service)
    await tool.execute(job_id="j1", commitment_id=created.id)

    events = [e for e in sink.events if e.kind == "commitment.revoked"]
    assert events[0].payload["has_reason"] is False


async def test_revoke_commitment_unknown(service, sink):
    tool = RevokeCommitmentTool(service)
    assert "Error" in await tool.execute(job_id="j1", commitment_id="ghost")
    assert "Error" in await tool.execute(job_id="ghost", commitment_id="x")


async def test_revoke_commitment_idempotent(service, sink):
    """重复 revoke 不应再发 trace 出问题——service 层返回同一 commitment。"""
    created = service.add_commitment("j1", text="rule")
    tool = RevokeCommitmentTool(service)
    r1 = await tool.execute(job_id="j1", commitment_id=created.id, reason="一")
    r2 = await tool.execute(job_id="j1", commitment_id=created.id, reason="二")
    assert "revoked" in r1
    assert "revoked" in r2
    # 两次都会发 trace——这是工具层契约：每次调用都发一次 trace
    revoked_events = [e for e in sink.events if e.kind == "commitment.revoked"]
    assert len(revoked_events) == 2


# -------- ListCommitmentsTool --------

async def test_list_commitments_empty(service, sink):
    tool = ListCommitmentsTool(service)
    result = await tool.execute(job_id="j1")
    assert "No commitments" in result
    assert "j1" in result


async def test_list_commitments_active_only_by_default(service, sink):
    a = service.add_commitment("j1", text="A")
    b = service.add_commitment("j1", text="B")
    service.revoke_commitment("j1", b.id)

    tool = ListCommitmentsTool(service)
    result = await tool.execute(job_id="j1")
    assert "1 commitment" in result
    assert a.id in result
    assert b.id not in result
    assert "A" in result


async def test_list_commitments_all(service, sink):
    a = service.add_commitment("j1", text="A")
    b = service.add_commitment("j1", text="B")
    service.revoke_commitment("j1", b.id)

    tool = ListCommitmentsTool(service)
    result = await tool.execute(job_id="j1", status="all")
    assert "2 commitment" in result
    assert a.id in result
    assert b.id in result


async def test_list_commitments_status_filter(service, sink):
    a = service.add_commitment("j1", text="A")
    b = service.add_commitment("j1", text="B")
    service.revoke_commitment("j1", b.id)

    tool = ListCommitmentsTool(service)
    revoked_result = await tool.execute(job_id="j1", status="revoked")
    assert b.id in revoked_result
    assert a.id not in revoked_result


async def test_list_commitments_invalid_status(service, sink):
    tool = ListCommitmentsTool(service)
    assert "Error" in await tool.execute(job_id="j1", status="bogus")


async def test_list_commitments_is_read_only(service):
    assert ListCommitmentsTool(service).read_only is True


async def test_create_and_revoke_are_not_read_only(service):
    assert CreateCommitmentTool(service).read_only is False
    assert RevokeCommitmentTool(service).read_only is False
