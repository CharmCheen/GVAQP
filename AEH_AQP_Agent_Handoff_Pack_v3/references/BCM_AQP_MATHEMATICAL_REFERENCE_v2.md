# BCM-AQP Mathematical Reference v2

**Title:** Binary Counterfactual Materialization-Aware Approximate Query Processing for Event-Level Video Discovery  
**Status:** Audited mathematical and implementation reference; **not** a claim that BCM-AQP is already validated.  
**Primary audience:** Codex and other implementation/evaluation agents.  
**Scope:** CPU replay over frozen units, cheap proxy features, an exact-on-query unit predicate, and event-level materialization/evaluation.  
**Audit date:** 2026-07-10.  

---

# 1. Chinese Executive Summary

## 1.1 重新审计后的核心结论

上一版数学 reference 不合格，原因不是“细节不够多”，而是没有完成用户要求的源码审计，并把若干尚未核查的实现语义直接写成了数学事实。本版本从上传的源码归档重新审计后，得到以下结论。

### 已经能够从实际代码确认的事实

1. **当前 MAP-anchor-only 不是 materialization-aware VOI planner。**  
   它是一个 deterministic component/diversity heuristic：
   - 用 proxy 的 0.70 quantile 建 high-proxy islands；
   - 加入未覆盖 local peaks；
   - 每 60 秒加入一个 audit representative；
   - 使用固定的 80/20 或 70/30 anchor/audit quota；
   - query score 不调用 materializer，也不计算 event-risk counterfactual。

2. **Stage 0.7 的 K3 实际语义比设计文档更窄。**  
   K3 使用：
   - queried positive units 作为 anchors；
   - 相邻 anchors 之间至多允许 1 个 unit gap；
   - 从当前 group 第一个 anchor 到新 anchor 的 span 不超过 40 秒；
   - 两个连续 anchors 之间不得存在 queried negative；
   - 输出 group 首尾之间的全部 contiguous units。

3. **`D_seg_max = 60s` 在 K3 路径中没有独立作用。**  
   K3 没有 selected expansion；60 秒 segment cap 只在 K4 expansion 中检查。K3 的输出因为 40 秒 core cap 而自然不超过 40 秒。论文不能把“40 秒 core cap + 60 秒 segment cap”同时表述为 K3 中两个独立生效的机制。

4. **queried negative 的 hard-barrier 语义在 Stage 0.7 K3 中成立，但范围有限。**  
   它只阻止两个 queried-positive anchors 跨越位于它们之间的 negative unit 合并。孤立 positive anchor 周围的 boundary negative 不会改变 K3 输出，因为 K3 本身不扩边界。

5. **clean benchmark 的 `original_k3`、`k3_bridge_safe` 和正式 event matching 核心函数无法从本次归档完全审计。**  
   `run_clean_benchmark.py` 从缺失的 `benchmark_lib.py` 导入：
   - `materialize_from_trace`；
   - `evaluate_events`；
   - `canonicalize_native_segments`。
   因而本版本不能猜测 M0 original K3 与 M1 bridge-safe 的精确差异，也不能声称 clean benchmark 的 matcher 与某个公式完全一致。

6. **归档内另一个 matcher 与文档声明并不相同。**  
   `latent_event_diag/evaluation.py` 用 Hungarian algorithm 最大化总 temporal IoU，然后删除零 IoU pairs；这不必然首先最大化 `overlap_any` matching cardinality。clean benchmark manifest 声称的是“cardinality first, tIoU tie-break”，但其实际 helper 缺失。两者必须分开记录。

7. **oracle 在线可访问性目前主要由代码约定而非接口隔离保证。**  
   clean benchmark 的 `OracleAccessor` 正确实施 duplicate/budget checks；但 `map_order` 把所有 `oracle_label` 放入 DataFrame 后调用 `simulate_map`。当前路径确实在选择 unit 后才索引 label，但函数拥有完整 label table，静态上仍存在未来修改造成 leakage 的风险。BCM 实现必须只接收 public table，并通过 `OracleAccessor.query` 获取 observation。

8. **当前 oracle 数据接口不是严格二元。**  
   frozen cache 含 `positive / negative / abstain`；MAP 和 adapter 构造时把 `abstain` 映射为 0。若 benchmark 中存在 abstain，这与“exact binary oracle”建模前提不一致。实现前必须确认 abstain 数量为 0，或把 abstain 作为第三种 observation outcome，不得静默当作 negative。

### 数学上真正成立的三层结构

- **Layer A — Normative optimal model:** 对 latent event relation 的 Bayes-optimal finite-budget sequential decision process。它是理论基准，通常不可计算。
- **Layer B — Tractable event-risk surrogate:** 只使用 cheap features 和已查询 observations 的结构风险；它不是 event-F1 本身。
- **Layer C — Implementable BCM-AQP:** 对每个候选 query 模拟 binary positive/negative state transition，重新计算 surrogate risk，再做 deterministic greedy selection。它目前只能称为 engineering heuristic，除非跨视频 calibration、regret 和 theory gates 通过。

### 当前最重要的数学结论

1. Bayes-optimal VOI 在期望意义下非负；但某个具体 outcome 后的 conditional Bayes risk 可以高于 query 前风险，不能作逐 outcome 的错误比较。
2. 固定 materializer 下的 expected utility 可以为负。Stage 0.7 K3 存在“新增 positive anchor 把两个正确事件连成一个长 event”的最小反例。
3. unit-level positive-probability ranking 的 unique-event recovery 最坏可只有 event-aware policy 的 `1/B`。
4. negative query 可在 Stage 0.7 K3 中具有直接任务价值：一个低 positive-probability gap query 返回 negative 后可把一个错误 merged event 分成两个正确 events。
5. candidate ceiling 只能上界 **evidence-certified event recall**。在宽松 `overlap_any` 下，长 segment 可能偶然覆盖没有任何 queried trigger 的 event，因此 raw overlap_any recall 不满足该 bound，除非额外假设 materializer evidence-faithful。
6. 当前 event-risk objective 一般不满足 submodularity；merge/split/boundary query 存在 complementarity。不得声称 greedy approximation ratio。
7. residual event-count certificate 需要唯一 canonical anchor、独立 audit stream 和已知 inclusion probabilities。缺任一条件只能称 empirical audit。

## 1.2 对 Codex 的直接结论

Codex 现在可以安全实现：

- public-only candidate/hypothesis construction；
- exact `OracleAccessor`-mediated query loop；
- Stage 0.7 K3 的 audited adapter；
- reference-free structural surrogate；
- binary counterfactual state copies；
- deterministic score/tie-break/cache/trace；
- candidate/materializer ceiling diagnostics；
- synthetic tests in Section 22。

Codex 现在**不能**安全声称或默认实现：

- existing `k3_bridge_safe` semantics；
- actor identity inference from binary labels；
- event completeness guarantee；
- submodular greedy guarantee；
- exact event-F1 VOI；
- abstain-as-negative correctness；
- current clean benchmark matcher semantics without `benchmark_lib.py`。

---

# 2. Scope and Non-Claims

## 2.1 Scope

This document specifies a mathematically disciplined candidate algorithm, **BCM-AQP**, for a frozen event-level video AQP benchmark. It separates normative theory from approximations and from current code behavior.

The online system receives:

- a temporally ordered public unit table;
- cheap features and proxy scores;
- an expensive oracle accessible only through a budgeted interface;
- a frozen materializer configuration;
- no evaluator reference relation.

The evaluator alone receives the complete event reference relation.

## 2.2 Non-claims

The following are **NOT PROVEN** or not yet supported:

- BCM-AQP is Bayes optimal;
- the structural surrogate is calibrated to event-F1;
- the greedy policy has a constant-factor approximation ratio;
- event-risk reduction is adaptive submodular;
- the current binary oracle identifies actor identity or event multiplicity;
- the clean benchmark `k3_bridge_safe` semantics have been audited from source;
- a statistical event-recall certificate exists;
- single-video VLM-relative results generalize to human-adjudicated cross-video settings.

## 2.3 Terminology status labels

Every formal statement is labeled as one of:

- **Definition**
- **Assumption**
- **Lemma**
- **Proposition**
- **Theorem**
- **Corollary**
- **Approximation**
- **Engineering heuristic**
- **Empirical hypothesis**
- **Open problem**
- **NOT PROVEN**

---

# 3. Audited Current-System Semantics

## 3.1 Audit corpus

The audit used the uploaded archive containing the prioritized design documents and the following code paths:

- `scripts/stage0_7_minimal_operator_compression.py`
- `scripts/stage1a_map_anchor_only.py`
- `scripts/stage1b_map_anchor_barrier.py`
- `src/garc_eval/latent_event_diag/oracles.py`
- `src/garc_eval/latent_event_diag/planners/policies.py`
- `src/garc_eval/latent_event_diag/materializers/simple.py`
- `src/garc_eval/latent_event_diag/materializers/k3_adapter.py`
- `src/garc_eval/latent_event_diag/evaluation.py`
- `src/garc_eval/latent_event_diag/experiment.py`
- `agent_run/clean_baseline_benchmark_v1/scripts/run_clean_benchmark.py`

The archive does **not** contain:

- `benchmark_lib.py`, imported by `run_clean_benchmark.py`;
- `latent_event_diag/models.py`;
- `latent_event_diag/planners/base.py`;
- the frozen CSV artifacts and action traces themselves.

Therefore exact source audit of the clean benchmark materializer and matcher is blocked.

## 3.2 Current implementation fact table

