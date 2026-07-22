# PSVR Failure Catalog

## F-BOTTLENECK-01 — Fixed scan/VERIFY factors do not realize recoverability ceilings

- Symptom: C10, C01, and C11 reproduce C00's macro F1 and unique-event outcome; V1 remains zero.
- Cause supported: max-gap scan and cell-diverse FIFO do not alter the relevant frontier/VERIFY path.
- Lesson: evaluator recoverability is not evidence that a particular reference-blind fixed factor can realize it.

## F-STAGE1-01 — Exposure improves without V1 event conversion

- Symptom: ST1 scans positive V1 units in every task aggregate yet recovers zero V1 events in 12/12 cells.
- V1_Q1 chain: positive unit → candidate succeeds; frontier entry fails because capacity retention discards the positive.
- V1_Q2 chain: some positive candidates enter and survive; none are selected for VERIFY before physical stop.
- Lesson: the workload is heterogeneous across frontier retention and VERIFY order/budget; more actions alone do not form a cross-video rule mechanism.

## F-STAGE1-02 — Exact physical repeat signature and repair-discipline deviation

- Symptom: 14/16 exact query signatures agree; V1 transition runs execute 8 versus 9 tail calls depending on physical latency.
- Additional deviation: profile freshness and fixed-control target restoration required two validity repairs in one cycle.
- Consequence: positive acceptance is forbidden. Semantic snapshots remain 16/16 consistent, so the negative result is retained with reduced evidence level.

## F-EXPOSE-001 — Candidate-exposure route fails cross-video gate

- Status: TERMINAL SCIENTIFIC REJECTION after the only allowed revision.
- Observation: R3 fixed 10-second temporal NMS has 0/4 positive-direction tasks, passes none
  of the preregistered quality thresholds, and yields no V1 reference-matched event.
- Negative control: all 72 cells are valid with matched scan/VERIFY opportunities, capacity,
  proxy observations, and zero safety/causality violations.
- Failure localization: on V0_Q1, FIFO creation order verifies true-positive/reference-matched
  unit 173; score-only and R3 rank negative unit 86 first. Unit 173 is retained, so capacity
  or frontier eviction does not explain the miss.
- Limitation: FIFO's apparent advantage is itself a single-event V0 coincidence and does not
  establish a generalized FIFO method. V1 scan plans expose no positive reference unit.
- Consequence: do not ablate, tune NMS, alter equal weights, or start a new route on V0/V1.
  Pause until a third independent source video is available.

## F-DS-001 — T_short unsafe VERIFY admission

- Status: OPEN; permanent negative sample retained
- Run: `Coverage-Interleave__T_short`
- Deadline: 30.778410 s at execution; final refrozen approximation 30.829949 s
- Coarse: 13.457909 s
- validation-anchor scan: 0.405684 s
- predicted guard: 16.679299 s
- physical VERIFY: 21.436421 s
- K3: 0.033795 s
- snapshot: 0.001517 s
- final wall: 35.663871 s
- final-deadline miss: 4.833922 s
- Root cause supported: Qwen-only pooled p95 reused for Qwen+YOLO-resident, post-coarse, first-oracle workload; small-sample p95 was treated as a guarantee.
- Additional undercount: lookup/prompt read, cleanup after the recorded action duration, raw-response fsync, and bookkeeping.
- Rejected explanation: K3/snapshot is the dominant cause.
- Revision trigger: H-DS1 must produce zero misses in 10 independent T_short physical runs.

## F-STATE-001 — Conflicting Stage 0 machine-readable status

- Status: OPEN
- `benchmark_manifest.result`, legacy `provenance_audit`, and legacy `leakage_test_report` describe the quarantined runner's initial failure while newer split reports pass.
- Required repair: preserve the negative files but add explicit supersession/legacy scope and make the manifest's authoritative status unambiguous.

## F-EVIDENCE-001 — No cross-video inference yet

- Status: OPEN LIMITATION
- Current PSVR physical evidence is one source video × one query. It cannot support paper-level cross-video claims.

## F-DS-002 — Per-commit K3 spawn was not the deployed workload

- Status: CLOSED BY PROTOCOL REPLACEMENT; raw evidence retained
- Run: `h_ds1_tail_guard_v1/raw/profile/sample_000.json`
- Observed commit: 14.525233 s, of which 14.517971 s was materializer process/import startup plus K3.
- Consequence: the sample cannot enter a persistent-K3 latency profile.
- Repair: new experiment directory and workload identity `h_ds1_tail_guard_v2_persistent_k3`; persistent worker starts before the deadline and accepts only queried evidence plus exact public unit metadata.

