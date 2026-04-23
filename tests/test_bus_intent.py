"""Phase 1 intent 管道的单测：SendMessageIntent、NoReplyChosen，
以及 MessageBus.publish_intent / consume_intent。

Step 2 里没有 producer 迁移——只加类型和 bus 通道。"""

from __future__ import annotations

import asyncio

import pytest

from nanobot.bus.events import Intent, NoReplyChosen, OutboundMessage, SendMessageIntent
from nanobot.bus.queue import MessageBus
from nanobot.trace import context, init_run
from nanobot.trace.core import _reset_for_test


@pytest.fixture(autouse=True)
def _reset_trace():
    _reset_for_test()
    init_run("test-run")
    yield
    _reset_for_test()


def test_send_message_intent_defaults():
    intent = SendMessageIntent(channel="cli", chat_id="direct", content="hi")
    assert intent.channel == "cli"
    assert intent.chat_id == "direct"
    assert intent.content == "hi"
    assert intent.reply_to is None
    assert intent.media == []
    assert intent.metadata == {}
    assert intent.trace_id is None
    assert intent.dedupe_key is None
    assert intent.origin == "planner"


def test_send_message_intent_accepts_all_fields():
    intent = SendMessageIntent(
        channel="telegram",
        chat_id="123",
        content="hello",
        reply_to="msg-42",
        media=["/tmp/a.png"],
        metadata={"foo": "bar"},
        trace_id="t1",
        dedupe_key="dk-1",
        origin="tool",
    )
    assert intent.origin == "tool"
    assert intent.dedupe_key == "dk-1"
    assert intent.media == ["/tmp/a.png"]


def test_no_reply_chosen_defaults():
    nr = NoReplyChosen()
    assert nr.trace_id is None
    assert nr.reason is None
    assert nr.origin == "planner"


def test_no_reply_chosen_with_reason():
    nr = NoReplyChosen(reason="cli_wake_no_reply", origin="planner")
    assert nr.reason == "cli_wake_no_reply"


async def test_publish_and_consume_send_intent():
    bus = MessageBus()
    intent = SendMessageIntent(channel="cli", chat_id="direct", content="hi")
    await bus.publish_intent(intent)
    assert bus.intents_size == 1

    received = await bus.consume_intent()
    assert received is intent
    assert bus.intents_size == 0


async def test_publish_and_consume_no_reply():
    bus = MessageBus()
    nr = NoReplyChosen(reason="tool_handled")
    await bus.publish_intent(nr)

    received = await bus.consume_intent()
    assert received is nr
    assert isinstance(received, NoReplyChosen)


async def test_publish_intent_autostamps_trace_id_from_context():
    bus = MessageBus()
    intent = SendMessageIntent(channel="cli", chat_id="direct", content="hi")
    with context(trace_id="t-abc"):
        await bus.publish_intent(intent)
    assert intent.trace_id == "t-abc"


async def test_publish_intent_preserves_explicit_trace_id():
    """intent 自带的显式 trace_id 优先于 contextvar——与 publish_outbound 同契约。"""
    bus = MessageBus()
    intent = SendMessageIntent(
        channel="cli", chat_id="direct", content="hi", trace_id="explicit",
    )
    with context(trace_id="ctx"):
        await bus.publish_intent(intent)
    assert intent.trace_id == "explicit"


async def test_intents_queue_is_isolated_from_outbound():
    """publish_intent 不能串到 outbound 队列，反之亦然——两条队列承载语义不同。"""
    bus = MessageBus()
    intent = SendMessageIntent(channel="cli", chat_id="direct", content="i")
    outbound = OutboundMessage(channel="cli", chat_id="direct", content="o")

    await bus.publish_intent(intent)
    await bus.publish_outbound(outbound)

    assert bus.intents_size == 1
    assert bus.outbound_size == 1

    got_intent = await bus.consume_intent()
    got_outbound = await bus.consume_outbound()
    assert got_intent is intent
    assert got_outbound is outbound


async def test_no_reply_chosen_autostamps_trace_id():
    """trace_id 自动盖章对 NoReplyChosen 也要生效——否则"沉默决定"这件事
    在 trace 里就接不回它的触发源。"""
    bus = MessageBus()
    nr = NoReplyChosen(reason="cli_wake_no_reply")
    with context(trace_id="t-silence"):
        await bus.publish_intent(nr)
    assert nr.trace_id == "t-silence"


async def test_intent_type_alias_includes_both_shapes():
    """``Intent`` 是下游 producer / effector 编程要认的唯一契约类型。"""
    s: Intent = SendMessageIntent(channel="cli", chat_id="c", content="x")
    n: Intent = NoReplyChosen()
    bus = MessageBus()
    await bus.publish_intent(s)
    await bus.publish_intent(n)
    assert isinstance(await bus.consume_intent(), SendMessageIntent)
    assert isinstance(await bus.consume_intent(), NoReplyChosen)
