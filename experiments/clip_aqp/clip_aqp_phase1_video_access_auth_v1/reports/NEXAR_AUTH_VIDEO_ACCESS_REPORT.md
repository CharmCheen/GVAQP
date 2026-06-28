# Nexar Authenticated Video Access Report

## 1. Goal

Rerun Nexar video access with Hugging Face authentication and proceed only to a bounded 10-video smoke test. This run did not run VLMs, train models, run GPU inference, or run candidate generation.

## 2. HF auth status

| auth_status | hf_cli_available | huggingface_cli_available | whoami_returncode | whoami_user | message |
| --- | --- | --- | --- | --- | --- |
| not_authenticated | True | True | 1 |  | token never printed; auth checked via CLI whoami |

## 3. Previous access result summary

Previous audit found HF repo public/listable with 2,857 files, Nexar-200 filenames mapped to HF paths, Kaggle not configured, and 1/10 unauthenticated smoke videos verified before remaining downloads timed out.

Prior report: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_v1/reports/NEXAR_VIDEO_ACCESS_REPORT.md`.

## 4. Authenticated smoke manifest

| video_id | filename | label | is_positive | is_normal | hf_path | local_target_path | previous_status | auth_download_status | file_size_bytes | duration_seconds | readable | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 00822.mp4 | 00822.mp4 | positive | True | False | train/positive/00822.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00822.mp4 | already_exists | already_readable | 17428930 | 40.466667 | True | included existing readable prior smoke video |
| 00208.mp4 | 00208.mp4 | positive | True | False | train/positive/00208.mp4 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1/downloaded/positive/00208.mp4 | download_timeout | not_attempted_auth_missing | 0 | nan | False | selected from previous HF-mapped smoke plan |
| 00072.mp4 | 00072.mp4 | positive | True | False | train/positive/00072.mp4 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1/downloaded/positive/00072.mp4 | download_timeout | not_attempted_auth_missing | 0 | nan | False | selected from previous HF-mapped smoke plan |
| 00128.mp4 | 00128.mp4 | positive | True | False | train/positive/00128.mp4 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1/downloaded/positive/00128.mp4 | download_timeout | not_attempted_auth_missing | 0 | nan | False | selected from previous HF-mapped smoke plan |
| 00205.mp4 | 00205.mp4 | positive | True | False | train/positive/00205.mp4 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1/downloaded/positive/00205.mp4 | download_timeout | not_attempted_auth_missing | 0 | nan | False | selected from previous HF-mapped smoke plan |
| 01924.mp4 | 01924.mp4 | negative | False | True | train/negative/01924.mp4 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1/downloaded/negative/01924.mp4 | download_timeout | not_attempted_auth_missing | 0 | nan | False | selected from previous HF-mapped smoke plan |
| 01429.mp4 | 01429.mp4 | negative | False | True | train/negative/01429.mp4 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1/downloaded/negative/01429.mp4 | download_timeout | not_attempted_auth_missing | 0 | nan | False | selected from previous HF-mapped smoke plan |
| 01904.mp4 | 01904.mp4 | negative | False | True | train/negative/01904.mp4 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1/downloaded/negative/01904.mp4 | download_timeout | not_attempted_auth_missing | 0 | nan | False | selected from previous HF-mapped smoke plan |
| 01486.mp4 | 01486.mp4 | negative | False | True | train/negative/01486.mp4 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1/downloaded/negative/01486.mp4 | download_timeout | not_attempted_auth_missing | 0 | nan | False | selected from previous HF-mapped smoke plan |
| 01171.mp4 | 01171.mp4 | negative | False | True | train/negative/01171.mp4 | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1/downloaded/negative/01171.mp4 | download_timeout | not_attempted_auth_missing | 0 | nan | False | selected from previous HF-mapped smoke plan |

## 5. Download results

| video_id | label | auth_download_status | attempt_count | file_size_bytes | duration_seconds | readable |
| --- | --- | --- | --- | --- | --- | --- |
| 00822.mp4 | positive | already_readable | 0 | 17428930 | 40.466667 | True |
| 00208.mp4 | positive | not_attempted_auth_missing | 0 | 0 | nan | False |
| 00072.mp4 | positive | not_attempted_auth_missing | 0 | 0 | nan | False |
| 00128.mp4 | positive | not_attempted_auth_missing | 0 | 0 | nan | False |
| 00205.mp4 | positive | not_attempted_auth_missing | 0 | 0 | nan | False |
| 01924.mp4 | negative | not_attempted_auth_missing | 0 | 0 | nan | False |
| 01429.mp4 | negative | not_attempted_auth_missing | 0 | 0 | nan | False |
| 01904.mp4 | negative | not_attempted_auth_missing | 0 | 0 | nan | False |
| 01486.mp4 | negative | not_attempted_auth_missing | 0 | 0 | nan | False |
| 01171.mp4 | negative | not_attempted_auth_missing | 0 | 0 | nan | False |

## 6. Video readability verification

Readable videos: `1/10`. Videos with at least one frame read: `1/10`.

| video_id | file_exists | file_size_bytes | duration_seconds | readable | frame_read_ok | maps_back_to_manifest |
| --- | --- | --- | --- | --- | --- | --- |
| 00822.mp4 | True | 17428930 | 40.466667 | True | True | True |
| 00208.mp4 | False | 0 | nan | False | False | True |
| 00072.mp4 | False | 0 | nan | False | False | True |
| 00128.mp4 | False | 0 | nan | False | False | True |
| 00205.mp4 | False | 0 | nan | False | False | True |
| 01924.mp4 | False | 0 | nan | False | False | True |
| 01429.mp4 | False | 0 | nan | False | False | True |
| 01904.mp4 | False | 0 | nan | False | False | True |
| 01486.mp4 | False | 0 | nan | False | False | True |
| 01171.mp4 | False | 0 | nan | False | False | True |

## 7. Frame smoke result

| status | readable_videos | frames |
| --- | --- | --- |
| skipped_fewer_than_5_readable | 1 | 0 |

Frame index rows: `0`.

## 8. Remaining blockers

HF CLI is available, but this environment is not logged in. Missing-video downloads were intentionally skipped to avoid unauthenticated retries and token leakage.

## 9. Recommendation

Run `hf auth login` or otherwise configure a valid Hugging Face token outside the logs, then rerun `scripts/run_nexar_auth_video_access.sh`.

VIDEO_AUTH_DECISION: NEED_HF_AUTH_OR_LICENSE
