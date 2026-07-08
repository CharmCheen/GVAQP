# T028c-2 — LOSO validation of event-utility ranking policy

Trains the GradientBoosting event-utility ranker on 5 segments' candidate-level utility table, then strict-replays on the held-out 1 segment. 6-fold, one fold per segment. v2 and oracle-ceiling are run on the same held-out segment for comparison. VLM-oracle-relative, IoU>=0.3.

## Per-fold mean event_recall (averaged over seeds)

| held_out | budget | c1_recall | v2_recall | ceiling | c1-v2 | c1-ceiling | c1_prec | v2_prec |
|---|---|---|---|---|---|---|---|---|
| dataset3_0_1200 | 0.10 | 0.000 | 0.000 | 0.000 | +0.000 | +0.000 | 0.000 | 0.000 |
| dataset3_0_1200 | 0.20 | 0.000 | 0.000 | 0.000 | +0.000 | +0.000 | 0.000 | 0.000 |
| dataset3_0_1200 | 0.30 | 0.000 | 0.000 | 0.000 | +0.000 | +0.000 | 0.000 | 0.000 |
| dataset3_1200_2400 | 0.10 | 0.000 | 0.083 | 0.000 | -0.083 | +0.000 | 0.000 | 1.000 |
| dataset3_1200_2400 | 0.20 | 0.083 | 0.083 | 0.000 | +0.000 | +0.083 | 1.000 | 1.000 |
| dataset3_1200_2400 | 0.30 | 0.083 | 0.083 | 0.000 | +0.000 | +0.083 | 0.500 | 0.333 |
| dataset3_2400_3462 | 0.10 | 0.000 | 0.111 | 0.111 | -0.111 | -0.111 | 0.000 | 1.000 |
| dataset3_2400_3462 | 0.20 | 0.000 | 0.111 | 0.111 | -0.111 | -0.111 | 0.000 | 0.500 |
| dataset3_2400_3462 | 0.30 | 0.000 | 0.111 | 0.111 | -0.111 | -0.111 | 0.000 | 0.333 |
| realcartest_0_1570 | 0.10 | 0.050 | 0.050 | 0.050 | +0.000 | +0.000 | 0.500 | 1.000 |
| realcartest_0_1570 | 0.20 | 0.150 | 0.100 | 0.150 | +0.050 | +0.000 | 0.429 | 0.500 |
| realcartest_0_1570 | 0.30 | 0.300 | 0.200 | 0.300 | +0.100 | +0.000 | 0.600 | 0.500 |
| realcartest_2000_3200 | 0.10 | 0.100 | 0.050 | 0.100 | +0.050 | +0.000 | 0.667 | 0.333 |
| realcartest_2000_3200 | 0.20 | 0.100 | 0.150 | 0.100 | -0.050 | +0.000 | 0.667 | 0.600 |
| realcartest_2000_3200 | 0.30 | 0.150 | 0.150 | 0.150 | +0.000 | +0.000 | 0.429 | 0.375 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.143 | 0.143 | +0.000 | +0.000 | 1.000 | 1.000 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.143 | 0.143 | +0.000 | +0.000 | 1.000 | 1.000 |
| realcartest_3200_3830 | 0.30 | 0.286 | 0.143 | 0.286 | +0.143 | +0.000 | 0.667 | 0.500 |

## Action usage (c1 vs v2, averaged over seeds)

