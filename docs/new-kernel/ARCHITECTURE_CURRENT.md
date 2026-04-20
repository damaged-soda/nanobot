# 当前架构

## Summary

当前系统仍然主要是 loop-centric：用户消息、cron、heartbeat 等入口最终倾向于汇入一次 agent turn 或 agent loop。

这个模型很容易上手，也符合 nanobot 原始项目的轻量定位，但它不天然支持事件回放、副作用隔离、长期任务分流、TDAD 验证和 cleanup verifier。

## Main flows

### 用户消息入口

channel 接收到用户消息后，通常会把它转成一次 agent 处理请求。

### AgentLoop / Planner

旧 `AgentLoop` 负责大量职责：消息处理、tool use、session 读写、memory/context 组装、输出生成，以及某些路径下的副作用触发。

### Tool execution

工具调用往往与 agent turn 绑定。工具结果回到同一个处理链路中。

### Outbound sending

外发消息可能从 agent 输出路径直接进入 channel 发送逻辑。这个路径需要被 effect isolation 改造。

### Cron invocation

cron 当前更接近“按时间触发一段 message 或 prompt”，而不是“产生一条 typed event”。

### Memory / context composition

context 常常在每次 run 时动态拼装，memory 可能被当成过宽的存储面。

## Strengths we want to preserve

- shell 简洁。
- 本地开发容易。
- channel-oriented 的产品形态清晰。
- provider / tool / workspace 这些外壳能力有复用价值。
- 用户体验接近 nanobot，不需要变成企业级 workflow 平台。

## Structural limitations

- `turn` 被放得太中心。
- planner 与副作用边界不够硬。
- job-specific 约束容易落到 global memory。
- cron 缺少资源化 job spec 和可仿真 tick。
- 无法天然 replay 未来执行上下文。
- cleanup verifier 没有发布边界。

## Areas treated as legacy

在新内核成型前，以下区域视为 legacy-compatible，而不是未来核心：旧 `AgentLoop` 主路径、旧 direct-send path、旧 cron prompt payload 模型、旧 context 动态拼装路径。

## Migration stance

不一次性推翻旧系统。优先通过 adapter / shim 建立新边界，然后逐步把旧路径降级为 consumer 或兼容执行器。
