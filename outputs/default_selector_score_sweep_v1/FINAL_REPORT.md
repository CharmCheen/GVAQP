# Default Selector Score Sweep v1 Final Report

Date: 2026-07-03

## Scope

This is a no-new-VLM development replay over the allowed default selector family: `score_topk + temporal NMS + duration cap`. It sweeps cheap score columns and temporal NMS gaps on the V13.8 center10 VLM-defined oracle reference.

All recall/precision/F1 numbers are labeled `v13_8_center10_oracle`; they are not human-ground-truth dangerous-event claims. `probe_set_v1` is not used.

## Best Methods By Budget

The table below includes `gap0` ablations. `gap0` is useful diagnostically because it degenerates to raw score ranking, but it is not the active-NMS operating recommendation.

| Budget | Best clip-F1 method | Clip F1 v13_8_center10_oracle | Clip precision | Clip recall | Event recall | Best event method | Best event recall |
|---:|---|---:|---:|---:|---:|---|---:|
| 5 | `score_topk_nms_yolo_vehicle_max_gap0` | 0.101 | 1.000 | 0.053 | 0.098 | `score_topk_nms_yolo_vehicle_max_gap0` | 0.098 |
| 10 | `score_topk_nms_bottom_roi_vehicle_count_mean_gap0` | 0.135 | 0.700 | 0.074 | 0.059 | `score_topk_nms_yolo_vehicle_mean_gap60` | 0.118 |
| 20 | `score_topk_nms_bottom_roi_vehicle_count_mean_gap0` | 0.246 | 0.700 | 0.149 | 0.098 | `score_topk_nms_yolo_vehicle_max_gap20` | 0.157 |
| 40 | `score_topk_nms_yolo_vehicle_mean_gap0` | 0.358 | 0.600 | 0.255 | 0.196 | `score_topk_nms_yolo_vehicle_max_gap60` | 0.294 |
| 80 | `score_topk_nms_yolo_vehicle_max_gap0` | 0.471 | 0.512 | 0.436 | 0.333 | `score_topk_nms_yolo_vehicle_mean_gap20` | 0.451 |
| 120 | `score_topk_nms_yolo_vehicle_mean_gap0` | 0.495 | 0.442 | 0.564 | 0.471 | `score_topk_nms_bottom_roi_vehicle_count_mean_gap20` | 0.569 |

## Active-NMS Recommendation

This table excludes `gap0` and `gap10`, keeping only configurations with active temporal suppression (`gap >= 20s`).

| Budget | Best active-NMS clip-F1 method | Clip F1 v13_8_center10_oracle | Clip precision | Clip recall | Event recall | Best active-NMS event method | Best event recall |
|---:|---|---:|---:|---:|---:|---|---:|
| 5 | `score_topk_nms_yolo_vehicle_max_gap20` | 0.101 | 1.000 | 0.053 | 0.098 | `score_topk_nms_yolo_vehicle_max_gap20` | 0.098 |
| 10 | `score_topk_nms_yolo_vehicle_mean_gap60` | 0.115 | 0.600 | 0.064 | 0.118 | `score_topk_nms_yolo_vehicle_mean_gap60` | 0.118 |
| 20 | `score_topk_nms_yolo_vehicle_max_gap20` | 0.211 | 0.600 | 0.128 | 0.157 | `score_topk_nms_yolo_vehicle_max_gap20` | 0.157 |
| 40 | `score_topk_nms_yolo_vehicle_max_gap20` | 0.299 | 0.500 | 0.213 | 0.294 | `score_topk_nms_yolo_vehicle_max_gap60` | 0.294 |
| 80 | `score_topk_nms_yolo_vehicle_mean_gap90` | 0.437 | 0.475 | 0.404 | 0.451 | `score_topk_nms_yolo_vehicle_mean_gap20` | 0.451 |
| 120 | `score_topk_nms_yolo_vehicle_max_gap60` | 0.486 | 0.433 | 0.553 | 0.569 | `score_topk_nms_bottom_roi_vehicle_count_mean_gap20` | 0.569 |

## B40 Comparison Against Current Fusion Gap30

- Current fusion gap30 clip F1 v13_8_center10_oracle: 0.224.
- Best active-NMS B40 clip F1 v13_8_center10_oracle: 0.299 via `score_topk_nms_yolo_vehicle_max_gap20`.
- Delta clip F1 v13_8_center10_oracle: 0.075.

This supports a dev-only score choice change within the fixed default selector family, not a CILS promotion and not a formal guarantee.

## Sanity Checks

| Check | Status | Details |
|---|---|---|
| 100pct_budget_deterministic_clip_and_event_recall_is_1 | PASS | All score/NMS configs fill all anchors at B=399. |
| random_mean_recall_curves_monotonic | PASS | 100 random repeats. |
| temporal_nms_gap0_degenerates_to_raw_score_ranking | PASS | Gap 0 compared with raw score order. |
| sorting_functions_do_not_read_oracle_labels | PASS | Selector uses score columns and anchor_time only; labels/events are read only in metrics(). |
| duplicate_selected_clips_not_counted_as_multiple_calls | PASS | All selections are unique anchor IDs. |

## Output Files

- `tables/input_audit.csv`
- `tables/method_budget_results_raw.csv`
- `tables/method_budget_summary.csv`
- `tables/best_methods_by_budget.csv`
- `tables/active_nms_best_methods_by_budget.csv`
- `tables/sanity_checks.csv`
- `figures/clip_f1_curve.svg`
- `figures/event_recall_curve.svg`

FINAL_DECISION: GO
