"""Commitment 工具：让 LLM 用结构化方式管理一个 cron job 上的持久规则。

核心思路：用户说"以后不要 X"这类影响未来行为的指令时，LLM 应该用这三个工具
操作对应 job 的 commitments 字段，而不是往 memory.md 写散文——那样下次 cron
真跑时规则进不了 prompt，用户的意图落空。
"""

from __future__ import annotations

from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import StringSchema, tool_parameters_schema
from nanobot.cron.service import CronService
from nanobot.cron.types import Commitment
from nanobot.trace import emit as trace_emit
from nanobot.trace import get_trace_id


def _format_commitment(c: Commitment) -> str:
    """给 LLM 看的单行 commitment 摘要。"""
    parts = [f"id={c.id}", f"status={c.status}", f'text="{c.text}"']
    if c.revoked_reason:
        parts.append(f'revoked_reason="{c.revoked_reason}"')
    return " ".join(parts)


@tool_parameters(
    tool_parameters_schema(
        job_id=StringSchema("Target cron job id. Use `cron` tool's list action to discover."),
        text=StringSchema(
            "The rule / commitment as natural language. Keep it as verifiable as "
            "possible (prefer 'never include neuroscience' over 'be nicer')."
        ),
        origin=StringSchema(
            "Who this commitment came from. Defaults to `user_request`.",
            enum=["user_request", "llm_inference", "system"],
        ),
        required=["job_id", "text"],
    )
)
class CreateCommitmentTool(Tool):
    """给一个 cron job 追加一条持久规则。

    LLM 应优先用这个工具处理"以后 X" / "别再 Y" / "改成 Z" 这类
    影响未来自动执行的用户请求，而不是往 memory 写散文。
    """

    def __init__(self, cron_service: CronService) -> None:
        self._cron = cron_service

    @property
    def name(self) -> str:
        return "create_commitment"

    @property
    def description(self) -> str:
        return (
            "Attach a persistent rule (commitment) to a recurring cron job. "
            "Use this whenever the user wants to change the behavior of a scheduled "
            "task from now on. Prefer this over writing to memory.md — memory is not "
            "guaranteed to be read when the cron job actually fires, but commitments "
            "are injected into the job's prompt every run."
        )

    async def execute(
        self,
        job_id: str,
        text: str,
        origin: str = "user_request",
        **kwargs: Any,
    ) -> str:
        if not job_id:
            return "Error: job_id is required"
        if not text or not text.strip():
            return "Error: text must be non-empty"
        if origin not in ("user_request", "llm_inference", "system"):
            return f"Error: invalid origin '{origin}'"

        commitment = self._cron.add_commitment(
            job_id,
            text=text.strip(),
            origin=origin,  # type: ignore[arg-type]
            source_trace_id=get_trace_id(),
        )
        if commitment is None:
            return f"Error: no such job '{job_id}'"

        trace_emit(
            "commitment.created",
            job_id=job_id,
            commitment_id=commitment.id,
            origin=origin,
            text_len=len(commitment.text),
        )
        return (
            f"Created commitment {commitment.id} on job {job_id}. "
            f"It will be injected into every future run of this job."
        )


@tool_parameters(
    tool_parameters_schema(
        job_id=StringSchema("Target cron job id."),
        commitment_id=StringSchema("The commitment id to revoke (from list_commitments)."),
        reason=StringSchema("Optional short rationale for why this is being revoked."),
        required=["job_id", "commitment_id"],
    )
)
class RevokeCommitmentTool(Tool):
    """撤销一条 commitment，让它不再进入后续 cron 运行的 prompt。"""

    def __init__(self, cron_service: CronService) -> None:
        self._cron = cron_service

    @property
    def name(self) -> str:
        return "revoke_commitment"

    @property
    def description(self) -> str:
        return (
            "Revoke an existing commitment on a cron job. The rule will no longer "
            "be injected into future runs. Use for 'undo' / 'never mind' / 'replace "
            "with something else' requests. Revoking is idempotent: revoking an "
            "already-revoked commitment is a no-op."
        )

    async def execute(
        self,
        job_id: str,
        commitment_id: str,
        reason: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not job_id:
            return "Error: job_id is required"
        if not commitment_id:
            return "Error: commitment_id is required"

        commitment = self._cron.revoke_commitment(
            job_id,
            commitment_id,
            reason=(reason.strip() if reason and reason.strip() else None),
        )
        if commitment is None:
            return f"Error: no such commitment '{commitment_id}' on job '{job_id}'"

        trace_emit(
            "commitment.revoked",
            job_id=job_id,
            commitment_id=commitment.id,
            status=commitment.status,
            has_reason=commitment.revoked_reason is not None,
        )
        return (
            f"Commitment {commitment.id} on job {job_id} is now "
            f"{commitment.status}. It will not be injected into future runs."
        )


@tool_parameters(
    tool_parameters_schema(
        job_id=StringSchema("Target cron job id."),
        status=StringSchema(
            "Which commitments to list. Defaults to `active`.",
            enum=["active", "revoked", "merged", "all"],
        ),
        required=["job_id"],
    )
)
class ListCommitmentsTool(Tool):
    """列出一个 cron job 当前挂着的 commitments（用于查现状）。"""

    def __init__(self, cron_service: CronService) -> None:
        self._cron = cron_service

    @property
    def name(self) -> str:
        return "list_commitments"

    @property
    def read_only(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return (
            "List commitments attached to a cron job. Default returns only active "
            "ones. Use `status=all` to include revoked/merged entries for audit."
        )

    async def execute(
        self,
        job_id: str,
        status: str = "active",
        **kwargs: Any,
    ) -> str:
        if not job_id:
            return "Error: job_id is required"
        if status not in ("active", "revoked", "merged", "all"):
            return f"Error: invalid status '{status}'"

        filter_status = None if status == "all" else status
        commitments = self._cron.list_commitments(job_id, status=filter_status)
        if not commitments:
            return f"No commitments (status={status}) on job '{job_id}'."
        lines = [f"{len(commitments)} commitment(s) on job '{job_id}' (status={status}):"]
        for c in commitments:
            lines.append(f"  - {_format_commitment(c)}")
        return "\n".join(lines)
