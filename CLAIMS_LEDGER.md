# Claims Ledger

> All claims below are **oracle-relative** to the VLM labels in `center10_vlm_oracle_events.csv` and `reference_events.csv` unless explicitly noted. They are not human ground truth and not formal statistical guarantees. The labels are produced by `Qwen3-VL-32B-Instruct`; the spotcheck is at `outputs/probe_set_v1/vlm_human_agreement_spotcheck.csv` (12 rows). Every recall/precision number in any future write-up must cite the data source and the track (`strict_replay` or `posthoc_eval`) it lives in.

## Can Claim (with source)

### Frozen-LATE-AQP-v1 cross-segment pass

- **Allowed wording**: "On three held-out segments of `realcartest`, Frozen-LATE-AQP-v1 reaches 90/90 event precision/recall at the practical budget cap (B<=120). Long-event recall macro-avg wins at 4 of 6 budget points (including B=120) versus B6 and B7. The average duration-weighted precision drop vs B7 is at most 0.2 percentage points across budgets (i.e., Ours is at least as precise on average)."
- **Source**: `outputs/late_aqp_frozen_cross_segment_v1/FINAL_REPORT.md` and `revised_claims_after_cross_segment.md`.
- **Track**: oracle-relative; not strict-replay (uses `event_id` indirectly through reference).
- **Caveats** (must accompany the claim): single video split into non-overlapping windows; all labels from one VLM oracle; no generalization claim beyond this oracle.

### Strict limited-oracle frontier: 90/90 reach on realcartest

- **Allowed wording**: "Under strict limited-oracle replay on realcartest, LATE-AQP-core reaches 90/90 on 3/3 segments at the practical budget cap (B<=120). B6-core and B7-core also reach 90/90 on 3/3 segments once Core/Halo release is applied."
- **Source**: `outputs/late_aqp_limited_oracle_frontier_v1/FINAL_REPORT.md` Q6/Q7.
- **Track**: LATE-AQP-core is `strict_replay`; B6/B7/B6-core/B7-core are `posthoc_eval` (they use `event_id` in selection).
- **Caveats**: no method reaches 90/90 at <=30% budget ratio.

### Cross-video 90/90 reach on dataset3

- **Allowed wording**: "Under strict limited-oracle replay on dataset3, LATE-AQP-core reaches 90/90 on 3/3 segments. B7-core reaches 90/90 on 3/3 segments with Core/Halo release."
- **Source**: `outputs/late_aqp_cross_video_frontier_v1/FINAL_REPORT.md` Q4/Q5.
- **Track**: LATE-AQP-core is `strict_replay`; B7-core is `posthoc_eval`.

### Core/Halo is a generic post-processing gain

- **Allowed wording**: "Once B6 and B7 receive the same Core/Halo release, they reach 90/90 on the same segments as LATE-AQP-core. The Core/Halo gain is therefore a generic release-stage gain, not a LATE-AQP-specific advantage."
- **Source**: `outputs/late_aqp_core_halo_attribution_v1/final_recommendation.md`; `outputs/late_aqp_limited_oracle_frontier_v1/FINAL_REPORT.md` Q10; `outputs/late_aqp_cross_video_frontier_v1/FINAL_REPORT.md` Q8.
- **Caveats**: guard overhead is real (mean 29.6% of budget; 41.4% at B<=20) and is paid by core methods, not by raw B6/B7. Reporting Core/Halo's value should mention the guard-overhead cost.

### Boundary-guard mechanics exist and are accounted

- **Allowed wording**: "The pipeline implements boundary guards up to MAX_GUARDS_PER_SIDE=3 per side. Guard calls are counted inside the same total budget as discovery / audit / repair. The 4-way budget split (audit / discovery / repair / guard) is logged per trial."
- **Source**: `outputs/late_aqp_core_halo_frontier/core_halo_design.md`; `outputs/late_aqp_event_diverse_discovery_v1/oracle_usage_report.md` (and the corresponding `late_aqp_limited_oracle_frontier_v1/oracle_usage_report.md`).
- **Caveats**: budget accounting errors are **logged** but **not enforced** as hard assertions; pre-fix D3 had a known `queried`-state accounting bug that was repaired in `late_aqp_d3_accounting_fix_v1/`.

### Repair trace lineage is available for the frozen pipeline

