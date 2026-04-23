# PLAN Phase 1：承诺资源化 + Simulate 能力

## Goal

让 LLM 对未来行为的修改走一条**可验证**的硬路径：用户请求"以后 X 不再出现在 Y 里"时，LLM 必须把这条规则落成一条结构化的 **Commitment**（不再写 memory.md），并能在**同一 turn 内**调用 simulate 验证"到下次那个 job 真跑的时候，这条规则是不是真的生效了"。

北极星场景：

- 用户说"以后新闻别再出现神经科学相关内容"。
- LLM 调 `create_commitment(job_id=<news_briefing>, text=...)`。
- LLM 调 `simulate_job_run(job_id=<news_briefing>)`：完整复刻 cron 会跑的那条链路，但真实发送被拦截；产出 briefing 文本 + verification verdict。
- verdict 说 "没有神经科学相关内容" → LLM 告诉用户"已记下并已验证下次会生效"。
- verdict 说 "仍然出现了" → LLM 有机会改措辞、再 simulate、再 verify，直到满意才回用户。

## Background

Phase 0 的 trace 让 job 运行**事后可见**，但对"LLM 改了规则，下次真会生效吗"这个问题没有手段——必须等到真 cron 跑完才知道，对 LLM 来说反馈闭环形同没有。

Phase 1 的原设计（outbound effect isolation）围绕"给 planner 出口加类型洁癖"，侦察后发现：

1. planner 实际**已经**走 bus 不直接碰 channel，洁癖处理的是不存在的问题。
2. 真正的痛点是：LLM 修改未来行为的通路太软——写 memory.md 和改实际执行规则**在系统层面没有区分**，LLM 可以选"写个笔记"来假装处理了，结果未来不生效。
3. 用户交付的**持久承诺**（定期 briefing 要遵循的规则、盯消息的过滤条件、提醒的措辞）本质上和"prompt 里的一行提示"是两个抽象层级，但当前全混在 memory 里。

所以方向调整：

- **不**再搞 intent/effect 类型洁癖。
- **构建**"持久承诺作为一等资源"的存储和工具。
- **给** LLM 一个能在 turn 内立刻执行的 simulate 工具，让它自己验证修改。

## Scope

### 1. Commitment 作为 CronJob 的字段

Commitment **不是**独立实体。它是 `CronJob` 上的一个可演化字段，和 `payload` / `schedule` / `state` 同级：

```json
{
  "id": "b7c233fa",
  "name": "Morning news briefing",
  "schedule": {...},
  "payload": {
    "kind": "agent_turn",
    "message": "Send a morning news briefing...",
    ...
  },
  "commitments": [
    {
      "id": "c5",
      "text": "未来的新闻不再出现神经科学相关信息",
      "origin": "user_request",
      "status": "active",
      "created_at_ms": 1779000000000,
      "source_trace_id": "xxx...",
      "revoked_at_ms": null,
      "revoked_reason": null,
      "verification_history": [
        { "run_at_ms": ..., "run_kind": "simulate", "verdict": "pass", "detail": null },
        { "run_at_ms": ..., "run_kind": "live",     "verdict": "fail", "detail": "..." }
      ]
    }
  ],
  "state": {...}
}
```

**外壳结构化**：`id` / `origin` / `status` / `created_at_ms` / `verification_history` / ...
**内容 prose**：`text` 字段。LLM 不预定义"append_exclusion"这种操作词汇——修改 = 新建 / revoke / supersede。

**对称状态保证**：无论用户是"每天发新闻，不要神经科学"一次说完，还是先说"每天发新闻"后补"不要神经科学"，最终 job 的数据形态一致（`payload.message` 描述 + `commitments` 中一条关于神经科学的规则），避免"前者进 payload、后者进独立 store"的错位。

### 2. 持久化 + 加载

- **不新建存储**：commitments 是 `CronJob` 的一个 JSON 字段，随 `jobs.json` 整体读写，利用 `CronService._load_store` / `_save_store` 现有 pattern。
- **旧数据兼容**：加载没有 `commitments` 字段的老 job 时默认为 `[]`。
- **CRUD 入口**：在 `CronService` 上加 `add_commitment(job_id, commitment)` / `revoke_commitment(job_id, commitment_id, reason)` / `list_commitments(job_id, status)` / `append_verification(job_id, commitment_id, record)`，写完调 `_save_store`。

