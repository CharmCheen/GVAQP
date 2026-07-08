# T028e-0 — proxy-free candidate generator ceiling audit

Extended candidate set with 5 proxy-free arms (SPACE_FILLING, LARGEST_GAP, VDC, MIDBAND, LOCAL_GAP_FLANK) on top of the original 4 (DISCOVER, BRIDGE, CERTIFY, ZERO_PROXY). Oracle ceiling selects the max-marginal-utility arm at each step (reads reference -> NOT strict-replay). Pass condition: at least one dataset3 proxy-zero segment ceiling rises above v2/c1.

## Mean event_recall: extended-ceiling vs original-ceiling vs v2

| segment | budget | ext_ceiling | orig_ceiling | v2 | ext-orig | ext-v2 |
|---|---|---|---|---|---|---|
| dataset3_0_1200 | 0.10 | 0.000 (0.000) | 0.000 (0.000) | 0.000 (0.000) | +0.000 | +0.000 |
| dataset3_0_1200 | 0.20 | 0.000 (0.000) | 0.000 (0.000) | 0.000 (0.000) | +0.000 | +0.000 |
| dataset3_0_1200 | 0.30 | 0.000 (0.000) | 0.000 (0.000) | 0.000 (0.000) | +0.000 | +0.000 |
| dataset3_1200_2400 | 0.10 | 0.083 (0.250) | 0.000 (0.000) | 0.000 (0.000) | +0.083 | +0.083 |
| dataset3_1200_2400 | 0.20 | 0.083 (0.143) | 0.000 (0.000) | 0.083 (1.000) | +0.083 | +0.000 |
| dataset3_1200_2400 | 0.30 | 0.083 (0.111) | 0.000 (0.000) | 0.083 (0.333) | +0.083 | +0.000 |
| dataset3_2400_3462 | 0.10 | 0.111 (0.500) | 0.111 (0.500) | 0.000 (0.000) | +0.000 | +0.111 |
| dataset3_2400_3462 | 0.20 | 0.111 (0.500) | 0.111 (0.500) | 0.000 (0.000) | +0.000 | +0.111 |
| dataset3_2400_3462 | 0.30 | 0.111 (0.333) | 0.111 (0.333) | 0.000 (0.000) | +0.000 | +0.111 |
| realcartest_0_1570 | 0.10 | 0.050 (0.500) | 0.050 (0.500) | 0.050 (1.000) | +0.000 | +0.000 |
| realcartest_0_1570 | 0.20 | 0.150 (0.429) | 0.150 (0.429) | 0.100 (0.500) | +0.000 | +0.050 |
| realcartest_0_1570 | 0.30 | 0.300 (0.600) | 0.300 (0.600) | 0.200 (0.500) | +0.000 | +0.100 |
| realcartest_2000_3200 | 0.10 | 0.100 (0.667) | 0.100 (0.667) | 0.050 (0.333) | +0.000 | +0.050 |
| realcartest_2000_3200 | 0.20 | 0.100 (0.333) | 0.100 (0.333) | 0.150 (0.600) | +0.000 | -0.050 |
| realcartest_2000_3200 | 0.30 | 0.150 (0.273) | 0.150 (0.273) | 0.150 (0.375) | +0.000 | +0.000 |
| realcartest_3200_3830 | 0.10 | 0.143 (1.000) | 0.143 (1.000) | 0.143 (1.000) | +0.000 | +0.000 |
| realcartest_3200_3830 | 0.20 | 0.143 (1.000) | 0.143 (1.000) | 0.143 (1.000) | +0.000 | +0.000 |
| realcartest_3200_3830 | 0.30 | 0.286 (0.667) | 0.286 (0.667) | 0.143 (0.500) | +0.000 | +0.143 |

## Extended-ceiling arm usage

| arm | n_calls | positive_rate | mean_u |
|---|---|---|---|
| DISCOVER | 1095 | 0.290 | 0.102 |
| BRIDGE | 48 | 1.000 | 0.303 |
| CERTIFY | 36 | 1.000 | 0.629 |
| ZERO_PROXY | 0 | 0.000 | 0.000 |
| ZERO_PROXY_SPACE_FILLING | 0 | 0.000 | 0.000 |
| ZERO_PROXY_LARGEST_GAP | 6 | 1.000 | 0.185 |
| ZERO_PROXY_VDC | 18 | 1.000 | 0.185 |
| ZERO_PROXY_MIDBAND | 27 | 1.000 | 0.175 |
| ZERO_PROXY_LOCAL_GAP_FLANK | 6 | 1.000 | 0.176 |

## Ceiling lift by video

- **realcartest**: ext_ceiling=0.158, orig_ceiling=0.158, v2=0.125, ext-orig=+0.000, ext-v2=+0.033
- **dataset3**: ext_ceiling=0.065, orig_ceiling=0.037, v2=0.019, ext-orig=+0.028, ext-v2=+0.046

## Pass/fail verdict

- **PASS**: dataset3 proxy-zero ceiling LIFTS above original 4-arm ceiling.
  Max lift: +0.083
- OK: realcartest ceiling does not regress (or regresses <0.01).
- This is an OFFLINE CEILING: selection reads reference, NOT strict-replay. If ceiling rises, proceed to T028e-1 (train event-utility selector with extended arm set, strict-replay LOSO). If ceiling does not rise, the proxy-free candidate families are insufficient and need redesign.