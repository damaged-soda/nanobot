# 路线图

本文件只覆盖已经决定要做或即将要做的阶段。更远的想法放在 Later 区，明确标为 frozen，避免过度设计。

## Phase 0：Observability scaffold（已完成）

### Goal

让当前系统在 trace 里完全可见，为后续重构提供安全网，同时沉淀出未来 event log 的格式雏形。

### 成果

- trace 事件结构 `{ts, run_id, trace_id, kind, payload}`（JSONL）稳定。
- 在 6 类关键边界注入观测：channel 入口 / planner 入出 / tool 前后 / channel 出口 / memory 读写 / cron 触发。
- sink 走 env 门控（`NANOBOT_TRACE` → stderr，`NANOBOT_TRACE_FILE` → 文件），默认零 sink。
- trace_id 跨 task 边界通过消息字段传递；contextvar 在同 task 内续跑。
- 集成测试覆盖 CLI 北极星链路和 cron 链路。

详见 [`plans/PLAN-phase0-observability.md`](./plans/PLAN-phase0-observability.md)（历史存档）。

## Phase 1：承诺资源化 + Simulate（当前）

### Goal

让 LLM 对"未来要怎么做"的修改走一条可验证的硬路径。用户说"以后 X 不再出现"时，LLM 必须把这条落成结构化 **Commitment**（不再写 memory.md），并能在同一 turn 内用 simulate 工具验证"到下次真 cron 跑时，这条规则是不是真的生效"。

### 核心痛点

用户让 nanobot 定期发新闻 briefing（AI / 国际 / 加密 / 神经科学）。某天说"以后不要神经科学"。nanobot 把这条写进 memory.md 就当处理完了，结果第二天 briefing 仍然包含神经科学——因为 memory.md 里的这条规则在 cron 真执行时**没有进 prompt**。

对 LLM 来说，反馈要等到第二天 cron 真跑完才到。闭环形同虚设。

### Scope（概述）

- `Commitment` 资源：稳定 id + prose text + 状态 + 审计字段。
- LLM 工具：`create_commitment` / `revoke_commitment` / `list_commitments`。
- Prompt builder：cron job 执行时把 active commitments 注入 prompt。
- Simulate 机制：contextvar + 轻量 recorder，只在 `MessageTool` 的 send path 拦截；其他路径零改动。
- `simulate_job_run` 工具：LLM 可在 turn 内调用，跑完整 job 执行链路但真实发送被拦截，返回 outputs + verdicts。
- Verification helper：独立 LLM 调用，判决 (evidence, claim)。
- Trace 新 kind：`commitment.created` / `commitment.revoked` / `job.simulated` / `verification.completed`。

**刻意不做**：不改真 cron 的投递行为（Phase 2）；不 mock 时间；不做 intent 类型层（验证不需要）。详见 PLAN。

### 北极星

用户在 CLI 说"以后新闻别再出现神经科学"：

1. LLM 调 `create_commitment(job_id=<news_briefing>, text="...")`。
2. LLM 调 `simulate_job_run(job_id=<news_briefing>)`。
3. verdict 若 pass → 回复用户"已记下并已验证"；若 fail → LLM 有机会改 commitment 表述、再 simulate、再 verify，通过才回复。
4. 第二天真 cron 跑时，prompt 里有这条 commitment，行为一致。

### Exit criteria

- 北极星场景在 CLI 下跑通（集成测试）。
- Commitment store 在进程重启后仍可读。
- MessageTool 在 simulate 下不触达真 channel（recorder 有捕获，真 send 计数为 0）。
- Trace 能完整串起"改承诺 → simulate → verify"链路，trace_id 贯穿。

详见 [`plans/PLAN-phase1-commitments.md`](./plans/PLAN-phase1-commitments.md)。

## Phase 2：Enforcement + 自动迭代（β，待启动）

α 给 LLM 提供**能力**；β 给**习惯和保障**。

### 拟议 scope

- 真 cron 触发时**自动**走 pre-delivery simulate + verify；verdict fail 则阻断投递或降级（具体策略 PLAN 时再定）。
- System prompt / skill 推动 LLM 在修改 commitment 后**习惯性**调用 simulate，不再靠它主动想起来。
- Verification 历史持久化并喂回下一轮 context，LLM 能看到"这条 commitment 过往兑现统计"。
- 失败后的自动迭代循环（LLM 改 → 再 simulate → 通过为止），可能需要最小的 "LLM-as-loop" 辅助结构。

启动时机：α 在真实使用里跑一段时间，明确出 verdict 正确率、commitment 形态、simulate 的副作用边界，再写 β 的 PLAN。

## Later（frozen）

以下方向明确不在当前视野内。Phase 1 / 2 走完后再评估是否开启。

- **Context compiler（完整版）**：可 hash / 可重放的上下文快照。α 的 prompt builder 已经是个最小版，但离"可 hash 重放"还有距离。
- **Mock time / 时间敏感 simulate**：支持"模拟明天 9 点 cron 触发"。α 目前假设 simulate 以"现在"为基准。
- **其他资源化**：`UserProfile` / `ProjectRules` / `ObservationStore` / `KnowledgeBase`——如果 α 之后发现除 commitment 之外还有大量规则零散在 memory 里，再按同样模式处理。
- **分布式 / 多进程 runtime**：v1 刻意单进程，规模化另议。
- **Legacy `AgentLoop` 全面重构**：目前 AgentLoop 继续承担 planner 角色，Phase 1 不动它的决策逻辑。全面重构属于 Later。

Frozen 不代表否决，只代表"现在不做、不设计、不写文档"。需要开启时先升级到正式 Phase，再写对应 PLAN。
