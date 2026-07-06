# First-Lag Report — When does v2 fall behind B6?

For each segment and budget, we report the first call index at which v2 cumulative long-event recall is strictly below B6 mean recall.

| Segment | Budget | first_lag_call | v2_recall_at_lag | b6_recall_at_lag | gap | interpretation |
|---------|--------|----------------|------------------|------------------|-----|----------------|
| realcartest_0_1570 | 10 | 1 | 0.000 | 0.025 | -0.025 | v2 starts behind |
| realcartest_0_1570 | 20 | 1 | 0.000 | 0.025 | -0.025 | v2 starts behind |
| realcartest_2000_3200 | 10 | 5 | 0.167 | 0.200 | -0.033 | v2 falls behind mid-run |
| realcartest_2000_3200 | 20 | 5 | 0.167 | 0.200 | -0.033 | v2 falls behind mid-run |
| realcartest_3200_3830 | 10 | 8 | 0.250 | 0.300 | -0.050 | v2 falls behind mid-run |
| realcartest_3200_3830 | 20 | 8 | 0.250 | 0.300 | -0.050 | v2 falls behind mid-run |
