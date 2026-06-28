# Local Candidate Smoke Report

## 1. Goal

Smoke-test video-content candidate generators on local videos and clips already present in the G-ARC project. This is pipeline feasibility/debugging only, not a replacement for Nexar-200 or clean event-boundary evaluation.

## 2. Local video inventory

Inventoried local video files: `2564`. Readable files: `2564`.

| video_path | file_size_bytes | duration_seconds | readable | source_category |
| --- | --- | --- | --- | --- |
| /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00822.mp4 | 17428930 | 40.47 | True | nexar_smoke_video |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000000_e000006.mp4 | 2041667 | 6.033 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000002_e000008.mp4 | 1971034 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000004_e000010.mp4 | 1533031 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000006_e000012.mp4 | 1443882 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000008_e000014.mp4 | 1386350 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000010_e000016.mp4 | 1311496 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000012_e000018.mp4 | 1279329 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000014_e000020.mp4 | 1415911 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000016_e000022.mp4 | 1580683 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000018_e000024.mp4 | 1479400 | 5.983 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000020_e000026.mp4 | 1492102 | 5.983 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000022_e000028.mp4 | 1611911 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000024_e000030.mp4 | 1716958 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000026_e000032.mp4 | 1213414 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000028_e000034.mp4 | 833117 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000030_e000036.mp4 | 891979 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000032_e000038.mp4 | 1355451 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000034_e000040.mp4 | 1585370 | 6 | True | local_clip |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/clips/round1_extra/test_s000036_e000042.mp4 | 1427441 | 6 | True | local_clip |

## 3. Local label inventory

Inventoried local label/proxy files: `181`.

| file_path | row_count | has_clip_id | has_start_end | has_oracle_label | has_human_label | has_proxy_score |
| --- | --- | --- | --- | --- | --- | --- |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/candidate_coverage_gate_v1/logs/progress.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/candidate_coverage_gate_v1/reports/00_asset_audit.md |  | True | True | False | False | True |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/candidate_coverage_gate_v1/reports/FINAL_CANDIDATE_COVERAGE_GATE_REPORT.md |  | False | False | False | False | True |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/candidate_coverage_gate_v1/reports/RESULT_INTERPRETATION.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/data_audit/phase0_units.csv | 1000 | True | True | False | True | True |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/diagnostics_v1/logs/progress.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/diagnostics_v1/reports/DIAGNOSTIC_REPORT.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/logs/progress.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/power_v1/logs/progress.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/power_v1/reports/POWER_REPORT.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/power_v1/tables/empirical_reference_blocks.csv | 397 | False | True | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/power_v1/tables/empirical_unique_blocks.csv | 1616 | False | True | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/logs/progress.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/reports/BLOCK_AUDIT_RECOMPUTE_CHECK.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/reports/BOUND_FORMULA_UNIT_TEST.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/reports/CERTIFICATION_ORACLE_IDENTITY.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/reports/PHASE0_REPORT_v2.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/reports/ROOT_CAUSE.md |  | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/tables/block_audit_rows_v2.csv | 2.272e+05 | False | True | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/reports/DATA_AUDIT.md |  | False | True | False | True | True |

## 4. Smoke dataset construction

Built `102` local-pseudo units from `kinematic_proxy` clips. `has_clean_event_boundary` is false for all units; no event_start/event_end boundaries were fabricated.

