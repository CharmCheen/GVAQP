# High-Budget Regression Check — v2 vs v1

Per-segment mean ± std for long_event_recall and precision at B=40/80/120.

| Segment | Budget | Metric | v1 mean | v1 std | v2 mean | v2 std | Δ (v2-v1) |
|---------|--------|--------|---------|--------|---------|--------|-----------|
| realcartest_0_1570 | 40 | recall | 0.800 | 0.100 | 0.800 | 0.100 | 0.000 |
| realcartest_0_1570 | 40 | precision | 0.407 | 0.040 | 0.407 | 0.040 | 0.000 |
| realcartest_0_1570 | 80 | recall | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| realcartest_0_1570 | 80 | precision | 0.276 | 0.005 | 0.276 | 0.005 | 0.000 |
| realcartest_0_1570 | 120 | recall | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| realcartest_0_1570 | 120 | precision | 0.209 | 0.000 | 0.209 | 0.000 | 0.000 |
| realcartest_2000_3200 | 40 | recall | 0.700 | 0.067 | 0.700 | 0.067 | 0.000 |
| realcartest_2000_3200 | 40 | precision | 0.177 | 0.012 | 0.177 | 0.012 | 0.000 |
| realcartest_2000_3200 | 80 | recall | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| realcartest_2000_3200 | 80 | precision | 0.149 | 0.000 | 0.149 | 0.000 | 0.000 |
| realcartest_2000_3200 | 120 | recall | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| realcartest_2000_3200 | 120 | precision | 0.111 | 0.000 | 0.111 | 0.000 | 0.000 |
| realcartest_3200_3830 | 40 | recall | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| realcartest_3200_3830 | 40 | precision | 0.138 | 0.010 | 0.138 | 0.010 | 0.000 |
| realcartest_3200_3830 | 80 | recall | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| realcartest_3200_3830 | 80 | precision | 0.101 | 0.000 | 0.101 | 0.000 | 0.000 |
| realcartest_3200_3830 | 120 | recall | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| realcartest_3200_3830 | 120 | precision | 0.101 | 0.000 | 0.101 | 0.000 | 0.000 |

## Regression flags

No v2 drop exceeds the v1 within-seed standard deviation at B=40/80/120.
