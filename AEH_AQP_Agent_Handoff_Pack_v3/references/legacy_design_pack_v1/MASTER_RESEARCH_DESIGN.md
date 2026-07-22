# MASTER RESEARCH DESIGN — Audited Event-Hypothesis AQP

**版本**：v1.0  
**冻结日期**：2026-07-10  
**状态**：研究设计规范；不是最终论文，也不代表所有目标组件已实现。  
**用途**：让新的 researcher / coding agent / evaluation agent / annotation agent / paper agent 在不依赖聊天历史的情况下继续工作。

---

## 0. Executive decision

本课题研究的是：

> 在长第一视角驾驶视频中，cheap primitives / proxy 可能遗漏稀有安全事件，而 expensive oracle（VLM 或人工）预算有限。系统需要在预算约束下发现、验证、去重和定位事件，并在可能时估计仍未发现的事件质量。

必须同时维护两条边界清楚的路线：

### 当前可防守系统

```text
MAP-anchor-only
    → BB-EM/K3
    → EventRelation
```

- **BB-EM/K3**：当前最稳主贡献候选；是 selector-agnostic 的 bounded / barrier-aware event materialization operator。
- **MAP-anchor-only**：已有 pilot 支持的轻量 acquisition enhancement；仅能声称在共享 materializer 的 strengthened-baseline 设置下有低预算增量。

### 顶会目标算法

```text
Audited Event-Hypothesis AQP (AEH-AQP)
```

由四部分组成：

1. actor-centric event hypotheses 作为 query execution state；
2. schema-derived typed probes 作为 physical operators；
3. materialization-aware adaptive planner；
4. independent audit ledger + residual missing-event estimator。

当前 **不能** 声称完整 AEH-AQP、SEHS、VOI planner 或 statistical certificate 已成立。

---

## 1. Research question

给定长视频 units：

```text
U = {u_1, ..., u_n}
```

每个 unit 可获得 cheap proxy / primitives，但 expensive oracle 只有在系统支付查询成本后才返回 observation。系统在总预算 `B` 下输出事件关系：

```text
EventRelation(
  event_id,
  event_type,
  actor_id_or_set,
  start_time,
  core_start_time,
  core_end_time,
  end_time,
  risk_level,
  confidence,
  evidence_summary,
  verification_state,
  canonical_anchor_time
)
```

核心问题不是“选择哪些 positive clips”，而是联合解决：

1. **candidate coverage**：真实事件是否进入 hypothesis space；
2. **budget allocation**：下一次 oracle query 应作用于哪个 hypothesis / attribute；
3. **event materialization**：sparse observations 如何变成 distinct event objects；
4. **residual completeness**：尚未发现的事件质量如何被独立估计。

---

## 2. Why this is not ARC / SUPG / ABae / EQUI-VOCAL

| System family | Query object | Main optimization target | Output |
|---|---|---|---|
| ARC | relevant clips | approximate relevant-clip retrieval | clips |
| SUPG | records satisfying an expensive predicate | record-level precision/recall guarantee | selected records |
| ABae | aggregate over records with expensive predicates | estimator error / allocation | aggregate |
| Seiden | frames / video segments | exploration–exploitation for video queries | retrieval / aggregate answer |
| EQUI-VOCAL | compositional scene-graph query | synthesize a query from examples | symbolic query + matched events |
| This project | structured temporal event objects | event discovery, materialization and residual completeness under oracle budget | EventRelation + optional residual estimate |

“使用 event graph”本身不构成 novelty。数据库贡献必须落在：

- query semantics；
- execution state；
- physical operators；
- budget optimizer；
- independent audit / stopping semantics。

---

## 3. Evidence status

### 3.1 Pilot-confirmed

- clip/unit evidence 与 event-set output 之间存在 materialization gap；
- naive/aggressive merge 会在证据变多时造成 destructive overmerge；
- BB-EM/K3 是当前最小、最可解释的 materializer 候选：

