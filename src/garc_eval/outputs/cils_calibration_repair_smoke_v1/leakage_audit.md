# Leakage Audit

- Proxy source fields: `['active_score', 'score_persistence', 'boundary_left_drop', 'boundary_right_drop', 'duration', 'signal_disagreement', 'method', 'source_signal']`
- Forbidden proxy fields intersect source fields: `[]`
- Candidate p-answer label columns present: `[]`
- Calibration uses only `smoke_pilot_samples.csv` oracle replay labels.
- Selector input is p_answer plus clean v2 feature columns; held-out labels are joined only for smoke evaluation/output reporting.
- Policy search: `no`; fixed `answer_quality_proxy_top + beta_bin_strata_lower` only.
- BLOCKER: `no`