| Topic | Audited implementation fact | Mathematical consequence |
|---|---|---|
| OracleAccessor | Rejects duplicate unit queries and queries beyond integer budget; returns one frozen cache row. | A correct Layer-C implementation should route all actual observations through this interface. |
| Oracle outcomes | Cache schema supports positive/negative/abstain; some MAP/adapter paths map abstain to 0. | Exact binary model requires zero abstains or explicit third outcome. |
| MAP component construction | Proxy q0.70 islands, uncovered local peaks, one representative per 60s window. | Current candidate generator is an engineering heuristic, not an event posterior. |
| MAP allocation | Fixed 80/20 anchor/audit for `B<=20`, 70/30 otherwise; audit may preempt if score exceeds anchor score by factor 120. | Current MAP is not a VOI optimizer and contains pilot-selected constants. |
| MAP score | Uses proxy statistics, query distance and nearby query count. | It does not model downstream materialization quality. |
| K3 anchors | Every queried unit with `oracle_label==1`. | Multiple positives from one event can be double-counted until merge prior groups them. |
| K3 barrier | Any queried negative strictly between consecutive positive anchors blocks their merge. | Negative evidence has partition value, but only inside an anchor gap. |
| K3 gap | At most one unqueried unit between consecutive anchors. | `G_max=1` is a frozen engineering prior. |
| K3 duration | Proposed first-anchor-to-new-anchor contiguous span must be <=40s. | K3 segment duration is bounded by 40s under ordered 10s units. |
| K3 segment cap | 60s cap is checked only in K4 selected expansion, not K3. | Do not present 60s as an independently active K3 invariant. |
| K3 event identity | Connected components under gap/duration/barrier rules. | Event partition is imposed by a deterministic prior, not identified by the binary oracle. |
| K3 bridge-safe | Actual helper absent from archive. | Exact M0/M1 difference is **NOT AUDITED**. |
| Latent diagnostic matcher | Hungarian assignment maximizing sum IoU, then keep IoU>0. | Not equivalent in general to maximum overlap-cardinality first. |
| Clean matcher | Manifest states overlap-cardinality then tIoU; helper missing. | Exact clean matching semantics are **NOT AUDITED**. |
| AUC | Normalized trapezoid over fixed budgets `[5,10,20,50,80,100]`; no B=0 point. | AUC depends on this budget grid and weights large budget intervals more heavily. |
| Trace replay | Wrapper saves unit/action/outcome trace and rematerializes every prefix. | Same acquisition trace can compare materializers if helper semantics are frozen. |

## 3.3 Document–code discrepancies requiring explicit tracking

1. **Design documents:** K3 has core cap 40s and segment cap 60s.  
   **Code:** K3 uses only the 40s check; 60s is unreachable without K4 expansion.

2. **Design language:** MAP is materialization-aware.  
   **Code:** Stage 1A never invokes K3 or an event-risk surrogate during query selection.

3. **Model premise:** exact binary oracle.  
   **Code:** abstain exists and may be mapped to negative.

4. **Online-access contract:** planner only sees queried labels.  
   **Code:** `simulate_map` receives a DataFrame containing all labels, although it indexes the selected label only after selection.

5. **Clean matcher description:** cardinality-first overlap matching.  
   **Available code:** a different diagnostic matcher maximizes total IoU; clean helper is missing.

6. **Target event schema:** actor-centric event relation.  
   **Current benchmark:** reference events are formed from consecutive positive units; current K3 outputs temporal intervals without actor/type identity.

## 3.4 Required audit before finalizing this reference as code-complete

**BLOCKING REQUIREMENT:** provide and audit `benchmark_lib.py`, or the exact files defining:

- `materialize_from_trace(..., "original_k3", ...)`;
- `materialize_from_trace(..., "k3_bridge_safe", ...)`;
- `evaluate_events(...)`;
- event-match tie breaking;
- canonicalization of native segments.

Until then, Sections 13–14 formalize the fully audited Stage 0.7 K3, not the unaudited clean-benchmark bridge-safe variant.

---

# 4. Notation

## 4.1 Units and public features

**Definition 4.1 (Atomic unit).**

Let

\[
U=\{u_1,\ldots,u_N\}
\]

be temporally ordered units. Each unit is

\[
u_i=(i,t_i^s,t_i^e,x_i),
\]

where `i` is the stable unit index, `[t_i^s,t_i^e)` is its half-open temporal interval, and `x_i` contains only public cheap features.

**Assumption A1 (Temporal index order).**

\[
i<j\implies t_i^s\le t_j^s.
\]

The audited K3 implementation uses integer index gaps, so this assumption is required.

## 4.2 Oracle variables

**Definition 4.2 (Exact unit predicate).**

The idealized binary oracle variable is

\[
Y_i=O(u_i)\in\{0,1\}.
\]

`Y_i=1` means that unit `u_i` contains evidence satisfying the benchmark predicate. It does **not** by itself identify event identity, actor identity, multiplicity, or boundaries.

**Assumption A2 (Correctness on query).**

When queried, the oracle returns the realized value of `Y_i` without classification error.

**Implementation precondition A2-I.**

If the physical cache contains `abstain`, then either:

1. no abstains occur in the frozen benchmark; or
2. the observation space is extended to `Y_i in {0,1,abstain}`.

Mapping abstain to zero is not justified by A2.

## 4.3 Histories and policies

**Definition 4.3 (History).**

At time `t`,

\[
H_t=(X,Q_t,Y_{Q_t},A_t),
\]

where `X={x_i}` is public, `Q_t` is the set or ordered sequence of queried units, `Y_{Q_t}` are observed outcomes, and `A_t` stores action types and costs.

**Definition 4.4 (Query policy).**

A policy `pi` maps history and remaining budget to either a feasible query or `STOP`:

\[
\pi(H_t,b_t)\in \mathcal Q(H_t)\cup\{STOP\}.
\]

The planner may not inspect `Y_i` for `i notin Q_t`.

## 4.4 Event relation

**Definition 4.5 (Target actor-centric event).**

The target schema is

\[
e=(event\_id,event\_type,actor\_id,support\_start,core\_start,
canonical\_anchor,core\_end,support\_end).
\]

Let the latent event relation be

\[
Z=E^\star=\{e_1,\ldots,e_M\}.
\]

## 4.5 Current implementable event schema

The audited Stage 0.7 K3 can only materialize

\[
\hat e=(start,end,positive\_anchor\_ids,source\_unit\_ids,confidence\_heuristic).
\]

It does not infer actor, type, core/support distinction, or canonical anchor.

## 4.6 Unit-to-event incidence

**Definition 4.6 (Evidence incidence).**

Let

\[
A_{ie}\in\{0,1\}
\]

indicate that unit `u_i` carries oracle-positive evidence for event `e` under the event schema.

A binary presence oracle is compatible with

\[
Y_i=\mathbf 1\left[\sum_{e\in E^\star}A_{ie}>0\right].
\]

This mapping is many-to-one. Different event relations can induce the same complete binary vector `Y`.

## 4.7 Loss

**Definition 4.7 (Event-level loss).**

Let

\[
L_{event}(\hat E,Z)\ge0
\]

be a frozen event-level loss. It may combine one-to-one detection loss, boundary error, duplicate/overmerge penalties and review cost. The evaluator reference `Z` is never available to the planner.

---

# 5. Formal Event-AQP Problem

## 5.1 Problem definition

**Definition 5.1 (Budgeted event-level AQP).**

Given public units `U`, features `X`, oracle variables `Y`, query costs `c(q)>0`, budget `B`, and materializer/terminal decision rules, choose a sequential policy `pi` and terminal EventRelation `Ehat` to minimize

\[
\mathbb E[L_{event}(\hat E,Z)]
\]

subject to

\[
\sum_{t} c(q_t)\le B.
\]

## 5.2 Why binary oracle correctness is insufficient for event semantics

**Proposition 5.1 (Non-identifiability from binary unit labels).**

Even with all `Y_1,...,Y_N` known exactly, event identity and partition are not identifiable without additional event semantics or structural assumptions.

### Assumptions

None beyond Definition 4.6.

### Proof by construction

Consider two adjacent positive units `u_1,u_2`, so `Y=(1,1)`. Both latent relations below induce the same labels:

- `Z_A`: one event spanning both units;
- `Z_B`: two distinct events, one per unit.

Therefore `Y` does not identify the partition. Similar constructions show boundary and actor identity are not identified.

### Applicability to current implementation

Current K3 resolves this ambiguity using gap, duration and negative-barrier priors. These are materializer semantics, not consequences of oracle correctness.

### Failure conditions

If the oracle returns an event identifier or a same/distinct relation, the ambiguity may be reduced.

### Corresponding unit test

Synthetic tests 2 and 3.

## 5.3 Event semantics contract required by any implementation

A complete system must specify at least one of:

1. **Rich oracle contract:** observations include event identity/relation/boundary attributes;
2. **Generative event model:** a probabilistic model links events to unit observations;
3. **Deterministic materialization prior:** e.g. K3 connected components;
4. **Human-adjudicated reference semantics:** used only by evaluator, not planner.

BCM-AQP v1 uses (3) for output and an approximate version of (2) for query scoring.

---

# 6. Oracle and Event-Semantics Contract

## 6.1 Online-access contract

**Definition 6.1 (Legal planner view).**

At step `t`, the planner may access:

- public unit rows and cheap features;
- observations returned for `Q_t`;
- deterministic state derived from those values;
- frozen hyperparameters.

It may not access:

- unqueried oracle labels;
- evaluator event IDs, event boundaries or canonical anchors;
- future trace rows;
- per-budget decisions selected using evaluator metrics.

## 6.2 Required OracleAccessor API

```text
query(unit_id, remaining_budget) -> OracleObservation
```

Required checks:

- `unit_id` has not previously been queried;
- cost is feasible;
- outcome is returned only after the selected action is committed;
- observation is appended to immutable trace;
- no method receives a full label-bearing DataFrame.

## 6.3 Current-code warning

The audited `OracleAccessor` enforces duplicate and budget checks. However the clean MAP wrapper constructs a full `oracle_label` column before calling `simulate_map`. The present function happens to select before indexing that label, but BCM must remove this ambient access rather than rely on discipline.

## 6.4 Reference semantics

The current clean benchmark reference is VLM-defined and constructed from consecutive positive units, using VLM-provided absolute event boundaries when available. This is a benchmark construction rule, not an actor-centric event ontology.

---

# 7. Layer A — Optimal Finite-Budget Policy

## 7.1 Terminal Bayes risk

**Definition 7.1 (Bayes terminal risk).**

For history `H`,

\[
R^\star(H)
=
\inf_{\hat E\in\mathcal D(H)}
\mathbb E[L_{event}(\hat E,Z)\mid H],
\]

where `D(H)` is the allowed terminal decision set.

Equivalently,

\[
J_0(H)=R^\star(H).
\]

## 7.2 Bellman recursion

**Theorem 7.1 (Finite-budget Bellman equation).**

For remaining budget `b>=0`,

