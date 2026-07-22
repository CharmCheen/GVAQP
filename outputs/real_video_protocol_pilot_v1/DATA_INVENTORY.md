# Data Inventory

Scope: existing local files only. No data was downloaded and no model was run.

## Videos Found

| path                                                 | exists   | role                                                                    | duration_seconds   |
|:-----------------------------------------------------|:---------|:------------------------------------------------------------------------|:-------------------|
| data/realcam/long_video_data/long_video_dataset3.mp4 | True     | available real video                                                    | 3462.930499        |
| try_or_no/videos/realcartest.mp4                     | False    | manifest source for selected realcartest universe                       | <NA>               |
| try_or_no/videos/realcartest_5k.mp4                  | True     | small realcartest_5k video with labels but no matched proxy table found | <NA>               |

Notes:

- `long_video_dataset3.mp4` is present and readable from prior metadata, but no reliable stitched reference segment file was found for adapter evaluation.
- `try_or_no/videos/realcartest.mp4` is referenced by existing realcartest CSV manifests but is missing on this server.
- `realcartest_5k.mp4` exists and has VLM-defined labels/events, but no matching cheap proxy score table was found in the scanned outputs.

## Relevant CSV Files

| path                                                                                                                  | exists   |   rows | columns                                                                                                                                                                                                                                                                                                          |
|:----------------------------------------------------------------------------------------------------------------------|:---------|-------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| outputs/late_aqp_frozen_cross_segment_v1/grid_realcartest_2000_3200.csv                                               | True     |    120 | bin_id, video_id, t_start, t_end, absolute_t_start, absolute_t_end, label, event_id, boundary_start, boundary_end, prior_score_max, prior_score_mean, num_sub_units, original_granularity, granularity_source_tag, is_positive, bin_idx, local_t_start ...                                                       |
| outputs/late_aqp_frozen_cross_segment_v1/ref_events_realcartest_2000_3200.csv                                         | True     |     20 | event_id, video_id, t_start, t_end, absolute_t_start, absolute_t_end, duration, event_type, involved_object, num_supporting_anchors, supporting_anchor_ids, label_source, oracle_version                                                                                                                         |
| src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/base_units.csv                               | True     |    600 | unit_id, video_id, t_start, t_end, absolute_t_start, absolute_t_end, duration                                                                                                                                                                                                                                    |
| src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/cheap_signals_per_unit.csv                   | True     |    600 | unit_id, t_start, t_end, absolute_t_start, absolute_t_end, num_sampled_frames, yolo_vehicle_count, person_count, bbox_area_mean, bbox_area_max, bbox_center_x, bbox_center_y, bbox_size_change, track_speed, track_acceleration, relative_motion_score, motion_energy, optical_flow_burst ...                    |
| src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/full_reference_units.csv                     | True     |    600 | unit_id, t_start, t_end, label_event, event_type, event_id, boundary_start, boundary_end, label_source, confidence, notes                                                                                                                                                                                        |
| src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/reference_events.csv                         | True     |     20 | event_id, video_id, t_start, t_end, absolute_t_start, absolute_t_end, duration, event_type, involved_object, num_supporting_anchors, supporting_anchor_ids, label_source, oracle_version                                                                                                                         |
| src/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/metadata/center10_proxy_features.csv             | True     |    347 | anchor_id, video_id, anchor_time, start_time, end_time, duration, source_video_path, construction_policy, num_overlapping_5s_clips, yolo_vehicle_mean, yolo_vehicle_max, yolo_vehicle_sum, object_count_mean, object_count_max, bbox_area_sum_mean, bbox_area_sum_max, max_bbox_area_mean, max_bbox_area_max ... |
| src/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1/oracle_outputs/dataset3_full_center10_parsed.csv | True     |    347 | anchor_id, video_id, anchor_time, start_time, end_time, duration, label, event_start, event_end, event_start_absolute, event_end_absolute, event_type, involved_object, ego_relevant, boundary_status, complete_event_visible, confidence, evidence ...                                                          |
| outputs/late_aqp_low_budget_fix_v1/new_labels/center10_full_oracle_labels_realcartest_5k.csv                          | True     |     21 | anchor_id, video_id, anchor_time, start_time, end_time, duration, label, event_start, event_end, event_start_absolute, event_end_absolute, event_type, involved_object, ego_relevant, boundary_status, complete_event_visible, confidence, evidence ...                                                          |
| outputs/late_aqp_low_budget_fix_v1/new_labels/center10_vlm_oracle_events_realcartest_5k.csv                           | True     |      3 | event_id, video_id, event_start, event_end, event_duration, event_type_majority, involved_object_majority, num_supporting_anchors, supporting_anchor_ids, mean_confidence_proxy, all_boundary_statuses, complete_event_visible_all, evidence_summary, label_source, oracle_version                               |

## Direct Adapter Usability

- `outputs/late_aqp_frozen_cross_segment_v1/grid_realcartest_2000_3200.csv`: usable after field mapping; has unit/window rows, `prior_score_max`, and `is_positive` pseudo-oracle labels.
- `outputs/late_aqp_frozen_cross_segment_v1/ref_events_realcartest_2000_3200.csv`: usable after field mapping; has reference event boundaries and event type.
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/*`: also usable, but was already exercised by the previous adapter dry-run at 2s granularity.
- `dataset3` files: video/proxy/full anchor labels exist, but reliable reference boundaries are missing or documented as degenerate, so they are not selected for this baseline pilot.

## Missing Fields / Risks

- Selected realcartest universe has complete CSV protocol fields after mapping, but the original raw `realcartest.mp4` is not present on this server.
- Selected reference events are VLM-defined pseudo-reference events, not human ground truth.
- Many realcartest reference events are point-anchor or sub-2s events evaluated against 10s bins; IoU=0.5 is expected to be harsh.

## Recommended Pilot Universe

Use `realcartest_2000_3200` from `outputs/late_aqp_frozen_cross_segment_v1`: 20 minutes, 120 ten-second units, 32 pseudo-positive units, and 20 VLM-defined reference events. This is the smallest complete CSV replay universe found for ARC/SUPG/ABae adapter validation.
