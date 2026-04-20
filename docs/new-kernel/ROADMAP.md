# 路线图

## Phase 0：冻结术语和边界

### Goal

建立文档控制面，让后续 Codex 改造有稳定语义。

### Scope

- 文档结构。
- 架构原则。
- north-star scenarios。
- 初始 ADR。

### Exit criteria

- 本目录 `AGENTS.md` 可用。
- `ARCHITECTURE_TARGET` 和 `ARCHITECTURE_PRINCIPLES` 完成初稿。
- `ROADMAP` 和 `STATUS` 对齐。

## Phase 1：Effect isolation

### Goal

让 outbound side effects 通过 intent/outbox/effector 边界。

### Scope

- `SendMessageIntent`
- `NoReplyChosen`
- outbound simulation recorder
- live sender effector adapter

### Non-goals

- full event kernel
- full cron rewrite
- full TDAD

### Exit criteria

- planner 不再直接发送消息。
- simulate mode 能验证 send/no-send/exactly-once。
- Scenario 1 最小版本通过。

## Phase 2：Cron 和 ingress 事件化

### Goal

让 cron、channel、collector 等入口统一成为 event producers。

### Scope

- `CronTicked`
- minimal `JobSpec`
- mock clock
- reminder verification

### Exit criteria

- 每天 9 点提醒场景可仿真。
- job-specific constraints 落在 `JobSpec`。
- Scenario 2 最小版本通过。

## Phase 3：Resource ownership + context compiler

### Goal

让未来执行上下文可编译、可审计、可回放。

### Scope

- resource ownership enforcement
- `ContextSnapshot`
- context provenance
- future context verification

### Exit criteria

- 能回答某次 run 看到了哪些资源。
- 能检测 job constraint 是否写错位置。

## Phase 4：TDAD + cleanup verifier + publish gate

### Goal

让行为验证和最小必要修改成为发布边界。

### Scope

- spec-driven scenario checks
- visible/hidden checks
- cleanup hunk pruning
- publish gate

### Exit criteria

- Scenario 4 最小版本通过。
- candidate patch 不能绕过 verification/publish gate。

## Phase 5：Legacy loop 降级

### Goal

旧 `AgentLoop` 不再是系统中枢，而是 planner consumer 或兼容 adapter。

### Scope

- legacy adapters
- routing from event runtime
- removal of direct side effects

### Exit criteria

- 主要 north-star scenarios 都通过新 runtime。
- legacy loop 只保留明确兼容职责。
