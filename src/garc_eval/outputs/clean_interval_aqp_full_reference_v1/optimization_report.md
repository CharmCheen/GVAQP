# Optimization Report

Method: CILS, calibrated interval-lattice selection.

Selection input: `interval_lattice_features_only.csv` plus budget-limited oracle replay samples.

Evaluation labels are joined only after each return set is selected.

Pilot policy for CILS: `top_score` budget-limited oracle replay.

Greedy constraints: expected precision >= tau, pairwise interval overlap <= 0.3, max returned intervals <= B.

| method | budget | tau | event_recall_mean | event_recall_std | observed_precision_mean | returned_duration_mean | duplicate_rate_mean | precision_violation_rate | duration_inflation_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CILS_full | 5 | 0.8 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 5 | 0.9 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 10 | 0.8 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 10 | 0.9 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 20 | 0.8 | 0.1 | 0 | 0.181818 | 178 | 0 | 1 | 0 |
| CILS_full | 20 | 0.9 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 40 | 0.8 | 0.15 | 0 | 0.384615 | 230 | 0.153846 | 1 | 0 |
| CILS_full | 40 | 0.9 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| CILS_full | 80 | 0.8 | 0.15 | 0 | 0.227273 | 344 | 0.0909091 | 1 | 0 |
| CILS_full | 80 | 0.9 | 0.15 | 0 | 0.266667 | 336 | 0.0666667 | 1 | 0 |
