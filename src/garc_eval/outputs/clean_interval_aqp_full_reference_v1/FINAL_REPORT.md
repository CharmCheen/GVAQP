# FINAL REPORT: clean_interval_aqp_full_reference_v1

## 1. Mini-Universe

| video_id | source_path | t_start | t_end | duration | selection_reason |
| --- | --- | --- | --- | --- | --- |
| realcartest | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4 | 2000 | 3200 | 1200 | 20min window maximizing VLM-defined event count with mixed positives/background; 20 reference events, 32/120 positive center10 anchors. Reference labels used only for mini-universe curation, not proposal generation. |

The selected segment contains 600 2s units and 20 VLM-defined reference events.
Positive unit rate is 0.133.

## 2. Oracle / Reference Definition

Reference labels are rematerialized from V13.8 Qwen3-VL-32B center10 pseudo-oracle outputs for
`O_enter_ego_path_v0`. They are not human truth. Full reference is used for evaluation and oracle replay
lookup only.

## 3. Cheap Signal Quality

Top cheap signals by AUC:

| signal | auc | ap | base_positive_rate |
| --- | --- | --- | --- |
| primary_signal_score | 0.732897 | 0.341544 | 0.133333 |
| cheap_fused_score | 0.727187 | 0.266552 | 0.133333 |
| yolo_vehicle_count | 0.69595 | 0.258113 | 0.133333 |
| signal_disagreement | 0.651082 | 0.201975 | 0.133333 |
| object_density_change | 0.650601 | 0.246345 | 0.133333 |
| track_acceleration | 0.648101 | 0.177751 | 0.133333 |
| person_count | 0.638726 | 0.345179 | 0.133333 |
| relative_motion_score | 0.61012 | 0.156229 | 0.133333 |

## 4. Interval Lattice Proposal Quality

| method | proposal_recall_iou_0_3 | proposal_recall_iou_0_5 | number_of_intervals | avg_duration | median_duration | duplicate_rate | background_duration_ratio | positive_unit_fraction | budgeted_recall@5 | budgeted_precision@5 | budgeted_recall@10 | budgeted_precision@10 | budgeted_recall@20 | budgeted_precision@20 | budgeted_recall@40 | budgeted_precision@40 | budgeted_recall@80 | budgeted_precision@80 | budgeted_recall@120 | budgeted_precision@120 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fixed_window | 0.3 | 0.3 | 505 | 15.695 | 10 | 0.0772277 | 0.866535 | 0.133465 | 0 | 0 | 0 | 0 | 0.05 | 0.1 | 0.1 | 0.25 | 0.1 | 0.1375 | 0.15 | 0.125 |
| multi_signal_union | 0.2 | 0.1 | 81 | 6.66667 | 4 | 0 | 0.889915 | 0.110085 | 0.1 | 0.4 | 0.1 | 0.2 | 0.15 | 0.15 | 0.15 | 0.075 | 0.2 | 0.05 | 0.2 | 0.0493827 |
| peak_expand | 0.2 | 0.1 | 186 | 20.3871 | 22 | 0.172043 | 0.760217 | 0.239783 | 0 | 0 | 0 | 0 | 0.05 | 0.25 | 0.1 | 0.325 | 0.15 | 0.2 | 0.15 | 0.166667 |
| threshold_merge | 0.2 | 0.2 | 354 | 8.85876 | 6 | 0.0649718 | 0.869211 | 0.130789 | 0.1 | 0.4 | 0.1 | 0.3 | 0.1 | 0.2 | 0.2 | 0.225 | 0.2 | 0.1625 | 0.2 | 0.141667 |
| valley_split | 0.25 | 0.05 | 94 | 14.1489 | 6 | 0.0106383 | 0.890337 | 0.109663 | 0.1 | 0.4 | 0.1 | 0.2 | 0.2 | 0.2 | 0.25 | 0.15 | 0.25 | 0.075 | 0.25 | 0.0638298 |

## 5. Main Comparison: Budget vs Event Recall