这样做避免了并列实体带来的一系列问题（独立文件锁、跨文件一致性、job 删除时 commitment 孤儿）。代价是 jobs.json 会变大；通过 `verification_history` 的上限（参照现有 `run_history` 的 `_MAX_RUN_HISTORY=20`）控制增长。

### 3. LLM 工具（3 个新 tool）

- `create_commitment(job_id: str, text: str, origin?: str = "user_request") -> commitment_id`
- `revoke_commitment(job_id: str, commitment_id: str, reason?: str) -> None`
- `list_commitments(job_id: str, status?: str = "active") -> list[Commitment]`

三个工具内部都通过 `CronService` 上的 CRUD 方法操作，不直接读写 jobs.json。统一注册到 `ToolRegistry`，schema 按现有 tool 的样式（`tool_parameters_schema`）。不新建工具分类目录。

### 4. Prompt builder 注入

Step 1 侦察确认：cron prompt 的**真正构造点**不在 `CronService._execute_job`（它只调 `on_job` 回调），而在 `nanobot/cli/commands.py:on_cron_job` 里的 `reminder_note`。那才是注入位置。

`on_cron_job` 构造 `reminder_note` 时，读 `job.commitments`（active 状态），把它们的 `text` 以固定模板拼进去：

```
[Scheduled Task] Timer finished.

Task '<name>' has been triggered.
Scheduled instruction: <payload.message>

## Active rules to follow
The following rules MUST be respected in this run. If any cannot be satisfied, say so explicitly in the output rather than silently violating.

- <commitments[0].text>
- <commitments[1].text>
- ...
```

`payload.message` 保留作为 job 的任务描述；`commitments` 是叠加的规则层。随着 β 阶段"毕业机制"的引入，稳定的 commitments 可以合并进 `payload.message`——这条路径是预留的，α 不做自动合并。

### 5. Simulate 机制（轻量，不重开 effector 架构）

最小机制：

- 一个 `_simulate_recorder: ContextVar[SimulateRecorder | None]` 放在 `nanobot/simulate/`（新目录）。
- `SimulateRecorder`：一个内存列表容器，`record(outbound: OutboundMessage)`。
- **唯一改动点**：`MessageTool.execute` 在真正 `_send_callback(msg)` 之前检查 contextvar——有 recorder 就 `recorder.record(msg)` 并返回 `"ok (simulated)"`；否则走原路径。
- `bus.publish_outbound` / channel manager / 重试 / stream 一行不改——**没必要动**，因为 job 执行阶段 LLM 真正发送走的是 MessageTool，bus / channel 是 shell 层的事。

simulate_job_run 实现：

```python
async def simulate_job_run(job_id: str) -> dict:
    recorder = SimulateRecorder()
    token = _simulate_recorder.set(recorder)
    try:
        # 和真 cron 一样的执行链路（复用 process_direct + 新 prompt builder）
        await agent.process_direct(build_cron_prompt(job_id), ...)
    finally:
        _simulate_recorder.reset(token)
    outputs = [r.content for r in recorder.captured]
    verdicts = await verify_all(commitments=active_commitments(job_id), outputs=outputs)
    return {"outputs": outputs, "verdicts": verdicts}
```

**安全边界**：simulate 只拦截发送，其他副作用（web_fetch、file write、shell exec）**会真发生**。α 假设现有 cron job 的执行体是 read-only-ish（抓新闻、读文件、组装文本），这一条在 Non-goals 里明说。超出这个假设的 job 暂时不适合 simulate。

### 6. Verification helper

纯函数式 LLM 调用：

```python
async def verify(evidence: str, claim: str, *, provider: LLMProvider) -> Verdict:
    """独立 LLM 调用，判定 evidence 是否满足 claim。
    无 session、无 tools、无 system prompt 注入，保证判断干净。"""
```

Verdict：

```python
@dataclass
class Verdict:
    passed: bool
    detail: str | None  # 失败时说明哪里不合规
```

- 有输出时：`evidence = briefing_text`，`claim = f"此输出必须同时满足以下承诺：{commitment_list}"`
- 沉默时：`evidence = fetched_content`，`claim = f"按以下承诺，这批输入不应触发通知：{commitment_list}"`

一个函数两种用法，调用者组装 (evidence, claim)。

### 7. Trace

新增 kind：

