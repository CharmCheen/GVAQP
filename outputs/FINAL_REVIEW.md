# SQ-CRAQ v2 Phase A/B FINAL_REVIEW

Review timestamp: 2026-07-02 UTC. This is a read-only review of generated Phase A/B artifacts. No VLM, YOLO, GPU inference, or new algorithm run was performed during this review.

## PASS / WARNING / FAIL

### PASS
- `probe_set_v1` has 25 manifest rows and 25 clips / 25 center frames / 25 contact sheets.
- Probe rows are marked `probe_set_v1`, `do_not_use_for_tuning=True`, and use `independent_equal_interval_time_grid_not_candidate_lattice`.
- Probe media times satisfy `media_t = local_t + 2000.0` for start and end.
- The probe README and reproducibility note explicitly prohibit tuning, threshold selection, selector choice, repair decisions, and candidate generation use.
- `cheap_signal_v2` reuses existing `object_tracks_dataset3_2fps.csv`; no script imports `ultralytics`, `torch`, CUDA, Qwen, or VLM inference code.
- `signal_upgrade_within_bin_metrics.csv` contains metrics only for `dataset_source=6_event_reference`; there are no expanded-reference or probe metrics.
- Grep found no added `r_upper` or `gamma_lower` fields and no code path setting CILS as a default selector.

### WARNING
- `try_or_no/videos/realcartest.mp4` is absent. Probe media uses fallback `data/realcam/long_video_data/long_video_dataset3.mp4`.
- The fallback duration is `3462.930499s`; with `local_to_media_offset_seconds=2000.0`, `probe_set_v1` covers only local `[0.0, 1462.930499]`, not the full historical 66-minute realcartest video.
- Cheap-signal v2 feature tables cover local `[0, 1200]`; `5` probe rows start after local 1200s and cannot be scored by the current feature tables without extending features. They were not evaluated in this run.
- `auc_best_direction` and `precision_at20_best_direction` choose the better of ascending/descending ranking directions. Treat them as diagnostic separation readouts, not as a deployable selector or tuning result.
- `src/garc_eval/experiments/sq_craq_v2_phase_ab/__pycache__/run_phase_ab.cpython-310.pyc` exists as a py_compile byproduct and should be excluded from commits/packages.
- `git status` could not be relied on because the repository triggers Git dubious-ownership protection in this environment; this review inventories the requested paths directly.

### FAIL

- No FAIL finding in the reviewed artifacts. The warnings above limit claim scope.

## File Inventory

Non-media files:
| path | size_bytes | lines |
| --- | --- | --- |
| src/garc_eval/experiments/sq_craq_v2_phase_ab/run_phase_ab.py | 35912 | 863 |
| outputs/probe_set_v1/README.md | 1154 | 25 |
| outputs/probe_set_v1/config/probe_set_v1.yaml | 569 | 11 |
| outputs/probe_set_v1/data_manifest/probe_set_manifest.csv | 18292 | 26 |
| outputs/probe_set_v1/logs/progress.md | 305 | 3 |
| outputs/probe_set_v1/probe_set_manifest.csv | 18292 | 26 |
| outputs/probe_set_v1/probe_set_review_sheet.csv | 13173 | 26 |
| outputs/probe_set_v1/reproducible_commands.md | 671 | 17 |
| outputs/cheap_signal_v2/config/cheap_signal_v2.yaml | 564 | 13 |
| outputs/cheap_signal_v2/data_manifest/input_manifest.csv | 805 | 7 |
| outputs/cheap_signal_v2/inside_outside_contrast_features.csv | 664178 | 601 |
| outputs/cheap_signal_v2/logs/progress.md | 370 | 4 |
| outputs/cheap_signal_v2/reports/signal_upgrade_evaluation_report.md | 7042 | 74 |
| outputs/cheap_signal_v2/reproducible_commands.md | 1021 | 23 |
| outputs/cheap_signal_v2/signal_upgrade_evaluation_report.md | 7042 | 74 |
| outputs/cheap_signal_v2/signal_upgrade_within_bin_metrics.csv | 19450 | 99 |
| outputs/cheap_signal_v2/tables/inside_outside_contrast_features.csv | 664178 | 601 |
| outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv | 21479802 | 11940 |
| outputs/cheap_signal_v2/tables/signal_upgrade_within_bin_metrics.csv | 19450 | 99 |
| outputs/cheap_signal_v2/tables/track_interaction_features.csv | 390713 | 1418 |
| outputs/cheap_signal_v2/track_interaction_features.csv | 390713 | 1418 |

Probe media summary:
| media_subdir | count | min_size_bytes | max_size_bytes | total_size_bytes |
| --- | --- | --- | --- | --- |
| clips | 25 | 2592052 | 5415677 | 102643427 |
| centers | 25 | 219801 | 416963 | 7805880 |
| sheets | 25 | 77727 | 121324 | 2489651 |

Media files are all under `outputs/probe_set_v1/probe_media/{clips,centers,sheets}` with 25 files per subdirectory. The individual file-size inventory was checked from the filesystem; binary media line counts are `n/a`.

## CSV Schemas And Samples

