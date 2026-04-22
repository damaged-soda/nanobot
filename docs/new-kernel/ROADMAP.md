# 路线图

本文件只覆盖已经决定要做或即将要做的阶段。更远的想法放在 Later 区，明确标为 frozen，避免过度设计。

## Phase 0：Observability scaffold（当前）

### Goal

让当前系统在 trace 里完全可见，为后续重构提供安全网，同时沉淀出未来 event log 的格式雏形。

### Scope

- 定义最小 trace 事件结构（`{ts, run_id, trace_id, kind, payload}`，JSONL）。
- 提供 `emit` API，内部用 contextvar 传递 run_id / trace_id。
- 默认 sink：stdout JSONL + 可选文件。
- 在六类关键边界注入 trace：
  - channel 入口（收到用户消息）
  - planner 入口 / 出口（agent loop 起止）
  - tool 调用前 / 后
  - channel 出口（真实发送点）
  - memory 读 / 写
  - cron 触发
- 提供最小查看方式：`jq` 过滤 JSONL 够用。

### Non-goals

- 不做采样、分布式追踪、span / trace 树。
- 不做 UI 或 dashboard。
- 不做 metric、不做告警。
- 不改任何现有行为，只加观测。

### Exit criteria

- 在 CLI 里发一条用户消息，能得到一份完整可读的 trace，覆盖从 channel 接收 → planner → tool → 发送的全部路径。
- 同一场景下，cron tick 也能产生对应 trace。
- trace 结构稳定，能作为 Phase 1 引入 intent/effect 事件时的载体。

## Phase 1：Outbound effect isolation

### Goal

把 planner 出口的发消息路径改走显式 intent，真实发送由 effector 负责。

### Scope（概述）

- 定义 `SendMessageIntent` 和 `NoReplyChosen`。
- planner 出口由直接 `channel.send(...)` 改为产出 intent。
- 新增 effector 作为薄 dispatcher，channel 内部 `send()` 保持不动。
- CLI 作为唯一 simulate pilot：提供 recorder fake，live / simulate 共用一条链路结构。
- 北极星场景：用户在 CLI 发消息，系统必须显式产出 reply intent 或 no-reply 决策；simulate 模式不产生真实输出。

### Exit criteria

- Trace 里能看到 intent 和 effect 是两个分开的事件。
- CLI 上 live 模式行为与改造前一致。
- CLI 上 simulate 模式能断言 send / no-send / exactly-once。

## Phase 2：Cron 事件化

### Goal

让 cron 不再"到点直接喂 prompt"，而是产生显式时间事件，让后续消费者根据资源状态处理。

### Scope（概述）

- 定义 `CronTicked` 事件。
- 定义最小 `JobSpec`，让 job 专属约束归属到 JobSpec，不再写进 global memory。
- cron producer 和 planner consumer 分离。
- 支持 mock clock / simulated tick。
- 北极星场景：每天 9 点提醒；mock 08:59 不发，mock 09:00 恰好发一次，replay 不重复发送。

### Exit criteria

- 上述提醒场景能在 simulate 模式下断言通过。
- Job 专属指令不再出现在 global memory。

## Later（frozen）

以下方向明确不在当前视野内。留作未来可能的方向，但不写详细文档、不建目录、不定义 schema。等 Phase 0–2 走完后再决定是否开启，以及以什么形态开启。

- **Context compiler**：把"每次现场拼 prompt"换成可审计、可 hash、可重放的上下文快照。
- **Resource ownership 全面化**：把 `JobSpec` 之外的 `UserProfile` / `ProjectRules` / `ObservationStore` / `KnowledgeBase` 也资源化。
- **TDAD / 行为 spec**：从行为规约出发做可执行检查。
- **Cleanup verifier / publish gate**：通过回退 hunk + 重跑检查删除多余修改，作为发布闸门。
- **Legacy `AgentLoop` 降级**：把旧 loop 彻底降级为 event 消费者或兼容 adapter。
- **分布式 / 多进程 runtime**：v1 刻意单进程，规模化另议。

Frozen 不代表否决，只代表"现在不做、不设计、不写文档"。需要开启时先升级到正式 Phase，再写对应 PLAN。
