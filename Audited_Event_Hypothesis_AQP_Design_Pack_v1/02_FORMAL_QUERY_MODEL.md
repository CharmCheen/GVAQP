# 02 — Formal Query Model：事件语义、关系模式与成本模型

## 1. 输入空间

将视频切分为有序 atomic units：

\[
U=\{u_1,\ldots,u_n\},\qquad
u_i=(t_i^s,t_i^e,x_i,p_i)
\]

其中：

- \(t_i^s,t_i^e\)：时间范围；
- \(x_i\)：可选 cheap primitives（actor tracks、motion、ego-path cue 等）；
- \(p_i\)：cheap proxy score；
- \(y_i\)：隐藏 oracle label，只能在查询 \(u_i\) 后读取。

当前 CSV replay 只有时间、frame 索引、`proxy_score` 和 hidden `oracle_label`；actor/type/risk 不得在 v0 中伪造。

## 2. 真实事件与 canonical anchor

真实事件集合：

\[
E^\star=\{e_1,\ldots,e_m\}
\]

事件对象：

\[
e=(\tau, A,[t_s,t_e],[t_c^s,t_c^e],r,z)
\]

- \(\tau\)：event type；
- \(A\)：actor 或 actor set；
- \([t_s,t_e]\)：完整事件边界；
- \([t_c^s,t_c^e]\)：核心风险区间；
- \(r\)：risk level；
- \(z\)：语义 evidence / attributes。

### 2.1 Canonical anchor

为使事件可被无重复地计数，每个事件必须定义唯一 canonical anchor：

\[
c:E^\star\rightarrow \{1,\ldots,n\}
\]

要求：

1. 每个事件恰有一个 anchor block；
2. anchor 定义只依赖 event schema，不依赖 discovery policy；
3. 两名标注者可在可接受误差内一致确定；
4. 多 unit evidence 不得生成多个 canonical anchors。

建议 schema：

- **cut-in**：目标 actor 首次进入 ego corridor / ego lane 的时刻；
- **pedestrian crossing**：pedestrian 首次进入 ego path/crossing zone 的时刻；
- **near-miss**：首次达到预注册风险条件或 ego/actor 明确开始 avoidance 的时刻；若不可唯一判定，标记 `anchor_ambiguous=1`，不进入 certificate 主分析。

Canonical anchor 是 audit estimator 的统计单位；它不是 event start 或风险峰值的同义词。

## 3. Query interface

概念查询语法：

```sql
EVENT_SELECT(
  video,
  event_schema,
  oracle
)
WITH ORACLE_BUDGET B
WITH AUDIT_BUDGET B_a
WITH REVIEW_BUDGET R
WITH MISSED_EVENT_RISK delta
RETURN EventRelation;
```

当前系统只实现 `ORACLE_BUDGET` 和 EventRelation 的时间片段子集；`MISSED_EVENT_RISK` 只有 audit estimator 通过验证后才能启用。

## 4. 关系模式

### 4.1 UnitTable

```text
UnitTable(
  video_id,
  unit_id,
  start_time,
  end_time,
  start_frame,
  end_frame,
  proxy_score,
  cheap_feature_version
)
```

### 4.2 ObservationTable

```text
ObservationTable(
  run_id,
  call_idx,
  action_type,
  target_type,
  target_id,
  unit_id,
  oracle_type,
  oracle_cost,
  oracle_response,
  response_schema_version,
  observed_at
)
```

### 4.3 HypothesisTable

```text
HypothesisTable(
  hypothesis_id,
  video_id,
  event_type_distribution,
  actor_ids,
  rough_start,
  rough_end,
  core_start,
  core_end,
  existence_probability,
  boundary_uncertainty,
  type_uncertainty,
  duplicate_risk,
  verification_state,
  evidence_ids,
  materialized_event_id
)
```

CSV-only v0 中 `actor_ids=unknown`，`event_type_distribution={safety_event_unknown:1}`。

### 4.4 HypothesisEdgeTable

```text
HypothesisEdgeTable(
  src_hypothesis_id,
  dst_hypothesis_id,
  relation_type,
  relation_probability,
  evidence_ids,
  state
)
```

允许的 relation：`duplicate`、`continuation`、`same_episode`、`independent`、`competing`、`fragment_of`。只有 relation 影响 query action 或 materialization 时才应建边；纯可视化边不是算法贡献。

### 4.5 EventRelation

