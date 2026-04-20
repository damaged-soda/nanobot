# PLAN-003：Context Compiler

## Goal

把“每次现场拼 prompt”的模式逐步替换为可审计、可 hash、可重放的 context compiler。

## Background

当前架构中，上下文往往在每次 run 时动态拼装。这样很难证明某个约束在未来执行时一定可见，也很难调试“为什么 agent 当时没看到某条规则”。

目标是引入 `ContextCompiler`：它从事件、资源、run mode、policy profile 编译出一份上下文快照。

## Scope

- 定义 context snapshot 的最小语义。
- 定义上下文来源和 resource 引用。
- 记录编译结果 hash / provenance。
- 在 simulate/replay 中复用同一编译路径。

## Non-goals

- 一次性重写所有 memory/context 逻辑。
- 完整长短期记忆系统重构。
- 复杂检索系统。

## Architecture impact

这一步确立“未来执行上下文是可回放工件”的原则。

## Steps

1. 梳理现有 context 来源。
2. 定义 `ContextSnapshot` 最小字段。
3. 定义 resource -> context 的编译规则。
4. 让至少一个 north-star scenario 使用 context snapshot。
5. 增加验证：job constraint 是否出现在 future context 中。

## Acceptance checks

- 能解释某次 run 使用了哪些 resource。
- 能重建某次 simulate run 的上下文。
- 能检测 job-specific 约束是否误写入 global memory。

## Docs to update

- `../ARCHITECTURE_TARGET.md`
- `../DOMAIN_MODEL.md`
- `../RESOURCE_OWNERSHIP.md`
- `../VERIFICATION_MODEL.md`