### `outputs/probe_set_v1/data_manifest/probe_set_manifest.csv`
- Rows: `25`
- Columns: `25`
- Schema: `['probe_id', 'review_id', 'candidate_id', 'probe_set', 'video_id', 'sampling_rule', 'video_source_status', 'video_path', 'local_to_media_offset_seconds', 'local_t_start', 'local_t_end', 'media_t_start', 'media_t_end', 'duration', 'context_start', 'context_end', 'source', 'clip_path', 'center_frame_path', 'sheet_path', 'clip_export_status', 'center_export_status', 'sheet_export_status', 'export_notes', 'do_not_use_for_tuning']`
- Sample note: sample shows first 10 + last 4 columns for readability
| probe_id | review_id | candidate_id | probe_set | video_id | sampling_rule | video_source_status | video_path | local_to_media_offset_seconds | local_t_start | center_export_status | sheet_export_status | export_notes | do_not_use_for_tuning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| probe_set_v1_0001 | probe_set_v1_0001 |  | probe_set_v1 | realcartest | independent_equal_interval_time_grid_not_candidate_lattice | fallback_dataset3_with_reference_absolute_offset | /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4 | 2000 | 0 | OK_EXISTING | OK |  | 1 |
| probe_set_v1_0002 | probe_set_v1_0002 |  | probe_set_v1 | realcartest | independent_equal_interval_time_grid_not_candidate_lattice | fallback_dataset3_with_reference_absolute_offset | /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4 | 2000 | 60.5388 | OK_EXISTING | OK |  | 1 |
| probe_set_v1_0003 | probe_set_v1_0003 |  | probe_set_v1 | realcartest | independent_equal_interval_time_grid_not_candidate_lattice | fallback_dataset3_with_reference_absolute_offset | /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4 | 2000 | 121.078 | OK_EXISTING | OK |  | 1 |
| probe_set_v1_0004 | probe_set_v1_0004 |  | probe_set_v1 | realcartest | independent_equal_interval_time_grid_not_candidate_lattice | fallback_dataset3_with_reference_absolute_offset | /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4 | 2000 | 181.616 | OK_EXISTING | OK |  | 1 |
| probe_set_v1_0005 | probe_set_v1_0005 |  | probe_set_v1 | realcartest | independent_equal_interval_time_grid_not_candidate_lattice | fallback_dataset3_with_reference_absolute_offset | /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4 | 2000 | 242.155 | OK_EXISTING | OK |  | 1 |

### `outputs/probe_set_v1/probe_set_manifest.csv`
- Rows: `25`
- Columns: `25`
- Schema: `['probe_id', 'review_id', 'candidate_id', 'probe_set', 'video_id', 'sampling_rule', 'video_source_status', 'video_path', 'local_to_media_offset_seconds', 'local_t_start', 'local_t_end', 'media_t_start', 'media_t_end', 'duration', 'context_start', 'context_end', 'source', 'clip_path', 'center_frame_path', 'sheet_path', 'clip_export_status', 'center_export_status', 'sheet_export_status', 'export_notes', 'do_not_use_for_tuning']`
- Sample note: sample shows first 10 + last 4 columns for readability
| probe_id | review_id | candidate_id | probe_set | video_id | sampling_rule | video_source_status | video_path | local_to_media_offset_seconds | local_t_start | center_export_status | sheet_export_status | export_notes | do_not_use_for_tuning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| probe_set_v1_0001 | probe_set_v1_0001 |  | probe_set_v1 | realcartest | independent_equal_interval_time_grid_not_candidate_lattice | fallback_dataset3_with_reference_absolute_offset | /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4 | 2000 | 0 | OK_EXISTING | OK |  | 1 |
| probe_set_v1_0002 | probe_set_v1_0002 |  | probe_set_v1 | realcartest | independent_equal_interval_time_grid_not_candidate_lattice | fallback_dataset3_with_reference_absolute_offset | /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4 | 2000 | 60.5388 | OK_EXISTING | OK |  | 1 |
| probe_set_v1_0003 | probe_set_v1_0003 |  | probe_set_v1 | realcartest | independent_equal_interval_time_grid_not_candidate_lattice | fallback_dataset3_with_reference_absolute_offset | /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4 | 2000 | 121.078 | OK_EXISTING | OK |  | 1 |
| probe_set_v1_0004 | probe_set_v1_0004 |  | probe_set_v1 | realcartest | independent_equal_interval_time_grid_not_candidate_lattice | fallback_dataset3_with_reference_absolute_offset | /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4 | 2000 | 181.616 | OK_EXISTING | OK |  | 1 |
| probe_set_v1_0005 | probe_set_v1_0005 |  | probe_set_v1 | realcartest | independent_equal_interval_time_grid_not_candidate_lattice | fallback_dataset3_with_reference_absolute_offset | /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4 | 2000 | 242.155 | OK_EXISTING | OK |  | 1 |

