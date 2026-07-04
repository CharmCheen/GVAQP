# FINAL REPORT: H7 Calibration Prep + Long-Event-Only Replay

## 1. Most Credible Conclusions
- No existing exhaustive human-annotated calibration window was found.
- A new H7 annotation package was generated with three windows: high_prior, low_prior, suspected_leakage.
- Long-event-only replay shows Ours-full improves event-level recall over B7 at most budgets.
- The improvement is strongest for duration>=1s and duration>=2s subsets.
- Budget accounting remains exact; no over-selection by Ours at budget=40.

## 2. H7 Exhaustive Annotation Status
- **Status**: pending human annotation.
- **Template**: `h7_annotation_template.csv`
- **Guide**: `h7_annotation_guide.md`
- **Calibration plan**: `audit_calibration_plan.md`

## 3. Long-Event-Only Replay Results

### Event-level recall (duration>=1s subset)

|   budget |   B6_ExSample |   B7_ExSample_plus_expansion |   Ours_full_LATE_AQP |
|---------:|--------------:|-----------------------------:|---------------------:|
|        5 |         0.106 |                        0.068 |                0.189 |
|       10 |         0.167 |                        0.128 |                0.356 |
|       20 |         0.383 |                        0.303 |                0.394 |
|       40 |         0.583 |                        0.564 |                0.728 |
|       80 |         0.878 |                        0.861 |                1     |
|      120 |         1     |                        1     |                1     |

### Budget curve (duration>=1s)

| method                     |   budget | event_subset   |   num_events |   event_recall_mean |   complete_event_coverage_mean |   boundary_iou_03_mean |   boundary_iou_05_mean |
|:---------------------------|---------:|:---------------|-------------:|--------------------:|-------------------------------:|-----------------------:|-----------------------:|
| B6_ExSample                |        5 | duration_ge_1s |            6 |           0.105556  |                              0 |              0.0388889 |              0.0111111 |
| B6_ExSample                |       10 | duration_ge_1s |            6 |           0.166667  |                              0 |              0.0666667 |              0.0166667 |
| B6_ExSample                |       20 | duration_ge_1s |            6 |           0.383333  |                              0 |              0.183333  |              0.0833333 |
| B6_ExSample                |       40 | duration_ge_1s |            6 |           0.583333  |                              0 |              0.383333  |              0.205556  |
| B6_ExSample                |       80 | duration_ge_1s |            6 |           0.877778  |                              0 |              0.694444  |              0.405556  |
| B6_ExSample                |      120 | duration_ge_1s |            6 |           1         |                              0 |              0.833333  |              0.5       |
| B7_ExSample_plus_expansion |        5 | duration_ge_1s |            6 |           0.0680556 |                              0 |              0.0402778 |              0.0333333 |
| B7_ExSample_plus_expansion |       10 | duration_ge_1s |            6 |           0.127778  |                              0 |              0.0722222 |              0.0472222 |
| B7_ExSample_plus_expansion |       20 | duration_ge_1s |            6 |           0.302778  |                              0 |              0.191667  |              0.119444  |
| B7_ExSample_plus_expansion |       40 | duration_ge_1s |            6 |           0.563889  |                              0 |              0.406944  |              0.254167  |
| B7_ExSample_plus_expansion |       80 | duration_ge_1s |            6 |           0.861111  |                              0 |              0.694444  |              0.418056  |
| B7_ExSample_plus_expansion |      120 | duration_ge_1s |            6 |           1         |                              0 |              0.833333  |              0.5       |
| Ours_full_LATE_AQP         |        5 | duration_ge_1s |            6 |           0.188889  |                              0 |              0.0222222 |              0         |
| Ours_full_LATE_AQP         |       10 | duration_ge_1s |            6 |           0.355556  |                              0 |              0.177778  |              0.166667  |
| Ours_full_LATE_AQP         |       20 | duration_ge_1s |            6 |           0.394444  |                              0 |              0.205556  |              0.166667  |
| Ours_full_LATE_AQP         |       40 | duration_ge_1s |            6 |           0.727778  |                              0 |              0.433333  |              0.388889  |
| Ours_full_LATE_AQP         |       80 | duration_ge_1s |            6 |           1         |                              0 |              0.833333  |              0.5       |
| Ours_full_LATE_AQP         |      120 | duration_ge_1s |            6 |           1         |                              0 |              0.833333  |              0.5       |

- At budget=40 on duration>=1s events:
  - Ours-full recall = 0.728±0.080
  - B7 recall = 0.564±0.174
  - Ours-full precision = 0.410
  - B7 precision = 0.364
  - Ours-full selected duration = 400.0s
  - B7 selected duration = 400.0s

## 4. Does Ours Support Temporal-Structure Repair?
- Event-level recall gains on long-interval events are consistent across budgets 10–80.
- Complete-event coverage and boundary IoU remain weak due to the strict full-containment metric and 10s bin size.
- The evidence supports a **weaker** repair claim: Ours improves discovery of long events, but full interval reconstruction is not yet demonstrated.

## 5. Required Claim Adjustments
- Do not claim H7 calibration is verified.
- Do not claim full interval reconstruction; frame the contribution as 'better discovery of long-interval events under budget constraints'.
- Do not claim comparison to SUPG/ABae until those baselines are run.

## 6. Recommendation

- **Primary recommendation**: A. continue LATE-AQP repair mainline and proceed to H7 annotation
- **Secondary recommendation**: C. pivot to dual-ledger calibration as main contribution if H7 annotation shows good calibration but coverage remains weak

## 7. Next Priority Order
1. Complete H7 exhaustive annotation (window_high_prior + window_low_prior).
2. Run SUPG and ABae baselines per `next_supg_abae_baseline_spec.md`.
3. Re-evaluate kill criteria after H7 and baselines are available.
