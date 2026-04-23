# 当前状态

## 当前阶段

**Phase 1：承诺资源化 + Simulate**（α）。PLAN 已就位，尚未动工。

详见 [`plans/PLAN-phase1-commitments.md`](./plans/PLAN-phase1-commitments.md)。

## 本阶段焦点

让用户对"未来要怎么做"的修改不再落到 memory.md，而是走结构化的 Commitment；让 LLM 能在同一 turn 内 simulate 验证修改是否真生效。

北极星：用户说"以后新闻不要神经科学" → LLM 创建 commitment → 同 turn simulate → verdict 判决 → 通过才回复用户。

## Phase 0 成果（已归档）

Trace scaffold 已落地，六类边界全部发事件（`channel.received` / `planner.entered` / `planner.exited` / `tool.called` / `tool.returned` / `channel.sent` / `memory.read` / `memory.write` / `cron.fired`）。trace_id 跨 task 边界通过消息字段 + contextvar 续跑。15 单测 + 2 集成测试全部通过。

详见 [`plans/PLAN-phase0-observability.md`](./plans/PLAN-phase0-observability.md)。

## 已知 gap（Phase 1 范围外）

- **Streaming 出口**：`send_delta` 路径不发射 `channel.sent`（只有非流式 send 覆盖）。
- **System channel / slash / heartbeat producer**：这些 OutboundMessage 不在 trace context 下，链路断开。
- **Dream 内部**：被 cron 触发时继承 trace_id，但 Dream 自己的 AgentRunner 不发 `planner.*` 事件。

以上都不阻碍 Phase 1 推进，出现具体痛点时再补。

## 方向调整记录（2026-04-23）

原 Phase 1（Outbound effect isolation）在 Step 2 之后讨论中发现方向错位：

1. Phase 0 侦察证明 planner 实际已经不直接调 channel，"intent/effect 类型洁癖"在解决不存在的问题。
2. 用户真正痛点是"修改了规则结果没生效"的信任断裂，不是"planner 混用 channel API"。
3. 原 Phase 1 的大部分 step 运行时行为零变化，只在加结构标签——典型的超前设计。

已弃掉的原 Phase 1 PLAN（`PLAN-phase1-outbound-effect-isolation.md`）从仓库删除。Phase 1 Step 2 加的类型（`SendMessageIntent` / `NoReplyChosen` / `IntentOrigin` / `Intent` / `bus.intents` 队列及相关方法）在新方向下无消费者，作为死代码处理（具体动作见 PR）。

## 冻结区域

Phase 1 期间不动：

- channel 内部 `send()` 实现、重试、stream coalesce。
- provider 层。
- planner 决策逻辑（`AgentLoop._run_agent_loop` 不改行为）。
- 上游 sync 策略。

## 最后更新

2026-04-23
