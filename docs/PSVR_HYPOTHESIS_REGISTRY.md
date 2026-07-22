# PSVR Hypothesis Registry

## H-RECOVER1 — Two-video recoverability and bottleneck audit

- Status: `COMPLETE_HETEROGENEOUS_BOTTLENECK`.
- Evidence: evaluator-only reuse of 72/72 valid H-EXPOSE2 traces; 2,772 chain rows and zero new physical calls.
- Result: V0_Q1 VERIFY-order limited; V0_Q2 scan-exposure limited; V1_Q1 scan-exposure limited; V1_Q2 floor only at the original fixed 12-scan ceiling.
- Limitation: reference-side ceilings are diagnostic and global conversion ratios apply only to already exposed positives.

## H-BOTTLE2 — Scan × VERIFY two-video factorial

- Status: `REJECT_FIXED_FACTORIAL_HETEROGENEOUS_BOTTLENECK`.
- Evidence: 96/96 physical cells; 24/24 C00 historical equivalence; zero failure, miss, replay, future access, visibility violation, missing snapshot, or invalid ledger.
- Result: S1 max-gap, V1 cell-diverse, and their combination improve no V1 task and fail all four substantive thresholds. Scan, VERIFY, and interaction signals are absent.
- Consequence: the independently frozen heterogeneous ceiling selects only H-STAGE1; fixed-factor tuning ends.

## H-STAGE1 — Observable stage-conditioned controller

- Status: `REJECT_NO_CROSS_VIDEO_QUALITY_SIGNAL`; route terminal.
- Evidence: 48/48 physically valid cells, 24/24 F0-C10 behavioral endpoints, zero safety/durability failures. Exact query signatures agree in 14/16 cells and semantic snapshots in 16/16.
- Quality: ST1 wins only V0_Q2. Macro AUC gain is 5.75%, F1 gain 0.0192, TTFC worsens, and total unique-event gain is one; all thresholds fail. V1 recovers zero events in 12/12 ST1 cells.
- Mechanism: V1_Q1 creates positive candidates but admits none to the frontier; V1_Q2 admits/survives some positives but verifies none. Residual bottleneck is heterogeneous frontier retention plus VERIFY allocation.
- Procedural limitation: the cycle required two preregistered validity repairs and failed the stricter exact-repeat condition. This precludes acceptance but does not weaken the conservative negative result.
- Consequence: no ablation or revision is triggered; `PSVR_TWO_VIDEO_SEARCH=NO_GO`.

## H-EXPOSE2 — Candidate exposure with fixed R3 temporal NMS

- Status: `REJECT`; revision 1 is terminal.
- Frozen revision: R3 `exposure_temporal_nms`, fixed 10-second window; no other scheduler,
  proxy, scanner, allocator, or weight change.
- Physical evidence: 72/72 valid cells (3 methods × 4 tasks × 2 deadlines × 3 repeats),
  complete schedules/snapshots, zero failure, duplicate, deadline miss, replay, future access,
  visibility violation, or invalid action ledger.
- Reference-scored result: R3 improves 0/4 tasks over each task's best baseline. Its macro
  AnytimeAUC_F1 is 0.0174505 versus FIFO 0.0450066; macro F1 is 0.0208333 versus 0.0541667;
  censored TTFC is 136.269 s versus 110.821 s. All four substantive thresholds fail and
  there is no V1 contribution.
- Mechanism interpretation: FIFO's V0_Q1 hit is a true reference match at unit 173 caused by
  creation-order VERIFY. Score-only and R3 choose higher-scored negative unit 86. Capacity
  does not bind and candidate creation/reference matching are shared.
- Competing explanation: conservative scan planning exposes no reference-positive V1 unit,
  so V1 nulls do not uniquely diagnose frontier quality. This prevents a positive mechanism
  claim but does not change the preregistered rejection.
- Consequence: `TWO_VIDEO_CORE_SIGNAL=ABSENT`; ablation not run; no second revision. A third
  independent source is required before considering a materially different core route.

## H-DS1 — Tail-aware verify-to-commit admission

