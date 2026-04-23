"""Phase 1 Step 2 的 commitment 相关测试：
CronJob.commitments 字段的序列化往返、旧 jobs.json 兼容加载，以及
CronService 上的 CRUD 方法（add / revoke / list）。

verification 是日志，不写回 commitment——见 PLAN 的 Scope 说明。
CommitmentVerificationRecord 类型留给 simulate_job_run 的返回值使用。"""

from __future__ import annotations

import json

from nanobot.cron.service import CronService
from nanobot.cron.types import (
    Commitment,
    CronJob,
    CronJobState,
    CronPayload,
    CronSchedule,
    CronStore,
)


def _make_job(
    job_id: str = "j1",
    commitments: list[Commitment] | None = None,
) -> CronJob:
    return CronJob(
        id=job_id,
        name=f"job-{job_id}",
        schedule=CronSchedule(kind="every", every_ms=60_000),
        payload=CronPayload(kind="agent_turn", message="hello"),
        state=CronJobState(),
        commitments=commitments or [],
    )


# -------- 序列化往返 --------

def test_job_without_commitments_serializes_with_empty_list(tmp_path):
    svc = CronService(tmp_path / "cron" / "jobs.json")
    svc._store = CronStore(jobs=[_make_job()])
    svc._save_store()

    data = json.loads((tmp_path / "cron" / "jobs.json").read_text())
    assert data["jobs"][0]["commitments"] == []


def test_commitment_full_roundtrip(tmp_path):
    """commitment 所有配置字段写回读完要一致。"""
    svc = CronService(tmp_path / "cron" / "jobs.json")
    c = Commitment(
        id="c1",
        text="未来的新闻不要神经科学",
        origin="user_request",
        status="active",
        created_at_ms=1_779_000_000_000,
        source_trace_id="trace-xxx",
        revoked_at_ms=None,
        revoked_reason=None,
    )
    svc._store = CronStore(jobs=[_make_job(commitments=[c])])
    svc._save_store()

    # 换个 service 重新加载
    svc2 = CronService(tmp_path / "cron" / "jobs.json")
    loaded = svc2._load_store()
    loaded_commitments = loaded.jobs[0].commitments
    assert len(loaded_commitments) == 1
    loaded_c = loaded_commitments[0]
    assert loaded_c == c  # dataclass __eq__ 做 deep compare


def test_revoked_commitment_roundtrip(tmp_path):
    svc = CronService(tmp_path / "cron" / "jobs.json")
    c = Commitment(
        id="c2",
        text="改得更温柔一点",
        origin="user_request",
        status="revoked",
        created_at_ms=1_779_000_000_000,
        revoked_at_ms=1_779_000_100_000,
        revoked_reason="被 c3 替代",
    )
    svc._store = CronStore(jobs=[_make_job(commitments=[c])])
    svc._save_store()

    svc2 = CronService(tmp_path / "cron" / "jobs.json")
    reloaded = svc2._load_store().jobs[0].commitments[0]
    assert reloaded.status == "revoked"
    assert reloaded.revoked_reason == "被 c3 替代"


def test_commitment_json_does_not_include_verification_history(tmp_path):
    """jobs.json 里不能出现 verification_history 字段——日志不应污染配置。"""
    svc = CronService(tmp_path / "cron" / "jobs.json")
    svc._store = CronStore(jobs=[_make_job(commitments=[
        Commitment(id="c1", text="x", created_at_ms=1, origin="user_request"),
    ])])
    svc._save_store()

    raw = (tmp_path / "cron" / "jobs.json").read_text()
    assert "verificationHistory" not in raw
    assert "verification_history" not in raw


# -------- 旧 jobs.json 兼容 --------

