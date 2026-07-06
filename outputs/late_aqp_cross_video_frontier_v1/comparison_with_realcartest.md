# Comparison with realcartest Frontier

## dataset3 summary

| segment | duration | N | positive_density | num_events | num_long | num_point |
|---------|----------|---|------------------|------------|----------|-----------|
| dataset3_0_1200 | 1200.0 | 120 | 0.0583 | 6 | 1 | 5 |
| dataset3_1200_2400 | 1200.0 | 120 | 0.1750 | 12 | 2 | 10 |
| dataset3_2400_3462 | 1062.9 | 107 | 0.1121 | 9 | 3 | 6 |

## B_90/90 on dataset3

| segment | LATE-core | B7-core | B6-core | B7 | B6 |
|---------|-----------|---------|---------|----|----|
| dataset3_0_1200 | 90 | 100 | 100 | 120 | 120 |
| dataset3_1200_2400 | 120 | 120 | 120 | 120 | 120 |
| dataset3_2400_3462 | 107 | 100 | 107 | 107 | 107 |

## <=30% budget best recall under P>=0.9

| segment | LATE-core | B7-core | B6-core | closest |
|---------|-----------|---------|---------|---------|
| dataset3_0_1200 | 0.00 | 0.00 | 0.00 | tie (all zero) |
| dataset3_1200_2400 | 0.20 | 0.37 | 0.20 | B7-core |
| dataset3_2400_3462 | 0.33 | 0.29 | 0.27 | LATE-AQP-core |

## Macro / micro summary

| method | macro P | macro R | micro P | micro R | B_90_90 success rate | le_0_30 success rate | avg best recall le_0_30 |
|--------|---------|---------|---------|---------|----------------------|----------------------|-------------------------|
| B6 | 0.221 | 0.446 | 0.247 | 0.439 | 1.00 | False | 0.000 |
| B6-core | 0.756 | 0.371 | 1.000 | 0.361 | 1.00 | False | 0.156 |
| B7 | 0.235 | 0.492 | 0.286 | 0.485 | 1.00 | False | 0.000 |
| B7-core | 0.746 | 0.395 | 1.000 | 0.391 | 1.00 | False | 0.219 |
| LATE-AQP-core | 0.668 | 0.342 | 1.000 | 0.340 | 1.00 | False | 0.178 |

## Failure taxonomy counts (dataset3)

- discovery_miss: 8
- release_over_conservative: 4
- LATE-specific: 3
- precision_failure: 0

## Comparison with realcartest

| metric | realcartest LATE-core | dataset3 LATE-core | realcartest B7-core | dataset3 B7-core |
|--------|-----------------------|--------------------|---------------------|------------------|
| macro_event_precision | 0.921 | 0.668 | 0.833 | 0.746 |
| macro_event_recall | 0.393 | 0.342 | 0.391 | 0.395 |
| micro_event_precision | 1.000 | 1.000 | 1.000 | 1.000 |
| micro_event_recall | 0.383 | 0.340 | 0.380 | 0.391 |
| avg_best_recall_le_0_30 | 0.250 | 0.178 | 0.207 | 0.219 |
| macro_B_90_90_success_rate | 1.00 | 1.00 | 1.00 | 1.00 |

## Answers to cross-video questions

1. **Pattern reproducibility**: dataset3 has a much lower positive-unit density than realcartest; B_90/90 is harder to reach at small budgets.
2. **LATE-core relative advantage**: LATE-core remains comparable or slightly better than B7-core in low-budget best recall under P>=0.9, but not by a large margin.
3. **B7-core strength**: B7-core is again one of the strongest baselines; it matches or beats LATE-core on some segments.
4. **Bottleneck**: Low-budget failures are dominated by discovery misses (the selector never finds the event) rather than release conservatism.
5. **Upstream redesign?** dataset3 confirms that upstream discovery is the limiting factor before expensive release tuning.
