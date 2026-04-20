# ADR-0003：所有副作用必须隔离在 intent/outbox/effector 边界之后

## Status

Accepted

## Context

如果 planner 在决策时直接调用 channel、工具或外部 API，系统很难仿真、回放和验证，也很难保证 exactly-once。

## Decision

planner 不能直接产生外部副作用。它只能产出 intent。真实 effect 由 effector 消费 intent 后执行。

## Alternatives considered

1. 继续让工具和 channel 直接在 agent loop 中执行。
2. 只在测试里 mock 副作用。
3. 只靠 prompt 要求 agent 谨慎。

## Consequences

- live/simulate 路径可以共享结构。
- verifier 能观察 would-be side effects。
- 需要新增 outbox-like boundary。
- 旧 direct-send path 必须逐步迁移或封装。
