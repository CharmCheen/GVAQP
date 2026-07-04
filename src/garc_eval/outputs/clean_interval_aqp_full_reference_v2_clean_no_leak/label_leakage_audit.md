# Label Leakage Audit

Feature-only lattice: `interval_lattice_features_only.csv`

Forbidden label-like columns found in feature-only table: []

Feature whitelist columns emitted: ['interval_id', 'method', 'source_signal', 'unit_start_idx', 'unit_end_idx_exclusive', 't_start', 't_end', 'duration', 'num_units', 'mean_score', 'max_score', 'sum_score', 'active_score', 'fused_score', 'cheap_fused_score', 'primary_score', 'score_persistence', 'score_std', 'boundary_left_drop', 'boundary_right_drop', 'signal_disagreement', 'vehicle_count', 'vehicle_count_mean', 'person_count', 'person_count_mean', 'motion_energy', 'motion_energy_mean', 'overlap_group_id']

Allowed columns missing from this lattice and skipped: []

Optimization input policy: CILS reads feature-only intervals and budget-limited oracle replay labels only.
Full interval labels are read only by oracle replay lookup, diagnostics, and final evaluation.

Status: PASS