\[
J_b(H)=
\min\left\{
R^\star(H),
\inf_{q\in\mathcal Q(H):c(q)\le b}
\sum_{y\in\mathcal Y_q}
P(Y_q=y\mid H)
J_{b-c(q)}(H\oplus(q,y))
\right\}.
\]

### Assumptions

- finite or measurable action/outcome spaces;
- posterior and conditional expectations exist;
- terminal loss is integrable;
- query costs are known.

### Proof

The first action is either `STOP`, incurring optimal terminal risk, or a feasible query `q`. Conditional on its outcome, the remaining problem has the same form with updated history and budget. The principle of optimality gives the recursion.

### Applicability

This is the normative model. It is not directly computable in the current system because the posterior over event relations and future observation outcomes is unavailable.

### Failure conditions

Non-stationary or path-dependent physical costs must be included in `H`; otherwise the recursion is misspecified.

### Unit test

A tiny two-unit exhaustive dynamic-programming test can compare recursion to enumeration.

## 7.3 Equal-cost and unequal-cost queries

**Corollary 7.1 (Last equal-cost query).**

If one unit of budget remains and all queries cost one, the optimal query maximizes one-step Bayes VOI.

For more than one remaining query, selecting the maximum one-step VOI need not be optimal because future query complementarity matters.

For unequal costs, the Bellman rule minimizes expected continuation risk among feasible actions. `VOI/cost` is generally **not** Bellman optimal.

## 7.4 Lagrangian anytime formulation

**Definition 7.2 (Query-cost Lagrangian).**

For `lambda_q>0`,

\[
V_{\lambda_q}(H)=
\min\left\{
R^\star(H),
\inf_q\left[
\lambda_q c(q)+
\mathbb E[V_{\lambda_q}(H\oplus(q,Y_q))\mid H]
\right]
\right\}.
\]

This supplies an optimal stopping action under the specified prior and loss.

## 7.5 When VOI/cost is only a heuristic

**Engineering heuristic 7.1.**

\[
q_t=\arg\max_q \frac{VOI(q\mid H_t)}{c(q)}
\]

is a myopic density rule. It is justified only under restrictive conditions such as a one-step decision, additive independent gains with fractional selection, or an explicit approximation theorem. None is currently established for event merge/split dynamics.

---

# 8. Bayes Value of Information

## 8.1 Definition

**Definition 8.1 (Bayes VOI).**

\[
VOI^\star(q\mid H)
=
R^\star(H)
-
\sum_yP(Y_q=y\mid H)R^\star(H\oplus(q,y)).
\]

## 8.2 Non-negativity

**Theorem 8.1 (Expected Bayes VOI is non-negative).**

\[
VOI^\star(q\mid H)\ge0.
\]

### Assumptions

The pre-query Bayes-optimal decision is still available after the observation.

### Proof

Let `d_H` be a Bayes-optimal terminal decision before query `q`. For each outcome `y`, the post-observation Bayes decision may choose any action available before, including `d_H`. Hence

\[
R^\star(H\oplus(q,y))
\le
\mathbb E[L_{event}(d_H,Z)\mid H,Y_q=y].
\]

Taking expectation over `Y_q` conditional on `H`,

\[
\sum_yP(y\mid H)R^\star(H\oplus(q,y))
\le
\mathbb E[L_{event}(d_H,Z)\mid H]
=R^\star(H).
\]

Subtracting proves the claim.

### Important correction

It is **not** generally true that

\[
R^\star(H\oplus(q,y))\le R^\star(H)
\]

for every individual outcome `y`. A surprising outcome can raise conditional risk; only the expectation is guaranteed not to increase.

### Applicability

This theorem concerns Bayes-optimal terminal decisions, not fixed K3 or a surrogate.

### Failure conditions

If receiving an observation forces an irreversible output rule and the old decision cannot be retained, the assumption fails.

### Unit test

An exhaustive finite latent-state test should verify non-negative expected VOI while allowing one outcome to have larger conditional risk.


---

# 9. Materializer-Conditioned Counterfactual Utility

## 9.1 Fixed-materializer risk

**Definition 9.1.** For a deterministic materializer `M`,

\[
R_M(H)=\mathbb E[L_{event}(M(H),Z)\mid H].
\]

Define its one-step expected risk reduction:

\[
\Delta_M(q\mid H)
=
R_M(H)
-
\sum_yP(Y_q=y\mid H)R_M(H\oplus(q,y)).
\]

## 9.2 Non-monotonicity

**Proposition 9.1 (Fixed-materializer utility can be negative).**

There exist an event relation, a history, and a correct query for which

\[
\Delta_M(q\mid H)<0.
\]

### Assumptions

- `M` is the audited Stage 0.7 K3;
- `G_max=1` unit and `D_core_max=40s`;
- loss is `1-event_F1` under one-to-one overlap matching.

### Construction

Use four 10-second units `u_0,...,u_3` and two true events:

- `e_A=[0,20)`;
- `e_B=[30,40)`.

History contains positive anchors at units 0 and 3. Since two units lie between them, K3 creates two predicted events and achieves F1=1.

Query `q=u_1`. Let the accurate outcome be positive because `u_1` belongs to `e_A`. The positive anchors become `{0,1,3}`. K3 merges `0` with `1`, then merges `3` because only unit 2 lies between anchors 1 and 3 and the total span is 40 seconds. It outputs one segment `[0,40)`. One-to-one matching can match only one of the two truths, so precision=1, recall=1/2 and F1=2/3.

Thus risk rises from 0 to 1/3 and `Delta_M=-1/3` when this outcome is certain.

### Applicability

This counterexample applies to the audited Stage 0.7 K3. It is precisely why a counterfactual planner must simulate output changes rather than treat every likely positive as beneficial.

### Failure conditions

A bridge-safe materializer that forbids this action-conditioned destructive merge may remove this example, but its actual source is absent and **NOT AUDITED**.

### Unit test

Synthetic test 4B in Section 22.

## 9.3 Distinguishing three quantities

The following must never be conflated:

1. **Bayes VOI** `VOI*`: expected reduction under a Bayes-optimal terminal decision; non-negative.
2. **Materializer-conditioned utility** `Delta_M`: expected reduction for a fixed materializer; may be negative.
3. **Engineering surrogate score** `Score_tilde`: change in a reference-free structural surrogate; may disagree with true event loss in either direction.

## 9.4 Implementable counterfactual score

For a binary query,

\[
Score(q\mid H)
=
\widetilde R(H)
-
\left[
\hat p_q(H)\widetilde R(T(H,q,1))
+(1-\hat p_q(H))\widetilde R(T(H,q,0))
\right],
\]

where:

- `T` is an approximate state transition;
- `p_hat_q` is estimated without unqueried labels;
- `R_tilde` is the structural surrogate below.

**Engineering heuristic 9.1 (Cost normalization).**

For heterogeneous query costs, BCM may rank

\[
Score_c(q\mid H)=\frac{Score(q\mid H)}{c(q)}.
\]

This is a greedy heuristic, not a Bellman-optimal rule. A query with negative score must not be selected unless a separate forced-audit policy requires it.

---

# 10. Layer B — Tractable Structural-Risk Surrogate

## 10.1 Requirements

The surrogate must:

- be computable from public features and queried observations only;
- be deterministic for fixed state/config;
- not use event reference IDs, boundaries, matches or evaluation metrics;
- have bounded, normalized terms;
- explicitly represent uncertainty about existence, partition, boundary and residual unseen mass;
- avoid treating unqueried units as negatives.

Define

\[
\widetilde R(H)
=
\lambda_{exist}R_{exist}(H)
+
\lambda_{partition}R_{partition}(H)
+
\lambda_{boundary}R_{boundary}(H)
+
\lambda_{residual}R_{residual}(H),
\]

with non-negative weights summing to one.

## 10.2 Event-existence uncertainty

### Random variable

For each provisional hypothesis `h`, let

\[
Z_h\in\{0,1\}
\]

indicate whether the hypothesis corresponds to at least one true event.

Let

\[
p_h=P(Z_h=1\mid H).
\]

### Risk term

Using binary entropy `h_2(p)=-p log_2 p-(1-p)log_2(1-p)`, define

\[
R_{exist}(H)
=
\frac{\sum_h w_h h_2(p_h)}{\sum_h w_h},
\]

with the convention zero if no hypotheses exist.

### Range

\[
0\le R_{exist}\le1.
\]

### Calculation

`p_h` may be initialized from a model trained on separate development videos or from a preregistered calibration table over public component features. It is updated only from queried observations.

### Calibration requirement

Reliability diagrams, Brier score and expected calibration error must be evaluated on held-out videos. Pilot event labels may not be used to tune `p_h` for the frozen test.

### Independence assumption

No independence is required merely to compute entropy of each marginal, but the sum is not the joint entropy. It is an approximation.

### Duplicate risk

Two hypotheses for one event can double-count uncertainty. BCM v1 must assign every initial unit to at most one owner hypothesis and maintain explicit relation edges for possible duplicates. The existence sum alone is not an event-count estimator.

### Status

**Approximation.**

## 10.3 Same-event/distinct-event partition uncertainty

### Random variable

For each ambiguous neighboring hypothesis pair `(h,k)`, let

\[
S_{hk}\in\{same,distinct\},
\qquad s_{hk}=P(S_{hk}=same\mid H).
\]

### Risk term

\[
R_{partition}(H)
=
\frac{\sum_{(h,k)\in\mathcal E_t}w_{hk}h_2(s_{hk})}
{\sum_{(h,k)\in\mathcal E_t}w_{hk}}.
\]

### Range

`[0,1]`.

### Calculation

The current binary oracle has no direct same/distinct response. Therefore `s_hk` must come from a calibrated temporal/actor model or a frozen heuristic based on:

- anchor separation;
- negative barriers;
- public actor/track continuity if available;
- action-conditioned evidence.

In CSV-only BCM v1, actor evidence is unavailable. The only hard update supported by the audited K3 is:

\[
q\text{ between }h,k,\;Y_q=0
\implies s_{hk}=0
\]

for materialization purposes.

A positive gap observation must **not** automatically imply `same`; it may belong to the left event, right event, or a third event.

### Independence assumption

Pairwise marginals need not form a globally consistent partition. Enforcing transitivity requires a correlation-clustering or partition posterior model, absent in v1.

