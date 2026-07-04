# Audit Calibration Plan

This plan documents how to compute H7 calibration metrics once the exhaustive
annotation package (`h7_annotation_template.csv`) is completed by human reviewers.

## 1. Input

- `outputs/late_aqp_h7_long_event_v1/h7_annotation_template.csv`
- Must contain filled `label` for every bin in `window_high_prior` and `window_low_prior`.

## 2. Metrics to compute

### 2.1 True positive-bin mass

```
TP_mass_true = sum over annotated bins of (bin_duration * I[label == positive])
```

For bins with `event_fraction_in_bin` filled, use
`bin_duration * event_fraction_in_bin` instead of full bin duration.

### 2.2 True event-duration mass

```
Event_mass_true = sum over annotated positive bins of
                  (event_t_end_local - event_t_start_local)
                  (deduplicated by event_id)
```

If event boundaries are not fully annotated, approximate using
`event_fraction_in_bin * bin_duration`.

### 2.3 Inside-E0 leakage calibration

For each E0 threshold (top10/top20/top30):

- p_in_true = (# positive bins inside E0) / (# bins inside E0)
- p_in_hat = audit-ledger estimate of p_in (from previous replay outputs)
- calibration_error_in = |p_in_true - p_in_hat|

### 2.4 Outside-E0 leakage calibration

For each E0 threshold:

- p_out_true = (# positive bins outside E0) / (# bins outside E0)
- L_out_true = p_out_true * (total video duration outside E0)
- L_out_hat = audit-ledger estimate from previous replay
- calibration_error_out = |L_out_true - L_out_hat|

### 2.5 Missing-mass estimation error

```
M_hat = estimated missing positive mass from audit ledger
M_true = TP_mass_true - discovered_positive_mass
missing_mass_error = |M_hat - M_true|
```

## 3. Windows used for H7

- `window_high_prior`: primary
- `window_low_prior`: primary

## 4. Windows NOT used for H7

- `window_suspected_leakage`: only for H1/H2 qualitative evidence.

## 5. Anti-contamination rules

- The annotation package must not be used to select E0 thresholds, repair rules,
  or selector parameters.
- Calibration error must be computed on a single pass; do not iterate thresholds
  after seeing the error.
- Report calibration error separately for `window_high_prior` and `window_low_prior`;
  do not merge them.

## 6. Minimum sample size

- At least 30 bins per window (3 minutes at 1s granularity, 1.5 minutes at 2s).
- At least 5 positive bins outside E0 to estimate p_out reliably.

## 7. If calibration fails

- If audit ledger systematically overestimates p_in: pivot to estimator redesign.
- If outside leakage is negligible: weaken repair claim to event-seed discovery.
- If calibration is good but coverage is weak: keep dual-ledger framework and
  focus on improving boundary expansion.
