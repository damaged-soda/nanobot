# Codex 工作规则

这些规则只适用于新内核路线相关的任务和文档，不是整个 nanobot 仓库的通用贡献规则。

## Mission

保留 nanobot 的 shell，逐步把 runtime 演进为 event-sourced、effect-isolated、可仿真、可验证的新内核。

## 开始任何任务前必须阅读

- `STATUS.md`
- `ARCHITECTURE_PRINCIPLES.md`
- `ROADMAP.md`
- `NORTH_STAR_SCENARIOS.md`
- 与当前任务直接相关的 `plans/PLAN-*.md`

## 硬性规则

- 不要新增 planner 直接产生外部副作用的路径。
- 不要把 job-specific 约束写入 global memory。
- 把 `turn` 视为 event 的一种，而不是系统中心抽象。
- 新增 event / intent / effect 时，必须更新 `EVENT_CATALOG.md`。
- 新增或改变 resource 所有权时，必须更新 `RESOURCE_OWNERSHIP.md`。
- 改变验证、仿真、replay、publish gate 语义时，必须更新 `VERIFICATION_MODEL.md`。
- 改变架构边界时，必须更新 `ARCHITECTURE_TARGET.md` 或新增 ADR。
- 修改长期计划、阶段目标或当前焦点时，必须更新 `STATUS.md` 和/或 `ROADMAP.md`。

## 工作方式

- 优先做小步、可回滚、可验证的改动。
- 优先增加 adapter / shim，不要在第一步大面积重写旧路径。
- 保持 live path 和 simulate path 的结构尽量一致。
- 不要为了让测试过而引入新的隐式状态。
- 不要留下未解释的临时分支、死代码或兼容路径。

## 完成标准

一项任务完成必须同时满足：

- 相关测试、仿真或验收检查通过。
- 相关文档已经同步更新。
- 没有新增 source-of-truth 歧义。
- 没有新增 planner 直接副作用。
- 如果产生候选 patch，必须说明 cleanup verifier 或等价检查如何覆盖多余改动风险。

## 文档事实来源

- 项目是什么：`README.md`
- 当前在做什么：`STATUS.md`
- 复杂任务怎么执行：`PLANS.md` 和 `plans/*`
- 当前真实架构：`ARCHITECTURE_CURRENT.md`
- 目标架构：`ARCHITECTURE_TARGET.md`
- 架构原则：`ARCHITECTURE_PRINCIPLES.md`
- 概念模型：`DOMAIN_MODEL.md`
- 事件类型：`EVENT_CATALOG.md`
- 资源归属：`RESOURCE_OWNERSHIP.md`
- 验证与发布：`VERIFICATION_MODEL.md`
- 样板场景：`NORTH_STAR_SCENARIOS.md`
- 阶段路线：`ROADMAP.md`
- 与上游关系：`UPSTREAM_STRATEGY.md`
- 长期架构决定：`adrs/*`