- Status: ACCEPTED FOR DEVELOPMENT under protocol `h_ds1_tail_guard_v2_persistent_k3`
- Stage: deadline safety
- Hypothesis: A workload-matched upper bound over the complete physical VERIFY path, combined with an independent durable-commit reservation, eliminates hard-deadline misses at T_short without eliminating all T_mid verification utility.
- Motivation: The rejected pooled-p95 guard admitted a path with at most 0.236 s predicted slack; physical VERIFY was 21.436 s versus a 15.671 s p95 from a mismatched Qwen-only profile.
- Mechanism: clean physical observations; upper = observed max + 0.90 quantile (higher method) of positive residuals above the median + frozen epsilon (`0.50 s` VERIFY, `0.25 s` commit). Admission is strict only when remaining > action upper + commit upper. Persistent K3 and selector workers start before the deadline inside empty chroots; all admission/VERIFY ledger fsyncs happen after the durable result snapshot.
- Changed variables: latency estimator, workload identity validation, action admission, ledger timestamps.
- Frozen variables: video, query, Qwen checkpoint, prompt, parser, frame sampling, YOLO checkpoint, batch=4, K3, reference, hardware, coarse scan definition. Runtime identity binds current hashes, package versions, warm-up policy, and serving topology.
- Baseline: rejected pooled operator-p95 guard preserved in `outputs/psvr_physical_smoke_test/`.
- Expected signature: unsafe T_short VERIFY is rejected; zero misses/incomplete snapshots/unsafe admissions in 10 physical T_short runs; at least one T_mid run admits a physical VERIFY.
- Failure conditions: any T_short deadline miss, incomplete snapshot, unsafe admitted action, cache/replay contamination, leakage, or zero T_mid physical VERIFY across the regression set.
- Profiling strata: 20 valid same-topology paths; units 50/57/60 are explicitly included with four proxy timestamps inside the same 10 s unit, then remaining units use proxy-only ranking. Parse failures and contaminated/incomplete calls are retained but cannot enter the profile.
- Invalidated attempt: `h_ds1_tail_guard_v1` retained one useful physical diagnostic, but per-commit process/import initialization made its 14.525 s K3 path a different workload. It is never mixed or resumed.
- Exact planned commands:
  - `PYTHONPATH=src pytest -q tests/psvr_runtime`
  - `python scripts/run_deadline_safety_validation.py pilot --runs 1`
  - `python scripts/run_deadline_safety_validation.py profile --runs 20`
  - `python scripts/run_deadline_safety_validation.py short --runs 10`
  - `python scripts/run_deadline_safety_validation.py mid --runs 3`
  - `python scripts/run_deadline_safety_validation.py finalize`
- Acceptance: `PSVR_DEADLINE_SAFETY=PASS`; utility is PASS if confirmed-event rate >0, WEAK if safe calls occur but no confirmation, FAIL if no physical VERIFY is admitted at T_mid.
- Result (2026-07-15): 20/20 valid physical profile observations, 10/10 T_short runs, and 3/3 T_mid runs. There were zero misses, incomplete snapshots, unsafe admissions, tail exceedances, cache replays, future-proxy accesses, or runtime failures. T_mid admitted 3/3 physical VERIFY calls but confirmed no event. Therefore `PSVR_DEADLINE_SAFETY=PASS` and `PSVR_SHORT_DEADLINE_UTILITY=WEAK`.
- Scope limitation: empirical development safety for one video/query/A800 workload, not a formal WCET guarantee.

## H-COV1 — Coverage-Debt Progressive Scan

- Status: REVISE; core pilot is WEAK
- Stage: core innovation physical pilot
- Hypothesis: while proxy evidence is only partially materialized, scheduling cells by unobserved duration, hierarchical scan debt, and already-observed local proxy signal recovers oracle-defined events earlier than sequential, uniform-temporal, and fixed coverage baselines.
- Frozen design: `priority = normalized_unobserved_duration + 0.5 * scan_level_debt + 0.25 * observed_local_proxy_signal`; batch=4; no future proxy; physical Qwen; unchanged K3; H-DS1 guard; T_short/T_mid/T_long; three physical runtime replicates per cell.
- Physical evidence: 45 total Stage-2 runs (36 baseline, 9 Coverage-Debt), zero misses/replays/causality violations, one runtime identity. Coverage-Debt recovered one unique event in all three T_long runs (F1=0.074074, recall=0.038462, precision=1.0; six physical calls) while every simple baseline recovered zero.
- Supported conclusion: Coverage-Debt is the current best development method by macro wall-clock AnytimeAUC_F1 (0.002822 versus 0 for simple baselines).
- Contradictory mechanism evidence: its macro maximum-gap integral is 0.158263, worse than Uniform-Temporal (0.156310) and fixed Coverage-Interleave (0.151569). Its endpoint gaps equal Uniform-Temporal (430/210/200 s) and are worse than fixed Coverage-Interleave (20 s at all deadlines).
- Decision: `H-COV1=REVISE`, not ACCEPT. The quality gain is real in these artifacts, but the preregistered gap condition is false.
- Parameter revision: not run. Changing lambda/beta cannot overcome fixed Coverage-Interleave's 20 s gap while the alternating design scans only 2.31%/4.62%/8.08% of units. A repair requires a different scan/verify action allocation and therefore a new predeclared design, not post-hoc tuning.
- Main alternative explanation: the single recovered event may be a deterministic single-video ranking coincidence; runtime repeats are not independent video/query samples.
- Rejection/revision trigger: reject the route if a predeclared coverage-first/debt-refinement ablation fails to retain the event gain while matching the fixed coverage gap trajectory under equal deadline and accounted GPU cost.