- **Allowed wording**: "The frozen cross-segment replay logs per-interval lineage: `source_lineage_summary`, `created_from_call_ids`, `created_by_action_type`, `trigger_call_id`, `repair_window_start`/`repair_window_end`. The full schema is at `outputs/late_aqp_frozen_cross_segment_v1/repair_trace_logging_spec.md`."
- **Source**: `outputs/late_aqp_frozen_cross_segment_v1/repair_trace_selected_intervals.csv`, `repair_trace_calls.csv`, `repair_trace_logging_spec.md`.
- **Caveats**: the v3 replay (`outputs/late_aqp_algorithm_v3_oracle_relative/`) does **not** fully log `source_action` lineage; many intervals are `unknown_not_logged`.

### Long-event replay wins for Ours-full

- **Allowed wording**: "On the long-event subset (duration>=1s) of the H7-era replay, Ours-full LATE-AQP improves event-level recall over B6 and B7 at most budgets, including reaching 1.000 recall at B=80 and B=120."
- **Source**: `outputs/late_aqp_h7_long_event_v1/FINAL_REPORT.md` "Event-level recall (duration>=1s subset)" table.
- **Caveats**: H7 annotation package is **pending human annotation**; this is a VLM-oracle-relative long-event subset, not a full ground truth.

### H7 annotation package is ready for human annotation

- **Allowed wording**: "An H7 calibration package with three windows (high_prior, low_prior, suspected_leakage) and a template + guide is ready at `outputs/late_aqp_h7_long_event_v1/`. Human annotation is the next annotation milestone; it is not the LATE-AQP performance conclusion."
- **Source**: `outputs/late_aqp_h7_long_event_v1/h7_annotation_template.csv`, `h7_annotation_guide.md`, `audit_calibration_plan.md`.
- **Caveats**: H7 is a calibration prep, not a main result.

### Phase 3 selector smoke is a completed negative diagnostic

- **Allowed wording**: "The first cheap-signal -> selector -> NMS -> budgeted return-set smoke completed with a negative diagnostic result: at B=40, uniform_random averaged 0.153 event_recall_iou_0_3 across 50 seeds, while the best deterministic cheap-signal selector reached 0.050. This is the empirical motivation for the next selector/return-set redesign (T010, EC-AQP)."
- **Source**: `outputs/agent_loop_v1/phase3_selector_smoke_v1/phase3_selector_smoke_report.md`.
- **Caveats**: this is `diagnostic_design_target_smoke`, not validation. Do not claim selector replacement.

### probe_set_v1 exists and is read-only

- **Allowed wording**: "`probe_set_v1` contains 25 probes with exported clips, center frames, and contact sheets. 25/25 local Qwen3-VL-32B oracle judgments are parsed; 7 are oracle-positive. Probe metrics exist only as VLM-oracle-relative diagnostics over the 20-probe feature-covered scope. The probe rows are marked frozen / read-only and are not used for tuning."
- **Source**: `outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`, `outputs/agent_loop_v1/probe_eval_after_vlm_oracle/probe_signal_metrics.csv`, `outputs/cheap_signal_v2/probe_feature_coverage_audit.md`.

### cheap_signal_v2 exists with documented coverage

- **Allowed wording**: "`cheap_signal_v2` provides track-interaction and inside/outside contrast features. Coverage is local [0, 1200] only. `auc_best_direction` is a design-target metric on 6_event_reference, not a deployed selector."
- **Source**: `outputs/cheap_signal_v2/signal_upgrade_within_bin_metrics.csv`, `probe_feature_coverage_audit.md`, `CLAIMS_LEDGER.md` "6-event diagnostic design target AUCs".

## Cannot Claim (explicit disallowed wording)

