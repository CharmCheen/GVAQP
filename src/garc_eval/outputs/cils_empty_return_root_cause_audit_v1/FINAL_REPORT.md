# FINAL REPORT: CILS Empty Return Root Cause Audit V1

## 1. Executive Summary

- CILS empty return is real: **yes**. `selected_intervals_by_trial_v2_clean.csv` is empty and clean main curve `number_returned=0`.
- Selector implementation bug: **not supported**. Oracle `p_answer` counterfactual returns intervals.
- Primary root cause: **calibrated `p_answer` is below the precision threshold, making the expected-precision constraint impossible**.
- Practical cause underneath: **top-score pilot sampling sees too few answer-positive intervals, so beta-bin calibration assigns a low posterior floor/ceiling**.
- Direction: fix pilot/calibration and reference target separation before changing selector mechanics.

## 2. Inputs And Audit Status

- Clean no-leak v2 input: `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak`.
- Code audit status: clean audit WARNING / no BLOCKER.
- Duration-stratified directory exists: `False`. This run used fallback duration strata from `reference_events.csv` when duration artifacts were absent.
- No model inference, no clean v2 modifications, no proposal-family changes.

## 3. Interval Subset And Candidate Availability

Event strata:

| duration_stratum | events | min_duration | median_duration | max_duration |
| --- | --- | --- | --- | --- |
| point_anchor | 14 | 0.2 | 0.7 | 0.7 |
| true_interval | 6 | 10.7 | 15.7 | 50.7 |

Candidate pool:

| total_candidates | answer_iou_0_3_positive_candidates | answer_iou_0_5_positive_candidates | discovery_positive_candidates | point_event_only_positive_candidates | interval_event_positive_candidates | candidates_that_hit_true_interval_events | candidates_that_hit_only_point_anchor_events | max_active_score_positive_rank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11939 | 1192 | 439 | 4445 | 15 | 1177 | 1177 | 15 | 30 |

There are answer-positive intervals in the candidate lattice. The empty return is therefore not caused by an empty feasible candidate universe.

## 4. Pilot Sampling Diagnosis

CILS main uses `top_score` pilot sampling:

| budget | policy | trials | mean_sample_positive_rate | zero_positive_pilot_rate | mean_interval_event_positives | mean_answer_positives |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | top_score | 100 | 0 | 1 | 0 | 0 |
| 10 | top_score | 100 | 0 | 1 | 0 | 0 |
| 20 | top_score | 100 | 0 | 1 | 0 | 0 |
| 40 | top_score | 100 | 0.05 | 0 | 2 | 2 |
| 80 | top_score | 100 | 0.1 | 0 | 8 | 8 |

The high-score pilot has low positive yield. This is the first probability-estimation bottleneck.

## 5. Calibration Probability Diagnosis

Budget-level p_answer distribution:

| budget | mean_max_p | mean_answer_positive_p | mean_interval_answer_positive_p |
| --- | --- | --- | --- |
| 5 | 0.142857 | 0.142857 | 0.142857 |
| 10 | 0.0833333 | 0.0833333 | 0.0833333 |
| 20 | 0.25 | 0.0489246 | 0.048965 |
| 40 | 0.25 | 0.0739862 | 0.074037 |
| 80 | 0.214286 | 0.119321 | 0.119493 |

For all clean main tau values (`0.5` and above), the calibrated `p_answer` maximum remains below tau, including B=80. Since CILS checks expected precision before accepting the first candidate, no interval can enter the set.

## 6. Selector Rejection Diagnosis

Dominant focus-cell rejection reasons:

| budget | tau | rejection_reason | count | total | fraction |
| --- | --- | --- | --- | --- | --- |
| 80 | 0.5 | p_answer_too_low | 240000 | 240000 | 1 |
| 80 | 0.6 | p_answer_too_low | 240000 | 240000 | 1 |
| 80 | 0.7 | p_answer_too_low | 240000 | 240000 | 1 |

Rejections are dominated by `p_answer_too_low` / precision-constraint failure. Duration penalty and overlap control are not primary blockers because no candidate passes the first precision gate.

## 7. Counterfactual Diagnostics

All counterfactual rows are `DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT`.

