# PLAN Phase 1：Outbound effect isolation

## Goal

把 planner 出口的发消息路径从无类型 `OutboundMessage` 升级为显式 `SendMessageIntent`。让 intent（planner 决定要做的动作）和 effect（真实被 channel 发出去的消息）在类型、路径、trace 上都可分辨；同时让 CLI 能在 simulate 模式下断言 intent 行为而不真正触达 channel。

北极星场景：

- **Live**：用户在 CLI 发消息，planner 要么产出 `SendMessageIntent`（必定导致后续 `channel.sent`），要么产出 `NoReplyChosen`（显式沉默）。对外行为与 Phase 0 完全一致。
- **Simulate**：同一条 CLI 链路不触达任何真实 channel。recorder 记录产出的 intent / no-reply，测试断言 exactly-once、send / no-send。

## Background

Phase 0 的侦察已经确认：

- Planner **不**直接调 `channel.send()`，走的是 `bus.publish_outbound(OutboundMessage(...))`。`bus` + `ChannelManager` consumer 已经是一堵半成品的 effect 墙。
- 但这堵墙没类型约束：`OutboundMessage` 只是个数据包；`MessageTool._send_callback: Callable[[OutboundMessage], Awaitable[None]]` 也是通用 `Callable`，没有任何结构上的保证说这条链路走到 effect 边界。
- "不回复" 当前是**沉默的**——planner 不 publish 任何东西。trace 里只能看到 `planner.exited`，看不到"planner 主动决定不发"的事实。

Phase 1 的任务：给这堵墙**加语义和类型**，再挂一个可替换的 effector，让 simulate 成为可能。不新建墙。

## Scope

### 类型升级

在 `nanobot/bus/events.py`：

- 新增 `SendMessageIntent`，字段继承 `OutboundMessage` 现有字段，再加：
  - `dedupe_key: str | None` — 用于 exactly-once 断言（同 key 的两次 intent 视为重复）。
  - `origin: Literal["planner", "tool", "system", "command"]` — 这个 intent 来自哪个产生者；Phase 1 先只用 `"planner"` 和 `"tool"`（MessageTool）。
  - `trace_id` 已在 Phase 0 加好，沿用。
- 新增 `NoReplyChosen`，字段最少：`trace_id`、`reason: str | None`、`origin`。
- `OutboundMessage` **保留**：它是"给 channel 发送的数据包"，Phase 1 之后由 effector 从 `SendMessageIntent` 构造。Planner 不再直接 new `OutboundMessage`。

### Bus / Effector

- `MessageBus` 新增 `intents: asyncio.Queue[SendMessageIntent | NoReplyChosen]`；保留现有 `outbound`（effector 内部用）。
- 引入 `Effector` Protocol（一个方法 `handle(intent) -> None`）。
  - `ChannelEffector`（live）：把 `SendMessageIntent` 转成 `OutboundMessage`，走现有 `ChannelManager._send_once` 逻辑；`NoReplyChosen` 只发 trace 不做别的。
  - `RecorderEffector`（simulate）：把收到的 intent 追加到内存列表，不触达任何 channel。
- Channel 内部 `send()`、重试策略、stream coalesce 等**一行不改**。

### Planner 出口迁移

`agent/loop.py` 里 7 个 `bus.publish_outbound(OutboundMessage(...))` 调用点全部改为 `bus.publish_intent(SendMessageIntent(...))`。其中 stream-delta / stream-end 这类控制消息**不是** intent——它们是 effect 层内部的传输分片，保留走 `bus.outbound`（由 effector 内部继续使用），不升级。

`MessageTool._send_callback` 签名从 `Callable[[OutboundMessage], ...]` 收紧为 `Callable[[SendMessageIntent], ...]`（或更精确的 Protocol）。注册处 `loop.py:284` 对应改为 `bus.publish_intent`。

### NoReplyChosen

显式标记 "planner 主动沉默"。当前代码里哪些路径算沉默需要侦察确认（Step 1），但至少包括：

- `_dispatch` 里 `response is None and msg.channel != "cli"` 的那个分支（CLI 分支发了空 OutboundMessage，是"沉默的显式终止信号"，也需要评估要不要改）。
- tool 调用完成但没触发 MessageTool 的 turn（tool-only 分支）。

每个路径在迁移时都要问一遍：这究竟是 "planner 决定不回复" 还是 "planner 还在处理中"？只有前者发 `NoReplyChosen`。

### CLI simulate pilot

CLI 新增 `--simulate` flag（`nanobot agent --simulate`）：

- Live 模式（默认）：装配 `ChannelEffector` + 现有 channel 启动流程。
- Simulate 模式：装配 `RecorderEffector`，**不**启动任何真实 channel；CLI 的 `_consume_outbound` 循环被替换为 "从 recorder 拉 intent 并显示摘要"。
- 退出时 dump 一份 recorder 快照（intent 列表）到 stdout 或文件。

### Trace

Phase 0 的 kind 沿用，新增：

- `intent.published`（producer 发 intent 时）
- `intent.consumed`（effector 开始处理 intent 时）
- `noreply.chosen`

`channel.sent` 在 live effector 里保留（与 Phase 0 一致），成为 "intent → effect" 链路的尾端。

## Non-goals

- **不动** channel 内部 `send()` / `send_delta` / 重试 / stream coalesce。
- **不动** provider 层、memory 语义、agent loop 决策逻辑。
- **不覆盖** system channel / slash command / heartbeat / subagent 的 OutboundMessage 产生点（Phase 0 STATUS 已记为 gap，留给后续）。
- **不做** intent 持久化 / replay / cross-process effector（Later，冻结中）。
- **不做** 非 CLI 的 simulate（telegram / feishu / discord 的 simulate 留给需要时再开）。
- **不加新依赖**——标准库 + 已有类型足够。

