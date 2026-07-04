# Counterfactual Diagnostics

All rows are `DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT`.

| variant | budget | tau | mean_returned | return_rate | mean_all_event_recall | mean_interval_event_recall | mean_expected_precision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| clean_calibrated | 40 | 0.6 | 0 | 0 | 0 | 0 | 0 |
| clean_calibrated | 80 | 0.1 | 1 | 1 | 0 | 0 | 0.2 |
| clean_calibrated | 80 | 0.2 | 1 | 1 | 0 | 0 | 0.2 |
| clean_calibrated | 80 | 0.3 | 0 | 0 | 0 | 0 | 0 |
| clean_calibrated | 80 | 0.4 | 0 | 0 | 0 | 0 | 0 |
| clean_calibrated | 80 | 0.5 | 0 | 0 | 0 | 0 | 0 |
| clean_calibrated | 80 | 0.6 | 0 | 0 | 0 | 0 | 0 |
| clean_calibrated | 80 | 0.7 | 0 | 0 | 0 | 0 | 0 |
| clean_calibrated | 80 | 0.8 | 0 | 0 | 0 | 0 | 0 |
| clean_calibrated | 80 | 0.9 | 0 | 0 | 0 | 0 | 0 |
| no_duration_penalty | 40 | 0.6 | 0 | 0 | 0 | 0 | 0 |
| no_duration_penalty | 80 | 0.1 | 1 | 1 | 0 | 0 | 0.2 |
| no_duration_penalty | 80 | 0.2 | 1 | 1 | 0 | 0 | 0.2 |
| no_duration_penalty | 80 | 0.3 | 0 | 0 | 0 | 0 | 0 |
| no_duration_penalty | 80 | 0.4 | 0 | 0 | 0 | 0 | 0 |
| no_duration_penalty | 80 | 0.5 | 0 | 0 | 0 | 0 | 0 |
| no_duration_penalty | 80 | 0.6 | 0 | 0 | 0 | 0 | 0 |
| no_duration_penalty | 80 | 0.7 | 0 | 0 | 0 | 0 | 0 |
| no_duration_penalty | 80 | 0.8 | 0 | 0 | 0 | 0 | 0 |
| no_duration_penalty | 80 | 0.9 | 0 | 0 | 0 | 0 | 0 |
| no_overlap_control | 40 | 0.6 | 0 | 0 | 0 | 0 | 0 |
| no_overlap_control | 80 | 0.1 | 17 | 1 | 0.15 | 0.5 | 0.211603 |
| no_overlap_control | 80 | 0.2 | 17 | 1 | 0.15 | 0.5 | 0.211603 |
| no_overlap_control | 80 | 0.3 | 0 | 0 | 0 | 0 | 0 |
| no_overlap_control | 80 | 0.4 | 0 | 0 | 0 | 0 | 0 |
| no_overlap_control | 80 | 0.5 | 0 | 0 | 0 | 0 | 0 |
| no_overlap_control | 80 | 0.6 | 0 | 0 | 0 | 0 | 0 |
| no_overlap_control | 80 | 0.7 | 0 | 0 | 0 | 0 | 0 |
| no_overlap_control | 80 | 0.8 | 0 | 0 | 0 | 0 | 0 |
| no_overlap_control | 80 | 0.9 | 0 | 0 | 0 | 0 | 0 |
| oracle_p_answer | 40 | 0.6 | 1 | 1 | 0.05 | 0.166667 | 1 |
| oracle_p_answer | 80 | 0.1 | 1 | 1 | 0.05 | 0.166667 | 1 |
| oracle_p_answer | 80 | 0.2 | 1 | 1 | 0.05 | 0.166667 | 1 |
| oracle_p_answer | 80 | 0.3 | 1 | 1 | 0.05 | 0.166667 | 1 |
| oracle_p_answer | 80 | 0.4 | 1 | 1 | 0.05 | 0.166667 | 1 |
| oracle_p_answer | 80 | 0.5 | 1 | 1 | 0.05 | 0.166667 | 1 |
| oracle_p_answer | 80 | 0.6 | 1 | 1 | 0.05 | 0.166667 | 1 |
| oracle_p_answer | 80 | 0.7 | 1 | 1 | 0.05 | 0.166667 | 1 |
| oracle_p_answer | 80 | 0.8 | 1 | 1 | 0.05 | 0.166667 | 1 |
| oracle_p_answer | 80 | 0.9 | 1 | 1 | 0.05 | 0.166667 | 1 |

Interpretation rules: if oracle `p_answer` selects intervals while calibrated `p_answer` does not, selector implementation is usable and the root cause is calibration/pilot probability estimation. If low tau begins returning intervals, the precision constraint is binding under the calibrated posterior.
