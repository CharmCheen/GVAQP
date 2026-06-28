# Data Asset Audit and Micro-CASQ Planning Report

## 1. Goal

Audit existing local data assets and plan a first Micro-CASQ adjudicated benchmark for `O_enter_ego_path_v0` without running VLM, YOLO, candidate generation, training, or dataset download.

## 2. Protocol Reference

Read `CASQ_CODEX_BRIEF_V12_1.md`. User-specified docs/clip_aqp/CASQ_CODEX_BRIEF_V12_1.md was missing; root CASQ_CODEX_BRIEF_V12_1.md was read as the available V12.1 protocol.

Key constraints applied: Nexar labels are `LOOSE_APPROXIMATION / AUDIT_UNRELIABLE`; old VLM labels are not human truth; no event boundaries were fabricated.

## 3. Data Discovery Scope

The audit searched under `/qiuyeqing/llama_prl/G-ARC` for CSV, Markdown, tarball, and relevant directory assets matching VLM, audit, clip, event, budget, proxy, candidate, Nexar, Roadclip, Phase 0, and Phase 1 patterns. Raw video directories were not recursively decoded or scanned beyond metadata-level directory existence.

## 4. Data Asset Inventory

- Discovered assets: 1268
- Tables: `tables/data_asset_inventory.csv`
- Report: `reports/DATA_ASSET_INVENTORY.md`

## 5. Data Role Classification

Definitions used in this audit:

- `debug_pipeline_data`: data useful for testing frame extraction, candidate generation, table schema, and scripts.
- `noisy_external_label_data`: data whose labels come from an external source such as Nexar alert/collision metadata and are not equivalent to `O_enter_ego_path_v0` unless audited.
- `candidate_mining_pool`: clips/windows/videos useful for finding possible `O_enter_ego_path_v0` events, but not treated as ground truth.
- `adjudication_pool`: selected clips/windows that should be reviewed by bounded 32B VLM and/or human adjudication.
- `gold_eval_candidate`: data that already has sufficiently clear labels and event boundaries to potentially enter a Micro-CASQ benchmark after verification.
- `not_currently_usable`: files/data lacking video path, timing, label semantics, or recoverable provenance.

Primary role counts: {'debug_pipeline_data': 231, 'not_currently_usable': 577, 'candidate_mining_pool': 357, 'noisy_external_label_data': 94, 'gold_eval_candidate': 9}

The classification is intentionally conservative. No noisy external, derived-boundary, pseudo-oracle, or old VLM label is promoted to gold.

## 6. Candidate Mining Pool

