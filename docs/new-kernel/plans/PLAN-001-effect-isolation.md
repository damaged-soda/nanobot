# PLAN-001：outbound messaging 的 effect isolation

## Goal

把 outbound message 从 planner 中剥离出来，让 planner 只产出显式 intent，真实发送由 effector 负责。

## Background

当前 loop-centric 架构中，planner 或 agent turn 很容易直接调用 channel 发送消息。这会让仿真、回放、验证和 exactly-once 检查变得困难。

目标是先做最小一刀：不重写整个 runtime，只把“发送消息”这类副作用改造成 intent -> outbox -> effector。

## Scope

- 引入 `SendMessageIntent`。
- 引入 `NoReplyChosen`。
- 增加 outbox-like boundary。
- 增加 live effector。
- 增加 simulation recorder / verifier。
- 让现有 shell 行为尽量保持兼容。

## Non-goals

- 完整 event log。
- 完整 context compiler。
- 完整 cron 重构。
- 完整 TDAD pipeline。
- 完整 cleanup verifier。

## Architecture impact

这一步确立第一条核心原则：planner 不直接产生外部副作用。它不会立即替换旧 `AgentLoop`，但会把旧 loop 的 outbound side effect 降级为 intent 生产。

## Steps

1. 找出现有 outbound send 的主要路径。
2. 定义最小 `SendMessageIntent` 数据结构。
3. 定义 `NoReplyChosen` 事件或等价记录。
4. 增加 outbox-like adapter。
5. live mode 中由 sender effector 消费 intent 并调用真实 channel。
6. simulate mode 中由 recorder/verifier 消费 intent，不调用真实 channel。
7. 增加最小验收测试。
8. 更新文档。

## Acceptance checks

- planner path 能产生 `SendMessageIntent`。
- no-reply 决策可观测。
- live mode 仍能正常发消息。
- simulate mode 不产生真实外部发送。
- simulate mode 能断言 send / no-send / exactly-once。

## Rollback / kill switch

保留一个兼容开关，使旧 direct-send path 可在紧急情况下恢复，但任何兼容路径必须被标注为 temporary，并有退出条件。

## Docs to update

- `../STATUS.md`
- `../EVENT_CATALOG.md`
- `../VERIFICATION_MODEL.md`
- `../NORTH_STAR_SCENARIOS.md`
- 必要时新增 ADR

## Exit criteria

北极星场景 1 的最小版本通过：用户消息进入后，系统能显式产生 reply intent 或 no-reply decision；simulate mode 能验证这件事而不产生真实副作用。
