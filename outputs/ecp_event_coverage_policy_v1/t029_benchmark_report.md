# T029 — ECP-c2-globalcap frozen benchmark

Apples-to-apples comparison of ECP-c2 (and c1, v2) against primary baselines. All data from existing strict-replay runs; no new experiments. LOSO for ECP variants; fixed-seed strict replay for baselines.

## Methods

- **ECP-c2-globalcap**
- **ECP-c1**
- **ECP-v2-LOSO**
- **HTS-EC-safe**
- **EventLift-discover-certify**
- **B7-strict-replay**
- **D3-norepair-core-strict**
- **fixed_10s_topproxy**

## Table A: Absolute performance (event_recall, event_precision)

| segment | budget | ECP-c2-globa | ECP-c1 | ECP-v2-LOSO | HTS-EC-safe | EventLift-di | B7-strict-re | D3-norepair- | fixed_10s_to |
| - | - | - | - | - | - | - | - | - | - | - |
| realcartest_0_1570 | 0.10 | R0.050/P0.500 | R0.050/P0.500 | R0.050/P1.000 | R0.067/P0.722 | R0.200/P0.667 | R0.150/P0.500 | R0.100/P0.286 | R0.050/P0.500 |
| realcartest_0_1570 | 0.20 | R0.150/P0.429 | R0.150/P0.429 | R0.100/P0.500 | R0.117/P0.806 | R0.250/P0.556 | R0.150/P0.375 | R0.150/P0.500 | R0.150/P0.500 |
| realcartest_0_1570 | 0.30 | R0.300/P0.600 | R0.300/P0.600 | R0.200/P0.500 | R0.183/P0.624 | R0.300/P0.429 | R0.250/P0.500 | R0.250/P0.500 | R0.300/P0.636 |
| realcartest_2000_3200 | 0.10 | R0.100/P1.000 | R0.100/P0.667 | R0.050/P0.333 | R0.100/P0.667 | R0.100/P1.000 | R0.050/P0.500 | R0.050/P1.000 | R0.100/P0.667 |
| realcartest_2000_3200 | 0.20 | R0.150/P0.750 | R0.100/P0.667 | R0.150/P0.600 | R0.100/P0.333 | R0.150/P0.429 | R0.100/P0.500 | R0.100/P0.400 | R0.100/P0.333 |
| realcartest_2000_3200 | 0.30 | R0.200/P0.444 | R0.150/P0.429 | R0.150/P0.375 | R0.200/P0.400 | R0.200/P0.444 | R0.150/P0.375 | R0.150/P0.600 | R0.200/P0.400 |
| realcartest_3200_3830 | 0.10 | R0.143/P1.000 | R0.143/P1.000 | R0.143/P1.000 | R0.143/P0.667 | R0.143/P0.333 | R0.429/P1.000 | R0.143/P1.000 | R0.143/P1.000 |
| realcartest_3200_3830 | 0.20 | R0.143/P0.500 | R0.143/P1.000 | R0.143/P1.000 | R0.143/P0.667 | R0.143/P0.500 | R0.429/P1.000 | R0.286/P0.667 | R0.143/P0.500 |
| realcartest_3200_3830 | 0.30 | R0.286/P0.667 | R0.286/P0.667 | R0.143/P0.500 | R0.143/P0.667 | R0.286/P0.400 | R0.571/P1.000 | R0.286/P0.667 | R0.286/P0.667 |
| dataset3_0_1200 | 0.10 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 | R0.167/P1.000 | R0.000/P0.000 |
| dataset3_0_1200 | 0.20 | R0.167/P0.500 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 | R0.167/P0.500 | R0.000/P0.000 |
| dataset3_0_1200 | 0.30 | R0.167/P0.500 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 | R0.167/P0.333 | R0.167/P0.500 | R0.000/P0.000 |
| dataset3_1200_2400 | 0.10 | R0.000/P0.000 | R0.000/P0.000 | R0.083/P1.000 | R0.000/P0.000 | R0.000/P0.000 | R0.000/P0.000 | R0.083/P0.200 | R0.000/P0.000 |
| dataset3_1200_2400 | 0.20 | R0.083/P0.250 | R0.083/P1.000 | R0.083/P1.000 | R0.000/P0.000 | R0.000/P0.000 | R0.083/P1.000 | R0.167/P0.400 | R0.000/P0.000 |
| dataset3_1200_2400 | 0.30 | R0.083/P0.250 | R0.083/P0.500 | R0.083/P0.333 | R0.000/P0.000 | R0.083/P0.250 | R0.083/P0.200 | R0.167/P0.250 | R0.000/P0.000 |
| dataset3_2400_3462 | 0.10 | R0.000/P0.000 | R0.000/P0.000 | R0.111/P1.000 | R0.000/P0.000 | R0.111/P0.333 | R0.111/P0.500 | R0.000/P0.000 | R0.000/P0.000 |
| dataset3_2400_3462 | 0.20 | R0.111/P0.500 | R0.000/P0.000 | R0.111/P0.500 | R0.000/P0.000 | R0.222/P0.667 | R0.111/P0.333 | R0.111/P1.000 | R0.000/P0.000 |
| dataset3_2400_3462 | 0.30 | R0.111/P0.500 | R0.000/P0.000 | R0.111/P0.333 | R0.111/P0.333 | R0.222/P0.667 | R0.111/P0.333 | R0.111/P1.000 | R0.111/P0.333 |

