# Root Cause Update

Verdict: **PILOT_CALIBRATION_REPAIR_HELPS**.

Best overall diagnostic replay row:

| pilot_policy | calibration_model | budget | tau | mean_returned | return_rate | interval_recall | precision | p95_duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| answer_quality_proxy_top | beta_bin_strata_lower | 20 | 0.5 | 1 | 1 | 0.166667 | 1 | 16 |

Best non-floor repaired row:

| pilot_policy | calibration_model | budget | tau | mean_returned | return_rate | interval_recall | precision | p95_duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| answer_quality_proxy_top | beta_bin_strata_lower | 20 | 0.5 | 1 | 1 | 0.166667 | 1 | 16 |

Interpretation: if only `calibrated_floor_*` rows return, the original root cause remains a calibration floor / probability estimation issue, not a selector implementation bug. If non-floor rows return with interval recall, pilot/calibration repair is promising.
