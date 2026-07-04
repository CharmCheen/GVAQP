# Post-Replay Diagnostic Report

## 1. H1 Positive Mass Accounting Recheck

The previous report contained two numbers that looked contradictory:
- `true_event_duration_mass` = 133.5s (sum of reference event durations).
- `outside_E0_positive_10s_bin_mass` up to 260.0s (full 10s bins outside E0).

These are different metrics. The table below reconciles them:

| E0_threshold   |   total_true_event_duration_mass |   total_positive_10s_bin_mass |   inside_true_event_duration_mass |   outside_true_event_duration_mass |   inside_positive_10s_bin_mass |   outside_positive_10s_bin_mass |   inside_event_count |   outside_event_count |   outside_event_fraction | notes                                                                                            |
|:---------------|---------------------------------:|------------------------------:|----------------------------------:|-----------------------------------:|-------------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|:-------------------------------------------------------------------------------------------------|
| top10          |                            133.5 |                           320 |                             39.85 |                              93.65 |                             60 |                             260 |                    3 |                    17 |                     0.85 | true_event_duration_mass uses event boundaries; positive_10s_bin_mass uses full 10s bin duration |
| top20          |                            133.5 |                           320 |                             60.4  |                              73.1  |                            110 |                             210 |                    6 |                    14 |                     0.7  | true_event_duration_mass uses event boundaries; positive_10s_bin_mass uses full 10s bin duration |
| top30          |                            133.5 |                           320 |                             73.2  |                              60.3  |                            160 |                             160 |                   10 |                    10 |                     0.5  | true_event_duration_mass uses event boundaries; positive_10s_bin_mass uses full 10s bin duration |

**Conclusion**: H1 remains valid under both definitions, but the magnitude differs.
- Under `true_event_duration_mass`, a substantial fraction of event mass lies outside top10/top20 E0.
- Under `positive_10s_bin_mass`, the numbers are larger because each positive bin contributes a full 10s.
- For future papers, we recommend reporting **true_event_duration_mass** as the primary H1 metric, and using positive_10s_bin_mass only as a secondary lattice coverage measure.

## 2. Point-Anchor vs Long-Event Stratification

