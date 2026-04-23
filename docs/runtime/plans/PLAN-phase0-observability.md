# PLAN Phase 0：Observability scaffold

## Goal

让当前系统在 trace 里完全可见，为后续重构提供安全网。同时确立的 trace 事件结构，之后会演进成 event log。

## Background

内核重构对外行为不变，没有观测就没有安全网：说不清改动前后哪里变了、哪里没变。Phase 0 不改行为，只加观测，是整个路线的地基。

北极星场景：在 CLI 发一条用户消息，产出一份完整可读的 trace，能看到 channel 接收 → planner → tool → 发送的全链路。

## Scope

### 数据结构

trace 事件是一条 JSON：

```json
{"ts": "<iso8601>", "run_id": "<uuid>", "trace_id": "<uuid>", "kind": "<dotted.name>", "payload": {...}}
```

- `ts`：事件发生时间，ISO 8601 字符串。
- `run_id`：一次 runtime 生命周期（进程启动到退出）。
- `trace_id`：一条用户消息 / 一次 cron tick 触发的因果链。
- `kind`：点分命名空间，例如 `channel.received`、`planner.entered`、`tool.called`。
- `payload`：每种 kind 自己的 schema，初期宽松。

### emit API

- `trace.emit(kind: str, **payload)`：发射一条事件。
- 内部使用 `contextvars.ContextVar` 存 `run_id` 和 `trace_id`。
- 提供 `trace.context(trace_id=...)` 上下文管理器，进入时绑定 trace_id，退出时清理。
- 进程启动时初始化 `run_id`。

### Sinks

- 默认：**无 sink**。`emit` 仍能安全调用，开销接近 no-op。
- `NANOBOT_TRACE=1` → JSONL 写 **stderr**（observability 惯例流，不污染 CLI 的 stdout 渲染；便于 `2>trace.jsonl | jq` 之类的 pipeline）。
- `NANOBOT_TRACE_FILE=path` → JSONL 追加到文件。
- 测试用：null sink。

（原文本写的是 "默认 stdout JSONL"；落地时改为 env 门控 stderr，避免 CLI 交互模式被 JSONL 冲掉 rich 渲染。）

初版不做异步写入、不做缓冲、不做压缩。一行一写，简单优先。

### 插桩点（六类）

| 类别 | 事件 kind | 载体位置（待 Step 1 侦察确认） |
|---|---|---|
| channel 入口 | `channel.received` | `nanobot/channels/*` 接收用户消息入口 |
| planner 入出 | `planner.entered` / `planner.exited` | `nanobot/agent/loop.py` |
| tool 调用前后 | `tool.called` / `tool.returned` | `nanobot/agent/tools/` 调用点 |
| channel 出口 | `channel.sent` | 所有 `channel.send(...)` 调用点（Phase 1 的改造目标，必须先可见） |
| memory 读写 | `memory.read` / `memory.write` | `nanobot/agent/memory.py` |
| cron 触发 | `cron.fired` | `nanobot/cron/` 调度点 |

初版 payload 字段保持最小：用户消息取 channel、user_id、content 长度、trace_id；planner 取模型名、tool 列表大小；tool 取 name、参数摘要；send 取 channel、target、content 长度；memory 取 key、bytes；cron 取 job_id、schedule。

**不记录完整用户消息正文或完整 LLM 输出**，避免隐私和噪声。长度和摘要够了。

### 查看方式

初版不做 UI：`tail -f` trace 文件 + `jq` 过滤。例如：

```bash
jq 'select(.kind | startswith("channel"))' trace.jsonl
```

## Non-goals

- 不做采样、分布式追踪、span / trace 树结构。
- 不做 TUI、dashboard、metric、告警。
- 不改 planner、channel 内部、provider、memory 的行为。
- 不引入新依赖（用标准库的 `json`、`contextvars`、`uuid` 即可）。
- 不要求所有 channel 一次性插全，CLI 优先保证北极星场景，其他 channel 允许后续补。

## Steps

每一步都应是一个独立可评审单元。

1. **侦察（read-only）**：扫出六类插桩点在当前代码里的确切位置，产出一张 `<file>:<line> → <kind>` 对照表。不改代码。
2. **trace 模块骨架**：新增 `nanobot/trace/` 模块，实现事件结构、`emit`、contextvar、stdout sink、文件 sink、null sink。加单测。
3. **runtime 初始化**：进程启动时生成 `run_id`，通过 env / CLI 选项启用文件 sink。
4. **Channel 入口插桩**（先 CLI，后其他）：在 CLI channel 收到消息处注入 `trace.context(trace_id=新生成)` 和 `channel.received` 事件。
5. **Planner 入出插桩**：在 agent loop 起止注入 `planner.entered` / `planner.exited`，trace_id 从 contextvar 继承。
6. **Tool 插桩**：在 tool 调用前后注入 `tool.called` / `tool.returned`。
7. **Channel 出口插桩**：在所有 `channel.send(...)` 调用点注入 `channel.sent`。这一步会遍历所有 channel，覆盖度以"能看到"为准，不改发送行为本身。
8. **Memory 插桩**：在 memory 读写关键入口注入 `memory.read` / `memory.write`。
9. **Cron 插桩**：在 cron 触发处注入 `cron.fired`。
10. **北极星场景验证**：写一个最小验收脚本或测试，在 CLI 启动后发送一条测试消息，断言 trace 同时包含 `channel.received`、`planner.entered`、`planner.exited`、`channel.sent`，且三者共享同一个 `trace_id`。
11. **Cron 场景验证**：验证 cron 路径能产生带 `trace_id` 的完整链路。
12. **文档同步**：更新 [`STATUS.md`](../STATUS.md) 标记 Phase 0 完成，准备 Phase 1。

## Acceptance checks

- CLI 发送一条消息后，trace 至少包含 4 类事件（channel.received / planner.entered / planner.exited / channel.sent）且共享 trace_id。
- Trace 在 async / streaming 路径下 trace_id 不丢失（需要一个针对 streaming 出口的专项验证）。
- 不开启文件 sink 时 stdout 输出可解析为 JSONL。
- 启用 trace 前后，CLI 端到端行为（含 tool 调用、cron 触发）与改造前一致。

## Risks & mitigation

- **contextvar 在异步 / 线程 / streaming 下丢失**：在 Step 4 就先写一个最小 async 测试覆盖，确保骨架能用再继续后续插桩。
- **channel 出口分散**：CLI 一条路径全覆盖优先，其他 channel 允许延后；但每个未覆盖 channel 要在 STATUS 已知风险里列出来。
- **payload schema 过早固化**：初版字段宽松，只承诺 `ts / run_id / trace_id / kind` 四个顶层字段稳定，`payload` 内部允许演进。

## Docs to update（完成时）

- [`STATUS.md`](../STATUS.md)：标记 Phase 0 完成，切入 Phase 1。
- [`ROADMAP.md`](../ROADMAP.md)：如果实际落地偏离计划，更新 Phase 0 摘要；Phase 1 scope 基于 Phase 0 实际 trace 格式再细化。

## Exit criteria

- 北极星场景在 CLI 下完整可见：单条用户消息链路的 trace 可读、共享 trace_id、覆盖四类以上事件。
- Cron 路径下 `cron.fired` 可见并带 trace_id。
- Trace 结构和 `emit` API 稳定到可以承载 Phase 1 引入的 intent / effect 事件（即加新 kind 不需要修改 emit 本身）。
