# SCAN–CONFIRM Decision Benchmark Contract V1

Status: `FROZEN_BEFORE_CONTROLLER_EVALUATION`  
Benchmark: `SCAN_CONFIRM_DECISION_BENCHMARK_V1`  
Research problem: `DEADLINE_AWARE_SCAN_CONFIRM_ACTION_SELECTION`

## Research question and scope

Under a hard, non-preemptive wall-clock deadline, can a causal myopic
value-per-second controller choose among SCAN, CONFIRM, and STOP more reliably
than fixed wall-clock allocation rules when the SCAN order, candidate generator,
Frontier, semantic Oracle, parser, event materializer, and durable commit are all
frozen? This is a two-video/four-query development mechanism pilot. Test data
remain sealed; cross-video generalization is not an available claim.

The frozen SCAN primitive is the public-state-only `ANYTIME_LARGEST_GAP`
midpoint traversal. Video identity cannot select a mode. Alternative scan modes
are evaluation baselines only. YOLO-guided region scheduling is closed. RL,
bandits, SMDPs, and a CONFIRM cascade are outside this contract.

## Frozen assets and identification

The source videos are V0 and V1 in
`outputs/psvr_two_video_loop/dev_benchmark_v1/VIDEO_MANIFEST.json`; the four
groups are V0_Q1, V0_Q2, V1_Q1, and V1_Q2. The frozen Y8 proxy extraction is
identified by `FINAL_PROXY_CONFIG.json`. Its unit-local ByteTrack reset makes an
arbitrary temporal order causal. The exhaustive physical Qwen3-VL-32B traces
and projected task labels in `dev_benchmark_v1` identify every unit's CONFIRM
outcome. Reference events are independently materialized from exhaustive
Oracle outputs, not from SCAN candidates.

The decision benchmark uses unit-level Candidate Witness clusters, matching the
frozen PSVR Frontier identity `(video, query, unit, bound_track)`. Candidate to
reference-event association is evaluator-only through the frozen source-unit
lineage. It is never policy input. Positive CONFIRM observations are passed to
the unchanged `consecutive_positive_units_v1`/`k3_bridge_safe` semantics;
utility is the number of distinct reference events durably recovered.

Main execution is strict trace replay: each SCAN uses its unit's measured
decode, detector, tracking, scoring, serialization, and scheduler obligation;
each CONFIRM uses its unit's physical inference time plus frozen parse,
materialization, snapshot, fsync, atomic rename, Frontier update, and scheduler
obligation. Thus action outcomes are complete and costs are measured physical
trace costs, while simultaneous end-to-end wall-clock support is initially
`APPROXIMATE` until an independently reset combined physical validation is run.
Replay never invokes a new Oracle.

## State, history boundary, and actions

At decision time `t`, `s_t=(b_t,C_t,F_t,H_t)`. Public fields are exactly those
in `outputs/scan_confirm_decision_v1/contracts/public_state_schema.json`:
remaining budget; coverage fraction and maximum unobserved gap; completed SCAN
count/time; Frontier size and score summaries; candidate ages; observed novel
cluster count; confirmed distinct utility; causal recent-yield summaries;
causal conservative cost estimates; completed action count; unused budget.

Video ID, filename, source dataset ID, reference locations, total event count,
future candidates/outcomes/costs, offline Oracle order, and held-out results are
forbidden policy inputs. IDs are retained only outside the controller for group
reset and reporting.

`SCAN` executes one complete AnytimeLargestGap microchunk. `CONFIRM` atomically
selects the highest-score legal retained witness, runs the frozen outcome,
parse/materialize/deduplicate/commit path, then terminalizes that witness.
`STOP` starts no action and returns the last durable snapshot. The controller
does not choose SCAN location, Frontier admission/retention, or CONFIRM target.

## Frontier lifecycle

Admission uses the frozen visible-candidate generator after a durably completed
SCAN. One bound top-track witness is retained per unit. Deduplication is the
frozen 10-second unit/candidate-cluster identity; already queried witnesses are
ineligible. Retention is score descending with deterministic `(unit_id,
track_id,candidate_id)` ties and capacity 10. Scores may be recomputed only from
currently visible candidates. There is no outcome-dependent aging eviction.
CONFIRM selects the highest frozen score. These rules are hashed separately and
cannot be changed by Myopic-VPS.

## Costs and deadline admission

Actions are indivisible. For action `a`, the causal conservative estimate
`cbar_t(a)` is the preregistered 0.90 empirical quantile of completed same-type
costs, falling back to the frozen development global quantile. An action is
legal iff `cbar_t(a) <= remaining_budget_sec`. If neither complete action fits,
STOP. A started action completes and its full measured cost is charged even if
the realized trace exceeds the estimate; such cases are recorded as deadline
overruns. No partial SCAN or CONFIRM exists. Final STOP durably records state.

SCAN accounting includes validation, seek/decode, Y8, tracking, candidate
generation, Frontier update, scheduler, serialization, and commit. CONFIRM
includes validation, physical Oracle inference, parse, resolution,
materialization, deduplication, snapshot/fsync/atomic commit, Frontier update,
and scheduler. All ledgers record estimated/actual cost, start/completion,
rejection, overrun, cumulative time, remaining time, and unused budget.

## Utility, budgets, metrics, and resets

Primary utility is `DISTINCT_CONFIRMED_EVENTS_AT_DEADLINE`. Budgets are 30, 60,
120, and 240 seconds, provided at least one action is admissible. Every
video/query/budget/seed run independently resets environment, Frontier,
coverage, posterior, and cost state. No long-budget result is truncated to
stand in for a short-budget run.

