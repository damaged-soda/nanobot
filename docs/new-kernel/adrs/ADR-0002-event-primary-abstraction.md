# ADR-0002：Event 成为顶级抽象

## Status

Accepted

## Context

旧架构以一次 agent turn 为中心。用户消息、cron、heartbeat、tool use 都容易被压成一次 turn。这不利于重放、审计、仿真和长期任务拆分。

## Decision

新内核以 event 为一级抽象。`turn` 只是 event 的一种，而不是 runtime 中心。

## Alternatives considered

1. 继续以 turn 为中心，只增强 memory 和 prompt。
2. 采用完整 workflow DAG 作为唯一抽象。
3. 采用 actor 但不保留 event log。

## Consequences

- 用户消息、cron tick、observation、intent、effect 都能统一建模。
- simulation/replay 更自然。
- 需要维护事件目录和版本语义。
