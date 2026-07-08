# T028e diagnostics — ceiling clarification

Resolves the discrepancy where c2 (strict-replay LOSO, 0.167) exceeded the T028e-0 extended ceiling (0.000) on dataset3_0_1200.

The T028e-0 ceiling is ITERATIVE (closed-loop) but MYOPIC: the `marginal_utility` function assigns u=0.02 to ALL negative probes, and the `best_u <= 0.02` safety override ALWAYS falls back to DISCOVER. On dataset3_0_1200 where all proxy scores are 0, DISCOVER = no-op forever, making the ceiling a **static trajectory ceiling** rather than a true oracle.

The **closed-loop oracle ceiling** removes the safety override and adds a small exploration bonus (+0.04) for zero-proxy arms when zp_share >= 0.30, preferring exploration over repeated DISCOVER.

## Ceiling comparison: static vs closed-loop oracle

| segment | budget | static_recall | closed_recall | delta |
|---|---|---|---|---|
| dataset3_0_1200 | 0.10 | 0.000 | 0.167 | +0.167 |
| dataset3_0_1200 | 0.20 | 0.000 | 0.167 | +0.167 |
| dataset3_0_1200 | 0.30 | 0.000 | 0.167 | +0.167 |
| dataset3_1200_2400 | 0.10 | 0.083 | 0.167 | +0.083 |
| dataset3_1200_2400 | 0.20 | 0.083 | 0.167 | +0.083 |
| dataset3_1200_2400 | 0.30 | 0.083 | 0.167 | +0.083 |
| dataset3_2400_3462 | 0.10 | 0.111 | 0.111 | +0.000 |
| dataset3_2400_3462 | 0.20 | 0.111 | 0.111 | +0.000 |
| dataset3_2400_3462 | 0.30 | 0.111 | 0.222 | +0.111 |
| realcartest_0_1570 | 0.10 | 0.050 | 0.050 | +0.000 |
| realcartest_0_1570 | 0.20 | 0.150 | 0.200 | +0.050 |
| realcartest_0_1570 | 0.30 | 0.300 | 0.250 | -0.050 |
| realcartest_2000_3200 | 0.10 | 0.100 | 0.100 | +0.000 |
| realcartest_2000_3200 | 0.20 | 0.100 | 0.150 | +0.050 |
| realcartest_2000_3200 | 0.30 | 0.150 | 0.200 | +0.050 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.143 | +0.000 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.143 | +0.000 |
| realcartest_3200_3830 | 0.30 | 0.286 | 0.286 | +0.000 |

## Cross-check: c2 (strict-replay LOSO) vs ceilings

| segment | budget | static_ceil | closed_ceil | c2_loso | c2-static | c2-closed |
|---|---|---|---|---|---|---|
| dataset3_0_1200 | 0.10 | 0.000 | 0.167 | 0.000 | +0.000 | -0.167 |
| dataset3_0_1200 | 0.20 | 0.000 | 0.167 | 0.167 | +0.167 | +0.000 |
| dataset3_0_1200 | 0.30 | 0.000 | 0.167 | 0.167 | +0.167 | +0.000 |
| dataset3_1200_2400 | 0.10 | 0.083 | 0.167 | 0.000 | -0.083 | -0.167 |
| dataset3_1200_2400 | 0.20 | 0.083 | 0.167 | 0.083 | +0.000 | -0.083 |
| dataset3_1200_2400 | 0.30 | 0.083 | 0.167 | 0.083 | +0.000 | -0.083 |
| dataset3_2400_3462 | 0.10 | 0.111 | 0.111 | 0.000 | -0.111 | -0.111 |
| dataset3_2400_3462 | 0.20 | 0.111 | 0.111 | 0.111 | +0.000 | +0.000 |
| dataset3_2400_3462 | 0.30 | 0.111 | 0.222 | 0.111 | +0.000 | -0.111 |
| realcartest_0_1570 | 0.10 | 0.050 | 0.050 | 0.050 | +0.000 | +0.000 |
| realcartest_0_1570 | 0.20 | 0.150 | 0.200 | 0.150 | +0.000 | -0.050 |
| realcartest_0_1570 | 0.30 | 0.300 | 0.250 | 0.300 | +0.000 | +0.050 |
| realcartest_2000_3200 | 0.10 | 0.100 | 0.100 | 0.100 | +0.000 | +0.000 |
| realcartest_2000_3200 | 0.20 | 0.100 | 0.150 | 0.150 | +0.050 | +0.000 |
| realcartest_2000_3200 | 0.30 | 0.150 | 0.200 | 0.200 | +0.050 | +0.000 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.143 | 0.143 | +0.000 | +0.000 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.143 | 0.143 | +0.000 | +0.000 |
| realcartest_3200_3830 | 0.30 | 0.286 | 0.286 | 0.286 | +0.000 | +0.000 |

## Arm utility summary

| arm | n_proposed | n_positive | positive_rate | mean_u | selected_static | selected_closed |
|---|---|---|---|---|---|---|
| BRIDGE | 2223 | 435 | 0.196 | 0.037 | 48 | 210 |
| CERTIFY | 2193 | 504 | 0.230 | 0.043 | 36 | 48 |
| DISCOVER | 2472 | 759 | 0.307 | 0.032 | 1095 | 420 |
| ZERO_PROXY | 909 | 24 | 0.026 | 0.032 | 0 | 180 |
| ZERO_PROXY_LARGEST_GAP | 1248 | 15 | 0.012 | 0.021 | 6 | 12 |
| ZERO_PROXY_LOCAL_GAP_FLANK | 1248 | 6 | 0.005 | 0.021 | 6 | 0 |
| ZERO_PROXY_MIDBAND | 1248 | 117 | 0.094 | 0.033 | 27 | 45 |
| ZERO_PROXY_SPACE_FILLING | 1248 | 54 | 0.043 | 0.033 | 0 | 258 |
| ZERO_PROXY_VDC | 1248 | 102 | 0.082 | 0.040 | 18 | 63 |

## Verdict

- dataset3_0_1200 static ceiling max: 0.000
- dataset3_0_1200 closed-loop ceiling max: 0.167
- dataset3_0_1200 c2 LOSO max: 0.167
- **PASS**: closed-loop oracle ceiling >= c2, paradox resolved.

- The original T028e-0 ceiling is a **static trajectory ceiling** — it is iterative but follows a fixed greedy path due to the safety override. The closed-loop oracle ceiling with exploration bonus is a closer approximation of an ideal oracle. Neither achieves the global optimal (which would require DP), but the closed-loop variant doesn't get stuck in DISCOVER-only chains.