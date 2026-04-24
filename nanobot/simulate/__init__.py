"""Simulate 机制：让 LLM 在同 turn 内跑 cron job 的完整执行链路，
但真实外发副作用被拦截——目前唯一陷阱点是 MessageTool 的 send path。"""

from nanobot.simulate.recorder import (
    SimulateRecorder,
    current_recorder,
    simulate_scope,
)

__all__ = ["SimulateRecorder", "current_recorder", "simulate_scope"]
