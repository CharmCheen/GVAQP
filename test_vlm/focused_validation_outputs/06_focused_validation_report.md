# Focused Validation Report

## 1. Experimental Definition
- full conservative VLM scan = pseudo-oracle target.
- This is not human GT.
- The evaluation target is budgeted recovery of VLM-defined positive clips/events using fewer VLM calls.
- Metrics are named `oracle_clip_recall`, `oracle_event_recall`, `oracle_event_precision`, `vlm_call_saving`, and `budgeted_event_iou`.

## 2. Input Inventory
- input directory: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded`
- labels: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv`
- proxy: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores_with_learned.csv`
- detected clips: 1000

## 3. Pseudo-oracle Statistics
- total clips: 1000
- positive clips: 61
- negative clips: 939
- positive rate: 0.061
- segments: 11
- top 3 segment positive share: 0.918

Top positive segments:

| segment_id | positive_clips |
| --- | --- |
| realcartest_seg001 | 36 |
| realcartest_seg005 | 16 |
| realcartest_5k_seg001 | 4 |
| realcartest_5k_seg002 | 2 |
| realcartest_seg003 | 2 |
| test_seg001 | 1 |
| realcartest_seg002 | 0 |
| realcartest_seg004 | 0 |
| realcartest_seg006 | 0 |
| realcartest_seg007 | 0 |

## 4. Human Sanity Check Package
- audit CSV: `focused_validation_outputs/02_audit_package/priority_audit_clips.csv`
- clips selected: 40
- Selection covers VLM positives, hard negatives, boundary negatives, and random negatives.
- Human labels should be used to detect obvious VLM pseudo-oracle collapse, not to claim full human GT.

## 5. Fixed-window to Variable-event Conversion
- Merge rule: adjacent positive windows in the same segment are merged when temporal gap <= threshold.
- gap thresholds tested: [0, 3, 6, 10]
- IoU thresholds tested: [0.1, 0.3, 0.5]
- event metrics CSV: `focused_validation_outputs/03_event_conversion/event_level_metrics.csv`

Event-level result table at gap=3 sec, IoU=0.3, budgets 10% and 20%:

| policy | budget_fraction | oracle_event_recall | oracle_event_precision | mean_event_iou | vlm_call_saving |
| --- | --- | --- | --- | --- | --- |
| top_learned_logreg | 0.100 | 0.483 | 0.875 | 0.860 | 0.900 |
| top_learned_rf | 0.100 | 0.483 | 1.000 | 0.813 | 0.900 |
| top_count | 0.100 | 0.345 | 1.000 | 1.000 | 0.900 |
| temporal_nms_count | 0.100 | 0.345 | 1.000 | 0.924 | 0.900 |
| adaptive_count_nms_expand | 0.100 | 0.345 | 1.000 | 1.000 | 0.900 |
| proxy_then_expansion_count | 0.100 | 0.276 | 1.000 | 1.000 | 0.900 |
| random | 0.100 | 0.034 | 0.200 | 0.556 | 0.900 |
| top_learned_rf | 0.200 | 0.655 | 0.864 | 0.919 | 0.800 |
| top_learned_logreg | 0.200 | 0.621 | 0.947 | 0.926 | 0.800 |
| top_count | 0.200 | 0.586 | 1.000 | 0.974 | 0.800 |
| adaptive_count_nms_expand | 0.200 | 0.586 | 1.000 | 0.974 | 0.800 |
| temporal_nms_count | 0.200 | 0.483 | 1.000 | 0.865 | 0.800 |
| proxy_then_expansion_count | 0.200 | 0.483 | 1.000 | 1.000 | 0.800 |
| random | 0.200 | 0.172 | 0.556 | 0.904 | 0.800 |

## 6. Temporal / Segment Concentration
- 61 positives concentrated in top 1 segment share: 0.590; top 3 share: 0.918.
- oracle events at gap=3 sec: 29.
- top 1 segment event share: 0.414.
- top_count / learned_proxy do not appear to be evaluated solely by one event if event recall is spread across multiple segments; inspect `method_selected_segment_distribution.csv` and timelines for manual confirmation.
- event-level recall comes from multiple independent oracle events when `matched_oracle_events` exceeds the top segment event count in `event_level_metrics.csv`.

## 7. 20-trial Smoke Stability
- random 20-seed summary: `focused_validation_outputs/05_smoke_trials/random_20seed_summary.csv`
- block bootstrap metrics: `focused_validation_outputs/05_smoke_trials/block_bootstrap_metrics.csv`
- policy rank stability: `focused_validation_outputs/05_smoke_trials/policy_rank_stability.csv`
- budget sensitivity: `focused_validation_outputs/05_smoke_trials/budget_sensitivity_metrics.csv`
- 20% random oracle_event_recall: 0.203
- 20% best non-random oracle_event_recall: 0.655
- Proxy-guided methods are considered stable only if they beat random across segment bootstrap and budget sensitivity outputs.

## 8. Decision
C. benchmark is too temporally concentrated and needs a new video source

Rationale:
- positive rate is 0.061; not vacuous.
- top3 segment positive share is 0.918.
- best 20% non-random event recall is 0.655 vs random 0.203.
- This decision is still conditional on the 40-clip human sanity check not finding obvious pseudo-oracle collapse.

## 9. Next Recommended Step
Fill `02_audit_package/priority_audit_clips.csv`, then run a follow-up analysis comparing human sanity labels against VLM pseudo-oracle errors before launching 100-trial formal evaluation.

## 10. Sampling Baseline Diagnostic Addendum

- Output directory: `/qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/07_sampling_baseline_comparison`
- Main CSV: `/qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/07_sampling_baseline_comparison/sampling_baseline_comparison.csv`
- Per-trial CSV: `/qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/07_sampling_baseline_comparison/sampling_baseline_comparison_by_budget.csv`
- Diagnostic conclusion: proxy contains useful ranking signal on this pilot/dev set.
- These results remain relative to the full conservative VLM pseudo-oracle, not human ground truth.
- The pilot benchmark can diagnose proxy signal, but due to temporal/segment concentration it should still not be promoted to formal 100-trial main evaluation without a less concentrated video source.
