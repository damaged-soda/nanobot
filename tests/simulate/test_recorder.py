"""Phase 1 Step 5 — SimulateRecorder + MessageTool 陷阱点。

核心不变式：
- live path（没进 simulate_scope）行为逐字节不变——真 `_send_callback` 照常调。
- simulate_scope 内 MessageTool 发送走 recorder，不触达真 channel。
- contextvar 退出作用域后状态干净，下一次发送继续走 live path。
- simulate 内部派生 asyncio task 继承 recorder（这是 contextvar 原生语义，
  但这条是 simulate 能覆盖"agent 内部 create_task 出去的副作用"的硬前提）。
"""

from __future__ import annotations

import asyncio

import pytest

from nanobot.agent.tools.message import MessageTool
from nanobot.bus.events import OutboundMessage
from nanobot.simulate import (
    SimulateRecorder,
    current_recorder,
    simulate_scope,
)


# -------- 裸 recorder --------

def test_current_recorder_default_is_none():
    assert current_recorder() is None


def test_simulate_scope_activates_then_clears():
    assert current_recorder() is None
    with simulate_scope() as rec:
        assert current_recorder() is rec
    assert current_recorder() is None


def test_simulate_recorder_records_messages():
    rec = SimulateRecorder()
    m = OutboundMessage(channel="cli", chat_id="u1", content="hi")
    rec.record(m)
    assert rec.captured == [m]


def test_simulate_scope_nested_isolates_inner_recorder():
    """嵌套作用域时内层拿到新 recorder，退出后回到外层——contextvar 标准语义。"""
    with simulate_scope() as outer:
        outer.record(OutboundMessage(channel="cli", chat_id="u", content="outer"))
        with simulate_scope() as inner:
            assert current_recorder() is inner
            inner.record(OutboundMessage(channel="cli", chat_id="u", content="inner"))
        assert current_recorder() is outer
        assert [m.content for m in outer.captured] == ["outer"]


# -------- MessageTool 与陷阱点 --------

def _make_tool() -> tuple[MessageTool, list[OutboundMessage]]:
    sent: list[OutboundMessage] = []

    async def send(msg: OutboundMessage) -> None:
        sent.append(msg)

    tool = MessageTool(
        send_callback=send,
        default_channel="cli",
        default_chat_id="u1",
    )
    return tool, sent


async def test_live_path_calls_real_send_callback():
    tool, sent = _make_tool()
    result = await tool.execute(content="hello")

    assert len(sent) == 1
    assert sent[0].content == "hello"
    assert result == "Message sent to cli:u1"
    assert "(simulated)" not in result
    assert tool._sent_in_turn is True


async def test_simulate_scope_suppresses_real_send():
    tool, sent = _make_tool()

    with simulate_scope() as rec:
        result = await tool.execute(content="hello under simulate")

    # 核心承诺：simulate 下真 callback 零调用
    assert sent == []
    # recorder 捕获到 outbound
    assert len(rec.captured) == 1
    assert rec.captured[0].content == "hello under simulate"
    # 返回串带 (simulated) 标记
    assert result.endswith("(simulated)")
    # _sent_in_turn 语义保持——与 live 一致，便于上层 on_cron_job 下游分支同构
    assert tool._sent_in_turn is True


async def test_live_path_restored_after_scope_exits():
    tool, sent = _make_tool()

    with simulate_scope():
        await tool.execute(content="inside")
    await tool.execute(content="after")

    assert [m.content for m in sent] == ["after"]


async def test_simulate_scope_records_across_create_task():
    """contextvar 在 asyncio.create_task 时会被拷贝到子 task——这是 simulate
    能覆盖 agent 内部 `asyncio.create_task(...)` 出去副作用的硬依赖。"""
    tool, sent = _make_tool()

    async def nested() -> None:
        await tool.execute(content="from child task")

    with simulate_scope() as rec:
        await asyncio.create_task(nested())

    assert sent == []
    assert [m.content for m in rec.captured] == ["from child task"]


async def test_media_suffix_still_present_under_simulate():
    """simulate 路径返回串格式要和 live 只差尾部 (simulated) 标记。"""
    tool, _ = _make_tool()

    with simulate_scope():
        result = await tool.execute(content="with attachments", media=["/tmp/a.png"])

    assert "with 1 attachments" in result
    assert result.endswith("(simulated)")


async def test_send_callback_failure_not_triggered_under_simulate():
    """即使真 callback 会爆，simulate 下也完全不应该调它。"""

    async def boom(_msg: OutboundMessage) -> None:
        raise RuntimeError("real send blew up")

    tool = MessageTool(send_callback=boom, default_channel="cli", default_chat_id="u1")

    with simulate_scope() as rec:
        result = await tool.execute(content="safe under simulate")

    assert not result.startswith("Error")
    assert len(rec.captured) == 1


async def test_exception_in_scope_still_resets_contextvar():
    """作用域内抛异常仍要清理 contextvar，否则污染后续 live path。"""
    tool, sent = _make_tool()

    with pytest.raises(RuntimeError):
        with simulate_scope():
            raise RuntimeError("boom mid-simulate")

    assert current_recorder() is None
    await tool.execute(content="after error")
    assert [m.content for m in sent] == ["after error"]