### `outputs/probe_set_v1/probe_set_review_sheet.csv`
- Rows: `25`
- Columns: `26`
- Schema: `['review_id', 'probe_id', 'video_id', 'probe_set', 'local_t_start', 'local_t_end', 'duration', 'context_start', 'context_end', 'source', 'clip_path', 'center_frame_path', 'sheet_path', 'do_not_use_for_tuning', 'suggested_event_type', 'human_event_type', 'human_is_true_interval', 'human_is_point_anchor', 'human_is_negative', 'corrected_start', 'corrected_end', 'boundary_confidence', 'keep_for_interval_eval', 'exclusion_reason', 'notes', 'final_reviewed_label']`
- Sample note: sample shows first 10 + last 4 columns for readability
| review_id | probe_id | video_id | probe_set | local_t_start | local_t_end | duration | context_start | context_end | source | keep_for_interval_eval | exclusion_reason | notes | final_reviewed_label |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| probe_set_v1_0001 | probe_set_v1_0001 | realcartest | probe_set_v1 | 0 | 10 | 10 | 0 | 10 | probe_set_v1_independent_temporal_grid |  |  |  |  |
| probe_set_v1_0002 | probe_set_v1_0002 | realcartest | probe_set_v1 | 60.5388 | 70.5388 | 10 | 60.5388 | 70.5388 | probe_set_v1_independent_temporal_grid |  |  |  |  |
| probe_set_v1_0003 | probe_set_v1_0003 | realcartest | probe_set_v1 | 121.078 | 131.078 | 10 | 121.078 | 131.078 | probe_set_v1_independent_temporal_grid |  |  |  |  |
| probe_set_v1_0004 | probe_set_v1_0004 | realcartest | probe_set_v1 | 181.616 | 191.616 | 10 | 181.616 | 191.616 | probe_set_v1_independent_temporal_grid |  |  |  |  |
| probe_set_v1_0005 | probe_set_v1_0005 | realcartest | probe_set_v1 | 242.155 | 252.155 | 10 | 242.155 | 252.155 | probe_set_v1_independent_temporal_grid |  |  |  |  |

### `outputs/cheap_signal_v2/data_manifest/input_manifest.csv`
- Rows: `6`
- Columns: `3`
- Schema: `['path', 'role', 'exists']`
- Sample note: sample shows all columns
| path | role | exists |
| --- | --- | --- |
| src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_lattice_features_only.csv | existing interval lattice features | 1 |
| src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_labels_v2_clean.csv | evaluation labels only | 1 |
| src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/cheap_signals_per_unit.csv | existing cheap signal unit table | 1 |
| src/garc_eval/outputs/track_transition_validation_v1/tables/object_tracks_dataset3_2fps.csv | existing YOLO 2fps track table | 1 |
| src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/reference_events_expanded_v1.csv | expanded reference if human review completed | 1 |

### `outputs/cheap_signal_v2/inside_outside_contrast_features.csv`
- Rows: `600`
- Columns: `64`
- Schema: `['unit_id', 'video_id', 'local_t_start', 'local_t_end', 'absolute_t_start', 'absolute_t_end', 'window_seconds_each_side', 'probe_set_usage', 'yolo_vehicle_count', 'yolo_vehicle_count_neighborhood_mean', 'yolo_vehicle_count_contrast', 'yolo_vehicle_count_z', 'person_count', 'person_count_neighborhood_mean', 'person_count_contrast', 'person_count_z', 'bbox_area_mean', 'bbox_area_mean_neighborhood_mean', 'bbox_area_mean_contrast', 'bbox_area_mean_z', 'bbox_area_max', 'bbox_area_max_neighborhood_mean', 'bbox_area_max_contrast', 'bbox_area_max_z', 'bbox_size_change', 'bbox_size_change_neighborhood_mean', 'bbox_size_change_contrast', 'bbox_size_change_z', 'track_speed', 'track_speed_neighborhood_mean', 'track_speed_contrast', 'track_speed_z', 'track_acceleration', 'track_acceleration_neighborhood_mean', 'track_acceleration_contrast', 'track_acceleration_z', 'relative_motion_score', 'relative_motion_score_neighborhood_mean', 'relative_motion_score_contrast', 'relative_motion_score_z', 'motion_energy', 'motion_energy_neighborhood_mean', 'motion_energy_contrast', 'motion_energy_z', 'optical_flow_burst', 'optical_flow_burst_neighborhood_mean', 'optical_flow_burst_contrast', 'optical_flow_burst_z', 'object_density_change', 'object_density_change_neighborhood_mean', 'object_density_change_contrast', 'object_density_change_z', 'signal_disagreement', 'signal_disagreement_neighborhood_mean', 'signal_disagreement_contrast', 'signal_disagreement_z', 'cheap_fused_score', 'cheap_fused_score_neighborhood_mean', 'cheap_fused_score_contrast', 'cheap_fused_score_z', 'primary_signal_score', 'primary_signal_score_neighborhood_mean', 'primary_signal_score_contrast', 'primary_signal_score_z']`
- Sample note: sample shows first 10 + last 4 columns for readability
| unit_id | video_id | local_t_start | local_t_end | absolute_t_start | absolute_t_end | window_seconds_each_side | probe_set_usage | yolo_vehicle_count | yolo_vehicle_count_neighborhood_mean | primary_signal_score | primary_signal_score_neighborhood_mean | primary_signal_score_contrast | primary_signal_score_z |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u0000 | realcartest | 0 | 2 | 2000 | 2002 | 30 | not_used | 4.5 | 2.93889 | 0.260274 | 0.163775 | 0.0964992 | 1.309 |
| u0001 | realcartest | 2 | 4 | 2002 | 2004 | 30 | not_used | 3 | 3.05208 | 0.164384 | 0.169806 | -0.00542237 | -0.0721985 |
| u0002 | realcartest | 4 | 6 | 2004 | 2006 | 30 | not_used | 2 | 3.13725 | 0.109589 | 0.174322 | -0.0647327 | -0.862333 |
| u0003 | realcartest | 6 | 8 | 2006 | 2008 | 30 | not_used | 0 | 3.31019 | 0 | 0.183663 | -0.183663 | -2.22635 |
| u0004 | realcartest | 8 | 10 | 2008 | 2010 | 30 | not_used | 1.33333 | 3.51754 | 0.0730594 | 0.194905 | -0.121846 | -1.30467 |

