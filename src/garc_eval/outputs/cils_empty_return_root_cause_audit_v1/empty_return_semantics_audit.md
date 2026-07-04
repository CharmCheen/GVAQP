# Empty Return Semantics Audit

- `selected_intervals_by_trial_v2_clean.csv` rows: `0`
- Main curve max `number_returned`: `0.0`
- Main curve max CILS recall IoU@0.3: `0.0`
- Empty return rate range: `1.0` to `1.0`
- Observed precision empty handling: `NaN` in clean v2 main rows = `True`

Conclusion: clean v2 CILS recall 0 comes from genuinely no selected intervals, not from selected intervals being filtered out during evaluation.
