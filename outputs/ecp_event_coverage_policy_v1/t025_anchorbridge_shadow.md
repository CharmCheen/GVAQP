# T025 — AnchorBridge shadow validation (revised)

Per-reference-event formation analysis. For each reference event we measure: how many positive anchor bins it contains, the largest empty-bin gap between its positives (bridge cost), and the IoU achievable by (a) the current pipeline rule (merge only consecutive positives) vs (b) the convex hull of all its positives (upper bound after full discovery + bridging).

**Strict-replay compatible**: queryable grid + offline reference only; no event_id online; no VLM. Isolates formation gap from discovery gap.

## Segment summary

| segment | n_ref | already_formable | short_event_granularity_limited | long_event_formable_gap | proxy_zero_blocked | median_gap | proxy_zero_events |
|---|---|---|---|---|---|---|---|
| realcartest_0_1570 | 20 | 8 | 12 | 0 | 0 | 0 | 0 |
| realcartest_2000_3200 | 20 | 6 | 14 | 0 | 0 | 0 | 0 |
| realcartest_3200_3830 | 7 | 4 | 3 | 0 | 0 | 0 | 0 |
| dataset3_0_1200 | 6 | 1 | 5 | 0 | 5 | 0 | 6 |
| dataset3_1200_2400 | 12 | 2 | 10 | 0 | 8 | 0 | 10 |
| dataset3_2400_3462 | 9 | 3 | 6 | 0 | 2 | 0 | 4 |

## Per-event detail

| segment | event | ref_dur | n_pos | max_gap | proxy_zero_pos | consec_iou | hull_iou |
|---|---|---|---|---|---|---|---|
| realcartest_0_1570 | 0 | 90.7 | 10 | 0 | 0 | 0.907 | 0.907 |
| realcartest_0_1570 | 1 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_0_1570 | 2 | 0.2 | 1 | 0 | 0 | 0.020 | 0.020 |
| realcartest_0_1570 | 3 | 0.5 | 1 | 0 | 0 | 0.050 | 0.050 |
| realcartest_0_1570 | 4 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_0_1570 | 5 | 0.2 | 1 | 0 | 0 | 0.020 | 0.020 |
| realcartest_0_1570 | 6 | 30.7 | 4 | 0 | 0 | 0.768 | 0.768 |
| realcartest_0_1570 | 7 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_0_1570 | 8 | 10.7 | 2 | 0 | 0 | 0.535 | 0.535 |
| realcartest_0_1570 | 9 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_0_1570 | 10 | 10.7 | 2 | 0 | 0 | 0.535 | 0.535 |
| realcartest_0_1570 | 11 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_0_1570 | 12 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_0_1570 | 13 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_0_1570 | 14 | 30.2 | 4 | 0 | 0 | 0.755 | 0.755 |
| realcartest_0_1570 | 15 | 40.7 | 5 | 0 | 0 | 0.814 | 0.814 |
| realcartest_0_1570 | 16 | 20.7 | 3 | 0 | 0 | 0.690 | 0.690 |
| realcartest_0_1570 | 17 | 10.7 | 2 | 0 | 0 | 0.535 | 0.535 |
| realcartest_0_1570 | 18 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_0_1570 | 19 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 0 | 20.7 | 3 | 0 | 0 | 0.690 | 0.690 |
| realcartest_2000_3200 | 1 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 2 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 3 | 0.2 | 1 | 0 | 0 | 0.020 | 0.020 |
| realcartest_2000_3200 | 4 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 5 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 6 | 20.7 | 3 | 0 | 0 | 0.690 | 0.690 |
| realcartest_2000_3200 | 7 | 10.7 | 2 | 0 | 0 | 0.535 | 0.535 |
| realcartest_2000_3200 | 8 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 9 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 10 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 11 | 10.7 | 2 | 0 | 0 | 0.535 | 0.535 |
| realcartest_2000_3200 | 12 | 10.7 | 2 | 0 | 0 | 0.535 | 0.535 |
| realcartest_2000_3200 | 13 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 14 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 15 | 50.7 | 6 | 0 | 0 | 0.845 | 0.845 |
| realcartest_2000_3200 | 16 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 17 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 18 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_2000_3200 | 19 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_3200_3830 | 0 | 30.7 | 4 | 0 | 0 | 0.767 | 0.767 |
| realcartest_3200_3830 | 1 | 10.2 | 2 | 0 | 0 | 0.510 | 0.510 |
| realcartest_3200_3830 | 2 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_3200_3830 | 3 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| realcartest_3200_3830 | 4 | 10.7 | 2 | 0 | 0 | 0.535 | 0.535 |
| realcartest_3200_3830 | 5 | 10.7 | 2 | 0 | 0 | 0.535 | 0.535 |
| realcartest_3200_3830 | 6 | 0.2 | 1 | 0 | 0 | 0.020 | 0.020 |
| dataset3_0_1200 | 0 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_0_1200 | 1 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_0_1200 | 2 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_0_1200 | 3 | 10.7 | 2 | 0 | 2 | 0.535 | 0.535 |
| dataset3_0_1200 | 4 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_0_1200 | 5 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_1200_2400 | 0 | 10.7 | 2 | 0 | 2 | 0.535 | 0.535 |
| dataset3_1200_2400 | 1 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_1200_2400 | 2 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_1200_2400 | 3 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| dataset3_1200_2400 | 4 | 80.7 | 9 | 0 | 6 | 0.897 | 0.897 |
| dataset3_1200_2400 | 5 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_1200_2400 | 6 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_1200_2400 | 7 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_1200_2400 | 8 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_1200_2400 | 9 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_1200_2400 | 10 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| dataset3_1200_2400 | 11 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_2400_3462 | 0 | 10.7 | 2 | 0 | 0 | 0.535 | 0.535 |
| dataset3_2400_3462 | 1 | 10.7 | 2 | 0 | 1 | 0.535 | 0.535 |
| dataset3_2400_3462 | 2 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| dataset3_2400_3462 | 3 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_2400_3462 | 4 | 10.2 | 2 | 0 | 1 | 0.510 | 0.510 |
| dataset3_2400_3462 | 5 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| dataset3_2400_3462 | 6 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |
| dataset3_2400_3462 | 7 | 0.7 | 1 | 0 | 1 | 0.070 | 0.070 |
| dataset3_2400_3462 | 8 | 0.7 | 1 | 0 | 0 | 0.070 | 0.070 |

