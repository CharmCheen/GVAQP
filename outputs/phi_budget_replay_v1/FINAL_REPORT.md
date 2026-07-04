# Phi-Budget Replay v1 Final Report

Date: 2026-07-03

## Scope

This is a no-new-VLM replay on the V13.8 center10 VLM-defined oracle reference. It evaluates a first executable version of the pasted Phi-risk design: separate audit and discovery ledgers, an audit floor, and DISCOVER/REPAIR/REFINE action bidding by expected Phi reduction per oracle call.

All recall/precision numbers below are labeled `v13_8_center10_oracle`; they are not human-ground-truth dangerous-event claims.

## Inputs

- Oracle labels: `experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv` (399 rows, 94 positive anchors).
- VLM-defined stitched pseudo-events: `experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv` (51 events).
- Cheap proxy features: `experiments/v13/v13_7_multimethod_replay/tables/center10_proxy_features.csv` (399 rows, score `score_fusion_yolo_motion`).
- `probe_set_v1` was not used.

## Primary Result

| Budget | Phi event recall v13_8_center10_oracle | Default event recall v13_8_center10_oracle | Phi clip precision v13_8_center10_oracle | Default clip precision v13_8_center10_oracle |
|---:|---:|---:|---:|---:|
| 5 | 0.023 | 0.039 | 0.238 | 0.400 |
| 10 | 0.050 | 0.059 | 0.262 | 0.300 |
| 20 | 0.092 | 0.098 | 0.248 | 0.350 |
| 40 | 0.180 | 0.255 | 0.259 | 0.375 |
| 80 | 0.301 | 0.392 | 0.243 | 0.300 |
| 120 | 0.430 | 0.490 | 0.251 | 0.292 |

## Interpretation

The Phi replay is a useful executable scaffold, but it should not yet be promoted as the default selector. It introduces the intended accounting discipline and repair/refine frontier mechanics, yet the first policy still competes against a weak proxy and a single-video VLM-defined reference.

The project default remains `score_topk + temporal NMS + duration cap`; CILS is not used or promoted here.

## Sanity Checks

| Check | Status | Details |
|---|---|---|
| 100pct_budget_deterministic_clip_and_event_recall_is_1 | PASS | All deterministic methods select all anchors at B=399. |
| random_mean_recall_curves_monotonic | PASS | Checked after aggregation below. |
| event_count_nonincreasing_with_merge_gap | PASS | [{"merge_gap_anchors": 0, "event_count_from_positive_anchor_merge": 51}, {"merge_gap_anchors": 1, "event_count_from_positive_anchor_merge": 37}, {"merge_gap_anchors": 2, "event_count_from_positive_anchor_merge": 28}, {"merge_gap_anchors": 3, "event_count_from_positive_anchor_merge": 27}, {"merge_gap_anchors": 6, "event_count_from_positive_anchor_merge": 18}] |
| temporal_nms_gap0_degenerates_to_raw_score_ranking | PASS | Compared full score order with NMS gap=0. |
| sorting_functions_do_not_read_oracle_labels | PASS | Static selectors use proxy score columns and time only; Phi selector uses oracle labels only inside execute_call after selection. |
| cluster_methods_do_not_count_duplicate_selected_clips_as_multiple_calls | PASS | All policies select unique anchor IDs up to budget. |
| coverage_aware_novelty_disabled_cluster_rep_baseline | NOT_APPLICABLE | This experiment does not implement coverage-aware cluster scheduling; it implements Phi action bidding with repair/refine frontier actions. |

## Output Files

- `tables/input_audit.csv`
- `tables/stratum_audit.csv`
- `tables/method_budget_results_raw.csv`
- `tables/method_budget_summary.csv`
- `tables/best_methods_by_budget.csv`
- `tables/sanity_checks.csv`
- `tables/phi_policy_trace_seed0.csv`
- `figures/event_recall_curve.svg`
- `figures/clip_precision_curve.svg`

FINAL_DECISION: NO-GO