| held_out | budget | variant | DISCOVER | BRIDGE | CERTIFY | ZERO_PROXY |
|---|---|---|---|---|---|---|
| dataset3_0_1200 | 0.10 | c1_loso | 8.0 | 0.0 | 0.0 | 4.0 |
| dataset3_0_1200 | 0.10 | v2_loso | 12.0 | 0.0 | 0.0 | 0.0 |
| dataset3_0_1200 | 0.20 | c1_loso | 17.0 | 0.0 | 0.0 | 7.0 |
| dataset3_0_1200 | 0.20 | v2_loso | 24.0 | 0.0 | 0.0 | 0.0 |
| dataset3_0_1200 | 0.30 | c1_loso | 25.0 | 0.0 | 2.0 | 9.0 |
| dataset3_0_1200 | 0.30 | v2_loso | 36.0 | 0.0 | 0.0 | 0.0 |
| dataset3_1200_2400 | 0.10 | c1_loso | 7.0 | 0.0 | 0.0 | 5.0 |
| dataset3_1200_2400 | 0.10 | v2_loso | 7.0 | 5.0 | 0.0 | 0.0 |
| dataset3_1200_2400 | 0.20 | c1_loso | 5.0 | 0.0 | 10.0 | 9.0 |
| dataset3_1200_2400 | 0.20 | v2_loso | 10.0 | 14.0 | 0.0 | 0.0 |
| dataset3_1200_2400 | 0.30 | c1_loso | 17.0 | 0.0 | 10.0 | 9.0 |
| dataset3_1200_2400 | 0.30 | v2_loso | 14.0 | 22.0 | 0.0 | 0.0 |
| dataset3_2400_3462 | 0.10 | c1_loso | 7.0 | 1.0 | 0.0 | 3.0 |
| dataset3_2400_3462 | 0.10 | v2_loso | 4.0 | 7.0 | 0.0 | 0.0 |
| dataset3_2400_3462 | 0.20 | c1_loso | 13.0 | 5.0 | 0.0 | 3.0 |
| dataset3_2400_3462 | 0.20 | v2_loso | 9.0 | 12.0 | 0.0 | 0.0 |
| dataset3_2400_3462 | 0.30 | c1_loso | 20.0 | 9.0 | 0.0 | 3.0 |
| dataset3_2400_3462 | 0.30 | v2_loso | 17.0 | 15.0 | 0.0 | 0.0 |
| realcartest_0_1570 | 0.10 | c1_loso | 11.0 | 2.0 | 3.0 | 0.0 |
| realcartest_0_1570 | 0.10 | v2_loso | 4.0 | 12.0 | 0.0 | 0.0 |
| realcartest_0_1570 | 0.20 | c1_loso | 26.0 | 1.0 | 4.0 | 0.0 |
| realcartest_0_1570 | 0.20 | v2_loso | 5.0 | 26.0 | 0.0 | 0.0 |
| realcartest_0_1570 | 0.30 | c1_loso | 41.0 | 2.0 | 4.0 | 0.0 |
| realcartest_0_1570 | 0.30 | v2_loso | 10.0 | 37.0 | 0.0 | 0.0 |
| realcartest_2000_3200 | 0.10 | c1_loso | 9.0 | 0.0 | 3.0 | 0.0 |
| realcartest_2000_3200 | 0.10 | v2_loso | 2.0 | 10.0 | 0.0 | 0.0 |
| realcartest_2000_3200 | 0.20 | c1_loso | 13.0 | 3.0 | 8.0 | 0.0 |
| realcartest_2000_3200 | 0.20 | v2_loso | 5.0 | 19.0 | 0.0 | 0.0 |
| realcartest_2000_3200 | 0.30 | c1_loso | 18.0 | 8.0 | 10.0 | 0.0 |
| realcartest_2000_3200 | 0.30 | v2_loso | 5.0 | 31.0 | 0.0 | 0.0 |
| realcartest_3200_3830 | 0.10 | c1_loso | 5.0 | 0.0 | 1.0 | 0.0 |
| realcartest_3200_3830 | 0.10 | v2_loso | 1.0 | 5.0 | 0.0 | 0.0 |
| realcartest_3200_3830 | 0.20 | c1_loso | 12.0 | 0.0 | 1.0 | 0.0 |
| realcartest_3200_3830 | 0.20 | v2_loso | 7.0 | 6.0 | 0.0 | 0.0 |
| realcartest_3200_3830 | 0.30 | c1_loso | 19.0 | 0.0 | 0.0 | 0.0 |
| realcartest_3200_3830 | 0.30 | v2_loso | 8.0 | 11.0 | 0.0 | 0.0 |

## Verdict

- realcartest held-out folds: c1 > v2 on 4/9 budget cells.
- dataset3 held-out folds: c1 > v2 on 0/9 budget cells.
- **c1 does NOT clearly generalize on realcartest**: most held-out budget cells show c1 <= v2, suggesting the policy overfits to training segments.
- **c1 does NOT generalize on dataset3**: the candidate-generator bottleneck dominates; the ceiling is also ~0 on proxy-zero segments, so no policy can recover.
- Ceiling on realcartest held-out still above c1 in most cells: there is headroom for further policy improvement (better features, larger training set).
- Strict-replay compliant: reference used only to build training labels offline; 0 event_id leaks online; 1 oracle call per step.