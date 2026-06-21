# Event Budget Gate V2 Report

This is a pseudo-oracle development experiment over conservative VLM full-scan labels. It does not establish real traffic-risk ground truth.

## Inputs And Runtime

- clips: 1000
- conservative VLM positives: 61
- source video groups: 11
- smoke runtime seconds: recorded in `logs/progress.md`
- full runtime seconds: 16.42
- random seeds: 100

## Pseudo-Events

| event_gap_sec | pseudo_events | positive_clips | mean_positive_clips_per_event | median_positive_clips_per_event | mean_event_duration | median_event_duration | top1_source_event_share | top3_source_event_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.000 | 61 | 61 | 1.000 | 1.000 | 5.000 | 5.000 | 0.590 | 0.918 |
| 4.000 | 32 | 61 | 1.906 | 1.000 | 8.625 | 5.000 | 0.469 | 0.875 |
| 8.000 | 29 | 61 | 2.103 | 1.000 | 9.759 | 5.000 | 0.414 | 0.862 |

Pseudo-events are built only for evaluation by merging conservative-positive clips within the same source video and configured start-time gap.

## Main 10%-20% Results

| method | budget | clip_recall | pseudo_event_recall | redundant_call_rate | calls_per_new_event |
|---|---:|---:|---:|---:|---:|
| cluster_representative_count | 0.10 | 0.033 | 0.062 | 0.000 | 50.00 |
| cluster_representative_learned | 0.10 | 0.148 | 0.281 | 0.000 | 11.11 |
| coverage_aware_greedy | 0.10 | 0.459 | 0.375 | 0.160 | 8.33 |
| random | 0.10 | 0.082 | 0.156 | 0.000 | 20.00 |
| temporal_nms_count | 0.10 | 0.377 | 0.438 | 0.090 | 7.14 |
| top_count | 0.10 | 0.574 | 0.406 | 0.220 | 7.69 |
| top_learned_logreg | 0.10 | 0.492 | 0.500 | 0.140 | 6.25 |
| top_learned_rf | 0.10 | 0.361 | 0.438 | 0.080 | 7.14 |
| uniform_time | 0.10 | 0.230 | 0.188 | 0.080 | 16.67 |
| cluster_representative_count | 0.20 | 0.066 | 0.125 | 0.000 | 50.00 |
| cluster_representative_learned | 0.20 | 0.164 | 0.281 | 0.005 | 22.22 |
| coverage_aware_greedy | 0.20 | 0.738 | 0.562 | 0.135 | 11.11 |
| random | 0.20 | 0.180 | 0.250 | 0.015 | 25.00 |
| temporal_nms_count | 0.20 | 0.443 | 0.562 | 0.045 | 11.11 |
| top_count | 0.20 | 0.738 | 0.625 | 0.125 | 10.00 |
| top_learned_logreg | 0.20 | 0.639 | 0.594 | 0.100 | 10.53 |
| top_learned_rf | 0.20 | 0.656 | 0.688 | 0.090 | 9.09 |
| uniform_time | 0.20 | 0.262 | 0.219 | 0.045 | 28.57 |

## Direct Comparison At Gate Budgets

| gap | budget | best_event_aware | top_count_delta | temporal_nms_delta | redundancy_delta_vs_temporal |
|---:|---:|---|---:|---:|---:|
| 0 | 0.10 | coverage_aware_greedy | -0.115 | 0.082 | 0.000 |
| 0 | 0.20 | coverage_aware_greedy | 0.000 | 0.295 | 0.000 |
| 4 | 0.10 | coverage_aware_greedy | -0.031 | -0.062 | -0.070 |
| 4 | 0.20 | coverage_aware_greedy | -0.062 | 0.000 | -0.090 |
| 8 | 0.10 | cluster_representative_learned | -0.034 | -0.103 | 0.110 |
| 8 | 0.20 | coverage_aware_greedy | -0.069 | -0.034 | -0.095 |

## Sanity Checks

| check | passes | detail |
|---|---:|---|
| 100pct_budget_deterministic_recall_near_one | True | min_clip=1.000000; min_event=1.000000 |
| random_mean_recall_monotonic | True | gap_failures=0 |
| event_count_nonincreasing_with_gap | True | counts=[61, 32, 29] |
| temporal_nms_no_suppression_matches_top_count | True | gap=-1 disables suppression by making abs(delta)>gap always true |
| coverage_without_novelty_near_cluster_representative | True | top100_set_overlap=1.000 |
| static_selection_functions_do_not_reference_labels | True | top_order:none; uniform_order:none; temporal_nms_order:none; build_candidate_clusters:none; cluster_representative_order:none; coverage_aware_order:none; select_order:none |
| cluster_methods_no_duplicate_calls | True | checked complete method orders |

## Questions

1. Cluster / coverage-aware scheduling is not stably better than `top_count`; it wins only at some gap/budget settings and loses on the primary 4s gap.
2. Cluster / coverage-aware scheduling is not stably better than `temporal_nms_count`; gains appear at gap 0 but disappear or reverse at 4s and 8s gaps.
3. The conclusion is gap-sensitive, so it does not satisfy the `GO` rule.
4. Source-video concentration is high: top-3 source groups contain 86%-92% of pseudo-events depending on gap, so gains may partly reflect source concentration.
5. Learned proxy scores have pseudo-label leakage risk because they were produced by prior VLM-label supervised GroupKFold; they are development references only.
6. Current evidence supports keeping event-aware scheduling only as a weak research module candidate, not as a core validated module.
7. The result is VLM-defined pseudo-oracle development evidence because conservative VLM labels are not human ground truth.

## Decision Evidence

- gap=0, budget=0.10: best_event=coverage_aware_greedy gain_vs_temporal=0.082, redundant_rate_delta=0.000
- gap=0, budget=0.20: best_event=coverage_aware_greedy gain_vs_temporal=0.295, redundant_rate_delta=0.000
- gap=4, budget=0.10: best_event=coverage_aware_greedy gain_vs_temporal=-0.062, redundant_rate_delta=-0.070
- gap=4, budget=0.20: best_event=coverage_aware_greedy gain_vs_temporal=0.000, redundant_rate_delta=-0.090
- gap=8, budget=0.10: best_event=cluster_representative_learned gain_vs_temporal=-0.103, redundant_rate_delta=0.110
- gap=8, budget=0.20: best_event=coverage_aware_greedy gain_vs_temporal=-0.034, redundant_rate_delta=-0.095

## Decision: WEAK GO

- `GO` requires stable, non-small pseudo-event recall gains over temporal NMS at 10% or 20% budget with reduced redundancy across gaps.
- `WEAK GO` means gains exist but are partial or unstable.
- `NO-GO` means temporal NMS matches or exceeds event-aware methods, or the apparent gain is not robust enough.