### `outputs/cheap_signal_v2/signal_upgrade_within_bin_metrics.csv`
- Rows: `98`
- Columns: `12`
- Schema: `['dataset_source', 'analysis_scope', 'feature_group', 'feature', 'n_rows', 'n_positive', 'n_negative', 'auc_desc', 'auc_best_direction', 'ranking_direction_for_precision_at20', 'precision_at20_best_direction', 'probe_set_v1_usage']`
- Sample note: sample shows all columns
| dataset_source | analysis_scope | feature_group | feature | n_rows | n_positive | n_negative | auc_desc | auc_best_direction | ranking_direction_for_precision_at20 | precision_at20_best_direction | probe_set_v1_usage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_optical_flow_burst_z_max | 87 | 16 | 71 | 0.182218 | 0.817782 | asc | 0.35 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_object_density_change_z_min | 87 | 16 | 71 | 0.802817 | 0.802817 | desc | 0.5 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_optical_flow_burst_z_mean | 87 | 16 | 71 | 0.203345 | 0.796655 | asc | 0.55 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_motion_energy_z_max | 87 | 16 | 71 | 0.226232 | 0.773768 | asc | 0.4 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_yolo_vehicle_count_z_mean | 87 | 16 | 71 | 0.759683 | 0.759683 | desc | 0.4 | not_used_for_tuning_or_threshold_selection |

### `outputs/cheap_signal_v2/tables/inside_outside_contrast_features.csv`
- Rows: `600`
- Columns: `64`
- Schema: `['unit_id', 'video_id', 'local_t_start', 'local_t_end', 'absolute_t_start', 'absolute_t_end', 'window_seconds_each_side', 'probe_set_usage', 'yolo_vehicle_count', 'yolo_vehicle_count_neighborhood_mean', 'yolo_vehicle_count_contrast', 'yolo_vehicle_count_z', 'person_count', 'person_count_neighborhood_mean', 'person_count_contrast', 'person_count_z', 'bbox_area_mean', 'bbox_area_mean_neighborhood_mean', 'bbox_area_mean_contrast', 'bbox_area_mean_z', 'bbox_area_max', 'bbox_area_max_neighborhood_mean', 'bbox_area_max_contrast', 'bbox_area_max_z', 'bbox_size_change', 'bbox_size_change_neighborhood_mean', 'bbox_size_change_contrast', 'bbox_size_change_z', 'track_speed', 'track_speed_neighborhood_mean', 'track_speed_contrast', 'track_speed_z', 'track_acceleration', 'track_acceleration_neighborhood_mean', 'track_acceleration_contrast', 'track_acceleration_z', 'relative_motion_score', 'relative_motion_score_neighborhood_mean', 'relative_motion_score_contrast', 'relative_motion_score_z', 'motion_energy', 'motion_energy_neighborhood_mean', 'motion_energy_contrast', 'motion_energy_z', 'optical_flow_burst', 'optical_flow_burst_neighborhood_mean', 'optical_flow_burst_contrast', 'optical_flow_burst_z', 'object_density_change', 'object_density_change_neighborhood_mean', 'object_density_change_contrast', 'object_density_change_z', 'signal_disagreement', 'signal_disagreement_neighborhood_mean', 'signal_disagreement_contrast', 'signal_disagreement_z', 'cheap_fused_score', 'cheap_fused_score_neighborhood_mean', 'cheap_fused_score_contrast', 'cheap_fused_score_z', 'primary_signal_score', 'primary_signal_score_neighborhood_mean', 'primary_signal_score_contrast', 'primary_signal_score_z']`
- Sample note: sample shows first 10 + last 4 columns for readability
| unit_id | video_id | local_t_start | local_t_end | absolute_t_start | absolute_t_end | window_seconds_each_side | probe_set_usage | yolo_vehicle_count | yolo_vehicle_count_neighborhood_mean | primary_signal_score | primary_signal_score_neighborhood_mean | primary_signal_score_contrast | primary_signal_score_z |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u0000 | realcartest | 0 | 2 | 2000 | 2002 | 30 | not_used | 4.5 | 2.93889 | 0.260274 | 0.163775 | 0.0964992 | 1.309 |
| u0001 | realcartest | 2 | 4 | 2002 | 2004 | 30 | not_used | 3 | 3.05208 | 0.164384 | 0.169806 | -0.00542237 | -0.0721985 |
| u0002 | realcartest | 4 | 6 | 2004 | 2006 | 30 | not_used | 2 | 3.13725 | 0.109589 | 0.174322 | -0.0647327 | -0.862333 |
| u0003 | realcartest | 6 | 8 | 2006 | 2008 | 30 | not_used | 0 | 3.31019 | 0 | 0.183663 | -0.183663 | -2.22635 |
| u0004 | realcartest | 8 | 10 | 2008 | 2010 | 30 | not_used | 1.33333 | 3.51754 | 0.0730594 | 0.194905 | -0.121846 | -1.30467 |

