# 北极星场景

这些场景用于把抽象架构拉回具体行为。阶段性改造应优先服务这些场景。

## Scenario 1：用户消息 -> 回复或不回复

### Goal

用户消息进入系统后，planner 必须显式做出回复或不回复的决策。

### Trigger event

- `UserMessageReceived`

### Expected chain

```text
UserMessageReceived
  -> planner consumer
    -> ReplyPlanned / NoReplyChosen
      -> SendMessageIntent? / no outbound intent
```

### Verification

- 不回复时必须产生可观察的 `NoReplyChosen`。
- 回复时必须产生 `SendMessageIntent`。
- simulate mode 不调用真实 channel。
- live mode 由 sender effector 真实发送。

### Failure modes

- planner 没有输出但也没有 `NoReplyChosen`。
- planner 直接调用 channel 发送。
- simulate mode 仍产生真实副作用。

## Scenario 2：每天 9 点提醒

### Goal

每天东京时间 09:00 给用户发送提醒，09:00 前不发送，同一 tick replay 不重复发送。

### Trigger event

- `CronTicked(job_id)`

### Key resources

- `JobSpec`
- `UserProfile`
- outbox view

### Expected chain

```text
CronTicked
  -> job dispatcher
    -> planner / reminder consumer
      -> SendMessageIntent
        -> sender effector
          -> MessageSent
```

### Verification

- mock 08:59：不产生发送 intent。
- mock 09:00：产生恰好一个发送 intent。
- replay 同一 tick：不重复发送。
- job-specific instruction 位于 `JobSpec`，而不是 global memory。

### Failure modes

- 提醒规则写进 global memory。
- 到 09:00 生成多个发送 intent。
- replay 导致重复发送。

## Scenario 3：24 小时持续采集 + 每日汇总

### Goal

系统持续收集某来源的信息，每天定时汇总给用户。

### Flow A：持续采集

```text
CollectTick
  -> collector
    -> ObservationCollected
      -> ObservationStore
```

### Flow B：每日汇总

```text
SummaryTick
  -> summarizer
    -> SendMessageIntent
      -> sender effector
```

### Verification

- 采集和汇总是两条独立流。
- 汇总从 `ObservationStore` 读取过去窗口数据。
- simulate mode 只验证 would-be outbound，不真实发送。
- collector failure 不应直接触发用户消息，除非有明确 alert policy。

### Failure modes

- 把持续采集写成单个 cron prompt。
- summarizer 依赖聊天历史而不是 observation store。
- 采集工具直接产生用户消息。

## Scenario 4：代码修改 + cleanup verifier

### Goal

agent 修改代码后，最终保留的 diff 必须既满足目标行为，又尽量删除过期试探性改动。

### Trigger event

- `CandidatePatchReady`

### Expected chain

```text
CandidatePatchReady
  -> acceptance checks
  -> cleanup verifier
    -> PatchHunkPruned / PatchHunkRetained
      -> PublishApproved / PublishRejected
```

### Verification

- candidate patch 通过目标检查。
- 对每个 hunk 尝试回退。
- 回退后仍通过的 hunk 被删除。
- 最终 patch 再次通过 acceptance 和 regression checks。

### Failure modes

- 测试过了但保留无关修改。
- cleanup verifier 只看文本，不重跑检查。
- agent 为了过验证而绕过测试或关闭检查。
