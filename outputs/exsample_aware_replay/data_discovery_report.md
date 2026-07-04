# ExSample-aware Replay — Data Discovery Report

**BASE_SEARCH_ROOT**: `/qiuyeqing/llama_prl/G-ARC`
**QUERY_PREDICATE**: `Visible Ego-Path Conflict (VEPC)`
**ATOMIC_BIN_SIZE**: 10s (locked)

## 1. Candidate Reference / Label Files

### `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v1/reference_events.csv`
- type: reference_events
- rows: 20
- columns: ['event_id', 'video_id', 't_start', 't_end', 'absolute_t_start', 'absolute_t_end', 'duration', 'event_type', 'involved_object', 'num_supporting_anchors', 'supporting_anchor_ids', 'label_source', 'oracle_version']
- time_range: (30.0, 1110.7)
- bin_durations: {0.7: 13, 10.7: 3, 20.7: 2, 0.2: 1, 50.7: 1}
- selected: False
- rationale: Alternate or older reference; not used as primary.

### `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v1/full_reference_units.csv`
- type: reference_labels
- rows: 600
- columns: ['unit_id', 't_start', 't_end', 'label_event', 'event_type', 'event_id', 'boundary_start', 'boundary_end', 'label_source', 'confidence', 'notes']
- time_range: (0.0, 1200.0)
- bin_durations: {2.0: 600}
- selected: False
- rationale: Alternate or older reference; not used as primary.

### `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv`
- type: reference_events
- rows: 20
- columns: ['event_id', 'video_id', 't_start', 't_end', 'absolute_t_start', 'absolute_t_end', 'duration', 'event_type', 'involved_object', 'num_supporting_anchors', 'supporting_anchor_ids', 'label_source', 'oracle_version']
- time_range: (30.0, 1110.7)
- bin_durations: {0.7: 13, 10.7: 3, 20.7: 2, 0.2: 1, 50.7: 1}
- selected: True
- rationale: Primary reference for replay.

### `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/full_reference_units.csv`
- type: reference_labels
- rows: 600
- columns: ['unit_id', 't_start', 't_end', 'label_event', 'event_type', 'event_id', 'boundary_start', 'boundary_end', 'label_source', 'confidence', 'notes']
- time_range: (0.0, 1200.0)
- bin_durations: {2.0: 600}
- selected: True
- rationale: Primary reference for replay.

### `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/reference_events.csv`
- type: reference_events
- rows: 20
- columns: ['event_id', 'video_id', 't_start', 't_end', 'absolute_t_start', 'absolute_t_end', 'duration', 'event_type', 'involved_object', 'num_supporting_anchors', 'supporting_anchor_ids', 'label_source', 'oracle_version']
- time_range: (30.0, 1110.7)
- bin_durations: {0.7: 13, 10.7: 3, 20.7: 2, 0.2: 1, 50.7: 1}
- selected: False
- rationale: Alternate or older reference; not used as primary.

### `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/full_reference_units.csv`
- type: reference_labels
- rows: 600
- columns: ['unit_id', 't_start', 't_end', 'label_event', 'event_type', 'event_id', 'boundary_start', 'boundary_end', 'label_source', 'confidence', 'notes']
- time_range: (0.0, 1200.0)
- bin_durations: {2.0: 600}
- selected: False
- rationale: Alternate or older reference; not used as primary.

### `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/reference_events_expanded_v1.csv`
- type: reference_events
- rows: 0
- columns: ['event_id', 'video_id', 'event_type', 't_start', 't_end', 'duration', 'source_review_id', 'boundary_confidence', 'keep_for_interval_eval', 'annotation_version', 'notes']
- time_range: (nan, nan)
- bin_durations: {}
- selected: False
- rationale: Empty file (header only); not usable.

## 2. Candidate Prior-Score Files

### `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/cheap_signals_per_unit.csv`
- type: prior_scores
- rows: 600
- columns (first 15): ['unit_id', 't_start', 't_end', 'absolute_t_start', 'absolute_t_end', 'num_sampled_frames', 'yolo_vehicle_count', 'person_count', 'bbox_area_mean', 'bbox_area_max', 'bbox_center_x', 'bbox_center_y', 'bbox_size_change', 'track_speed', 'track_acceleration']
- time_range: (0.0, 1200.0)
- bin_durations (top 10): {2.0: 600}
- selected: True
- rationale: Primary per-unit prior score source (cheap_fused_score).

### `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/cheap_signals_per_unit.csv`
- type: prior_scores
- rows: 600
- columns (first 15): ['unit_id', 't_start', 't_end', 'absolute_t_start', 'absolute_t_end', 'num_sampled_frames', 'yolo_vehicle_count', 'person_count', 'bbox_area_mean', 'bbox_area_max', 'bbox_center_x', 'bbox_center_y', 'bbox_size_change', 'track_speed', 'track_acceleration']
- time_range: (0.0, 1200.0)
- bin_durations (top 10): {2.0: 600}
- selected: False
- rationale: Interval-level aggregation; not atomic-unit prior.

