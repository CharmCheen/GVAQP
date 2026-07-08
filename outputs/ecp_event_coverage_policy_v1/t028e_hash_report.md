# T028e-H — HASH_STRATIFIED candidate family ceiling audit

Adds `ZERO_PROXY_HASH` as a 10th candidate arm (ceiling-only). HASH produces a stable seed-specific permutation of zero-proxy bins and proposes the first unqueried bin at each step. This is a CEILING audit — NOT strict-replay.

## Ceiling comparison: with-HASH vs without-HASH

| segment | budget | nohash_static | hash_static | nohash_closed | hash_closed | d_static | d_closed |
|---|---|---|---|---|---|---|---|
| realcartest_0_1570 | 0.10 | 0.050 | 0.050 | 0.050 | 0.050 | +0.000 | +0.000 |
| realcartest_0_1570 | 0.20 | 0.150 | 0.150 | 0.200 | 0.200 | +0.000 | +0.000 |
| realcartest_0_1570 | 0.30 | 0.300 | 0.300 | 0.250 | 0.250 | +0.000 | +0.000 |
| realcartest_2000_3200 | 0.10 | 0.100 | 0.100 | 0.100 | 0.100 | +0.000 | +0.000 |
| realcartest_2000_3200 | 0.20 | 0.100 | 0.100 | 0.150 | 0.150 | +0.000 | +0.000 |
| realcartest_2000_3200 | 0.30 | 0.150 | 0.150 | 0.200 | 0.200 | +0.000 | +0.000 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.143 | 0.143 | 0.143 | +0.000 | +0.000 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.143 | 0.143 | 0.143 | +0.000 | +0.000 |
| realcartest_3200_3830 | 0.30 | 0.286 | 0.286 | 0.286 | 0.286 | +0.000 | +0.000 |
| dataset3_0_1200 | 0.10 | 0.000 | 0.000 | 0.167 | 0.111 | +0.000 | -0.056 |
| dataset3_0_1200 | 0.20 | 0.000 | 0.000 | 0.167 | 0.111 | +0.000 | -0.056 |
| dataset3_0_1200 | 0.30 | 0.000 | 0.000 | 0.167 | 0.111 | +0.000 | -0.056 |
| dataset3_1200_2400 | 0.10 | 0.083 | 0.083 | 0.167 | 0.139 | +0.000 | -0.028 |
| dataset3_1200_2400 | 0.20 | 0.083 | 0.083 | 0.167 | 0.167 | +0.000 | +0.000 |
| dataset3_1200_2400 | 0.30 | 0.083 | 0.083 | 0.167 | 0.167 | +0.000 | +0.000 |
| dataset3_2400_3462 | 0.10 | 0.111 | 0.111 | 0.111 | 0.111 | +0.000 | +0.000 |
| dataset3_2400_3462 | 0.20 | 0.111 | 0.111 | 0.111 | 0.111 | +0.000 | +0.000 |
| dataset3_2400_3462 | 0.30 | 0.111 | 0.111 | 0.222 | 0.222 | +0.000 | +0.000 |

## Static ceiling arm calls (HASH added)

| segment | budget | DISCOVER | BRIDGE | CERTIFY | ... | ZP_HASH |
|---|---|---|---|---|---|---|
| realcartest_0_1570 | 0.10 | 15 | 1 | 0 | | 0 |
| realcartest_0_1570 | 0.20 | 30 | 1 | 0 | | 0 |
| realcartest_0_1570 | 0.30 | 46 | 1 | 0 | | 0 |
| realcartest_2000_3200 | 0.10 | 10 | 2 | 0 | | 0 |
| realcartest_2000_3200 | 0.20 | 22 | 2 | 0 | | 0 |
| realcartest_2000_3200 | 0.30 | 33 | 3 | 0 | | 0 |
| realcartest_3200_3830 | 0.10 | 5 | 1 | 0 | | 0 |
| realcartest_3200_3830 | 0.20 | 12 | 1 | 0 | | 0 |
| realcartest_3200_3830 | 0.30 | 18 | 1 | 0 | | 0 |
| dataset3_0_1200 | 0.10 | 10 | 1 | 0 | | 0 |
| dataset3_0_1200 | 0.20 | 22 | 1 | 0 | | 0 |
| dataset3_0_1200 | 0.30 | 34 | 1 | 0 | | 0 |
| dataset3_1200_2400 | 0.10 | 5 | 0 | 3 | | 1 |
| dataset3_1200_2400 | 0.20 | 16 | 0 | 3 | | 1 |
| dataset3_1200_2400 | 0.30 | 27 | 0 | 3 | | 1 |
| dataset3_2400_3462 | 0.10 | 10 | 0 | 1 | | 0 |
| dataset3_2400_3462 | 0.20 | 20 | 0 | 1 | | 0 |
| dataset3_2400_3462 | 0.30 | 31 | 0 | 1 | | 0 |

## Pass/fail

- dataset3_0_1200 static ceiling: nohash=0.000, hash=0.000
- dataset3_1200_2400 static ceiling: nohash=0.083, hash=0.083
- Mean VDC calls on dataset3 (static): 0.6
- Mean HASH calls on dataset3 (static): 0.2
- **NEUTRAL**: HASH does not change dataset3_0_1200 static ceiling.
- OK: realcartest ceiling does not regress.
- OK: HASH does not dominate zp budget (0.2 vs VDC 0.6).

- HASH is NOT added to main c2. This is a ceiling-only audit. If HASH provides clear seed-diversity benefit and does not regress, it can be considered for ECP-c3 in a future iteration.