| method                     |   budget | event_type    |   num_events |   event_recall_mean |   event_recall_std |   hit_at_5s_mean |   hit_at_10s_mean |   complete_event_coverage_mean |   boundary_iou_03_mean |   boundary_iou_05_mean |   fragmentation_rate_mean |   duplicate_rate_mean | notes   |
|:---------------------------|---------:|:--------------|-------------:|--------------------:|-------------------:|-----------------:|------------------:|-------------------------------:|-----------------------:|-----------------------:|--------------------------:|----------------------:|:--------|
| B6_ExSample                |        5 | point_anchor  |           14 |           0.0380952 |          0.0441601 |       0.0380952  |         0.0380952 |                     0.0380952  |             0          |             0          |                   1       |             0         |         |
| B6_ExSample                |        5 | long_interval |            6 |           0.105556  |          0.100769  |       0.0333333  |         0.0722222 |                     0          |             0.0388889  |             0.0111111  |                   1.17647 |             0.176471  |         |
| B6_ExSample                |        5 | all           |           20 |           0.0583333 |          0.0409946 |       0.0366667  |         0.0483333 |                     0.0266667  |             0.0116667  |             0.00333333 |                   1.08333 |             0.0833333 |         |
| B7_ExSample_plus_expansion |        5 | point_anchor  |           14 |           0.0428571 |          0.0516727 |       0.0428571  |         0.0428571 |                     0.0428571  |             0          |             0          |                   1       |             0         |         |
| B7_ExSample_plus_expansion |        5 | long_interval |            6 |           0.0680556 |          0.0846995 |       0.0569444  |         0.0611111 |                     0          |             0.0402778  |             0.0333333  |                   2.29167 |             1.29167   |         |
| B7_ExSample_plus_expansion |        5 | all           |           20 |           0.0504167 |          0.0325933 |       0.0470833  |         0.0483333 |                     0.03       |             0.0120833  |             0.01       |                   1.60417 |             0.604167  |         |
| Ours_full_LATE_AQP         |        5 | point_anchor  |           14 |           0.0119048 |          0.0266199 |       0.0119048  |         0.0119048 |                     0.0119048  |             0          |             0          |                   1       |             0         |         |
| Ours_full_LATE_AQP         |        5 | long_interval |            6 |           0.188889  |          0.0566558 |       0.00555556 |         0.0222222 |                     0          |             0.0222222  |             0          |                   1.93333 |             0.933333  |         |
| Ours_full_LATE_AQP         |        5 | all           |           20 |           0.065     |          0.0229129 |       0.01       |         0.015     |                     0.00833333 |             0.00666667 |             0          |                   1.85    |             0.85      |         |
| B6_ExSample                |       10 | point_anchor  |           14 |           0.0761905 |          0.0663257 |       0.0761905  |         0.0761905 |                     0.0761905  |             0          |             0          |                   1       |             0         |         |
| B6_ExSample                |       10 | long_interval |            6 |           0.166667  |          0.096225  |       0.0555556  |         0.111111  |                     0          |             0.0666667  |             0.0166667  |                   1.46    |             0.46      |         |
| B6_ExSample                |       10 | all           |           20 |           0.103333  |          0.0531246 |       0.07       |         0.0866667 |                     0.0533333  |             0.02       |             0.005      |                   1.27586 |             0.275862  |         |
| B7_ExSample_plus_expansion |       10 | point_anchor  |           14 |           0.097619  |          0.0737327 |       0.097619   |         0.097619  |                     0.097619   |             0          |             0          |                   1       |             0         |         |
| B7_ExSample_plus_expansion |       10 | long_interval |            6 |           0.127778  |          0.117326  |       0.0916667  |         0.106944  |                     0          |             0.0722222  |             0.0472222  |                   2.44444 |             1.44444   |         |
| B7_ExSample_plus_expansion |       10 | all           |           20 |           0.106667  |          0.052414  |       0.0958333  |         0.100417  |                     0.0683333  |             0.0216667  |             0.0141667  |                   1.61379 |             0.613793  |         |
| Ours_full_LATE_AQP         |       10 | point_anchor  |           14 |           0.0857143 |          0.0285714 |       0.0857143  |         0.0857143 |                     0.0857143  |             0          |             0          |                   1       |             0         |         |
| Ours_full_LATE_AQP         |       10 | long_interval |            6 |           0.355556  |          0.0566558 |       0.183333   |         0.355556  |                     0          |             0.177778   |             0.166667   |                   2.02222 |             1.02222   |         |
| Ours_full_LATE_AQP         |       10 | all           |           20 |           0.166667  |          0.0235702 |       0.115      |         0.166667  |                     0.06       |             0.0533333  |             0.05       |                   1.65    |             0.65      |         |
| B6_ExSample                |       20 | point_anchor  |           14 |           0.161905  |          0.0974738 |       0.161905   |         0.161905  |                     0.161905   |             0          |             0          |                   1       |             0         |         |
| B6_ExSample                |       20 | long_interval |            6 |           0.383333  |          0.156051  |       0.138889   |         0.272222  |                     0          |             0.183333   |             0.0833333  |                   1.54885 |             0.548851  |         |
| B6_ExSample                |       20 | all           |           20 |           0.228333  |          0.0853262 |       0.155      |         0.195     |                     0.113333   |             0.055      |             0.025      |                   1.27091 |             0.270913  |         |
| B7_ExSample_plus_expansion |       20 | point_anchor  |           14 |           0.171429  |          0.0867007 |       0.171429   |         0.171429  |                     0.171429   |             0          |             0          |                   1       |             0         |         |
| B7_ExSample_plus_expansion |       20 | long_interval |            6 |           0.302778  |          0.130851  |       0.251389   |         0.280556  |                     0          |             0.191667   |             0.119444   |                   2.72316 |             1.72316   |         |
| B7_ExSample_plus_expansion |       20 | all           |           20 |           0.210833  |          0.0616385 |       0.195417   |         0.204167  |                     0.12       |             0.0575     |             0.0358333  |                   1.77042 |             0.770417  |         |
| Ours_full_LATE_AQP         |       20 | point_anchor  |           14 |           0.102381  |          0.0439671 |       0.102381   |         0.102381  |                     0.102381   |             0          |             0          |                   1       |             0         |         |
| Ours_full_LATE_AQP         |       20 | long_interval |            6 |           0.394444  |          0.0911179 |       0.355556   |         0.383333  |                     0          |             0.205556   |             0.166667   |                   2.93611 |             1.93611   |         |
| Ours_full_LATE_AQP         |       20 | all           |           20 |           0.19      |          0.0416333 |       0.178333   |         0.186667  |                     0.0716667  |             0.0616667  |             0.05       |                   2.21833 |             1.21833   |         |
| B6_ExSample                |       40 | point_anchor  |           14 |           0.342857  |          0.128307  |       0.342857   |         0.342857  |                     0.342857   |             0          |             0          |                   1       |             0         |         |
| B6_ExSample                |       40 | long_interval |            6 |           0.583333  |          0.127294  |       0.35       |         0.488889  |                     0          |             0.383333   |             0.205556   |                   1.92667 |             0.926667  |         |
| B6_ExSample                |       40 | all           |           20 |           0.415     |          0.0838153 |       0.345      |         0.386667  |                     0.24       |             0.115      |             0.0616667  |                   1.4029  |             0.402898  |         |
| B7_ExSample_plus_expansion |       40 | point_anchor  |           14 |           0.360119  |          0.120372  |       0.360119   |         0.360119  |                     0.360119   |             0          |             0          |                   1       |             0         |         |
| B7_ExSample_plus_expansion |       40 | long_interval |            6 |           0.563889  |          0.173717  |       0.523611   |         0.536111  |                     0          |             0.406944   |             0.254167   |                   2.87097 |             1.87097   |         |
| B7_ExSample_plus_expansion |       40 | all           |           20 |           0.42125   |          0.0800163 |       0.409167   |         0.412917  |                     0.252083   |             0.122083   |             0.07625    |                   1.75422 |             0.75422   |         |
| Ours_full_LATE_AQP         |       40 | point_anchor  |           14 |           0.438095  |          0.0512873 |       0.438095   |         0.438095  |                     0.438095   |             0          |             0          |                   1       |             0         |         |
| Ours_full_LATE_AQP         |       40 | long_interval |            6 |           0.727778  |          0.0803157 |       0.594444   |         0.711111  |                     0          |             0.433333   |             0.388889   |                   2.355   |             1.355     |         |
| Ours_full_LATE_AQP         |       40 | all           |           20 |           0.525     |          0.0281366 |       0.485      |         0.52      |                     0.306667   |             0.13       |             0.116667   |                   1.56449 |             0.564495  |         |
| B6_ExSample                |       80 | point_anchor  |           14 |           0.661905  |          0.116545  |       0.661905   |         0.661905  |                     0.661905   |             0          |             0          |                   1       |             0         |         |
| B6_ExSample                |       80 | long_interval |            6 |           0.877778  |          0.0853461 |       0.705556   |         0.844444  |                     0          |             0.694444   |             0.405556   |                   2.41278 |             1.41278   |         |
| B6_ExSample                |       80 | all           |           20 |           0.726667  |          0.0771722 |       0.675      |         0.716667  |                     0.463333   |             0.208333   |             0.121667   |                   1.51775 |             0.51775   |         |
| B7_ExSample_plus_expansion |       80 | point_anchor  |           14 |           0.711905  |          0.111397  |       0.711905   |         0.711905  |                     0.711905   |             0          |             0          |                   1       |             0         |         |
| B7_ExSample_plus_expansion |       80 | long_interval |            6 |           0.861111  |          0.133218  |       0.85       |         0.855556  |                     0          |             0.694444   |             0.418056   |                   2.95792 |             1.95792   |         |
| B7_ExSample_plus_expansion |       80 | all           |           20 |           0.756667  |          0.0763581 |       0.753333   |         0.755     |                     0.498333   |             0.208333   |             0.125417   |                   1.66739 |             0.66739   |         |
| Ours_full_LATE_AQP         |       80 | point_anchor  |           14 |           0.661905  |          0.055123  |       0.661905   |         0.661905  |                     0.661905   |             0          |             0          |                   1       |             0         |         |
| Ours_full_LATE_AQP         |       80 | long_interval |            6 |           1         |          0         |       0.933333   |         1         |                     0          |             0.833333   |             0.5        |                   2.71111 |             1.71111   |         |
| Ours_full_LATE_AQP         |       80 | all           |           20 |           0.763333  |          0.0385861 |       0.743333   |         0.763333  |                     0.463333   |             0.25       |             0.15       |                   1.67464 |             0.674637  |         |
| B6_ExSample                |      120 | point_anchor  |           14 |           1         |          0         |       1          |         1         |                     1          |             0          |             0          |                   1       |             0         |         |
| B6_ExSample                |      120 | long_interval |            6 |           1         |          0         |       1          |         1         |                     0          |             0.833333   |             0.5        |                   3       |             2         |         |
| B6_ExSample                |      120 | all           |           20 |           1         |          0         |       1          |         1         |                     0.7        |             0.25       |             0.15       |                   1.6     |             0.6       |         |
| B7_ExSample_plus_expansion |      120 | point_anchor  |           14 |           1         |          0         |       1          |         1         |                     1          |             0          |             0          |                   1       |             0         |         |
| B7_ExSample_plus_expansion |      120 | long_interval |            6 |           1         |          0         |       1          |         1         |                     0          |             0.833333   |             0.5        |                   3       |             2         |         |
| B7_ExSample_plus_expansion |      120 | all           |           20 |           1         |          0         |       1          |         1         |                     0.7        |             0.25       |             0.15       |                   1.6     |             0.6       |         |
| Ours_full_LATE_AQP         |      120 | point_anchor  |           14 |           1         |          0         |       1          |         1         |                     1          |             0          |             0          |                   1       |             0         |         |
| Ours_full_LATE_AQP         |      120 | long_interval |            6 |           1         |          0         |       1          |         1         |                     0          |             0.833333   |             0.5        |                   3       |             2         |         |
| Ours_full_LATE_AQP         |      120 | all           |           20 |           1         |          0         |       1          |         1         |                     0.7        |             0.25       |             0.15       |                   1.6     |             0.6       |         |

