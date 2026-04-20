# 目标架构

## High-level shape

目标形态是：

```text
nanobot shell
  -> event-sourced runtime kernel
    -> assurance layer
```

这也可以称为：`nanobot shell + new event kernel`、`event-sourced + effect-isolated agent runtime`、`CQRS-lite agent architecture`。

## Top-level layers

### Shell / Adapters

保留 nanobot 的用户可见外壳：channel adapters、CLI / gateway、workspace conventions、provider / tool registry、配置和启动体验。

### Event Runtime

新内核的中心：append-only event log、dispatcher、consumer scheduler、outbox、materialized views、run modes。

### Consumers

只消费事件并产出新的事件或 intent，不直接产生外部副作用。例如 planner、collector、summarizer、memory reducer、verifier、janitor / cleanup minimizer。

### Effectors

真正产生外部副作用的执行单元。例如 sender、tool runner、artifact writer、external API caller。

### Assurance Layer

跨越整个 runtime 的验证边界：simulation、replay、TDAD、cleanup verifier、regression checks、publish gate。

## Primary abstractions

- `Event`：系统中已经发生的事实。
- `Intent`：系统准备做的动作，尤其是可能产生外部副作用或持久状态变化的动作。
- `Effect`：外部世界或持久状态实际发生的结果。
- `Resource`：长期存在、有 owner、可被引用的状态对象。
- `View`：从 event log materialize 出来的查询视图，不是 source of truth。
- `Run`：同一逻辑在不同模式下的一次执行，例如 live、simulate、replay、compile。

## Run modes

- `live`：真实运行，effectors 会产生真实副作用。
- `simulate`：仿真运行，真实 effectors 被 recorder/verifier 替换。
- `replay`：基于历史 event log 重放。
- `compile`：用于 TDAD 或 agent/prompt/artifact 编译，不直接发布。

## Core claims

- `turn` 只是 event 的一种，不是系统中心。
- planner 只能产出 intent，不能直接产生 effect。
- 每个 effect 都必须有前置 intent。
- 每类持久约束必须归属到明确 resource。
- memory 不能代替 `JobSpec`、`ProjectRules`、`UserProfile` 等资源。
- simulation/replay 是一级能力。
- build -> verify -> publish 是发布边界。

## What v1 intentionally avoids

第一版刻意不做：Kafka 或重型分布式消息总线、多进程 actor runtime、全量 workflow/orchestration 平台、企业级权限模型、一次性替换所有 legacy paths。

第一版应保持单进程、轻量、本地可理解。
