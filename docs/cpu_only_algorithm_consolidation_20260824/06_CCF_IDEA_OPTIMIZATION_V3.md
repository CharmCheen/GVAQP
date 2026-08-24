# GVAQP CCF Idea Optimization V3

Date: 2026-08-24

Status: `IDEA_V3_NOT_YET_CANONICAL`

This document is the third-round revision of V2 rather than a rewrite. It preserves V2's generalization boundary, three-tier cost contract, asymmetric pilot rule, data expansion gate, hypothesis order, and stop-loss criteria. V3 only repairs five execution gaps identified in the external review.

## 1. Refined title

### Recommended English title

**Discovery Before Verification: Deadline-Safe Open-Semantic Event Queries over Unscanned Video**

### Recommended Chinese title

**先发现，再验证：未扫描视频上的硬截止开放语义事件查询**

This title is more database-facing than the previous title because it names the central operator dependency, the execution constraint, and the query result type.

## 2. Refined one-sentence thesis

> Open-semantic querying over initially unscanned video is a causal-frontier execution problem: SCAN actions create future VERIFY opportunities, while only verified and durably committed events completed before a hard deadline contribute query utility.

The paper should not be organized around “a better controller.” It should be organized around this execution model, its regime boundary, and the simplest algorithm that exploits the structure.

## 3. Problem abstraction: Causal-Frontier Event Query

Let the execution state at time \(t\) be:

\[
X_t=(U_t,F_t,R_t,t),
\]

where:

- \(U_t\) is the set of unscanned temporal cells;
- \(F_t\) is the exposed candidate frontier;
- \(R_t\) is the durable, deduplicated event relation;
- \(t\) is elapsed physical or simulated time.

A SCAN action transforms the action space itself:

\[
\operatorname{SCAN}(c): U_t \rightarrow U_{t+1},\quad F_t \rightarrow F_{t+1}.
\]

A VERIFY action may consume only a candidate already present in \(F_t\):

\[
\operatorname{VERIFY}(x),\quad x\in F_t.
\]

A positive verification changes user-visible state only after atomic commit:

\[
\operatorname{COMMIT}(x): R_t\rightarrow R_{t+1}.
\]

The deadline objective is:

\[
\max |R_D|,
\]

or its normalized anytime form:

\[
\max \frac{1}{D}\int_0^D \frac{|R_t|}{|R^*|}\,dt.
\]

This formalization distinguishes GVAQP from a fixed-candidate ranking problem. It also prevents a baseline from receiving unscanned candidates for free.

## 4. Method: DATB-SV `(V3 revision: theory time-box)`

DATB-SV remains intentionally deterministic:

1. breadth-first temporal-bisection SCAN order;
2. VERIFY restricted to the exposed frontier;
3. fixed 1:1 SCAN/VERIFY interleaving with safe fallback;
4. conservative deadline admission with commit reserve;
5. atomic event materialization and event-ID deduplication.

### Theoretical proof target

For a dyadic temporal partition, after completing level \(d\) of breadth-first midpoint scanning, the maximum unscanned temporal gap is bounded by:

\[
G_d \le \frac{L}{2^d},
\]

where \(L\) is video duration.

The paper should prove the discrete-cell equivalent and derive a worst-case event-touch condition: once the maximum gap is shorter than a target event's duration under the frozen exposure model, that event cannot remain entirely between sampled locations.

This is a proof target, not an established theorem in the current repository. It provides a stronger reason for temporal bisection than empirical convenience.

### Discrete proof task

The proof is assigned an independent theoretical work package named `T_THEORY_MAX_GAP`, with a budget of 12 investigator-hours. It is pure analytical work, requires no GPU or new inference, and runs in parallel with T0, T0.5, T1, and T2 rather than blocking their execution.

The minimum acceptable result is:

1. define the discrete temporal-cell equivalent of maximum unscanned gap under the frozen breadth-first midpoint order;
2. prove an upper bound equivalent to \(G_d\le L/2^d\), including integer rounding and boundary cells;
3. state the exact exposure assumption under which an event of duration \(\ell\) cannot remain untouched after the maximum gap falls below \(\ell\);
4. derive a worst-case event-touch depth and convert it to a worst-case SCAN count or time bound under a declared cost tier.

If a strict proof cannot be completed within 12 hours, set the status to `FORMAL_BOUND_NOT_ESTABLISHED`. The allowed downgrade is an empirically validated upper-bound observation over the frozen T1 synthetic design. In that case the manuscript must call it an empirical invariant or observed bound, not a theorem, guarantee, proof, or worst-case result.

