# Repair Utility v3 Specification

All utility formulas are pre-registered. Repair actions are ranked by utility and executed until the repair budget is exhausted.

## Common setup

- Outside-positive seeds come from audit outside the initial \( E_0 \) envelope.
- Each candidate repair action is one unqueried neighbor bin of a seed.
- `expected_cost = 1` oracle call per bin.

## Variants

### U0_current

```
utility = seed_prior_score
```

Baseline: expand around the highest-prior outside positives first.

### U1_leakage_density

```
outside_leakage_rate = (# positive outside audits) / (# outside audits)
utility = outside_leakage_rate * local_unqueried_duration / expected_cost
```

Favor regions with empirically high leakage and still-unqueried mass.

### U2_temporal_continuity

```
neighbor_positive_density = count of observed positive neighbors
continuity_score = seed_prior * (1 + neighbor_positive_density)
utility = seed_prior * neighbor_positive_density * continuity_score / expected_cost
```

Favor seeds whose neighbors already look positive, encouraging contiguous repairs.

### U3_long_event_oriented

```
estimated_uncovered_event_duration_gain = min(3.0, 1.0 + |seed_prior - neighbor_prior|)
boundary_uncertainty = neighbor_prior
utility = estimated_uncovered_event_duration_gain * boundary_uncertainty / expected_cost
```

Targets bins that may extend an event boundary and have non-trivial prior.

### U4_precision_aware

```
precision_risk_penalty = neighbor_prior / seed_prior
utility = U3 * precision_risk_penalty
```

Down-weight neighbors whose prior is much lower than the seed, reducing precision risk.

## Metrics

Same as audit-schedule experiments, with emphasis on `long_interval` recall and precision.
