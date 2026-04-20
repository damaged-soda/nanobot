# ADR-0001：保留 nanobot shell，不保留旧 core 作为未来中心

## Status

Accepted

## Context

nanobot 的 shell 简洁、易用、适合作为 personal-agent 产品外壳。但旧运行模型偏 loop-centric，难以天然支持 event sourcing、effect isolation、simulation、TDAD 和 cleanup verifier。

## Decision

保留 nanobot shell，重做 runtime kernel。旧 `AgentLoop` 逐步降级为 planner consumer 或兼容 adapter。

## Alternatives considered

1. 继续在旧 `AgentLoop` 上打补丁。
2. 完全从零重写整个项目。
3. 换用另一个大型 agent/workflow framework。

## Consequences

- 可以复用 nanobot 的产品外壳。
- 新内核可以采用不同运行时模型。
- 迁移期需要维护 legacy adapter。
- 架构文档和边界控制变得非常重要。
