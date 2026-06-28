# Nexar Video Access Report

## 1. Goal

Resolve whether Nexar videos for the Phase 1.4 candidate feasibility benchmark can be accessed through local files, Hugging Face, Kaggle, or manual upload. This run did not run VLMs, GPU inference, training, candidate generation, or full-dataset download.

## 2. Local File Search

Local media files found under the target Nexar root and broader datasets tree: `2`. Manifest rows with an existing local file before HF download: `1`.

| video_id | label | manifest_local_video_path | matched_existing_path | local_exists | needed_for_smoke_subset |
| --- | --- | --- | --- | --- | --- |
| 00822.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00822.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00822.mp4 | True | True |
| 00208.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00208.mp4 | nan | False | True |
| 00072.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00072.mp4 | nan | False | True |
| 00128.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00128.mp4 | nan | False | True |
| 00205.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00205.mp4 | nan | False | True |
| 00408.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00408.mp4 | nan | False | True |
| 00948.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00948.mp4 | nan | False | True |
| 00457.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00457.mp4 | nan | False | True |
| 00471.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00471.mp4 | nan | False | True |
| 00900.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00900.mp4 | nan | False | True |
| 00841.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00841.mp4 | nan | False | True |
| 00333.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00333.mp4 | nan | False | True |
| 00564.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00564.mp4 | nan | False | True |
| 00245.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00245.mp4 | nan | False | True |
| 00171.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00171.mp4 | nan | False | True |
| 00795.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00795.mp4 | nan | False | True |
| 00372.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00372.mp4 | nan | False | True |
| 00938.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00938.mp4 | nan | False | True |
| 00884.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00884.mp4 | nan | False | True |
| 00641.mp4 | positive | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00641.mp4 | nan | False | True |

## 3. Hugging Face Access

Dataset repo checked: `nexar-ai/nexar_collision_prediction`. `huggingface-cli` installed: `True`. Python `datasets` installed: `True`. Repo info ok: `True`. File listing ok: `True`. File count: `2857`. Repo gated: `False`.

| access_status | count |
| --- | --- |
| hf_remote_available | 399 |
| local_available | 1 |

## 4. Kaggle Access

Kaggle CLI installed: `False`. Credentials exist: `False`. Status: `not_configured`. No Kaggle download was attempted.

## 5. Download Plan

The plan maps every Nexar-200 manifest row to a target path and expected remote source where available. The first 50 positive and 50 normal rows are marked as the Phase 1.4 smoke subset.

| video_id | filename | label | needed_for_smoke_subset | expected_remote_source | local_target_path | access_status | required_action | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 00822.mp4 | 00822.mp4 | positive | True | train/positive/00822.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00822.mp4 | local_available | use_local_file | HF listing metadata only; no full dataset download performed. |
| 00208.mp4 | 00208.mp4 | positive | True | train/positive/00208.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00208.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00072.mp4 | 00072.mp4 | positive | True | train/positive/00072.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00072.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00128.mp4 | 00128.mp4 | positive | True | train/positive/00128.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00128.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00205.mp4 | 00205.mp4 | positive | True | train/positive/00205.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00205.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00408.mp4 | 00408.mp4 | positive | True | train/positive/00408.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00408.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00948.mp4 | 00948.mp4 | positive | True | train/positive/00948.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00948.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00457.mp4 | 00457.mp4 | positive | True | train/positive/00457.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00457.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00471.mp4 | 00471.mp4 | positive | True | train/positive/00471.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00471.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00900.mp4 | 00900.mp4 | positive | True | train/positive/00900.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00900.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00841.mp4 | 00841.mp4 | positive | True | train/positive/00841.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00841.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00333.mp4 | 00333.mp4 | positive | True | train/positive/00333.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00333.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00564.mp4 | 00564.mp4 | positive | True | train/positive/00564.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00564.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00245.mp4 | 00245.mp4 | positive | True | train/positive/00245.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00245.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00171.mp4 | 00171.mp4 | positive | True | train/positive/00171.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00171.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00795.mp4 | 00795.mp4 | positive | True | train/positive/00795.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00795.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00372.mp4 | 00372.mp4 | positive | True | train/positive/00372.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00372.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00938.mp4 | 00938.mp4 | positive | True | train/positive/00938.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00938.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00884.mp4 | 00884.mp4 | positive | True | train/positive/00884.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00884.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |
| 00641.mp4 | 00641.mp4 | positive | True | train/positive/00641.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke/positive/00641.mp4 | hf_remote_available | download_smoke_only | HF listing metadata only; no full dataset download performed. |

## 6. Controlled Smoke Download

Target directory: `/qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_smoke`. Download cap: 5 positive and 5 normal videos.

| video_id | label | download_status | file_size | duration | readable | maps_back_to_manifest |
| --- | --- | --- | --- | --- | --- | --- |
| 00822.mp4 | positive | already_exists | 17428930 | 40.466667 | True | True |
| 00208.mp4 | positive | download_timeout | 0 | nan | False | True |
| 00072.mp4 | positive | download_timeout | 0 | nan | False | True |
| 00128.mp4 | positive | download_timeout | 0 | nan | False | True |
| 00205.mp4 | positive | download_timeout | 0 | nan | False | True |
| 01924.mp4 | negative | download_timeout | 0 | nan | False | True |
| 01429.mp4 | negative | download_timeout | 0 | nan | False | True |
| 01904.mp4 | negative | download_timeout | 0 | nan | False | True |
| 01486.mp4 | negative | download_timeout | 0 | nan | False | True |
| 01171.mp4 | negative | download_timeout | 0 | nan | False | True |

## 7. Verification

Verification requires file exists, file size > 0, readable duration from ffprobe or OpenCV, and filename mapping back to the Nexar-200 manifest.

Verified videos: `1/10`.

## 8. Recommendation

HF metadata access works, but the controlled unauthenticated smoke download did not verify all 10 videos. Configure an HF token or complete any required HF access step, then rerun the access audit.

VIDEO_ACCESS_DECISION: NEED_HF_AUTH_OR_LICENSE
