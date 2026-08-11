# V1/V2 M5 evidence recovery: recomputation report

## Result

`V2_ONLINE_M5_EVIDENCE_STATUS = LOCALLY_RECOMPUTED` for the recovered V2
trace/summary pair. Recalculation of trapezoidal exposure AUC from the immutable
action trace agrees with the stored summary for every checked reported value
within `1e-9`; reconciliation rows are in `metric_reconciliation.csv`.

The recovered V2 numbers include: short-video combined/shuffled AUC 244.8547,
short-video time-index AUC 363.1214, long-video combined AUC 701.8247,
leave-best-region-out AUC 366.4854, and no-shrinkage AUC 681.2203.

## Interpretation boundary

This recovery verifies that the reported V2 metrics reproduce from the recovered
trace. It does not alter the preregistered negative interpretation. The
cross-video shuffled gate fails, time-index is stronger on the short video, and
the long-video gain collapses after best-region removal.

The V1 M5 action trace and AUC table were recovered and hashed, but V1 remains
`OFFLINE_FULL_INFORMATION_DIAGNOSTIC_ONLY`: the erratum establishes future
observation lookahead. It cannot become online evidence through recovery.

## Method

For each `video_id, method`, rows were ordered by `action_index` and AUC was
recomputed as `trapezoid(exposure, time)`. No policy code was executed, no
input was changed, and no reference or new-video result was accessed.