- `commitment.created` / `commitment.revoked` — 工具调用发出
- `job.simulated` — simulate_job_run 启动
- `verification.completed` — 一次 verify 调用结束（带 verdict）

顶层字段（`ts`/`run_id`/`trace_id`/`kind`/`payload`）契约不变，沿用 Phase 0。

## Non-goals

- **不**在真 cron 上 pre-delivery 自动拦截 + 阻断投递（留给 β）。
- **不** mock 时间；simulate 以"现在"为基准跑。需要时间敏感场景的 job 暂不适合 α 验证（在产物里标为 known limitation）。
- **不**做事件触发（"盯消息" 按 cron 轮询方式解决，与 briefing 同机制）。
- **不**做自动多轮迭代；LLM 需要自己决定何时再次 simulate。
- **不**做"毕业机制"（稳定 commitment 自动合并进 `payload.message` 并豁免后续验证）。数据模型里预留 `status` 字段支持该路径，但自动合并 / 合并时机 / 人工确认等策略留给 β——α 先跑一段时间看实际形态再设计。
- **不**迁移已有 memory.md 里的旧规则；一次性手动迁移，之后统一走 commitments。
- **不**改 ChannelManager / bus.outbound / channel 内部。
- **不**加新依赖。
- **不**做 dedupe / retry / cross-process / 分布式。
- **不**引入 intent 类型层级（原 Phase 1 Step 2 的 SendMessageIntent / NoReplyChosen 等在新方向下无消费者，已回退）。

## Steps

每步都是一个可独立评审、可回滚的单元。

1. **侦察（read-only）**：**已完成**。关键结论：
   - Cron prompt 的真构造点是 `nanobot/cli/commands.py:on_cron_job` 的 `reminder_note`，**不**是 `CronService._execute_job`。
   - Simulate 唯一陷阱点是 `nanobot/agent/tools/message.py:106` 的 `self._send_callback(msg)`。
   - jobs.json 已有完整的 `_load_store` / `_save_store` + mtime-cache pattern，commitments 字段随之读写即可。
   - ToolRegistry 按 `self.tools.register(Instance)` 声明式注册，commitment 工具挂在 `if self.cron_service` 块内。
   - Simulate 和真 cron 用 `process_direct(prompt, session_key=...)` 同一入口，simulate 用 `session_key="simulate:<job_id>"` 隔离历史。

2. **Commitment 数据模型 + CronJob 字段扩展**：
   - 在 `nanobot/cron/types.py` 加 `Commitment` / `CommitmentVerificationRecord` dataclass。
   - 给 `CronJob` 加 `commitments: list[Commitment] = field(default_factory=list)`。
   - 扩展 `CronService._load_store` / `_save_store`：加载老数据时默认 `[]`；保存时 camelCase 化。
   - 在 `CronService` 加 CRUD API：`add_commitment` / `revoke_commitment` / `list_commitments` / `append_verification`，内部统一调 `_save_store`。
   - 单测：序列化往返、老 jobs.json 兼容加载、CRUD 语义。

3. **LLM 工具 3 个**：
   - 在 `nanobot/agent/tools/commitment.py` 新增 `CreateCommitmentTool` / `RevokeCommitmentTool` / `ListCommitmentsTool`。
   - 内部调 `CronService` 的对应 CRUD 方法，不直接读写 jobs.json。
   - 在 `AgentLoop._register_default_tools` 的 `if self.cron_service` 块内注册。
   - 每个工具发对应 trace kind（`commitment.created` / `commitment.revoked` / `commitment.listed`）。
   - 单测每个工具返回值、store 副作用、trace 发射。

4. **Prompt builder 注入 commitments**：
   - 在 `_execute_job` 构造 prompt 处读 active commitments 拼进去。
   - 加 snapshot 测试锁模板。

5. **Simulate 机制**：
   - `nanobot/simulate/`（新目录）：`recorder.py`（SimulateRecorder + contextvar）。
   - `MessageTool.execute` 的最小 patch：真正 `_send_callback` 前检查 contextvar。
   - 单测拦截行为 + contextvar 清理保证。

6. **Verification helper**：
   - `nanobot/verification/`（新目录）：`verify.py`。
   - 纯 LLM 调用，提示工程 + JSON 解析。
   - 单测（mock provider）覆盖 pass / fail / malformed response。