def test_load_legacy_jobs_json_without_commitments_field(tmp_path):
    """加载不含 commitments 字段的旧 jobs.json 时不能报错，应默认为 []。"""
    path = tmp_path / "cron" / "jobs.json"
    path.parent.mkdir(parents=True)
    legacy = {
        "version": 1,
        "jobs": [
            {
                "id": "legacy",
                "name": "legacy job",
                "enabled": True,
                "schedule": {"kind": "every", "everyMs": 60000},
                "payload": {
                    "kind": "agent_turn",
                    "message": "hi",
                    "deliver": False,
                    "channel": None,
                    "to": None,
                },
                "state": {
                    "nextRunAtMs": None,
                    "lastRunAtMs": None,
                    "lastStatus": None,
                    "lastError": None,
                    "runHistory": [],
                },
                "createdAtMs": 0,
                "updatedAtMs": 0,
                "deleteAfterRun": False,
                # 故意没有 "commitments" 字段
            }
        ],
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")

    svc = CronService(path)
    store = svc._load_store()
    assert len(store.jobs) == 1
    assert store.jobs[0].commitments == []


# -------- CRUD: add_commitment --------

def test_add_commitment_appends_to_job(tmp_path):
    svc = CronService(tmp_path / "cron" / "jobs.json")
    svc._store = CronStore(jobs=[_make_job("j1")])
    svc._save_store()

    commitment = svc.add_commitment(
        "j1",
        text="不要神经科学",
        origin="user_request",
        source_trace_id="trace-abc",
    )
    assert commitment is not None
    assert commitment.id  # 非空
    assert commitment.text == "不要神经科学"
    assert commitment.status == "active"
    assert commitment.origin == "user_request"
    assert commitment.source_trace_id == "trace-abc"
    assert commitment.created_at_ms > 0

    job = svc.get_job("j1")
    assert len(job.commitments) == 1
    assert job.commitments[0] is commitment


def test_add_commitment_unknown_job_returns_none(tmp_path):
    svc = CronService(tmp_path / "cron" / "jobs.json")
    svc._store = CronStore(jobs=[])
    svc._save_store()
    assert svc.add_commitment("missing", text="x") is None


def test_add_commitment_persists(tmp_path):
    """add 后重新加载，commitment 还在。"""
    path = tmp_path / "cron" / "jobs.json"
    svc = CronService(path)
    svc._store = CronStore(jobs=[_make_job("j1")])
    svc._save_store()

    created = svc.add_commitment("j1", text="规则")
    assert created is not None

    svc2 = CronService(path)
    job = svc2.get_job("j1")
    assert len(job.commitments) == 1
    assert job.commitments[0].id == created.id


# -------- CRUD: revoke_commitment --------

def test_revoke_commitment_flips_status(tmp_path):
    svc = CronService(tmp_path / "cron" / "jobs.json")
    svc._store = CronStore(jobs=[_make_job("j1")])
    svc._save_store()
    created = svc.add_commitment("j1", text="规则")

    revoked = svc.revoke_commitment("j1", created.id, reason="用户改主意")
    assert revoked is not None
    assert revoked.status == "revoked"
    assert revoked.revoked_reason == "用户改主意"
    assert revoked.revoked_at_ms is not None


def test_revoke_commitment_unknown_job_or_commitment(tmp_path):
    svc = CronService(tmp_path / "cron" / "jobs.json")
    svc._store = CronStore(jobs=[_make_job("j1")])
    svc._save_store()
    assert svc.revoke_commitment("missing", "whatever") is None
    assert svc.revoke_commitment("j1", "missing") is None


def test_revoke_already_revoked_is_noop(tmp_path):
    """revoke 已经 revoked 的 commitment 不应再改 revoked_at_ms / reason。"""
    svc = CronService(tmp_path / "cron" / "jobs.json")
    svc._store = CronStore(jobs=[_make_job("j1")])
    svc._save_store()
    created = svc.add_commitment("j1", text="规则")
    first = svc.revoke_commitment("j1", created.id, reason="原因一")
    original_ts = first.revoked_at_ms

    second = svc.revoke_commitment("j1", created.id, reason="原因二")
    assert second.status == "revoked"
    # 原因和时间戳应保持第一次的
    assert second.revoked_reason == "原因一"
    assert second.revoked_at_ms == original_ts


# -------- CRUD: list_commitments --------

def test_list_commitments_default_only_active(tmp_path):
    svc = CronService(tmp_path / "cron" / "jobs.json")
    svc._store = CronStore(jobs=[_make_job("j1")])
    svc._save_store()
    a = svc.add_commitment("j1", text="A")
    b = svc.add_commitment("j1", text="B")
    svc.revoke_commitment("j1", b.id)

    active = svc.list_commitments("j1")
    assert [c.text for c in active] == ["A"]


def test_list_commitments_explicit_status_filter(tmp_path):
    svc = CronService(tmp_path / "cron" / "jobs.json")
    svc._store = CronStore(jobs=[_make_job("j1")])
    svc._save_store()
    a = svc.add_commitment("j1", text="A")
    b = svc.add_commitment("j1", text="B")
    svc.revoke_commitment("j1", b.id)

    revoked = svc.list_commitments("j1", status="revoked")
    assert [c.text for c in revoked] == ["B"]


def test_list_commitments_status_none_returns_all(tmp_path):
    svc = CronService(tmp_path / "cron" / "jobs.json")
    svc._store = CronStore(jobs=[_make_job("j1")])
    svc._save_store()
    svc.add_commitment("j1", text="A")
    b = svc.add_commitment("j1", text="B")
    svc.revoke_commitment("j1", b.id)

    all_c = svc.list_commitments("j1", status=None)
    assert {c.text for c in all_c} == {"A", "B"}


def test_list_commitments_missing_job_returns_empty(tmp_path):
    svc = CronService(tmp_path / "cron" / "jobs.json")
    svc._store = CronStore(jobs=[])
    svc._save_store()
    assert svc.list_commitments("missing") == []