## Table B: Recall delta over ECP-v2-LOSO

| segment | budget | ECP-c2-globalcap | ECP-c1 | HTS-EC-safe | EventLift-discover-certify | B7-strict-replay | D3-norepair-core-strict | fixed_10s_topproxy |
| - | - | - | - | - | - | - | - | - | - |
| realcartest_0_1570 | 0.10 | +0.000 | +0.000 | +0.017 | +0.150 | +0.100 | +0.050 | -0.000 |
| realcartest_0_1570 | 0.20 | +0.050 | +0.050 | +0.017 | +0.150 | +0.050 | +0.050 | +0.050 |
| realcartest_0_1570 | 0.30 | +0.100 | +0.100 | -0.017 | +0.100 | +0.050 | +0.050 | +0.100 |
| realcartest_2000_3200 | 0.10 | +0.050 | +0.050 | +0.050 | +0.050 | -0.000 | -0.000 | +0.050 |
| realcartest_2000_3200 | 0.20 | +0.000 | -0.050 | -0.050 | +0.000 | -0.050 | -0.050 | -0.050 |
| realcartest_2000_3200 | 0.30 | +0.050 | +0.000 | +0.050 | +0.050 | +0.000 | +0.000 | +0.050 |
| realcartest_3200_3830 | 0.10 | +0.000 | +0.000 | -0.000 | -0.000 | +0.286 | -0.000 | -0.000 |
| realcartest_3200_3830 | 0.20 | +0.000 | +0.000 | -0.000 | -0.000 | +0.286 | +0.143 | -0.000 |
| realcartest_3200_3830 | 0.30 | +0.143 | +0.143 | -0.000 | +0.143 | +0.429 | +0.143 | +0.143 |
| dataset3_0_1200 | 0.10 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | +0.167 | +0.000 |
| dataset3_0_1200 | 0.20 | +0.167 | +0.000 | +0.000 | +0.000 | +0.000 | +0.167 | +0.000 |
| dataset3_0_1200 | 0.30 | +0.167 | +0.000 | +0.000 | +0.000 | +0.167 | +0.167 | +0.000 |
| dataset3_1200_2400 | 0.10 | -0.083 | -0.083 | -0.083 | -0.083 | -0.083 | +0.000 | -0.083 |
| dataset3_1200_2400 | 0.20 | +0.000 | +0.000 | -0.083 | -0.083 | +0.000 | +0.083 | -0.083 |
| dataset3_1200_2400 | 0.30 | +0.000 | +0.000 | -0.083 | +0.000 | +0.000 | +0.083 | -0.083 |
| dataset3_2400_3462 | 0.10 | -0.111 | -0.111 | -0.111 | +0.000 | +0.000 | -0.111 | -0.111 |
| dataset3_2400_3462 | 0.20 | +0.000 | -0.111 | -0.111 | +0.111 | +0.000 | +0.000 | -0.111 |
| dataset3_2400_3462 | 0.30 | +0.000 | -0.111 | +0.000 | +0.111 | +0.000 | +0.000 | +0.000 |

## Summary: wins/losses vs ECP-v2-LOSO

- **ECP-c2-globalcap**: 7 wins / 2 losses / 9 ties over v2
- **ECP-c1**: 4 wins / 5 losses / 9 ties over v2
- **HTS-EC-safe**: 4 wins / 7 losses / 7 ties over v2
- **EventLift-discover-certify**: 8 wins / 2 losses / 8 ties over v2
- **B7-strict-replay**: 7 wins / 2 losses / 9 ties over v2
- **D3-norepair-core-strict**: 10 wins / 2 losses / 6 ties over v2
- **fixed_10s_topproxy**: 5 wins / 6 losses / 7 ties over v2

## Table C: Recall delta over best-per-cell