### Double counting

A chain of three hypotheses contributes multiple pair edges. Normalize by total edge weight and report edge count. Do not interpret this as number of uncertain events.

### Status

**Approximation; actor-free v1 is weak.**

## 10.4 Boundary uncertainty

### Random variables

For each existing hypothesis `h`, let discrete endpoint variables be

\[
L_h\in\mathcal L_h,
\qquad R_h\in\mathcal R_h.
\]

### Entropy version

\[
R_{boundary}(H)
=
\frac{1}{2\sum_hw_h}
\sum_hw_h
\left[
\frac{H(L_h)}{\log_2\max(2,|\mathcal L_h|)}
+
\frac{H(R_h)}{\log_2\max(2,|\mathcal R_h|)}
\right].
\]

### Range

`[0,1]`.

### Current implementability

K3 does not probe or expand boundaries. For current BCM v1, endpoint supports may be defined as bounded neighborhoods around anchor components, and negative observations may truncate supports. This term is meaningful only if `REFINE_BOUNDARY` actions are enabled.

### Alternative width heuristic

If endpoint distributions are unavailable,

\[
R_{boundary}^{width}
=
\frac{1}{2|H|}
\sum_h
\left[
\frac{|\mathcal L_h|-1}{N-1}
+
\frac{|\mathcal R_h|-1}{N-1}
\right].
\]

This is an engineering heuristic, not posterior entropy.

### Status

**Approximation; disabled by default in anchor-only BCM v1.**

## 10.5 Residual unseen-event mass

### Random variable

Partition the timeline into preregistered audit cells `c in C_t`. Let

\[
M_c\in\{0,1\}
\]

indicate that cell `c` contains the canonical anchor of at least one event not represented by current hypotheses.

Let

\[
m_c=P(M_c=1\mid H).
\]

### Risk term

\[
R_{residual}(H)
=
\frac{\sum_c v_c m_c}{\sum_c v_c}.
\]

### Calculation

Before an independent audit estimator exists, `m_c` may use:

- a separately trained audit calibration model;
- online Beta-Bernoulli updates from dedicated audit queries;
- a preregistered public coverage prior.

Using the same proxy that generated candidate hypotheses can create zero-proxy lockout. A nonzero exploration floor is required.

### Range

`[0,1]`.

### Independence assumption

The marginal average does not require cell independence. Any confidence interval does.

### Event duplication

If a cell can contain multiple canonical anchors, `M_c` measures presence, not event count. Residual count estimation then requires a count variable.

### Status

**Empirical hypothesis until independent audit calibration.**

## 10.6 Weight selection

Weights may be set only by:

1. frozen development videos;
2. separate training videos;
3. preregistered no-training defaults;
4. online Bayesian updates using queried observations, if the update rule is frozen;
5. sensitivity analysis reported without selecting the best test result.

They may not be tuned from current test reference labels.

### Recommended no-training default for initial implementation

For anchor/audit-only BCM v1:

\[
(\lambda_{exist},\lambda_{partition},\lambda_{boundary},\lambda_{residual})
=(0.45,0.20,0.00,0.35).
\]

This is a preregistered engineering default, not a theorem. Boundary weight remains zero until boundary actions exist.

## 10.7 Surrogate validity tests

Before using the surrogate for a paper claim, report on held-out videos:

- Spearman correlation between predicted score and realized one-step event-loss reduction;
- top-k query regret against an evaluator-only oracle-informed one-step planner;
- calibration of `p_q`;
- prior-wrong stress tests;
- frequency of negative realized materializer utility among queries with positive surrogate score.

---

# 11. Latent Event-Hypothesis State

## 11.1 Minimal hypothesis state

**Definition 11.1 (EventHypothesis).**

Each hypothesis `h` contains:

```text
hypothesis_id
owner_unit_ids
seed_unit_id
existence_probability p_h
anchor_probability_by_unit
left_endpoint_distribution or support
right_endpoint_distribution or support
queried_positive_ids
queried_negative_ids
verification_state
materialized_event_id optional
```

## 11.2 Relation state

**Definition 11.2 (RelationEdge).**

```text
src_hypothesis_id
dst_hypothesis_id
same_event_probability
relation_state: unresolved / hard_distinct / confirmed_same / competing
supporting_observation_ids
```

Current binary BCM v1 should use only `unresolved` and `hard_distinct`; `confirmed_same` requires a richer relation oracle or an audited bridge rule.

## 11.3 Exact generative observation model

A possible latent model is a noisy-OR:

\[
P(Y_q=0\mid Z_1,\ldots,Z_H)
=(1-b_q)\prod_h(1-a_{hq})^{Z_h},
\]

where:

- `a_hq` is the probability that existing event `h` makes unit `q` positive;
- `b_q` is background positive probability.

Exact posterior inference is exponential in the number of overlapping hypotheses.

## 11.4 Mean-field posterior update

**Approximation 11.1.** Maintain independent marginals `p_h`.

Let

\[
C_{-h,q}=(1-b_q)\prod_{k\ne h}(1-a_{kq}p_k).
\]

For a negative outcome:

\[
p_h'
=
\frac{p_h(1-a_{hq})}{1-a_{hq}p_h}.
\]

For a positive outcome:

\[
p_h'
=
\frac{p_h[1-C_{-h,q}(1-a_{hq})]}
{p_h[1-C_{-h,q}(1-a_{hq})]+(1-p_h)[1-C_{-h,q}]}.
\]

### Assumptions

- mean-field independence of other hypothesis indicators;
- calibrated `a_hq,b_q`;
- noisy-OR observation model.

### Status

**Approximation, not theorem about the real benchmark.**

## 11.5 Simpler single-owner update for BCM v1

When every query unit has one owner hypothesis `h(q)`, use likelihoods:

\[
a_q=P(Y_q=1\mid Z_h=1),\qquad b_q=P(Y_q=1\mid Z_h=0).
\]

Then standard Bernoulli Bayes updates apply:

\[
p_h'=
\frac{a_qp_h}{a_qp_h+b_q(1-p_h)}\quad (Y_q=1),
\]

\[
p_h'=
\frac{(1-a_q)p_h}{(1-a_q)p_h+(1-b_q)(1-p_h)}\quad (Y_q=0).
\]

This is implementable if `a_q,b_q` are frozen from separate calibration data.

## 11.6 Multiple positive units from one event

To avoid counting one event repeatedly:

- positive observations inside the same owner hypothesis update its evidence and posterior;
- existence utility saturates at the hypothesis level;
- a second positive does not create a new hypothesis unless it lies outside all existing ownership regions;
- materialization may use multiple anchors without adding multiple existence masses.

## 11.7 Adjacent distinct events

Adjacent hypotheses remain separate until explicit same-event evidence exists. A temporal gap prior may raise `s_hk`, but a positive gap observation alone cannot force same-event status.

## 11.8 Negative observations

A queried negative may have three action-conditioned effects:

1. **Core negative:** decreases hypothesis existence probability.
2. **Boundary negative:** truncates endpoint support.
3. **Gap negative:** sets a hard distinct/barrier relation between adjacent hypotheses.

The action type must be stored in history. The same binary value has different structural meaning depending on target selection.

## 11.9 Unqueried is not negative

For any unit `q notin Q_t`, no hard barrier or exclusion may be created. It retains prior uncertainty. This is a mandatory invariant.

---

# 12. Region and Typed-Action Selection

## 12.1 Dynamic region family

**Definition 12.1.** At time `t`, define

\[
\mathcal R_t=
\mathcal R_t^{core}
\cup\mathcal R_t^{anchor}
\cup\mathcal R_t^{gap}
\cup\mathcal R_t^{boundary}
\cup\mathcal R_t^{audit}.
\]

- candidate core regions;
- anchor neighborhoods;
- uncertain inter-hypothesis gaps;
- uncertain boundaries;
- uncovered audit cells.

## 12.2 Unified actions

| Action | Region | Intended uncertainty reduction |
|---|---|---|
| `DISCOVER_CORE` | candidate core | existence / distinct-event coverage |
| `PROBE_STRUCTURE` | uncertain gap or relation | partition / overmerge risk |
| `REFINE_BOUNDARY` | endpoint neighborhood | boundary uncertainty |
| `AUDIT_UNCOVERED` | uncovered cell | residual unseen-event mass |

## 12.3 Region value

For a single next query,

\[
V(R\mid H)=\max_{q\in R\setminus Q_t}Score(q\mid H).
\]

The planner selects the best query across all regions:

\[
q_t=\arg\max_{R\in\mathcal R_t}\;V(R\mid H_t).
\]

No fixed 80/20 or 70/30 allocation is part of BCM. Those ratios remain MAP baselines.

## 12.4 Candidate deduplication

The same unit can be proposed by multiple action generators. BCM treats `(action_type,unit_id)` as the action identity because counterfactual semantics differ by action. It must nevertheless prevent duplicate physical oracle calls. If two actions target the same unit, select one action semantics before querying and store the chosen action type.

## 12.5 Outcome-probability estimation

`estimate_outcome_probability(q,H)` may use:

- separate-video logistic calibration;
- Beta-Bernoulli bins over action type, proxy quantile and region role;
- a preregistered monotone proxy map.

It may not use the unqueried label.

A no-training Beta-Bernoulli version stores, for bin `b`,

\[
\hat p_b=
\frac{\alpha_0+n_b^+}{\alpha_0+\beta_0+n_b^++n_b^-}.
\]

Online updates use only observations already obtained in the same run. A hierarchical prior is recommended because low budgets leave many bins empty.

## 12.6 Stop action

BCM stops when:

- no feasible unqueried candidate remains;
- remaining budget is below every candidate cost;
- maximum score is below a frozen threshold `epsilon_stop`;
- a separate mandatory audit budget must be preserved.

`epsilon_stop=0` is the safest initial default for a risk-reduction score.

---

# 13. Formal BB-EM/K3 Definition

## 13.1 Scope

This section formalizes **the audited Stage 0.7 K3** in `stage0_7_minimal_operator_compression.py`. It does not claim to formalize the unavailable clean-benchmark bridge-safe helper.

## 13.2 Inputs

Let:

\[
P_t=\{i:(i,1)\in H_t\}
\]

be queried positive unit indices and

\[
N_t=\{i:(i,0)\in H_t\}
\]

