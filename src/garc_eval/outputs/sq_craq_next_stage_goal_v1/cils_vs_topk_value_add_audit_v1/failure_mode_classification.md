# Failure Mode Classification

| failure_mode | applies | evidence |
| --- | --- | --- |
| TOPK_ALREADY_SUFFICIENT | True | best synthetic top-k reaches the same recall-at-precision region as CILS |
| CILS_OVER_CONSERVATIVE | True | CILS has many empty/non-return settings in prior metrics |
| CILS_LOSES_RANKING_INFORMATION | True | calibration/thresholding does not dominate score ranking |
| CALIBRATION_NO_VALUE_ADD | True | no stable calibrated-selector gain over top-k variants |
| ORACLE_BUDGET_NOT_JUSTIFIED | True | top-k variants spend no calibration oracle budget |
| SMALL_REFERENCE_INCONCLUSIVE | True | only six interval_eval events |
