# Acceptance Audit

- Output timestamp: 2026-06-27T12:37:42Z
- Previous output directory: `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/realcartest_proxy_materialization_v1`
- Acceptance decision: `ACCEPT_REALCARTEST_FOR_STRICT_SECOND_VIDEO_VALIDATION`

## Required File Checks

| check | status | raw value | condition |
|---|---:|---|---|
| file_exists:FINAL_SUMMARY.md | PASS | True | required file exists |
| file_exists:RUN_LOG.md | PASS | True | required file exists |
| file_exists:reports/INPUT_INVENTORY.md | PASS | True | required file exists |
| file_exists:reports/SMOKE_TEST_REPORT.md | PASS | True | required file exists |
| file_exists:reports/FULL_RUN_REPORT.md | PASS | True | required file exists |
| file_exists:reports/ANCHOR_FEATURE_REPORT.md | PASS | True | required file exists |
| file_exists:reports/FEASIBILITY_AUDIT_REPORT.md | PASS | True | required file exists |
| file_exists:tables/realcartest_anchor_proxy_features_2fps.csv | PASS | True | required file exists |
| file_exists:tables/realcartest_l3_labeled_subset_eval.csv | PASS | True | required file exists |
| file_exists:tables/realcartest_high_selectivity_predicate_scout.csv | PASS | True | required file exists |
| file_exists:tables/final_decision.csv | PASS | True | required file exists |
| label_provenance | PASS | Qwen3-VL-32B/V13.6/O_enter_ego_path_v0 | V13.8 labels must be Qwen3-VL-32B V13.6 O_enter_ego_path_v0 and comparable to dataset3 query |
| dataset3_window_definition | PASS | confirmed center_time_s/anchor_time +/- 5 s | dataset3 object_count_mean window found and realcartest uses same window, or fallback explicitly marked |
| run_log_completeness | PASS | phase_mentions=28, decision_mentions=10, unattended_decision_recorded=True | RUN_LOG exists, records phases, and records unattended autonomous decisions |
| high_selectivity_scout | PASS | rows=7, circular=['NONE'] | CIRCULAR_DEFINITION_WARNING absent/NONE and positives are existing Qwen oracle labels |
| raw_feature_sanity | PASS | rows=399, positive=94, negative=305, feature_warning_rows=0, object_count_mean_auc=0.756418 | 399 rows, 94 positive, 305 negative, required proxy columns present, feature warnings 0 |
| acceptance_decision | ACCEPT_REALCARTEST_FOR_STRICT_SECOND_VIDEO_VALIDATION | missing_files=[]; label_status=PASS; window_confirmed=True | decision enum from task acceptance gate |

## Deployable vs Evaluation Boundary

- Deployable policy inputs for later phases are `anchor_id`, timestamp, cheap proxy scores, and GLM parsed labels.
- Existing Qwen labels and `event_cluster_id` are used only for evaluation metrics in this validation.

## Comparability Notes

- Label provenance is accepted only because the prior materialization reports V13.8 Qwen3-VL-32B with the V13.6 `O_enter_ego_path_v0` prompt.
- Window comparability is accepted only because dataset3 and realcartest both report a 10s center window, `center_time_s`/`anchor_time` +/- 5s.
- The high-selectivity scout is not treated as oracle-relative evidence beyond its existing Qwen-label evaluation columns.
