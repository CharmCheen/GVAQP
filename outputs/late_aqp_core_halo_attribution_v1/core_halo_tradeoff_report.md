# Core/Halo Tradeoff Analysis

Release variants computed without re-running discovery.

| Segment | Budget | Variant | Precision | Recall | Duration |
|---------|--------|---------|-----------|--------|----------|
| realcartest_0_1570 | 120 | core_only | 1.000 | 0.850 | 410.0 |
| realcartest_0_1570 | 120 | core_plus_1bin_halo | 1.000 | 0.850 | 682.0 |
| realcartest_0_1570 | 120 | core_plus_2bin_halo | 0.949 | 0.850 | 754.0 |
| realcartest_0_1570 | 120 | core_plus_positive_guard | 1.000 | 0.850 | 410.0 |
| realcartest_0_1570 | 120 | full_window | 0.467 | 0.840 | 1046.0 |

## Reach 90/90?

Yes: 20 segment-budget-variant combinations reach 90/90.
- realcartest_2000_3200 B=120 core_only: P=1.000, R=1.000
- realcartest_2000_3200 B=120 core_plus_1bin_halo: P=1.000, R=1.000
- realcartest_2000_3200 B=120 core_plus_2bin_halo: P=1.000, R=1.000
- realcartest_2000_3200 B=120 core_plus_positive_guard: P=1.000, R=1.000
- realcartest_2000_3200 B=120 full_window: P=1.000, R=1.000
- realcartest_3200_3830 B=80 core_only: P=1.000, R=1.000
- realcartest_3200_3830 B=80 core_plus_1bin_halo: P=1.000, R=1.000
- realcartest_3200_3830 B=80 core_plus_2bin_halo: P=1.000, R=1.000
- realcartest_3200_3830 B=80 core_plus_positive_guard: P=1.000, R=1.000
- realcartest_3200_3830 B=80 full_window: P=1.000, R=1.000
- realcartest_3200_3830 B=100 core_only: P=1.000, R=1.000
- realcartest_3200_3830 B=100 core_plus_1bin_halo: P=1.000, R=1.000
- realcartest_3200_3830 B=100 core_plus_2bin_halo: P=1.000, R=1.000
- realcartest_3200_3830 B=100 core_plus_positive_guard: P=1.000, R=1.000
- realcartest_3200_3830 B=100 full_window: P=1.000, R=1.000
- realcartest_3200_3830 B=120 core_only: P=1.000, R=1.000
- realcartest_3200_3830 B=120 core_plus_1bin_halo: P=1.000, R=1.000
- realcartest_3200_3830 B=120 core_plus_2bin_halo: P=1.000, R=1.000
- realcartest_3200_3830 B=120 core_plus_positive_guard: P=1.000, R=1.000
- realcartest_3200_3830 B=120 full_window: P=1.000, R=1.000

## Hardest segment (realcartest_0_1570) B=120

- core_only: P=1.000, R=0.850
- core_plus_1bin_halo: P=1.000, R=0.850
- full_window: P=0.467, R=0.840

Adding halo does not reach 90/90 or causes precision to drop below 0.9, indicating upstream discovery is the limiting factor.
