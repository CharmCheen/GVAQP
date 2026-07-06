# SQ-CRAQ Handoff

> **Note for future agents:** The root state files were previously out of sync with the actual experimental progress. As of `outputs/state_sync_late_aqp_v1/`, the LATE-AQP frontier is the mainline, not the Phase 3 selector smoke. Always read `PROJECT_STATE.md` first, then `CLAIMS_LEDGER.md`, then this file. Do **not** restart any of the failed routes listed in `FAILURES.md` without a new reason.

## Current Safe State

LATE-AQP pipeline (audit + discovery + repair + boundary guard + Core/Halo release) is implemented and validated under strict limited-oracle replay. Frozen v1 config passes the cross-segment replay; v2 cold-start fix is split-validated on a non-original tuning segment. No new VLM, YOLO, API, or GPU inference should run unless explicitly authorized.

## What "mainline" means here

- **Default selector**: `score_topk` + temporal NMS + duration cap (this is the AGENTS.md default and it has not been changed).
- **Default release module**: Core/Halo release (boundary guard up to `MAX_GUARDS_PER_SIDE=3` per side; positive guard bins merged into core; halo reported as diagnostic only). This is treated as a generic post-processing gain, not a LATE-specific advantage.
- **Strongest current empirical baseline (posthoc_eval)**: **B7-core** (B7 chunk-bandit + temporal expansion + Core/Halo). Use this as the comparison target for any new discovery policy.
- **Strongest strict-replay alternative**: **D3-norepair-core** (chunk-bandit Thompson sampling, no repair, Core/Halo release). Use this when the comparison must not use `event_id` for selection.
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

## Latest Important Outputs (read these before doing anything else)

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

## Pending / Blocked / Decision-Only

- T007: `probe_v2_expansion` — **blocked**, waiting on user decision.
- T008: probe_v2 launch decision — pending.
- T010: AQP selector/return-set redesign toward EC-AQP — **active / highest priority**.

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