be queried negative unit indices.

Let frozen parameters be:

\[
G_{max}=1,\qquad D_{core}=40\text{s}.
\]

`D_seg=60s` is present in configuration but not used by K3.

## 13.3 Gap and duration functions

For anchors `i<j`,

\[
gap(i,j)=\max(0,j-i-1).
\]

For an interval of unit IDs `[a,b]`,

\[
duration(a,b)=
\max_{a\le k\le b}t_k^e-
\min_{a\le k\le b}t_k^s.
\]

Define hard barrier predicate

\[
Barrier(i,j;N_t)
=\mathbf 1[\exists n\in N_t:i<n<j].
\]

## 13.4 Sequential grouping algorithm

Sort positive anchors:

\[
p_1<\cdots<p_m.
\]

Initialize current group `G=[p_1]`. For each next anchor `p_j`, let `p_prev` be the last anchor in `G` and `p_first` the first. Merge `p_j` into `G` iff:

\[
gap(p_{prev},p_j)\le G_{max},
\]

\[
duration(p_{first},p_j)\le D_{core},
\]

and

\[
Barrier(p_{prev},p_j;N_t)=0.
\]

Otherwise close the group and start a new group at `p_j`.

## 13.5 Component-to-event conversion

For each anchor group with first/last indices `(a,b)`, K3 emits one event segment covering all extant units with IDs in `[a,b]`:

\[
\hat e=[\min_{a\le k\le b}t_k^s,
\max_{a\le k\le b}t_k^e).
\]

Thus unqueried units between anchors are included in the segment.

## 13.6 Tie breaking

- positive anchors are sorted by integer unit ID;
- no proxy score is used for materialization;
- event IDs follow group creation order;
- identical inputs produce identical output order.

## 13.7 M0 original K3 versus M1 bridge-safe

**Audit status: BLOCKED / NOT PROVEN.**

The clean benchmark wrapper invokes two variants through `benchmark_lib.materialize_from_trace`, but that file is absent from the archive. The wrapper provides only these facts:

- both variants use the same public config dictionary;
- the same action trace can be replayed under both;
- a sanity message asserts bridge-safe groups cannot be fewer than original groups;
- M1 is evaluated as the current method.

These wrapper facts are insufficient to derive the exact bridge rule. Codex must not implement a guessed bridge-safe variant from this document.

---

# 14. Materializer Invariants and Proofs

## 14.1 Positive-anchor coverage

**Theorem 14.1.** For every `p in P_t`, there exists an output event segment containing unit `p`.

### Assumptions

- `p` is a valid unit ID;
- oracle log has one consistent label per queried unit;
- K3 completes without data errors.

### Proof

Every positive anchor appears once in the sorted anchor list. The grouping loop either appends it to an existing group or starts a new group. Component conversion emits an interval from each group’s first to last anchor, which contains every group anchor.

### Applicability

Exact for Stage 0.7 K3.

### Failure conditions

Invalid IDs, conflicting duplicate observations, or later filtering outside K3.

### Unit test

Tests 1, 3, 4 and 5.

## 14.2 Queried-negative barrier safety

**Theorem 14.2.** No K3 output group contains a queried negative strictly between two consecutive positive anchors in that group.

### Proof

Before appending every new anchor, K3 checks the open interval between the previous anchor and new anchor. If a negative occurs there, it starts a new group. Any internal point of a multi-anchor group lies between some consecutive anchor pair. Therefore no internal queried negative exists.

### Applicability

Exact for Stage 0.7 K3.

### Limitations

- a negative outside the anchor span has no effect;
- a boundary negative does not shrink an isolated event because K3 does no expansion;
- this theorem does not specify bridge-safe behavior.

### Unit test

Tests 5 and 6.

## 14.3 Boundedness

**Theorem 14.3 (Core-span bound).** Every K3 output segment has duration at most 40 seconds.

### Assumptions

- temporal order agrees with unit ID;
- duration is computed from the same unit rows as output;
- no post-K3 expansion is applied.

### Proof

A group is extended only if the proposed first-to-new-anchor contiguous interval has duration at most `D_core=40s`. The final output interval is exactly that first-to-last-anchor interval.

### Corollary 14.3a

Every K3 output also satisfies the configured 60-second bound, but only because 40<=60. The 60-second rule is not independently exercised.

### Unit test

Test 10.

## 14.4 Determinism

**Theorem 14.4.** Fixed unit table, observation table, configuration and code version produce the same K3 EventRelation.

### Proof

All operations are deterministic sorts, set membership checks and arithmetic; no random state is used. Event ordering is determined by sorted anchors.

### Failure conditions

- duplicate conflicting rows;
- unstable external DataFrame serialization/type coercion;
- non-temporal unit IDs.

### Unit test

Test 11.

## 14.5 Idempotence

**NOT PROVEN / NOT WELL-DEFINED.**

The current function signature is

```text
M(UnitTable, ObservationTable, OriginalSegments, Config) -> EventRelation
```

and does not accept an EventRelation as input. Therefore `M(M(H))` is not type-correct. The relevant tested property should be **rerun stability**:

\[
M(H)=M(H)
\]

under identical serialized inputs, not algebraic idempotence.

To claim idempotence, define a canonical observation-compatible state extractor `C` and prove

\[
M(C(M(H),H))=M(H).
\]

No such extractor currently exists.

### Unit test

A serialization round-trip test may check rerun stability, not mathematical idempotence.

## 14.6 Direct time complexity

Let `P=|P_t|` and `N=|U|`.

The current pandas/Python implementation performs:

- sorting anchors: `O(P log P)`;
- for each anchor, constructing a contiguous ID list and scanning duration/gap: worst `O(N)`;
- total grouping: worst `O(PN)`;
- output interval construction: `O(N)` across disjoint groups in typical ordered data.

Worst case is `O(N^2)` when `P=Theta(N)`.

## 14.7 Optimized complexity

With:

- sorted anchor/negative sets;
- prefix count of queried negatives;
- endpoint arrays for interval duration;
- balanced search tree for local insertion;

merge eligibility becomes `O(1)` or `O(log N)` per adjacent anchor. Full materialization becomes

\[
O(P\log P+P+N_{out}).
\]

An incremental positive or negative observation can update neighboring groups in

\[
O(\log P+k),
\]

where `k` is the locally affected anchor span. Worst case remains linear if a change propagates through a long chain.

---

# 15. Propositions and Counterexamples

## 15.1 Proposition 1 — Record ranking can lose a factor `B`

**Proposition 15.1.** For any integer budget `B>=1`, there exists an instance where a unit-level top-positive-probability policy discovers one unique event while an event-aware policy discovers `B`, giving ratio `1/B`.

### Assumptions

- an event is discovered iff at least one unit in its trigger set is queried;
- top ranking does not diversify after observing positives;
- all query costs are one;
- event-aware policy knows the provisional grouping, not true labels.

### Construction

Create one event `e_0` with `B` units `a_1,...,a_B`, each assigned score `p_H`. Create `B` other events `e_1,...,e_B`, each with one candidate `b_j` assigned score `p_L`, where `p_H>p_L>0`. All units are truly positive.

Top ranking spends all `B` queries on `a_1,...,a_B`, discovering only `e_0`. An event-aware component-first policy queries `b_1,...,b_B`, discovering `B` events.

### Ratio

\[
\frac{1}{B}.
\]

### Applicability

This formalizes the motivation for component-first probing. It does not prove current MAP identifies true components.

### Failure conditions

A record policy that suppresses already-covered components is already event-aware and avoids the example.

### Unit test

Test 8.

## 15.2 Proposition 2 — A low-positive-probability negative query can improve event-F1

**Proposition 15.2.** Under audited K3, a query with very low `P(Y_q=1|H)` can have positive task value because a negative outcome prevents a false merge.

### Construction

Use three 10-second units:

- `u_0` positive anchor for true event `e_A=[0,10)`;
- `u_1` unqueried and truly negative;
- `u_2` positive anchor for true event `e_B=[20,30)`.

Before querying `u_1`, K3 merges anchors 0 and 2 because the gap is one unit and total duration is 30 seconds. It outputs one prediction, yielding precision=1, recall=1/2, F1=2/3.

After querying `u_1` and observing negative, the hard barrier splits the output into two predictions, yielding F1=1.

The query has value 1/3 in F1 even though its positive probability may be near zero.

### Applicability

Exact for Stage 0.7 K3.

### Failure conditions

If no two positive anchors straddle the query, an isolated boundary negative has no effect in K3. If the materializer already separates the anchors, value is zero.

### Unit test

Test 5.

## 15.3 Proposition 3 — Candidate ceiling

**Definition 15.1 (Trigger set).** For true event `e`, let `A(e)` be units whose query can provide admissible discovery evidence for `e`.

**Definition 15.2 (Evidence-certified discovery).** Event `e` is certified discovered only if the matched predicted event is supported by at least one queried unit in `A(e)`.

**Proposition 15.3.** If planner queries are restricted to candidate set `C`, then

\[
Recall_{certified}(\pi,M)
\le
\frac{|\{e\in E^\star:A(e)\cap C\ne\emptyset\}|}{|E^\star|}.
\]

### Proof

Any event with `A(e) intersect C` empty cannot receive a queried trigger under a policy restricted to `C`, and therefore cannot be certified discovered. At most the remaining events can be counted.

### Important limitation

This is **not** necessarily an upper bound on raw `overlap_any` recall. A long materialized segment can overlap an event without querying any trigger for it. Candidate ceiling should therefore be evaluated using evidence-certified matches or an evidence-faithful materializer assumption.

### Applicability

Candidate ceiling is a mandatory planner gate only after the discovery criterion is made evidence-faithful.

### Unit test

A synthetic overcoverage test should show raw overlap recall exceeding certified ceiling while certified recall obeys it.

## 15.4 Proposition 4 — General event-risk reduction is not submodular

**Proposition 15.4.** Event-risk reduction with merge/split or boundary complementarity need not be submodular.

### Construction

Let two queries `q_1,q_2` be required together to resolve whether a long candidate interval contains two distinct events. Define utility:

\[
F(\emptyset)=F(\{q_1\})=F(\{q_2\})=0,
\qquad F(\{q_1,q_2\})=1.
\]

Then

