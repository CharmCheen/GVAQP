# MRPO-V1 Contract Completion Matrix

| requirement                                                | status                              | authoritative_evidence                                                                                 |
|:-----------------------------------------------------------|:------------------------------------|:-------------------------------------------------------------------------------------------------------|
| Frozen objective and claim scope                           | PASS                                | contracts/frozen_contract.json; reports/FINAL_PROXY_DECISION.md                                        |
| Two design videos; no validation/test reuse                | PASS                                | audits/asset_audit.json                                                                                |
| 40/60/90/120 region candidates and retained tails          | PASS                                | audits/label_audit.json; experiments/macro_region_sensitivity/phase0_label_sensitivity.csv             |
| Selected length and partition hash                         | PASS                                | contracts/frozen_stage_a_candidate.json                                                                |
| Preview config count <=4 and label-free selection          | PASS                                | preview/operator_manifests/P0_SELECTION.json                                                           |
| Every preview config cost/determinism/coverage/missingness | PASS                                | audits/preview_cost_audit.json; preview/operator_manifests/P0_SELECTION.json                           |
| Preview ratio <=0.10 and cost decomposition                | PASS                                | audits/preview_cost_audit.json                                                                         |
| Canonical midpoint mapping; boundary tie; event once       | PASS                                | audits/label_audit.json; labels/event_region_map.parquet                                               |
| 263 exposable, 268 all, ceiling reported                   | PASS                                | audits/asset_audit.json; metrics/ranking_metrics.json                                                  |
| Binary/count labels and H0 empty                           | PASS                                | contracts/label_contract.json; labels/region_binary_labels.parquet; labels/region_count_labels.parquet |
| Feature families <=8 and forbidden intersection empty      | PASS                                | audits/feature_legality_audit.json; audits/leakage_audit.json                                          |
| Model families <=5; configs <=50; constraints              | PASS                                | experiments/models/config_ranking.csv; contracts/search_budget.json                                    |
| B0-B8 mandatory controls                                   | PASS                                | experiments/controls/                                                                                  |
| Random >=100 seeds/video                                   | PASS                                | metrics/random_baseline_distribution.json                                                              |
| Primary Recall@20 complete-region cost                     | PASS                                | metrics/ranking_metrics.json; metrics/per_region_metrics.csv                                           |
| Recall@10/30, AUC, AUPRC, Spearman, used cost              | PASS                                | metrics/per_video_metrics.csv                                                                          |
| Binary Brier and Count MAE                                 | PASS                                | metrics/per_video_metrics.csv; predictions/candidate_lovo_calibration_predictions.parquet              |
| Per-video and nested leave-one-video-out direction         | PASS                                | metrics/leave_one_video_out_direction.json                                                             |
| Leave-best-region-out and contribution ratio               | PASS                                | metrics/ranking_metrics.json                                                                           |
| Preview-cost-adjusted net yield at 60s and frozen q grid   | PASS                                | metrics/net_event_yield_budget_grid.csv; metrics/cost_adjusted_metrics.json                            |
| Phase 0-3 completed within search budget                   | PASS                                | reports/PHASE0_ASSET_AND_LABEL_AUDIT.md; experiments/                                                  |
| Exploratory Gate evaluated                                 | PASS                                | metrics/exploratory_gate.json                                                                          |
| Formal validation                                          | NOT_APPLICABLE_PREREQUISITE_MISSING | VALIDATION_VIDEO_COUNT=0; contract requires >=4                                                        |
| One-step allocator                                         | CORRECTLY_BLOCKED_BY_FAILED_GATE    | metrics/exploratory_gate.json                                                                          |
| Guarded marginal/RL/Bandit prohibited                      | PASS_NOT_IMPLEMENTED                | reports/FINAL_PROXY_DECISION.md                                                                        |
| All nine failure-analysis categories                       | PASS                                | reports/FAILURE_ANALYSIS.md; metrics/failure_analysis_metrics.json                                     |
| Required deliverable tree                                  | PASS                                | artifact_hash_manifest.json; reports/INDEPENDENT_RESULT_AUDIT.json                                     |
| Final terminal fields                                      | PASS                                | reports/FINAL_PROXY_DECISION.md                                                                        |
