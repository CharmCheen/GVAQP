# T030a — ECP-Portfolio candidate ceiling audit

Closed-loop oracle ceiling with 10 portfolio arms: ECP_DISCOVER, ECP_CERTIFY, ECP_BRIDGE, ECP_ZERO_PROXY_VDC, B7_NEXT, D3_NEXT, EventLift_DISCOVER, EventLift_CERTIFY, HTS_EC_TREE, TOPPROXY_NEXT.

At each step, ALL arms propose their next query; offline marginal event-utility selects the best. Exploration bonus for zp arms when zp_share >= 0.30. No safety override.

## Ceiling comparison: Portfolio vs baselines

| segment | budget | Portfolio | ECP-c2 | B7 | D3 | HTS-EC | EventLift | TopProxy |
|---|---|---|---|---|---|---|---|---|
| realcartest_0_1570 | 0.10 | R0.150/P0.500 | R0.050/P0.500 | R0.150/P0.500 | R0.100/P0.286 | R0.067/P0.722 | R0.200/P0.667 | R0.050/P0.500 |
| realcartest_0_1570 | 0.20 | R0.200/P0.500 | R0.150/P0.429 | R0.150/P0.375 | R0.150/P0.500 | R0.117/P0.806 | R0.250/P0.556 | R0.150/P0.500 |
| realcartest_0_1570 | 0.30 | R0.250/P0.417 | R0.300/P0.600 | R0.250/P0.500 | R0.250/P0.500 | R0.183/P0.624 | R0.300/P0.429 | R0.300/P0.636 |
| realcartest_2000_3200 | 0.10 | R0.100/P0.500 | R0.100/P1.000 | R0.050/P0.500 | R0.050/P1.000 | R0.100/P0.667 | R0.100/P1.000 | R0.100/P0.667 |
| realcartest_2000_3200 | 0.20 | R0.150/P0.429 | R0.150/P0.750 | R0.100/P0.500 | R0.100/P0.400 | R0.100/P0.333 | R0.150/P0.429 | R0.100/P0.333 |
| realcartest_2000_3200 | 0.30 | R0.150/P0.333 | R0.200/P0.444 | R0.150/P0.375 | R0.150/P0.600 | R0.200/P0.400 | R0.200/P0.444 | R0.200/P0.400 |
| realcartest_3200_3830 | 0.10 | R0.143/P0.500 | R0.143/P1.000 | R0.429/P1.000 | R0.143/P1.000 | R0.143/P0.667 | R0.143/P0.333 | R0.143/P1.000 |
| realcartest_3200_3830 | 0.20 | R0.143/P0.333 | R0.143/P0.500 | R0.429/P1.000 | R0.286/P0.667 | R0.143/P0.667 | R0.143/P0.500 | R0.143/P0.500 |
| realcartest_3200_3830 | 0.30 | R0.143/P0.333 | R0.286/P0.667 | R0.571/P1.000 | R0.286/P0.667 | R0.143/P0.667 | R0.286/P0.400 | R0.286/P0.667 |
| dataset3_0_1200 | 0.10 | R0.167/P1.000 | R0.000/P0.000 | R0.000/P0.000 | R0.167/P1.000 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 |
| dataset3_0_1200 | 0.20 | R0.167/P0.500 | R0.167/P0.500 | R0.000/P0.000 | R0.167/P0.500 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 |
| dataset3_0_1200 | 0.30 | R0.167/P0.250 | R0.167/P0.500 | R0.167/P0.333 | R0.167/P0.500 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 |
| dataset3_1200_2400 | 0.10 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 | R0.083/P0.200 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 |
| dataset3_1200_2400 | 0.20 | R0.000/P0.000 | R0.083/P0.250 | R0.083/P1.000 | R0.167/P0.400 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 |
| dataset3_1200_2400 | 0.30 | R0.083/P0.200 | R0.083/P0.250 | R0.083/P0.200 | R0.167/P0.250 | R0.000/P0.000 | R0.083/P0.250 | R0.000/P0.000 |
| dataset3_2400_3462 | 0.10 | R0.000/P0.000 | R0.000/P0.000 | R0.111/P0.500 | R0.000/P0.000 | R0.000/P0.000 | R0.111/P0.333 | R0.000/P0.000 |
| dataset3_2400_3462 | 0.20 | R0.111/P0.500 | R0.111/P0.500 | R0.111/P0.333 | R0.111/P1.000 | R0.000/P0.000 | R0.222/P0.667 | R0.000/P0.000 |
| dataset3_2400_3462 | 0.30 | R0.111/P0.333 | R0.111/P0.500 | R0.111/P0.333 | R0.111/P1.000 | R0.111/P0.333 | R0.222/P0.667 | R0.111/P0.333 |