```text
positive anchors
+ gap limit
+ duration prior
+ queried-negative hard barrier
```

### 3.2 Pilot-supported

- MAP component-first anchor probing 在共享 K3 的 strengthened-baseline 比较中改善低预算 F1、AUC 和 unique-events/query；
- 该证据不能泛化到所有 native baselines 或多视频。

### 3.3 Open audits

- K3/K4/C6 输出相同是否因为 optional mechanisms 未触发，还是 variant harness 问题；
- MAP-anchor-barrier 的高预算 overcoverage 上升来自哪个状态更新或 materialization path；
- SUPG all-selected 与 confirmed-only 是否在 adapter 中真实退化一致；
- 所有 MAP 参数与 budget gate 的真实代码值和 provenance。

### 3.4 Not established

- actor-centric graph 带来 planner 增量；
- learned or calibrated VOI 有效；
- candidate space 足够覆盖人工 GT；
- residual-mass estimator 有有效 coverage；
- SIGMOD/VLDB 级 statistical guarantee。

---

## 4. Formal query semantics

建议最终定义：

```sql
EVENT_SELECT(
  video,
  event_schema,
  reference_oracle
)
WITH ORACLE BUDGET B
WITH OPTIONAL MISSED_EVENT RISK delta
RETURN EventRelation, ResidualEstimate
```

真实事件集合为 `E*`。执行策略 `π` 在 history `H_t` 下选择 action：

```text
a_t = π(H_t),   Σ Cost(a_t) ≤ B
```

最终经验目标：

```text
maximize:
  weighted distinct-event coverage
  - false-positive penalty
  - boundary loss
  - duplicate / overmerge penalty
  - returned-video review cost
```

对于 certificate 路线，每个事件必须有唯一 **canonical anchor**，使事件可被映射到唯一 audit block；否则 residual event count 不可识别。

---

## 5. Current physical operator: BB-EM/K3

### 5.1 Signature

```text
BB_EM(
  ObservationTable,
  ProxyTable,
  CandidateTable,
  FrozenConfig
) -> EventRelation
```

### 5.2 Input semantics

```text
ObservationTable(
  video_id, unit_id, start_time, end_time,
  queried, oracle_label, query_step, action_type
)

ProxyTable(
  video_id, unit_id, proxy_score, optional_primitives
)

CandidateTable(
  video_id, unit_id, hypothesis_id, selected_by_policy
)
```

### 5.3 K3 invariants

1. queried positive unit 可成为 anchor；
2. queried negative unit 是 hard barrier；
3. 不跨 hard barrier 合并；
4. anchor link 必须满足 frozen gap limit；
5. segment 必须满足 frozen duration bounds；
6. 不读取 unqueried label；
7. 新证据不能在没有显式 link evidence 时破坏性合并两个已分离事件。

### 5.4 Current frozen pilot values

```text
G_max       = 1 unit
D_core_max  = 40 s
D_seg_max   = 60 s
```

这些值属于 pilot-selected config，cross-video test 中不得调整。

---

## 6. Current acquisition policy: MAP-anchor-only

### 6.1 Hypothesis abstraction

当前 MAP 使用 proxy-only temporal components，而非完整 actor graph：

```text
component_id
interval
core candidate
max / mean proxy
queried count
positive-anchor count
coverage state
```

### 6.2 Allowed actions

```text
CONFIRM_ANCHOR(component)
AUDIT_UNCOVERED(region)
```

禁止在当前版本中声称 actor linking、type disambiguation、bridge relation 或 risk reasoning。

### 6.3 Current claim

允许：

> Component-first materialization-aware probing has pilot evidence of improving low-budget event discovery under a shared BB-EM materializer.

禁止：

> MAP dominates ARC/SUPG/ABae at every budget.

在 `B≤10`，native ARC 的 raw `overlap_any` 结果更强；boundedness 和 overcoverage 只能作为并列语境，不能替代主指标事实。

