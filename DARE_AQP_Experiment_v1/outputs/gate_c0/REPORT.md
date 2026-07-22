# Gate C0 hierarchical block-oracle ceiling

**Decision: `CONDITIONAL_C0_ONLY`.**

## Observed ceiling evidence

- Population: 347 units, 26 canonical anchors.
- Primary exact count-guided plan (80% recall, COUNT cost x1.25): 85 interval calls and 21 certifications.
- Constant-cost ratio: 0.367 of dense complete audit.
- Linear-duration-cost ratio: 4.495 of dense complete audit.
- Minimum fixed-cost fraction on the registered 0.05 grid needed to beat 70% dense: 0.95.
- Continuous break-even requires fixed-cost fraction strictly above 0.919267.
- Frozen unit-order distinct events at B=100 (strict traces): B0_uniform_random=9.4, B5_ARC_native=7.2, M1_MAP_anchor_only=11.0.

## Conclusion

The ceiling is useful only when interval calls are dominated by fixed overhead. Do not launch a broad VLM experiment; first measure 10s/30s/60s/120s latency and accuracy on a small stratified operator-contract pilot.

This result does not establish that a real block VLM is exact or has the required cost curve. `count_root_oracle_any_ceiling` is evaluator-informed and diagnostic only.

Authoritative tables: `break_even.csv`, `cost_curves.csv`, `query_traces.csv`, `unit_order_comparators.csv`, and `unit_audit_zero_hit_lower_bound.csv`.
