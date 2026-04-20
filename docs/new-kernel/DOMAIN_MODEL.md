# 领域模型

## Core entities

### Event

事件是系统中已经发生的事实。事件应尽量 append-only，不应被随意修改。命名建议使用过去式，例如 `UserMessageReceived`、`CronTicked`、`ObservationCollected`、`MessageSent`。

### Intent

意图是系统准备执行的动作。尤其是可能产生外部副作用或持久状态变化的动作，都必须先表示为 intent。命名建议以 `Intent` 结尾，例如 `SendMessageIntent`、`ToolCallIntent`、`WriteArtifactIntent`、`ScheduleJobIntent`。

### Effect

effect 是真实发生的外部结果或持久化结果。例如 `MessageSent`、`ToolExecuted`、`ArtifactWritten`、`ExternalCallFailed`。

### Resource

resource 是长期存在、有 owner、可被引用的状态对象。例如 `UserProfile`、`JobSpec`、`ProjectRules`、`ObservationStore`、`KnowledgeBase`、`WorkingPatch`。

### View

view 是从 event log 或 resource 派生出的查询视图，不是 authoritative source。

### Run

run 表示同一逻辑在某种模式下的一次执行。常见 run mode：`live`、`simulate`、`replay`、`compile`。

## Invariants

- Event 表示事实。
- Intent 表示计划。
- Effect 表示实际发生。
- Resource 拥有持久约束。
- View 只是派生查询结果。
- Memory 不是万能 resource。

## Naming rules

- 事实类事件用过去式：`UserMessageReceived`。
- 意图类事件用 `Intent` 后缀：`SendMessageIntent`。
- 资源用名词：`JobSpec`、`UserProfile`。
- View 用查询视角命名：`PendingOutboxView`。