---

## 7. Target algorithm: Audited Event-Hypothesis AQP

### 7.1 Event-hypothesis state

```text
h = {
  hypothesis_id,
  actor_id_or_set,
  event_type_distribution,
  rough_interval,
  core_interval,
  positive_anchors,
  negative_barriers,
  boundary_uncertainty,
  identity_uncertainty,
  type_uncertainty,
  duplicate_risk,
  fragment_relations,
  verification_state,
  evidence_lineage
}
```

### 7.2 Schema-derived probes

统一形式：

```text
PROBE(target, attribute)
```

属性可包括：

```text
existence
boundary_left
boundary_right
identity
relation
event_type
risk
```

最小实现顺序：

```text
CONFIRM_CORE
AUDIT_REGION
EXPAND_BOUNDARY
STOP
```

只有最小版本通过 gates，才加入：

```text
BRIDGE_FRAGMENT
LINK_OR_SPLIT
DISAMBIGUATE_TYPE
actor-centric graph
```

### 7.3 Adaptive planner

目标是 materialization-aware value of information：

```text
VOI(a) = expected downstream EventRelation utility gain / Cost(a)
```

不能直接使用 reference events。Outcome model 必须用 held-out videos 或在线已查询 observations 校准，并报告 calibration error、prior-wrong robustness 与 action regret。

### 7.4 Independent audit ledger

总预算拆分：

```text
B = B_discovery + B_audit
```

- discovery ledger：可高度自适应、有偏；
- audit ledger：独立随机抽取 canonical-anchor blocks，inclusion probability 已知；
- audit oracle 在抽中的 block 内完整计数尚未被 discovery 捕获的 anchors；
- 使用 Horvitz–Thompson / stratified estimator 估计 residual mass；
- 必须通过 empirical coverage test 后才能称 certificate。

---

## 8. Three ceiling experiments before planner expansion

### 8.1 Candidate ceiling

查询全部 hypotheses 时，人工 GT events 中有多少能被 candidate space 表达？

```text
GO: ceiling ≥ 0.80
NO-GO: < 0.80 → 停止 planner，修 hypothesis construction
```

至少同时报告：

- core candidate ceiling；
- materializable candidate ceiling；
- proxy-invisible event count。

### 8.2 Oracle-informed planner ceiling

允许 planner 知道真标签，但仍遵守 action space 与 budget，测可达到的理论上限。

```text
target-budget GO: event recall ≥ 0.70–0.75
```

若 ceiling 本身低，则扩 action space；不要调 learner。

### 8.3 Materializer ceiling

固定 queried evidence 后，reference-aware optimal partition 可达到多少？若 BB-EM 接近 upper bound，则冻结 BB-EM；若差距大，再研究 event partition operator。

---

## 9. Evaluation protocol

### 9.1 Required baselines

```text
Native ARC / SUPG / ABae
ARC + shared BB-EM
SUPG + shared BB-EM
ABae + shared BB-EM
MAP-anchor-only + BB-EM
Minimal SEHS-node + BB-EM
```

任何 planner claim 必须基于 shared materializer 比较；否则增益可能只是后处理。

### 9.2 Primary and secondary metrics

Primary：

```text
event_detection@overlap_any, one-to-one matching
```

Secondary：

```text
IoU@0.3 / IoU@0.5
matched mean IoU
overcoverage
overmerge multiplicity
prediction count error
avg / p90 / max duration
duplicate / oversplit diagnostics
```

Efficiency：

```text
event-F1 AUC over budget
unique events per query
oracle calls to target quality
returned seconds / review minutes
combined oracle + review cost
```

不能因 ARC 在主指标上获胜就只报告 boundedness；两者必须并列。

### 9.3 Data rules

- pilot 仅用于开发；
- test 必须多视频、人工 adjudicated GT；
- 至少一个 external dataset / source；
- video-level paired bootstrap / confidence interval；
- 参数在 test 前冻结；
- test 后修改参数则该 split 作废。