## F-BL-001 — Fixed +5 s scan exceeded the final truncated unit

- Status: CLOSED BY DIRECT FAIRNESS REPAIR; all pre-fix evidence invalidated and retained
- Failed run: `stage_2_baselines/invalidated_last_unit_midpoint_v0/raw/scan_then_verify__T_mid__replicate_00/attempt_001`
- Observation: final unit 346 ends at 3462.93 s, but the initial pilot used `start_time + 5.0`, requesting a frame beyond the physical video. The final batch had 3 requested/decoded rows but one failed decode and zero valid scores.
- Repair: use `start_time + duration_seconds/2` for every unit, including the truncated final unit; rerun all 36 baseline cells from empty corrected state.
- Retention: 260 pre-fix files remain under `invalidated_last_unit_midpoint_v0` and do not enter any result table or decision.

## F-COV-001 — Coverage-Debt quality gain without best gap trajectory

- Status: OPEN RESEARCH FAILURE / REVISION TARGET
- Evidence: Coverage-Debt macro gap integral 0.158263 versus Uniform-Temporal 0.156310 and fixed Coverage-Interleave 0.151569, despite macro AnytimeAUC_F1 0.002822 versus 0.
- Interpretation: observed signal changed verification value, but the alternating action allocation did not improve coverage debt beyond simple farthest-point scanning and could not match the fixed coarse grid.
- Rejected claim: H-COV1 is not accepted merely because one event was recovered.
- Next discriminating action: suspended until benchmark expansion. Do not run another single-task coverage/debt revision; first establish multi-task inputs and test tie/path robustness.

## F-EVAL-001 — Generated early-recall diagnostic used row order

- Status: CLOSED BY AUDIT SUPERSESSION; decision unaffected
- Observation: `stage_2_baselines/DECISION.json` reports `early_recall_gain_vs_best_simple=0.0192308`, but the aggregation selected the first six lexicographically ordered rows, which include T_long.
- Correct value: mean recall over T_short and T_mid is 0 for every method; early-recall gain is 0.
- Consequence: do not cite the generated early-recall field. The quality condition remains true independently because Coverage-Debt macro AnytimeAUC_F1 is 0.002822 versus 0.

## F-HFACT-001 — Stage-3 manifest omitted two runtime identity fields

- Status: CLOSED BEFORE PHYSICAL EXECUTION; preflight artifact retained.
- Observation: the first C0 smoke attempt failed before runtime startup because `video_sha256` and `query_id` were omitted when copying the immutable Stage-2 runtime identity into the Stage-3 manifest.
- Evidence of zero physical consumption: the inherited runner failed while constructing `RuntimeIdentity`, before its protected runtime block; no oracle service or invocation existed. The attempt is retained as `preflight_failed.json` and is not counted toward the 40 physical runs.
- Repair: copy the two existing Stage-2 identity fields without changing the identity hash, deadlines, factors, or operators; then freeze the resolved config before the first physical run.

## F-EVAL-002 — Per-run generated event IDs are not semantic event-set keys

- Status: CLOSED BY AUDIT SUPERSESSION; primary metrics and Branch A unchanged.
- Observation: the initial Stage-3 aggregate compared generated `event_id` values containing `run_id`, falsely marking positive cells as event-set inconsistent.
- Repair: authoritative `AUDITED_METHOD_DEADLINE_METRICS.json` compares `(start_time,end_time,anchor_unit_ids)` semantic keys. All 12 cells have consistent event sets and exact action traces across their three runtime repeats.
- Additional lesson: C1 and C3 recover different reference events (`vlm_event_0022` and `vlm_event_0004`), so H-FACT1 supports marginal scan quality, not identical-event mediation.

## F-COMP-001 — Equal VERIFY quota does not imply equal completed calls under a fail-closed guard

- Status: RESOLVED AS RESULT ACCOUNTING; no reruns or unsafe forced actions.
- Observation: every component run had a common upper quota of five VERIFY actions, but tail-aware deadline admission yielded four completed calls in three runs and five in the others.
- Consequence: completed VERIFY count is reported as a mechanism/result metric, not forced by bypassing the shared guard.
- Falsification: unequal calls do not explain the attribution. All S2 T_high runs completed five calls and recovered no event; S3 and S4 recovered events within their first four and three calls respectively.

## F-EVAL-003 — Candidate creation must include promotion after negative VERIFY

