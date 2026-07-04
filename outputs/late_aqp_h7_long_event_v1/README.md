# H7 Calibration Prep + Long-Event-Only Replay for LATE-AQP (v1)

This directory contains two parallel deliverables:

1. **H7 calibration preparation**: search for an existing exhaustive human-annotated
   calibration window; if none exists, generate an annotation package and guide.
2. **Long-event-only replay**: re-analyse the previous replay outputs restricted to
   long-interval reference events, to isolate whether Ours-full's advantage is
   driven by temporal-structure repair rather than point-anchor seed discovery.

No new VLM/YOLO/GPU/API calls are made. Existing labels, prior scores, and replay
outputs are read but not modified.

## Inputs

- `outputs/exsample_aware_replay/`
- `outputs/exsample_aware_replay_postdiagnostic_v1/`
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv`
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/full_reference_units.csv`

## Outputs

| File | Description |
|------|-------------|
| `input_manifest.csv` | List of input files used |
| `h7_exhaustive_window_discovery.md` | Search results for existing exhaustive annotation windows |
| `h7_annotation_package_status.md` | Status of H7 annotation package |
| `h7_annotation_template.csv` | Template for exhaustive human annotation |
| `h7_annotation_guide.md` | Annotation instructions and quality rules |
| `long_event_only_replay_metrics.csv` | Long-event-only metrics by method/budget |
| `long_event_only_budget_curve.csv` | Budget-curve data for plotting |
| `long_event_only_case_studies.md` | Per-event case studies |
| `audit_calibration_plan.md` | Plan for computing calibration metrics after annotation |
| `next_supg_abae_baseline_spec.md` | Specification for future SUPG/ABae baselines |
| `FINAL_REPORT.md` | Consolidated findings and recommendation |

## Reproduce

```bash
bash outputs/late_aqp_h7_long_event_v1/commands.sh
```
