# PLAN-002：把 cron 改造成事件源

## Goal

让 cron 不再“到点直接给 agent 一段 prompt”，而是产生显式事件，例如 `CronTicked`、`CollectWindowOpened`、`SummaryWindowOpened`。

## Background

当前 cron-like 任务容易把复杂长期行为压成一句 prompt。对于“每天 9 点提醒”或“24 小时采集 + 每天汇总”这类任务，更合理的模型是：cron 只负责产生时间事件，后续消费者根据 job spec 和资源状态处理。

## Scope

- 定义最小 `CronTicked` 事件。
- 让 job-specific instructions 归属到 `JobSpec`。
- 让 cron producer 和 planner consumer 分离。
- 增加 mock clock / simulated tick 的验证路径。

## Non-goals

- 完整替换所有 cron 功能。
- 完整分布式调度。
- 完整长期采集系统。

## Architecture impact

这一步把 cron 从“agent prompt trigger”降级为 ingress producer。

## Steps

1. 定义 `CronTicked` 事件语义。
2. 定义最小 `JobSpec` 字段。
3. 让 cron 到点时产生事件，而不是直接调用 agent prompt。
4. 通过 adapter 维持旧 job 的兼容执行。
5. 增加 simulated tick 验证。
6. 更新事件和资源文档。

## Acceptance checks

- mock 到 08:59 不会产生发送 intent。
- mock 到 09:00 产生恰好一个发送 intent。
- replay 同一 tick 不重复发送。
- job-specific 约束不写入 global memory。

## Docs to update

- `../EVENT_CATALOG.md`
- `../RESOURCE_OWNERSHIP.md`
- `../NORTH_STAR_SCENARIOS.md`
- `../VERIFICATION_MODEL.md`
