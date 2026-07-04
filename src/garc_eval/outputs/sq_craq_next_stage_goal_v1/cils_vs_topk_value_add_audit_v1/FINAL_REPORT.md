# CILS vs Top-K Value-Add Audit V1

## Verdict

`CILS_VALUE_ADD_NEGATIVE + INCONCLUSIVE_DUE_TO_SMALL_REFERENCE`

## Answers

1. Does CILS have value-add? **No stable independent value-add was established.**
2. Should CILS remain the core algorithm? **No.**
3. Should CILS be downgraded to optional selector / ablation? **Yes.**
4. Should default selector move to top-k + NMS + duration cap? **Yes, as the pragmatic default while SQ-CRAQ envelope/audit is developed.**

## Evidence

| score_condition | method | topk_best_recall_p08 | topk_seed_count | topk_mean_count | cils_best_recall_p08 | cils_seed_count | cils_mean_count | recall_gain_cils_minus_baseline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| synthetic_auc_0_95 | topk_nms_duration_penalty | 1 | 19 | 20 | 1 | 5 | 10.4444 | 0 |
| synthetic_auc_0_95 | topk_nms | 1 | 19 | 20 | 1 | 5 | 10.4444 | 0 |
| synthetic_auc_0_95 | raw_topk | 1 | 20 | 75 | 1 | 5 | 10.4444 | 0 |
| synthetic_auc_0_95 | duration_penalized_topk | 1 | 20 | 75 | 1 | 5 | 10.4444 | 0 |
| synthetic_auc_0_90 | topk_nms_duration_penalty | 1 | 8 | 20 | 1 | 2 | 11.8 | 0 |
| synthetic_auc_0_90 | topk_nms | 1 | 7 | 20 | 1 | 2 | 11.8 | 0 |
| synthetic_auc_0_90 | raw_topk | 1 | 20 | 75 | 1 | 2 | 11.8 | 0 |
| synthetic_auc_0_90 | duration_penalized_topk | 1 | 20 | 75 | 1 | 2 | 11.8 | 0 |
| oracle_signal | duration_penalized_topk | 0.833333 | 1 | 75 | nan | nan | nan | -0.833333 |
| synthetic_auc_0_85 | raw_topk | 1 | 20 | 55.3846 | nan | nan | nan | -1 |
| synthetic_auc_0_80 | raw_topk | 1 | 12 | 28.2353 | nan | nan | nan | -1 |
| synthetic_auc_0_85 | duration_penalized_topk | 1 | 20 | 55.3846 | nan | nan | nan | -1 |
| oracle_signal | topk_nms_duration_penalty | 1 | 1 | 20 | nan | nan | nan | -1 |
| oracle_signal | topk_nms | 1 | 1 | 20 | nan | nan | nan | -1 |
| oracle_signal | raw_topk | 1 | 1 | 75 | nan | nan | nan | -1 |
| synthetic_auc_0_80 | duration_penalized_topk | 1 | 11 | 31.7647 | nan | nan | nan | -1 |

## Failure Modes

| failure_mode | applies | evidence |
| --- | --- | --- |
| TOPK_ALREADY_SUFFICIENT | True | best synthetic top-k reaches the same recall-at-precision region as CILS |
| CILS_OVER_CONSERVATIVE | True | CILS has many empty/non-return settings in prior metrics |
| CILS_LOSES_RANKING_INFORMATION | True | calibration/thresholding does not dominate score ranking |
| CALIBRATION_NO_VALUE_ADD | True | no stable calibrated-selector gain over top-k variants |
| ORACLE_BUDGET_NOT_JUSTIFIED | True | top-k variants spend no calibration oracle budget |
| SMALL_REFERENCE_INCONCLUSIVE | True | only six interval_eval events |

All results are `DIAGNOSTIC_ONLY`; the interval reference has only six true interval events and synthetic label-informed signals are not real cheap signals.
