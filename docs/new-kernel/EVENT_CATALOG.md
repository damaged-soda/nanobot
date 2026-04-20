# 事件目录

本文件维护 event / intent / effect 的集中目录。新增或改变事件语义时必须更新这里。

## Ingress events

### `UserMessageReceived`

含义：channel 收到用户消息。

生产者：channel adapter。

消费者：planner、policy checker、logger。

仿真语义：可以由测试夹具注入。

### `CronTicked`

含义：某个 job 的调度时间到达。

生产者：cron producer。

消费者：job dispatcher、planner、collector、summarizer。

仿真语义：应支持 mock clock。

### `ObservationCollected`

含义：collector 从外部来源采集到 observation。

生产者：collector。

消费者：observation store、summarizer、dedupe。

## Decision events

### `ReplyPlanned`

含义：planner 决定需要回复。

### `NoReplyChosen`

含义：planner 显式决定不回复。注意：不回复不是“什么都没发生”，而是一条可审计决策。

### `SummaryRequested`

含义：某个窗口需要生成汇总。

## Intent events

### `SendMessageIntent`

含义：系统准备发送消息。真实发送必须由 sender effector 消费该 intent 后执行。

### `ToolCallIntent`

含义：系统准备调用工具。

### `WriteArtifactIntent`

含义：系统准备写入 artifact 或 workspace 文件。

### `ScheduleJobIntent`

含义：系统准备创建或更新 job。

## Effect events

### `MessageSent`

含义：真实发送已经完成。

### `MessageDeliveryFailed`

含义：发送失败。

### `ToolExecuted`

含义：工具调用已执行。

### `ArtifactWritten`

含义：artifact 已写入。

## Verification / publish events

### `SimulationRunStarted`

含义：一次仿真开始。

### `VerificationPassed`

含义：某个 verification check 通过。

### `VerificationFailed`

含义：某个 verification check 失败。

### `CandidatePatchReady`

含义：候选 patch 已生成。

### `PatchHunkPruned`

含义：cleanup verifier 删除了一个不必要 hunk。

### `PublishApproved`

含义：候选改动允许发布。

### `PublishRejected`

含义：候选改动禁止发布。

## 每个事件类型必须定义

新增事件时至少说明：Meaning、Producer、Consumers、Required fields、Idempotency expectations、Simulation semantics。
