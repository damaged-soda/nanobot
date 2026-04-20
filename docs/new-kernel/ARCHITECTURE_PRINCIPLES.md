# 架构原则

## 1. Event 是一级抽象

`turn`、cron tick、用户消息、采集结果、发送意图都应被建模为事件流中的对象。

## 2. Planner 不直接产生副作用

planner、summarizer、memory reducer 等消费者只能产出 event 或 intent。

## 3. Intent 必须先于 Effect

任何外部副作用都必须有显式前置 intent。不能出现“顺手就发了”“顺手就写了”。

## 4. 每类持久约束只有一个 owner

job-specific 规则归 `JobSpec`。用户长期偏好归 `UserProfile`。项目级规则归 `ProjectRules`。memory 不得充当万能存储。

## 5. Simulation 和 Replay 是一级能力

同一条事件链应能在 live、simulate、replay 中运行。仿真不是 debug hack，而是验证基础设施。

## 6. Build -> Verify -> Publish

任何可发布改动都必须先构建候选，再验证目标行为，再发布。

## 7. Cleanup verifier 是发布闸门

cleanup verifier 不是美化工具，而是防止过期试探性修改进入最终 diff 的核心机制。

## 8. 先保证语义正确，再考虑规模

第一版优先单进程、简单、可观察。不要过早引入分布式消息系统或复杂编排平台。

## 9. 新内核不应复制旧 loop 的隐式耦合

不要把旧 `AgentLoop` 换个名字搬进新 runtime。旧 loop 应逐步降级为 consumer 或兼容执行器。

## 10. 文档是架构的一部分

新增 event、resource、verification semantics 时必须更新相应文档。否则代码即使能跑，也视为未完成。