## 5. Reordered hypotheses

### Primary mechanism hypothesis H2

> DATB-SV's advantage over sequential and uniform discovery increases with temporal sparsity and multimodality, and approaches zero for dense, temporally contiguous events.

H2 is tested first because it identifies the regime in which the new execution model matters. A positive average result without this interaction would look like an engineering heuristic; a verified regime boundary supports a systems contribution.

### Performance hypothesis H1

> Within the regime identified by H2 and under identical candidate-access, oracle, commit, and cost semantics, DATB-SV increases distinct committed events before deadline relative to simple fixed baselines.

### Oracle invariance hypothesis H3

> Given identical confirmation records, changing oracle-source metadata does not alter the action trace; changing oracle judgments may alter measured utility but not the scheduler contract.

### External utility hypothesis H4

> Equal positive-clip yield need not imply equal independently annotated human-event utility.

H4 remains external validation. It is not used to select DATB-SV parameters.

## 6. H2-first CPU experiment `(V3 revision: budgeted fractional design)`

Construct a deterministic synthetic trace family. Synthetic results test mechanism and implementation, not real-world prevalence.

### Frozen factors

| Factor | Levels |
|---|---|
| Event density | sparse, medium, dense |
| Temporal modes | 1, 3, 6 separated regions |
| Event duration | short, medium, long |
| Proxy exposure noise | none, false-negative dominant, false-positive dominant |
| VERIFY/SCAN cost ratio | 1, 3, 10, 30 |
| Deadline tightness | 20%, 40%, 60% of exhaustive cost |

The expanded mixed-level full factorial contains

\[
3^5\times4=972
\]

design points and is not admitted under the T1 time-box.

### Budget reverse calculation

The current in-memory CPU replay is budgeted conservatively at 0.5 seconds per policy-seed call. This is a planning upper estimate and must be replaced by a frozen preflight measurement before T1 execution if the observed median is higher. The primary comparison contains five policies. Budgeting five seed slots per design point, including repeated seeds for the random policy and deterministic replication checks, gives:

\[
0.5\text{ s}\times5\text{ policies}\times5\text{ seeds}=12.5\text{ s/design point}.
\]

Of the 24 investigator-hours assigned to T1, at most eight elapsed CPU-hours may be consumed by the frozen matrix. Applying a fourfold safety factor for serialization, metric aggregation, logging, and slower-than-estimated traces gives the maximum affordable number of design points:

\[
N_{max}=\left\lfloor\frac{8\times3600}{12.5\times4}\right\rfloor=576.
\]

The remaining 16 investigator-hours are reserved for generator implementation, invariant checks, analysis, and the frozen report. If the preflight estimate implies fewer than 324 affordable points under this formula, T1 must stop with `DESIGN_EXCEEDS_TIMEBOX`; it may not reduce seeds, factors, or levels after seeing outcomes.

### Frozen fractional factorial

T1 uses a 324-point mixed-level regular fraction. Encode event density \(A\), temporal modes \(B\), event duration \(C\), proxy exposure noise \(D\), and deadline tightness \(F\) as levels \(\{0,1,2\}\). Enumerate the full \(3^4=81\) combinations of \(A,B,C,D\), then define:

\[
F=(A+B+C+D)\bmod3.
\]

Cross these 81 rows with all four VERIFY/SCAN cost ratios \(\{1,3,10,30\}\), producing:

\[
81\times4=324
\]

design points. The three-level core has a length-five defining relation and therefore provides at least Resolution IV separation of main effects from two-factor interactions; under the regular linear-component interpretation it is a Resolution V core. The analysis retains all main effects and preregistered two-factor interactions, with primary emphasis on policy-by-density, policy-by-temporal-modes, policy-by-cost-ratio, and policy-by-deadline interactions.

All interactions of order three or higher are deliberately excluded. They require substantially more design points, are not needed to test the stated sparse/multimodal mechanism, and would be difficult to interpret as a systems design boundary. No higher-order interaction may be added after outcomes are observed.

The five primary policies are DATB-SV 1:1, sequential 1:1, uniform-stride 1:1, largest-gap 1:1, and random 1:1. Alternative SCAN/VERIFY policy ratios remain secondary ablations and run only on a preregistered sentinel subset of the design matrix; they are not used to select the primary policy.

### Freeze artifacts and exclusions

Before T1 starts, the following independent artifacts must exist:

```text
docs/cpu_only_algorithm_consolidation_20260824/frozen_h2_design_matrix_v1.csv
docs/cpu_only_algorithm_consolidation_20260824/frozen_h2_generator_spec_v1.json
docs/cpu_only_algorithm_consolidation_20260824/frozen_h2_analysis_plan_v1.md
```

The seed list is frozen as `1729, 3253, 4999, 7919, 104729`. Deterministic policies must agree across seed slots; disagreement is an implementation failure.

Rows may be excluded only for a schema-invalid trace, a violated causal-frontier invariant, an impossible offline reference, or a non-finite timestamp/cost. Runtime failures remain in the matrix with an explicit failure status. Zero effect, negative effect, unexpected direction, or an inconvenient regime is never an exclusion reason. The design matrix, generator hash, seeds, sentinel subset, exclusions, and analysis formula must be frozen before any policy comparison output is inspected.

### Baselines

- sequential SCAN plus identical VERIFY logic;
- uniform-stride SCAN plus identical VERIFY logic;
- largest-gap SCAN plus identical VERIFY logic;
- random SCAN with frozen seeds;
- temporal bisection with alternative fixed SCAN/VERIFY ratios.

### Primary endpoint

Normalized anytime distinct-committed-event AUC under a common cost tier.

### Decisive analysis

Estimate the interaction between policy and preregistered temporal regime. Report the full regime map, not only the best average.

H2 receives `PASS` only if the DATB-SV advantage is directionally ordered across the frozen sparse/multimodal to dense/contiguous regimes and is robust across at least two VERIFY/SCAN cost ratios. A single favorable synthetic configuration is `FAIL`, not `PARTIAL`.

### C1-to-C3 cost-ratio bridge

The logarithmic grid \(\{1,3,10,30\}\) covers a 30-fold range while keeping the design below the 576-point budget ceiling. When paired common-path measurements later produce a Tier C3 VERIFY/SCAN ratio, apply the following frozen rule:

1. if the C3 ratio lies within \([1,30]\), use the two nearest tested ratios to bracket the expected regime; interpolation may be reported as sensitivity analysis but not as a newly fitted policy;
2. if the C3 ratio is below 1 or above 30, rerun an H2 supplement containing the measured ratio and at least one neighboring logarithmic point before making a C3 mechanism claim;
3. an out-of-support C3 ratio must never be assigned the behavior of the nearest grid endpoint or extrapolated from the original regime map.

The supplement reuses the frozen generator, policies, seeds, exclusions, and analysis. Only the cost-ratio column may be extended, with the C3 measurement record serving as provenance.

## 7. Corrected interpretation of the existing six workloads

The current corpus contains a crossed design:

```text
3 videos x 2 queries = 6 video-query cells
```

These are not six fully independent generalization samples. They contain only:

```text
3 video clusters
2 query clusters
```

Consequences:

1. Stage 1 can establish implementation validity and descriptive within-corpus effects.
2. It cannot PASS a broad cross-video and cross-query generalization gate.
3. A raw pair-level bootstrap is invalid.
4. A six-cell workload bootstrap remains fragile because video and query dependencies are crossed.
5. Leave-one-video-out and leave-one-query-out are diagnostics, not reliable asymptotic inference at these cluster counts.

The Stage 1 label is therefore changed from an implicit generalization study to:

```text
EXISTING_CORPUS_INTERNAL_EFFECT_REPLAY
```

Its maximum evidence grade is `DESCRIPTIVE_INTERNAL_SUPPORT`.

## 8. Data expansion gate

Data expansion must be planned before Stage 1 outcomes are used to choose new queries or videos.

### Development-scale expansion

Minimum target:

```text
6 long videos x 4 query families = 24 video-query cells
```

This supports robustness diagnostics but remains weak for broad inferential claims.

### Claim-grade target

Recommended target:

```text
at least 8 long videos
at least 8 semantically distinct queries
at least 4 query families
at least 2 independent video sources or datasets
```

Suggested query families are object state, multi-object interaction, temporally extended action, and safety/near-miss event. Queries and source videos must be selected before observing DATB-SV versus baseline outcomes on those workloads.

The resulting crossed cells should be analyzed with workload-level effects plus leave-one-video-out, leave-one-query-out, and a preregistered crossed-effects or multiway-cluster procedure. Exact inference remains limited when either cluster dimension is small.

This expansion requires new model inference and is therefore:

```text
BLOCKED_BY_NON_CPU_REQUIREMENT
```

It is a future acquisition plan, not authorization to run inference now.

## 9. Cost validity contract `(V3 revision: explicit grid support)`

