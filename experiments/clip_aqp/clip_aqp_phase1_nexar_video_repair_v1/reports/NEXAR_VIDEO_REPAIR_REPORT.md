# Nexar Video Repair Report

## 1. Goal

Repair Nexar-200 video mapping by downloading exactly the videos required by `nexar_200_manifest.csv`, preserving Hugging Face relative paths under `videos_hf`.

## 2. Why previous candidate run failed

Previous candidate gate report exists and recorded 76 / 400 readable rows with 0 readable positives.

Prior artifacts used:

- `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1/reports/NEXAR_CANDIDATE_FEASIBILITY_REPORT.md`
- `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1/tables/nexar_video_mapping.csv`
- `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1/tables/nexar_video_readability.csv`

## 3. HF authentication status

- Status: `authenticated_token_present_whoami_failed`
- Username: ``
- Method: `hf auth whoami retried; local token present`

No Hugging Face token is printed or logged.

## 4. Manifest summary

| metric | value |
| --- | --- |
| total_rows | 400 |
| positive_rows | 200 |
| normal_negative_rows | 200 |
| available_columns | dataset, video_id, split, label, is_positive, is_normal, event_moment, alert_time, original_event_start, original_event_end, derived_event_start, derived_event_end, boundary_source, boundary_confidence, local_video_path, local_metadata_path, notes |
| filename_video_id_fields | video_id, local_video_path |

## 5. HF path resolution

- HF repo files listed: `2857`
- HF video files listed: `2844`
- Manifest rows resolved: `400 / 400`

| resolve_status | resolve_method | rows |
| --- | --- | --- |
| resolved | exact_filename | 400 |

Target manifest: `manifests/nexar_200_target_video_manifest.csv`.

## 6. Pre-download local inventory

- Local video files under `videos_hf`: `457`
- Readable local video files under `videos_hf`: `457`

Manifest-local match before download:

| label | rows | readable |
| --- | --- | --- |
| normal | 200 | 78 |
| positive | 200 | 168 |

Explicit pre-download counts:

- readable positive rows: `168`
- readable normal rows: `78`
- missing positive rows: `32`
- missing normal rows: `122`

## 7. Download repair result

| download_status | rows |
| --- | --- |
| downloaded | 146 |
| failed | 8 |
| skipped_already_readable | 246 |

Download table: `tables/download_repair_results.csv`.

## 8. Post-download readability

- total_manifest_rows: `400`
- readable_rows: `392`
- readable_fraction: `0.9800`
- positive_readable: `200 / 200` (`1.0000`)
- normal_readable: `192 / 200` (`0.9600`)

Post-download table: `tables/post_download_manifest_readability.csv`.

## 9. Remaining missing/unreadable files

Remaining unreadable manifest rows: `8`.

| manifest_row_id | video_id | label | resolved_hf_path | local_path | exists | file_size_bytes | readable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 330 | 01484.mp4 | normal | train/negative/01484.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_hf/train/negative/01484.mp4 | False | 0 | False |
| 331 | 01724.mp4 | normal | train/negative/01724.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_hf/train/negative/01724.mp4 | False | 0 | False |
| 332 | 01824.mp4 | normal | train/negative/01824.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_hf/train/negative/01824.mp4 | False | 0 | False |
| 333 | 01849.mp4 | normal | train/negative/01849.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_hf/train/negative/01849.mp4 | False | 0 | False |
| 334 | 01538.mp4 | normal | train/negative/01538.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_hf/train/negative/01538.mp4 | False | 0 | False |
| 348 | 01996.mp4 | normal | train/negative/01996.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_hf/train/negative/01996.mp4 | False | 0 | False |
| 349 | 01588.mp4 | normal | train/negative/01588.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_hf/train/negative/01588.mp4 | False | 0 | False |
| 350 | 01752.mp4 | normal | train/negative/01752.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_hf/train/negative/01752.mp4 | False | 0 | False |

## 10. Recommendation

Do not run candidate generation in this repair step. If the decision is `READY_FOR_NEXAR_CANDIDATE_RERUN`, rerun the Nexar candidate feasibility pipeline against the repaired `videos_hf` tree. If only partial readiness is reached, use an explicitly documented readable subset rather than claiming Nexar-200 completion.

VIDEO_REPAIR_DECISION: READY_FOR_NEXAR_CANDIDATE_RERUN