## H-FACT1 — Scan scheduler × action allocation factorization

- Status: VALID; Branch A; `COMPOSITE_SCAN_SIGNAL=PRESENT`.
- Question: does the Stage-2 quality signal arise from the composite scan-cell order S1, adaptive scan/VERIFY allocation A1, or their interaction?
- Frozen factorization: C0=S0+A0, C1=S1+A0, C2=S0+A1, C3=S1+A1. A0 is the Stage-2 Coverage-Interleave fixed 29-SCAN then VERIFY schedule; A1 is the current state-dependent alternating rule. C0 and C3 are behavior-equivalent to their Stage-2 counterparts.
- Physical evidence: four valid smoke runs followed by exactly 36 matrix runs (4 methods × 3 frozen deadlines × 3 runtime repeats), reaching the 40-run cap. There were zero failures, deadline misses, cache replays, future-proxy accesses, or candidate-observation violations under one runtime identity.
- Decisive result: at T_transition and T_high, C1 recovered `vlm_event_0022` in 3/3 repeats while C0 recovered none; C2 matched C0 at zero; C3 recovered `vlm_event_0004` in 3/3 repeats. All methods recovered zero at T_low. Within every method/deadline cell, semantic event sets and exact action traces were consistent.
- Supported conclusion: the S1 composite scan ordering has a marginal development quality signal under fixed A0. This is Branch A, not evidence for an allocation-only effect or an interaction-only effect.
- Scope limitation: one video-query is one semantic sample; repeats measure runtime stability only. H-COV1 remains REVISE, because H-FACT1 does not identify which S1 component is causal and does not establish generalization.
- Main alternative: the two recovered events may be deterministic ranking coincidences on this development video.
- Next discriminating action: in a later bounded cycle, preregister a scan-priority component ablation separating duration, hierarchical debt, and observed local proxy signal. No tuning or multi-video execution occurred in H-FACT1.

## H-SCAN-COMP1 — Scan-priority component attribution

- Status: VALID; `SCAN_COMPONENT_ATTRIBUTION=DEBT`; `DEBT_COMPONENT_SIGNAL=PRESENT_ON_CURRENT_DEV_TASK`.
- Frozen question: under the same A0 fixed allocation, is the C1 signal dependent on duration, hierarchical debt, proxy signal, or their interaction?
- Design: reuse S0=C0 and S1=C1 at T_transition/T_high after exact config/hash audit; add S2=duration+proxy, S3=duration+debt, and S4=debt+proxy. New matrix was exactly 3 methods × 2 deadlines × 3 runtime repeats = 18 physical runs.
- Validity: 18/18 new runs completed under one runtime identity with zero failures, deadline misses, replay, future access, or candidate-observation violations. The 18-run physical cap was reached without extras.
- Decisive pattern: S0 0/6; S1 6/6; S2 0/6; S3 6/6; S4 6/6. S2 failed even with five VERIFY calls at T_high, while S3/S4 confirmed within four/three calls, ruling out admitted-call count as the explanation.
- Event paths: S1 and S4 recover unit 317 (`vlm_event_0022`); S3 recovers unit 246. Debt is the shared retained component, but a debt-only arm was not tested, so necessity within this component family is supported while standalone sufficiency is not.
- Narrow hypothesis registered: with fixed VERIFY allocation, the debt term changes hierarchical refinement order such that reference-positive regions reach the visible candidate frontier earlier. Status is candidate for multi-task validation, not ACCEPTED.
- Alternative explanation: debt ordering may align fortuitously with event locations on this one development video-query.
- Next gate: `MULTI_TASK_SCAN_SIGNAL` using at least three independent videos × at least two queries, with selected debt-bearing scan, Fixed Coverage, and Uniform Temporal. H-SCAN1 may become `ACCEPT_CANDIDATE` only if at least two independent video-query tasks show consistent direction and removing debt reduces utility.
- Stop rule: no further single-video tuning, weight search, or second component ablation.

## H-SCAN1A — Structural versus observed-proxy group ablation