\[
F(\{q_2\})-F(\emptyset)=0,
\]

but

\[
F(\{q_1,q_2\})-F(\{q_1\})=1,
\]

violating diminishing returns.

### Adaptive interpretation

If the value of `q_2` becomes large only after observing a particular outcome of `q_1`, adaptive submodularity also fails.

### Consequence

No ordinary greedy max-coverage approximation guarantee applies to BCM in general.

### Simplified setting where submodularity may hold

If:

- event identities are fixed and disjoint;
- each query independently detects event `e` with known probability `theta_eq`;
- utility is weighted event coverage only;
- no boundary, merge, split, duplicate or review-cost interactions exist;

then

\[
F(S)=\sum_e w_e\left[1-\prod_{q\in S\cap A(e)}(1-\theta_{eq})\right]
\]

is monotone submodular.

Adaptive submodularity under corresponding independent item-state assumptions is plausible but **NOT PROVEN in this document**.

### Unit test

A two-query complementarity test must verify increasing marginal value.


---

# 16. Candidate, Planner and Materializer Ceilings

## 16.1 Candidate ceiling

Use Proposition 15.3 with a human-adjudicated trigger mapping or a frozen evaluator-only mapping. Report both:

- raw candidate event coverage;
- evidence-certified candidate event coverage.

**GO gate:** candidate ceiling at target scope at least 0.80.  
**NO-GO:** below 0.80; improve candidate/hypothesis construction before planner optimization.

## 16.2 Oracle-informed planner ceiling

**Definition 16.1.** An evaluator-only policy may use full labels/reference to choose at most `B` legal queries from the frozen action space, while using the same materializer.

This provides an upper bound for the action space, not an online method.

Compute exactly by exhaustive search only for small synthetic cases. For real `N`, use integer programming, dynamic programming over disjoint components, or a documented optimistic heuristic. If approximate, label it `estimated planner ceiling`, not a theorem.

**GO gate:** target-budget event recall at least 0.70–0.75.  
**NO-GO:** low ceiling means the action/candidate space is insufficient.

## 16.3 Materializer ceiling

Fix a query trace or evidence set and compare:

- audited K3;
- bridge-safe only after source audit;
- evaluator-informed optimal partition/boundary output.

This isolates output construction from acquisition.

## 16.4 Why the three ceilings must remain separate

- low candidate ceiling: missing hypotheses;
- high candidate but low planner ceiling: insufficient action set or budget;
- high planner but low achieved result: policy/outcome-model failure;
- high queried evidence but low materializer ceiling: output construction failure.

---

# 17. Submodularity Analysis

## 17.1 Adaptive monotonicity

For Bayes-optimal terminal risk, expected information cannot hurt, as shown in Theorem 8.1. This is an expected decision-theoretic monotonicity statement.

For fixed K3 or `R_tilde`, adaptive monotonicity is **NOT PROVEN** and can fail because a positive observation may trigger destructive merge or raise a heuristic uncertainty term.

## 17.2 Ordinary submodularity

General BCM utility is **not submodular** by Proposition 15.4. Complementarity arises from:

- two observations jointly proving a split;
- a positive anchor becoming valuable only after another confirms existence;
- boundary left/right probes jointly defining an interval;
- audit evidence changing the value of discovery queries;
- action-conditioned barrier semantics.

## 17.3 Adaptive submodularity

**NOT PROVEN.** The required conditional diminishing-returns property is incompatible with the minimal complementarity examples above.

## 17.4 Permissible paper language

Allowed:

> BCM uses a greedy counterfactual structural-risk heuristic.

Not allowed:

> BCM has a `(1-1/e)` guarantee.

unless a simplified objective and its assumptions are formally isolated and proved.

---

# 18. Independent Audit and Residual Estimate

This section is a future AEH-AQP reference, not a current BCM-v1 implementation claim.

## 18.1 Canonical-anchor population

Partition the video into audit cells `C={1,...,K}`. Assume every true event has exactly one canonical anchor and is assigned to exactly one cell.

After freezing the discovery output, define

\[
z_c=\mathbf 1[\text{cell }c\text{ contains the canonical anchor of an undiscovered event}].
\]

If multiple events may have anchors in one cell, replace `z_c` by a nonnegative count. The binary formulation is invalid otherwise.

## 18.2 Horvitz–Thompson estimator

Let `I_c` indicate inclusion in an independent audit sample, with known probability

\[
\pi_c=P(I_c=1)>0.
\]

Define

\[
\widehat N_{miss}
=
\sum_{c=1}^K\frac{I_cz_c}{\pi_c}.
\]

**Theorem 18.1 (HT unbiasedness).**

\[
\mathbb E[\widehat N_{miss}]=N_{miss}=\sum_cz_c.
\]

### Proof

By linearity of expectation,

\[
\mathbb E\left[\frac{I_cz_c}{\pi_c}\right]
=\frac{z_c}{\pi_c}P(I_c=1)=z_c.
\]

Summing over cells gives the result.

### Assumptions

- `z_c` is fixed relative to the sampling randomization;
- inclusion probabilities are known and positive;
- audit classification correctly determines whether an undiscovered canonical anchor is present;
- discovery output is frozen before defining `z_c`, or the joint design is explicitly modeled.

### Applicability

Not yet established because canonical anchors and independent audit have not been validated.

### Unit test

Monte Carlo sampling over a fixed synthetic cell population should recover the true mean.

## 18.3 Variance

For independent Poisson inclusion,

\[
Var(\widehat N_{miss})
=
\sum_c\frac{1-\pi_c}{\pi_c}z_c^2,
\]

with unbiased estimator

\[
\widehat{Var}
=
\sum_{c\in S}\frac{1-\pi_c}{\pi_c^2}z_c^2.
\]

For stratified simple random sampling without replacement, stratum `h` with `N_h` cells and `n_h` samples has

\[
\widehat N_h=N_h\bar z_h,
\]

\[
\widehat{Var}(\widehat N_h)
=N_h^2(1-n_h/N_h)\frac{s_h^2}{n_h}.
\]

## 18.4 Discovery/audit separation

The discovery planner may be adaptive and biased. The audit ledger must use a separately seeded, preregistered probability sample. Discovery queries cannot be retroactively counted as audit samples unless their inclusion probabilities under the full adaptive policy are known and incorporated.

## 18.5 Confidence intervals and sequences

A normal interval is unreliable for sparse rare events at small audit sample sizes. Permissible options include:

- exact/binomial intervals for equal-probability binary cells;
- design-based finite-population intervals under stratified SRS;
- conservative empirical-Bernstein bounds for bounded independent HT contributions;
- preregistered confidence sequences under sequential independent audit sampling.

A valid method and its assumptions must be stated. Until empirical coverage is verified, label the output `empirical audit interval`, not `certificate`.

## 18.6 Stopping rule

Let `U_miss(delta)` be an upper confidence bound. A possible stopping rule is

\[
U_{miss}(\delta)\le\epsilon_{count}
\]

or a lower bound on recall

\[
\frac{N_{disc}}{N_{disc}+U_{miss}(\delta)}\ge r_{target}.
\]

This requires `N_disc` to count distinct events correctly.

## 18.7 No unique anchor

Without a unique canonical anchor, the audit can estimate sampled positive-unit mass or positive time mass, but not distinct event count. A guarantee on event recall is then unidentified.

---

# 19. Complexity

Let:

- `N`: number of units;
- `H`: hypotheses;
- `E`: relation edges;
- `C_t`: candidate actions at step `t`;
- `P_t`: positive anchors;
- `B`: oracle budget.

## 19.1 Candidate construction

Current MAP-style construction:

- proxy quantile/sort: `O(N log N)`;
- island scan/local peaks/windows: `O(N)` after sorting;
- memory: `O(N)`.

## 19.2 Hypothesis state

- disjoint owner hypotheses: `O(N+H)`;
- sparse neighboring relation graph: `O(H+E)`;
- dense pairwise graph should be avoided (`O(H^2)`).

## 19.3 Direct counterfactual materialization

Audited K3 direct implementation is worst-case

\[
O(P_tN)
\]

per simulated outcome. Scoring all candidates is

\[
O(C_tP_tN)
\]

per round and

\[
O\left(\sum_{t=1}^B C_tP_tN\right)
\]

over the run.

For `N=347`, a simple implementation is acceptable if profiling confirms latency and all states are in memory.

## 19.4 Cache of counterfactual results

Use key:

```text
(state_hash, action_type, unit_id, simulated_outcome,
 materializer_version, materializer_config_hash,
 surrogate_config_hash)
```

Repeated queries in the same immutable state become `O(1)` lookup. Across rounds the state hash changes, so cache reuse is limited unless dependencies are localized.

## 19.5 Optimized local materializer update

With ordered anchor/negative sets and prefix structures:

- insert observation: `O(log N)`;
- identify affected neighboring groups: `O(log P_t)`;
- recompute local span: `O(k)`;
- update local surrogate edges: `O(deg(h))`.

Then candidate scoring can approach

\[
O\left(C_t(\log N+k+deg)\right)
\]

per round.

## 19.6 Long-video scaling requirements

For large `N`:

- interval tree or ordered set for anchors/barriers;
- prefix sums for negative counts;
- component-level candidate pruning;
- top-k approximate score screening before exact counterfactual materialization;
- incremental risk contributions;
- batched/cached probability inference;
- bounded relation graph degree.

---

# 20. BCM-AQP Pseudocode

