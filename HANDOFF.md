# SQ-CRAQ Handoff

> **Note for future agents:** The root state files were previously out of sync with the actual experimental progress. As of `outputs/state_sync_late_aqp_v1/`, the LATE-AQP frontier is the mainline, not the Phase 3 selector smoke. Always read `PROJECT_STATE.md` first, then `CLAIMS_LEDGER.md`, then this file. Do **not** restart any of the failed routes listed in `FAILURES.md` without a new reason.

## Current Safe State

LATE-AQP pipeline (audit + discovery + repair + boundary guard + Core/Halo release) is implemented and validated under strict limited-oracle replay. Frozen v1 config passes the cross-segment replay; v2 cold-start fix is split-validated on a non-original tuning segment. No new VLM, YOLO, API, or GPU inference should run unless explicitly authorized.

## What "mainline" means here

- **Default selector**: `score_topk` + temporal NMS + duration cap (this is the AGENTS.md default and it has not been changed).
- **Default release module**: Core/Halo release (boundary guard up to `MAX_GUARDS_PER_SIDE=3` per side; positive guard bins merged into core; halo reported as diagnostic only). This is treated as a generic post-processing gain, not a LATE-specific advantage.
- **Strongest current empirical baseline (posthoc_eval)**: **B7-core** (B7 chunk-bandit + temporal expansion + Core/Halo). Use this as the comparison target for any new discovery policy.
- **Strongest strict-replay alternative**: **D3-norepair-core** (chunk-bandit Thompson sampling, no repair, Core/Halo release). Use this when the comparison must not use `event_id` for selection.
- **New mainline (2026-07-07): Event-Coverage Policy (ECP)**, `outputs/ecp_event_coverage_policy_v1/ECP_DESIGN.md`. ECP is a **policy layer** above the discovery executor (HTS-EC / EventLift-DC), not a replacement for the default selector or Core/Halo. Its arms are event-level operators (discover / bridge / certify / zero-proxy / stop); its reward is marginal event-recall/precision/IoU. First concrete experiment is T025 (AnchorBridge shadow). Default selector and Core/Halo release remain unchanged.
- **Reference labels**: `center10_vlm_oracle_events.csv` (non-dev segments) and `reference_events.csv` (dev segment). These are VLM-oracle-relative, not human ground truth.
- **oracle adapter spec**: `outputs/late_aqp_limited_oracle_frontier_v1/oracle_adapter_spec.md`. Each `query_unit` / `query_interval` call consumes one oracle call; `event_id` is never returned to the method.

## Ready For Human Work

- H7 annotation package: `outputs/late_aqp_h7_long_event_v1/h7_annotation_template.csv` and `h7_annotation_guide.md`. **Status: pending human annotation.**
- `outputs/probe_set_v1/vlm_human_agreement_spotcheck.csv` (12-row spotcheck table).
- `outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`.
- `outputs/probe_set_v1/probe_media/clips/`, `centers/`, `sheets/`.
- `outputs/state_sync_late_aqp_v1/large_artifact_manifest.md` — files > 50MB still tracked in git; needs user decision on externalization.

## Ready For No-Compute Follow-Up

- **T010: AQP selector/return-set redesign toward EC-AQP** (`TASK_QUEUE.yaml`). EC-AQP reframes the objective from per-interval precision/recall to event-coverage mass over the reference event set, and adds a residual missing-mass estimator. Design only; no VLM, YOLO, or GPU training is needed.
- Inspect `outputs/agent_loop_v1/phase3_selector_smoke_v1/selected_intervals.csv` and `event_coverage.csv` for the negative Phase 3 smoke failure cases; these motivate the EC-AQP objective.
- Inspect `outputs/late_aqp_event_diverse_discovery_v1/unique_event_coverage.csv` and `discovery_miss_reduction.csv` to characterize the upstream discovery miss structure.
- Inspect `outputs/late_aqp_cross_video_frontier_v1/cross_video_failure_taxonomy.csv` for the failure-taxonomy distribution across both videos (most low-budget failures are discovery misses).
- **Next active work (T025, ECP Step 1):** inspect `outputs/hts_ec_v0_phase2a_rp_opportunity_v1/rp_strategy_miss_analysis.csv` and `outputs/hts_ec_v0_phase2a_rp_strategy_shadow_v1/rp_strategy_shadow_summary.csv` to quantify the AnchorBridge opportunity (proxy-signal segments: `gap_bracket_v2/largest_gap_local_flank_or_proxy_neighbor` = 11/30 shadow hits; proxy-zero `dataset3_0_1200` = 0 hits). This isolates the event-formation gap from the discovery gap.