### `outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv`
- Rows: `11939`
- Columns: `130`
- Schema: `['interval_id', 'method', 'source_signal', 'unit_start_idx', 'unit_end_idx_exclusive', 't_start', 't_end', 'duration', 'num_units', 'mean_score', 'max_score', 'sum_score', 'active_score', 'fused_score', 'cheap_fused_score', 'primary_score', 'score_persistence', 'score_std', 'boundary_left_drop', 'boundary_right_drop', 'signal_disagreement', 'vehicle_count', 'vehicle_count_mean', 'person_count', 'person_count_mean', 'motion_energy', 'motion_energy_mean', 'overlap_group_id', 'discovery_positive', 'positive_unit_fraction', 'matched_event_id', 'best_iou', 'any_overlap', 'center_hit', 'event_hit_iou_0_3', 'event_hit_iou_0_5', 'event_overlap_ratio', 'interval_purity', 'duration_inflation', 'answer_iou_0_3', 'answer_iou_0_5', 'answer_overlap_purity', 'track_num_detections_mean', 'track_num_detections_max', 'track_num_detections_min', 'track_num_tracks_mean', 'track_num_tracks_max', 'track_num_tracks_min', 'track_tracks_in_ego_center_mean_mean', 'track_tracks_in_ego_center_mean_max', 'track_tracks_in_ego_center_mean_min', 'track_ego_enter_count_mean', 'track_ego_enter_count_max', 'track_ego_enter_count_min', 'track_ego_enter_count_sum', 'track_approach_ego_count_mean', 'track_approach_ego_count_max', 'track_approach_ego_count_min', 'track_approach_ego_count_sum', 'track_max_ego_approach_rate_mean', 'track_max_ego_approach_rate_max', 'track_max_ego_approach_rate_min', 'track_mean_track_speed_mean', 'track_mean_track_speed_max', 'track_mean_track_speed_min', 'track_max_track_speed_mean', 'track_max_track_speed_max', 'track_max_track_speed_min', 'track_close_pair_count_sum_mean', 'track_close_pair_count_sum_max', 'track_close_pair_count_sum_min', 'track_close_pair_count_sum_sum', 'track_approaching_pair_count_sum_mean', 'track_approaching_pair_count_sum_max', 'track_approaching_pair_count_sum_min', 'track_approaching_pair_count_sum_sum', 'track_min_pair_distance_mean', 'track_min_pair_distance_max', 'track_min_pair_distance_min', 'track_min_ttc_mean', 'track_min_ttc_max', 'track_min_ttc_min', 'track_max_closing_rate_mean', 'track_max_closing_rate_max', 'track_max_closing_rate_min', 'track_mean_relative_speed_mean', 'track_mean_relative_speed_max', 'track_mean_relative_speed_min', 'contrast_yolo_vehicle_count_z_mean', 'contrast_yolo_vehicle_count_z_max', 'contrast_yolo_vehicle_count_z_min', 'contrast_person_count_z_mean', 'contrast_person_count_z_max', 'contrast_person_count_z_min', 'contrast_bbox_area_mean_z_mean', 'contrast_bbox_area_mean_z_max', 'contrast_bbox_area_mean_z_min', 'contrast_bbox_area_max_z_mean', 'contrast_bbox_area_max_z_max', 'contrast_bbox_area_max_z_min', 'contrast_bbox_size_change_z_mean', 'contrast_bbox_size_change_z_max', 'contrast_bbox_size_change_z_min', 'contrast_track_speed_z_mean', 'contrast_track_speed_z_max', 'contrast_track_speed_z_min', 'contrast_track_acceleration_z_mean', 'contrast_track_acceleration_z_max', 'contrast_track_acceleration_z_min', 'contrast_relative_motion_score_z_mean', 'contrast_relative_motion_score_z_max', 'contrast_relative_motion_score_z_min', 'contrast_motion_energy_z_mean', 'contrast_motion_energy_z_max', 'contrast_motion_energy_z_min', 'contrast_optical_flow_burst_z_mean', 'contrast_optical_flow_burst_z_max', 'contrast_optical_flow_burst_z_min', 'contrast_object_density_change_z_mean', 'contrast_object_density_change_z_max', 'contrast_object_density_change_z_min', 'contrast_signal_disagreement_z_mean', 'contrast_signal_disagreement_z_max', 'contrast_signal_disagreement_z_min', 'contrast_cheap_fused_score_z_mean', 'contrast_cheap_fused_score_z_max', 'contrast_cheap_fused_score_z_min', 'contrast_primary_signal_score_z_mean', 'contrast_primary_signal_score_z_max', 'contrast_primary_signal_score_z_min']`
- Sample note: sample shows first 10 + last 4 columns for readability
| interval_id | method | source_signal | unit_start_idx | unit_end_idx_exclusive | t_start | t_end | duration | num_units | mean_score | contrast_cheap_fused_score_z_min | contrast_primary_signal_score_z_mean | contrast_primary_signal_score_z_max | contrast_primary_signal_score_z_min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| iv2_0000000 | fixed_window | active_score | 0 | 5 | 0 | 10 | 10 | 5 | 0.468875 | -0.618283 | -0.63131 | 1.309 | -2.22635 |
| iv2_0000001 | fixed_window | active_score | 2 | 7 | 4 | 14 | 10 | 5 | 0.478851 | -0.538599 | -0.845739 | 0.410671 | -2.22635 |
| iv2_0000002 | fixed_window | active_score | 4 | 9 | 8 | 18 | 10 | 5 | 0.37939 | -0.862223 | -0.379049 | 0.410671 | -1.30467 |
| iv2_0000003 | fixed_window | active_score | 6 | 11 | 12 | 22 | 10 | 5 | 0.29731 | -1.0078 | -0.228988 | 0.43602 | -1.23639 |
| iv2_0000004 | fixed_window | active_score | 8 | 13 | 16 | 26 | 10 | 5 | 0.246411 | -1.53291 | -0.350725 | 0.52999 | -1.23639 |

