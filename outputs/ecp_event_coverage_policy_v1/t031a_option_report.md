# T031a — Interval-option closed-loop ceiling

Closed-loop oracle ceiling with 10 interval-level options. Multi-step options (B7_EXPAND, ANCHOR_BRIDGE, etc.) simulate multiple queries internally; utility is computed per-call. Ceiling uses true labels to evaluate options offline — NOT strict replay.

## Recall ceiling: options vs baselines

| segment | budget | OptionCeil | ECP-c2 | B7 | D3 | EventLift |
|---|---|---|---|---|---|---|
| realcartest_0_1570 | 0.10 | R0.050/P0.333 | R0.050 | R0.150 | R0.100 | R0.200 |
| realcartest_0_1570 | 0.20 | R0.050/P0.250 | R0.150 | R0.150 | R0.150 | R0.250 |
| realcartest_0_1570 | 0.30 | R0.250/P0.625 | R0.300 | R0.250 | R0.250 | R0.300 |
| realcartest_2000_3200 | 0.10 | R0.100/P0.667 | R0.100 | R0.050 | R0.050 | R0.100 |
| realcartest_2000_3200 | 0.20 | R0.150/P0.600 | R0.150 | R0.100 | R0.100 | R0.150 |
| realcartest_2000_3200 | 0.30 | R0.150/P0.375 | R0.200 | R0.150 | R0.150 | R0.200 |
| realcartest_3200_3830 | 0.10 | R0.143/P1.000 | R0.143 | R0.429 | R0.143 | R0.143 |
| realcartest_3200_3830 | 0.20 | R0.143/P1.000 | R0.143 | R0.429 | R0.286 | R0.143 |
| realcartest_3200_3830 | 0.30 | R0.286/P0.667 | R0.286 | R0.571 | R0.286 | R0.286 |
| dataset3_0_1200 | 0.10 | R0.167/P1.000 | R0.000 | R0.000 | R0.167 | R0.000 |
| dataset3_0_1200 | 0.20 | R0.167/P0.500 | R0.167 | R0.000 | R0.167 | R0.000 |
| dataset3_0_1200 | 0.30 | R0.167/P0.250 | R0.167 | R0.167 | R0.167 | R0.000 |
| dataset3_1200_2400 | 0.10 | R0.000/P0.000 | R0.000 | R0.000 | R0.083 | R0.000 |
| dataset3_1200_2400 | 0.20 | R0.083/P0.250 | R0.083 | R0.083 | R0.167 | R0.000 |
| dataset3_1200_2400 | 0.30 | R0.167/P0.333 | R0.083 | R0.083 | R0.167 | R0.083 |
| dataset3_2400_3462 | 0.10 | R0.000/P0.000 | R0.000 | R0.111 | R0.000 | R0.111 |
| dataset3_2400_3462 | 0.20 | R0.111/P0.500 | R0.111 | R0.111 | R0.111 | R0.222 |
| dataset3_2400_3462 | 0.30 | R0.111/P0.333 | R0.111 | R0.111 | R0.111 | R0.222 |

## Key deltas: OptionCeil vs ECP-c2 vs B7

| segment | budget | option_recall | c2_recall | B7_recall | opt-c2 | opt-B7 |
|---|---|---|---|---|---|---|
| realcartest_0_1570 | 0.10 | 0.050 | 0.050 | 0.150 | +0.000 | -0.100 |
| realcartest_0_1570 | 0.20 | 0.050 | 0.150 | 0.150 | -0.100 | -0.100 |
| realcartest_0_1570 | 0.30 | 0.250 | 0.300 | 0.250 | -0.050 | +0.000 |
| realcartest_2000_3200 | 0.10 | 0.100 | 0.100 | 0.050 | +0.000 | +0.050 |
| realcartest_2000_3200 | 0.20 | 0.150 | 0.150 | 0.100 | +0.000 | +0.050 |
| realcartest_2000_3200 | 0.30 | 0.150 | 0.200 | 0.150 | -0.050 | +0.000 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.143 | 0.429 | +0.000 | -0.286 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.143 | 0.429 | +0.000 | -0.286 |
| realcartest_3200_3830 | 0.30 | 0.286 | 0.286 | 0.571 | +0.000 | -0.286 |
| dataset3_0_1200 | 0.10 | 0.167 | 0.000 | 0.000 | +0.167 | +0.167 |
| dataset3_0_1200 | 0.20 | 0.167 | 0.167 | 0.000 | +0.000 | +0.167 |
| dataset3_0_1200 | 0.30 | 0.167 | 0.167 | 0.167 | +0.000 | +0.000 |
| dataset3_1200_2400 | 0.10 | 0.000 | 0.000 | 0.000 | +0.000 | +0.000 |
| dataset3_1200_2400 | 0.20 | 0.083 | 0.083 | 0.083 | +0.000 | -0.000 |
| dataset3_1200_2400 | 0.30 | 0.167 | 0.083 | 0.083 | +0.083 | +0.083 |
| dataset3_2400_3462 | 0.10 | 0.000 | 0.000 | 0.111 | +0.000 | -0.111 |
| dataset3_2400_3462 | 0.20 | 0.111 | 0.111 | 0.111 | +0.000 | -0.000 |
| dataset3_2400_3462 | 0.30 | 0.111 | 0.111 | 0.111 | +0.000 | -0.000 |

## Option usage (mean calls)

| option | mean_calls |
|---|---|
| ZERO_PROXY_VDC | 18.9 |
| DISCOVER | 8.4 |
| BRIDGE | 4.6 |
| B7_EXPAND_FIXED_R3 | 3.0 |
| CERTIFY_BOUNDARY | 2.2 |
| ANCHOR_BRIDGE | 1.7 |
| CERTIFY | 1.5 |
| B7_EXPAND_STOP_NEG | 1.4 |

## Per-video mean recall


### realcartest

- Option ceiling: recall=0.147, prec=0.613
- ECP-c2: recall=0.169
- B7: recall=0.253
- D3: recall=0.168
- EventLift: recall=0.197

### dataset3

- Option ceiling: recall=0.108, prec=0.352
- ECP-c2: recall=0.080
- B7: recall=0.074
- D3: recall=0.127
- EventLift: recall=0.071

## Pass/fail

- realcartest: option=0.147, c2=0.169, B7=0.253
- dataset3: option=0.108, c2=0.080
- realcartest_3200_3830 @0.30: option=0.286, B7=0.571
- **FAIL**: Option ceiling (0.147) does not significantly exceed c2 (0.169).
- **FAIL**: B7_EXPAND (0.286) still far from B7 (0.571) on realcartest_3200_3830.

- This is an OFFLINE CEILING. If option ceiling significantly exceeds c2 and approaches B7 on realcartest_3200_3830, proceed to T031b (train option policy for strict replay).