| dataset | video_id | unit_id | source_video_path | start_time | end_time | duration | source_clip_path | label_source | oracle_label | human_label | proxy_score_existing | has_clean_event_boundary | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00000_s000000000ms_e000005000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 0 | 5 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00000_s000000000ms_e000005000ms.mp4 | conservative_vlm_pseudo_oracle | 0 |  | 0 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00001_s000002000ms_e000007000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 2 | 7 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00001_s000002000ms_e000007000ms.mp4 | human_audit_conservative | 0 | 0 | 0.5895 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00002_s000004000ms_e000009000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 4 | 9 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00002_s000004000ms_e000009000ms.mp4 | human_audit_conservative | 0 | 0 | 0.5283 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00003_s000006000ms_e000011000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 6 | 11 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00003_s000006000ms_e000011000ms.mp4 | human_audit_conservative | 0 | 0 | 0.5352 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00004_s000008000ms_e000013000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 8 | 13 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00004_s000008000ms_e000013000ms.mp4 | human_audit_conservative | 0 | 0 | 0.7255 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00005_s000010000ms_e000015000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 10 | 15 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00005_s000010000ms_e000015000ms.mp4 | human_audit_conservative | 1 | 0 | 0.925 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00006_s000012000ms_e000017000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 12 | 17 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00006_s000012000ms_e000017000ms.mp4 | human_audit_conservative | 1 | 1 | 0.6387 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00007_s000014000ms_e000019000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 14 | 19 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00007_s000014000ms_e000019000ms.mp4 | human_audit_conservative | 1 | 0 | 0.5867 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00008_s000016000ms_e000021000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 16 | 21 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00008_s000016000ms_e000021000ms.mp4 | human_audit_conservative | 1 | 1 | 0.5933 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00009_s000018000ms_e000023000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 18 | 23 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00009_s000018000ms_e000023000ms.mp4 | human_audit_conservative | 1 | 1 | 0.595 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00010_s000020000ms_e000025000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 20 | 25 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00010_s000020000ms_e000025000ms.mp4 | human_audit_conservative | 1 | 1 | 0.6698 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |
| local_kinematic_proxy_debug | realcartest_5k | realcartest_5k_clip00011_s000022000ms_e000027000ms | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 | 22 | 27 | 5 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips/realcartest_5k_clip00011_s000022000ms_e000027000ms.mp4 | human_audit_conservative | 1 | 1 | 0.6802 | False | local-pseudo debugging unit; no clean event boundary; label is not human-truth event interval |

## 5. Candidate generators

| candidate_name | status | uses_oracle_annotation |
| --- | --- | --- |
| fixed_sliding_window | completed | False |
| random | completed | False |
| motion_energy | completed | False |
| existing_proxy_score | completed | False |
| yolo_count_proxy | completed | False |
| optional_clip_or_siglip_score | skipped_no_local_model_assets | False |

## 6. Evaluation metrics and limitations

Because clean event boundaries are absent, evaluation is unit-level enrichment against available conservative VLM/human-audit labels. Metrics are positive coverage, precision@k, enrichment over the local positive base rate, returned duration, runtime, and throughput where available. These are local-pseudo debugging metrics, not strict event IoU recall.

## 7. Results

| candidate_name | k | label_column | top_k_recall_or_positive_rate | precision_at_k | enrichment_over_random | event_or_positive_coverage_if_available | returned_duration | runtime | throughput_fps | positive_count_at_k | total_positive_count | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| motion_energy | 5 | human_label_eval | 0.05 | 0.2 | 1.02 | 0.05 | 25 | 0.4276 |  | 1 | 20 | unit-level local-pseudo enrichment; no event IoU recall because clean event boundaries are absent |
| yolo_count_proxy | 5 | human_label_eval | 0.05 | 0.2 | 1.02 | 0.05 | 25 | 24.39 |  | 1 | 20 | unit-level local-pseudo enrichment; no event IoU recall because clean event boundaries are absent |
| existing_proxy_score | 5 | human_label_eval | 0 | 0 | 0 | 0 | 25 | 0.001637 |  | 0 | 20 | unit-level local-pseudo enrichment; no event IoU recall because clean event boundaries are absent |
| fixed_sliding_window | 5 | human_label_eval | 0 | 0 | 0 | 0 | 25 | 0.001292 |  | 0 | 20 | unit-level local-pseudo enrichment; no event IoU recall because clean event boundaries are absent |
| random | 5 | human_label_eval | 0 | 0 | 0 | 0 | 25 | 0.001486 |  | 0 | 20 | unit-level local-pseudo enrichment; no event IoU recall because clean event boundaries are absent |

Full results: `tables/local_candidate_eval_results.csv`.

## 8. Runtime / GPU usage

GPU visible: `True`. GPU used: `True`. GPU model: `NVIDIA A800-SXM4-80GB`. YOLO status: `completed`. Frames processed by YOLO: `306`. YOLO throughput fps: `10.649652408101042`.

## 9. What can transfer to Nexar once videos are available

- Local media inventory, frame extraction, fixed-window generation, motion scoring, YOLO count features, candidate CSV schema, and unit-level evaluation code paths can transfer directly.
- The evaluation target must change from local-pseudo clip labels to Nexar derived-boundary or clean event-boundary evaluation when videos are available.
- Certificate claims still require the repaired block/event audit and must not use these local pseudo labels as human ground truth.

## 10. Recommendation

Use this code path as the bounded candidate smoke pipeline once Nexar videos are accessible. Keep local results as debugging evidence only.

LOCAL_CANDIDATE_DECISION: PIPELINE_READY_FOR_NEXAR_VIDEO