Every result row must carry one and only one cost tier.

### Tier C1: `SIMULATED_BOUND`

- CPU-only replay;
- frozen deterministic or distributional action costs;
- valid for algorithmic sensitivity and mechanism analysis;
- maximum evidence grade: `PARTIAL`;
- prohibited wording: “measured wall-clock speedup” or “deployment deadline guarantee.”

### Tier C2: `CACHED_MEASURED_UNPAIRED`

- historical measured durations from incompatible hardware, paths, or runs;
- usable only as context or sensitivity ranges;
- evidence grade: `FAIL` for comparative cost claims;
- must not be mixed into a single SCAN/VERIFY ratio and presented as measured cost.

### Tier C3: `PAIRED_COMMON_PATH`

- SCAN and VERIFY measured on the same execution path, hardware, workload, and accounting boundary;
- includes decode, preprocessing, inference, materialization, and commit according to the frozen contract;
- supports a cost-validity `PASS` if repeated measurements justify the admission bounds.

### Required provenance fields

```text
cost_tier
cost_source_id
hardware_id
software/operator_version
workload_id
action_type
paired_run_id
measurement_boundary
raw_duration
admission_bound
bound_estimation_rule
timestamp
```

Stage 1 permits only Tier C1 for comparative replay. Every Stage 1 table and figure must include `Cost tier: C1 / simulated-bound / PARTIAL validity` in its title or caption.

The Tier C1 H2 regime map has explicit cost-ratio support only on \([1,30]\), sampled at \(\{1,3,10,30\}\). Tier C3 measurements inside that interval may be bracketed by tested points. Measurements outside it trigger the frozen supplemental-test rule in Section 6 and cannot inherit the C1 conclusion by extrapolation.

## 10. Asymmetric pilot rule

A small human pilot is not scientifically useless. Its valid role is asymmetric falsification, not confirmation.

An outcome-blind, preregistered two-workload pilot could support:

```text
both deltas near zero or contradictory
-> stop or redesign annotation assumptions
```

It cannot support:

```text
both deltas positive
-> claim the effect exists
```

Because the current decision is algorithm-first, this pilot is deferred. The protocol should describe it as “not currently necessary and non-inferential,” not “methodologically invalid.”

## 11. Time-box and stop-loss rules `(V3 revision: parity and theory budgets)`

Use effort budgets because they are more reproducible than calendar delays.

### T0: provenance recovery

Budget: one focused CPU workday or eight investigator-hours.

Stop rule: if a compatible endogenous exposure/cost/oracle manifest cannot be recovered without reconstructing values from downstream outcomes, mark it `RETIRED_FOR_CLAIM_USE`.

### T0.5: evaluator parity audit

Budget: six investigator-hours. This budget is independent of T0's eight hours and cannot be absorbed into provenance recovery.

Run the policy evaluator and fixed-baseline evaluator on the same always-VERIFY action trace with identical candidate records, budget, oracle outputs, event IDs, episode boundaries, unfinished-action treatment, and reference utility. Utility, regret, action counts, and per-step cumulative outputs must match exactly, except for explicitly frozen floating-point tolerance.

Stop rule: if exact parity cannot be established within six hours, set `EVALUATOR_PARITY_UNRESOLVED` and retire every historical controller/MAB/RL positive or negative claim that depends on the evaluator. The unresolved state cannot be interpreted as algorithm success, algorithm failure, evidence for retraining, or permission to change the evaluator after inspecting policy outcomes.

### T1: H2 synthetic mechanism test

Budget: three CPU workdays or 24 investigator-hours after the generator schema is frozen.

Stop rule: if H2 fails its ordered regime test, do not expand DATB-SV variants. Downgrade to execution-contract/measurement work.

### T2: existing-corpus replay

Budget: five CPU workdays or 40 investigator-hours after provenance passes.

Predeclared smallest effect of interest:

```text
median relative gain >= 5% in normalized anytime committed-event AUC
and
at least one additional committed event at two adjacent practical deadlines
in a majority of the six workload cells
```

This threshold is an engineering decision criterion, not a significance test.

Stop rule: if the effect is below this threshold, directionally unstable, or driven by one video/query, do not request GPU expansion for the algorithm paper. Route to a rigorous negative or measurement study.

### T3: non-CPU expansion

Authorization condition: H2 passes, T2 reaches at least `DESCRIPTIVE_INTERNAL_SUPPORT`, and a frozen acquisition plan exists.

Otherwise T3 remains blocked.

### T_THEORY_MAX_GAP: discrete proof