| variant | budget | tau | mean_returned | return_rate | mean_all_event_recall | mean_interval_event_recall | mean_expected_precision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| clean_calibrated | 80 | 0.1 | 1 | 1 | 0 | 0 | 0.2 |
| clean_calibrated | 80 | 0.5 | 0 | 0 | 0 | 0 | 0 |
| clean_calibrated | 80 | 0.6 | 0 | 0 | 0 | 0 | 0 |
| no_duration_penalty | 80 | 0.1 | 1 | 1 | 0 | 0 | 0.2 |
| no_duration_penalty | 80 | 0.5 | 0 | 0 | 0 | 0 | 0 |
| no_duration_penalty | 80 | 0.6 | 0 | 0 | 0 | 0 | 0 |
| no_overlap_control | 80 | 0.1 | 17 | 1 | 0.15 | 0.5 | 0.211603 |
| no_overlap_control | 80 | 0.5 | 0 | 0 | 0 | 0 | 0 |
| no_overlap_control | 80 | 0.6 | 0 | 0 | 0 | 0 | 0 |
| oracle_p_answer | 80 | 0.1 | 1 | 1 | 0.05 | 0.166667 | 1 |
| oracle_p_answer | 80 | 0.5 | 1 | 1 | 0.05 | 0.166667 | 1 |
| oracle_p_answer | 80 | 0.6 | 1 | 1 | 0.05 | 0.166667 | 1 |

Low-tau diagnostics show whether the calibrated posterior can select when the precision threshold drops. Oracle-`p_answer` diagnostics show the selector can select when probabilities are informative, ruling against a selector implementation bug as the primary cause.

## 8. Root Cause Conclusion

| root_cause | support | evidence |
| --- | --- | --- |
| PILOT_NO_POSITIVES | budget_dependent_not_primary | B=5: zero_rate=1.000, pos_rate=0.000; B=10: zero_rate=1.000, pos_rate=0.000; B=20: zero_rate=1.000, pos_rate=0.000; B=40: zero_rate=0.000, pos_rate=0.050; B=80: zero_rate=0.000, pos_rate=0.100. B=80 has positives, so no-positive pilot alone cannot explain empty return. |
| CALIBRATION_FLOOR_TOO_LOW | strong | B=80 mean max p_answer=0.214, below tau_p grid minimum 0.5 |
| PRECISION_CONSTRAINT_IMPOSSIBLE | strong | first selected candidate must satisfy p_answer >= tau; clean calibrated p_answer max is below tau=0.5 |
| SELECTOR_IMPLEMENTATION_BUG | not_supported | oracle p_answer B=80 tau=0.5 return_rate=1.000 |
| UTILITY_OR_DURATION_PENALTY_SUPPRESSES_SELECTION | not_primary | positive utility exists; rejection happens before utility can matter because expected precision fails |
| OVERLAP_CONTROL_SUPPRESSES_SELECTION | not_primary | no selected spans exist before precision rejection; overlap conflicts are not the first blocker |
| SCORE_RANKING_FAILURE | secondary | top_score pilot positive rates are low despite many answer-positive candidates |
| REFERENCE_MIXTURE_EFFECT | secondary | point/interval mixture affects global target, but interval positives are still assigned low p_answer under top-score pilot |

Primary root cause: **CALIBRATION_FLOOR_TOO_LOW / PRECISION_CONSTRAINT_IMPOSSIBLE**, caused by weak top-score pilot positives and poor score-to-answer alignment.

Secondary causes: **PILOT_SPARSITY**, **SCORE_RANKING_FAILURE**, and **REFERENCE_MIXTURE_EFFECT**.

## 9. Impact On Research Direction

- Clean v2 CILS=0 can be interpreted as the current CILS calibration/pilot design failing on this pseudo-oracle workload.
- It should **not** be interpreted as proof that interval proposal generation is impossible; interval positives exist and oracle probability counterfactual can select them.
- Next work should prioritize **A. fixing pilot/calibration** and **C. separating/rebuilding true interval reference**. Selector implementation repair is not the first target.

## 10. Recommended Next Actions

1. Build a calibration/pilot repair experiment that reserves exploration budget for interval-event-positive strata instead of pure top-score pilots.
2. Re-evaluate CILS on the true-interval subset separately from point-anchor events, keeping the no-leak whitelist protocol.
3. Compare repaired calibration against a simple audited proposal-repair baseline before continuing the current CILS route.