### `outputs/cheap_signal_v2/tables/signal_upgrade_within_bin_metrics.csv`
- Rows: `98`
- Columns: `12`
- Schema: `['dataset_source', 'analysis_scope', 'feature_group', 'feature', 'n_rows', 'n_positive', 'n_negative', 'auc_desc', 'auc_best_direction', 'ranking_direction_for_precision_at20', 'precision_at20_best_direction', 'probe_set_v1_usage']`
- Sample note: sample shows all columns
| dataset_source | analysis_scope | feature_group | feature | n_rows | n_positive | n_negative | auc_desc | auc_best_direction | ranking_direction_for_precision_at20 | precision_at20_best_direction | probe_set_v1_usage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_optical_flow_burst_z_max | 87 | 16 | 71 | 0.182218 | 0.817782 | asc | 0.35 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_object_density_change_z_min | 87 | 16 | 71 | 0.802817 | 0.802817 | desc | 0.5 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_optical_flow_burst_z_mean | 87 | 16 | 71 | 0.203345 | 0.796655 | asc | 0.55 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_motion_energy_z_max | 87 | 16 | 71 | 0.226232 | 0.773768 | asc | 0.4 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_yolo_vehicle_count_z_mean | 87 | 16 | 71 | 0.759683 | 0.759683 | desc | 0.4 | not_used_for_tuning_or_threshold_selection |

### `outputs/cheap_signal_v2/tables/track_interaction_features.csv`
- Rows: `1417`
- Columns: `23`
- Schema: `['probe_set_usage', 'feature_source', 'bin_seconds', 'local_t_start', 'local_t_end', 'media_t_start', 'media_t_end', 'num_detections', 'num_tracks', 'tracks_in_ego_center_mean', 'ego_enter_count', 'approach_ego_count', 'max_ego_approach_rate', 'mean_track_speed', 'max_track_speed', 'mean_area_change_per_s', 'pair_count_mean', 'close_pair_count_sum', 'approaching_pair_count_sum', 'min_pair_distance', 'min_ttc', 'max_closing_rate', 'mean_relative_speed']`
- Sample note: sample shows first 10 + last 4 columns for readability
| probe_set_usage | feature_source | bin_seconds | local_t_start | local_t_end | media_t_start | media_t_end | num_detections | num_tracks | tracks_in_ego_center_mean | min_pair_distance | min_ttc | max_closing_rate | mean_relative_speed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| not_used | track_transition_validation_v1/object_tracks_dataset3_2fps.csv | 1 | 0 | 1 | 2000 | 2001 | 9 | 6 | 3.5 | 0.0106197 | 2.63203 | 0.04157 | 0.0255555 |
| not_used | track_transition_validation_v1/object_tracks_dataset3_2fps.csv | 1 | 1 | 2 | 2001 | 2002 | 8 | 4 | 3 | 0.0339379 |  | 0.0155347 | 0.0264511 |
| not_used | track_transition_validation_v1/object_tracks_dataset3_2fps.csv | 1 | 2 | 3 | 2002 | 2003 | 8 | 4 | 3 | 0.067131 |  | 0.0108813 | 0.0373716 |
| not_used | track_transition_validation_v1/object_tracks_dataset3_2fps.csv | 1 | 3 | 4 | 2003 | 2004 | 9 | 5 | 2 | 0.0760488 | 3.21575 | 0.0452162 | 0.0553126 |
| not_used | track_transition_validation_v1/object_tracks_dataset3_2fps.csv | 1 | 4 | 5 | 2004 | 2005 | 7 | 4 | 2.5 | 0.0757733 |  | 0.00675987 | 0.040465 |

