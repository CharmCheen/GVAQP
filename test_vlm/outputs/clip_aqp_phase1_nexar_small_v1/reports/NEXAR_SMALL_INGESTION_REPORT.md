# Nexar Small-Subset CASQ Ingestion Report

## 1. Goal

Run a Phase 1.1 smoke test to determine whether a small Nexar subset can be mapped into CASQ event-boundary and unit/block schemas without downloading the full dataset, running VLMs, training models, or fabricating event boundaries.

## 2. Data Access Status

- Nexar scaffold README: `/qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/README_CASQ_MAPPING.md`
- README exists: `True`
- Access decision: `LOCAL_METADATA_READY`
- Access message: Prepared manifest from 2 metadata file(s); no videos downloaded.
- Hugging Face token present: `False`
- Hugging Face/API probe status: `not_run`
- Hugging Face/API probe error: none
- Metadata sources used: `['/qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/negative/metadata.csv', '/qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv']`
- Videos downloaded by this run: `False`

## 3. Download / Manifest Summary

- Manifest path: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_small_v1/download_manifest/nexar_small_manifest.csv`
- Manifest rows: `50`
- CASQ events converted: `25`
- CASQ units converted: `550`

| dataset | video_id | split | label | is_positive | is_normal | event_moment | alert_time | original_event_start | original_event_end | local_video_path | local_metadata_path | download_status | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nexar | 00822.mp4 | train | positive | True | False | 19.5 | 18.633 |  |  | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00822.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv | metadata_available_video_not_downloaded | selected from local/public metadata; expected video path recorded but video download not attempted |
| nexar | 00208.mp4 | train | positive | True | False | 19.8 | 19.233 |  |  | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00208.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv | metadata_available_video_not_downloaded | selected from local/public metadata; expected video path recorded but video download not attempted |
| nexar | 00072.mp4 | train | positive | True | False | 20.101 | 20.068 |  |  | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00072.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv | metadata_available_video_not_downloaded | selected from local/public metadata; expected video path recorded but video download not attempted |
| nexar | 00128.mp4 | train | positive | True | False | 19.267 | 18.333 |  |  | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00128.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv | metadata_available_video_not_downloaded | selected from local/public metadata; expected video path recorded but video download not attempted |
| nexar | 00205.mp4 | train | positive | True | False | 21.146 | 18.196 |  |  | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00205.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv | metadata_available_video_not_downloaded | selected from local/public metadata; expected video path recorded but video download not attempted |
| nexar | 00408.mp4 | train | positive | True | False | 19.953 | 17.551 |  |  | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00408.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv | metadata_available_video_not_downloaded | selected from local/public metadata; expected video path recorded but video download not attempted |
| nexar | 00948.mp4 | train | positive | True | False | 20.287 | 19.219 |  |  | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00948.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv | metadata_available_video_not_downloaded | selected from local/public metadata; expected video path recorded but video download not attempted |
| nexar | 00457.mp4 | train | positive | True | False | 19.6 | 19.367 |  |  | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00457.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv | metadata_available_video_not_downloaded | selected from local/public metadata; expected video path recorded but video download not attempted |
| nexar | 00471.mp4 | train | positive | True | False | 19.833 | 18.267 |  |  | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00471.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv | metadata_available_video_not_downloaded | selected from local/public metadata; expected video path recorded but video download not attempted |
| nexar | 00900.mp4 | train | positive | True | False | 21.177 | 17.942 |  |  | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/raw/train/positive/00900.mp4 | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv | metadata_available_video_not_downloaded | selected from local/public metadata; expected video path recorded but video download not attempted |

## 4. Annotation Fields Found

- Expected metadata files: `['metadata/train_metadata.csv', 'metadata/train_metadata.json', 'metadata/metadata.csv', 'metadata/metadata.jsonl']`
- Expected annotation fields: `['time_of_event', 'time_of_alert', 'label']`
- Original `event_start` / `event_end` exists in observed metadata: `False`
- Event moment observed in metadata: `True`
- Alert time observed in metadata: `True`
- Event moment / alert time expected from scaffold: `True`
- Positive identification: positive collision/near-collision cases with event/alert time
- Normal identification: normal-driving videos from metadata label when available

The observed public metadata contains `time_of_event` and `time_of_alert`, but not original interval fields named `event_start` / `event_end`.

## 5. CASQ Boundary Mapping

- If original `event_start` / `event_end` exist, converters use them directly with `boundary_source=original_annotation`.
- If `alert_time` and `event_moment` exist, converters derive `[alert_time, event_moment]` with `boundary_source=derived_from_alert_time_to_event_moment` and `boundary_confidence=medium`.
- If only `event_moment` exists, converters derive `[max(0, event_moment - 2.5), event_moment + 2.5]` with `boundary_source=derived_from_event_moment` and `boundary_confidence=low`.
- If only `alert_time` exists, converters derive `[alert_time, alert_time + 5.0]` with `boundary_source=derived_from_alert_time` and `boundary_confidence=low`.
- If neither original boundary nor event moment/alert time exists, no event boundary is created.

Derived boundaries are explicitly marked and must not be treated as original human interval annotations.

## 6. Converted CASQ Events

| metric | value |
| --- | --- |
| num_videos | 50 |
| num_positive_videos | 25 |
| num_normal_videos | 25 |
| num_casq_events | 25 |
| boundary_source_distribution | {'derived_from_alert_time_to_event_moment': 25} |
| boundary_confidence_distribution | {'medium': 25} |
| usable_event_boundaries | 25 |

Conversion status:

| video_id | conversion_status | notes |
| --- | --- | --- |
| 00822.mp4 | converted | derived precursor interval; not original human interval |
| 00208.mp4 | converted | derived precursor interval; not original human interval |
| 00072.mp4 | converted | derived precursor interval; not original human interval |
| 00128.mp4 | converted | derived precursor interval; not original human interval |
| 00205.mp4 | converted | derived precursor interval; not original human interval |
| 00408.mp4 | converted | derived precursor interval; not original human interval |
| 00948.mp4 | converted | derived precursor interval; not original human interval |
| 00457.mp4 | converted | derived precursor interval; not original human interval |
| 00471.mp4 | converted | derived precursor interval; not original human interval |
| 00900.mp4 | converted | derived precursor interval; not original human interval |
| 00841.mp4 | converted | derived precursor interval; not original human interval |
| 00333.mp4 | converted | derived precursor interval; not original human interval |
| 00564.mp4 | converted | derived precursor interval; not original human interval |
| 00245.mp4 | converted | derived precursor interval; not original human interval |
| 00171.mp4 | converted | derived precursor interval; not original human interval |
| 00795.mp4 | converted | derived precursor interval; not original human interval |
| 00372.mp4 | converted | derived precursor interval; not original human interval |
| 00938.mp4 | converted | derived precursor interval; not original human interval |
| 00884.mp4 | converted | derived precursor interval; not original human interval |
| 00641.mp4 | converted | derived precursor interval; not original human interval |

## 7. Converted CASQ Units

The converter creates fixed 5s, 10s, and 15s units for manifest rows with metadata video IDs. Tail fragments shorter than the configured unit length are dropped to keep unit durations fixed.

| metric | value |
| --- | --- |
| num_units | 550 |
| background_units | 455 |
| event_overlap_units | 95 |
| unit_durations | ['10.0', '15.0', '5.0'] |

## 8. Schema Validation

| check | passed | detail |
| --- | --- | --- |
| event_start_lt_event_end | True |  |
| event_midpoint_inside_interval | True |  |
| event_duration_positive | True |  |
| derived_boundaries_explicitly_marked | True |  |
| no_fabricated_boundaries | True |  |
| all_matched_event_ids_exist | True |  |
| normal_videos_have_no_positive_event | True |  |
| source_paths_exist_if_downloaded | True |  |

Validation checks cover interval order, midpoint inclusion, positive duration, matched event IDs, normal-video event leakage, fabricated-boundary markings, derived-boundary markings, and downloaded source path existence.

## 9. Limitations

- Only metadata CSV files were used; videos were not downloaded.
- No full dataset download was attempted.
- CASQ intervals are derived from `time_of_alert` and `time_of_event`; they are not original human event_start/event_end interval annotations.
- Source video paths are expected paths only until the approved 25 positive / 25 normal videos are downloaded or otherwise placed locally.
- Existing Phase 0 pseudo-events remain debugging-only and were not used as human-truth boundaries.

## 10. Recommendation

Use this metadata-only smoke result to request the bounded video subset next: 25 positive videos and 25 normal videos matching the manifest. For a 200-event expansion, treat Nexar boundaries as derived precursor intervals unless a source with original interval annotations is added.

NEXAR_SMALL_DECISION: BOUNDARIES_ARE_DERIVED_ONLY