## Latest Important Outputs (read these before doing anything else)

- `EVENTLIFT_FULL_BENCHMARK_V1_REPORT.md` and `EVENTLIFT_RESULTS_SYNTHESIS.md` — EventLift-AQP v1 full benchmark (9 methods × 6 segments × 3 budgets × 3 seeds, 486 runs, 0 violations). EventLift-discover-certify (DC) achieves highest macro recall (0.156) at budget 0.30 among strict_replay methods; CERTIFY improves precision on 4/6 segments and recall on 2/6 without hurting recall anywhere. AUDIT fires only on dev segment (17/36 calls); SUPPRESS never fires. Safe stopping not claimed (all 486 runs abstain). B7-strict-replay is the fair B7 comparison (B7-core-posthoc is context-only).
- `PROXY_BIAS_DR_FEASIBILITY.md` and `outputs/eventlift_dr_feasibility/` — DR / AIPW audit-correction feasibility diagnosis: Gate A=PASS (proxy bias), Gate B=CONDITIONAL (deployable per-stratum-LOO p_model gives ≥20% RMSE reduction on 1/6 segments — dataset3_0_1200 only; raw-minmax strawman credit on 4/6 does not count), Gate C=PASS border-line (dual-use audit correction vs failed forced-exploration priors). Pre-implementation feasibility only; no implementation, no SOTA claim, no safe stopping claim. DR / AIPW is a known estimator family.
- `HTS_AQP_DESIGN.md` and `outputs/hts_aqp_phase0_feasibility/` — HTS-AQP design + Phase 0 God's-eye deterministic feasibility simulation (b ∈ {2,4}, all 6 segments reported including adverse cases). Verdict = **B (weakly feasible / segment-dependent)**: at b=4, savings-vs-flat-scan on dataset3 segments = 21-59%, HTS finds all 6-12 events in 49-95 calls where best existing strict-replay baseline finds 1-2 of 6-12. No strict-replay baseline reaches HTS full coverage at any available budget, so a strict equal-coverage ratio is unavailable. realcartest_2000_3200 shows −0.8% (b=4) and −20.8% (b=2) regression due to coarse-positive saturation on dense segments. Coarse-to-fine is a known hierarchical search paradigm; only its application to event-level AQP is candidate-novel. Coarse-oracle-VLM-reliability assumption is unvalidated.
- `HTS_EC_DELTA_AND_FEASIBILITY.md` and `outputs/hts_ec_feasibility_v1/` — HTS-EC feasibility synthesis (Gates A/B/C v1 + v2). **Latest gate decision: A (proceed to strict-replay implementation).** Gate C v2 = PASS under God's-eye simulation: `HTS_EC_dual_frontier_gated` passes all 4 conditions (rc_2000=0.250 vs flat 0.200, sparse savings preserved). Key design: theoretical break-even density d*≈0.245 (no circularity), Beta-posterior detector (P(d≥d*)>0.75, k_min=5), gated dual frontier. **CAVEAT: God's-eye only; strict-replay implementation (posterior drill/prune) is the next step.** naive-HTS-strict-single_probe is broken in strict-replay (1 call, 0 recall); naive-HTS-strict-posterior is functional but weak (0.000–0.286). Source: `hts_ec_feasibility_v1` + `hts_aqp_phase0_feasibility`.
- `outputs/late_aqp_limited_oracle_frontier_v1/FINAL_REPORT.md` — strict limited-oracle frontier on realcartest.
- `outputs/late_aqp_cross_video_frontier_v1/FINAL_REPORT.md` — same evaluation on dataset3.
- `outputs/late_aqp_event_diverse_discovery_v1/FINAL_REPORT.md` — D1/D2/D3/D3-norepair vs B6/B7.
- `outputs/late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md` — chunk-bandit `queried`-state bug fix and post-fix comparison.
- `outputs/late_aqp_core_halo_attribution_v1/final_recommendation.md` — Core/Halo is generic.
- `outputs/late_aqp_frozen_cross_segment_v1/FINAL_REPORT.md` and `revised_claims_after_cross_segment.md` — frozen v1 config, revised claims.
- `outputs/late_aqp_low_budget_fix_v1/final_validation_report.md` and `frozen_v2_config.md` — v2 cold-start fix; split-validated, not re-validated on the original failure segments.
- `outputs/late_aqp_repair_negative_diagnosis_v1/FINAL_DIAGNOSIS.md` — the original "repair is net-negative" claim was contaminated by a chunk-bandit accounting bug; the diagnosis recommends fixing the bug and re-evaluating.
- `outputs/late_aqp_v2_original_segment_verification/verdict_report.md` and `outputs/late_aqp_hybrid_coldstart_v1/verdict_report.md` — both cold-start tweaks `FAIL` on the original failure segments.
- `outputs/late_aqp_algorithm_v3_oracle_relative/FINAL_REPORT.md` — v3 audit-schedule and repair-utility designs; modest improvements only.
- `outputs/late_aqp_h7_long_event_v1/FINAL_REPORT.md` — H7 calibration prep; Ours-full improves event-level recall over B7 at most budgets for the long-event subset.
- `outputs/ecp_event_coverage_policy_v1/ECP_DESIGN.md` — **NEW MAINLINE (2026-07-07): Event-Coverage Policy.** Reframes the bottleneck from "proxy accuracy" to "event-level budgeted decision policy" under weak proxy / expensive oracle / unknown boundaries. ECP unifies DISCOVER+ROBUST_PROBE+BRIDGE+CERTIFY+ZERO_PROXY as event-level bandit arms above HTS-EC / EventLift-DC. Validation plan T025 (AnchorBridge shadow) -> T026 (action-utility labeling) -> T027 (hand-designed bandit).
- `outputs/ecp_event_coverage_policy_v1/ECP_STEPS1_3_SYNTHESIS.md` — **ECP Steps 1-3 results (Round 21).** T025: formation gap is temporal granularity + proxy-zero discovery (not gap-bridging; positives already contiguous, max_internal_gap=0 for all 74 events). T026: BRIDGE most efficient arm (0.474 pos rate) but under-used by hand weights. T027: hand-designed ECP bandit strict-replay matches/beats HTS-EC-safe on realcartest, weak on dataset3.
- `outputs/ecp_event_coverage_policy_v1/ECP_STEP4_SYNTHESIS.md` — **ECP Step 4 results (Round 22).** T028a: reweighted v2 fixes BRIDGE under-use but NOT clearly better than v1. T028b: offline logistic policy == v2 on every cell (re-learns logger).
- `outputs/ecp_event_coverage_policy_v1/ECP_STEP4C_SYNTHESIS.md` — **ECP Step 4c results (Round 23).** T028c-0 ceiling: learnable signal EXISTS on realcartest (+0.10..+0.14 over v2) but NOT on proxy-zero dataset3 (candidate-generator bottleneck). T028c-1 event-utility ranker is the FIRST ECP variant to beat v2 on realcartest (recovers ceiling on collapsed cells, no precision loss). T028d deferred; T028e (proxy-free candidate generator) next lever for dataset3.

