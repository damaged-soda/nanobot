"""simulate_job_run 工具：把 cron job 在同 turn 内"试跑"一遍。

LLM 改完 commitment 后立即调这个工具，跑完整执行链路（reminder_note
构造 → process_direct → planner → tools → MessageTool）但真实 send 被
SimulateRecorder 拦下；把捕获的 outputs 喂给 verify() 逐条判决，给出
LLM 可读的回执。

设计约束：
- prompt 构造点和 live cron 共用 `build_cron_reminder_note`，**结构同构**
  是 PLAN §5 的硬要求——任何形态偏移都会让 simulate 的判决失去意义。
- session_key 用 `"simulate:<job_id>"` 隔离 simulate 的会话历史，避免
  污染 user 的 CLI session 或真 cron 的 cron:<job_id> session。
- trace_id 由 contextvar 自然继承（process_direct 不创建新 context），
  让 "改 commitment → simulate → verify" 在 trace 里串成一条线。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import StringSchema, tool_parameters_schema
from nanobot.bus.events import OutboundMessage
from nanobot.cron.prompt import build_cron_reminder_note
from nanobot.cron.service import CronService
from nanobot.cron.types import Commitment, CronJob
from nanobot.providers.base import LLMProvider
from nanobot.simulate import simulate_scope
from nanobot.trace import emit as trace_emit
from nanobot.verification import Verdict, verify


# 类型别名：调用 AgentLoop.process_direct 的最小签名。
# 通过签名而非传整个 AgentLoop 进来——降低耦合，单测也好 mock。
ProcessDirectFn = Callable[..., Awaitable["OutboundMessage | None"]]


@tool_parameters(
    tool_parameters_schema(
        job_id=StringSchema(
            "Target cron job id. Use `cron` tool's list action to discover."
        ),
        required=["job_id"],
    )
)
class SimulateJobRunTool(Tool):
    """Run a cron job through the full execution path *without* hitting real
    channels, then verify outputs against the job's active commitments.

    Use this AFTER changing a commitment (`create_commitment` / `revoke_commitment`)
    to confirm the change actually takes effect when the job runs. Outputs are
    captured by SimulateRecorder; real `_send_callback` is suppressed.

    Side-effect caveat (α): only the channel `send` boundary is intercepted.
    Other side effects inside the job (web fetch, file write, shell exec)
    *will* really happen. Avoid back-to-back simulates of jobs with real
    side effects.
    """

    def __init__(
        self,
        cron_service: CronService,
        process_direct: ProcessDirectFn,
        provider: LLMProvider,
        model: str,
    ) -> None:
        self._cron = cron_service
        self._process_direct = process_direct
        self._provider = provider
        self._model = model

    @property
    def name(self) -> str:
        return "simulate_job_run"

    @property
    def description(self) -> str:
        return (
            "Simulate a cron job run in this turn: builds the same prompt the "
            "real cron would build (including active commitments), runs the "
            "agent loop, but suppresses real outbound sends. Then verifies "
            "the captured outputs against each active commitment and returns "
            "a verdict per rule. Use to confirm a commitment change will be "
            "honored before promising the user it will."
        )

    async def execute(self, job_id: str, **kwargs: Any) -> str:
        if not job_id:
            return "Error: job_id is required"

        job = self._cron.get_job(job_id)
        if job is None:
            return f"Error: no such job '{job_id}'"

        active = [c for c in job.commitments if c.status == "active"]
        prompt = build_cron_reminder_note(job)

        trace_emit(
            "job.simulated",
            job_id=job.id,
            job_name=job.name,
            commitments_count=len(active),
        )

        with simulate_scope() as recorder:
            response = await self._process_direct(
                prompt,
                session_key=f"simulate:{job.id}",
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to or "direct",
            )

        captured_contents = [m.content for m in recorder.captured]
        if captured_contents:
            outputs = captured_contents
        else:
            # 没走 MessageTool 的 job（比如直接 return text）回退到 final response。
            fallback = response.content if response else ""
            outputs = [fallback] if fallback else []

        verdicts = await self._run_verifications(active, outputs)
        return _format_result(job, outputs, active, verdicts)

    async def _run_verifications(
        self,
        commitments: list[Commitment],
        outputs: list[str],
    ) -> list[Verdict]:
        if not commitments or not outputs:
            return []
        evidence = "\n\n".join(outputs)
        results: list[Verdict] = []
        for c in commitments:
            verdict = await verify(
                evidence=evidence,
                claim=c.text,
                provider=self._provider,
                model=self._model,
            )
            trace_emit(
                "verification.completed",
                commitment_id=c.id,
                run_kind="simulate",
                verdict="pass" if verdict.passed else "fail",
                has_detail=verdict.detail is not None,
            )
            results.append(verdict)
        return results


def _format_result(
    job: CronJob,
    outputs: list[str],
    commitments: list[Commitment],
    verdicts: list[Verdict],
) -> str:
    lines = [f"Simulated job '{job.name}' ({job.id})."]

    if outputs:
        lines.append(f"\nOutputs ({len(outputs)} captured):")
        for i, out in enumerate(outputs, start=1):
            preview = out if len(out) <= 400 else out[:400] + "...(truncated)"
            lines.append(f"  {i}. {preview}")
    else:
        lines.append("\nOutputs: (none captured — agent did not produce output)")

    if not commitments:
        lines.append("\nVerdicts: (no active commitments on this job)")
        return "\n".join(lines)

    if not verdicts:
        # 有 commitments 但没 outputs → 跳过 verify
        lines.append(
            "\nVerdicts: (skipped — no outputs to evaluate against "
            f"{len(commitments)} active commitment(s))"
        )
        return "\n".join(lines)

    passed = sum(1 for v in verdicts if v.passed)
    lines.append(f"\nVerdicts ({passed}/{len(verdicts)} passed):")
    for c, v in zip(commitments, verdicts):
        tag = "pass" if v.passed else "fail"
        suffix = f" — {v.detail}" if v.detail else ""
        lines.append(f"  - {tag}: {c.id} ({c.text}){suffix}")
    return "\n".join(lines)
