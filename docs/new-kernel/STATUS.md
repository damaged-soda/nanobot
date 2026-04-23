# 当前状态

## 当前阶段

Phase 0 **已完成**。下一步是 Phase 1（Outbound effect isolation），PLAN 尚未撰写。

## Phase 0 成果

Trace scaffold 已落地，在六类边界发射事件：

- `channel.received`（CLI 入口，`cli/commands.py` + `channels/base.py` 的 `_handle_message` 是统一口，其它 channel 暂不逐个插）
- `planner.entered` / `planner.exited`（`agent/loop.py:_run_agent_loop`）
- `tool.called` / `tool.returned`（`agent/runner.py:_run_tool`）
- `channel.sent`（非 CLI 走 `channels/manager.py:_send_once`；CLI 走 `cli/commands.py:_consume_outbound`）
- `memory.read` / `memory.write`（`agent/memory.py:MemoryStore`）
- `cron.fired`（`cron/service.py:_execute_job`）

trace_id 传递机制：
- 同 task 内：`contextvars`（planner / tool / memory 链）
- 跨 task（bus 队列）：作为数据字段存在 `InboundMessage.trace_id` / `OutboundMessage.trace_id`，`MessageBus.publish_inbound/outbound` 在 producer 未显式设置时自动从 contextvar 捕获
- cron 路径：`_execute_job` 起点生成 trace_id，通过 contextvar 贯通到 `process_direct` → `_run_agent_loop`

验收：
- CLI 端到端 integration test：一条消息产生 `channel.received` → `planner.entered` → `planner.exited` → `channel.sent` 共享同一 trace_id
- Cron 路径 integration test：`cron.fired` → `planner.entered` / `planner.exited` 共享 trace_id
- 15 个 trace 模块单测 + 2 个 integration test 全部通过

## 与原 PLAN 的偏离

- **Sink 默认**：原 PLAN 写 "默认 stdout JSONL"。实际实现为 **env 门控，默认无 sink**：
  - `NANOBOT_TRACE=1` → JSONL 写 stderr（observability 惯例流，不污染 CLI 的 stdout Markdown 渲染）
  - `NANOBOT_TRACE_FILE=path` → JSONL 追加到文件
  - 两个都不设 → 零 sink，`emit` 近似 no-op

## 已知 gap（后续 Phase 视情况补齐）

- **Streaming 出口**：`send_delta` 路径（telegram / feishu / matrix 流式）未发射 `channel.sent`，只有非流式 `send` 路径覆盖。
- **Slash command / Heartbeat / Subagent → system channel**：这些 OutboundMessage producer 当前不在 trace context 下运行，bus auto-capture 拿不到 trace_id，链路断开。Phase 0 明确选择不覆盖。
- **Dream 内部**：`agent.dream.run()` 被 cron 触发后继承 trace_id（memory 读写会带），但 Dream 自己的 AgentRunner 执行不发 `planner.*` 事件。

## 冻结区域

Phase 0 期间未动（仍冻结到下一步明确放开前）：

- planner / agent loop 的决策逻辑
- channel 内部 `send()` 实现
- provider 层
- memory 系统语义
- 上游 sync 策略

## 最后更新

2026-04-22
