# 03 — Method Architecture：从 BB-EM 到 Audited SEHS

## 1. 总体查询计划

```text
CheapPrimitiveScan / ProxyScan
        ↓
HypothesisSeed
        ↓
Adaptive Probe Executor
        ↓
HypothesisStateUpdate
        ↓
BB-EM Event Materialization
        ↓
EventRelation
        ↘
     Independent Audit Ledger
        ↓
Residual-Mass Estimate / Stop Decision
```

当前实现成熟度不均衡：BB-EM 最成熟，MAP-anchor-only 有 pilot 支持，完整 hypothesis graph、VOI 和 audit certificate 尚未闭环。

## 2. BB-EM/K3：冻结的 pilot materializer

### 2.1 输入

- 有序 UnitTable；
- 已查询 ObservationTable；
- 可选 CandidateTable；
- 固定参数 `G_max`、`D_core_max`、`D_seg_max`。

### 2.2 语义

- queried positive → anchor；
- queried negative → hard barrier；
- merge 是显式受限行为，不是默认连通分量；
- segment 不得跨 hard barrier；
- segment duration 不得超过上限；
- unqueried unit 不能成为新 event seed。

### 2.3 伪代码

```text
BB_EM_K3(U, Observations, G_max, D_core_max, D_seg_max):
    A ← sorted queried-positive units
    N ← queried-negative units
    components ← []

    for anchor a in A:
        if components is empty:
            start new component with a
            continue

        c ← last component
        link_allowed ← (
            gap(c.last_anchor, a) <= G_max
            and no negative unit in N lies between c.last_anchor and a
            and span(c.first_anchor, a) <= D_core_max
        )

        if link_allowed:
            append a to c
        else:
            start new component with a

    segments ← anchor spans of components
    split any segment violating D_seg_max
    assert no segment crosses N
    return segments
```

### 2.4 Invariants

1. `Barrier safety`：不跨 queried-negative barrier。
2. `Duration boundedness`：不超过预注册上限。
3. `No unobserved seeding`：未查询 label 不能生成新事件。
4. `Selector agnosticism`：不依赖 ARC/SUPG/ABae/Ours 内部逻辑。
5. `Evidence monotonicity with caution`：新增 positive anchor 可增加或扩充事件，但不得无显式条件破坏性合并此前分离事件。

### 2.5 当前开放审计

K3、K4、C6 在 pilot 指标完全一致。必须统计 optional rule trigger count 和 output lineage，以排除 variant harness 复用或无效消融。

## 3. MAP-anchor-only：当前最小 acquisition policy

### 3.1 Hypothesis seed

只用 proxy 与时间构造 temporal components：

1. high-proxy islands；
2. local peaks；
3. uncovered-window audit candidates；
4. candidate deduplication。

### 3.2 状态

```text
TemporalComponent(
  component_id,
  start_unit,
  end_unit,
  core_unit,
  max_proxy,
  mean_proxy,
  queried_count,
  positive_anchor_count,
  distance_to_nearest_query,
  status
)
```

### 3.3 Actions

- `CONFIRM_ANCHOR(component)`；
- `AUDIT_UNCOVERED(region)`。

Stage 1A 不允许 barrier、bridge、type、actor、boundary actions。

### 3.4 当前评分

```text
score_anchor(c) =
  proxy_eventness(c)
  × temporal_novelty(c)
  × coverage_gap(c)
  / (1 + nearby_query_count)

score_audit(r) =
  uncovered_duration(r)
  × representative_proxy(r)
  × isolation_bonus(r)
```

固定 action 比例属于 pilot heuristic，不能作为最终 optimizer 原理。

## 4. Minimal SEHS-node：下一阶段最小方法

只有 ceiling gates 通过才实现。目标不是完整 actor graph，而是证明 query-time event state 有增量。

### 4.1 State

```text
h = {
  hypothesis_id,
  support_interval,
  core_candidates,
  positive_anchors,
  negative_barriers,
  existence_probability,
  boundary_uncertainty,
  verification_state
}
```

### 4.2 Actions

只保留：

- `CONFIRM_CORE(h)`；
- `AUDIT_REGION(r)`；
- `EXPAND_BOUNDARY(h, side)`；
- `STOP`。

不实现 graph relation、actor linking、type disambiguation，直到 minimal node 在 held-out videos 上超过公平 baseline。

### 4.3 Rule-based v0

```text
priority =
  expected_new_core_gain
  + small_boundary_gain
  + uncovered_region_gain
  - duplicate_query_penalty
```

