"""Cron types。"""

from dataclasses import dataclass, field
from typing import Literal


# 一条 commitment 是"用户交付的持久规则"（例如"briefing 不要神经科学"）。
# 外壳结构化，text 内容是 prose——LLM 读写承诺都不拆字段。
CommitmentOrigin = Literal["user_request", "llm_inference", "system"]
CommitmentStatus = Literal["active", "revoked", "merged"]

# 下面两个类型在 simulate_job_run 的返回值和 trace event payload 里用到，
# 不写回 Commitment——verification 是日志，不属于配置。
CommitmentRunKind = Literal["simulate", "live"]
CommitmentVerdict = Literal["pass", "fail"]


@dataclass
class CommitmentVerificationRecord:
    """一次验证的结果。作为 simulate_job_run 的返回值结构 / trace event payload
    的一部分存在，**不**落进 jobs.json——日志 / 历史应通过 trace 流式观察，
    不要和配置混在一份 JSON 里。"""
    run_at_ms: int
    run_kind: CommitmentRunKind
    verdict: CommitmentVerdict
    detail: str | None = None


@dataclass
class Commitment:
    """挂在 CronJob 上的一条持久规则。"""
    id: str
    text: str
    origin: CommitmentOrigin = "user_request"
    status: CommitmentStatus = "active"
    created_at_ms: int = 0
    # 创建这条 commitment 时 LLM 那一轮的 trace_id，方便回溯因果。
    source_trace_id: str | None = None
    revoked_at_ms: int | None = None
    revoked_reason: str | None = None


@dataclass
class CronSchedule:
    """Schedule definition for a cron job."""
    kind: Literal["at", "every", "cron"]
    # For "at": timestamp in ms
    at_ms: int | None = None
    # For "every": interval in ms
    every_ms: int | None = None
    # For "cron": cron expression (e.g. "0 9 * * *")
    expr: str | None = None
    # Timezone for cron expressions
    tz: str | None = None


@dataclass
class CronPayload:
    """What to do when the job runs."""
    kind: Literal["system_event", "agent_turn"] = "agent_turn"
    message: str = ""
    # Deliver response to channel
    deliver: bool = False
    channel: str | None = None  # e.g. "whatsapp"
    to: str | None = None  # e.g. phone number


@dataclass
class CronRunRecord:
    """A single execution record for a cron job."""
    run_at_ms: int
    status: Literal["ok", "error", "skipped"]
    duration_ms: int = 0
    error: str | None = None


@dataclass
class CronJobState:
    """Runtime state of a job."""
    next_run_at_ms: int | None = None
    last_run_at_ms: int | None = None
    last_status: Literal["ok", "error", "skipped"] | None = None
    last_error: str | None = None
    run_history: list[CronRunRecord] = field(default_factory=list)


@dataclass
class CronJob:
    """A scheduled job."""
    id: str
    name: str
    enabled: bool = True
    schedule: CronSchedule = field(default_factory=lambda: CronSchedule(kind="every"))
    payload: CronPayload = field(default_factory=CronPayload)
    state: CronJobState = field(default_factory=CronJobState)
    # 可演化的规则层：cron 每次执行时把 active commitments 叠加到 prompt。
    # β 阶段稳定 commitment 可以被"毕业"到 payload.message 里并标 merged。
    commitments: list[Commitment] = field(default_factory=list)
    created_at_ms: int = 0
    updated_at_ms: int = 0
    delete_after_run: bool = False


@dataclass
class CronStore:
    """Persistent store for cron jobs."""
    version: int = 1
    jobs: list[CronJob] = field(default_factory=list)