```text
EventRelation(
  event_id,
  video_id,
  event_type,
  actor_ids,
  start_time,
  core_start_time,
  core_end_time,
  end_time,
  risk_level,
  confidence,
  evidence_summary,
  verification_state,
  canonical_anchor_time,
  returned_review_seconds
)
```

### 4.6 AuditLedger

```text
AuditLedger(
  audit_round,
  block_id,
  inclusion_probability,
  stratum,
  sampled,
  oracle_cost,
  canonical_anchor_count,
  residual_anchor_count,
  discovered_before_audit,
  adjudication_status
)
```

## 5. Typed query actions

统一表示为：

\[
\operatorname{PROBE}(target,attribute,oracle)
\]

属性包括：

- `existence`：CONFIRM_CORE；
- `coverage`：AUDIT_REGION；
- `left_boundary` / `right_boundary`；
- `identity`：actor linkage；
- `type`；
- `relation`：LINK_OR_SPLIT / BRIDGE；
- `barrier`：查询 gap 是否包含 negative boundary evidence。

当前 binary-unit replay 只可信支持 `existence`、`coverage`、邻域 boundary probe 和 barrier probe。不能用 binary label 模拟 actor/type oracle 后仍声称 typed semantics 已验证。

## 6. 预算与成本

总预算可分为：

\[
B=B_{discovery}+B_{audit}
\]

Discovery ledger 可自适应、有偏；Audit ledger 必须有已知 inclusion probability，且不能由 discovery planner 控制抽样概率。

建议联合成本：

\[
C_{total}=c_o\cdot N_{oracle}+c_r\cdot T_{returned}+c_h\cdot N_{human\ review}
\]

其中 `returned seconds` 是实际下游复核成本。它不能替换 event-F1 主指标，但必须用于解释 aggressive broad segments 的系统代价。

## 7. 目标函数

目标策略 \(\pi\)：

\[
\max_\pi\ \mathbb E\left[
\sum_{e\in E^\star}w_e\mathbf 1(e\text{ discovered})
-\lambda FP
-\mu L_{boundary}
-\rho C_{review}
\right]
\]

约束：

\[
\sum_t Cost(a_t)\le B
\]

当前 replay 的可操作近似：

- 主项：unique event core coverage；
- 次项：prediction count、overmerge、duration 与 IoU；
- 成本：oracle calls 与 returned seconds。

## 8. Event matching

当前主指标为 one-to-one `event_detection@overlap_any`。必须同时报告：

- precision / recall / F1；
- IoU@0.3、IoU@0.5、matched mean IoU；
- overcoverage ratio；
- overmerge multiplicity；
- prediction count error；
- returned seconds。

最终人工 GT 阶段建议加入：

- actor-consistent event match；
- type-consistent event match；
- canonical-anchor recall；
- phase/core interval quality。

## 9. Residual event estimator

将完整时间轴分成 audit blocks \(b=1,\ldots,K\)，每个 block 以已知概率 \(\pi_b>0\) 被独立或分层抽样。令 \(Y_b\) 为该 block 中、在 audit 前仍未被 discovery 找到的 canonical anchors 数量。Horvitz–Thompson 型估计：

\[
\widehat M_{res}=\sum_{b\in S_a}\frac{Y_b}{\pi_b}
\]

在 discovery state 固定、anchor 唯一、inclusion probabilities 正确和 audit oracle 完整计数的条件下，该估计针对 residual canonical-anchor total 具有 design-based 可解释性。

必须注意：

- discovery 与 audit 可共享 oracle infrastructure，但不能共享自适应抽样逻辑；
- audit block 中必须计数所有 residual anchors，不能只给 block binary label；
- confidence bound 需单独验证 coverage；
- sparse events、clustered events 与 ambiguous anchors 会显著增加方差；
- 未通过 simulation 和 held-out coverage test 前只能称 `residual estimator prototype`。

## 10. 理论路线

可能证明 adaptive submodularity 的对象应限制在“distinct event core coverage”，而不是含 boundary/overmerge penalty 的完整 utility。候选充分条件：

1. hypotheses 的 latent existence 近似条件独立；
2. 每次 probe 只揭示局部 state；
3. 新事件覆盖收益单调且边际递减；
4. duplicate hypotheses 对同一 canonical event 的收益饱和。

Boundary loss、relation repair 和 negative merge penalty 可能破坏单调性/次模性。理论 agent 应先证明受限 core-discovery objective；失败时诚实转为 empirical VOI optimizer，不得强行声称 approximation guarantee。