| method | budget | tau | event_recall | precision | returned_duration_mean | duplicate_rate_mean |
| --- | --- | --- | --- | --- | --- | --- |
| CILS_full | 5 | 0.8 | 0 | 0 | 0 | 0 |
| CILS_full | 5 | 0.9 | 0 | 0 | 0 | 0 |
| CILS_full | 10 | 0.8 | 0 | 0 | 0 | 0 |
| CILS_full | 10 | 0.9 | 0 | 0 | 0 | 0 |
| CILS_full | 20 | 0.8 | 0.1 | 0.181818 | 178 | 0 |
| CILS_full | 20 | 0.9 | 0 | 0 | 0 | 0 |
| CILS_full | 40 | 0.8 | 0.15 | 0.384615 | 230 | 0.153846 |
| CILS_full | 40 | 0.9 | 0 | 0 | 0 | 0 |
| CILS_full | 80 | 0.8 | 0.15 | 0.227273 | 344 | 0.0909091 |
| CILS_full | 80 | 0.9 | 0.15 | 0.266667 | 336 | 0.0666667 |
| arc_plus_uniform_outside_audit_simplified | 5 | 0.8 | 0.101 | 0.645 | 121.62 | 0.01 |
| arc_plus_uniform_outside_audit_simplified | 5 | 0.9 | 0.101 | 0.645 | 121.62 | 0.01 |
| arc_plus_uniform_outside_audit_simplified | 10 | 0.8 | 0.2015 | 0.520667 | 350.58 | 0.116333 |
| arc_plus_uniform_outside_audit_simplified | 10 | 0.9 | 0.1065 | 0.565476 | 265.78 | 0.19119 |
| arc_plus_uniform_outside_audit_simplified | 20 | 0.8 | 0.199 | 0.470026 | 653.42 | 0.266871 |
| arc_plus_uniform_outside_audit_simplified | 20 | 0.9 | 0.111 | 0.473005 | 449.78 | 0.237818 |
| arc_plus_uniform_outside_audit_simplified | 40 | 0.8 | 0.208 | 0.460787 | 1069.98 | 0.346221 |
| arc_plus_uniform_outside_audit_simplified | 40 | 0.9 | 0.208 | 0.52522 | 550.98 | 0.274646 |
| arc_plus_uniform_outside_audit_simplified | 80 | 0.8 | 0.2165 | 0.226766 | 1952.22 | 0.159198 |
| arc_plus_uniform_outside_audit_simplified | 80 | 0.9 | 0.216 | 0.231245 | 1854.38 | 0.158542 |
| arc_style_prune_refine_simplified | 5 | 0.8 | 0.1 | 0.666667 | 118 | 0 |
| arc_style_prune_refine_simplified | 5 | 0.9 | 0.1 | 0.666667 | 118 | 0 |
| arc_style_prune_refine_simplified | 10 | 0.8 | 0.1 | 0.6 | 250 | 0.2 |
| arc_style_prune_refine_simplified | 10 | 0.9 | 0.1 | 0.6 | 250 | 0.2 |
| arc_style_prune_refine_simplified | 20 | 0.8 | 0.1 | 0.5 | 420 | 0.25 |
| arc_style_prune_refine_simplified | 20 | 0.9 | 0.1 | 0.5 | 420 | 0.25 |
| arc_style_prune_refine_simplified | 40 | 0.8 | 0.2 | 0.529412 | 554 | 0.294118 |
| arc_style_prune_refine_simplified | 40 | 0.9 | 0.2 | 0.529412 | 554 | 0.294118 |
| arc_style_prune_refine_simplified | 80 | 0.8 | 0.2 | 0.352941 | 1870 | 0.27451 |
| arc_style_prune_refine_simplified | 80 | 0.9 | 0.2 | 0.352941 | 1870 | 0.27451 |
| cheap_signal_only | 5 | 0.8 | 0.1 | 0.4 | 128 | 0 |
| cheap_signal_only | 5 | 0.9 | 0.1 | 0.4 | 128 | 0 |
| cheap_signal_only | 10 | 0.8 | 0.1 | 0.3 | 292 | 0.1 |
| cheap_signal_only | 10 | 0.9 | 0.1 | 0.3 | 292 | 0.1 |
| cheap_signal_only | 20 | 0.8 | 0.1 | 0.2 | 504 | 0.1 |
| cheap_signal_only | 20 | 0.9 | 0.1 | 0.2 | 504 | 0.1 |
| cheap_signal_only | 40 | 0.8 | 0.2 | 0.225 | 766 | 0.125 |
| cheap_signal_only | 40 | 0.9 | 0.2 | 0.225 | 766 | 0.125 |
| cheap_signal_only | 80 | 0.8 | 0.2 | 0.225 | 2238 | 0.175 |
| cheap_signal_only | 80 | 0.9 | 0.2 | 0.225 | 2238 | 0.175 |
| fixed_window_topk | 5 | 0.8 | 0 | 0 | 90 | 0 |
| fixed_window_topk | 5 | 0.9 | 0 | 0 | 90 | 0 |
| fixed_window_topk | 10 | 0.8 | 0 | 0 | 170 | 0 |
| fixed_window_topk | 10 | 0.9 | 0 | 0 | 170 | 0 |
| fixed_window_topk | 20 | 0.8 | 0.05 | 0.1 | 380 | 0.05 |
| fixed_window_topk | 20 | 0.9 | 0.05 | 0.1 | 380 | 0.05 |
| fixed_window_topk | 40 | 0.8 | 0.1 | 0.25 | 760 | 0.2 |
| fixed_window_topk | 40 | 0.9 | 0.1 | 0.25 | 760 | 0.2 |
| fixed_window_topk | 80 | 0.8 | 0.1 | 0.1375 | 1450 | 0.1125 |
| fixed_window_topk | 80 | 0.9 | 0.1 | 0.1375 | 1450 | 0.1125 |
| oracle_confirmed_only | 5 | 0.8 | 0.1 | 0.666667 | 118 | 0 |
| oracle_confirmed_only | 5 | 0.9 | 0.1 | 0.666667 | 118 | 0 |
| oracle_confirmed_only | 10 | 0.8 | 0.1 | 0.6 | 250 | 0.2 |
| oracle_confirmed_only | 10 | 0.9 | 0.1 | 0.6 | 250 | 0.2 |
| oracle_confirmed_only | 20 | 0.8 | 0.1 | 0.5 | 420 | 0.25 |
| oracle_confirmed_only | 20 | 0.9 | 0.1 | 0.5 | 420 | 0.25 |
| oracle_confirmed_only | 40 | 0.8 | 0.2 | 0.529412 | 554 | 0.294118 |
| oracle_confirmed_only | 40 | 0.9 | 0.2 | 0.529412 | 554 | 0.294118 |
| oracle_confirmed_only | 80 | 0.8 | 0.2 | 0.352941 | 1870 | 0.27451 |
| oracle_confirmed_only | 80 | 0.9 | 0.2 | 0.352941 | 1870 | 0.27451 |
| oracle_full_scan_upper_bound | 5 | 0.8 | 0.25 | 1 | 34 | 0 |
| oracle_full_scan_upper_bound | 5 | 0.9 | 0.25 | 1 | 34 | 0 |
| oracle_full_scan_upper_bound | 10 | 0.8 | 0.35 | 1 | 64 | 0 |
| oracle_full_scan_upper_bound | 10 | 0.9 | 0.35 | 1 | 64 | 0 |
| oracle_full_scan_upper_bound | 20 | 0.8 | 0.35 | 1 | 64 | 0 |
| oracle_full_scan_upper_bound | 20 | 0.9 | 0.35 | 1 | 64 | 0 |
| oracle_full_scan_upper_bound | 40 | 0.8 | 0.35 | 1 | 64 | 0 |
| oracle_full_scan_upper_bound | 40 | 0.9 | 0.35 | 1 | 64 | 0 |
| oracle_full_scan_upper_bound | 80 | 0.8 | 0.35 | 1 | 64 | 0 |
| oracle_full_scan_upper_bound | 80 | 0.9 | 0.35 | 1 | 64 | 0 |
| supg_on_windows_simplified | 5 | 0.8 | 0.0005 | 0.004 | 0.5 | 0.002 |
| supg_on_windows_simplified | 5 | 0.9 | 0 | 0 | 0 | 0 |
| supg_on_windows_simplified | 10 | 0.8 | 0.0015 | 0.006 | 10 | 0.003 |
| supg_on_windows_simplified | 10 | 0.9 | 0 | 0 | 0 | 0 |
| supg_on_windows_simplified | 20 | 0.8 | 0.0115 | 0.0252857 | 41.38 | 0.0133571 |
| supg_on_windows_simplified | 20 | 0.9 | 0 | 0 | 0 | 0 |
| supg_on_windows_simplified | 40 | 0.8 | 0.0235 | 0.0452724 | 167.52 | 0.030565 |
| supg_on_windows_simplified | 40 | 0.9 | 0 | 0 | 0 | 0 |
| supg_on_windows_simplified | 80 | 0.8 | 0.0375 | 0.0843471 | 212.74 | 0.0522101 |
| supg_on_windows_simplified | 80 | 0.9 | 0 | 0 | 0 | 0 |
| threshold_merge_topk | 5 | 0.8 | 0.1 | 0.4 | 128 | 0 |
| threshold_merge_topk | 5 | 0.9 | 0.1 | 0.4 | 128 | 0 |
| threshold_merge_topk | 10 | 0.8 | 0.1 | 0.3 | 292 | 0.1 |
| threshold_merge_topk | 10 | 0.9 | 0.1 | 0.3 | 292 | 0.1 |
| threshold_merge_topk | 20 | 0.8 | 0.1 | 0.2 | 504 | 0.1 |
| threshold_merge_topk | 20 | 0.9 | 0.1 | 0.2 | 504 | 0.1 |
| threshold_merge_topk | 40 | 0.8 | 0.2 | 0.225 | 816 | 0.125 |
| threshold_merge_topk | 40 | 0.9 | 0.2 | 0.225 | 816 | 0.125 |
| threshold_merge_topk | 80 | 0.8 | 0.2 | 0.1625 | 1210 | 0.1125 |
| threshold_merge_topk | 80 | 0.9 | 0.2 | 0.1625 | 1210 | 0.1125 |