低预算优先 core / audit；边界 probe 只在 core 已确认且高价值 unverified hypotheses 基本耗尽后执行。

## 5. 目标 AEH-AQP hypothesis graph

### 5.1 必要节点

- `primitive node`：actor track / motion / ego relation；
- `atomic interval node`；
- `event hypothesis node`；
- `oracle observation node`；
- `materialized event node`。

CSV-only 阶段只具备后四者中的 interval、hypothesis、observation、event 的弱版本。

### 5.2 必要边

- temporal adjacency；
- same actor / track continuity；
- supports / contradicts；
- duplicate / competing；
- continuation / fragment-of；
- independent；
- confirms / rejects / refines。

边必须改变 action enumeration、probability update 或 materialization；否则属于工程包装。

## 6. Typed probes

完整 action space 由 event schema 字段产生，而非手写六条规则：

```text
PROBE(h, existence)
PROBE(h, left_boundary)
PROBE(h, right_boundary)
PROBE(h, type)
PROBE(h, actor_identity)
PROBE((h_i,h_j), relation)
PROBE(region, residual_presence)
```

不同 oracle 返回不同 schema，必须有明确成本与不可比性处理。

## 7. Counterfactual materialization-aware VOI

状态 \(S_t\) 包括当前 observations、hypotheses 和 EventRelation \(R_t\)。对 action \(a\) 及可能 outcome \(o\)：

\[
R_t^{a,o}=Materialize(Update(S_t,a,o))
\]

\[
VOI(a)=\frac{\sum_o P(o\mid a,S_t)[J(R_t^{a,o})-J(R_t)]}{Cost(a)}
\]

`J` 不得使用 reference events。可用 surrogate：

- distinct supported hypothesis count；
- duplicate saturation；
- returned duration；
- unresolved long gaps；
- boundary uncertainty；
- audit coverage。

### 7.1 Outcome calibration

v0 使用在线 Beta-Bernoulli bins：proxy quantile × action type × target position。跨视频后再训练 ranker。

必须报告：

- Brier score / ECE；
- prior-wrong stress test；
- oracle-informed planner regret；
- action mix 稳定性。

### 7.2 Asymmetric barrier semantics

`PLACE_BARRIER` 的 positive 结果不能默认桥接左右事件：

```text
negative → hard barrier
positive → isolated ambiguous anchor
          does not auto-merge existing events
```

Invariant：一次 barrier probe 不得自动把两个此前分离的 materialized events 合并。

## 8. Independent audit ledger

### 8.1 原则

- audit sample 的概率在 discovery outcome 之前确定或由合法分层设计确定；
- discovery planner 不得选择 audit blocks；
- audit oracle 必须按 canonical anchor 计数，而不是 block binary label；
- audit observations 可用于最终估计，但不能回写 discovery ranking 后仍声称 estimator independent，除非使用 sample splitting / two-phase design。

### 8.2 执行

```text
1. Freeze discovery EventRelation R_d.
2. Draw audit blocks with known probabilities.
3. Human/VLM adjudicates all canonical anchors in each block.
4. Mark whether each anchor was already discovered.
5. Estimate residual mass and uncertainty.
6. Stop only if pre-registered upper bound is below tolerance.
```

## 9. AEH-AQP 总伪代码

```text
AEH_AQP(Video V, Schema S, Budget B, AuditBudget Ba):
    U, P ← CheapPrimitiveScan(V)
    G ← HypothesisSeed(U, P, S)
    O ← empty ObservationTable

    while discovery_cost(O) < B:
        A ← EnumerateTypedActions(G, O)
        for a in A:
            estimate P(outcome | a, G, O)
            simulate counterfactual state and EventRelation
            score[a] ← expected event-set gain / cost
        a* ← argmax score
        if score[a*] <= stop_threshold:
            break
        o ← query oracle(a*)
        O ← O ∪ {(a*, o)}
        G ← UpdateHypotheses(G, a*, o)

    R ← BB_EM_or_TypedMaterializer(G, O)
    L_a ← IndependentAudit(V, R, S, Ba)
    M_hat, CI ← EstimateResidualMass(L_a)
    return R, M_hat, CI, O, L_a
```

## 10. 不应实现的捷径

- 用 reference-aware utility 做 online VOI；
- 用同一 proxy 同时生成候选、校准 outcome、证明 completeness，却无独立 audit；
- 直接把 scene graph 输入 GNN，缺少可解释 action/cost semantics；
- 用一个 B=50 gate 代替 adaptive planning，并称为 query optimizer；
- barrier positive 直接当 bridge；
- 在单 pilot 上训练 learned ranker。
