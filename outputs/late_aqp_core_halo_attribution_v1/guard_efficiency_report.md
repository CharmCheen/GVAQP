# Guard Efficiency Report

Statistics computed over LATE-AQP-core guard calls. 'total' is the sum across seeds; guard_fraction uses the per-seed mean.

| Segment | Budget | total | per_seed_mean | positive | negative_stop | positive_rate | guard_fraction |
|---------|--------|-------|---------------|----------|---------------|---------------|----------------|
| realcartest_0_1570 | 5 | 0 | 0.00 | 0 | 0 | 0.000 | 0.000 |
| realcartest_0_1570 | 10 | 0 | 0.00 | 0 | 0 | 0.000 | 0.000 |
| realcartest_0_1570 | 20 | 47 | 9.40 | 41 | 6 | 0.872 | 0.573 |
| realcartest_0_1570 | 40 | 66 | 13.20 | 39 | 27 | 0.591 | 0.455 |
| realcartest_0_1570 | 60 | 109 | 21.80 | 66 | 43 | 0.606 | 0.408 |
| realcartest_0_1570 | 80 | 121 | 24.20 | 59 | 62 | 0.488 | 0.313 |
| realcartest_0_1570 | 100 | 94 | 18.80 | 23 | 71 | 0.245 | 0.191 |
| realcartest_0_1570 | 120 | 77 | 15.40 | 10 | 67 | 0.130 | 0.128 |
| realcartest_2000_3200 | 5 | 18 | 3.60 | 14 | 4 | 0.778 | 0.720 |
| realcartest_2000_3200 | 10 | 42 | 8.40 | 21 | 21 | 0.500 | 0.840 |
| realcartest_2000_3200 | 20 | 25 | 5.00 | 15 | 10 | 0.600 | 0.379 |
| realcartest_2000_3200 | 40 | 80 | 16.00 | 24 | 56 | 0.300 | 0.510 |
| realcartest_2000_3200 | 60 | 91 | 18.20 | 27 | 64 | 0.297 | 0.357 |
| realcartest_2000_3200 | 80 | 119 | 23.80 | 24 | 95 | 0.202 | 0.307 |
| realcartest_2000_3200 | 100 | 139 | 27.80 | 35 | 104 | 0.252 | 0.282 |
| realcartest_2000_3200 | 120 | 0 | 0.00 | 0 | 0 | 0.000 | 0.000 |
| realcartest_3200_3830 | 5 | 20 | 4.00 | 15 | 5 | 0.750 | 0.800 |
| realcartest_3200_3830 | 10 | 10 | 2.00 | 5 | 5 | 0.500 | 0.200 |
| realcartest_3200_3830 | 20 | 20 | 4.00 | 5 | 15 | 0.250 | 0.213 |
| realcartest_3200_3830 | 40 | 56 | 11.20 | 11 | 45 | 0.196 | 0.284 |
| realcartest_3200_3830 | 60 | 45 | 9.00 | 0 | 45 | 0.000 | 0.150 |
| realcartest_3200_3830 | 80 | 0 | 0.00 | 0 | 0 | 0.000 | 0.000 |
| realcartest_3200_3830 | 100 | 0 | 0.00 | 0 | 0 | 0.000 | 0.000 |
| realcartest_3200_3830 | 120 | 0 | 0.00 | 0 | 0 | 0.000 | 0.000 |

## Overall (LATE-AQP-core)

- Total guard calls: 1179
- Positive guard calls: 434 (36.8%)
- Negative stop calls: 745 (63.2%)
- Mean guard fraction of total budget: 29.6%
- Mean guard calls per selected interval: 0.82
- Mean guard calls per recovered event: 1.84

## Answers

1. Guards consume a mean of **29.6%** of LATE-AQP-core's total budget.
2. **36.8%** of guard calls land on positive bins (effective boundary expansion); the rest are negative-stop confirmations.
3. At B<=20 the guard fraction is **41.4%**, confirming that guard overhead is proportionally highest when the total budget is small.
4. Whether a dynamic guard cap is needed depends on whether the low-budget tradeoff (high guard fraction, lower recall) is acceptable; the data here does not force a redesign, but a per-interval adaptive cap could be explored.