## 6. Precision / Recall / Boundary / Duration / Duplicate Summary

See `precision_recall_duration_duplicate_summary.csv`. Main CILS table:

| method | budget | tau | event_recall_mean | event_recall_std | observed_precision_mean | returned_duration_mean | duplicate_rate_mean | precision_violation_rate | duration_inflation_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CILS_full | 5 | 0.8 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 5 | 0.9 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 10 | 0.8 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 10 | 0.9 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 20 | 0.8 | 0.1 | 0 | 0.181818 | 178 | 0 | 1 | 0 |
| CILS_full | 20 | 0.9 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 40 | 0.8 | 0.15 | 0 | 0.384615 | 230 | 0.153846 | 1 | 0 |
| CILS_full | 40 | 0.9 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 80 | 0.8 | 0.15 | 0 | 0.227273 | 344 | 0.0909091 | 1 | 0 |
| CILS_full | 80 | 0.9 | 0.15 | 0 | 0.266667 | 336 | 0.0666667 | 1 | 0 |

## 7. Ablation Conclusions

Mean ablation results are in `ablation_results.csv`. Compact view:

| ablation | event_recall_mean | precision_mean |
| --- | --- | --- |
| CILS_full | 0.055 | 0.106037 |
| fused_signal | 0.02 | 0.0766667 |
| no_boundary_quality | 0.06 | 0.104709 |
| no_calibration_raw_score | 0.075 | 0.833333 |
| no_duration_penalty | 0.07 | 0.109334 |
| no_lattice_fixed_windows | 0.005 | 0.025 |
| no_overlap_control | 0.06 | 0.131078 |
| primary_signal_only | 0.06 | 0.0339706 |