```text
Algorithm BCM-AQP-v1

Input:
    PublicUnitTable U_public          # no oracle labels
    OracleAccessor O
    total budget B
    frozen materializer M
    frozen surrogate config Lambda
    frozen candidate/action config Cfg

Output:
    EventRelation E_hat
    ActionTrace T

1: assert U_public has no oracle_label or evaluator columns
2: H <- empty observation history
3: hypotheses <- build_hypotheses(U_public, H, Cfg)
4: relations <- build_relation_edges(hypotheses, U_public, H, Cfg)
5: state <- PlannerState(U_public, H, hypotheses, relations, spent_cost=0)
6: E_hat <- M(state.observations)
7: risk <- surrogate_risk(state, E_hat, Lambda)
8: T <- empty immutable trace

9: while state.spent_cost < B:
10:     actions <- enumerate_actions(state, Cfg)
11:     actions <- remove actions whose physical unit was already queried
12:     actions <- remove actions with cost > B - state.spent_cost
13:     if actions is empty: break

14:     best <- NONE
15:     for q in actions in deterministic order:
16:         p_pos <- estimate_outcome_probability(q, state)
17:         assert p_pos was computed without unqueried labels/reference

18:         state_pos <- counterfactual_update(state, q, POSITIVE)
19:         E_pos <- materialize_counterfactual(state_pos, M)
20:         R_pos <- surrogate_risk(state_pos, E_pos, Lambda)

21:         state_neg <- counterfactual_update(state, q, NEGATIVE)
22:         E_neg <- materialize_counterfactual(state_neg, M)
23:         R_neg <- surrogate_risk(state_neg, E_neg, Lambda)

24:         raw_score <- risk - [p_pos * R_pos + (1-p_pos) * R_neg]
25:         score <- raw_score / cost(q)        # optional frozen heuristic
26:         update best using score, then deterministic tie break

27:     if best is NONE: break
28:     if best.score <= epsilon_stop: break

29:     commit selected action to trace with state_before_hash
30:     obs <- O.query(best.unit_id)             # only real label access
31:     state <- update_after_observation(state, best.action, obs)
32:     state.spent_cost <- state.spent_cost + obs.cost
33:     E_hat <- M(state.observations)
34:     risk <- surrogate_risk(state, E_hat, Lambda)
35:     append obs, state_after_hash and scores to T

36: return E_hat, T
```

## 20.1 Mandatory safety properties

- counterfactual branches are simulated; they never call `O`;
- actual oracle is called once only after selection;
- reference relation never enters lines 1–36;
- budget uses actual action cost;
- action type is retained for action-conditioned updates;
- same saved trace can be replayed with another materializer;
- if abstain is possible, pseudocode must add an abstain branch rather than coerce it.

---

# 21. Codex Implementation Contract

## 21.1 `EventHypothesis`

```python
@dataclass(frozen=True)
class EventHypothesis:
    hypothesis_id: str
    owner_unit_ids: tuple[int, ...]
    seed_unit_id: int
    existence_probability: float
    anchor_probability_by_unit: tuple[tuple[int, float], ...]
    left_support: tuple[int, ...]
    right_support: tuple[int, ...]
    queried_positive_ids: tuple[int, ...]
    queried_negative_ids: tuple[int, ...]
    verification_state: str
```

### Requirements

- probabilities finite and clipped to `[eps,1-eps]` only for numerical logs;
- no evaluator fields;
- immutable or versioned;
- owner units initially disjoint.

## 21.2 `RelationEdge`

```python
@dataclass(frozen=True)
class RelationEdge:
    src_id: str
    dst_id: str
    same_event_probability: float
    relation_state: str
    evidence_observation_ids: tuple[str, ...]
```

Allowed v1 states: `unresolved`, `hard_distinct`. `confirmed_same` is disabled unless a relation oracle is available.

## 21.3 `PlannerState`

```python
@dataclass(frozen=True)
class PlannerState:
    public_units: PublicUnitTable
    observations: tuple[OracleObservation, ...]
    hypotheses: tuple[EventHypothesis, ...]
    relation_edges: tuple[RelationEdge, ...]
    queried_unit_ids: frozenset[int]
    spent_cost: float
    state_version: int
    state_hash: str
```

No hidden labels/reference may be present in this object.

## 21.4 `build_hypotheses(...)`

```text
Input:
    public units, frozen candidate config, queried observations optional
Output:
    deterministic hypothesis list and owner mapping
Oracle access:
    prohibited
Reference access:
    prohibited
Complexity:
    O(N log N)
```

Initial v1 may replicate MAP q0.70 islands/local peaks/audit cells, but must label this `MAP_CANDIDATE_HEURISTIC_V1`, not a learned event model.

## 21.5 `estimate_outcome_probability(...)`

```text
Input:
    QueryAction, PlannerState, frozen calibration object
Output:
    probability vector over legal outcomes
Oracle access:
    prohibited
Reference access:
    prohibited
Determinism:
    required for frozen state/config
Numerical cases:
    empty bin -> hierarchical prior; NaN proxy -> explicit default/error
```

## 21.6 `counterfactual_update(...)`

```text
Input:
    immutable PlannerState, QueryAction, simulated outcome
Output:
    new immutable simulated state
Oracle access:
    prohibited
Reference access:
    prohibited
```

The function must distinguish unqueried units from simulated negatives and must not mutate the real state.

## 21.7 `materialize_counterfactual(...)`

```text
Input:
    simulated state observations, audited materializer adapter
Output:
    EventRelation
Oracle/reference access:
    prohibited
Caching key:
    state_hash + action + outcome + materializer version/config hash
```

Initial safe adapter: audited Stage 0.7 K3. Existing clean `k3_bridge_safe` cannot be used until its source is supplied and audited.

## 21.8 `surrogate_risk(...)`

```text
Input:
    PlannerState, EventRelation, frozen lambda/config
Output:
    finite scalar and per-term diagnostic dictionary
Reference access:
    prohibited
Range:
    each component in [0,1]; weighted total in [0,1]
```

If a component is disabled or undefined, its weight must be zero and the diagnostic must state why.

## 21.9 `score_query(...)`

Returns:

```text
p_positive
risk_current
risk_if_positive
risk_if_negative
raw_expected_reduction
cost_normalized_score
cache_hit flags
```

Tie breaking:

1. higher score;
2. higher raw expected reduction;
3. lower cost;
4. action priority frozen in config;
5. lower unit ID.

## 21.10 `select_query(...)`

Must not call oracle. It returns an action proposal and full diagnostic row. It must reject already queried units and infeasible costs.

## 21.11 `update_after_observation(...)`

This is the only planner state transition receiving a real observation. It must verify the selected unit/action matches the committed request.

## 21.12 Oracle interface

```python
class OracleAccessor(Protocol):
    def query(self, unit_id: int) -> OracleObservation: ...
```

The implementation must enforce duplicate/budget checks. Do not pass a full label-bearing unit table to planner functions.

## 21.13 Trace schema

Minimum fields:

```text
run_id
call_idx
state_before_hash
action_type
region_id
hypothesis_ids
unit_id
estimated_p_positive
risk_before
risk_if_positive
risk_if_negative
raw_score
normalized_score
oracle_outcome_after_query
oracle_cost
state_after_hash
materializer_version
surrogate_version
```

## 21.14 Clean benchmark compatibility

Before comparing with clean benchmark:

- use its frozen unit/proxy/oracle/reference hashes;
- do not modify matching or budget grid;
- replay existing baselines unchanged;
- record that actual bridge-safe/matcher audit remains blocked until `benchmark_lib.py` is present.

---

# 22. Synthetic Test Specification

All tests use temporally ordered 10-second units unless otherwise stated. Tests may use a simple frozen probability map so query order is deterministic.

## Test 1 — Single isolated event

- Units: `u0,u1,u2`.
- Labels: `0,1,0`.
- Proxy: `0.1,0.9,0.1`.
- Expected query: discover/core query `u1` first.
- Expected K3 output: one segment `[10,20)`.
- Invariant: positive-anchor coverage, deterministic tie independent.
- Validates: Definitions 5.1, 13.5; Theorem 14.1.

## Test 2 — Two adjacent distinct events

- Units: `u0,u1,u2`.
- Labels: `1,0,1`.
- True events: `[0,10)`, `[20,30)`.
- Query trace: `u0`, `u2`, then gap `u1`.
- Before gap observation: K3 outputs one `[0,30)` segment.
- After negative: two segments.
- Invariant: barrier safety.
- Validates: Proposition 15.2.

## Test 3 — One event spanning multiple positive units

- Units: `u0,u1,u2`.
- Labels: `1,1,0`.
- True event: `[0,20)`.
- Expected K3 output after querying `u0,u1`: one segment `[0,20)`.
- Invariant: multiple anchors do not imply multiple materialized events.
- Validates: hypothesis saturation and K3 grouping.

## Test 4 — Positive anchors separated by unqueried gap

- Units: `u0,u1,u2`.
- Queried labels: `u0=1,u2=1`; `u1` unqueried.
- Expected K3 output: one `[0,30)` segment because one-unit gap is allowed.
- Invariant: unqueried is not negative; K3 includes unqueried interior unit.
- Validates: audited implementation semantics.

## Test 4B — Destructive positive bridge

- Units: `u0,u1,u2,u3`.
- Initial queried positives: `u0,u3`; K3 outputs two events.
- Query `u1` and observe positive.
- Expected K3 output: one `[0,40)` segment.
- Validates: Proposition 9.1 and possible negative materializer utility.

## Test 5 — Positive anchors separated by queried negative

- Same as Test 4, but query `u1=0`.
- Expected output: two segments.
- Invariant: hard barrier.
- Validates: Theorem 14.2.

## Test 6 — Boundary negative

- Positive: `u1=1`; queried negatives: `u0=0,u2=0`.
- Expected K3 output: `[10,20)` exactly as with only `u1` positive.
- Invariant: boundary negatives have no additional effect without expansion.
- Validates: limitation of negative-barrier value proposition.

## Test 7 — All-negative video

- All labels zero.
- Expected output: empty EventRelation for every budget.
- Planner may stop when all candidates exhausted/score nonpositive.
- Invariant: no unsupported event creation.

## Test 8 — Long proxy island with duplicate units

- Event A has `B` high-score positive units in one component.
- `B` other events each have one slightly lower-score unit.
- Top-record policy discovers one event; component/event-aware policy discovers `B`.
- Validates: Proposition 15.1 and hypothesis-level saturation.

## Test 9 — Low-proxy isolated unseen event

- One true positive unit has proxy zero outside all high-proxy islands.
- Expected behavior: `AUDIT_UNCOVERED` candidate exists and eventually competes under residual risk/exploration floor.
- Failure condition: candidate generator never exposes unit.
- Validates: residual term and candidate ceiling.

## Test 10 — Core/segment cap collision

- Positive units `u0,...,u4`, each 10s.
- Expected K3 grouping: first four span 40s; fifth begins new group because proposed span is 50s.
- Expected: no independent 60s segment-cap trigger.
- Validates: Theorem 14.3 and code discrepancy.

## Test 11 — Deterministic tie

