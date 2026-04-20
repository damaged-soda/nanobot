# 资源归属

本文件定义每类持久信息应该归属到哪里，防止 source-of-truth 错位。

## `UserProfile`

### Owns

- 用户长期偏好。
- 稳定用户事实。
- 联系方式或身份偏好。

### Does not own

- 某个 job 的专属注意事项。
- 某次 run 的临时约束。
- 项目级代码规则。

## `JobSpec`

### Owns

- schedule / cron expression。
- job-specific instructions。
- job-specific verification profile。
- job 的状态、启用/禁用、目标 channel。

### Does not own

- 全局用户偏好。
- unrelated project rules。
- 长期知识库事实。

## `ProjectRules`

### Owns

- 仓库级约束。
- coding style。
- done-when 定义。
- 发布流程规则。

## `ObservationStore`

### Owns

- 原始 observation。
- 规范化 observation。
- 采集来源、时间、去重 key。

### Does not own

- 最终用户汇报内容。
- memory summary。

## `KnowledgeBase`

### Owns

- 可复用、提炼过的知识。
- 跨 job 可共享的事实或模式。

### Does not replace

- `JobSpec`
- `ProjectRules`
- `UserProfile`

## `WorkingPatch`

### Owns

- 发布前候选修改。
- scratch workspace 状态。
- cleanup verifier 处理对象。

### Rules

- 必须可丢弃。
- 必须可 diff。
- 必须经过 verification / cleanup 后才能 publish。

## Ownership rule

如果一条信息会影响未来自动执行，那么必须问：未来哪个 resource 拥有它？没有 owner 的信息不得被写入长期状态。
