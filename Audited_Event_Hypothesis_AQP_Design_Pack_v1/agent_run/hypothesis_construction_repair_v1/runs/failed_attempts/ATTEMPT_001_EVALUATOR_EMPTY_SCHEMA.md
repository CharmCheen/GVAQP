# Failed Attempt 001 — Evaluator Empty Schema

- Variant/budget reached: H1, B=5.
- Planner execution: completed and saved with the frozen H1 config.
- Failure: direct composition of `match_events` and `compute_metrics` did not normalize the no-prediction empty match schema; `compute_metrics` raised `KeyError: matched`.
- Interpretation: evaluator compatibility failure, not a planner result.
- Fix: route evaluation through the frozen `evaluate_events` wrapper, matching H0's audited path.
- Action: restart the complete formal matrix from empty histories.