| segment | budget | ECP-c2-globa | ECP-c1 | ECP-v2-LOSO | HTS-EC-safe | EventLift-di | B7-strict-re | D3-norepair- | fixed_10s_to | best_method |
| - | - | - | - | - | - | - | - | - | - | - | - |
| realcartest_0_1570 | 0.10 | -0.150 | -0.150 | -0.150 | -0.133 | +0.000 | -0.050 | -0.100 | -0.150 | EventLift-disco |
| realcartest_0_1570 | 0.20 | -0.100 | -0.100 | -0.150 | -0.133 | +0.000 | -0.100 | -0.100 | -0.100 | EventLift-disco |
| realcartest_0_1570 | 0.30 | +0.000 | +0.000 | -0.100 | -0.117 | +0.000 | -0.050 | -0.050 | +0.000 | EventLift-disco |
| realcartest_2000_3200 | 0.10 | +0.000 | +0.000 | -0.050 | +0.000 | -0.000 | -0.050 | -0.050 | -0.000 | HTS-EC-safe |
| realcartest_2000_3200 | 0.20 | +0.000 | -0.050 | +0.000 | -0.050 | +0.000 | -0.050 | -0.050 | -0.050 | EventLift-disco |
| realcartest_2000_3200 | 0.30 | +0.000 | -0.050 | -0.050 | +0.000 | -0.000 | -0.050 | -0.050 | -0.000 | HTS-EC-safe |
| realcartest_3200_3830 | 0.10 | -0.286 | -0.286 | -0.286 | -0.286 | -0.286 | +0.000 | -0.286 | -0.286 | B7-strict-repla |
| realcartest_3200_3830 | 0.20 | -0.286 | -0.286 | -0.286 | -0.286 | -0.286 | +0.000 | -0.143 | -0.286 | B7-strict-repla |
| realcartest_3200_3830 | 0.30 | -0.286 | -0.286 | -0.429 | -0.429 | -0.286 | +0.000 | -0.286 | -0.286 | B7-strict-repla |
| dataset3_0_1200 | 0.10 | -0.167 | -0.167 | -0.167 | -0.167 | -0.167 | -0.167 | +0.000 | -0.167 | D3-norepair-cor |
| dataset3_0_1200 | 0.20 | +0.000 | -0.167 | -0.167 | -0.167 | -0.167 | -0.167 | -0.000 | -0.167 | ECP-c2-globalca |
| dataset3_0_1200 | 0.30 | +0.000 | -0.167 | -0.167 | -0.167 | -0.167 | -0.000 | -0.000 | -0.167 | ECP-c2-globalca |
| dataset3_1200_2400 | 0.10 | -0.083 | -0.083 | -0.000 | -0.083 | -0.083 | -0.083 | +0.000 | -0.083 | D3-norepair-cor |
| dataset3_1200_2400 | 0.20 | -0.083 | -0.083 | -0.083 | -0.167 | -0.167 | -0.083 | +0.000 | -0.167 | D3-norepair-cor |
| dataset3_1200_2400 | 0.30 | -0.083 | -0.083 | -0.083 | -0.167 | -0.083 | -0.083 | +0.000 | -0.167 | D3-norepair-cor |
| dataset3_2400_3462 | 0.10 | -0.111 | -0.111 | -0.000 | -0.111 | +0.000 | +0.000 | -0.111 | -0.111 | B7-strict-repla |
| dataset3_2400_3462 | 0.20 | -0.111 | -0.222 | -0.111 | -0.222 | +0.000 | -0.111 | -0.111 | -0.222 | EventLift-disco |
| dataset3_2400_3462 | 0.30 | -0.111 | -0.222 | -0.111 | -0.111 | +0.000 | -0.111 | -0.111 | -0.111 | EventLift-disco |

## Per-segment highlight


### realcartest

- **ECP-c2-globalcap**: mean recall=0.169, mean precision=0.654 (n=9 cells)
- **ECP-c1**: mean recall=0.158, mean precision=0.662 (n=9 cells)
- **ECP-v2-LOSO**: mean recall=0.125, mean precision=0.645 (n=9 cells)
- **HTS-EC-safe**: mean recall=0.133, mean precision=0.617 (n=9 cells)
- **EventLift-discover-certify**: mean recall=0.197, mean precision=0.529 (n=9 cells)
- **B7-strict-replay**: mean recall=0.253, mean precision=0.639 (n=9 cells)
- **D3-norepair-core-strict**: mean recall=0.168, mean precision=0.624 (n=9 cells)
- **fixed_10s_topproxy**: mean recall=0.164, mean precision=0.578 (n=9 cells)

### dataset3

- **ECP-c2-globalcap**: mean recall=0.080, mean precision=0.278 (n=9 cells)
- **ECP-c1**: mean recall=0.018, mean precision=0.167 (n=9 cells)
- **ECP-v2-LOSO**: mean recall=0.065, mean precision=0.463 (n=9 cells)
- **HTS-EC-safe**: mean recall=0.012, mean precision=0.037 (n=9 cells)
- **EventLift-discover-certify**: mean recall=0.071, mean precision=0.213 (n=9 cells)
- **B7-strict-replay**: mean recall=0.074, mean precision=0.300 (n=9 cells)
- **D3-norepair-core-strict**: mean recall=0.127, mean precision=0.539 (n=9 cells)
- **fixed_10s_topproxy**: mean recall=0.012, mean precision=0.037 (n=9 cells)

## Compliance

- All methods strict-replay compliant (no online use of event_id / reference).
- ECP variants: LOSO cross-segment (6-fold); baselines: fixed-seed strict replay.
- Data sources: hts_ec_v0_strict_v1, ecp_event_coverage_policy_v1.
- No new VLM/GPU/oracle calls. Benchmark is aggregation-only.