# nanobot 新内核改造文档集

这是一个基于 nanobot 的改造型 fork 文档骨架。目标不是继续在旧 `AgentLoop` 上堆功能，而是保留 nanobot 易用、轻量、channel-friendly 的产品外壳，同时逐步演进出一个 **event-sourced、effect-isolated、可仿真、可验证** 的新 runtime kernel。

本目录只描述新内核的中长期演进路线和工程治理规则，不替代根目录 `README.md`，也不替代 `docs/` 下已有的用户文档、SDK 文档或 channel 文档。

## 项目定位

一句话：**保留 nanobot shell，重做 runtime kernel。**

`shell` 指用户可见的产品外壳：CLI、gateway、channel 适配、workspace 习惯、provider/tool 接入等。

`kernel` 指真正决定系统如何运行的内核：事件日志、消费者调度、intent/outbox/effect、资源所有权、context compiler、simulation/replay、TDAD、cleanup verifier 等。

## 为什么需要这个 fork

当前 nanobot 很适合上手，但默认运行模型仍然偏 `turn-centric` 和 `loop-centric`：用户消息、cron、heartbeat 等入口容易被压成“把一段 prompt 交给 agent loop”。

这会带来几个结构性问题：

- **source-of-truth 错位**：job 专属约束可能被写进 global memory，而不是 job 自己的 spec。
- **副作用与决策耦合**：planner 在决定行为时可能直接发消息、写文件或调用外部系统，导致仿真和回放困难。
- **长期任务被压缩成单次 turn**：例如“24 小时持续采集 + 每日汇总”本应是两个流，却容易被写成一个 cron prompt。
- **过期修改残留**：agent 先试探性修改 A，再靠 B 修好问题，但 A 仍留在最终 diff 里。
- **未来执行上下文不可重放**：很难证明“这次写入的约束，在未来真正执行时是否可见”。

## 我们要构建什么

```text
nanobot shell
  -> event-sourced runtime kernel
    -> assurance layer
```

核心思想：

- `turn` 只是 event 的一种，不再是系统中心。
- planner 只能产出 intent，不能直接产生副作用。
- 每个 effect 都必须有一个前置 intent。
- 持久约束必须归属到明确的 resource，而不是随意写进 memory。
- simulation/replay 是一级能力，不是调试附件。
- TDAD 和 cleanup verifier 是 publish gate，而不是 prompt 里的自我反思。

## 第一阶段重点

第一阶段只做 outbound behavior 的 effect isolation：

- 把 outbound message 从 planner 中剥离出来。
- 引入 `SendMessageIntent` / `NoReplyChosen` / outbox-like boundary。
- 让 simulation mode 能验证“该发、不该发、正好发一次”，而不真的调用外部 channel。

## 建议阅读顺序

1. `AGENTS.md`：Codex 工作规则。
2. `STATUS.md`：当前阶段和当前焦点。
3. `ARCHITECTURE_PRINCIPLES.md`：架构原则。
4. `ARCHITECTURE_TARGET.md`：目标架构。
5. `NORTH_STAR_SCENARIOS.md`：北极星场景。
6. `ROADMAP.md`：阶段性路线。
7. `DOMAIN_MODEL.md`、`EVENT_CATALOG.md`、`RESOURCE_OWNERSHIP.md`：语义模型。
8. `VERIFICATION_MODEL.md`：验证和发布模型。
