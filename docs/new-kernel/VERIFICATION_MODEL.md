# 验证模型

## Why verification is externalized

planner 不是正确性的最终裁判。让同一个模型“自己想想是否做对了”不足以支撑长期自动化。系统需要外部化、可执行、可重放的验证机制。

## Assurance layer

assurance layer 横跨 runtime：simulation、replay、scenario checks、regression checks、TDAD checks、cleanup verification、publish gate。

它不是一个 prompt，也不是一个 memory 策略，而是 runtime 的边界层。

## Verification categories

### Visible checks

开发/编译过程中可见的检查，用于指导候选改动收敛。

### Hidden checks

候选改动通过 visible checks 后再运行，用于防止只针对表面 case 过拟合。

### Scenario checks

围绕 north-star scenarios 的端到端行为检查。

### Regression checks

防止已有行为被破坏。

### Cleanup checks

验证最终 diff 中每块保留修改是否仍然必要。

## TDAD in this repo

TDAD 的角色是：把需求或行为 spec 变成可执行检查，然后在 simulation/replay 环境中验证候选改动是否真的支持目标未来行为。

在本项目中，TDAD 不应该直接等同于“让模型反思”。它需要依赖 explicit spec、executable checks、simulation harness、observable intent/effect traces、publish gate。

## Cleanup verifier in this repo

cleanup verifier 的角色是防止过期的试探性修改进入最终发布结果。

基本流程：

1. 生成 candidate patch。
2. 跑 acceptance checks，确认目标行为满足。
3. 对 diff 做 hunk/file 级回退实验。
4. 如果撤销某块改动后检查仍通过，则删除该块改动。
5. 直到没有可删除的多余改动。
6. 再进入 publish gate。

## Publish rule

任何候选改动只有同时满足以下条件才能发布：

- 目标行为已被验证。
- 回归检查通过。
- simulate path 没有真实副作用。
- 保留修改仍然有必要。
- 相关文档已同步。

## Simulation semantics

simulate mode 中：不调用真实 channel 发送消息；不真实写外部系统；不真实调用不可逆 API；effectors 被 recorder/verifier 替换；intent / would-be effect 必须可观察。

## Evidence

一次验证结果至少应能回答：触发了哪些事件、产生了哪些 intent、live 模式下会产生哪些 effect、simulate 模式是否阻止真实副作用、哪些检查通过或失败、如果涉及 patch 哪些 hunk 被保留或删除。
