# Temporal Correlation and Refinement Audit

All event quantities are empirical structure relative to the frozen full-context Oracle pseudo-reference, not ground-truth event prevalence.

## Composite visible-trigger neighbor result

- `PSP_V0_SHORT` composite: P(new neighbor event | trigger)=0.1912, without trigger=0.0000, absolute gain=0.1912.
- `PSP_V1_LONG` composite: P(new neighbor event | trigger)=0.3030, without trigger=0.4000, absolute gain=-0.0970.

Component-wise preregistered trigger gates:

- `bbox_growth_signal`: STOP, pooled RR=1.6595744680851063.
- `candidate_trigger`: STOP, pooled RR=1.6595744680851063.
- `center_entry_signal`: STOP, pooled RR=1.1538891104906261.
- `composite_visible_trigger`: STOP, pooled RR=1.4345172031076583.
- `late_track_entry_signal`: STOP, pooled RR=1.8450226244343892.
- `lateral_motion_signal`: PASS, pooled RR=3.236111111111111.

```text
EFFECTIVE_OBSERVATION_REDUNDANCY_HORIZON = 8 units (80 s)
MAXIMUM_EMPIRICAL_REFINEMENT_RADIUS = 0 units (0 s)
FIXED_REFINEMENT_GATE = PASS
PASSING_TRIGGER_SET = lateral_motion_signal
```

Each component gate requires positive gain on both videos and pooled RR >= 1.25 (or an undefined ratio caused by a zero no-trigger base rate). Passing the association gate permits only fixed-baseline testing; it does not establish scheduling value.
