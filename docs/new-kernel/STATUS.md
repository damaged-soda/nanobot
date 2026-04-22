# 当前状态

## 当前阶段

Phase 0：Observability scaffold。

## 当前焦点

建立 trace 基础设施并在当前系统关键边界注入观测点，**不改任何现有行为**。

详细任务见 [`plans/PLAN-phase0-observability.md`](./plans/PLAN-phase0-observability.md)。

## 本阶段范围

见 [`ROADMAP.md`](./ROADMAP.md) 的 Phase 0 一节。简述：

- 定义 trace 事件结构 + `emit` API + 默认 sink。
- 在六类边界注入 trace：channel 入口 / planner 入出 / tool 前后 / channel 出口 / memory 读写 / cron 触发。
- 不新增行为、不重构现有路径。

## 验收标准

- CLI 发一条用户消息 → 产出一份完整可读的 trace，覆盖 channel 接收 → planner → tool → 发送全链路。
- Cron tick 能产生对应 trace。
- trace 结构稳定，足以承载 Phase 1 引入的 intent/effect 事件。

## 冻结区域

Phase 0 期间不动：

- planner / agent loop 的决策逻辑。
- channel 内部 `send()` 实现。
- provider 层。
- memory 系统语义。
- 上游 sync 策略。

任何超出"加观测"范围的改动都不属于 Phase 0。

## 已知风险

- 某些路径（例如工具调用、长流式输出）可能已经隐含副作用，插桩时需要注意不引入重复或遗漏。
- 某些 channel 的 send 调用点分散，初版插桩可能不完整，以 CLI 为准保证北极星场景覆盖即可，其他 channel 允许后续补齐。
- contextvar 在异步 / 多线程 / streaming 路径下的传递需要验证。

## 最后更新

2026-04-22