### `/qiuyeqing/llama_prl/G-ARC/outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv`
- type: prior_scores
- rows: 11939
- columns (first 15): ['interval_id', 'method', 'source_signal', 'unit_start_idx', 'unit_end_idx_exclusive', 't_start', 't_end', 'duration', 'num_units', 'mean_score', 'max_score', 'sum_score', 'active_score', 'fused_score', 'cheap_fused_score']
- time_range: (0.0, 1200.0)
- bin_durations (top 10): {4.0: 1809, 8.0: 1686, 16.0: 1569, 12.0: 1404, 24.0: 1266, 32.0: 1186, 6.0: 794, 2.0: 573, 10.0: 432, 20.0: 212}
- selected: False
- rationale: Interval-level aggregation; not atomic-unit prior.

### `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_lattice_v2_clean.csv`
- type: prior_scores
- rows: 11939
- columns (first 15): ['interval_id', 'method', 'source_signal', 'unit_start_idx', 'unit_end_idx_exclusive', 't_start', 't_end', 'duration', 'num_units', 'mean_score', 'max_score', 'sum_score', 'active_score', 'fused_score', 'cheap_fused_score']
- time_range: (0.0, 1200.0)
- bin_durations (top 10): {4.0: 1809, 8.0: 1686, 16.0: 1569, 12.0: 1404, 24.0: 1266, 32.0: 1186, 6.0: 794, 2.0: 573, 10.0: 432, 20.0: 212}
- selected: False
- rationale: Interval-level aggregation; not atomic-unit prior.

## 3. Granularity Distribution and Switch-Point Analysis

- Unique bin durations in primary units: [2.0]
- Bin duration counts: {2.0: 600}
- Granularity switch detected: **no**. The entire analysed segment uses a single 2s granularity.
- `granularity_source_tag` for all merged 10s bins is set to `uniform_2s_no_switch_found`.
- Layered reporting by `granularity_source_tag` will therefore have only one stratum for this dataset.

## 4. Primary Data Selection Summary

- Reference units: `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/full_reference_units.csv`
- Prior scores: `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/cheap_signals_per_unit.csv`
- Reference events: `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv`
- Reason for choosing `clean_no_leak` over `label_aligned`: the no-leak version passed the feature-only label-leakage audit and uses a whitelist of features, making it the fairest basis for replay.

## 5. Coverage and Bias Quantification

- Total 10s bins: 120
- Labeled bins: 120 (100.0% of analysed segment)
- Positive bins: 32 (26.7%)
- Negative bins: 88 (73.3%)
- Analysed segment duration: 1200.0s
- Positive temporal mass (from reference events): 133.5s (11.12% of segment)
- Mean prior (all bins): 0.3091
- Mean prior (positive bins): 0.3602
- Mean prior (negative bins): 0.2906
- Median prior (all bins): 0.3152
- Median prior (positive bins): 0.3565
- Median prior (negative bins): 0.2894
- Bias note: Labeled bins are heavily biased toward high-prior regions if positive-bin priors are markedly higher than negative-bin priors.

## 6. Important Data Caveats

- Reference labels are VLM-oracle outputs (`qwen3_vl_32b_v13_6_prompt`), not human labels. Metrics reported against these labels should be interpreted as VLM-defined-positive recovery, not human-ground-truth recall.
- No existing exhaustive human-annotated continuous window was found. The exhaustive annotation package has been generated as a template but is **pending human annotation**. Calibration metrics dependent on it will be marked **未验证 / pending human annotation**.
- The data has no granularity switch within the analysed 1200s segment, so Layer-A reporting by `granularity_source_tag` collapses to a single stratum.
- All labels are binary (positive/negative) in the primary units; no uncertain labels are present, so the uncertain-merge rule produces zero uncertain 10s bins.

## 7. Ambiguities Requiring Human Confirmation

1. **Prior-score aggregation for 10s bins**: the task specifies 10s atomic bins but the raw prior scores exist at 2s. We pre-register `max` aggregation for the primary 10s prior. If a different aggregation (e.g. mean) is preferred, it must be decided before running baselines.
2. **Granularity switch**: no switch was found in the primary 1200s segment. If the user expects a switch at a specific timestamp (e.g. tied to a larger video), that timestamp was not recoverable from the available files.

## 8. Generated Artifacts

- `/qiuyeqing/llama_prl/G-ARC/outputs/exsample_aware_replay/atomic_grid_10s.csv`: 10s atomic bin grid with labels and prior scores.
- `/qiuyeqing/llama_prl/G-ARC/outputs/exsample_aware_replay/exhaustive_subset_annotation_package/exhaustive_bins_template.csv`: template for exhaustive human annotation (pending).
- `/qiuyeqing/llama_prl/G-ARC/outputs/exsample_aware_replay/preregistered_config.json`: pre-registered hyperparameters.
