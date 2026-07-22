# 06 — Agent / LLM Operating Manual

## 1. 适用对象

- coding agent；
- experiment agent；
- data audit / annotation agent；
- theory agent；
- literature agent；
- paper-writing agent；
- red-team reviewer。

## 2. 开始任务前必须读取

1. `README.md`；
2. `12_DECISION_LOG.md`；
3. 与任务相关的正式 spec；
4. `11_FROZEN_CONFIG_FOR_CROSS_VIDEO.md`；
5. 现有 stage 的 FINAL_REPORT 与 sanity report。

不得仅凭聊天摘要改代码。

## 3. 状态标签

所有结论必须带一个标签：

- `VERIFIED_ARTIFACT`：由代码、hash、sanity 和可复现输出验证；
- `PILOT_CONFIRMED`：单 pilot 统计支持；
- `PILOT_SUPPORTED`：有限证据、非决定性；
- `HYPOTHESIS`：待实验；
- `TARGET_DESIGN`：未来方法；
- `DEPRECATED`：不得用于新 claim；
- `BLOCKED`：存在 source/implementation conflict；
- `NOT_APPLICABLE`。

禁止把 `TARGET_DESIGN` 写成过去式。

## 4. 全局硬约束

1. reference events 只能用于 evaluation、annotation audit、diagnostic ceiling。
2. hidden oracle labels 只能在 policy 已选择 unit/action 后读取。
3. 任何 query ranking 中不得使用 reference overlap、event id 或未来 observation。
4. 不得修改 baseline 原始输出后仍称 native baseline。
5. strengthened baseline 必须明确标记 `+ BB-EM`。
6. 不得 per-budget pick-best 配置作为单一方法。
7. 不得在 held-out/test video 上调参数。
8. 不得调用新模型/GPU/下载，除非 task spec 明确允许。
9. 所有随机性固定 seed，并记录版本。
10. 发现 bug 时先停止与报告，不能偷偷修后覆盖旧结果。

## 5. 标准任务输入

每个任务 spec 必须包含：

```text
Goal
Research question
Allowed changes
Forbidden changes
Inputs and versions
Frozen parameters
Baselines
Budgets
Metrics
Sanity checks
Expected outputs
GO/NO-GO rules
Claim impact
```

缺少其中任一关键字段，agent 应输出 `TASK_SPEC_INCOMPLETE`，不得自行猜测会影响论文结论的设置。

## 6. 标准运行输出

### 文件

```text
script/config changes
run_manifest.json
artifact_hashes.csv
metrics_by_run.csv
sanity_checks.md
FINAL_REPORT.md
logs/progress.md update
```

### FINAL_REPORT 必须回答

1. 做了什么、没做什么；
2. 输入与 commit/config hash；
3. sanity 是否全过；
4. 主要结果；
5. 失败/异常；
6. 决策；
7. 对 claim 的影响；
8. 下一步是否被 gate 允许。

## 7. Claim hygiene

### 可用表述

- “On the current pilot…”
- “Under fixed oracle logs…”
- “Under a shared BB-EM materializer…”
- “The evidence supports…”
- “The result does not establish…”

### 禁止表述

- “proves generalization” 对单视频结果；
- “guarantees recall” 对未验证 estimator；
- “SEHS outperforms all baselines” 对 B≤10 native ARC 反例；
- “actor-aware” 对 CSV-only 方法；
- “all components contribute” 对零 AUC-drop 消融。

## 8. 数据泄漏检查清单

每个 selector run 自动验证：

- query choice 前是否访问 `oracle_label`；
- component/hypothesis 是否含 reference-derived 字段；
- budget prefix 是否正确；
- call_idx 是否严格递增；
- 是否重复查询；
- evaluator 是否读取新 segments；
- parameter selection 是否使用 test metrics。

## 9. 实现审计要求

任何 ablation 机制必须输出：

```text
candidate_count
trigger_count
blocked_count
applied_count
output_changed_count
output_hash
```

零指标差异不能自动解释为“机制无用”；先判断未触发、被其他规则支配还是代码路径无效。

## 10. Agent 角色说明

### Coding agent

只实现 spec；不得修改目标函数、指标或参数。发现必要变更，先提交 design change proposal。

### Evaluation agent

独立于方法实现；验证 path、hash、metric protocol 和 native/strengthened 标签。

### Data agent

负责 event schema、canonical anchor、annotation agreement；不得调方法。

### Theory agent

只在明确假设下推导；需列出哪些 empirical mechanisms 破坏假设。

### Literature agent

优先一手论文/官方源码；区分 query object、guarantee、cost model、output semantics。

### Red-team agent

寻找 leakage、unfair cost、post-hoc threshold、metric gaming、pseudo-GT circularity。

## 11. Design change process

任何冻结方法/参数修改必须创建：

```text
CHANGE_ID
motivation
old value / new value
which data motivated change
whether test data was seen
required reruns
claim impact
approval status
```

若看过 held-out 结果后修改，该 held-out split 自动失效。

## 12. Handoff 模板

```markdown
# Handoff: <task>

## Status
DONE / PARTIAL / BLOCKED

## Commit and config
- commit:
- config hash:
- data manifest:

## Files changed

## Commands run

## Sanity summary

## Results

## Decision

## Claim impact

## Known caveats

## Exact next task
```

## 13. 失败处理

- 代码失败：保留 logs，不覆盖 output directory；
- sanity fail：不发布 metrics；
- metric mismatch：比较 evaluator input hash；
- baseline bug：所有受影响 stage 标记 invalid 并重跑；
- ground-truth disagreement：暂停 model ranking；
- no significant gain：如实 NO-GO，不增加复杂机制“救结果”。
