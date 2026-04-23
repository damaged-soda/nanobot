"""Async message queue for decoupled channel-agent communication."""

import asyncio

from nanobot.bus.events import InboundMessage, Intent, OutboundMessage
from nanobot.trace import get_trace_id


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.

    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.

    ``intents`` 队列是 Phase 1 新增：planner / tool 侧 producer 把
    :class:`SendMessageIntent` / :class:`NoReplyChosen` 推进来，effector 消费后
    （live 模式下）再转成具体的 OutboundMessage 丢进 ``outbound``。
    """

    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self.intents: asyncio.Queue[Intent] = asyncio.Queue()

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent.

        Auto-stamps the current trace_id onto the message so it survives the
        asyncio.Queue boundary into the consumer task.
        """
        if msg.trace_id is None:
            msg.trace_id = get_trace_id()
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish a response from the agent to channels.

        Auto-stamps the current trace_id onto the message so it survives the
        asyncio.Queue boundary into the outbound dispatcher task.
        """
        if msg.trace_id is None:
            msg.trace_id = get_trace_id()
        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()

    async def publish_intent(self, intent: Intent) -> None:
        """发布一个 planner / tool intent（send-message 或 no-reply）。

        自动把当前 trace_id 盖章到 intent 上，让它能穿过 asyncio.Queue 的 task
        边界传到 effector。**不**在这里发 trace 事件——``intent.published`` 由
        producer 侧发，这样原始产生位置在 trace 里仍然可见。
        """
        if intent.trace_id is None:
            intent.trace_id = get_trace_id()
        await self.intents.put(intent)

    async def consume_intent(self) -> Intent:
        """取下一条 intent（队列空时阻塞）。"""
        return await self.intents.get()

    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()

    @property
    def intents_size(self) -> int:
        """待消费的 intent 数量。"""
        return self.intents.qsize()
