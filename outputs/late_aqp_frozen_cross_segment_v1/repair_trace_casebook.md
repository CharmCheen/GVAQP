# Repair-Trace Casebook

Concrete examples of causal repair-trace events from `repair_trace_calls.csv`.

Overall counts: 184 repair_expansion calls; 184 triggered by outside-envelope positives; 48 of those produced positive duration overlap.

## Successful repair expansion

- **Call id**: `realcartest_2000_3200_ours_b40_t0_11`
- **Segment**: `realcartest_2000_3200`, budget=40, trial=0
- **Action**: repair_expansion
- **Unit**: `b77` at [770.0, 780.0]
- **Oracle label**: positive
- **Triggered by**: `realcartest_2000_3200_ours_b40_t0_9` (`b76`, label=positive)
- **Repair window**: [760, 770]
- **Overlap with event**: 0.700 s

## False repair expansion (no overlap)

- **Call id**: `realcartest_2000_3200_ours_b5_t3_1`
- **Segment**: `realcartest_2000_3200`, budget=5, trial=3
- **Action**: repair_expansion
- **Unit**: `b6` at [60.0, 70.0]
- **Oracle label**: negative
- **Triggered by**: `realcartest_2000_3200_ours_b5_t3_0` (`b7`, label=positive)
- **Repair window**: [70, 80]
- **Overlap with event**: 0.000 s

## Outside-envelope positive trigger

- **Call id**: `realcartest_2000_3200_ours_b5_t3_0`
- **Segment**: `realcartest_2000_3200`, budget=5, trial=3
- **Action**: audit_outside
- **Unit**: `b7` at [70.0, 80.0]
- **Oracle label**: positive
- **Hit event**: realcartest_event_0023 (point_anchor)
- **Overlap with event**: 0.700 s

## Initial-envelope discovery of long event

- **Call id**: `realcartest_2000_3200_ours_b5_t0_2`
- **Segment**: `realcartest_2000_3200`, budget=5, trial=0
- **Action**: discovery_initial_envelope
- **Unit**: `b88` at [880.0, 890.0]
- **Oracle label**: positive
- **Hit event**: realcartest_event_0037 (long_interval)
- **Overlap with event**: 0.700 s

## Interpretation
- Repair expansions are almost always triggered by an `audit_outside_positive` event, confirming the causal chain.
- Some repairs add units that do not overlap a reference event; these are false-positive duration that can dilute precision.
- The trace therefore supports the *existence* of the repair mechanism, but its empirical precision gain must be evaluated by the aggregate duration-precision tables.
