# Stage 1A Diagnostic: Native ARC vs MAP-BBEM Output Quality Audit

## Scope

This diagnostic only reads Stage 1A aggregated metrics. It does not change oracle allocation, selected units, baseline outputs, or materialization.

## Main Metrics

| budget | method | F1 | precision | recall | avg_dur | max_dur | overcoverage | overmerge | refs/pred | count_err | mean_iou | IoU@0.3 | IoU@0.5 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | ARC-refinement@th0.3 native | 0.524158 | 0.509524 | 0.540000 | 29.173593 | 150.000000 | 4.629213 | 0.698442 | 0.698442 | 1.200000 | 0.180667 | 0.194239 | 0.000000 |
| 5 | ARC-refinement@th0.4 native | 0.368182 | 0.476923 | 0.300000 | 18.743590 | 50.000000 | 1.767790 | 0.476923 | 0.476923 | 7.400000 | 0.207500 | 0.122727 | 0.061364 |
| 5 | MAP-anchor-only + K3 | 0.181818 | 1.000000 | 0.100000 | 10.000000 | 10.000000 | 0.149813 | 1.000000 | 1.000000 | 18.000000 | 0.473123 | 0.090909 | 0.090909 |
| 5 | ABae-stratified-confirmed + K3 | 0.162996 | 1.000000 | 0.090000 | 10.000000 | 10.000000 | 0.134831 | 1.000000 | 1.000000 | 18.200000 | 0.185488 | 0.035573 | 0.017391 |
| 10 | ARC-refinement@th0.3 native | 0.524158 | 0.509524 | 0.540000 | 28.341558 | 150.000000 | 4.494382 | 0.698442 | 0.698442 | 1.200000 | 0.182521 | 0.194239 | 0.000000 |
| 10 | ARC-refinement@th0.4 native | 0.402050 | 0.515385 | 0.330000 | 17.366300 | 50.000000 | 1.662921 | 0.515385 | 0.515385 | 7.200000 | 0.219320 | 0.145900 | 0.061007 |
| 10 | MAP-anchor-only + K3 | 0.400000 | 1.000000 | 0.250000 | 10.000000 | 10.000000 | 0.374532 | 1.000000 | 1.000000 | 15.000000 | 0.224249 | 0.080000 | 0.080000 |
| 10 | ABae-stratified-confirmed + K3 | 0.271568 | 1.000000 | 0.160000 | 13.000000 | 16.000000 | 0.284644 | 1.100000 | 1.100000 | 16.800000 | 0.164691 | 0.033391 | 0.016000 |
| 20 | MAP-anchor-only + K3 | 0.571429 | 1.000000 | 0.400000 | 11.250000 | 20.000000 | 0.674157 | 1.000000 | 1.000000 | 12.000000 | 0.283228 | 0.142857 | 0.142857 |
| 20 | ARC-refinement@th0.4 native | 0.532452 | 0.654652 | 0.450000 | 15.510256 | 50.000000 | 1.602996 | 0.654652 | 0.654652 | 6.200000 | 0.215853 | 0.177014 | 0.070672 |
| 20 | ARC-refinement@th0.3 native | 0.531127 | 0.513853 | 0.550000 | 26.659740 | 150.000000 | 4.269663 | 0.701039 | 0.701039 | 1.400000 | 0.184363 | 0.193310 | 0.000000 |
| 20 | SUPG-RT-all-selected + K3 | 0.389624 | 1.000000 | 0.250000 | 12.750000 | 18.000000 | 0.434457 | 1.000000 | 1.000000 | 15.000000 | 0.258878 | 0.141757 | 0.048468 |

## Pairwise Deltas vs MAP-anchor-only + K3

| budget | comparison | delta_F1 | max_dur_ratio | overcoverage_multiple | delta_mean_iou | delta_IoU@0.3 | delta_IoU@0.5 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 5 | ARC-refinement@th0.3 native minus MAP-anchor-only + K3 | 0.342340 | 15.000000 | 30.900000 | -0.292456 | 0.103330 | -0.090909 |
| 5 | ARC-refinement@th0.4 native minus MAP-anchor-only + K3 | 0.186364 | 5.000000 | 11.800000 | -0.265623 | 0.031818 | -0.029545 |
| 5 | ABae-stratified-confirmed + K3 minus MAP-anchor-only + K3 | -0.018822 | 1.000000 | 0.900000 | -0.287635 | -0.055336 | -0.073518 |
| 10 | ARC-refinement@th0.3 native minus MAP-anchor-only + K3 | 0.124158 | 15.000000 | 12.000000 | -0.041728 | 0.114239 | -0.080000 |
| 10 | ARC-refinement@th0.4 native minus MAP-anchor-only + K3 | 0.002050 | 5.000000 | 4.440000 | -0.004930 | 0.065900 | -0.018993 |
| 10 | ABae-stratified-confirmed + K3 minus MAP-anchor-only + K3 | -0.128432 | 1.600000 | 0.760000 | -0.059558 | -0.046609 | -0.064000 |
| 20 | ARC-refinement@th0.4 native minus MAP-anchor-only + K3 | -0.038976 | 2.500000 | 2.377778 | -0.067375 | 0.034157 | -0.072186 |
| 20 | ARC-refinement@th0.3 native minus MAP-anchor-only + K3 | -0.040302 | 7.500000 | 6.333333 | -0.098866 | 0.050453 | -0.142857 |
| 20 | SUPG-RT-all-selected + K3 minus MAP-anchor-only + K3 | -0.181805 | 0.900000 | 0.644444 | -0.024350 | -0.001100 | -0.094390 |

## Interpretation

ARC-refinement@th0.3 native has the strongest B=5/10 overlap_any F1, but it uses much longer and broader predictions: max duration is 150s and overcoverage is about 4.5x reference duration. Its IoU@0.5 is 0 at B=5/10.
ARC-refinement@th0.4 native is less extreme, but at B=5/10 it still has 50s max duration and materially higher overcoverage than MAP+K3. At B=10 its F1 is effectively tied with MAP+K3, while MAP+K3 has precision 1.0, 10s max duration, lower overcoverage, and slightly higher IoU@0.5.
At B=20, MAP+K3 has the best F1 among the audited rows and keeps bounded durations, lower overcoverage, and better IoU@0.5 than ARC native.

## Decision

MAP_BBEM_DEFENSIBLE_AS_BOUNDED_EVENT_SET_MATERIALIZATION

Conclusion: native ARC's B=5/10 overlap_any advantage is not clean evidence of better event localization. It is strongly coupled to aggressive output duration/overcoverage, especially ARC@th0.3. MAP-BBEM should be defended as bounded event-set materialization; low-budget claims should still state that native ARC can win overlap_any at B=5/10 under permissive overlap_any scoring.