## Do-Not-Repeat Failed Routes

These routes have been tried and **failed** to deliver an oracle-relative performance advantage over B7-core. Do not re-run them as the next step without a new mechanism:

- **Another D1/D2/D3 discovery sweep along the same axes.** D1 (temporal-NMS prior), D2 (component proposals), D3 (chunk-bandit + repair) all reach 90/90 but **none** achieves a strictly lower B_90/90 than B7-core on any of 6 segments (`outputs/late_aqp_event_diverse_discovery_v1/FINAL_REPORT.md` Q4). Adding more variants along the same axes will not establish a discovery-side advantage.
- **v2 `cold_start_fallback` on the original failure segments.** Split-validated only. The original realcartest cross-segment low-budget failure could not be re-tested because that footage is no longer available (`outputs/late_aqp_low_budget_fix_v1/README.md` "Caution").
- **`hybrid_coldstart` (r=0.5) as a low-budget fix.** 0/3 segments with substantive improvement at both B=10 and B=20 (`outputs/late_aqp_hybrid_coldstart_v1/verdict_report.md`).
- **Treating "repair is net-negative" as a settled conclusion without first fixing the chunk-bandit accounting bug.** The diagnosis (`outputs/late_aqp_repair_negative_diagnosis_v1/FINAL_DIAGNOSIS.md`) and the fix (`outputs/late_aqp_d3_accounting_fix_v1/`) showed the original comparison was contaminated. After the fix, repair is still not additive; do not re-derive a "repair is net-negative" conclusion from the pre-fix data.
- **Claiming Core/Halo is a LATE-specific advantage.** It is generic; B6-core and B7-core reach 90/90 on the same segments as LATE-AQP-core (`outputs/late_aqp_core_halo_attribution_v1/final_recommendation.md`).
- **Phase 3 fixed cheap-signal selector** (`outputs/agent_loop_v1/phase3_selector_smoke_v1/`). Deterministic cheap-signal selectors underperform the 50-seed uniform random baseline on B=40 event_recall_iou_0_3. This is the empirical motivation for EC-AQP, not a route to revisit.
- **CILS as the default selector.** Per AGENTS.md, CILS is ablation-only.

