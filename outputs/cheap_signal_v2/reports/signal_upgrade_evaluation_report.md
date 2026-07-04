# Cheap Signal V2 Evaluation Report

## Scope

This run implements SQ-CRAQ v2 Phase B only. It does not compute formal guarantee,
confidence interval, gamma lower bound, sample splitting, or certificate statistics.
The default selector was not changed.

## Inputs

| path | role | exists |
| --- | --- | --- |
| src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_lattice_features_only.csv | existing interval lattice features | True |
| src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_labels_v2_clean.csv | evaluation labels only | True |
| src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/cheap_signals_per_unit.csv | existing cheap signal unit table | True |
| src/garc_eval/outputs/track_transition_validation_v1/tables/object_tracks_dataset3_2fps.csv | existing YOLO 2fps track table | True |
| src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/reference_events_expanded_v1.csv | expanded reference if human review completed | True |
| outputs/probe_set_v1/probe_set_review_sheet.csv | independent probe set annotation sheet | True |

## New Feature Tables

| output | rows | notes |
| --- | ---: | --- |
| `track_interaction_features.csv` | 1417 | 1s and 5s bins from existing YOLO 2fps tracks |
| `inside_outside_contrast_features.csv` | 600 | per-2s unit z/contrast features against +/-30s temporal neighborhood |

## Evaluation Availability

| dataset_source | status | action |
| --- | --- | --- |
| `6_event_reference` | available | within-bin AUC/precision@20 reported below |
| `expanded_reference` | available_empty (0 rows) | not used unless non-empty human-reviewed file exists |
| `probe_set_v1` | pending_annotation | read-only evaluation only after annotation; not used for tuning |

## Within-Bin Results

Metrics below are on `dataset_source=6_event_reference`, `analysis_scope=within_top_p_answer_bin`.
`auc_best_direction` reports the better of ascending/descending ranking direction as a diagnostic
separation readout; it is not a selector change.

| dataset_source | analysis_scope | feature_group | feature | n_rows | n_positive | n_negative | auc_desc | auc_best_direction | ranking_direction_for_precision_at20 | precision_at20_best_direction | probe_set_v1_usage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_optical_flow_burst_z_max | 87 | 16 | 71 | 0.182218 | 0.817782 | asc | 0.35 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_object_density_change_z_min | 87 | 16 | 71 | 0.802817 | 0.802817 | desc | 0.5 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_optical_flow_burst_z_mean | 87 | 16 | 71 | 0.203345 | 0.796655 | asc | 0.55 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_motion_energy_z_max | 87 | 16 | 71 | 0.226232 | 0.773768 | asc | 0.4 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_yolo_vehicle_count_z_mean | 87 | 16 | 71 | 0.759683 | 0.759683 | desc | 0.4 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_relative_motion_score_z_max | 87 | 16 | 71 | 0.757923 | 0.757923 | desc | 0.35 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | track_interaction_signal | track_mean_track_speed_mean | 87 | 16 | 71 | 0.256162 | 0.743838 | asc | 0.35 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_primary_signal_score_z_min | 87 | 16 | 71 | 0.742958 | 0.742958 | desc | 0.35 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | track_interaction_signal | track_mean_relative_speed_mean | 87 | 16 | 71 | 0.257923 | 0.742077 | asc | 0.4 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_person_count_z_max | 87 | 16 | 71 | 0.264525 | 0.735475 | asc | 0.3 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_primary_signal_score_z_mean | 87 | 16 | 71 | 0.735035 | 0.735035 | desc | 0.3 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_object_density_change_z_max | 87 | 16 | 71 | 0.28037 | 0.71963 | asc | 0.4 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_yolo_vehicle_count_z_min | 87 | 16 | 71 | 0.716549 | 0.716549 | desc | 0.3 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_person_count_z_mean | 87 | 16 | 71 | 0.302817 | 0.697183 | asc | 0.3 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | existing_signal | motion_energy_mean | 87 | 16 | 71 | 0.304577 | 0.695423 | asc | 0.45 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_track_acceleration_z_max | 87 | 16 | 71 | 0.689261 | 0.689261 | desc | 0.1 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | track_interaction_signal | track_max_ego_approach_rate_min | 87 | 16 | 71 | 0.682218 | 0.682218 | desc | 0.35 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | track_interaction_signal | track_min_ttc_mean | 87 | 16 | 71 | 0.681338 | 0.681338 | desc | 0.35 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_signal_disagreement_z_max | 87 | 16 | 71 | 0.319982 | 0.680018 | asc | 0.35 | not_used_for_tuning_or_threshold_selection |
| 6_event_reference | within_top_p_answer_bin | inside_outside_contrast_signal | contrast_bbox_area_max_z_mean | 87 | 16 | 71 | 0.678697 | 0.678697 | desc | 0.25 | not_used_for_tuning_or_threshold_selection |

## Limitations

- Existing expanded reference is empty, so no `expanded_reference` metrics are available.
- `probe_set_v1` has no completed labels in this run, so no probe metrics are available.
- Track features reuse existing 2fps YOLO/linkage outputs; no new detector or VLM inference was run.
- Track timestamps are aligned to local reference time with the historical +2000s offset.
- Results are diagnostic empirical recall/precision signal checks, not formal guarantees.

## Decision

`WEAK_GO_DIAGNOSTIC`
