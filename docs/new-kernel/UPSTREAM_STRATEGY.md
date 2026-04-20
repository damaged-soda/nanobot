# 上游策略

## Base

本 fork 基于 nanobot 的某个稳定 tag/commit。实际落库时在这里填写：

- Upstream repo：`<url>`
- Base tag/commit：`<tag-or-sha>`
- Fork created at：`<date>`

## What we keep aligned

尽量与上游保持同步的部分：

- shell-facing behavior。
- channel integrations。
- provider/tool utility code。
- 不影响新 runtime 语义的 bug fix。

## What becomes fork-owned

本 fork 自有并优先保留的部分：

- event-sourced runtime kernel。
- effect isolation semantics。
- verification model。
- publish gate。
- resource ownership rules。
- TDAD / cleanup verifier 集成。

## Sync policy

- 不连续追上游，采用 intentional sync。
- 每次 sync 前先评估是否影响 runtime semantics。
- 上游 cron/context/memory 改动逐项判断，不盲目合并。

## Conflict rule

当上游变化与本 fork 的目标架构冲突时：

> 保留本 fork 的 runtime 语义，除非明确决定回退该架构方向。

## Documentation rule

任何影响上游策略的决定必须更新本文件，并在必要时新增 ADR。
