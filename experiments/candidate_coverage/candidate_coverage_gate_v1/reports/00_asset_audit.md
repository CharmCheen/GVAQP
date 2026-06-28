# Candidate Coverage Gate V1 Asset Audit

This audit is for a cheap candidate proposal coverage experiment over VLM-defined pseudo-events. It is not a human-ground-truth benchmark.

## Inputs

- main proxy CSV: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores.csv` rows=1000
- conservative labels CSV: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv` rows=1000 positives=61
- learned score CSV: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores_with_learned.csv` reference_only=True
- event files: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/event_budget_gate_v2/tables` gaps=[0.0, 4.0, 8.0]

## Candidate Construction Fields

- `top_count`: `score_count`
- `temporal_nms_count`: `score_count`, `source_video`, `start_time`
- `top_kinematic`: `score_kinematic`
- `top_ego_path`: normalized `max_ego_path_overlap`, `max_predicted_entry`, `max_lateral_toward_ego_path`
- `rule_like_conjunction`: quantiles of `score_kinematic`, `max_predicted_entry`, `max_lateral_toward_ego_path`, `stable_track_count`
- `rank_fusion_proxy`: reciprocal rank fusion over count, kinematic, predicted-entry, lateral, persistence
- `score_union_proxy`: union of count, temporal NMS, kinematic, and ego-path candidate lists

## Data Shape

- clips: 1000
- source videos/groups: 11
- inferred stride seconds: 4
- proxy columns: `['clip_id', 'video_id', 'segment_id', 'start_time', 'end_time', 'clip_path', 'score_count', 'score_naive', 'score_kinematic', 'mean_vehicle_count', 'max_vehicle_count', 'max_area_growth', 'max_center_motion', 'max_ego_path_overlap', 'max_predicted_entry', 'max_lateral_toward_ego_path', 'max_temporal_persistence', 'track_count', 'stable_track_count', 'source_video', 'score_count_norm', 'score_naive_norm', 'score_kinematic_norm', 'mean_vehicle_count_norm', 'max_vehicle_count_norm', 'max_area_growth_norm', 'max_center_motion_norm', 'max_ego_path_overlap_norm', 'max_predicted_entry_norm', 'max_lateral_toward_ego_path_norm', 'max_temporal_persistence_norm', 'track_count_norm', 'stable_track_count_norm', 'ego_path_score', 'rank_fusion_score']`

## Leakage Risk

- Main methods read `proxy_scores.csv`, which does not include conservative labels.
- Conservative labels and pseudo-events are used only for evaluation.
- Learned scores are loaded only as reference methods because they were previously trained from conservative pseudo-labels with GroupKFold.
