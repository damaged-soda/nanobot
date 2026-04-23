# nanobot runtime 演进文档

这个目录是 nanobot fork 的 runtime 演进控制面。不替代根目录 `README.md`，也不替代 `docs/` 下的用户文档。

## 一句话定位

**保留 nanobot shell，把 runtime 演进为可观测、可仿真、可自验证的形态。**

- `shell`：用户可见的产品外壳，包括 CLI、gateway、channel 适配、provider、workspace、tool、skill。这部分继续跟随上游，不做重写。
- `runtime`：真正决定系统如何运行的那一层，包括观测、仿真、承诺结构、验证循环。这部分是 fork 的重做对象。

## 为什么需要这个 fork

当前 nanobot 的运行模型里，用户交付的**持久承诺**（"每天 9 点发 briefing"、"以后不要神经科学的新闻"、"盯住 X 类型的空投"）和**短期会话记忆**混在一起，都塞在 memory 相关 md 里。LLM 不区分两者，经常把"我要改变未来行为"的指令当"记笔记"处理，结果：

- 用户说"以后新闻不要神经科学"，nanobot 写进 memory.md，第二天 briefing 照旧出现——**规则没进到真执行时的 prompt**。
- LLM 做完修改后没有任何手段在当前 turn 内验证"下次那个定时任务真跑时会不会按我这次改的来"，反馈要等到真 cron 跑完。

这不是打补丁能解决的问题，需要从两个结构上的缺口下手：

1. **承诺是一等资源**，不是 memory 里的一行散文。有稳定 id、状态、审计、归属到具体 job。
2. **simulate 是一级能力**，LLM 可以在自己这一轮里调用，真实跑一遍执行链路（但真实副作用被拦截），用一次干净的 LLM 调用判决"这次输出是否遵循了承诺"。

所以选择 fork，逐步把 runtime kernel 推到这个形态。

## 核心概念

- **Commitment**：用户（或 LLM 推断）交付的持久规则，如 "briefing 不要神经科学"。内容是 prose，**外壳结构化**（id / status / verification_history / ...），作为所属 `CronJob` 的一个字段存在，随 `jobs.json` 持久化——保证同一意图不会因为"一次说完"还是"分批说"落成不同形态。
- **Simulate**：一次完整的 job 执行复刻，真实发送被拦截成 recorder 捕获，其他路径照常跑。LLM 可在 turn 内调用，不需要等真 cron。
- **Verification**：一次独立 LLM 调用（无 session、无工具），判决 `(evidence, claim)` 是否一致。给 simulate 提供自评能力，也能在真 cron 投递后事后复盘。

## 执行策略：先观测，再验证

Phase 0 先把系统行为变可观测（trace 覆盖六类边界，JSONL 格式，稳定字段），这是后续一切改造的安全网。

Phase 1 在可观测基础上，把承诺做成资源、给 simulate 铺第一条路。行为改变仍然最小化——只在 MessageTool 加一个 contextvar 拦截点；其他路径零改动。

Phase 0 的 trace 格式同时是未来 event log / replay 的载体，投入不会浪费。

## 阶段概览

- **Phase 0（已完成）**：observability scaffold。trace 格式、emit API、六类边界观测全部到位。
- **Phase 1（当前）**：承诺资源化 + Simulate。Commitment 作为 CronJob 字段 + LLM 工具 + prompt 注入 + simulate 机制 + verification helper。
- **Phase 2（待启动）**：Enforcement + 自动迭代。真 cron 自动走 pre-delivery verify；LLM 习惯性 simulate；失败自动迭代。
- **Later（frozen）**：Context compiler 完整版、mock time、更多资源化、分布式等。等 Phase 1 / 2 走完再评估。

## 阅读顺序

1. [`PRINCIPLES.md`](./PRINCIPLES.md) — 架构原则，后续所有改动的判据。
2. [`STATUS.md`](./STATUS.md) — 当前阶段、焦点、已知 gap。
3. [`ROADMAP.md`](./ROADMAP.md) — 阶段路线。
4. [`plans/PLAN-phase1-commitments.md`](./plans/PLAN-phase1-commitments.md) — 当前阶段详细计划。

Agent 工作规则（Codex / Claude Code 共用）放在仓库根的 [`AGENTS.md`](../../AGENTS.md)，自动加载。
