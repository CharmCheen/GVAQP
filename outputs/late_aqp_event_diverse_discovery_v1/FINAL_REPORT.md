# FINAL REPORT — Upstream Event-Diverse Discovery Redesign for LATE-AQP

## 1. Which discovery policy improves current LATE-D0?

- LATE-D1-core-radius20 (D1 best): lower B_90/90 than D0 on 2/6 segments
- LATE-D2-core-q20-smass-rhighest (D2 best): lower B_90/90 than D0 on 1/6 segments
- LATE-D3-core-chunk120 (D3 best): lower B_90/90 than D0 on 1/6 segments
- D3-norepair-core-chunk120 (D3-norepair best): lower B_90/90 than D0 on 3/6 segments

## 2. Did D1/D2/D3 reduce duplicate sampling?

Mean duplicate_sampling_rate by method (lower is better):

- D3-norepair-core-chunk120: 0.760
- B6-core: 0.767
- D3-norepair-core-chunk30: 0.845
- B7-core: 0.873
- LATE-D2-core-q50-smax-rhighest: 0.873
- LATE-D2-core-q50-smass-rcenter: 0.918
- D3-norepair-core-chunk60: 0.925
- LATE-D2-core-q20-smass-rhighest: 0.931
- LATE-D2-core-q50-smass-rhighest: 0.936
- LATE-D2-core-q50-smax-rcenter: 0.981
- LATE-D1-core-radius30: 0.985
- LATE-D2-core-q20-smax-rhighest: 0.991
- LATE-D2-core-q30-smass-rhighest: 0.996
- LATE-D2-core-q20-smass-rcenter: 1.002
- LATE-D2-core-q30-smax-rhighest: 1.003
- LATE-D2-core-q20-smax-rcenter: 1.010
- LATE-D2-core-q30-smax-rcenter: 1.016
- LATE-D2-core-q30-smass-rcenter: 1.018
- LATE-D1-core-radius20: 1.053
- LATE-D3-core-chunk30: 1.054
- LATE-D3-core-chunk60: 1.106
- LATE-D3-core-chunk120: 1.186
- LATE-D1-core-radius10: 1.219
- LATE-D0-core: 1.356

## 3. Did D1/D2/D3 reduce discovery_miss?

- realcartest_0_1570: D0 missed 19.2; best alternative LATE-D1-core-radius20 missed 8.8 @ ratio=0.299
- realcartest_2000_3200: D0 missed 19.0; best alternative LATE-D1-core-radius20 missed 9.4 @ ratio=0.300
- realcartest_3200_3830: D0 missed 6.0; best alternative LATE-D1-core-radius20 missed 4.2 @ ratio=0.159
- dataset3_0_1200: D0 missed 6.0; best alternative B7-core missed 3.8 @ ratio=0.300
- dataset3_1200_2400: D0 missed 12.0; best alternative B7-core missed 7.6 @ ratio=0.300
- dataset3_2400_3462: D0 missed 8.2; best alternative B7-core missed 6.0 @ ratio=0.299

## 4. Did any LATE variant beat B7-core in B_90/90?

- No LATE variant achieved a strictly lower B_90/90 than B7-core on any segment.

## 5. Did any method reach 90/90 at <=30% budget?

No.

Closest methods by segment (best recall under P>=0.9 within <=30% budget):

- realcartest_0_1570: LATE-D1-core-radius10 R=0.590
- realcartest_2000_3200: LATE-D1-core-radius20 R=0.540
- realcartest_3200_3830: LATE-D2-core-q20-smass-rcenter R=0.600
- dataset3_0_1200: B7-core R=0.367
- dataset3_1200_2400: LATE-D1-core-radius30 R=0.417
- dataset3_2400_3462: LATE-D2-core-q50-smass-rhighest R=0.400

## 6. Is the bottleneck still upstream discovery?

Mean discovery_miss_count at <=30% budget by method:

- LATE-D1-core-radius20: 10.19
- LATE-D1-core-radius30: 10.21
- LATE-D1-core-radius10: 10.27
- LATE-D2-core-q30-smass-rcenter: 10.59
- LATE-D2-core-q20-smass-rcenter: 10.64
- LATE-D2-core-q30-smax-rcenter: 10.74
- LATE-D2-core-q20-smax-rcenter: 10.76
- LATE-D2-core-q50-smass-rcenter: 10.76
- LATE-D2-core-q50-smax-rcenter: 10.93
- LATE-D2-core-q30-smax-rhighest: 11.02
- LATE-D2-core-q50-smass-rhighest: 11.03
- LATE-D2-core-q30-smass-rhighest: 11.05
- LATE-D2-core-q50-smax-rhighest: 11.06
- LATE-D2-core-q20-smass-rhighest: 11.06
- LATE-D3-core-chunk120: 11.26
- LATE-D2-core-q20-smax-rhighest: 11.27
- LATE-D3-core-chunk60: 11.29
- LATE-D0-core: 11.36
- LATE-D3-core-chunk30: 11.47
- B7-core: 11.56
- B6-core: 11.58
- D3-norepair-core-chunk120: 11.71
- D3-norepair-core-chunk30: 11.71
- D3-norepair-core-chunk60: 11.89