## 8. Stress Test Conclusions

| stress_test | event_recall_mean | precision_mean |
| --- | --- | --- |
| best_proxy | 0.02 | 0.0766667 |
| low_density_blindspot_proxy | 0.02 | 0.0766667 |
| noisy_proxy | 0.02 | 0.0766667 |
| partial_inverted_proxy | 0.02 | 0.0766667 |
| random_baseline | 0.0926 | 0.0894 |
| random_proxy | 0.02 | 0.0766667 |

## 9. Decision

Decision: `WEAK_OR_INCONCLUSIVE`.

Success criterion checked: CILS must improve event recall over both `threshold_merge_topk` and
`arc_style_prune_refine_simplified` at at least two budget points for tau 0.8 or 0.9, while maintaining
observed precision and without obvious duration or duplicate inflation.

Improvement budget counts by tau and required baseline:

_No rows._

Promising-by-tau flags: {}.

## 10. Next Step

If decision is PROMISING, the next step is a second clean mini-universe on a different long video before
claiming generalization. If weak or inconclusive, inspect calibration sparsity, blind spots, and whether
interval boundaries are too short for IoU>=0.3 event matching before running more VLM.

## Limitations

- This is a pseudo-oracle mini-universe experiment on a single selected segment.
- Universe selection used existing VLM labels for curation, so prevalence is not unbiased.
- Cached YOLOv8n detections were reused; optical flow is represented by a detection-derived burst proxy.
- No formal clip-level recall certificate is claimed here.