**Key observations**:
- At budget=40, Ours-full recall on point-anchor events = 0.438 vs B7 = 0.360.
- At budget=40, Ours-full recall on long-interval events = 0.728 vs B7 = 0.564.
- Ours-full improves on long-interval events, supporting the temporal-structure repair claim.

## 3. Precision, Selected Duration, and Duplicate Rate

| method                     |   budget |   selected_total_duration |   selected_positive_duration_overlap |   selected_precision_duration_based |   selected_positive_bin_precision |   duplicate_rate |   fragmentation_rate |   false_positive_duration |
|:---------------------------|---------:|--------------------------:|-------------------------------------:|------------------------------------:|----------------------------------:|-----------------:|---------------------:|--------------------------:|
| B6_ExSample                |        5 |                        50 |                               12.667 |                               0.253 |                             0.253 |            0.067 |                3.917 |                    37.333 |
| B6_ExSample                |       10 |                       100 |                               24.667 |                               0.247 |                             0.247 |            0.267 |                5.483 |                    75.333 |
| B6_ExSample                |       20 |                       200 |                               57.333 |                               0.287 |                             0.287 |            0.271 |                4.138 |                   142.667 |
| B6_ExSample                |       40 |                       400 |                              115     |                               0.288 |                             0.288 |            0.403 |                2.805 |                   285     |
| B6_ExSample                |       80 |                       800 |                              219.667 |                               0.275 |                             0.275 |            0.518 |                1.558 |                   580.333 |
| B7_ExSample_plus_expansion |        5 |                        50 |                               15.333 |                               0.307 |                             0.307 |            0.483 |                3.201 |                    34.667 |
| B7_ExSample_plus_expansion |       10 |                       100 |                               31.75  |                               0.318 |                             0.318 |            0.593 |                3.787 |                    68.25  |
| B7_ExSample_plus_expansion |       20 |                       200 |                               71.333 |                               0.357 |                             0.357 |            0.77  |                2.661 |                   128.667 |
| B7_ExSample_plus_expansion |       40 |                       400 |                              145.5   |                               0.364 |                             0.364 |            0.754 |                1.943 |                   254.5   |
| B7_ExSample_plus_expansion |       80 |                       800 |                              251.5   |                               0.314 |                             0.314 |            0.667 |                1.237 |                   548.5   |
| Ours_full_LATE_AQP         |        5 |                        50 |                               23     |                               0.46  |                             0.46  |            0.85  |                3.4   |                    27     |
| Ours_full_LATE_AQP         |       10 |                       100 |                               54.667 |                               0.547 |                             0.547 |            0.65  |                2.333 |                    45.333 |
| Ours_full_LATE_AQP         |       20 |                       200 |                               81.333 |                               0.407 |                             0.407 |            1.218 |                2.767 |                   118.667 |
| Ours_full_LATE_AQP         |       40 |                       400 |                              164     |                               0.41  |                             0.41  |            0.564 |                1.886 |                   236     |
| Ours_full_LATE_AQP         |       80 |                       800 |                              255.333 |                               0.319 |                             0.319 |            0.675 |                1.297 |                   544.667 |

