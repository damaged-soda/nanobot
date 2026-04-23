# AGENTS.md

本文件是 nanobot 仓库在任何自动化 agent（Codex、Claude Code 等）中启动时的共同规则。规则区分任务类型，不是所有改动都遵循同一套。

## 第一步：识别任务属于哪一边

- **Runtime 工作**：runtime 演进路线相关的改造，包括 agent loop 行为、承诺资源、副作用拦截 / 仿真、观测 / trace、验证循环、runtime 文档与 PLAN。
  → 执行下面的 **Runtime 规则**。

- **Shell 工作**：channel adapter、provider、workspace、tool、skill、上游 sync、常规 bug 修复与功能迭代。
  → 按现有 nanobot 贡献惯例处理，遵循 `docs/` 下的用户文档与代码现有模式。**不要**把 Runtime 规则强加进来。

- **不确定属于哪一边**：先问，不要自己裁定。

## Runtime 规则

### Mission

保留 nanobot shell，把 runtime 逐步演进为**可观测、可仿真、可自验证**的形态。核心 thesis：LLM 必须能在 turn 内验证自己对未来行为的修改，不靠等真 cron 跑完事后复盘。

Phase 0（observability）已完成。当前 Phase 1 focus 是"承诺资源化 + Simulate 能力"。

### 开始任何 Runtime 任务前必读

- `docs/runtime/PRINCIPLES.md`
- `docs/runtime/STATUS.md`
- `docs/runtime/ROADMAP.md`
- 当前阶段的 `docs/runtime/plans/PLAN-*.md`

### 硬性规则：始终适用

- **不超前设计**：没有代码承载的抽象、目录、catalog、schema 不写进文档。Phase 1 第一版因违反这条踩过一次坑（effector 整层建了又删），引以为戒。
- **不绕过原则**：如果某条计划和 `PRINCIPLES.md` 冲突，先讨论修改原则，不允许在计划里偷偷绕过。
- **不把 `turn` 当系统中心**：新增代码路径时不要强化 turn-centric 假设。
- **不把影响未来执行的规则写进 memory**：持久承诺必须走结构化 Commitment。memory 只承担短期会话工作记忆。

### 硬性规则：Phase 1 专属

- **MessageTool 的 send path 是 simulate 的唯一陷阱点**：在此处插 contextvar 拦截。不要把拦截扩散到 bus / channel / manager，否则破坏"channel 内部零改动"的承诺。
- **Trace 结构稳定优先**：顶层字段（`ts` / `run_id` / `trace_id` / `kind` / `payload`）不动；新增 kind 按 Phase 0 沿用的 dotted-name 惯例。
- **simulate 的副作用假设要显式**：如果某段 job 执行路径包含非 read-only 副作用（写外部状态、调不可逆 API），不能默认认为它可以被 simulate——需要在 PLAN 或 STATUS 中列为 known limitation。

### Runtime 任务完成标准

- 相关测试或验收检查通过。
- 对应 STATUS / ROADMAP / PLAN 已同步更新。
- 没有新增 source-of-truth 歧义（特别是承诺类信息只在 commitment store 里有一份）。
- 没有新增 "不通过 MessageTool 的真 channel send"。

## 通用规则（两边都适用）

### 确认节奏

- 非 trivial 改动按步确认，不要一口气推到底。
- 涉及删除、重命名、跨模块重构、破坏性操作（`push --force`、`reset --hard`、`rm -rf` 等）前必须先问。
- 上游 sync / merge 前必须先问，不要自动合并。

### 文档纪律

- 不主动扩写文档。
- `docs/runtime/` 目前是这些文件：`README.md` / `PRINCIPLES.md` / `ROADMAP.md` / `STATUS.md` / `plans/PLAN-phase0-observability.md`（历史存档）/ `plans/PLAN-phase1-commitments.md`（当前）。不要新增文件或目录，PLAN 除外，且只为当前或下一个 Phase 写。
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
- 插桩或改造时，保持 live path 与 simulate path 结构一致。simulate 在 Phase 1 落地；不要在代码里做"live 和 simulate 分叉"的判断，一切通过统一陷阱点（contextvar）自然切换。

## 文档事实来源（Runtime）

- 项目定位、核心思想：`docs/runtime/README.md`
- 架构原则：`docs/runtime/PRINCIPLES.md`
- 当前在做什么：`docs/runtime/STATUS.md`
- 阶段路线：`docs/runtime/ROADMAP.md`
- 当前 PLAN：`docs/runtime/plans/PLAN-phase1-commitments.md`
