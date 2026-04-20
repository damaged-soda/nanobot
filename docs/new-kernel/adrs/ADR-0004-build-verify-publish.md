# ADR-0004：采用 Build -> Verify -> Publish 边界

## Status

Accepted

## Context

agent 修改代码或配置时，容易先做试探性修改，再通过其他修改解决问题，最终把过期修改留在 diff 中。仅靠测试通过不足以保证改动最小且必要。

## Decision

所有可发布改动都必须先成为 candidate，再经过 verification 和 cleanup verifier，最后才允许 publish。

## Alternatives considered

1. 让 agent 自己反思是否需要清理。
2. 只依赖常规测试。
3. 只依赖人工 review。

## Consequences

- cleanup verifier 成为 publish gate。
- scratch workspace / candidate patch 变得重要。
- 需要定义 acceptance checks 和 regression checks。
- 发布流程更重，但更适合长期自动化。
