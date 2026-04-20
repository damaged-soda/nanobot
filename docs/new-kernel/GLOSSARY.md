# 术语表

## nanobot shell

保留自 nanobot 的产品外壳，包括 CLI、gateway、channel、workspace、provider/tool 接入等用户可见能力。

## event-sourced core

以 append-only event log 为中心的运行内核。状态可以从事件重建或派生。

## effect isolation

决策和副作用分离。planner 只能产出 intent，真实副作用由 effector 消费 intent 后执行。

## event

系统中已经发生的事实。

## intent

系统准备做的动作，尤其是可能产生外部副作用或持久状态变化的动作。

## effect

外部世界或持久状态实际发生的结果。

## resource

长期存在、有明确 owner 的状态对象。

## view

由 event/resource 派生出的查询视图，不是权威事实来源。

## run mode

运行模式，例如 live、simulate、replay、compile。

## TDAD

Test-Driven AI Agent Definition。在本项目中指从行为 spec 出发，用可执行检查验证 agent/artifact 是否满足目标行为。

## cleanup verifier

发布前最小化候选改动的验证器。它通过回退 hunk 并重跑检查，删除不再必要的修改。

## publish gate

候选修改进入真实 workspace 或外部世界之前必须通过的验证边界。

## source-of-truth 错位

一条信息被写进了错误的持久载体。例如 job 专属约束被写入 global memory，而不是 `JobSpec`。
