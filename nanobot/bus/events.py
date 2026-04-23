"""Event types for the message bus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


IntentOrigin = Literal["planner", "tool", "system", "command"]


@dataclass
class InboundMessage:
    """Message received from a chat channel."""

    channel: str  # telegram, discord, slack, whatsapp
    sender_id: str  # User identifier
    chat_id: str  # Chat/channel identifier
    content: str  # Message text
    timestamp: datetime = field(default_factory=datetime.now)
    media: list[str] = field(default_factory=list)  # Media URLs
    metadata: dict[str, Any] = field(default_factory=dict)  # Channel-specific data
    session_key_override: str | None = None  # Optional override for thread-scoped sessions
    trace_id: str | None = None  # Observability: propagates across the bus task boundary

    @property
    def session_key(self) -> str:
        """Unique key for session identification."""
        return self.session_key_override or f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    """Message to send to a chat channel."""

    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None  # Observability: propagates across the bus task boundary


@dataclass
class SendMessageIntent:
    """planner / tool 决定"发一条用户可见消息"的意图。

    与 :class:`OutboundMessage` 刻意分开：intent 是 planner 决定要做什么，
    effector 负责把它落到真正的 channel send。simulate 模式下 effector 只记录
    intent，不真的发出去。
    """

    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    dedupe_key: str | None = None  # 同一个 key 出现两次 = 重复 intent（测试可断言）
    origin: IntentOrigin = "planner"


@dataclass
class NoReplyChosen:
    """planner / tool 决定本轮"不回复"的意图。

    把"选择沉默"做成显式事件，simulate 测试才能区分"主动决定不回复"和
    "还在处理中 / 崩了"。
    """

    trace_id: str | None = None
    reason: str | None = None
    origin: IntentOrigin = "planner"


Intent = SendMessageIntent | NoReplyChosen