- **Disallowed**: "LATE-AQP beats B7-core on B_90/90." Source: `outputs/late_aqp_event_diverse_discovery_v1/FINAL_REPORT.md` Q4: "No LATE variant achieved a strictly lower B_90/90 than B7-core on any segment." Cross-video confirmation at `outputs/late_aqp_cross_video_frontier_v1/FINAL_REPORT.md` Q6: on 1/3 dataset3 segments LATE-core B_90/90 > B7-core B_90/90.
- **Disallowed**: "Core/Halo is a LATE-AQP-specific advantage." Source: `outputs/late_aqp_core_halo_attribution_v1/final_recommendation.md`; `outputs/late_aqp_limited_oracle_frontier_v1/FINAL_REPORT.md` Q10. The gain is generic.
- **Disallowed**: "Repair is net-negative on chunk-bandit discovery (settled)." Source: `outputs/late_aqp_repair_negative_diagnosis_v1/FINAL_DIAGNOSIS.md` and `outputs/late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md`: the original conclusion was contaminated by a `queried`-state accounting bug. After the fix, repair is **not** consistently additive; the cleanest statement is "neutral after the fix", not "net-negative".
- **Disallowed**: "D3 / D1 / D2 outperforms B7-core on B_90/90." Source: `outputs/late_aqp_event_diverse_discovery_v1/FINAL_REPORT.md` Q4.
- **Disallowed**: "v2 cold_start_fallback solves the low-budget problem on the original realcartest failure segments." Source: `outputs/late_aqp_low_budget_fix_v1/README.md` "Caution": the v2 fix was tuned on `realcartest_5k` and validated on `realcartest_3830_3920`; the original cross-segment low-budget failure could not be re-tested because the footage is no longer available.
- **Disallowed**: "hybrid_coldstart (r=0.5) fixes the low-budget problem." Source: `outputs/late_aqp_hybrid_coldstart_v1/verdict_report.md` "Overall verdict: FAIL".
- **Disallowed**: "v2 cold_start_fallback fixes the low-budget problem on the original failure segments." Source: `outputs/late_aqp_v2_original_segment_verification/verdict_report.md` "Verdict: FAIL".
- **Disallowed**: "Phase 3 cheap-signal selectors are ready to replace the default selector." Source: `outputs/agent_loop_v1/phase3_selector_smoke_v1/phase3_selector_smoke_report.md`: deterministic selectors underperform uniform random.
- **Disallowed**: "CILS is the default selector." Source: `AGENTS.md` "Never" list: CILS is ablation-only.
- **Disallowed**: "probe_set_v1 AUC / precision / recall are human ground truth metrics." Source: `outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv` is VLM-oracle-relative, 7 positives, 20-probe feature-covered scope.
- **Disallowed**: "expanded_reference validates the signal." Source: `expanded_reference` is empty.
- **Disallowed**: "true recall", "ground truth recall", "human ground truth recall" for any metric in this repo. The closest equivalent is "VLM-oracle-relative recall", which must be labeled as such.
- **Disallowed**: "formal guarantee", "certificate", "statistical bound". This project does not compute or claim any.
- **Disallowed**: "current probe media covers the full 66-minute realcartest video." Source: `try_or_no/videos/realcartest.mp4` is absent; current coverage is the dataset3 fallback.
- **Disallowed**: "signal X is significantly better than signal Y" or "validated signal superiority" on the probe_set_v1 7-positive scope. The Phase 3 smoke is negative; bootstrap intervals on the 20-probe scope are wide.
- **Disallowed**: "any method reaches 90/90 at <=30% budget ratio." Source: `outputs/late_aqp_limited_oracle_frontier_v1/FINAL_REPORT.md` Q5; `outputs/late_aqp_cross_video_frontier_v1/FINAL_REPORT.md` Q3.
- **Disallowed**: "EventLift-DR / AIPW audit correction is validated to reduce oracle budget on dataset3." Source: `PROXY_BIAS_DR_FEASIBILITY.md` — Gate B is CONDITIONAL, the deployable per-stratum-LOO p_model gives ≥20% reduction on only 1/6 segments (dataset3_0_1200); the ≥4/6 aggregate outcome relies on crediting a deliberately miscalibrated raw-minmax strawman. EventLift-DR has not been implemented or benchmarked on interval return-set coverage; only the residual-calibration RMSE claim has been evaluated.
- **Disallowed**: "HTS-AQP (Hierarchical Tree Search) outperforms existing baselines." Source: `outputs/hts_aqp_phase0_feasibility/HTS_PHASE0_FEASIBILITY_REPORT.md` — the God's-eye Phase 0 simulation achieves a coverage that no strict_replay baseline reaches at any available budget, so a strict equal-coverage oracle-call ratio is unavailable; the verdict is **B (weakly feasible / segment-dependent)**, not A. The simulation uses `any-overlap` coverage convention; baselines use IoU ≥ 0.3 — these are not equivalent, and a real Phase 1 evaluation must switch to IoU ≥ 0.3 before any performance claim. HTS is a known paradigm (hierarchical multi-resolution search); coarse-oracle-VLM-reliability assumption is unvalidated.
- **Disallowed**: "HTS-AQP eliminates the granularity hyperparameter" / "HTS-AQP has no hyperparameters." Source: `HTS_AQP_DESIGN.md` §2.4 — branching factor `b`, prior pseudo-count `k0`, and exploration constant `c` are still hyperparameters. The design replaces (bin_size, chunk_size, suppression_radius) with (b, k0, c); it does not eliminate hyperparameters. Sensitivity must be reported.
- **Disallowed**: "DR / AIPW audit correction is a novel statistical estimator." Source: standard DR / AIPW literature and `AGENTS.md` "Never" list. The estimator family is known; only its design-based application to event-level AQP discovery posterior is candidate-novel.
- **Disallowed**: "Ours wins on B_90/90" for the cross-video dataset3 evaluation as a single unqualified statement. The full table is in `cross_video_precision_recall_frontier.csv`: 2/3 segments tie or LATE wins, 1/3 LATE loses.

