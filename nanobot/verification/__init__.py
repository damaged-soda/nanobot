"""Phase 1 verification helper：独立 LLM 判决 (evidence, claim)。

用法见 docs/runtime/plans/PLAN-phase1-commitments.md §6：
- 有输出时：evidence = 输出文本，claim = "必须满足以下承诺：..."
- 沉默时：  evidence = 抓到的原始材料，claim = "按以下承诺，这批输入不应触发通知：..."

一个函数两种用法，调用者负责组装 (evidence, claim)。
"""

from nanobot.verification.verify import Verdict, verify

__all__ = ["Verdict", "verify"]
