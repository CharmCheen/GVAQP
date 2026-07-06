# Failure Casebook

This casebook uses the stored candidate/core bin traces in `event_diverse_frontier_raw.csv` to produce concrete per-event examples. event_id is used only for evaluation/casebook, never for selection.

## Per-segment/method summary (at max budget with budget_ratio <= 0.30, averaged over seeds)

| segment | method | budget | event_recall | discovery_miss | release_over_conservative |
|---------|--------|--------|--------------|----------------|---------------------------|
| realcartest_0_1570 | B7-core | 47 | 0.300 | 14.4 | 0.0 |
| realcartest_0_1570 | LATE-D0-core | 47 | 0.250 | 15.4 | 0.0 |
| realcartest_0_1570 | LATE-D1-core-radius20 | 47 | 0.560 | 8.8 | 0.0 |
| realcartest_0_1570 | LATE-D2-core-q30-smass-rhighest | 47 | 0.350 | 14.2 | 0.0 |
| realcartest_0_1570 | LATE-D3-core-chunk60 | 47 | 0.180 | 16.8 | 0.0 |
| realcartest_0_1570 | D3-norepair-core-chunk60 | 47 | 0.290 | 15.0 | 0.0 |
| realcartest_2000_3200 | B7-core | 36 | 0.320 | 14.4 | 0.0 |
| realcartest_2000_3200 | LATE-D0-core | 36 | 0.360 | 13.2 | 0.0 |
| realcartest_2000_3200 | LATE-D1-core-radius20 | 36 | 0.540 | 9.4 | 0.0 |
| realcartest_2000_3200 | LATE-D2-core-q30-smass-rhighest | 36 | 0.210 | 16.0 | 0.0 |
| realcartest_2000_3200 | LATE-D3-core-chunk60 | 36 | 0.210 | 16.2 | 0.0 |
| realcartest_2000_3200 | D3-norepair-core-chunk60 | 36 | 0.180 | 16.6 | 0.0 |
| realcartest_3200_3830 | B7-core | 13 | 0.114 | 6.4 | 0.0 |
| realcartest_3200_3830 | LATE-D0-core | 13 | 0.200 | 5.6 | 0.0 |
| realcartest_3200_3830 | LATE-D1-core-radius20 | 13 | 0.200 | 5.6 | 0.0 |
| realcartest_3200_3830 | LATE-D2-core-q30-smass-rhighest | 13 | 0.286 | 5.0 | 0.0 |
| realcartest_3200_3830 | LATE-D3-core-chunk60 | 13 | 0.314 | 5.0 | 0.0 |
| realcartest_3200_3830 | D3-norepair-core-chunk60 | 13 | 0.114 | 6.2 | 0.0 |
| dataset3_0_1200 | B7-core | 36 | 0.367 | 3.8 | 0.0 |
| dataset3_0_1200 | LATE-D0-core | 36 | 0.000 | 6.0 | 0.0 |
| dataset3_0_1200 | LATE-D1-core-radius20 | 36 | 0.367 | 3.8 | 0.0 |
| dataset3_0_1200 | LATE-D2-core-q30-smass-rhighest | 36 | 0.000 | 6.0 | 0.0 |
| dataset3_0_1200 | LATE-D3-core-chunk60 | 36 | 0.200 | 5.0 | 0.0 |
| dataset3_0_1200 | D3-norepair-core-chunk60 | 36 | 0.333 | 4.0 | 0.0 |
| dataset3_1200_2400 | B7-core | 36 | 0.383 | 7.6 | 0.0 |
| dataset3_1200_2400 | LATE-D0-core | 36 | 0.167 | 10.0 | 0.0 |
| dataset3_1200_2400 | LATE-D1-core-radius20 | 36 | 0.117 | 10.8 | 0.0 |
| dataset3_1200_2400 | LATE-D2-core-q30-smass-rhighest | 36 | 0.167 | 10.0 | 0.0 |
| dataset3_1200_2400 | LATE-D3-core-chunk60 | 36 | 0.133 | 10.4 | 0.0 |
| dataset3_1200_2400 | D3-norepair-core-chunk60 | 36 | 0.183 | 10.2 | 0.0 |
| dataset3_2400_3462 | B7-core | 32 | 0.333 | 6.0 | 0.0 |
| dataset3_2400_3462 | LATE-D0-core | 32 | 0.333 | 6.0 | 0.0 |
| dataset3_2400_3462 | LATE-D1-core-radius20 | 32 | 0.311 | 6.2 | 0.0 |
| dataset3_2400_3462 | LATE-D2-core-q30-smass-rhighest | 32 | 0.333 | 6.0 | 0.0 |
| dataset3_2400_3462 | LATE-D3-core-chunk60 | 32 | 0.111 | 8.0 | 0.0 |
| dataset3_2400_3462 | D3-norepair-core-chunk60 | 32 | 0.200 | 7.2 | 0.0 |

