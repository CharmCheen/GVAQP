# B_90/90 Summary

B_90/90 is the first budget in {5,10,20,40,60,80,100,120} where mean event_precision >= 0.9 and mean event_recall >= 0.9.

| Segment | Method | B_90_90 | precision_at_point | recall_at_point |
|---------|--------|---------|--------------------|------------------|
| realcartest_0_1570 | B6 | not_reached | 0.395 | 0.790 |
| realcartest_0_1570 | B7 | not_reached | 0.204 | 0.770 |
| realcartest_0_1570 | LATE-AQP-core | not_reached | 1.000 | 0.850 |
| realcartest_2000_3200 | B6 | 120 | 1.000 | 1.000 |
| realcartest_2000_3200 | B7 | 120 | 1.000 | 1.000 |
| realcartest_2000_3200 | LATE-AQP-core | 120 | 1.000 | 1.000 |
| realcartest_3200_3830 | B6 | 80 | 1.000 | 1.000 |
| realcartest_3200_3830 | B7 | 80 | 1.000 | 1.000 |
| realcartest_3200_3830 | LATE-AQP-core | 80 | 1.000 | 1.000 |

## Section 5 answers

### a) LATE-AQP-core reaches 90/90 in 2/3 segments.

- realcartest_2000_3200: B_90/90 = 120 (P=1.000, R=1.000)
- realcartest_3200_3830: B_90/90 = 80 (P=1.000, R=1.000)

### b) B6/B7 on the same segments

- realcartest_0_1570: B6 B_90/90 = not_reached (P=0.395, R=0.790); B7 B_90/90 = not_reached (P=0.204, R=0.770)
- realcartest_2000_3200: B6 B_90/90 = 120 (P=1.000, R=1.000); B7 B_90/90 = 120 (P=1.000, R=1.000)
- realcartest_3200_3830: B6 B_90/90 = 80 (P=1.000, R=1.000); B7 B_90/90 = 80 (P=1.000, R=1.000)

### c) B_90/90 premium of LATE-AQP-core vs best of B6/B7

- realcartest_2000_3200: LATE-AQP-core B=120 / best baseline B=120 = 1.00x
- realcartest_3200_3830: LATE-AQP-core B=80 / best baseline B=80 = 1.00x

Max premium observed: 1.00x.

### d) LATE-AQP-core reaches but baselines do not

No such segment in this experiment.

### e) Guard budget overhead

Across all segments and budgets, guard calls account for a mean of **29.2%** of LATE-AQP-core's total used budget.

Guard overhead is one contributor to LATE-AQP-core needing more budget than B6/B7, but it is not the only factor: B6/B7 operate on raw selected intervals without any precision-constrained release, so they avoid both the guard cost and the recall loss from discarding halo regions.
