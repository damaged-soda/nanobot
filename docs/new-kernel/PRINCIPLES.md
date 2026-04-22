# 架构原则

本文件列出所有后续改造都必须服从的核心原则。后续计划、代码、文档都引用这里。如果某条原则和具体计划冲突，优先修改原则本身（需要讨论），不允许在计划里偷偷绕过。

## 1. 保留 shell，重做 kernel

nanobot 的产品外壳继续与上游对齐，是这个 fork 的复用资产：CLI、channel adapter、provider、workspace、tool、skill。

真正重做的是 runtime kernel：事件模型、副作用边界、观测、仿真、验证。

把精力花在 shell 上是浪费，因为上游会继续演进；把精力花在 kernel 上才是这个 fork 存在的理由。

## 2. 先观测后重构

任何结构性改动，必须先让被改动的区域在 trace 里完全可见，再动结构。

原因：内部重构对外行为不变，没有观测就没有安全网，改动前后我们说不清哪里变了、哪里没变。把"观测"作为 Phase 0，是因为它既是安全网，也是未来 event log 的雏形，投入不会浪费。

## 3. Event / Intent / Effect 三分

- **Event**：已经发生的事实，命名用过去式，例如 `UserMessageReceived`。
- **Intent**：系统准备做的动作，命名以 `Intent` 结尾，例如 `SendMessageIntent`。
- **Effect**：外部世界或持久状态实际发生的结果，例如 `MessageSent`。

Event 表示"发生了什么"，Intent 表示"打算做什么"，Effect 表示"真做了什么"。三者不混用，也不能用 memory / log / context 这些万能词替代。

## 4. Turn 不是中心

用户消息、cron tick、工具返回、外部采集结果都是 event，不是某一次 turn 的附属物。旧 `AgentLoop` 的"一次 turn"只是一种 event 消费模式，不是系统中心抽象。

## 5. Planner 不直接产生副作用（目标）

决策者（planner / summarizer / memory reducer）只能产出 event 或 intent，不能直接调 channel、写文件、调外部 API。真实副作用由 effector 消费 intent 后执行。

这是目标状态，当前代码尚未满足。Phase 1 处理 outbound 这一类最常见的副作用。

## 6. 持久约束必须有显式 owner（目标）

会影响未来自动执行的信息，必须归属到具名 resource（未来可能是 `JobSpec` / `UserProfile` / `ProjectRules` 等）。memory 不是万能存储。

这是目标状态，当前仓库不强制此规则，但新增代码路径时应避免把 job 专属约束写入 global memory。

## 7. Simulation 与 Replay 是一级能力

同一条事件链应能在 live / simulate / replay 三种模式下运行，结构一致。仿真不是 debug 附件，而是验证基础设施。Phase 0 的 trace 格式同时作为 replay 的载体。

## 8. 不超前设计

文档只描述当前阶段有代码承载或即将承载的东西。没有代码的抽象、目录、catalog、schema 不写进文档。

原因：空定义会随实现变形，维护纪律的成本高过价值。需要时再写，宁可晚不要早。
