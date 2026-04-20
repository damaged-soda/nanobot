# 执行计划

对于跨文件、跨阶段或涉及架构边界的改造，必须使用计划文件。

## 什么时候需要计划

- 显著重构。
- 横切多个模块的架构变化。
- 需要多步迁移的兼容改造。
- 任何预期超过一个短会话的任务。
- 会影响 event / intent / effect / resource 语义的任务。

## 每个计划必须包含

- Goal
- Background
- Scope
- Non-goals
- Architecture impact
- Steps
- Acceptance checks
- Rollback / kill switch
- Docs to update
- Exit criteria

## 当前计划

- `plans/PLAN-001-effect-isolation.md`
- `plans/PLAN-002-cron-as-event-source.md`
- `plans/PLAN-003-context-compiler.md`