- Candidate pool size: 488314
- Source counts: {'gt_clips': 2010, 'priority_audit_clips': 40, 'oracle_events_gap0': 32, 'oracle_events_gap10': 27, 'oracle_events_gap3': 29, 'oracle_events_gap6': 29, 'returned_events_adaptive_count_nms_expand_budget10_gap0': 10, 'returned_events_adaptive_count_nms_expand_budget10_gap10': 10, 'returned_events_adaptive_count_nms_expand_budget10_gap3': 10, 'returned_events_adaptive_count_nms_expand_budget10_gap6': 10, 'returned_events_adaptive_count_nms_expand_budget15_gap0': 14, 'returned_events_adaptive_count_nms_expand_budget15_gap10': 13, 'returned_events_adaptive_count_nms_expand_budget15_gap3': 13, 'returned_events_adaptive_count_nms_expand_budget15_gap6': 13, 'returned_events_adaptive_count_nms_expand_budget20_gap0': 20, 'returned_events_adaptive_count_nms_expand_budget20_gap10': 16, 'returned_events_adaptive_count_nms_expand_budget20_gap3': 17, 'returned_events_adaptive_count_nms_expand_budget20_gap6': 17, 'returned_events_adaptive_count_nms_expand_budget25_gap0': 24, 'returned_events_adaptive_count_nms_expand_budget25_gap10': 20, 'returned_events_adaptive_count_nms_expand_budget25_gap3': 21, 'returned_events_adaptive_count_nms_expand_budget25_gap6': 21, 'returned_events_adaptive_count_nms_expand_budget30_gap0': 24, 'returned_events_adaptive_count_nms_expand_budget30_gap10': 19, 'returned_events_adaptive_count_nms_expand_budget30_gap3': 21, 'returned_events_adaptive_count_nms_expand_budget30_gap6': 21, 'returned_events_adaptive_count_nms_expand_budget5_gap0': 5, 'returned_events_adaptive_count_nms_expand_budget5_gap10': 5, 'returned_events_adaptive_count_nms_expand_budget5_gap3': 5, 'returned_events_adaptive_count_nms_expand_budget5_gap6': 5, 'returned_events_proxy_then_expansion_count_budget10_gap0': 10, 'returned_events_proxy_then_expansion_count_budget10_gap10': 8, 'returned_events_proxy_then_expansion_count_budget10_gap3': 8, 'returned_events_proxy_then_expansion_count_budget10_gap6': 8, 'returned_events_proxy_then_expansion_count_budget15_gap0': 13, 'returned_events_proxy_then_expansion_count_budget15_gap10': 9, 'returned_events_proxy_then_expansion_count_budget15_gap3': 10, 'returned_events_proxy_then_expansion_count_budget15_gap6': 10, 'returned_events_proxy_then_expansion_count_budget20_gap0': 18, 'returned_events_proxy_then_expansion_count_budget20_gap10': 13, 'returned_events_proxy_then_expansion_count_budget20_gap3': 14, 'returned_events_proxy_then_expansion_count_budget20_gap6': 14, 'returned_events_proxy_then_expansion_count_budget25_gap0': 24, 'returned_events_proxy_then_expansion_count_budget25_gap10': 19, 'returned_events_proxy_then_expansion_count_budget25_gap3': 20, 'returned_events_proxy_then_expansion_count_budget25_gap6': 20, 'returned_events_proxy_then_expansion_count_budget30_gap0': 26, 'returned_events_proxy_then_expansion_count_budget30_gap10': 21, 'returned_events_proxy_then_expansion_count_budget30_gap3': 23, 'returned_events_proxy_then_expansion_count_budget30_gap6': 23, 'returned_events_proxy_then_expansion_count_budget5_gap0': 5, 'returned_events_proxy_then_expansion_count_budget5_gap10': 5, 'returned_events_proxy_then_expansion_count_budget5_gap3': 5, 'returned_events_proxy_then_expansion_count_budget5_gap6': 5, 'returned_events_random_budget10_gap0': 5, 'returned_events_random_budget10_gap10': 5, 'returned_events_random_budget10_gap3': 5, 'returned_events_random_budget10_gap6': 5, 'returned_events_random_budget15_gap0': 6, 'returned_events_random_budget15_gap10': 5, 'returned_events_random_budget15_gap3': 6, 'returned_events_random_budget15_gap6': 6, 'returned_events_random_budget20_gap0': 10, 'returned_events_random_budget20_gap10': 8, 'returned_events_random_budget20_gap3': 9, 'returned_events_random_budget20_gap6': 9, 'returned_events_random_budget25_gap0': 12, 'returned_events_random_budget25_gap10': 10, 'returned_events_random_budget25_gap3': 11, 'returned_events_random_budget25_gap6': 11, 'returned_events_random_budget30_gap0': 15, 'returned_events_random_budget30_gap10': 11, 'returned_events_random_budget30_gap3': 13, 'returned_events_random_budget30_gap6': 13, 'returned_events_random_budget5_gap0': 4, 'returned_events_random_budget5_gap10': 4, 'returned_events_random_budget5_gap3': 4, 'returned_events_random_budget5_gap6': 4, 'returned_events_temporal_nms_count_budget10_gap0': 22, 'returned_events_temporal_nms_count_budget10_gap10': 10, 'returned_events_temporal_nms_count_budget10_gap3': 10, 'returned_events_temporal_nms_count_budget10_gap6': 10, 'returned_events_temporal_nms_count_budget15_gap0': 27, 'returned_events_temporal_nms_count_budget15_gap10': 13, 'returned_events_temporal_nms_count_budget15_gap3': 14, 'returned_events_temporal_nms_count_budget15_gap6': 14, 'returned_events_temporal_nms_count_budget20_gap0': 27, 'returned_events_temporal_nms_count_budget20_gap10': 13, 'returned_events_temporal_nms_count_budget20_gap3': 14, 'returned_events_temporal_nms_count_budget20_gap6': 14, 'returned_events_temporal_nms_count_budget25_gap0': 30, 'returned_events_temporal_nms_count_budget25_gap10': 16, 'returned_events_temporal_nms_count_budget25_gap3': 17, 'returned_events_temporal_nms_count_budget25_gap6': 17, 'returned_events_temporal_nms_count_budget30_gap0': 30, 'returned_events_temporal_nms_count_budget30_gap10': 16, 'returned_events_temporal_nms_count_budget30_gap3': 17, 'returned_events_temporal_nms_count_budget30_gap6': 17, 'returned_events_temporal_nms_count_budget5_gap0': 11, 'returned_events_temporal_nms_count_budget5_gap10': 7, 'returned_events_temporal_nms_count_budget5_gap3': 7, 'returned_events_temporal_nms_count_budget5_gap6': 7, 'returned_events_top_count_budget10_gap0': 13, 'returned_events_top_count_budget10_gap10': 9, 'returned_events_top_count_budget10_gap3': 10, 'returned_events_top_count_budget10_gap6': 10, 'returned_events_top_count_budget15_gap0': 16, 'returned_events_top_count_budget15_gap10': 11, 'returned_events_top_count_budget15_gap3': 12, 'returned_events_top_count_budget15_gap6': 12, 'returned_events_top_count_budget20_gap0': 21, 'returned_events_top_count_budget20_gap10': 16, 'returned_events_top_count_budget20_gap3': 17, 'returned_events_top_count_budget20_gap6': 17, 'returned_events_top_count_budget25_gap0': 24, 'returned_events_top_count_budget25_gap10': 19, 'returned_events_top_count_budget25_gap3': 21, 'returned_events_top_count_budget25_gap6': 21, 'returned_events_top_count_budget30_gap0': 24, 'returned_events_top_count_budget30_gap10': 19, 'returned_events_top_count_budget30_gap3': 21, 'returned_events_top_count_budget30_gap6': 21, 'returned_events_top_count_budget5_gap0': 6, 'returned_events_top_count_budget5_gap10': 6, 'returned_events_top_count_budget5_gap3': 6, 'returned_events_top_count_budget5_gap6': 6, 'returned_events_top_learned_logreg_budget10_gap0': 19, 'returned_events_top_learned_logreg_budget10_gap10': 16, 'returned_events_top_learned_logreg_budget10_gap3': 16, 'returned_events_top_learned_logreg_budget10_gap6': 16, 'returned_events_top_learned_logreg_budget15_gap0': 21, 'returned_events_top_learned_logreg_budget15_gap10': 18, 'returned_events_top_learned_logreg_budget15_gap3': 18, 'returned_events_top_learned_logreg_budget15_gap6': 18, 'returned_events_top_learned_logreg_budget20_gap0': 22, 'returned_events_top_learned_logreg_budget20_gap10': 17, 'returned_events_top_learned_logreg_budget20_gap3': 19, 'returned_events_top_learned_logreg_budget20_gap6': 19, 'returned_events_top_learned_logreg_budget25_gap0': 27, 'returned_events_top_learned_logreg_budget25_gap10': 20, 'returned_events_top_learned_logreg_budget25_gap3': 22, 'returned_events_top_learned_logreg_budget25_gap6': 22, 'returned_events_top_learned_logreg_budget30_gap0': 27, 'returned_events_top_learned_logreg_budget30_gap10': 21, 'returned_events_top_learned_logreg_budget30_gap3': 22, 'returned_events_top_learned_logreg_budget30_gap6': 22, 'returned_events_top_learned_logreg_budget5_gap0': 12, 'returned_events_top_learned_logreg_budget5_gap10': 11, 'returned_events_top_learned_logreg_budget5_gap3': 12, 'returned_events_top_learned_logreg_budget5_gap6': 12, 'returned_events_top_learned_rf_budget10_gap0': 15, 'returned_events_top_learned_rf_budget10_gap10': 14, 'returned_events_top_learned_rf_budget10_gap3': 14, 'returned_events_top_learned_rf_budget10_gap6': 14, 'returned_events_top_learned_rf_budget15_gap0': 24, 'returned_events_top_learned_rf_budget15_gap10': 18, 'returned_events_top_learned_rf_budget15_gap3': 20, 'returned_events_top_learned_rf_budget15_gap6': 20, 'returned_events_top_learned_rf_budget20_gap0': 26, 'returned_events_top_learned_rf_budget20_gap10': 19, 'returned_events_top_learned_rf_budget20_gap3': 22, 'returned_events_top_learned_rf_budget20_gap6': 22, 'returned_events_top_learned_rf_budget25_gap0': 27, 'returned_events_top_learned_rf_budget25_gap10': 20, 'returned_events_top_learned_rf_budget25_gap3': 23, 'returned_events_top_learned_rf_budget25_gap6': 23, 'returned_events_top_learned_rf_budget30_gap0': 27, 'returned_events_top_learned_rf_budget30_gap10': 20, 'returned_events_top_learned_rf_budget30_gap3': 22, 'returned_events_top_learned_rf_budget30_gap6': 22, 'returned_events_top_learned_rf_budget5_gap0': 9, 'returned_events_top_learned_rf_budget5_gap10': 8, 'returned_events_top_learned_rf_budget5_gap3': 8, 'returned_events_top_learned_rf_budget5_gap6': 8, 'oracle_events_gap3_for_concentration': 29, 'phase0_pseudo_events': 29, 'phase0_units': 1000, 'block_audit_rows_v2': 227200, 'candidate_subset_smoke': 100, 'candidate_generation_status': 5, 'nexar_conversion_status': 1, 'existing_proxy_score': 102, 'yolo_count_proxy': 103, 'local_candidate_generation_status': 6, 'R4_event_moment_window_10p0s': 200, 'R4_event_moment_window_15p0s': 200, 'R4_event_moment_window_5p0s': 200, 'casq_events': 225, 'casq_units_nexar_200': 4401, 'nexar_200_manifest': 400, 'nexar_200_conversion_status': 400, 'vlm_micro_audit': 400, 'nexar_candidate_subset_200': 400, 'nexar_candidate_subset_smoke': 100, 'nexar_video_mapping': 400, 'nexar_video_readability': 400, 'nexar_candidate_event_hits_v2': 31104, 'nexar_candidate_subset_balanced_readable': 384, 'nexar_candidate_subset_full_readable': 392, 'nexar_candidate_video_split_v2': 384, 'nexar_candidate_windows': 2000, 'nexar_video_mapping_v2': 400, 'nexar_video_readability_v2': 400, 'representation_candidate_status_v2': 1, 'casq_units_nexar_small': 550, 'nexar_small_manifest': 50, 'nexar_small_conversion_status': 50, 'nexar_200_target_video_manifest': 400, 'nexar_auth_smoke_manifest': 10, 'nexar_video_access_plan': 400, 'pseudo_events_gap_0p0': 61, 'pseudo_events_gap_4p0': 32, 'pseudo_events_gap_8p0': 29, 'kinematic_proxy': 53816, 'human_audit': 68, 'proxy_scores': 2602, 'vlm_labels_conservative': 1622, 'roadclip': 1746, 'predicted_clips': 144906, 'ground_truth_clips': 5931}
- Table: `tables/micro_casq_candidate_pool_index.csv`