- Status: CLOSED BEFORE FINAL REPORT.
- Observation: the first evaluator draft checked positive frontier creation only after SCAN. Under A0, a positive candidate often becomes top-ranked only after higher-scored negative candidates are queried.
- Repair: authoritative Stage-4 metrics define candidate creation as the first time a scanned reference-positive unit reaches the visible unqueried top frontier, whether after SCAN or after a completed negative VERIFY. Positive exposure per scan is separately defined as positive scanned units divided by scan actions.

## F-STATE-002 — H-SCAN1A started after related Stage-4 evidence already existed

- Status: DISCLOSED; evidence preserved, not pooled.
- Observation: the authoritative worktree already contained a completed, differently grouped S0-S4 component experiment before the H-SCAN1A request, even though the new task described H-FACT1 as its starting point.
- Repair: move the prior directory intact to `stage_4_prior_debt_component_ablation`, record its combined hash in the new task manifest, and run all 28 requested H-SCAN1A physical samples fresh.
- Limitation: H-SCAN1A is prospective for its new runs and D3 proxy-only arm, but its interpretation is not blind to all related component evidence.

## F-SPEC-001 — Four-way eligibility equality conflicts with frozen D0

- Status: RESOLVED BY EXPLICIT SCOPE, not by changing a method.
- Observation: the specification requires D0 to remain H-FACT1 C0 fixed-grid ordering and also asks all four methods to have identical eligible cells. C0's `range(1,N,3)` cells are not the midpoint hierarchy used by D1-D3.
- Resolution: preserve D0 equivalence; verify identical eligibility only for the actual component ablations D1/D2/D3; mark four-way eligibility equality not applicable due to the frozen-definition conflict.

## F-EVAL-004 — Missing TTFC must serialize as null

- Status: CLOSED BEFORE FINAL DECISION.
- Observation: the first audited-decision write rejected non-standard NaN values for D0/D3, which have no confirmed event and hence no TTFC.
- Repair: serialize missing TTFC as JSON `null`; no metric or branch rule changed.

## F-TIE-001 — Structural result fails exact-tie robustness

- Status: OPEN SCIENTIFIC LIMITATION; route-level conclusion deferred to multi-task evidence.
- Observation: under otherwise frozen D2+A0 execution, TB0 recovered one event in 3/3 physical runs while TB1 and TB2 recovered none in 0/6.
- Negative control: all nine runs were valid with zero deadline misses, replay, future access, or visibility violation; endpoint coverage and maximum gap were equal.
- Mechanism evidence: only TB0 promoted the relevant positive region into the visible VERIFY frontier in time.
- Consequence: `COVERAGE_STRUCTURAL_MECHANISM=NOT_ESTABLISHED`; D2+TB0 is tie-sensitive descriptive evidence, not a usable method.
- Next discriminator: multi-task H-TIE1 after benchmark expansion; no more single-task tie seeds.

## F-INPUT-001 — Insufficient independent long development sources

- Status: PAUSED EXTERNAL INPUT REQUIRED.
- Observation: the bounded Phase-A audit has 609 candidate rows and 607 existing paths but only one eligible independent long source, `long_video_dataset3`.
- Negative evidence: 604 Nexar paths / 603 unique hashes are only 15.00–49.464883 seconds; `realcartest_5k` is derived; canonical realcartest and dataset2 bytes are absent; dataset2 is also in-cabin; DrivingDojo-mini has no video-container entry; held-out and output derivatives are excluded.
- Required repair: provide two original forward-facing source videos, preferably at least 30 minutes, with unique capture-session sidecars under `data/realcam/psvr_dev_inputs/`.
- Exact recovery: `python scripts/audit_psvr_dev_inputs.py`.
- Interpretation: input pause only; it does not establish method failure or project `NO_GO`.

## F-AUDIT-001 — Superseded input-audit draft probed held-out media metadata

- Status: DISCLOSED AND FAIL-CLOSED IN FINAL AUDIT.
- Observation: before the existing manifest's canonical-heldout role was recovered, a superseded audit draft ran metadata-only ffprobe and SHA-256 on `try_or_no/test.mov`.
- Exposure boundary: no semantic reference, label, method output, query evaluation, or tuning information was accessed.
- Repair: the final audit filters the path before inspection and copies identity metadata only from the pre-existing manifest; the independent verifier refuses to hash that path.
- Reporting: `HELD_OUT_OPENED=false` is defined as no semantic/reference/method evaluation or tuning access, while the metadata-byte incident remains explicitly recorded.