## Pending Validation

- **ECP (Event-Coverage Policy) redesign (T010/T025..T028c).** T010 is the ECP mainline (`outputs/ecp_event_coverage_policy_v1/ECP_DESIGN.md`); T025-T028c are COMPLETE (Rounds 21-23). T028c-0 oracle ceiling proved learnable event-level signal EXISTS on proxy-informative realcartest (+0.10..+0.14 over v2 on cells v2 regressed on) but NOT on proxy-zero dataset3_0_1200/1200_2400 (candidate generator cannot propose zero-proxy positives -> ceiling≈0). T028c-1 event-utility ranker (GradientBoosting on u(arm|state,arm), trained on candidate-level utilities NOT logger-confined) is strict-replay and recovers the ceiling on collapsed cells: realcartest_3200_3830 @0.30 c1 0.286=ceiling beats v2 0.143; realcartest_0_1570 @0.30 c1 0.250 vs v2 0.200; dataset3_2400_3462 c1 0.111>v2 0.000. **First ECP variant to beat v2 on realcartest without precision loss.** Claim status: **partially supported on proxy-informative realcartest, still NOT supported on proxy-zero dataset3** (candidate-generator bottleneck, not policy). T028d (IPS/DR) deferred until stochastic logger; T028e (proxy-free candidate generator) is the real next lever for dataset3. ECP does not alter default selector or Core/Halo release.
- **EC-AQP redesign (T010/T020/T022).** Superseded by ECP: the event-coverage-mass objective is absorbed as the reward term inside ECP. The T020 design doc and T022 offline prototype are folded into ECP's 4-step plan (T025/T026/T027 + learned policy). The claim "EC-AQP improves low-budget event coverage" is **not supported** until those steps land.
- **EventLift-DR / AIPW audit correction (T023).** Feasibility-only (`outputs/eventlift_dr_feasibility/`, `PROXY_BIAS_DR_FEASIBILITY.md`). Gate A = PASS (proxy-bias diagnosis), Gate B = CONDITIONAL (deployable per-stratum-LOO p_model gives ≥20% RMSE reduction on 1/6 segments — dataset3_0_1200; raw-minmax strawman credit on ≥4/6 does not count toward a real PASS), Gate C = PASS border-line. Until T023 lands and an interval return-set coverage comparison against ABae-residual-strict (under the deployable p_model only) is run, the claim "EventLift-DR reduces audit budget cost without lowering recall on weak-proxy dataset3 segments" is **not supported**. DR / AIPW is a known estimator family, not a novel statistical invention; only design-based application to event-level AQP discovery posterior is candidate-novel.
- **HTS-AQP hierarchical tree search (T024).** Phase 0 God's-eye deterministic simulation only (`outputs/hts_aqp_phase0_feasibility/`). Verdict = **B (weakly feasible / segment-dependent)**. Coverage-convention mismatch flag: Phase 0 uses `any-overlap` between positive bins and reference events; baselines use IoU ≥ 0.3 between returned intervals and reference events. These are **not equivalent**; Phase 0 coverage numbers are diagnostic upper bounds. No strict_replay baseline reaches HTS full coverage at any available budget, so a strict equal-coverage oracle-call ratio is unavailable. Until T024 lands and a real Beta+UCB+frontier HTS-Discover Phase 1 prototype is evaluated under IoU ≥ 0.3, the claim "HTS-AQP outperforms existing baselines on dataset3 sparse segments in oracle-call efficiency" is **not supported**. Coarse-to-fine is a standard hierarchical search paradigm, not a novel contribution; only its application to event-level AQP is candidate-novel. The coarse-oracle-VLM-reliability assumption (real VLM coarse-window judgment vs strict-replay OR aggregation of dense labels) is **not validated** and must be flagged in any future write-up as a simulation-only limitation.
- **HTS-EC saturation-aware hierarchical executor (T024 successor).** Feasibility gates run in `outputs/hts_ec_feasibility_v1/`, synthesized in `HTS_EC_DELTA_AND_FEASIBILITY.md`. Gate decision = **A (proceed to implementation)** — upgraded from B after Gate C v2. Gate A (granularity heterogeneity) = CONDITIONAL: 3/6 segments show positive adaptive gain, macro +0.0435 (relative +18.44%). Gate B (saturation detector) = spec FAIL / calibrated PASS (circularity risk noted for v1). Gate C v1 (per-node fallback) = CONDITIONAL: detector_fallback doesn't fix rc_2000 (delta=−0.100). **Gate C v2 (global fallback + dual frontier) = PASS**: `HTS_EC_dual_frontier_gated` passes all 4 conditions — rc_2000 recall=0.250 (beats flat 0.200 by +0.050) AND preserves sparse savings (ds3_0_1200=0.167, ds3_1200_2400=0.083, ds3_2400_3462=0.222). `HTS_EC_detector_per_node_fallback` with conservative Beta-posterior detector also passes all 4 (0.200, 0.167, 0.083, 0.333). Key design: (1) theoretical break-even density d*≈0.245 (no labels, no circularity — derived from tree structure alone), (2) Beta-posterior detector (P(d≥d*)>0.75, k_min=5), (3) gated dual frontier (fine bins only activated when detector triggers). **HTS-EC-v0 strict-replay implemented** (`src/garc_eval/hts_ec_v0.py`, `outputs/hts_ec_v0_strict_v1/`, `HTS_EC_V0_STRICT_REPLAY_REPORT.md`): 162 runs, 0 budget violations, 0 event_id leaks. HTS-EC-safe (P_thresh=0.85, k_min=4) passes 6/7 gates. **Supported under strict replay**: (a) dense-segment regression on rc_2000 eliminated (recall=0.200=flat, no regression), (b) detector triggers correctly (on dense, not sparse), (c) fine frontier is gated (0.000 fine fraction on sparse for safe variant). **NOT supported**: (a) HTS-EC-v0 outperforms EventLift-DC or B7-strict on any segment (it matches but does not beat), (b) HTS-EC-v0 solves the weak-proxy problem on dataset3 (0.000 on ds3_0_1200, 0.111 on ds3_2400_3462 = flat), (c) ready for paper-facing benchmark (needs Phase 2: CERTIFY + weak-proxy fix + more segments). God's-eye-to-strict gap: −0.05 to −0.29 across segments (expected: posterior drill/prune is more conservative than God's-eye labels). The claim "HTS-EC gated dual frontier eliminates the naive HTS dense-segment regression under strict replay" is **supported**. The claim "HTS-EC outperforms existing baselines" is **not supported**. Source: `hts_ec_feasibility_v1` + `hts_ec_v0_strict_v1` + `hts_aqp_phase0_feasibility`. Track: strict_replay / godseye / feasibility_detector.
- **H7 human annotation (T018 follow-up).** Package is ready; annotation requires explicit authorization. Until the annotation is in, "long-event recall is grounded in human labels" is not supported; current numbers are VLM-oracle-relative.
- **probe_v2 expansion (T007/T008).** Blocked on user decision. Do not start without explicit go-ahead; not on the mainline.
- **Externalization of >100MB CSV artifacts (T021).** Tracked in git; see `outputs/state_sync_late_aqp_v1/large_artifact_manifest.md`. Do not move/delete without user decision.
- **Per-interval adaptive guard cap.** A guard overhead of 29.6% mean (41.4% at B<=20) is observed; whether a dynamic cap is worth the boundary-precision cost is **not yet evaluated**.
- **Algorithm v3 audit schedules and repair utilities in a strict-replay setting.** `outputs/late_aqp_algorithm_v3_oracle_relative/` is simulation-only and the `source_action` lineage is not fully logged. The v3 ideas (V3_two_phase, U1_leakage_density) are candidates for re-evaluation under strict replay.
- **Generalization of B7-core / LATE-core 90/90 to videos other than realcartest and dataset3.** Only two videos have been tested. The cross-video result holds; the cross-dataset / cross-predicate result is not yet established.
- **Whether the guard-overhead cost of Core/Halo is justified when the discovery backbone already covers the events.** The "core methods pay 0-30% guard overhead" comparison suggests the cost is real; whether an adaptive cap could reduce it without breaking the 90/90 frontier is open.
