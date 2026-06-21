# Sampling Baseline Input Inventory

- labels_csv: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv`
- proxy_csv: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores_with_learned.csv`
- focused_event_metrics_csv: `/qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/03_event_conversion/event_level_metrics.csv` exists=True
- joined rows: 1000
- oracle positives: 61
- learned RF field used: `score_learned_rf`
- missing RF candidate fields: `['learned_rf_score', 'rf_score', 'score_rf']`

## Label Fields
`['clip_id', 'video_id', 'segment_id', 'start_time', 'end_time', 'clip_path', 'conservative_positive', 'risk_level', 'affected_ego', 'event_type', 'starts_outside_ego_path', 'enters_ego_path', 'requires_ego_attention', 'negative_reason', 'confidence', 'evidence', 'raw_response', 'runtime_sec', 'status', 'error_message']`

## Proxy Fields
`['clip_id', 'video_id', 'segment_id', 'start_time', 'end_time', 'clip_path', 'score_count', 'score_naive', 'score_kinematic', 'mean_vehicle_count', 'max_vehicle_count', 'max_area_growth', 'max_center_motion', 'max_ego_path_overlap', 'max_predicted_entry', 'max_lateral_toward_ego_path', 'max_temporal_persistence', 'track_count', 'stable_track_count', 'vlm_label', 'event_type', 'negative_reason', 'score_count_norm', 'score_naive_norm', 'score_kinematic_norm', 'ensemble_count_naive_score', 'ensemble_all_proxy_score', 'score_learned_logreg', 'score_learned_rf']`

## Joined Fields
`['clip_id', 'video_id', 'segment_id', 'start_time', 'end_time', 'clip_path', 'score_count', 'score_naive', 'score_kinematic', 'score_learned_rf', 'segment_id_label', 'start_time_label', 'end_time_label', 'clip_path_label', 'conservative_positive', 'risk_level', 'event_type', 'negative_reason', 'evidence', 'oracle_positive']`