- At budget=40, Ours-full selected total duration = 400.0s vs B7 = 400.0s.
- Duration-based precision: Ours = 0.410, B7 = 0.364.
- False-positive duration: Ours = 236.0s, B7 = 254.5s.

## 4. Parameter Stability

| method                     |    mean |       std |   min |   max |   num_param_configs |
|:---------------------------|--------:|----------:|------:|------:|--------------------:|
| B6_ExSample                | 0.415   | 0.005     |  0.41 |  0.42 |                   3 |
| B7_ExSample_plus_expansion | 0.42125 | 0.0281332 |  0.36 |  0.47 |                  12 |
| Ours_full_LATE_AQP         | 0.525   | 0.015     |  0.51 |  0.54 |                   3 |

**Interpretation**: A small std relative to the mean indicates stable advantage across pre-registered parameters. A large std means the result depends on parameter choice.

# Budget=40 Case Study

Comparing B7 (chunk_size=120.0s, k=3.0) vs Ours-full (E0=top30).

## Event hit counts (across 10 trials)

- Hit by both: 15 events → ['realcartest_event_0022', 'realcartest_event_0023', 'realcartest_event_0024', 'realcartest_event_0028', 'realcartest_event_0029', 'realcartest_event_0031', 'realcartest_event_0032', 'realcartest_event_0033', 'realcartest_event_0034', 'realcartest_event_0035', 'realcartest_event_0036', 'realcartest_event_0037', 'realcartest_event_0038', 'realcartest_event_0039', 'realcartest_event_0040']
- Hit only by Ours-full: 1 events → ['realcartest_event_0041']
- Hit only by B7: 4 events → ['realcartest_event_0025', 'realcartest_event_0026', 'realcartest_event_0027', 'realcartest_event_0030']
- Hit by neither: 0 events → []

## Events hit only by Ours-full

- **realcartest_event_0041** (point_anchor, duration=0.7s, event interval 1110.0-1110.7s)
  - selected bins: ['1110-1120s']
  - any bin inside top30 E0: True

## Events hit only by B7

- **realcartest_event_0025** (point_anchor, duration=0.2s, event interval 120.5-120.7s)
  - selected bins: ['120-130s']

- **realcartest_event_0026** (point_anchor, duration=0.7s, event interval 250.0-250.7s)
  - selected bins: ['250-260s']

- **realcartest_event_0027** (point_anchor, duration=0.7s, event interval 320.0-320.7s)
  - selected bins: ['320-330s']

- **realcartest_event_0030** (point_anchor, duration=0.7s, event interval 530.0-530.7s)
  - selected bins: ['530-540s']

## Interpretation

- Ours-only events: 0 long-interval, 1 point-anchor.
- All Ours-only events are point-anchor. This weakens the 'temporal structure repair' claim; the gain is better described as event-seed discovery.

