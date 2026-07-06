# Upstream Event-Diverse Discovery Redesign for LATE-AQP (v2)

Evaluates D0/D1/D2/D3/D3-norepair discovery policies against B6-core/B7-core on realcartest and dataset3.

## Run

```bash
bash outputs/late_aqp_event_diverse_discovery_v1/commands.sh
```

## Key outputs

- `context_manifest.md` — Context assembly record.
- `discovery_policy_specs.md` — Formal definitions of D0-D3.
- `event_diverse_frontier_raw.csv` — Per-seed raw results.
- `unique_event_coverage.csv` — 9.1 unique event coverage.
- `discovery_miss_reduction.csv` — 9.2 discovery miss reduction.
- `precision_recall_under_budget_ratio.csv` — 9.3 low-budget P/R.
- `b90_90_comparison.csv` — 9.4 B_90/90 comparison.
- `segment_regime_analysis.csv` — 9.5 regime analysis.
- `machinery_overhead_report.csv` — 9.6 overhead report.
- `repair_marginal_value_report.md` — 9.7 repair marginal value.
- `failure_casebook.md` — Failure patterns.
- `FINAL_REPORT.md` — Summary conclusions.
