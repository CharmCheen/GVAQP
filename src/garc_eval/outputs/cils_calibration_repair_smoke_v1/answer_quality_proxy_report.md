# Answer Quality Proxy Report

Formula copied from `cils_calibration_repair_replay_v1` without retuning:

`rank(active_score) + rank(score_persistence) + rank(boundary_left_drop + boundary_right_drop) + 0.5 * moderate_duration_flag - rank(signal_disagreement) - overlong_duration_penalty`

Allowed source fields: `['active_score', 'score_persistence', 'boundary_left_drop', 'boundary_right_drop', 'duration', 'signal_disagreement', 'method', 'source_signal']`.

Forbidden fields used: `[]`.

Top-K diagnostic precision, using labels only for post-hoc smoke audit:

| K | answer_positive_rate | answer_positive_count | mean_duration | p95_duration |
| --- | --- | --- | --- | --- |
| 20 | 0.05 | 1 | 13 | 32 |
| 50 | 0.12 | 6 | 16 | 32 |
| 100 | 0.13 | 13 | 15.52 | 32 |
| 200 | 0.11 | 22 | 13.46 | 32 |
| 400 | 0.15 | 60 | 14.82 | 32 |
