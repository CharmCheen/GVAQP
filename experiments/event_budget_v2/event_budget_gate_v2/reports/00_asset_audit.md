# Asset Audit

This is an engineering asset audit for a VLM-defined pseudo-event scheduling experiment. It is not a human-ground-truth benchmark audit.

## Inputs

- clips_csv: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/clips.csv` exists=True
- proxy_csv: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores_with_learned.csv` rows=1000
- labels_csv: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv` rows=1000
- tracks_csv: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/tracks.csv` exists=True rows=655261

## Joined Table

- joined clips: 1000
- source videos/groups: 11
- conservative VLM positives: 61
- positive rate: 0.0610
- inferred clip stride seconds: 4
- event gaps tested seconds: 0, 4, 8

## Schema

- label columns: `['clip_id', 'video_id', 'segment_id', 'start_time', 'end_time', 'clip_path', 'conservative_positive', 'risk_level', 'affected_ego', 'event_type', 'starts_outside_ego_path', 'enters_ego_path', 'requires_ego_attention', 'negative_reason', 'confidence', 'evidence', 'raw_response', 'runtime_sec', 'status', 'error_message']`
- proxy columns: `['clip_id', 'video_id', 'segment_id', 'start_time', 'end_time', 'clip_path', 'score_count', 'score_naive', 'score_kinematic', 'mean_vehicle_count', 'max_vehicle_count', 'max_area_growth', 'max_center_motion', 'max_ego_path_overlap', 'max_predicted_entry', 'max_lateral_toward_ego_path', 'max_temporal_persistence', 'track_count', 'stable_track_count', 'vlm_label', 'event_type', 'negative_reason', 'score_count_norm', 'score_naive_norm', 'score_kinematic_norm', 'ensemble_count_naive_score', 'ensemble_all_proxy_score', 'score_learned_logreg', 'score_learned_rf']`
- joined columns: `['clip_id', 'video_id', 'segment_id', 'start_time', 'end_time', 'clip_path', 'score_count', 'score_naive', 'score_kinematic', 'mean_vehicle_count', 'max_vehicle_count', 'max_area_growth', 'max_center_motion', 'max_ego_path_overlap', 'max_predicted_entry', 'max_lateral_toward_ego_path', 'max_temporal_persistence', 'track_count', 'stable_track_count', 'vlm_label', 'event_type', 'negative_reason', 'score_count_norm', 'score_naive_norm', 'score_kinematic_norm', 'ensemble_count_naive_score', 'ensemble_all_proxy_score', 'score_learned_logreg', 'score_learned_rf', 'video_id_label', 'segment_id_label', 'start_time_label', 'end_time_label', 'clip_path_label', 'conservative_positive', 'risk_level', 'affected_ego', 'event_type_label', 'starts_outside_ego_path', 'enters_ego_path', 'requires_ego_attention', 'negative_reason_label', 'confidence', 'evidence', 'raw_response', 'status', 'error_message', 'source_video', 'oracle_positive', 'score_learned_rf_norm', 'score_learned_logreg_norm', 'score_disagreement', 'row_index']`
- proxy score fields: `['score_count', 'score_naive', 'score_kinematic', 'track_count', 'stable_track_count', 'score_count_norm', 'score_naive_norm', 'score_kinematic_norm', 'score_learned_logreg', 'score_learned_rf']`
- learned score fields: `['score_learned_logreg', 'score_learned_rf']`
- track/kinematic fields: `['clip_id', 'frame_idx', 'time_sec', 'track_id', 'class_name', 'conf', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'w', 'h', 'area', 'frame_w', 'frame_h']`

## Source Video Concentration

count     11.000000
mean      90.909091
std      136.515534
min        1.000000
25%        5.500000
50%       12.000000
75%      113.500000
max      399.000000

## Existing Logic Reused

- Input schema follows `test_vlm/experiments/roadclip_budget_v2/09_vlm_oracle_acceleration_benchmark.py`.
- Temporal NMS ordering mirrors the existing score-sort plus same-source time suppression pattern.
- Pseudo-event merging follows existing positive clip merge-by-source and start-time gap logic.

## Leakage Risk

- `score_learned_logreg` and `score_learned_rf` were materialized in the prior pipeline using conservative VLM labels with segment-level GroupKFold.
- This avoids same-segment train/test leakage but still uses the evaluation pseudo-oracle to create learned scores, so learned methods are development references only and not main conclusions.
- Conservative VLM labels are used here only after method orders are computed.