## Completed Agent Loop Items

- T001: Registered Phase A/B artifacts. `outputs/agent_loop_v1/round2_phase_ab_registration.md`.
- T002: Built probe_set_v1 annotation package. `outputs/probe_set_v1/annotation_package/`.
- T003: Audited probe vs cheap-signal coverage. `outputs/cheap_signal_v2/probe_feature_coverage_audit.md`.
- T004: Prepared round-5 decision handoff. `outputs/agent_loop_v1/HANDOFF_ROUND5.md`.
- T005: Local Qwen3-VL oracle labels for probe_set_v1 (25/25 parsed, 7 oracle-positive). `outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`. VLM-oracle-relative, not human truth.
- T006: Pre-annotation design check and label template. `outputs/probe_set_v1/probe_set_human_labels_template.csv`.
- T009: Phase 3 minimal selector smoke. `outputs/agent_loop_v1/phase3_selector_smoke_v1/`. **Result: negative diagnostic smoke; motivates EC-AQP redesign.**
- T011: Frozen-LATE-AQP-v1 cross-segment validation. `outputs/late_aqp_frozen_cross_segment_v1/`. **Pass: long-event recall macro-avg wins at 4/6 budgets including B=120.**
- T012: Limited-oracle retrieval frontier on realcartest. `outputs/late_aqp_limited_oracle_frontier_v1/`. **Pass: LATE-AQP-core reaches 90/90 on 3/3 segments; B7-core reaches 90/90 on 3/3.**
- T013: Event-diverse discovery redesign (D1/D2/D3/D3-norepair). `outputs/late_aqp_event_diverse_discovery_v1/`. **Negative for performance advantage: no LATE variant beats B7-core on B_90/90.**
- T014: D3 chunk-bandit accounting fix. `outputs/late_aqp_d3_accounting_fix_v1/`. **Bug fixed; repair still not additive post-fix.**
- T015: Cross-video validation on dataset3. `outputs/late_aqp_cross_video_frontier_v1/`. **Core/Halo generic gain confirmed; bottleneck is upstream discovery.**
- T016: Low-budget diagnosis and v2 fix. `outputs/late_aqp_low_budget_discovery_diagnosis_v1/`, `late_aqp_low_budget_fix_v1/`, `late_aqp_v2_original_segment_verification/`, `late_aqp_hybrid_coldstart_v1/`. **Split-validated; cold-start and hybrid routes both FAIL on the original failure segments.**
- T017: LATE-AQP algorithm v3 audit-schedule and repair-utility designs. `outputs/late_aqp_algorithm_v3_oracle_relative/`. **Modest B=20 improvement; no utility dominates both recall and precision; `source_action` lineage not fully logged in the v3 replay.**
- T018: H7 calibration prep + long-event-only replay. `outputs/late_aqp_h7_long_event_v1/`. **H7 annotation package pending human annotation; Ours-full improves event-level recall over B7 at most budgets for the long-event subset.**
- T019: Agent state sync. `outputs/state_sync_late_aqp_v1/`. **This file and `PROJECT_STATE.md`, `CLAIMS_LEDGER.md`, `FAILURES.md`, `TASK_QUEUE.yaml`, `EXPERIMENT_REGISTRY.csv`, `AGENTS.md`, `large_artifact_manifest.md` were updated to reflect the LATE-AQP frontier.**
- T010 (reformulated): EC-AQP -> **Event-Coverage Policy (ECP)** mainline. `outputs/ecp_event_coverage_policy_v1/ECP_DESIGN.md`. **Design doc complete; reframes bottleneck as event-level budgeted decision policy; validation plan T025->T026->T027.**
- T025: ECP Step 1 — AnchorBridge shadow validation. **COMPLETE** (`t025_anchorbridge_shadow*.md/.csv`). Formation gap = temporal granularity + proxy-zero discovery, NOT gap-bridging.
- T026: ECP Step 2 — action-level offline utility labeling. **COMPLETE** (`t026_action_utility.csv`). BRIDGE most efficient arm; under-used by hand weights.
- T027: ECP Step 3 — hand-designed event-utility bandit. **COMPLETE (first pass)** (`t027_ecp_bandit_*.md/.csv`). Strict-replay; matches/beats HTS-EC-safe on realcartest, weak on dataset3.
- T028: ECP Step 4 — reweight BRIDGE + strengthen ZERO_PROXY + offline learned policy on T026 table. **COMPLETE (first pass):** T028a reweight not a clear win; T028b learned policy == v2 (re-learns logger).
- T028c: ECP Step 4c — candidate ceiling + event-utility ranking policy. **COMPLETE:** T028c-0 ceiling proves learnable signal on realcartest but not proxy-zero dataset3; T028c-1 ranker beats v2 on realcartest (first ECP win). T028d (IPS/DR) **DEFERRED** (needs stochastic logger); T028e (proxy-free candidate generator) **PENDING** (real lever for dataset3).
- T028c-2: ECP Step 4c-2 — LOSO cross-segment validation. **COMPLETE:** c1 generalizes on realcartest held-out (0 regressions, 4/9 improvements up to +0.143, hits ceiling on 2 cells); does NOT generalize on dataset3 (candidate-generator bottleneck). Action shift: c1 uses more DISCOVER+CERTIFY, less BRIDGE. Outputs: `t028c2_loso_*`.
- T028e: ECP Step 4e — proxy-free candidate generator. **COMPLETE:** T028e-0 ceiling audit added 5 proxy-free arms; dataset3_1200_2400 ceiling lifts +0.083. T028e-1 strict-replay LOSO: c2 matches c1 on realcartest (0 regressions), beats v2 on 2/9 dataset3 cells, most importantly dataset3_0_1200 @0.20/0.30 c2=0.167 vs v2=0.000 (ceiling was 0). VDC is the key proxy-free arm. Outputs: `t028e0_ceiling_*`, `t028e1_loso_*`, `t028e_synthesis.md`.

