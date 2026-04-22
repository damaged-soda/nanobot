# nanobot 新内核改造文档

这个目录是 nanobot fork 的改造控制面。不替代根目录 `README.md`，也不替代 `docs/` 下的用户文档。

## 一句话定位

**保留 nanobot shell，重做 runtime kernel。**

- `shell`：用户可见的产品外壳，包括 CLI、gateway、channel 适配、provider、workspace、tool、skill。这部分继续跟随上游，不做重写。
- `kernel`：真正决定系统如何运行的内核，包括事件模型、副作用边界、观测、仿真、验证。这部分是 fork 的重做对象。

## 为什么需要这个 fork

当前 nanobot 的运行模型偏 loop-centric：用户消息、cron、heartbeat 等入口容易被压成"把一段 prompt 交给 agent loop"。这带来几个结构性问题：

- 决策和副作用耦合，planner 可能直接调 channel、写文件、调外部 API，导致仿真和回放困难。
- 持久约束归属不明，job 专属规则常常被写进 global memory。
- 长期任务被压成单次 turn，例如"24 小时采集 + 每日汇总"本应是两条流，却被写成一个 cron prompt。
- 未来执行上下文不可重放，很难证明"这次写入的约束在未来真正执行时是否可见"。

这些都不是打补丁能解决的问题，所以选择 fork，把 runtime kernel 逐步换掉。

## 核心概念（极简版）

三个基础抽象：

- **Event**：已经发生的事实。命名过去式，例如 `UserMessageReceived`。
- **Intent**：系统准备做的动作。命名以 `Intent` 结尾，例如 `SendMessageIntent`。
- **Effect**：真实产生的外部结果。例如 `MessageSent`。

一条核心规则：**planner 只能产出 event 或 intent，不能直接产生 effect**。

这是目标状态，当前代码还没满足。路线图就是逐步把现实推向这个状态。

## 执行策略：先观测后重构

内核重构对外行为不变，没有观测就没有安全网。所以在动任何结构之前，先让被改动的区域在 trace 里完全可见。

这个"观测先行"的策略同时是未来 event log 的雏形——trace 格式本身就会演进成 event 格式，投入不浪费。

## 阶段概览

- **Phase 0（当前）**：observability scaffold。建立 trace 格式、emit API、最小 sink，在当前系统关键边界注入观测点，**不改行为**。
- **Phase 1**：outbound effect isolation。把 planner 出口的发消息路径改走 `SendMessageIntent` → effector。以 CLI 作为 simulate pilot。
- **Phase 2**：cron 事件化。cron 不再直接 trigger prompt，而是产生 `CronTicked` 事件。
- **Later（frozen）**：context compiler、TDAD、cleanup verifier、publish gate 等。等 Phase 0–2 走完再决定。

## 阅读顺序

1. [`PRINCIPLES.md`](./PRINCIPLES.md) — 架构原则，后续所有改动的判据。
2. [`STATUS.md`](./STATUS.md) — 当前阶段、焦点、exit 标准。
3. [`ROADMAP.md`](./ROADMAP.md) — 阶段路线。
4. [`plans/PLAN-phase0-observability.md`](./plans/PLAN-phase0-observability.md) — 当前阶段详细计划。

Agent 工作规则（Codex / Claude Code 共用）放在仓库根的 [`AGENTS.md`](../../AGENTS.md)，自动加载。