High discovery miss counts at low budgets indicate the bottleneck remains upstream discovery.

## 7. Does repair have independent marginal value on the strongest discovery backbone (D3)?

Aggregated per segment as best unique events / best long-event recall across all evaluated budgets, then averaged across segments (uses summary metrics `num_unique_events_hit` and `long_event_recall`).

Average repair marginal contribution (D3-core minus D3-norepair-core):

- chunk=30.0s: delta_unique_events=-0.500, delta_long_recall=+0.000
- chunk=60.0s: delta_unique_events=+0.000, delta_long_recall=+0.000
- chunk=120.0s: delta_unique_events=-0.167, delta_long_recall=+0.000

Repair shows no clear positive marginal contribution on either unique events or long-event recall.
Repair is associated with fewer unique events on 2/3 chunk configurations, suggesting audit/repair budget may displace discovery calls.

## 8. Does machinery overhead cover its gains?

Mean oracle-call fractions by method (guard + repair + discovery + audit = 1.0 within rounding):

- D3-norepair-core-chunk120: guard=0.134, repair=0.000, discovery=0.866
- D3-norepair-core-chunk30: guard=0.180, repair=0.000, discovery=0.820
- D3-norepair-core-chunk60: guard=0.153, repair=0.000, discovery=0.847
- LATE-D0-core: guard=0.252, repair=0.040, discovery=0.542
- LATE-D1-core-radius10: guard=0.376, repair=0.036, discovery=0.420
- LATE-D1-core-radius20: guard=0.340, repair=0.035, discovery=0.458
- LATE-D1-core-radius30: guard=0.335, repair=0.036, discovery=0.464
- LATE-D2-core-q20-smass-rcenter: guard=0.322, repair=0.031, discovery=0.481
- LATE-D2-core-q20-smass-rhighest: guard=0.290, repair=0.037, discovery=0.503
- LATE-D2-core-q20-smax-rcenter: guard=0.293, repair=0.040, discovery=0.498
- LATE-D2-core-q20-smax-rhighest: guard=0.267, repair=0.038, discovery=0.523
- LATE-D2-core-q30-smass-rcenter: guard=0.321, repair=0.033, discovery=0.487
- LATE-D2-core-q30-smass-rhighest: guard=0.286, repair=0.033, discovery=0.515
- LATE-D2-core-q30-smax-rcenter: guard=0.299, repair=0.038, discovery=0.497
- LATE-D2-core-q30-smax-rhighest: guard=0.292, repair=0.031, discovery=0.506
- LATE-D2-core-q50-smass-rcenter: guard=0.315, repair=0.034, discovery=0.490
- LATE-D2-core-q50-smass-rhighest: guard=0.296, repair=0.032, discovery=0.498
- LATE-D2-core-q50-smax-rcenter: guard=0.299, repair=0.029, discovery=0.507
- LATE-D2-core-q50-smax-rhighest: guard=0.274, repair=0.038, discovery=0.520
- LATE-D3-core-chunk120: guard=0.250, repair=0.033, discovery=0.543
- LATE-D3-core-chunk30: guard=0.256, repair=0.033, discovery=0.539
- LATE-D3-core-chunk60: guard=0.264, repair=0.038, discovery=0.529

### Overhead-vs-gain assessment

- B6-core and B7-core have no guard/repair overhead; their B_90/90 and low-budget recall set the baseline.
- LATE-D1-core-radius20 reduces discovery miss relative to D0 (section 3) but pays ~34-38% guard+repair overhead.
  It does not, however, achieve a lower B_90/90 than B7-core on any segment, so the overhead is not buying a winning frontier position.
- LATE-D2-core variants pay ~27-35% guard+repair overhead and reach 90/90 on more segments than D0, but still do not beat B7-core's B_90/90.
- LATE-D3-core pays ~25-30% guard+repair overhead; D3-norepair-core avoids repair overhead entirely and ties or beats LATE-D3-core on B_90/90 (`repair_marginal_value_report.md`).
- Because no LATE variant beats B7-core and repair's marginal unique-event contribution is non-positive (section 7), the guard+repair machinery is currently a net drag relative to the performance baseline.

**Conclusion**: The additional guard/repair overhead of the LATE variants is not covered by corresponding B_90/90 or low-budget recall gains against B7-core.

## 9. Recommended next step

D. None of the new discovery policies consistently beat B7-core; B7-core remains stronger. The performance advantage route is not established.
E. Consider pivoting to audit/estimator contributions rather than performance advantage.