The primary curve is `U_pi(B)` and primary AUC is trapezoidal utility over the
four deadline points, macro-averaged over video/query groups. Secondary metrics
are time to first utility, SCAN/CONFIRM wall-clock, Oracle calls, generated
clusters, duplicates, zero-yield actions, deadline rejections/overruns, unused
budget, maximum gap, Frontier occupancy, event recall/F1, and their deadline
AUC where defined.

## Controllers and baselines

Required policies are R0 SCAN-first, R1 CONFIRM-first, R2 75:25, R3 50:50, R4
25:75, R5 periodic alternating, R6 Frontier-empty-SCAN-otherwise-CONFIRM, R7
random legal action, and R8 Myopic-VPS. Ratios use cumulative realized SCAN
wall time divided by SCAN+CONFIRM wall time; they are not action-count ratios.
All policies share every frozen operator and reset.

ARC is formal only if video, query, candidate universe, Oracle, Frontier, SCAN,
CONFIRM, reference, deadline, materialization, commit, and hardware are all
identical. Otherwise its result is context only and no formal delta is reported.

## Myopic-VPS and preregistered estimators

For SCAN, `X` is newly admitted distinct witness clusters. With
`lambda~Gamma(alpha_s,beta_s)`, the posterior mean is
`(alpha_s+K_s)/(beta_s+n_s)` and `VPS_scan=lambda_hat/c_hat_scan`. Coverage
buckets are LOW `[0,1/3)`, MEDIUM `[1/3,2/3)`, HIGH `[2/3,1]`; a bucket with
fewer than three completed actions falls back to the global posterior.

For CONFIRM, `Y=1` iff the atomic action adds a new distinct reference event.
With `p~Beta(alpha_c,beta_c)`, the posterior mean is
`(alpha_c+K_c)/(alpha_c+beta_c+n_c)` and
`VPS_confirm=p_hat/c_hat_confirm`. Frozen score buckets are LOW `[0,1/3)`,
MEDIUM `[1/3,2/3)`, HIGH `[2/3,1]`; fewer than three observations falls back
globally.

At most two priors are development candidates: uninformative
`alpha_s=beta_s=alpha_c=beta_c=1`, and global empirical prior with strength 2.
Margins are 0 and 0.001 utility/sec. Development selection is macro AUC with
deterministic lexical tie-break. The chosen setting is frozen before any future
validation/test. Default ties choose SCAN. The action rule is exactly the rule
in the task specification, including Frontier-empty and legality fallbacks.

No current-video future is used for initialization. Maximum search budgets are
2 priors, 2 margins, 4 state bucket schemas, 16 total Myopic settings, one
engineering repair cycle, and one future formal test evaluation.

## Offline action Oracles

`ONE_STEP_ACTION_ORACLE` is evaluator-only and chooses the legal action with
largest realized immediate new utility per realized second, deterministic SCAN
tie-break. `MULTI_STEP_TRACE_ORACLE` is evaluator-only beam search over the full
future deterministic trace state and maximizes final utility; beam width and
whether exactness was achieved are reported. Neither Oracle output, order,
cost, nor statistic enters online state, priors, or selection.

## Ablations, statistics, and gates

A0 is full Myopic-VPS. A1 removes cost normalization; A2 removes shrinkage; A3
uses global SCAN yield; A4 global CONFIRM rate; A5 removes coverage buckets; A6
removes score buckets; A7 sets margin zero; A8 switches tie-break; A9 removes
remaining-budget use from value choice while retaining mandatory admission;
A10 replaces action-specific realized trace costs in the cost estimator with
the frozen global median. Exactly one mechanism changes per ablation.

Inference uses video/query groups, never action rows: 10,000 paired group
bootstrap draws, percentile 95% CIs, per-group deltas, group win rate, median
delta, leave-best-group-out, best-group contribution, and budget contribution.
With only four development groups, `STATISTICAL_POWER=LIMITED`.

Myopic is established only if all eight gates in the user specification pass:
positive macro AUC against the strongest fixed ratio; majority nonnegative
groups; no systematic low-budget loss; positive full-cost delta; positive
leave-best-group-out; best-group contribution below 0.50; no single-budget
driver; and measurable offline-Oracle headroom. Failure selects the strongest
fixed allocation, keeps contextual bandits/SMDPs deferred, and prohibits RL.
SMDP can only be proposed in a new contract if multi-step headroom and stable
long-horizon errors satisfy all four specified conditions.

Immediate scientific stop conditions are unidentifiable utility, incomplete
action outcomes, leakage, required Frontier/CONFIRM changes, single-group-only
improvement, persistent low-budget harm, nonpositive full-cost gain, uniformly
stronger fixed allocation, or exhausted search budget. One controlled repair
may address only paths, schemas, trace alignment, accounting, mapping,
admission, numerics, cache integrity, or determinism and must be logged with
before/after hashes and reruns.

## Claim scope and deliverables

This contract permits only a development mechanism-pilot claim. Formal
generalization remains not established because no independent validation video
is available and test remains sealed. Physical trace replay and any new
end-to-end physical validation are reported separately.

Required implementation, audit, benchmark, baseline, Myopic, Oracle, ablation,
statistics, physical-validation, metric, report, environment, version, repair,
and artifact-hash outputs are those enumerated in the task specification under
`src/garc_eval/scan_confirm_controller`, `configs`, `scripts`, and
`outputs/scan_confirm_decision_v1`.

This file is immutable after its SHA-256 is entered in
`outputs/scan_confirm_decision_v1/contracts/freeze_manifest.json`. Any allowed
repair creates an amendment record; it never edits this contract silently.