- Two candidates have identical probability/risk/cost.
- Expected query: lower unit ID after frozen action-priority tie break.
- Repeated runs produce byte-equivalent trace except timestamp fields, which should be excluded or frozen.
- Validates: determinism.

## Test 12 — Zero budget

- `B=0`.
- Oracle calls: zero.
- Output: materialization from empty observation state, normally empty for K3.
- Validates: Bellman terminal case and budget accounting.

## Test 13 — Budget larger than candidate count

- Budget exceeds legal unique units/actions.
- Expected: no duplicate query; stop after candidate exhaustion.
- Validates: OracleAccessor and stop rule.

## Test 14 — Outcome access leakage sentinel

- Planner receives a public table physically lacking label column.
- A hidden sentinel label store raises if read before committed query.
- Expected: query selection succeeds without sentinel access; exactly one access occurs after commit.
- Validates: online accessibility contract.

## Test 15 — Abstain outcome

- Oracle returns abstain for one query.
- Binary implementation must fail clearly or execute a frozen abstain branch.
- It must not silently convert abstain to negative.
- Validates: A2-I.

## Test 16 — Matcher cardinality counterexample

Use IoU matrix approximately

\[
\begin{pmatrix}1&\epsilon\\\epsilon&0\end{pmatrix},\quad 0<\epsilon<1/2.
\]

A max-sum-IoU assignment chooses one positive match after zero filtering, while maximum overlap cardinality is two. Test the actual clean matcher once helper source is available.

---

# 23. Claim–Assumption–Evidence Matrix

| Claim | Status | Required assumptions | Current evidence | Promotion gate |
|---|---|---|---|---|
| Exact queried-unit oracle | Modeling assumption | no error; abstain handled | cache treated as reference oracle | audit abstain count/schema |
| Event identity from binary labels | False in general | richer semantics/model | Proposition 5.1 counterexample | actor/relation oracle or validated model |
| K3 positive-anchor coverage | Theorem for audited K3 | valid ordered units/log | source audit | synthetic tests |
| K3 hard-barrier safety | Theorem for audited K3 | negative strictly inside anchor gap | source audit | synthetic tests |
| K3 40s bound | Theorem | no post expansion | source audit | synthetic test 10 |
| K3 independent 60s cap | False for K3 path | K4 expansion required | code audit | do not claim |
| K3 idempotence | NOT WELL-DEFINED | canonical compatible state needed | none | define typed composition |
| `k3_bridge_safe` semantics | BLOCKED | missing helper source | wrapper only | provide/audit benchmark_lib.py |
| Bayes VOI nonnegative | Theorem | optimal decision can ignore observation | proof in Section 8 | finite-state unit test |
| Fixed materializer utility nonnegative | False | — | counterexample | do not claim |
| Structural surrogate equals event-F1 risk | NOT PROVEN | calibrated posterior/loss link | none | held-out correlation/regret |
| MAP is materialization-aware | Not true of Stage 1A code | materializer counterfactual required | score code audit | BCM implementation |
| Event-aware ranking can beat record ranking by B | Proposition | component knowledge / trigger discovery | construction | synthetic test 8 |
| Candidate ceiling bounds raw overlap recall | False without evidence-faithfulness | certified matching | analysis | report certified ceiling |
| General objective submodular | False in general | interactions absent | counterexample | simplified theorem only |
| HT residual estimate unbiased | Theorem under design | unique anchor, known inclusion, accurate audit | mathematical proof | annotation/audit validation |
| Statistical recall certificate | NOT PROVEN | valid CI/CS + canonical anchors | none | empirical coverage gate |
| BCM beats baselines | Empirical hypothesis | frozen fair benchmark | not yet run | cross-video tests |

---

# 24. Open Mathematical Questions

1. Can an evidence-faithful event matching criterion be defined without penalizing legitimate boundary uncertainty?
2. Can actor-centric hypotheses be constructed with a calibrated cheap model whose candidate ceiling exceeds 0.80?
3. Can a restricted event-coverage objective recover adaptive submodularity while preserving useful partition actions?
4. What action-conditioned observation model prevents positive gap probes from causing destructive merge?
5. How should event-F1, returned review seconds and oracle cost be combined without benchmark-specific weight tuning?
6. Can a proper scoring rule train the surrogate to predict one-step terminal loss reduction on separate videos?
7. What is the minimal canonical-anchor annotation protocol with acceptable inter-annotator agreement?
8. Can independent audit use adaptive stratification while maintaining computable inclusion probabilities and confidence sequences?
9. How should multi-event-per-unit observations be represented when 10-second units contain more than one event?
10. Does the actual clean benchmark matcher maximize overlap cardinality first? **BLOCKED pending helper source.**
11. What exact rule distinguishes `original_k3` and `k3_bridge_safe`? **BLOCKED pending helper source.**

---

# 25. Implementation GO / NO-GO Checklist

## 25.1 Current BCM-AQP v1 parts with mathematical basis

- finite-budget Bellman formulation as a normative benchmark;
- expected non-negativity of Bayes VOI;
- possible negativity of fixed-materializer utility;
- event-level duplicate saturation motivation and `1/B` construction;
- exact audited Stage 0.7 K3 anchor/gap/duration/barrier semantics;
- candidate ceiling for evidence-certified discovery;
- HT unbiasedness under explicit audit design assumptions;
- no-general-submodularity counterexample.

## 25.2 Parts that remain engineering heuristics

- proxy q0.70 component construction;
- 60-second audit windows;
- current MAP score and quotas;
- existence/partition/boundary/residual surrogate weights;
- Beta-bin outcome model without held-out calibration;
- greedy cost-normalized score;
- stop threshold;
- relation-edge priors in actor-free CSV replay.

## 25.3 What Codex can safely implement now

**GO:**

- public-only `PlannerState` and trace schema;
- audited Stage 0.7 K3 adapter;
- candidate/action generation with explicit heuristic versioning;
- simulated positive/negative branches;
- structural-risk diagnostic terms;
- deterministic greedy selection;
- OracleAccessor-mediated observation;
- synthetic tests and ceiling tools;
- trace replay with the audited K3.

**Conditional GO:**

- gap/structure probes only if positive outcomes use a new explicitly tested action-conditioned update that does not silently assume same-event;
- abstain support after the observation contract is frozen.

## 25.4 What Codex must not implement as if already validated

**NO-GO:**

- guessed clean-benchmark bridge-safe materializer;
- guessed clean-benchmark cardinality-first matcher;
- actor/type/risk fields derived from binary labels alone;
- evaluation-reference-dependent query scoring;
- fixed test-tuned lambda weights;
- submodular approximation claims;
- residual recall certificate without independent audit.

## 25.5 Claims forbidden before cross-video experiments

- BCM improves event-F1 AUC generally;
- BCM dominates ARC/SUPG/ABae;
- outcome calibration is robust;
- candidate ceiling exceeds 0.80 outside the pilot;
- fixed K3 parameters generalize;
- MAP/BCM low-budget gain is statistically stable;
- VLM-relative event semantics agree with human safety-event semantics.

## 25.6 Claims forbidden before independent audit

- event recall lower bound;
- missed-event risk at confidence `1-delta`;
- calibrated stopping guarantee;
- residual event count estimate with valid coverage;
- completeness certificate.

## 25.7 Final acceptance status of this reference

### Mathematically complete for

- Layer A normative derivation;
- Layer B surrogate specification and assumptions;
- Layer C implementation contract;
- audited Stage 0.7 K3;
- propositions/counterexamples;
- independent audit reference;
- synthetic tests.

### Code-audit acceptance

**PARTIALLY BLOCKED.** The requested requirement “mathematical definitions match actual K3/K3-safe code” cannot be fully satisfied because the archive omits `benchmark_lib.py`, which contains the actual clean-benchmark `original_k3`, `k3_bridge_safe` and event matcher implementations. This document deliberately does not guess them.

### Required next artifact

Provide the missing helper source. Then update only:

- Section 3 implementation fact table;
- Section 13.7 M0/M1 difference;
- bridge-safe invariants in Section 14;
- matcher semantics and Test 16;
- compatibility notes in Section 21.

No algorithm code or benchmark run is required for that audit.

---

# Appendix A — Audited Source Map

| Semantics | Source |
|---|---|
| Oracle duplicate/budget enforcement | `clean_baseline_benchmark_v1/scripts/run_clean_benchmark.py`, `OracleAccessor` |
| MAP components | `scripts/stage1a_map_anchor_only.py`, `build_components` |
| MAP score/quota | same file, `score_anchor`, `build_audit_regions`, `simulate_map` |
| Stage 0.7 K3 | `scripts/stage0_7_minimal_operator_compression.py`, `build_groups`, `expand_group`, `construct_k_segments` |
| K3 adapter ignores relation observations | `src/garc_eval/latent_event_diag/materializers/k3_adapter.py` |
| typed synthetic oracle | `src/garc_eval/latent_event_diag/oracles.py` |
| diagnostic relation/gap planners | `src/garc_eval/latent_event_diag/planners/policies.py` |
| available diagnostic matcher | `src/garc_eval/latent_event_diag/evaluation.py` |
| trace creation/prefix replay wrapper | `clean_baseline_benchmark_v1/scripts/run_clean_benchmark.py`, `trace_from_order`, `write_run` |
| normalized trapezoid AUC | Stage 0.7/1A scripts and clean benchmark aggregation |
| unavailable clean materializer/matcher | missing `clean_baseline_benchmark_v1/scripts/benchmark_lib.py` |

# Appendix B — Recommended Immediate Codex Audit Task

```text
Task: Complete the BCM code-semantics audit without changing algorithms.

Required input:
  clean_baseline_benchmark_v1/scripts/benchmark_lib.py
  and any imported helper defining materialize_from_trace/evaluate_events.

Required output:
  1. exact pseudocode for original_k3;
  2. exact pseudocode for k3_bridge_safe;
  3. line-by-line difference table;
  4. proof/counterexample for positive-anchor coverage, negative barrier,
     boundedness, determinism and rerun stability for each variant;
  5. exact matching optimization objective and tie break;
  6. whether matcher maximizes cardinality before IoU;
  7. update this reference's blocked sections only.

Prohibited:
  code modification;
  new benchmark run;
  new VLM calls;
  inference from names or report prose when source is absent.
```