## Concrete examples

### B7-core success but LATE-D0 failure

- **event**: realcartest_event_0002 in realcartest_0_1570 (point_anchor, [260.5,260.7])
  - B7-core selected (core): [10.0,110.0], [730.0,750.0], [760.0,770.0], [1050.0,1090.0], [1110.0,1160.0]...
  - LATE-D0-core selected (core): [10.0,110.0], [500.0,510.0], [730.0,750.0], [1110.0,1160.0]
  - Reason: upstream_discovery_miss for LATE-D0-core (event not in candidate set).

### LATE-D1/D2/D3 success while LATE-D0 fails

- **event**: realcartest_event_0007 in realcartest_0_1570 (point_anchor, [700.0,700.7])
  - LATE-D1-core-radius20 selected (core): [10.0,90.0], [500.0,510.0], [530.0,540.0], [580.0,590.0], [740.0,750.0]...
  - LATE-D0-core selected (core): [10.0,110.0], [500.0,510.0], [730.0,750.0], [1110.0,1160.0]
  - Reason: alternative discovery policy found the event that D0's prior-ranked discovery missed.

### D3 assists but D1/D2 do not

- **event**: realcartest_event_0023 in realcartest_2000_3200 (point_anchor, [70.0,70.7])
  - LATE-D3-core-chunk60 selected (core): [30.0,60.0], [250.0,260.0], [830.0,880.0], [980.0,990.0]
  - LATE-D1-core-radius20 selected (core): [30.0,60.0], [90.0,100.0], [120.0,130.0], [380.0,410.0], [490.0,510.0]...
  - LATE-D2-core-q30-smass-rhighest selected (core): [850.0,890.0], [960.0,970.0], [980.0,990.0]
  - Reason: chunk-bandit exploration reached an event outside the high-prior regions that D1/D2 focused on.

### D1/D2 assist but D3 does not

- **event**: realcartest_event_0004 in realcartest_0_1570 (point_anchor, [500.0,500.7])
  - LATE-D1-core-radius20 selected (core): [10.0,90.0], [500.0,510.0], [530.0,540.0], [580.0,590.0], [740.0,750.0]...
  - LATE-D3-core-chunk60 selected (core): [10.0,110.0], [550.0,590.0], [1050.0,1090.0]
  - Reason: prior-guided policy found a high-prior event that the chunk-bandit did not sample.

### D3-core vs D3-norepair-core

**Example where repair helped (D3-core hits, D3-norepair misses):**
- **event**: realcartest_event_0014 in realcartest_0_1570 (long_interval, [1050.5,1080.7])
  - LATE-D3-core selected (core): [10.0,110.0], [550.0,590.0], [1050.0,1090.0]
  - D3-norepair-core selected (core): [730.0,750.0], [760.0,770.0], [1170.0,1200.0], [1210.0,1230.0]
  - Likely reason: audit-triggered repair expanded into this event's neighborhood.

**Example where repair did not help (D3-norepair hits, D3-core misses):**
- **event**: realcartest_event_0004 in realcartest_0_1570 (point_anchor, [500.0,500.7])
  - D3-norepair-core selected (core): [730.0,750.0], [760.0,770.0], [1170.0,1200.0], [1210.0,1230.0]
  - LATE-D3-core selected (core): [10.0,110.0], [550.0,590.0], [1050.0,1090.0]
  - Likely reason: repair consumed budget that could have gone to additional chunk-bandit discovery.


## How to read the casebook

- `core_hit_rate > 0` means the event was overlapped by at least one core interval in at least one seed.
- `candidate_hit_rate > 0` but `core_hit_rate = 0` means the event was found by discovery but discarded by the strict Core/Halo release (release_over_conservative).
- `candidate_hit_rate = 0` means the event was never selected by discovery (discovery_miss).
- Intervals shown are from seed 0 at the maximum <=30% budget ratio for that segment.
