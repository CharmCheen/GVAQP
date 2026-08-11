# Selector × Materializer Interaction Audit

This secondary replay was frozen to 3 regimes × 2 policies × 3 budgets × 3 videos before results.  K0 and C1 consume identical traces; it does not retune C1 or rerun the full primary matrix.

| Proxy regime | Policy | Median ΔF1 (C1−C0) |
|---|---|---:|
| E3_EXPOSURE_SEVERE_KEEP040 | StaticProxyRank | 0.3323 |
| E3_EXPOSURE_SEVERE_KEEP040 | TemporalCoverage | 0.0951 |
| R0_ORIGINAL | StaticProxyRank | 0.3253 |
| R0_ORIGINAL | TemporalCoverage | 0.0750 |
| R3_RANK_SEVERE_HASH | StaticProxyRank | 0.1996 |
| R3_RANK_SEVERE_HASH | TemporalCoverage | 0.0750 |

- Cross-subgroup median range: `0.2573`.
- Videos with at least the frozen `0.05` subgroup range: `3 / 3`.
- Frozen decision: `SYSTEMATIC`.

An interaction here means the **size** of C1's correction depends on which sparse trace the proxy/policy creates; it does not mean either stage changes the other's implementation.  The reference remains full-grid K3-defined, so this is model-relative mechanism evidence.
