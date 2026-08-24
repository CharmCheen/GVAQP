# GVAQP CCF Idea Optimization V2

Date: 2026-08-24

Status: `IDEA_V2_NOT_YET_CANONICAL`

This document refines, rather than silently overwrites, the previous frozen idea report. It incorporates the generalization, cost-tier, pilot-interpretation, and time-box criticisms raised after the first consolidation.

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

## 4. Method: DATB-SV

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

## 6. H2-first CPU experiment

Construct a deterministic synthetic trace family. Synthetic results test mechanism and implementation, not real-world prevalence.

### Frozen factors

| Factor | Levels |
|---|---|
| Event density | sparse, medium, dense |
| Temporal modes | 1, 3, 6 separated regions |
| Event duration | short, medium, long |
| Proxy exposure noise | none, false-negative dominant, false-positive dominant |
| VERIFY/SCAN cost ratio | 1, 4, 10 |
| Deadline tightness | 20%, 40%, 60% of exhaustive cost |

Use a balanced factorial or a preregistered fractional factorial if the full Cartesian product is unnecessary. Seeds, trace generator, and exclusions must be frozen before comparing policies.

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

## 9. Cost validity contract

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

## 11. Time-box and stop-loss rules

Use effort budgets because they are more reproducible than calendar delays.

### T0: provenance recovery

Budget: one focused CPU workday or eight investigator-hours.

Stop rule: if a compatible endogenous exposure/cost/oracle manifest cannot be recovered without reconstructing values from downstream outcomes, mark it `RETIRED_FOR_CLAIM_USE`.

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

## 14. Revised stage order

```text
T0 provenance recovery or retirement
  -> evaluator parity audit
  -> H2 synthetic mechanism test under C1 costs
  -> existing six-cell descriptive replay under C1 costs
  -> stop-loss decision
  -> only if passed: preregister data expansion
  -> paired common-path physical measurement under C3 costs
  -> claim-grade external workload evaluation
  -> frozen human-event external validation
```

The evaluator parity audit precedes interpretation of historical controller regret. It does not reopen controller training.

## 15. Final optimized verdict

The strongest version of the idea is not:

> A controller decides whether to SCAN or VERIFY.

It is:

> Open-semantic queries over unscanned video require deadline-safe execution over a causal candidate frontier. Temporal bisection supplies a worst-case discovery-spread guarantee, fixed interleaving prevents unsupported learned complexity, and durable event materialization defines what counts as an on-time answer.

The direction remains worth pursuing because H2 can be tested cheaply and decisively on CPU. It should be abandoned as an algorithm paper if the regime interaction or existing-corpus effect fails the frozen stop rules.