Budget: 12 investigator-hours, independent of all CPU experiment budgets.

This task runs in parallel and does not block T1 or T2. Success requires the discrete maximum-gap bound, its rounding/boundary conditions, the frozen exposure assumption, and the derived worst-case event-touch relation.

Stop rule: if a strict proof is incomplete at 12 hours, set `FORMAL_BOUND_NOT_ESTABLISHED`, stop proof expansion, and use only the empirical-bound downgrade defined in Section 4.

## 12. Two-dimensional decision matrix

Algorithmic effect and cost validity must be reported separately.

| Algorithmic effect | Cost tier | Allowed conclusion |
|---|---|---|
| PASS | C3 | Claim-grade deadline systems evidence, subject to generalization |
| PASS | C1 | Mechanism supported under simulated costs only |
| PARTIAL | C3 | Physical effect is heterogeneous or small |
| PARTIAL | C1 | Exploratory evidence only |
| Any | C2 | No comparative deadline claim |
| FAIL | Any | Do not rescue with controller training or post-hoc workloads |

Generalization is a third independent axis. Six existing cells cannot exceed `DESCRIPTIVE_INTERNAL_SUPPORT` regardless of effect size or cost tier.

## 13. Paper contribution ladder

### Minimum defensible contribution

A formal execution contract and reproducible negative/measurement result showing when clip/frame-oriented query evaluation fails to represent durable event utility.

### Strong systems contribution

The causal-frontier abstraction, DATB-SV, a proved maximum-gap property, and an H2 regime map under simulated and measured common-path costs.

### SIGMOD/VLDB-level target

All of the strong systems contribution plus:

1. diverse preregistered video and query clusters;
2. fair adapted comparisons with ExSample, ZEUS, Seiden, FiGO, and LAVA;
3. nontrivial end-to-end effect under Tier C3 costs;
4. robustness across oracle implementations;
5. independent human-event validation showing that durable-event utility matters beyond clip yield.

## 14. Revised stage order `(V3 revision: parallel calendar)`

```text
Parallel Track A: historical-data readiness
T0 provenance recovery or retirement [8 h]
  -> T0.5 evaluator parity audit [6 h]
  -> T2 existing six-cell descriptive replay under C1 costs [40 h]

Parallel Track B: mechanism readiness
T1 design/generator/seeds/exclusions freeze
  -> frozen 324-row design matrix
  -> H2 synthetic mechanism test under C1 costs [24 h total]

Parallel Track C: analytical support
T_THEORY_MAX_GAP discrete proof [12 h, non-blocking]

Track A + Track B gates
  -> stop-loss decision
  -> only if passed: preregister data expansion
  -> paired common-path physical measurement under C3 costs
  -> if C3 ratio is outside [1,30]: frozen H2 supplemental test
  -> claim-grade external workload evaluation
  -> frozen human-event external validation
```

T0 and T1 have no input dependency and may begin on the same calendar day. T1's design, generator, factor levels, seeds, exclusions, and matrix freeze must not inspect T0 recovery outcomes. T2 still waits for compatible T0 provenance and resolved evaluator parity. The evaluator parity audit precedes interpretation of historical controller regret and does not reopen controller training.

## 15. Final optimized verdict

The strongest version of the idea is not:

> A controller decides whether to SCAN or VERIFY.

It is:

> Open-semantic queries over unscanned video require deadline-safe execution over a causal candidate frontier. Temporal bisection supplies a worst-case discovery-spread guarantee, fixed interleaving prevents unsupported learned complexity, and durable event materialization defines what counts as an on-time answer.

The direction remains worth pursuing because H2 can be tested cheaply and decisively on CPU. It should be abandoned as an algorithm paper if the regime interaction or existing-corpus effect fails the frozen stop rules.

## 16. V2 -> V3 change summary

1. Replaced the infeasible full H2 factorial with a frozen 324-point mixed-level Resolution IV-or-higher fraction after a 24-hour budget reverse calculation.
2. Added an independent six-hour T0.5 evaluator parity audit and the `EVALUATOR_PARITY_UNRESOLVED` retirement rule.
3. Changed T0 and T1 from serial execution to parallel provenance and mechanism tracks while preserving all V2 effort budgets.
4. Expanded the cost-ratio grid to \(\{1,3,10,30\}\) and froze the out-of-support Tier C3 supplemental-test rule.
5. Added the 12-hour non-blocking `T_THEORY_MAX_GAP` task and the `FORMAL_BOUND_NOT_ESTABLISHED` empirical downgrade.
