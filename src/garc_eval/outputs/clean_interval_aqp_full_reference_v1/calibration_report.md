# Calibration Report

Oracle replay budgets: [5, 10, 20, 40, 80]

Trials per policy/budget: 100

Calibration implemented: beta-binomial score-duration-disagreement strata. Logistic/isotonic was not
used because several budget/policy combinations have too few positives for stable fitting.

| budget | policy | calibration | brier | auc | sample_positive_rate |
| --- | --- | --- | --- | --- | --- |
| 5 | decision_aware_simple | beta_bin_strata | 0.280278 | 0.5 | 0.6 |
| 5 | stratified_by_score_duration_disagreement | beta_bin_strata | 0.243756 | 0.465842 | 0.054 |
| 5 | top_score | beta_bin_strata | 0.280278 | 0.5 | 0.6 |
| 5 | uniform | beta_bin_strata | 0.244175 | 0.527066 | 0.324 |
| 10 | decision_aware_simple | beta_bin_strata | 0.225133 | 0.512068 | 0.4 |
| 10 | stratified_by_score_duration_disagreement | beta_bin_strata | 0.256129 | 0.439051 | 0.057 |
| 10 | top_score | beta_bin_strata | 0.241221 | 0.588984 | 0.5 |
| 10 | uniform | beta_bin_strata | 0.242268 | 0.559656 | 0.333 |
| 20 | decision_aware_simple | beta_bin_strata | 0.219842 | 0.654008 | 0.25 |
| 20 | stratified_by_score_duration_disagreement | beta_bin_strata | 0.262934 | 0.413953 | 0.0665 |
| 20 | top_score | beta_bin_strata | 0.209159 | 0.605145 | 0.4 |
| 20 | uniform | beta_bin_strata | 0.227627 | 0.607077 | 0.3275 |
| 40 | decision_aware_simple | beta_bin_strata | 0.197694 | 0.6829 | 0.225 |
| 40 | stratified_by_score_duration_disagreement | beta_bin_strata | 0.26926 | 0.405657 | 0.06675 |
| 40 | top_score | beta_bin_strata | 0.217084 | 0.616143 | 0.425 |
| 40 | uniform | beta_bin_strata | 0.213434 | 0.650122 | 0.3305 |
| 80 | decision_aware_simple | beta_bin_strata | 0.234368 | 0.563428 | 0.2125 |
| 80 | stratified_by_score_duration_disagreement | beta_bin_strata | 0.266444 | 0.467112 | 0.093 |
| 80 | top_score | beta_bin_strata | 0.301351 | 0.617303 | 0.6375 |
| 80 | uniform | beta_bin_strata | 0.19846 | 0.700664 | 0.333875 |