### `outputs/cheap_signal_v2/track_interaction_features.csv`
- Rows: `1417`
- Columns: `23`
- Schema: `['probe_set_usage', 'feature_source', 'bin_seconds', 'local_t_start', 'local_t_end', 'media_t_start', 'media_t_end', 'num_detections', 'num_tracks', 'tracks_in_ego_center_mean', 'ego_enter_count', 'approach_ego_count', 'max_ego_approach_rate', 'mean_track_speed', 'max_track_speed', 'mean_area_change_per_s', 'pair_count_mean', 'close_pair_count_sum', 'approaching_pair_count_sum', 'min_pair_distance', 'min_ttc', 'max_closing_rate', 'mean_relative_speed']`
- Sample note: sample shows first 10 + last 4 columns for readability
| probe_set_usage | feature_source | bin_seconds | local_t_start | local_t_end | media_t_start | media_t_end | num_detections | num_tracks | tracks_in_ego_center_mean | min_pair_distance | min_ttc | max_closing_rate | mean_relative_speed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| not_used | track_transition_validation_v1/object_tracks_dataset3_2fps.csv | 1 | 0 | 1 | 2000 | 2001 | 9 | 6 | 3.5 | 0.0106197 | 2.63203 | 0.04157 | 0.0255555 |
| not_used | track_transition_validation_v1/object_tracks_dataset3_2fps.csv | 1 | 1 | 2 | 2001 | 2002 | 8 | 4 | 3 | 0.0339379 |  | 0.0155347 | 0.0264511 |
| not_used | track_transition_validation_v1/object_tracks_dataset3_2fps.csv | 1 | 2 | 3 | 2002 | 2003 | 8 | 4 | 3 | 0.067131 |  | 0.0108813 | 0.0373716 |
| not_used | track_transition_validation_v1/object_tracks_dataset3_2fps.csv | 1 | 3 | 4 | 2003 | 2004 | 9 | 5 | 2 | 0.0760488 | 3.21575 | 0.0452162 | 0.0553126 |
| not_used | track_transition_validation_v1/object_tracks_dataset3_2fps.csv | 1 | 4 | 5 | 2004 | 2005 | 7 | 4 | 2.5 | 0.0757733 |  | 0.00675987 | 0.040465 |

## Probe Set Audit
| check | result |
| --- | --- |
| probe rows | 25 |
| clip files | 25 |
| center frames | 25 |
| contact sheets | 25 |
| all probe_set == probe_set_v1 | True |
| all do_not_use_for_tuning == True | True |
| media start = local start + offset | True |
| media end = local end + offset | True |
| all clip durations 10s | True |
| sampling rule independent time grid | True |

Selected probe time rows:
| probe_id | local_t_start | local_t_end | media_t_start | media_t_end |
| --- | --- | --- | --- | --- |
| probe_set_v1_0001 | 0 | 10 | 2000 | 2010 |
| probe_set_v1_0002 | 60.5388 | 70.5388 | 2060.54 | 2070.54 |
| probe_set_v1_0003 | 121.078 | 131.078 | 2121.08 | 2131.08 |
| probe_set_v1_0013 | 726.465 | 736.465 | 2726.47 | 2736.47 |
| probe_set_v1_0025 | 1452.93 | 1462.93 | 3452.93 | 3462.93 |

The generation code uses an equal-interval `np.linspace` time grid and writes empty `candidate_id`; it does not draw probe times from candidate lattice, review queue, or envelope outputs. It does read the existing reference event table only to recover the historical local/media offset, not to choose probe centers.

## Video Source And Time Axis
- `try_or_no/videos/realcartest.mp4` exists: `False`.
- Fallback path: `data/realcam/long_video_data/long_video_dataset3.mp4`.
- Fallback duration: `3462.930499s`.
- `local_to_media_offset_seconds`: `2000.0`.
- Current probe logical window: `[0.0, 1462.930499]` local seconds.
- Current probe set must not be described as covering the full 66-minute realcartest video.

Five reference-event offset checks:
| event_id | t_start | t_end | absolute_t_start | absolute_t_end | offset_check_start | offset_check_end | start_in_track_range | end_in_track_range |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| realcartest_event_0022 | 30 | 50.7 | 2030 | 2050.7 | 2030 | 2050.7 | 1 | 1 |
| realcartest_event_0023 | 70 | 70.7 | 2070 | 2070.7 | 2070 | 2070.7 | 1 | 1 |
| realcartest_event_0024 | 90 | 90.7 | 2090 | 2090.7 | 2090 | 2090.7 | 1 | 1 |
| realcartest_event_0025 | 120.5 | 120.7 | 2120.5 | 2120.7 | 2120.5 | 2120.7 | 1 | 1 |
| realcartest_event_0026 | 250 | 250.7 | 2250 | 2250.7 | 2250 | 2250.7 | 1 | 1 |

Object-track media timestamp range: `[2.500000, 3462.499333]`; all reference event absolute starts/ends fall within this range.

## Cheap Signal V2 Audit
- `track_interaction_features.csv`: 1417 rows, 23 columns; bin counts `{1: 1177, 5: 240}`; local time range `[0, 1200]`, media range `[2000, 3200]`.
- `inside_outside_contrast_features.csv`: 600 rows, 64 columns; local time range `[0, 1200]`, absolute/media range `[2000, 3200]`.
- `feature_source` is `track_transition_validation_v1/object_tracks_dataset3_2fps.csv` for track features.
- `object_tracks_dataset3_2fps.csv`: 34814 rows; timestamp range `[2.5, 3462.499333]`.

