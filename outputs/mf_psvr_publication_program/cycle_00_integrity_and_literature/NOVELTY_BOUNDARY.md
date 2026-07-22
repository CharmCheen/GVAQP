# MF-PSVR Novelty Boundary

`BOUNDARY_STATUS = CONDITIONAL_RESEARCH_HYPOTHESIS`

## Decision

No defensible "first" claim is currently supported. The literature audited so
far covers each listed broad ingredient: proxy/oracle allocation, relevant-clip
confidence, query-time adaptive scan, learned query-driven temporal refinement,
cheap-to-expensive multi-pass operators, high-accuracy validation, continuous
partial results, query-dependent fidelity scheduling, and question-adaptive
frame selection.

MF-PSVR remains scientifically viable only as a **joint method-and-measurement
hypothesis**: under a cold-proxy retrospective query, schedule endogenous SCAN,
selective semantic REFINE, frozen VERIFY, EventRelation materialization, and
durable commit against one actually enforced deadline, and demonstrate that the
learned controller/refiner improves cross-source anytime recovery beyond simple
and mechanism-matched controls.

That statement describes what must be tested. It is not yet a contribution.

## Established prior-art boundaries

| Prior | What it already establishes | Boundary left for this project |
|---|---|---|
| [ARC](https://doi.org/10.1145/3726302.3729896) | Relevant-clip query formalization; exhaustive predicate-conditioned proxy probabilities; temporal clustering; candidate/non-candidate oracle sampling; confidence-aware progressive refinement. | Incomplete online proxy evidence, strict action co-scheduling, confirmed typed relation, and durable stop semantics are outside the audited contract. |
| [SUPG](https://doi.org/10.14778/3407790.3407804) | Proxy-guided adaptive oracle sampling with precision/recall guarantees over a fully scored record universe. | Endogenous discovery and physical action cost are not its formal endpoint. |
| [ExSample](https://arxiv.org/abs/2005.09141) | Query-time adaptive sampling over unindexed temporal chunks with continual reprioritization from expensive results. | No separate learned semantic fidelity, verified temporal relation, or durable deadline contract. |
| [Seiden](https://doi.org/10.14778/3598581.3598599) | Query-agnostic oracle anchors, query-dependent MAB sampling, temporal interpolation, and downstream retrieval/AQP. | Index cost is amortized and output is not a confirmed event relation. |
| [MIRIS](https://doi.org/10.1145/3318464.3389692) | Query-driven tracking with learned query-specific filters/refiners, uncertainty resolution, and selective frame-rate increases. | No separate frozen semantic verifier or strict durable anytime deadline. |
| [DIVA](https://www.usenix.org/conference/atc21/presentation/xu) | Capture-time landmarks; query-specific multi-pass cheap-to-expensive operators; online upgrades; cloud high-accuracy validation; continuously refined/materialized results. | It optimizes progress/full delay in a camera-cloud deployment, not recoverable EventRelation prefixes under a fixed first-query stop deadline. |
| [Zeus](https://doi.org/10.1145/3514221.3526181) | Temporal action localization with an accuracy-aware RL agent that selects segment resolution, length, and sampling rate online. | It optimizes complete-query throughput/accuracy, not durable stop-time recovery with a separate unit confirmation contract. |
| [FiGO](https://doi.org/10.1145/3514221.3517857) | Query-time profiling, recursive video-chunk splitting, and per-chunk model/skip assignment while accounting for optimization plus execution time. | It produces a plan under an accuracy constraint rather than co-scheduling an anytime confirmed event prefix. |
| [Boggart](https://www.usenix.org/conference/nsdi23/presentation/agarwal-neil) | Model-agnostic ingest trajectories plus query-time selective user-CNN inference and accuracy-bounded temporal propagation. | Its ingest index is amortized; propagated frame/object output is not individually verified or durably committed under a first-query deadline. |
| [VideoStorm](https://www.usenix.org/conference/nsdi17/technical-sessions/presentation/zhang) | Online selection/allocation among video configurations using offline resource-quality profiles and per-query quality/lag utility. | Live multi-query cluster scheduling differs from retrospective event recovery and durable output. |
| [Focus](https://www.usenix.org/conference/osdi18/presentation/hsieh) and [EKO](https://arxiv.org/abs/2104.01671) | Ingest/query cost trade-offs, approximate indexes, adaptive sampling, and machine-oriented video storage. | The frozen workload begins without materialized query proxy evidence and charges a first query. |
| [Adaptive Greedy Frame Selection (2026)](https://arxiv.org/abs/2603.20180) | Question-aware relevance/coverage selection and routing over a bounded 1-FPS candidate pool under a frame budget. | It is one-shot QA frame selection, not progressive physical event recovery. |

The hashes and audit scope for these sources are in
[SOURCE_MANIFEST.json](SOURCE_MANIFEST.json). The search was targeted rather
than a formal systematic review; a broader database search and citation-chain
update remain mandatory before submission. Consequently, absence from this
table must never be used as proof of priority.

## Claims that are not admissible

The following claims are rejected now, independent of future benchmark gains:

- first proxy plus oracle video-query system;
- first progressive sampling of video at query time;
- first relevant-clip query system;
- first query-conditioned temporal refinement or learned intermediate fidelity;
- first cheap-to-expensive multi-pass video execution;
- first candidate/validator staging or progressive result materialization;
- first adaptive video configuration scheduler;
- first RL-based temporal action-query controller;
- first per-chunk heterogeneous model/fidelity plan;
- first model-agnostic index with query-time selective expensive inference and
  temporal propagation;
- first anytime or partial-result video query;
- first query-aware long-video frame selector;
- faithful ARC, SUPG, ABae, Seiden, MIRIS, ExSample, DIVA, Zeus, FiGO, or
  Boggart reproduction when reporting a benchmark-semantic physical adaptation.

The term "EventRelation" is project-specific vocabulary, not itself a research
contribution. Durability and deadline accounting are useful only if they change
the scientific conclusion or enable a method that wins under that contract.

## Conditional contribution bundle

The strongest potentially defensible bundle has four inseparable parts.

### 1. Execution contract

A retrospective semantic event query begins with incomplete query-time evidence.
Initialization, decode, all model tiers, controller overhead, verification,
materialization, serialization, fsync, and atomic commit share a monotonic hard
deadline. Any stopped run exposes a recoverable prefix of confirmed results.

### 2. Action formulation

The controller chooses among heterogeneous actions whose opportunity set changes
as evidence arrives:

- `SCAN`: create immutable candidate opportunities from raw video;
- `REFINE`: selectively acquire query-conditioned temporal semantic evidence;
- `VERIFY`: invoke the unchanged expensive semantic oracle;
- `MATERIALIZE/COMMIT`: construct and durably expose confirmed EventRelation
  state.

Commit is a reserved mandatory action, not free cleanup. The candidate universe
is endogenous rather than a fully scored fixed population.

The frozen Qwen verifier is part of the benchmark and evaluation contract, not
a novel mechanism. MIRIS already has an expensive final detector/predicate path,
and DIVA already validates cheap evidence with a high-accuracy cloud detector.

### 3. Learned decision mechanism

Independent-source models estimate candidate verification value and the
incremental value per second of REFINE versus SCAN/VERIFY. The method must be
deadline-conditioned and calibrated on groups independent of V0/V1. Complexity
earns inclusion only if paired ablations show a cross-source gain.

### 4. Empirical result

The frozen development method must improve paired task-level AnytimeAUC_F1 over
FIFO, score-only, ExSample-style incomplete scan, Zeus-style adaptive
configuration, FiGO-style chunk/fidelity planning, and other applicable
cost-matched controls. Native-cost MIRIS, DIVA, or Boggart superiority may be
claimed only from their FIRSTQUERY/AMORTIZED views—not from transfer or generic
cascade controls. The method must then pass the preregistered third-source gate
without retuning.

Parts 1–3 without Part 4 support an engineering artifact, not the intended
positive method paper.

## Competing hypotheses and discriminating predictions

### H-MF: learned multi-fidelity co-scheduling is causally useful

Predictions:

1. Leave-one-source-out candidate-value ranking improves verified-positive yield
   and task-level anytime utility over FIFO, random, and the frozen Y8 score.
2. REFINE changes which candidates are verified and its ablation crosses the
   minimum component-effect margin defined below, with benefit not isolated to
   V0.
3. A deadline-conditioned controller outperforms fixed cheap-to-expensive
   multipass, ExSample-style chunk allocation, Zeus-style adaptive
   configuration, and FiGO-style planning across the frozen deadline grid, not
   only at one favorable stop point.
4. Gains remain after charging model load/warm-up, controller inference,
   materialization, and durable commit.

### H-SIMPLE: coverage/order explains all gains

Prediction: FIFO, seeded random coverage, or Y8 score falls within the
preregistered practical-equivalence margins once candidate identity and deadline
accounting are repaired. If observed, abandon the learned controller/refiner
claim.

### H-PRIOR: a known mechanism explains all gains

Prediction: ExSample-style adaptive chunks, ARC-unit refinement, Zeus adaptive
configuration, FiGO chunk/model planning, or an appropriately costed
MIRIS/DIVA/Boggart view falls within the practical-equivalence margin. If
observed, either adopt the simpler/prior mechanism as the scientific conclusion
or identify a different demonstrated bottleneck; do not relabel it MF-PSVR
novelty.

### H-MEASUREMENT: apparent gains are accounting artifacts

Prediction: the advantage disappears when initialization, warm-up, physical
oracle latency, K3, serialization, fsync, and commit are included, or when
deadline misses and failed runs are retained. If observed, invalidate earlier
positive rows and revise the method.

### H-SHIFT: learned semantics are source-specific

Prediction: random-row splits look positive but grouped leave-source-out or the
third frozen source fails. If observed, reject generalization and either collect
more independent sessions or simplify to a source-agnostic method.

## Preregistered estimands and decision margins

These definitions apply before any new V0/V1 physical result is generated.

### Task summaries and failure handling

- The independent unit is `source_video x query`.
- For each task/method, summarize the three physical latency repeats by the
  median intention-to-run metric. Repeats are not resampled as independent data.
- A failure or deadline miss contributes the last valid durable snapshot at or
  before the deadline; if none exists, it contributes the empty relation
  (`F1=0`, `AnytimeAUC_F1=0`). It is never dropped.
- If no event is confirmed, TTFC is right-censored and reported at the frozen
  `T_high` horizon for the decision summary.
- Primary paired estimand:
  `Delta_AUC = mean_task(AUC_method - AUC_comparator)`.
  Secondary paired estimands use final F1, TTFC, VERIFY-order regret, total
  unique events, and unique events per physical oracle call.

### Development positive gate versus FIFO

All of the following are required:

1. **Cross-source direction:** V0 and V1 each have at least one query with
   `Delta AUC >= 0.01` or `Delta F1 >= 0.02`.
2. **Task noninferiority:** at least 3/4 tasks satisfy both
   `Delta AUC >= -0.01` and `Delta F1 >= -0.02`.
3. **Effect size:** at least two of the frozen program thresholds hold: macro
   relative AUC gain >=15%, macro absolute F1 gain >=0.05, macro TTFC reduction
   >=20%, at least two additional unique events across four tasks, VERIFY-order
   regret reduction >=20%, or events-per-oracle-call gain >=15%.
4. **Cost/safety:** refiner overhead <=10% of deadline, zero increase in deadline
   misses, zero replay/future-access/visibility violation, and complete cost
   accounting.

### Practical equivalence and causal component gate

A comparator **matches** MF-PSVR for the controller/mechanism claim when MF-PSVR
fails to exceed it on every practical margin: `Delta AUC < 0.01`,
`Delta F1 < 0.02`, TTFC reduction <10%, fewer than one additional unique event,
and VERIFY-regret reduction <10%, with no compensating safety advantage. One
such simple, Zeus-style, or FiGO-style match rejects the learned-controller
superiority claim.

REFINE earns an independent contribution only if Full minus no-REFINE reaches
at least one of: AUC +0.01, F1 +0.02, TTFC reduction 10%, one additional unique
event, or VERIFY-regret reduction 10%; Full must also be AUC-nonnegative on at
least 3/4 tasks and the effect cannot occur only on V0. Otherwise select the
simpler no-REFINE method.

### Frozen third-source gate

After development freeze: at least one third-source query must reach
`Delta AUC >=0.01` or `Delta F1 >=0.02`; at least 4/6 total tasks must satisfy
the noninferiority margins above; macro AUC and F1 differences must be
nonnegative and at least one efficiency metric (TTFC, regret, or events/call)
must improve. No threshold or model may be retuned.

### Uncertainty

Report paired task values, macro/median/worst task, and a 95% percentile
bootstrap interval formed by resampling independent tasks only. With four
development tasks the interval is descriptive and cannot override the effect,
cross-source, safety, or third-source gates. Physical repeats are never
bootstrapped.

## Claim-status ledger

| Candidate statement | Current status | Evidence needed to promote it |
|---|---|---|
| The legacy rule-based two-video search is not a positive core method. | Established within the frozen legacy contract. | Preserve existing negative artifacts; no retuning. |
| Immutable opportunity binding and earlier clock placement are implementation-tested. | Established in unit/source tests only. | Preserve hashes and tests. |
| The repaired contract is physically valid end to end. | Unestablished. | Trace-level deadline/identity/snapshot audit on every new method. |
| MF-PSVR improves cross-video anytime event recovery. | Unsupported. | Paired physical V0/V1 results and uncertainty at the task level. |
| Query-conditioned REFINE independently contributes. | Unsupported. | No-REFINE, shuffled-query, score-only, cost-matched, and model-capacity ablations. |
| Co-scheduling beats adaptive scan/configuration/planning priors. | Unsupported. | ExSample/Zeus/FiGO plus applicable native-cost or mechanism controls under disclosed contracts. |
| Results generalize to an unseen source. | Unsupported. | One preregistered third-source evaluation after method freeze. |
| The systems bundle is novel. | Unresolved. | Positive mechanism evidence plus broader primary-source/citation-chain review and adversarial external review. |

## Rejection and revision triggers

Reject the positive MF-PSVR candidate, or narrow it to a measurement paper, if
any of these observations occurs:

- independent training sessions do not contain enough Q1/Q2 positives to
  estimate grouped generalization without target leakage;
- candidate-value or REFINE gains vanish under leave-source-out evaluation;
- a simple, Zeus-style, or FiGO-style control matches under the fixed practical
  equivalence rule above;
- gains require per-video/per-query threshold tuning;
- strict deadline misses, commit overhead, or failure retention erase utility;
- the frozen third source fails the quantitative gate above;
- later primary literature contains the same execution/output contract and
  method bundle;
- EventRelation confirmation cannot be mapped consistently across methods.

## Next highest-value action

Before training a complex controller, construct and freeze the independent
DrivingDojo/source-session manifest, generate immutable candidate witnesses, and
measure per-source and per-query oracle-positive counts. This single measurement
tests the central assumption that a query-aligned, leakage-free semantic model
is identifiable. If class support is inadequate, the program must pivot before
spending substantial training or physical-oracle budget.
