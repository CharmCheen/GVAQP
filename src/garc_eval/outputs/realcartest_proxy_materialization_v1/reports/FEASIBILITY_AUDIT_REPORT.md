# FEASIBILITY_AUDIT_REPORT.md - realcartest L3 and high-selectivity feasibility

## Label Scope

- Positive means the existing V13.8 `O_enter_ego_path_v0` Qwen3-VL-32B oracle-relative label.
- Positive does not mean the cheap predicate itself is true, and no new oracle labels were generated.
- Label provenance is confirmed from V13.8 FINAL_REPORT: Qwen3-VL-32B-Instruct with the V13.6 prompt and negative-not-abstain rule.

## L3 Feasibility

| Key | Value |
|---|---:|
| labeled_anchors | 399 |
| positive_count | 94 |
| negative_count | 305 |
| positive_rate | 0.236 |
| object_count_mean_auc | 0.756 |
| label_provenance_trusted | YES |
| labels_enough_for_directional_l3_eval | YES |

| k | precision_at_k | recall_at_k | event_cluster_coverage |
|---:|---:|---:|---:|
| 5 | 1.000 | 0.053 | 3 |
| 10 | 0.800 | 0.085 | 4 |
| 20 | 0.800 | 0.170 | 7 |
| 40 | 0.675 | 0.287 | 11 |
| 80 | 0.625 | 0.532 | 21 |
| 100 | 0.530 | 0.564 | 23 |
| 399 | 0.236 | 1.000 | 51 |

## High-Selectivity Predicate Scout

| predicate | selected | selectivity | qwen_pos_rate | event_coverage | suitable |
|---|---:|---:|---:|---:|---|
| object_count_mean > 0 | 399 | 1.000 | 0.236 | 51 | NO |
| object_count_mean above median | 198 | 0.496 | 0.364 | 36 | YES |
| object_count_mean above 75th percentile | 100 | 0.251 | 0.530 | 23 | YES |
| vehicle_count_mean > 0 | 397 | 0.995 | 0.237 | 51 | NO |
| vehicle_count_mean above median | 197 | 0.494 | 0.350 | 35 | YES |
| person_count_mean > 0 | 249 | 0.624 | 0.281 | 39 | YES |
| lateral_presence_mean > 0.5 | 355 | 0.890 | 0.259 | 50 | NO |

## Circular Definition Warning

- NONE for this scout: positive counts/rates use existing independent V13.8 oracle labels, not predicate-implied pseudo-labels.

## Interpretation

- Engineering conclusion: realcartest has complete 2fps raw YOLO materialization and complete anchor features.
- Research caution: these are VLM-oracle-relative labels, not human truth; any Strategy 7 or L3 claim must retain that qualifier.
- Final feasibility decision from Phase 4/5: `REALCARTEST_PROXY_READY_FOR_SECOND_VIDEO_VALIDATION`.
