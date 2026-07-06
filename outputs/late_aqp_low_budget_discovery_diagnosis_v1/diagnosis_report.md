# Diagnosis Report — Why Discovery-Only v2 Still Loses to B6 at B=10/20

## Methodology

We reconstructed the per-call cumulative discovery curve for B6 (chunk-level Thompson sampling) and Frozen-LATE-AQP-v2 (top-prior-score discovery) on the three original failure segments, budgets 10 and 20, 5 seeds each. No new labels or oracle calls were used.

## Findings

### realcartest_0_1570

**B=10**: final v2 recall=0.125, B6 recall=0.150, gap=-0.025. starts behind.

**B=20**: final v2 recall=0.250, B6 recall=0.300, gap=-0.050. starts behind.

### realcartest_2000_3200

**B=10**: final v2 recall=0.333, B6 recall=0.267, gap=+0.067. falls behind at call 5 but recovers/overtakes by the final call.

**B=20**: final v2 recall=0.500, B6 recall=0.467, gap=+0.033. falls behind at call 5 but recovers/overtakes by the final call.

### realcartest_3200_3830

**B=10**: final v2 recall=0.250, B6 recall=0.450, gap=-0.200. falls behind at call 8 and stays behind.

**B=20**: final v2 recall=0.500, B6 recall=0.600, gap=-0.100. falls behind at call 8 and stays behind.

## Candidate-level observations (not fixes)

### v2 top-B selection: long-event duplication

For the bins v2 would select with budget B, this table shows the average number of *distinct* long events hit and the average duplication ratio (selected long bins / distinct long events - 1). A high duplication ratio means the prior ranking is putting multiple top calls on the same long event, which wastes low-budget samples.

| Segment | Budget | avg_unique_long_events | avg_long_bin_duplication |
|---------|--------|------------------------|--------------------------|
| realcartest_0_1570 | 10 | 1.00 | 8.00 |
| realcartest_0_1570 | 20 | 2.00 | 4.50 |
| realcartest_2000_3200 | 10 | 2.00 | 1.00 |
| realcartest_2000_3200 | 20 | 3.00 | 1.67 |
| realcartest_3200_3830 | 10 | 1.00 | 2.00 |
| realcartest_3200_3830 | 20 | 2.00 | 2.00 |

### Top-prior bins per segment

The first 10 bins v2 would pick (ranked by `prior_score_max`). If the very top bins are negative or all belong to the same event, the prior signal is poorly aligned with long events.

**realcartest_0_1570**

| rank | bin | t_start | t_end | prior_score | label | event_id | event_type |
|------|-----|---------|-------|-------------|-------|----------|------------|
| 1 | 0 | 0.0 | 10.0 | 1.000 | negative |  |  |
| 2 | 1 | 10.0 | 20.0 | 1.000 | positive | realcartest_event_0000 | long_interval |
| 3 | 2 | 20.0 | 30.0 | 1.000 | positive | realcartest_event_0000 | long_interval |
| 4 | 3 | 30.0 | 40.0 | 1.000 | positive | realcartest_event_0000 | long_interval |
| 5 | 5 | 50.0 | 60.0 | 1.000 | positive | realcartest_event_0000 | long_interval |
| 6 | 9 | 90.0 | 100.0 | 1.000 | positive | realcartest_event_0000 | long_interval |
| 7 | 6 | 60.0 | 70.0 | 1.000 | positive | realcartest_event_0000 | long_interval |
| 8 | 7 | 70.0 | 80.0 | 1.000 | positive | realcartest_event_0000 | long_interval |
| 9 | 8 | 80.0 | 90.0 | 1.000 | positive | realcartest_event_0000 | long_interval |
| 10 | 10 | 100.0 | 110.0 | 1.000 | positive | realcartest_event_0000 | long_interval |

**realcartest_2000_3200**

| rank | bin | t_start | t_end | prior_score | label | event_id | event_type |
|------|-----|---------|-------|-------------|-------|----------|------------|
| 1 | 105 | 1050.0 | 1060.0 | 0.521 | negative |  |  |
| 2 | 88 | 880.0 | 890.0 | 0.515 | positive | realcartest_event_0037 | long_interval |
| 3 | 87 | 870.0 | 880.0 | 0.497 | positive | realcartest_event_0037 | long_interval |
| 4 | 102 | 1020.0 | 1030.0 | 0.482 | negative |  |  |
| 5 | 86 | 860.0 | 870.0 | 0.480 | positive | realcartest_event_0037 | long_interval |
| 6 | 93 | 930.0 | 940.0 | 0.475 | negative |  |  |
| 7 | 49 | 490.0 | 500.0 | 0.474 | positive | realcartest_event_0029 | long_interval |
| 8 | 81 | 810.0 | 820.0 | 0.472 | positive | realcartest_event_0036 | point_anchor |
| 9 | 51 | 510.0 | 520.0 | 0.469 | negative |  |  |
| 10 | 36 | 360.0 | 370.0 | 0.469 | negative |  |  |

**realcartest_3200_3830**

| rank | bin | t_start | t_end | prior_score | label | event_id | event_type |
|------|-----|---------|-------|-------------|-------|----------|------------|
| 1 | 1 | 10.0 | 20.0 | 1.000 | positive | realcartest_event_0042 | long_interval |
| 2 | 2 | 20.0 | 30.0 | 1.000 | positive | realcartest_event_0042 | long_interval |
| 3 | 3 | 30.0 | 40.0 | 1.000 | positive | realcartest_event_0042 | long_interval |
| 4 | 5 | 50.0 | 60.0 | 1.000 | negative |  |  |
| 5 | 4 | 40.0 | 50.0 | 1.000 | negative |  |  |
| 6 | 6 | 60.0 | 70.0 | 1.000 | negative |  |  |
| 7 | 7 | 70.0 | 80.0 | 1.000 | negative |  |  |
| 8 | 29 | 290.0 | 300.0 | 1.000 | negative |  |  |
| 9 | 24 | 240.0 | 250.0 | 1.000 | negative |  |  |
| 10 | 25 | 250.0 | 260.0 | 1.000 | negative |  |  |

## Interpretation

- **Call-1 lag** (`realcartest_0_1570`): the highest-prior bin is not on a long event, so v2's very first sample is wasted compared to B6's chunk draw.
- **Mid-run lag with recovery** (`realcartest_2000_3200`): v2 temporarily falls behind around call 5 but its top-prior bins eventually hit enough long events to catch up. The lag is due to exploration inefficiency, not a bad first call.
- **Mid-run lag without recovery** (`realcartest_3200_3830`): v2's top-prior bins hit a long event early (call 1) but then stay on that event or pick low-value bins, while B6 keeps discovering new long events across chunks. This is a diversity/exploration problem.

In all three segments, the root cause is that **static prior-score ranking is not diversity-aware**: it can spend multiple low-budget calls on the same high-scoring event or region, whereas B6's chunk-level Thompson sampling spreads calls across chunks and adapts to where new events appear.

## Suggested directions for a real fix (not implemented)

1. **Diversity-aware discovery**: after selecting a bin, down-weight or skip other bins that hit the same event, so each call targets a distinct long event.
2. **Event-level Thompson sampling**: maintain a per-event discovery counter and sample chunks proportionally to the upper confidence bound of undiscovered long events.
3. **Hybrid cold-start policy**: keep low-budget discovery but seed it with B6-style chunk sampling for the first few calls, then switch to prior-ranking once enough event coverage is established.
4. **Re-evaluate prior signal calibration**: if the top-prior bins are repeatedly not long events, the roadclip score_count may need recalibration (out of scope for this no-new-data task).
