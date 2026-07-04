# Audit Schedule v3 Specification

All formulas below are pre-registered. Results are reported without post-hoc adjustment.

## Common simulation setup

- Atomic grid: 121 bins of 10 s each.
- Reference oracle \( O_{\text{ref}} \): VLM-oracle labels from `clean_interval_aqp_full_reference_v2_clean_no_leak`.
- Initial envelope \( E_0 \): top 20% bins by `prior_score_max`.
- Audit samples inside vs outside \( E_0 \) are weighted by prior score.
- Repair expands one bin to each side of an outside-positive seed, selected by the active repair utility.
- Discovery fills the remaining budget with the highest-prior unqueried bins.

## Variants

### V2_static25 (baseline)

```
audit_calls = round(B * 0.25)
```

This replicates the previous Ours-full static audit fraction.

### V3_min_floor

```
audit_calls = max(2, num_strata)
num_strata = 3  # inside E0, outside E0, boundary
```

Reserve only a small audit floor at low budgets; allocate the rest to discovery.

### V3_budget_aware

```
audit_fraction(B) = min(0.25, max(0.05, 1 / sqrt(B)))
audit_calls = round(B * audit_fraction(B))
```

Audit fraction decreases with budget because high-budget runs have enough discovery calls to find leakage empirically.

### V3_leakage_gated

```
initial_audit = max(2, ceil(B * 0.05))
cap = round(B * 0.25)
run initial_audit
if outside-positive found:
    extra = cap - initial_audit (leave >=1 call for discovery)
    run extra audit
else:
    stop auditing, use remaining budget for discovery
```

Spend more on audit only if leakage is detected.

### V3_two_phase

```
phase1 = min(ceil(B * 0.10), num_strata * 2)
run phase1
if outside-positive found:
    phase2 = up to cap = round(B * 0.25), weighted 70% outside / 30% inside
else:
    phase2 = 0, all remaining budget to discovery
```

## Event subsets

- `all`: all reference events.
- `point_anchor`: duration < 1 s.
- `long_interval`: duration >= 1 s.
- `duration_ge_2s`: duration >= 2 s.
- `duration_ge_5s`: duration >= 5 s.

## Metrics

- event-level recall
- long-event recall
- selected precision
- selected total duration
- false-positive duration
- positive duration overlap
- complete-event coverage
- boundary IoU@0.3 and @0.5
- repair-triggered hit count
- audit / discovery / repair calls used
- budget accounting error
