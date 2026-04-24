"""Phase 1 Step 4 — `_build_cron_reminder_note` 的模板快照。

cron 真跑时 prompt 的构造是 commitments 进 LLM 的唯一入口，模板变化会悄悄
改变 LLM 对规则的感知方式，所以用精确字符串断言锁住格式。
"""

from __future__ import annotations

from nanobot.cli.commands import _build_cron_reminder_note
from nanobot.cron.types import (
    Commitment,
    CronJob,
    CronJobState,
    CronPayload,
    CronSchedule,
)


def _job(commitments: list[Commitment] | None = None) -> CronJob:
    return CronJob(
        id="j1",
        name="Morning briefing",
        schedule=CronSchedule(kind="every", every_ms=60_000),
        payload=CronPayload(kind="agent_turn", message="Send a news briefing"),
        state=CronJobState(),
        commitments=commitments or [],
    )


def test_no_commitments_matches_legacy_template():
    note = _build_cron_reminder_note(_job())
    assert note == (
        "[Scheduled Task] Timer finished.\n\n"
        "Task 'Morning briefing' has been triggered.\n"
        "Scheduled instruction: Send a news briefing"
    )


def test_active_commitments_are_appended_as_rules_block():
    note = _build_cron_reminder_note(_job([
        Commitment(id="c1", text="不要包含神经科学", status="active"),
        Commitment(id="c2", text="控制在 300 字以内", status="active"),
    ]))
    assert note == (
        "[Scheduled Task] Timer finished.\n\n"
        "Task 'Morning briefing' has been triggered.\n"
        "Scheduled instruction: Send a news briefing\n\n"
        "## Active rules to follow\n"
        "The following rules MUST be respected in this run. "
        "If any cannot be satisfied, say so explicitly in the output "
        "rather than silently violating.\n\n"
        "- 不要包含神经科学\n"
        "- 控制在 300 字以内"
    )


def test_revoked_and_merged_commitments_are_excluded():
    note = _build_cron_reminder_note(_job([
        Commitment(id="c1", text="active one", status="active"),
        Commitment(id="c2", text="old one", status="revoked"),
        Commitment(id="c3", text="graduated one", status="merged"),
    ]))
    assert "active one" in note
    assert "old one" not in note
    assert "graduated one" not in note
    # 只有一条 bullet
    assert note.count("\n- ") == 1


def test_empty_commitments_list_does_not_add_rules_block():
    """commitments=[] 必须和 commitments 字段不存在的老 job 渲染同一份 prompt。"""
    note = _build_cron_reminder_note(_job([]))
    assert "Active rules to follow" not in note
