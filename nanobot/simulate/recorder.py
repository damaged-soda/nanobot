"""SimulateRecorder + contextvar：simulate 唯一陷阱点的储存层。

设计动机见 docs/runtime/plans/PLAN-phase1-commitments.md。

不要把拦截扩散到 bus / channel / manager——"channel 内部零改动"是 Phase 1
的硬承诺，效果拦截点只在 MessageTool.execute 一处，这里只提供 recorder
的生命周期容器。
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator

from nanobot.bus.events import OutboundMessage


@dataclass
class SimulateRecorder:
    """一次 simulate 里捕获到的 outbound。

    MessageTool 在 `_send_callback` 之前看到 current_recorder() 非空时，
    改为 `recorder.record(msg)`，真正发送不会发生。
    """

    captured: list[OutboundMessage] = field(default_factory=list)

    def record(self, message: OutboundMessage) -> None:
        self.captured.append(message)


# 内部 contextvar；外部访问一律走 current_recorder() / simulate_scope()。
_simulate_recorder: ContextVar[SimulateRecorder | None] = ContextVar(
    "nanobot_simulate_recorder", default=None
)


def current_recorder() -> SimulateRecorder | None:
    """当前是否在 simulate 作用域内；live path 永远拿到 None。"""
    return _simulate_recorder.get()


@contextmanager
def simulate_scope() -> Iterator[SimulateRecorder]:
    """进入 simulate 作用域。块内的 MessageTool 发送会进 recorder 不走真 channel。

    contextvar 原生就支持 `asyncio.create_task` 的继承，所以 agent 内部派生
    task 不会漏拦——线程 / callback 场景另算（见 PLAN Risks）。
    """
    recorder = SimulateRecorder()
    token = _simulate_recorder.set(recorder)
    try:
        yield recorder
    finally:
        _simulate_recorder.reset(token)