- Revision: 0.
- Status: `ACCEPT_STRUCTURAL_SIGNAL`; Branch S-A; `COVERAGE_STRUCTURAL_SIGNAL=PRESENT`; `H-COV1=REVISE_MORE_SPECIFIC`.
- Claim tested: under frozen A0, does C1 quality derive from the proxy-independent structural group (`span/N + 0.5 log2(span+1)/log2(N+1)`), the observed local proxy group (`0.25 local_signal`), or their interaction?
- Arms: D0=fixed Coverage; D1=full; D2=structural only by exact proxy contribution zeroing; D3=proxy only by exact structural zeroing. D1/D2/D3 share eligible midpoint cells, hierarchy, normalizations, tie-break and fallback. D0 retains H-FACT1 C0's fixed grid, so four-way identical eligibility is incompatible with D0 equivalence and was explicitly marked not applicable.
- Correctness: 47 tests; six H-FACT1 C1 runs replayed without scheduler mismatch; 174 visited states and 9,630 eligible-cell decompositions checked with maximum absolute error 2.78e-17. D1 physical smoke exactly matched C1 scan, proxy, five query targets and snapshot-event sequence.
- Physical evidence: 4/4 valid smoke plus 24/24 valid formal runs, exactly 28 physical runs. Zero failure, deadline miss, replay, future access, visibility violation, or incomplete snapshot under one runtime identity.
- Formal effectiveness: D0 0/6, D1 6/6, D2 6/6, D3 0/6. D2 mean AnytimeAUC_F1=0.021592 and median TTFC=86.86 s versus D1 0.018749 and 89.23 s. D2 recovers `vlm_event_0017`; D1 recovers `vlm_event_0022`.
- Mechanism: D1/D2 expose 17 positive cells and have max gap 40 s; D3 exposes 9 and has max gap 1725 s despite identical 29 scan batches and five VERIFY calls. D3 never promotes a reference-positive cell to the visible candidate frontier.
- Tie limitation: D2's winning unit lies in an equal-structural-priority batch. Its within-batch order does not control exposure, but tie-break controls equal-score cutoff membership. The result is conditional on the frozen hierarchy and ascending-unit tie-break.
- Prior-evidence disclosure: a different related Stage-4 component experiment existed before this preregistration and is preserved under `stage_4_prior_debt_component_ablation`; H-SCAN1A's 28 new runs are prospective but not interpreted as blind to that evidence.
- Scope: one semantic video-query. Runtime repeats establish stability, not generalization. `PSVR_CORE_INNOVATION_PILOT=WEAK` and usable-method status remains NOT_YET.
- Historical next action (completed in Cycle 05): register H-SCAN1B to test exact-tie robustness before any factorial split.

## H-SCAN1B — Exact-tie robustness gate

- Revision: 0.
- Status: `FAIL_TIE_ROBUSTNESS`; `STRUCTURAL_TIE_ROBUSTNESS=FAIL`; `H-COV1=REVISE_TIE_SENSITIVE`.
- Frozen comparison: D2 + A0 under TB0 ascending deterministic tie, TB1 reverse deterministic tie, and TB2 preregistered deterministic seeded-hash tie.
- Physical evidence: 9/9 valid runs; TB0 recovered one event in 3/3, TB1/TB2 recovered none in 0/6; zero failure, deadline miss, replay, future access, or visibility violation.
- Mechanism: all orders reached equal final coverage and maximum gap and touched several reference-positive units, but only TB0 promoted unit 246 into the VERIFY frontier in time to confirm `vlm_event_0017`.
- Decision: the one-task D2 signal is path/tie-sensitive. Do not claim a general structural scan mechanism or run the forbidden U×L factorial on this gate result.
- Scope: one video-query; runtime repeats are not independent semantic samples.

## H-TIE1 — Multi-task tie/path validation

- Status: `SUSPENDED_INPUT_REQUIRED`, not rejected.
- Required input: three independent source videos, at least two frozen queries, six valid oracle-defined video-query tasks, and common task deadlines.
- Resume condition: Phase-A source gate passes, then Phases B-E freeze queries, references, tasks, and deadlines.

## BENCHMARK_UNBLOCK — Bounded independent-source inventory

- Status: `PAUSED_INPUT_REQUIRED`; `BENCHMARK_INPUT_POOL=INSUFFICIENT`.
- Hypothesis: the permitted local/configured pool contains at least two additional independent long sources beyond dataset3.
- Falsifying observation: 609 rows / 607 existing paths yielded only one eligible source. Nexar has 604 paths / 603 unique hashes but a maximum duration of 49.464883 seconds; known alternatives are missing, derived, short, held-out, or semantically unsuitable.
- Decision: hypothesis rejected for the present local state; this is an external-input pause, not project `NO_GO`.
- Next exact command: `python scripts/audit_psvr_dev_inputs.py`.

## H-PP0 — Partial-proxy regime

- Status: ACCEPTED FOR DEVELOPMENT
- Evidence: Regime-B T_min=29.829949 s, T_max=123.952474 s, normalized width=0.759344 with Qwen resident during proxy measurements.
- Scope: one video, one query, A800 only.

## H-P95 — Independent operator p95 guarantees a hard deadline

- Status: REJECTED
- Reason: T_short physical miss at 35.663871 s; VERIFY residual +5.765303 s relative to the admitted p95 estimate.
