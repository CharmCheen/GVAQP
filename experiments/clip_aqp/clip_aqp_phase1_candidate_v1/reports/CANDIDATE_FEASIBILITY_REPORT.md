# Phase 1.4 Nexar Video-based Candidate Feasibility Report

## 1. Goal

Test whether non-oracle video-based candidate generators can produce high-recall returned clips for the Nexar-200 derived-boundary CASQ/G-ClipAQP benchmark. This run did not run VLMs, train models, build a large perception stack, or fabricate event boundaries.

## 2. Why this stage follows Phase 1.3

Phase 1.3 concluded `DISENTANGLE_DECISION: CANDIDATE_QUALITY_IS_MAIN_BOTTLENECK`: the repaired certificate can work when the returned set is good, but the practical metadata-hash returned set had true derived recall around 0.06. Phase 1.4 therefore first checks whether video content is accessible for practical candidate generation.

## 3. Data access and subset

A smoke subset of 50 positive and 50 normal manifest rows was selected without using alert/event timing fields for candidate generation. The manifest points to local video paths under the Nexar raw directory, but none of the smoke-subset files exists locally, and the available metadata files contain no remote download URLs.

| video_id | label | download_status | file_size | access_detail |
| --- | --- | --- | --- | --- |
| 00822.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00208.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00072.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00128.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00205.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00408.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00948.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00457.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00471.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00900.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00841.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00333.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00564.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00245.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00171.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00795.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00372.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00938.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00884.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |
| 00641.mp4 | positive | missing_no_download_url | 0 | manifest points to missing local file and metadata has no remote URL |

## 4. Candidate generators implemented

The pipeline scripts for fixed sliding windows, motion energy, YOLO count proxy, CLIP/SigLIP text score, and optional small-VLM score are staged to skip gracefully. Because video access failed, no practical candidate windows were generated.

| candidate_name | status | dependency_status | uses_oracle_annotation | uses_video_content | notes |
| --- | --- | --- | --- | --- | --- |
| fixed_sliding_window | skipped_no_video_access | available_metadata_only_but_not_run_without_video_access | False | False | No candidate windows generated because no Nexar video files were accessible. |
| motion_energy | skipped_no_video_access | available | False | True | No candidate windows generated because no Nexar video files were accessible. |
| yolo_count_proxy | skipped_no_video_access | available | False | True | No candidate windows generated because no Nexar video files were accessible. |
| clip_or_siglip_text_score | skipped_no_video_access | available | False | True | No candidate windows generated because no Nexar video files were accessible. |
| optional_small_vlm_score | skipped_no_video_access | missing_dependency_or_not_configured | False | True | No candidate windows generated because no Nexar video files were accessible. |

## 5. Leakage controls

Candidate generation was not allowed to use `alert_time`, `event_moment`, `event_start`, `event_end`, `derived_event_start`, or `derived_event_end`. The subset written for candidate generation excludes those timing fields; derived boundaries remain evaluation-only.

| check | passed | detail |
| --- | --- | --- |
| forbidden_time_fields_not_used_for_candidate_generation | True | subset selection used label balance only; event timing fields excluded from generation-safe subset |
| smoke_subset_50_positive_50_normal | True | positive=50, normal=50 |
| manifest_has_200_positive_200_normal | True | rows=400 |

## 6. Candidate recall vs budget

No candidate recall-vs-budget evaluation was run because no video files were accessible and no candidate sets were generated.

_empty_

## 7. Runtime and cost

GPU visible: `True`. GPU model: `NVIDIA A800-SXM4-80GB`. GPU used: `False`. Reason: No video files were accessible, so no GPU inference was run.

Runtime was limited to metadata access checks and placeholder table/report generation. Throughput and GPU cost for feature extraction are not meaningful because zero frames were processed.

## 8. Certificate results for promising candidates

No candidate configuration reached the evaluation stage, so there were no promising candidates with true derived recall >= 0.5 to certify. Certificate validity constraints are marked not applicable rather than passed.

_empty_

## 9. Limitations of derived boundaries

- Nexar intervals are derived from alert time to event moment and are not human-adjudicated original event boundaries.
- This access-blocked run cannot answer whether motion, YOLO, CLIP/SigLIP, or small-VLM candidates are sufficient.
- Any later candidate evaluation must continue to treat derived boundaries as oracle-relative evaluation only.

## 10. Recommendation

Obtain or link the controlled Nexar video subset before running feature extraction. Start with the 50 positive / 50 normal smoke subset, record GPU use explicitly, and only expand to 200 / 200 if access and runtime are reasonable.

CANDIDATE_DECISION: NEED_VIDEO_ACCESS