---

## 10. Immediate execution plan

```text
T00 Repository sync and artifact manifest
T01 Pre-cross-video robustness audit
T02 Human GT + canonical anchor protocol
T03 Candidate / planner / materializer ceilings
T04 Minimal SEHS-node replay
T05 Independent audit ledger prototype
T06 Frozen cross-video validation
T07 Adaptive-submodularity feasibility
```

### Hard gate before cross-video

必须完成：

1. C6/K3 trigger and path audit；
2. Stage 1B overcoverage lineage forensics；
3. SUPG variant path audit；
4. complete frozen config extracted from code；
5. repository/artifact sync；
6. human GT schema and canonical-anchor agreement study。

---

## 11. GO / NO-GO logic

| Observation | Decision |
|---|---|
| candidate ceiling <0.80 | stop planner; repair candidate generation |
| oracle-informed planner ceiling low | expand or redefine action space |
| ceiling high but Minimal SEHS ≤ ARC+BB-EM | planner idea no-go; keep BB-EM-only line |
| BB-EM gains disappear cross-video | downgrade to pilot engineering module |
| canonical anchor cannot be made unique/reliable | stop certificate line |
| audit interval fails empirical coverage | empirical audit only; no guarantee language |
| actor graph has no independent gain | remove graph from main method |
| only raw overlap_any improves via long segments | no bounded event-set claim |

---

## 12. Claim ladder

### Claimable now, only as pilot findings

- event materialization gap exists on the pilot；
- K3 is the current minimal BB-EM candidate；
- MAP-anchor-only has pilot evidence against strengthened baselines。

### Claimable after cross-video validation

- BB-EM is a selector-agnostic event materialization operator；
- MAP / Minimal SEHS accelerates event discovery under shared materialization；
- boundedness / review-cost tradeoff is stable across videos。

### Claimable only after audit validation

- residual event mass estimate；
- calibrated stopping rule；
- missed-event risk statement / certificate。

---

## 13. Agent operating contract

每个 agent 必须先读取：

```text
AGENT_START_HERE.md
README.md
06_AGENT_OPERATING_MANUAL.md
07_AGENT_TASK_QUEUE.md
11_FROZEN_CONFIG_FOR_CROSS_VIDEO.md
12_DECISION_LOG.md
```

每次任务必须输出：

```text
TASK_ID
inputs + hashes
code version / commit
frozen parameters
run commands
sanity results
metrics
failure cases
claim status change
next decision
```

状态标签仅允许：

```text
PILOT_CONFIRMED
PILOT_SUPPORTED
CROSS_VIDEO_CONFIRMED
HYPOTHESIS
BLOCKED
REJECTED
NOT_CLAIMABLE
```

若代码、artifact 与文档冲突，停止实验并标记：

```text
BLOCKED_BY_SOURCE_CONFLICT
```

---

## 14. Paper endpoint options

### Endpoint A — Practical systems paper

- materialization gap；
- BB-EM physical operator；
- MAP / Minimal SEHS empirical acceleration；
- decoupled and frozen cross-video evaluation。

### Endpoint B — Strong AQP paper

在 A 基础上增加：

- canonical-anchor event semantics；
- independent audit ledger；
- validated residual estimator / stopping rule；
- optional adaptive-submodular result for restricted core-coverage objective。

在 certificate 未通过前，不得用 “guaranteed event recall” 或 “missed-event risk guarantee”。

---

## 15. Single best next move

不是继续扩完整 graph，也不是继续在 pilot 上调参数。下一步应完成：

```text
Repository sync + preflight audit + human GT/canonical anchor + three ceilings
```

三类 ceiling 通过后再实现 Minimal SEHS-node；Minimal SEHS-node 在 shared BB-EM、held-out videos 上有明确增量后，才投入 full actor graph、calibrated VOI 与 audit certificate。