Rows recommended for adjudication are mining seeds only, not labels.

## 7. Adjudication Sampling Plan

Target strata: likely positive, label disagreement, possible false negative, hard negative, and boundary uncertain.

Suggested first target: 50-100 confirmed positive events and 200-300 confirmed negative windows, with ambiguous/abstain retained but excluded from headline metrics.

## 8. Adjudication Schema

Schema: `schema/micro_casq_adjudication_schema.json`

Template: `tables/micro_casq_adjudication_template.csv`

## 9. Micro-CASQ Benchmark Protocol

Protocol: `reports/MICRO_CASQ_BENCHMARK_PROTOCOL.md`

Gold-eval rows require positive/negative labels, recoverable video path, clip timing, and `boundary_status=ok` for positive event-IoU metrics.

## 10. Data Path Decision

Decision memo: `reports/DATA_PATH_DECISION_MEMO.md`

Recommendation: `BUILD_MICRO_CASQ_FROM_EXISTING_DATA`

## 11. Risks and Limitations

- Existing pools are biased toward prior debugging and candidate experiments.
- Nexar-derived labels cannot support `O_enter_ego_path_v0` oracle-relative claims.
- Old VLM labels are useful for mining, not human truth.
- Human-audited subsets may be narrow and need boundary verification.
- A later adjudication run must remain bounded and must not become full-video VLM scanning.

## 12. Next Action

Select a bounded adjudication sample from `tables/micro_casq_adjudication_sampling_plan.csv`, review unique videos first, and populate `tables/micro_casq_adjudication_template.csv`. After adjudication, build Micro-CASQ v0 with video-level `candidate_dev`, `heldout_eval`, and fresh `certification_sample` splits.

## 13. Final Recommendation

DATA_PATH_RECOMMENDATION: BUILD_MICRO_CASQ_FROM_EXISTING_DATA
