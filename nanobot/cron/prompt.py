"""Cron job 触发时注入 agent 的 prompt 构造。

提到这个独立模块的原因：live 路径（`cli/commands.py:on_cron_job`）和
simulate 路径（`agent/tools/simulate.py`）都要用，形态必须**逐字节一致**
——这是 PLAN §5 "live path 与 simulate path 结构同构" 的具体兑现。
"""

from __future__ import annotations

from nanobot.cron.types import CronJob


def build_cron_reminder_note(job: CronJob) -> str:
    """构造 cron 触发时注入 agent 的 reminder_note。

    没有 active commitment 时保持旧格式；有的话在末尾追加 "Active rules to
    follow" 区块——这是 Phase 1 把结构化承诺真正推进到 prompt 的通路。
    """
    note = (
        "[Scheduled Task] Timer finished.\n\n"
        f"Task '{job.name}' has been triggered.\n"
        f"Scheduled instruction: {job.payload.message}"
    )
    active = [c for c in job.commitments if c.status == "active"]
    if active:
        bullets = "\n".join(f"- {c.text}" for c in active)
        note += (
            "\n\n## Active rules to follow\n"
            "The following rules MUST be respected in this run. "
            "If any cannot be satisfied, say so explicitly in the output "
            "rather than silently violating.\n\n"
            f"{bullets}"
        )
    return note
