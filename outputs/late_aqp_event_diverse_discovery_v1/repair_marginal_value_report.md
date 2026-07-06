# Repair Marginal Value Report

Comparison of LATE-D3-core (chunk-bandit discovery + repair + Core/Halo) vs D3-norepair-core (chunk-bandit discovery + Core/Halo, no repair).

## chunk_size = 30s

- Average delta unique events (D3 - no-repair): -1.300
- Segments where D3 has strictly more unique events: 0/6
- Segments where D3 has strictly fewer unique events: 5/6
- Average delta long-event recall (D3 - no-repair): -0.028

| segment | D3 unique | no-repair unique | delta | D3 long-R | no-repair long-R | delta | D3 B_90/90 | no-repair B_90/90 |
|---------|-----------|------------------|-------|-----------|------------------|-------|------------|-------------------|
| realcartest_0_1570 | 18.60 | 20.00 | -1.40 | 1.000 | 1.000 | +0.000 | 157 | 157 |
| realcartest_2000_3200 | 16.80 | 20.00 | -3.20 | 0.933 | 1.000 | -0.067 | not_reached | 120 |
| realcartest_3200_3830 | 5.60 | 7.00 | -1.40 | 1.000 | 1.000 | +0.000 | not_reached | 60 |
| dataset3_0_1200 | 6.00 | 6.00 | +0.00 | 1.000 | 1.000 | +0.000 | 120 | 100 |
| dataset3_1200_2400 | 11.60 | 12.00 | -0.40 | 0.900 | 1.000 | -0.100 | 120 | 120 |
| dataset3_2400_3462 | 7.60 | 9.00 | -1.40 | 1.000 | 1.000 | +0.000 | not_reached | 107 |

## chunk_size = 60s

- Average delta unique events (D3 - no-repair): -0.967
- Segments where D3 has strictly more unique events: 0/6
- Segments where D3 has strictly fewer unique events: 6/6
- Average delta long-event recall (D3 - no-repair): -0.011

| segment | D3 unique | no-repair unique | delta | D3 long-R | no-repair long-R | delta | D3 B_90/90 | no-repair B_90/90 |
|---------|-----------|------------------|-------|-----------|------------------|-------|------------|-------------------|
| realcartest_0_1570 | 18.60 | 20.00 | -1.40 | 1.000 | 1.000 | +0.000 | 157 | 157 |
| realcartest_2000_3200 | 17.40 | 20.00 | -2.60 | 0.933 | 1.000 | -0.067 | not_reached | 120 |
| realcartest_3200_3830 | 6.40 | 7.00 | -0.60 | 1.000 | 1.000 | +0.000 | 63 | 60 |
| dataset3_0_1200 | 5.80 | 6.00 | -0.20 | 1.000 | 1.000 | +0.000 | 120 | 120 |
| dataset3_1200_2400 | 11.40 | 12.00 | -0.60 | 1.000 | 1.000 | +0.000 | 120 | 120 |
| dataset3_2400_3462 | 8.60 | 9.00 | -0.40 | 1.000 | 1.000 | +0.000 | 100 | 100 |

## chunk_size = 120s

- Average delta unique events (D3 - no-repair): -1.167
- Segments where D3 has strictly more unique events: 0/6
- Segments where D3 has strictly fewer unique events: 4/6
- Average delta long-event recall (D3 - no-repair): -0.046

| segment | D3 unique | no-repair unique | delta | D3 long-R | no-repair long-R | delta | D3 B_90/90 | no-repair B_90/90 |
|---------|-----------|------------------|-------|-----------|------------------|-------|------------|-------------------|
| realcartest_0_1570 | 17.80 | 20.00 | -2.20 | 0.975 | 1.000 | -0.025 | not_reached | 157 |
| realcartest_2000_3200 | 17.20 | 20.00 | -2.80 | 0.933 | 1.000 | -0.067 | not_reached | 120 |
| realcartest_3200_3830 | 5.60 | 7.00 | -1.40 | 0.950 | 1.000 | -0.050 | not_reached | 60 |
| dataset3_0_1200 | 6.00 | 6.00 | +0.00 | 1.000 | 1.000 | +0.000 | 80 | 60 |
| dataset3_1200_2400 | 12.00 | 12.00 | +0.00 | 1.000 | 1.000 | +0.000 | 120 | 120 |
| dataset3_2400_3462 | 8.40 | 9.00 | -0.60 | 0.867 | 1.000 | -0.133 | 107 | 100 |

## D3-norepair-core vs B7-core

Both use a chunk-bandit-style discovery backbone, but differ in release details:
- B7-core uses the existing B7 temporal expansion + Core/Halo; it is posthoc_eval because it uses event_id.
- D3-norepair-core uses strict-replay chunk-bandit discovery (no event_id) + Core/Halo; no repair.
- Core/Halo guard rules and MAX_GUARDS_PER_SIDE=3 are the same.

| segment | no-repair best R@P>=0.9 le30 | B7-core best R@P>=0.9 le30 | no-repair B_90/90 | B7-core B_90/90 |
|---------|------------------------------|----------------------------|-------------------|------------------|
| realcartest_0_1570 | 0.290 | 0.300 | 157 | 157 |
| realcartest_2000_3200 | 0.180 | 0.320 | 120 | 120 |
| realcartest_3200_3830 | 0.114 | 0.114 | 60 | 60 |
| dataset3_0_1200 | 0.333 | 0.367 | 120 | 60 |
| dataset3_1200_2400 | 0.183 | 0.383 | 120 | 120 |
| dataset3_2400_3462 | 0.200 | 0.333 | 100 | 100 |