## Reading

- `already_formable`: events whose positives already sit in one contiguous run hitting IoU>=0.3 under the current rule (mostly ref_dur>=10.7s events). Once discovered, formation is fine.
- `short_event_granularity_limited`: events with ref_dur<20s whose best possible interval (convex hull of ALL its positives) still gives IoU<0.3. Their positives are ALREADY contiguous (max_internal_gap=0 everywhere), so AnchorBridge gap-bridging CANNOT help. The bottleneck is temporal resolution: the event is shorter than a 10s bin, so a bin-level interval structurally cannot reach IoU>=0.3. Only sub-bin boundary resolution (VLM/CERTIFY on the bin) can recover these — this is exactly ECP's CERTIFY / expand_boundary arm and the multi-fidelity cascade.
- `long_event_formable_gap`: events with ref_dur>=20s that still do not form well despite contiguous positives — rare here (boundary/semantic edge case).
- `proxy_zero_blocked`: events whose positives are all prior_score_max==0.0 AND not yet formable. These are the proxy-zero regime where DISCOVERY (not formation) is the blocker — confirming the RP shadow (0 bridge-positive hits on dataset3_0_1200).
**Headline**: across all 74 reference events, max_internal_gap=0 — positives within an event are already contiguous. So the ECP BRIDGE arm (gap-bridging) addresses a near-empty gap; the real formation levers are (a) sub-bin boundary resolution for the many short (<1s) events and (b) proxy-zero discovery for the dataset3 segments. This sharpens ECP: CERTIFY/expand_boundary + multi-fidelity cascade matter more than AnchorBridge gap-filling.