## Portfolio vs best baseline recall delta

| segment | budget | pf_recall | best_bl_recall | best_bl | delta |
|---|---|---|---|---|---|
| realcartest_0_1570 | 0.10 | 0.150 | 0.200 | EventLift-DC | -0.050 |
| realcartest_0_1570 | 0.20 | 0.200 | 0.250 | EventLift-DC | -0.050 |
| realcartest_0_1570 | 0.30 | 0.250 | 0.300 | EventLift-DC | -0.050 |
| realcartest_2000_3200 | 0.10 | 0.100 | 0.100 | HTS-EC | +0.000 |
| realcartest_2000_3200 | 0.20 | 0.150 | 0.150 | EventLift-DC | +0.000 |
| realcartest_2000_3200 | 0.30 | 0.150 | 0.200 | HTS-EC | -0.050 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.429 | B7 | -0.286 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.429 | B7 | -0.286 |
| realcartest_3200_3830 | 0.30 | 0.143 | 0.571 | B7 | -0.429 |
| dataset3_0_1200 | 0.10 | 0.167 | 0.167 | D3 | +0.000 |
| dataset3_0_1200 | 0.20 | 0.167 | 0.167 | D3 | +0.000 |
| dataset3_0_1200 | 0.30 | 0.167 | 0.167 | B7 | +0.000 |
| dataset3_1200_2400 | 0.10 | 0.000 | 0.083 | D3 | -0.083 |
| dataset3_1200_2400 | 0.20 | 0.000 | 0.167 | D3 | -0.167 |
| dataset3_1200_2400 | 0.30 | 0.083 | 0.167 | D3 | -0.083 |
| dataset3_2400_3462 | 0.10 | 0.000 | 0.111 | B7 | -0.111 |
| dataset3_2400_3462 | 0.20 | 0.111 | 0.222 | EventLift-DC | -0.111 |
| dataset3_2400_3462 | 0.30 | 0.111 | 0.222 | EventLift-DC | -0.111 |

**Portfolio wins: 0, ties: 5, losses: 13**

## Per-video mean recall


### realcartest


### dataset3


### realcartest

- Portfolio ceiling: recall=0.159, prec=0.427
- ECP-c2 LOSO: recall=0.169, prec=0.654
- B7: recall=0.253, prec=0.639
- D3: recall=0.168, prec=0.624
- HTS-EC: recall=0.133, prec=0.617
- EventLift-DC: recall=0.197, prec=0.529

### dataset3

- Portfolio ceiling: recall=0.090, prec=0.309
- ECP-c2 LOSO: recall=0.080, prec=0.278
- B7: recall=0.074, prec=0.300
- D3: recall=0.127, prec=0.539
- HTS-EC: recall=0.012, prec=0.037
- EventLift-DC: recall=0.071, prec=0.213

## Portfolio arm usage (mean calls per segment-budget-seed)

| arm | mean_calls | positive_rate_est |
|---|---|---|
| ECP_ZERO_PROXY_VDC | 20.3 | - |
| B7_NEXT | 6.7 | - |
| EventLift_DISCOVER | 3.8 | - |
| ECP_DISCOVER | 3.0 | - |
| ECP_CERTIFY | 2.3 | - |
| EventLift_CERTIFY | 6.3 | - |
| ECP_BRIDGE | 6.0 | - |
| HTS_EC_TREE | 2.7 | - |

## Pass/fail

- Portfolio realcartest mean recall: 0.159 vs B7: 0.253 (delta -0.094)
- Portfolio dataset3 mean recall: 0.090 vs D3: 0.127 (delta -0.037)
- **FAIL**: Portfolio ceiling does not clearly exceed best single baselines (0 wins).

- This is an OFFLINE CEILING. If it passes, proceed to T030b (train event-utility portfolio selector for strict replay).