7. **simulate_job_run 工具**：
   - 组合 Step 4 + 5 + 6。
   - 注册到 ToolRegistry，schema。
   - trace 发 `job.simulated` / `verification.completed`。
   - 单测端到端（mock provider）。

8. **北极星 test**：
   - CLI 级集成测试：mock provider 按顺序返回 `create_commitment 调用` / 文本含神经科学的 briefing / 文本不含神经科学的 briefing 的内容，断言 verdict 正确切换。
   - 断言 commitment store 的持久化、trace 事件序列。

9. **文档同步**：
   - `STATUS.md` 切 Phase 2（β：enforced verification + 自动迭代）。
   - `ROADMAP.md` 根据 α 实际落地更新 Phase 2 scope。

## Acceptance checks

- 新建一个 commitment（通过 `add_commitment(job_id, ...)`）后，下一次真 cron 运行的 `reminder_note` 里有这一条承诺（snapshot test）。
- `simulate_job_run(job_id)` 产出 `(outputs, verdicts)`；verdicts 对 active commitments 逐条返回 pass/fail。
- MessageTool 在 simulate 模式下**不**触达真 channel（计数真 send 为 0，recorder 有捕获）。
- 整个链路 trace_id 贯穿：`commitment.created` → `job.simulated` → planner / tool / memory / send path 拦截 → `verification.completed`。
- jobs.json 写回后重新加载，commitments 字段及 verification_history 完整保留（序列化往返测试）。
- 加载不含 `commitments` 字段的老 jobs.json 时不报错，job.commitments 自动为 `[]`。
- 全量测试 + Phase 0 已有场景无回归。

## Risks & mitigation

- **simulate 不够纯**：除发送外的副作用（web_fetch、file write）会真发生。如果 job 执行过程中写了磁盘 / 调了外部 API，simulate 次数多了会产生真实副作用积累。**Mitigation**：α 明确说明此假设；在 simulate 工具 docstring 和 tool description 里警告 LLM 不要短时间连续 simulate；trace 上 `job.simulated` 可被监测频次。
- **verification 的 LLM 判决不稳**：同一条 (evidence, claim) 两次调用可能 verdict 不同。**Mitigation**：低 temperature（0 或 0.1）；prompt 强约束 JSON 格式；verdict 只作为 LLM 自省信号，不做硬 gate（gate 是 β 的事）。
- **commitment 文本歧义**：用户说得模糊（"温柔一点"）会产生难判决的 commitment。**Mitigation**：承认此限制；LLM 创建时可提示 "承诺要可验证，避免纯主观"；但不强制——α 以能工作为先，模糊承诺 verify 失败就是失败，暴露出来比隐藏好。
- **contextvar 跨 task 漏拦**：simulate 期间 agent 内部若通过 `asyncio.create_task(...)` 派生新 task，contextvar 是**会**被拷贝的（Python 行为），但对 task 外的 callback / thread 则不拷贝。**Mitigation**：Step 5 的单测覆盖常见异步路径；发现遗漏再补（AGENTS.md 鼓励已知风险显式列出）。
- **老 memory.md 规则与新 commitments 并存**：一段时间内两边都有"规则"。**Mitigation**：接受这个过渡状态，不在 α 做自动迁移。α 完成后可以用一轮 LLM 手动迁移（工具都已具备）。

## Docs to update（完成时）

- `STATUS.md`：标记 Phase 1 完成，焦点切到 Phase 2（β）。
- `ROADMAP.md`：Phase 2 scope 基于 α 实际产出的类型和工具再细化。
- `PRINCIPLES.md`：如落地过程中发现某条原则需要调整（而不是绕过），同步修改。

## Exit criteria

- 用户在 CLI 说"以后新闻不要神经科学"，系统不再落到 memory.md，而是在对应 CronJob 上追加一条 commitment 并能在同一 turn 内 simulate 得到 verdict。
- `simulate_job_run` 可被 LLM 自发重复调用验证修改，每次都有 trace 可追。
- 一次"改承诺 → simulate 失败 → 改表述 → simulate 通过"的自循环能在集成测试里跑通。
- Commitments 随 jobs.json 持久化，进程重启后仍可读；verification_history 被正确截断到上限。
- 对称状态保证：同一用户意图，无论一次说完还是分两次说，最终 jobs.json 里这个 job 的数据结构一致。
