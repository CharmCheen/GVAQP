# Post-Replay Diagnostic for ExSample-aware LATE-AQP (v1)

This directory contains a post-hoc diagnostic of the results produced in
`outputs/exsample_aware_replay/`.

## Goal

Determine whether the previous replay results actually support the claim that
LATE-AQP's repair mechanism contributes value beyond "ExSample + simple temporal
expansion" (B7). The diagnostic does **not** re-run any oracle, model, or
feature extraction; it only re-analyses existing labels, prior scores, and the
previously sampled intervals.

## Input

All inputs are read from:

```
outputs/exsample_aware_replay/
```

Key files:

- `data_discovery_report.md`
- `atomic_grid_10s.csv`
- `baseline_results.csv`
- `per_budget_metrics.csv`
- `per_method_selected_intervals.csv`
- `budget_accounting_audit.csv`
- `h1_h7_summary.md`
- `kill_criteria_report.md`
- `error_cases.md`
- `exhaustive_subset_status.md`

## Outputs

| File | Description |
|------|-------------|
| `postdiagnostic_report.md` | Main diagnostic findings |
| `h1_mass_accounting_recheck.csv` | Reconciliation of positive-mass definitions |
| `event_type_stratified_metrics.csv` | Point-anchor vs long-event metrics |
| `precision_duration_duplicate_metrics.csv` | Precision, duration, duplicate analysis |
| `parameter_stability_metrics.csv` | Parameter and seed variance |
| `budget40_case_study.md` | Case study of the strongest evidence point |
| `revised_h1_h7_summary.md` | H1–H7 re-assessment |
| `revised_kill_criteria_report.md` | Kill-criteria re-assessment |
| `next_experiment_recommendation.md` | Recommended next steps |

## How to reproduce

```bash
bash outputs/exsample_aware_replay_postdiagnostic_v1/commands.sh
```

## Important caveats

- Reference labels are VLM-oracle outputs, not human labels.
- 14 of 20 reference events are point-anchor events (<1s); with 10s bins,
  boundary-IoU metrics are structurally capped.
- Calibration metrics (H7) remain **unverified** because no exhaustive
  human-annotated window exists yet.
