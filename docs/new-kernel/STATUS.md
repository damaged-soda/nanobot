# 当前状态

## 当前阶段

Phase 1：outbound behavior 的 effect isolation。

## 当前目标

让 outbound message 从 planner 中剥离出来，改为通过 intent / outbox / effector 边界处理。

## 当前范围

- 引入显式的 `SendMessageIntent`。
- 引入显式的 `NoReplyChosen`。
- 引入 outbox-like boundary。
- 让 simulation path 能检查 send / no-send / exactly-once。
- 通过 adapter 保持旧 shell 行为尽量不变。

## 非目标

- 完整 event-sourced kernel。
- 完整 context compiler。
- 完整 resource ownership rewrite。
- 完整 TDAD pipeline。
- 完整 cleanup verifier。
- 分布式 message bus 或多进程 runtime。

## 验收标准

- planner path 不再直接调用真实 channel 发送消息。
- live mode 仍能正常向外发送消息。
- simulate mode 能验证：应该发送、不应该发送、正好发送一次。
- 北极星场景 1 初步通过。
- 相关 event / intent / verification 文档已更新。

## 冻结区域

- 旧 memory 系统的核心语义。
- provider 层。
- 大多数 channel adapter 的外部接口。
- upstream sync 策略。

## 已知风险

- 旧 `AgentLoop` 可能隐含多个直接副作用路径。
- channel 抽象可能把“计划发送”和“真实发送”混在一起。
- simulation path 如果只 mock 最外层，可能漏掉内部直接副作用。

## 最后更新时间

- YYYY-MM-DD
