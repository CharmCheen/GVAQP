# Algorithm v3 Summary

## Oracle-relative LATE-AQP v3

**Query**: Visible Ego-Path Conflict (VEPC)
**Oracle**: VLM-oracle \( O_{\text{ref}} \) from `clean_interval_aqp_full_reference_v2_clean_no_leak`
**Input**: 10 s atomic bins with `prior_score_max`
**Output**: selected event intervals + oracle-relative mass estimates + leakage report

## Core algorithm

1. **Envelope discovery**: \( E_0 = \) top 20% bins by prior score.
2. **Audit**: sample inside and outside \( E_0 \) according to the active audit schedule.
3. **Leakage detection**: outside-positive samples flag candidate-envelope leakage.
4. **Repair**: expand one bin to each side of leakage seeds, ranked by active repair utility.
5. **Discovery**: fill remaining budget with highest-prior unqueried bins.

## Audit schedule v3

| schedule | description |
|----------|-------------|
| V2_static25 | 25% fixed audit fraction |
| V3_min_floor | small floor `max(2, num_strata)` |
| V3_budget_aware | `min(0.25, max(0.05, 1/sqrt(B)))` |
| V3_leakage_gated | expand audit only if leakage found |
| V3_two_phase | pilot audit then conditional second tranche |

## Repair utility v3

| utility | description |
|---------|-------------|
| U0_current | seed prior |
| U1_leakage_density | leakage rate * unqueried mass |
| U2_temporal_continuity | prior * neighbor positive density * continuity |
| U3_long_event_oriented | duration gain * boundary uncertainty |
| U4_precision_aware | U3 weighted by precision risk |

## Empirical highlights

- Long-event recall@20 best schedule: V3_two_phase (0.517)
- Long-event recall@40 best schedule: V3_leakage_gated (0.733)
- Precision@40 best schedule: V3_budget_aware (0.325)
- Selected duration@40 (all schedules): {'V2_static25': 400.0, 'V3_budget_aware': 400.0, 'V3_leakage_gated': 400.0, 'V3_min_floor': 400.0, 'V3_two_phase': 400.0}
- Long-event recall@40 best repair utility: U1_leakage_density (0.750)
- Precision@40 best repair utility: U0_current (0.325)

## Logging requirement

The next implementation must record per-selected-interval `source_action`, `trigger_sample_id`, and `repair_window_*` fields. Without this, causal claims about audit-triggered repair remain unsupported.