## Pending / Blocked / Decision-Only

- T007: `probe_v2_expansion` — **blocked**, waiting on user decision.
- T008: probe_v2 launch decision — pending.
- T010: AQP selector/return-set redesign toward EC-AQP — **active / highest priority**.
- T023: EventLift-DR targeted ablation prototype (design-only successor to `proxy_bias_dr_feasibility_v1`) — **pending, requires explicit human authorization**. In-scope segments: dataset3_0_1200 + optionally dataset3_1200_2400. p_model = per_stratum_loo only. Audit-share ∈ {0.10, 0.20} only. Audit-sample-isolation required. Default selector unchanged. DR / AIPW is a known estimator family.
- T024: HTS-Discover (Phase 1) spec-only successor to `hts_aqp_phase0_feasibility` — **pending, requires explicit human authorization**. Pre-implementation requirements: b ∈ {2,4,8} sensitivity, k0 prior-pseudo-count sensitivity, hybrid fallback for >20% density segments to address the realcartest_2000_3200 b=2 −20.8% regression, coverage-convention switch from Phase 0's `any-overlap` to IoU ≥ 0.3 for any actual evaluation. Default selector unchanged. Coarse-to-fine is a known search paradigm.

## Current Blocker

No current blocker for the next no-new-VLM step.

`outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv` is VLM-oracle-relative, not human ground truth. Future metrics must say "relative to VLM oracle judgment" and must not use "true recall" or "ground truth recall."

`outputs/agent_loop_v1/probe_eval_after_vlm_oracle/` is limited to 20/25 probes because current cheap_signal_v2 features cover local `[0, 1200]`; probes 21-25 remain unscored.

`outputs/agent_loop_v1/phase3_selector_smoke_v1/` is the negative Phase 3 smoke. **Treated as `diagnostic_design_target_smoke`, not validation. Do not claim selector replacement from this experiment.**

`outputs/late_aqp_algorithm_v3_oracle_relative/repair_trace_events.csv` and `outputs/late_aqp_frozen_cross_segment_v1/repair_trace_selected_intervals.csv` are the most complete lineage logs to date; the v3 replay's `source_action` lineage is `unknown_not_logged` for some intervals.

`outputs/late_aqp_low_budget_fix_v1/new_labels/raw_vlm_responses_realcartest_5k/` are raw VLM responses used only for the v2 tuning round; they are not part of the main result.

## Requires Explicit Authorization

- Any additional VLM/API labeling beyond the completed `probe_set_v1` and `late_aqp_low_budget_fix_v1` Qwen3-VL oracle runs.
- Any new YOLO or GPU inference.
- Extending feature extraction over additional video time.
- Any full replay or selector integration that uses labels beyond diagnostic evaluation.
- H7 human annotation: the package is ready at `outputs/late_aqp_h7_long_event_v1/`, but human annotation requires explicit authorization.
- Externalizing the >100MB CSV artifacts listed in `outputs/state_sync_late_aqp_v1/large_artifact_manifest.md` (e.g., moving them to external storage). Currently they are tracked in git; see the manifest for path/size and the recommended action.