Track feature missingness top columns:
| column | missing_ratio |
| --- | --- |
| min_ttc | 0.279464 |
| min_pair_distance | 0.0444601 |
| probe_set_usage | 0 |
| local_t_start | 0 |
| local_t_end | 0 |
| feature_source | 0 |
| bin_seconds | 0 |
| media_t_end | 0 |

Contrast feature missingness top columns:
| column | missing_ratio |
| --- | --- |
| unit_id | 0 |
| video_id | 0 |
| local_t_start | 0 |
| local_t_end | 0 |
| absolute_t_start | 0 |
| absolute_t_end | 0 |
| window_seconds_each_side | 0 |
| probe_set_usage | 0 |

## Evaluation Audit

Metric source availability:
| dataset_source | status | metric_rows |
| --- | --- | --- |
| 6_event_reference | available; metrics present | 98 |
| expanded_reference | empty reference file (0 rows); no metrics emitted | 0 |
| probe_set_v1 | unannotated review sheet; no metrics emitted | 0 |

Signal-family summary, all tagged `dataset_source=6_event_reference`:
| dataset_source | feature_group | best_auc | best_precision_at20 | feature_count | n_rows | n_positive |
| --- | --- | --- | --- | --- | --- | --- |
| 6_event_reference | existing_signal | 0.695423 | 0.45 | 10 | 87 | 16 |
| 6_event_reference | inside_outside_contrast_signal | 0.817782 | 0.55 | 42 | 87 | 16 |
| 6_event_reference | track_interaction_signal | 0.743838 | 0.4 | 46 | 87 | 16 |

Top diagnostic rows:
| dataset_source | feature_group | feature | auc_best_direction | ranking_direction_for_precision_at20 | precision_at20_best_direction |
| --- | --- | --- | --- | --- | --- |
| 6_event_reference | inside_outside_contrast_signal | contrast_optical_flow_burst_z_max | 0.817782 | asc | 0.35 |
| 6_event_reference | inside_outside_contrast_signal | contrast_object_density_change_z_min | 0.802817 | desc | 0.5 |
| 6_event_reference | inside_outside_contrast_signal | contrast_optical_flow_burst_z_mean | 0.796655 | asc | 0.55 |
| 6_event_reference | inside_outside_contrast_signal | contrast_motion_energy_z_max | 0.773768 | asc | 0.4 |
| 6_event_reference | inside_outside_contrast_signal | contrast_yolo_vehicle_count_z_mean | 0.759683 | desc | 0.4 |
| 6_event_reference | inside_outside_contrast_signal | contrast_relative_motion_score_z_max | 0.757923 | desc | 0.35 |
| 6_event_reference | track_interaction_signal | track_mean_track_speed_mean | 0.743838 | asc | 0.35 |
| 6_event_reference | inside_outside_contrast_signal | contrast_primary_signal_score_z_min | 0.742958 | desc | 0.35 |

These numbers support only a diagnostic within-bin separation comparison on the small six-event reference. They do not support generalization, selector replacement, recall/precision claims on expanded reference, or any probe-set conclusion.

## Leakage And Boundary Checks
- Probe data read in `run_phase_ab.py` is limited to status reporting in `write_feature_reports`; it is not used to compute features, thresholds, rankings, or selected candidates.
- The only label join for evaluation is `interval_labels_v2_clean.csv` / `reference_events.csv`, used after feature construction for `6_event_reference` metrics.
- Grep for `r_upper`, `gamma_lower`, confidence interval, and sample splitting found only negative prose statements; no new certificate fields are computed.
- Grep for `CILS`/`cils` found no default-selector code path; config says `default_selector_changed: false`.
- Grep for model/GPU inference found only prose statements saying no VLM/new YOLO inference was run; no inference imports or calls are present.

## Strongest Supported Conclusion

On the available `6_event_reference` within the existing top `p_answer` bin, the newly materialized diagnostic feature families show stronger TP/FP separation than the reviewed existing-signal baseline: best existing AUC `0.695`, best track-interaction AUC `0.744`, and best inside/outside contrast AUC `0.818`. This is a small-reference, diagnostic-only signal-quality result.

## Unsupported Conclusions
- Do not claim improved recall or precision on the full realcartest video.
- Do not claim results on `expanded_reference`; it is empty.
- Do not claim results on `probe_set_v1`; it is unannotated.
- Do not claim the probe set covers the full 66-minute realcartest video.
- Do not claim a formal guarantee, certificate, confidence interval, or valid statistical bound.
- Do not promote any new signal to the default selector based on this review.

## Next-Step Recommendations From Existing Outputs Only
- Treat `probe_set_v1` as frozen read-only material and annotate it before any probe metrics are computed.
- If future probe evaluation is desired, first document that current cheap-signal features stop at local 1200s and either restrict evaluation to covered probe rows or extend features in a separately authorized run.
- Package/commit only source, CSV reports, Markdown reports, and intended media; exclude `__pycache__`.
- Keep `6_event_reference` metrics explicitly labeled diagnostic and small-reference-only in any handoff.
