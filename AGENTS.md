# AGENTS.md

本文件是 nanobot 仓库在任何自动化 agent（Codex、Claude Code 等）中启动时的共同规则。规则区分任务类型，不是所有改动都遵循同一套。

## 第一步：识别任务属于哪一边

- **Kernel 工作**：新内核路线相关的改造，包括 agent loop 行为、event 模型、副作用边界、观测 / trace、仿真 / replay、资源归属、新内核文档与 PLAN。
  → 执行下面的 **Kernel 规则**。

- **Shell 工作**：channel adapter、provider、workspace、tool、skill、上游 sync、常规 bug 修复与功能迭代。
  → 按现有 nanobot 贡献惯例处理，遵循 `docs/` 下的用户文档与代码现有模式。**不要**把 Kernel 规则强加进来。

- **不确定属于哪一边**：先问，不要自己裁定。

## Kernel 规则

### Mission

保留 nanobot shell，把 runtime 逐步演进为 event-sourced、effect-isolated、可仿真、可验证的新内核。当前第一步是让系统可观测（Phase 0）。

### 开始任何 Kernel 任务前必读

- `docs/new-kernel/PRINCIPLES.md`
- `docs/new-kernel/STATUS.md`
- `docs/new-kernel/ROADMAP.md`
- 当前阶段的 `docs/new-kernel/plans/PLAN-*.md`

### 硬性规则：始终适用

- **不超前设计**：没有代码承载的抽象、目录、catalog、schema 不写进文档。
- **不绕过原则**：如果某条计划和 `PRINCIPLES.md` 冲突，先讨论修改原则，不允许在计划里偷偷绕过。
- **不把 `turn` 当系统中心**：新增代码路径时不要强化 turn-centric 假设。
- **不把 job 专属约束写入 global memory**：即使当前还没有 `JobSpec`，也不要反向强化错位。

### 硬性规则：Phase 0 专属

- **只加观测，不改行为**：Phase 0 期间任何改动必须是"插桩"性质。planner、channel 内部、provider、memory 语义一律不动。
- **Trace 结构稳定优先**：trace 事件结构（顶层字段）变更需要谨慎，它会演进为未来 event log。

### Kernel 任务完成标准

- 相关测试或验收检查通过。
- 对应 STATUS / ROADMAP / PLAN 已同步更新。
- 没有新增 source-of-truth 歧义。
- 没有新增 planner 直接副作用（Phase 0 应该一个都没有）。

## 通用规则（两边都适用）

### 确认节奏

- 非 trivial 改动按步确认，不要一口气推到底。
- 涉及删除、重命名、跨模块重构、破坏性操作（`push --force`、`reset --hard`、`rm -rf` 等）前必须先问。
- 上游 sync / merge 前必须先问，不要自动合并。

### 文档纪律

- 不主动扩写文档。
- `docs/new-kernel/` 目前是 6 个文件（README / PRINCIPLES / ROADMAP / STATUS / AGENTS 已合并到根目录本文件 / plans/PLAN-phase0-observability.md）。不要新增文件或目录，PLAN 除外，且只为当前或下一个 Phase 写。
- 没有要求时不要生成 CHANGELOG、README 更新、架构决策记录。

### Git 规则

- 未经明确授权不要 commit 或 push。
- 不要修改 git config。
- 不要用 `--no-verify`、`--no-gpg-sign` 等绕过 hook / 签名的选项。
- 如果某次 commit 被 hook 拦住，修完问题后新建 commit，不要 `--amend` 上一条。

### 工作方式

- 优先小步、可回滚、可验证的改动。
- 不要为了让测试过而引入隐式状态。
- 不要留下未解释的临时分支、死代码或兼容路径。
- 插桩或改造时，保持 live path 与 simulate path 结构一致（simulate 在 Phase 1 才真正出现，但现在的选择就要为它铺路）。

## 文档事实来源（Kernel）

- 项目定位、核心思想：`docs/new-kernel/README.md`
- 架构原则：`docs/new-kernel/PRINCIPLES.md`
- 当前在做什么：`docs/new-kernel/STATUS.md`
- 阶段路线：`docs/new-kernel/ROADMAP.md`
- 当前 PLAN：`docs/new-kernel/plans/PLAN-phase0-observability.md`