## Steps

每一步都应是一个独立可评审单元。

1. **侦察（read-only）**：
   - 枚举 planner / tool 侧所有 `OutboundMessage` 构造点（Phase 0 已知 7 + MessageTool 1，确认是否遗漏）。
   - 枚举"显式沉默"候选路径（_dispatch 的空 OutboundMessage 分支、tool-only turn 尾部等）。
   - 枚举 stream-delta / stream-end 等控制消息路径，确认不在迁移范围。
   - 产出 `<file>:<line> → 迁移类别（intent / noreply / 不迁移）` 对照表。
2. **SendMessageIntent + NoReplyChosen 类型**：在 `bus/events.py` 新增两个 dataclass；加 `MessageBus.publish_intent` / `consume_intent`；单测。**不改**任何 producer。
3. **Effector 抽象**：定义 `Effector` Protocol；实现 `ChannelEffector`（把 intent 转成现有 OutboundMessage 流程）和 `RecorderEffector`。`ChannelEffector` 用回 Phase 0 的 `_send_once`，channel 内部零改动。单测 recorder。
4. **接线（live 模式）**：启动流程里拉起 `ChannelEffector` 作为 intent consumer，现有 channel manager 的 outbound consume loop 保留不变。此时 intent 队列是空的（没人 publish），系统行为 = Phase 0。
5. **Planner 出口迁移**：`agent/loop.py` 里的 7 个 `publish_outbound(OutboundMessage(...))` 改为 `publish_intent(SendMessageIntent(...))`。`MessageTool` 签名收紧，注册处同步。此时 live 模式完整跑通新链路。
6. **NoReplyChosen 插桩**：Step 1 列出的沉默路径显式发 `NoReplyChosen`。trace 里新增 `noreply.chosen`。
7. **CLI simulate flag**：CLI 入口加 `--simulate`；simulate 时装 `RecorderEffector`，跳过真实 channel 启动；退出时 dump recorder。
8. **北极星测试（live）**：一个端到端 test：CLI live 模式 + mock provider，assert trace 里有 `intent.published` → `channel.sent`，trace_id 贯穿。
9. **北极星测试（simulate）**：同样 mock 路径，simulate 模式下 assert：
   - 有回复场景 → recorder 恰好收到 1 条 `SendMessageIntent`，无任何 `channel.sent`。
   - 无回复场景 → recorder 恰好收到 1 条 `NoReplyChosen`，无 `SendMessageIntent`。
   - dedupe_key 重复时 recorder 能识别（或至少断言保留原始两条）。
10. **文档同步**：更新 `STATUS.md` 切 Phase 2；`ROADMAP.md` 的 Phase 2 scope 基于 Phase 1 实际类型再细化。

## Acceptance checks

- CLI live 模式端到端行为与 Phase 0 完成时完全一致（现有集成测试全绿 + 手工 smoke）。
- CLI simulate 模式下不产生任何 `channel.sent` trace 事件；recorder 产出与 planner 决策一一对应。
- Trace 里 `intent.published` / `intent.consumed` / `channel.sent` / `noreply.chosen` 清晰区分，trace_id 贯穿。
- 没有任何 `OutboundMessage` 的裸构造出现在 planner / tool 路径（只允许在 effector 内部构造）。
- `MessageTool.send_callback` 签名为 intent producer，不再接受通用 `Callable[[OutboundMessage], ...]`。

## Risks & mitigation

- **Stream-delta / stream-end 被误升级**：这些是 effect 层内部传输，不是 intent。Step 1 侦察必须明确把它们排除，Step 5 迁移时照对照表走。
- **"沉默" 路径的认定歧义**：哪些算 `NoReplyChosen`、哪些是"系统还在处理"不该发事件，需要在 Step 6 逐路径 review。宁可少发、不可错发——漏一个先记为已知 gap，好过把中间态误标为 no-reply。
- **Effector 生命周期**：live 的 ChannelEffector 需要跟 ChannelManager 的启动 / 关闭顺序协调，避免双消费或遗漏。Step 4 先以"空 intent 队列"验证接线，再 Step 5 开始灌流量。
- **Dedupe 语义早熟**：Phase 1 不做真正的重放 / 幂等，`dedupe_key` 先只是标签，RecorderEffector 仅用于测试断言。实际去重逻辑等到 Later。
- **System channel / slash / heartbeat 的 OutboundMessage 旁路**：Phase 0 已标记。Phase 1 明确不处理，但 Step 1 要再次点名确认没有新增来源。

## Docs to update（完成时）

- [`STATUS.md`](../STATUS.md)：标记 Phase 1 完成，切入 Phase 2；把 intent / effect 类型和 effector 抽象写进"当前形态"。
- [`ROADMAP.md`](../ROADMAP.md)：如落地偏离计划，更新 Phase 1 摘要；Phase 2（cron 事件化）基于 Phase 1 的 intent 类型再细化 scope。

## Exit criteria

- Planner 路径上不存在 `OutboundMessage` 裸构造，全部走 `SendMessageIntent`（或 `NoReplyChosen`）。
- `MessageTool` 等决策者工具的 send callback 是 intent producer 类型，结构上禁止旁路。
- CLI simulate 模式可跑、可断言 send / no-send / exactly-once。
- Trace 能稳定区分 intent 与 effect，是 Phase 2（cron 事件化）引入 `CronTicked` 事件时的现成载体。
