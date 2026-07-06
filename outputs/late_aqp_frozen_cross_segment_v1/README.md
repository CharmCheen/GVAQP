# Frozen Cross-Segment Validation + Repair Trace for LATE-AQP

## Goal
Freeze a single LATE-AQP configuration and validate whether the previously reported advantage over ExSample-style baselines holds on 2–3 unseen video segments, with causal repair-trace logging.

## Query predicate
`Visible Ego-Path Conflict (VEPC)` — oracle-relative, relative to existing VLM-oracle labels (`O_ref`).

## Frozen configuration (`frozen_config.yaml`)
- Audit schedule: `V3_two_phase`
- Repair utility: `U0_current`
- E0 threshold: `top20`
- Atomic bin size: `10 s`
- Budgets: `[5, 10, 20, 40, 80, 120]`
- Event split: `point_anchor` (< 1 s), `long_interval` (>= 1 s)
- Baselines:
  - B6 ExSample-style adaptive chunk sampling, `chunk_size = 120 s`
  - B7 ExSample + simple temporal expansion, `chunk_size = 120 s`, `k = 3`
  - Frozen-LATE-AQP-v1
- Random seed base: `20260705`
- Trials: 5 seeds (`[0,1,2,3,4]`)

## Segments
- `dev`: `realcartest_2000_3200` (the previous development segment, 120 bins, density ≈ 26.7 %)
- `unseen_low`: `realcartest_1630_2000` (37 bins, density ≈ 5.4 %, only point-anchor events)
- `unseen_medium`: `realcartest_3200_3830` (63 bins, density ≈ 20.6 %)
- `unseen_high`: `realcartest_0_1570` (157 bins, density ≈ 28.0 %)

## Data sources
- VLM-oracle reference events: `experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv`
- Dev reference events (for comparison): `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv`
- Prior scores for unseen segments: `experiments/roadclip_budget_v2/roadclip_budget_v2/proxy_scores.csv` (`score_count`)
- Dev prior scores: `outputs/exsample_aware_replay/atomic_grid_10s.csv` (recomputed from `cheap_signals_per_unit.csv`)
- Video manifest: `experiments/roadclip_budget_v2/roadclip_budget_v2/video_inventory.csv`

## Outputs
All required files are produced under this directory, including:
- `data_discovery_report.md`
- `segment_selection_report.md`
- `segment_density_report.csv`
- `repair_trace_logging_spec.md`
- `repair_trace_calls.csv`
- `repair_trace_selected_intervals.csv`
- `cross_segment_metrics.csv`
- `cross_segment_budget_curves.csv`
- `cross_segment_long_event_metrics.csv`
- `selected_duration_precision_report.csv`
- `generate_reports.py`
- `secondary_analysis.py`
- `per_budget_breakdown.csv`
- `repair_causal_chain.csv`
- `repair_trace_casebook.md`
- `pass_fail_criteria_report.md`
- `revised_claims_after_cross_segment.md`
- `FINAL_REPORT.md`

## How to reproduce
```bash
cd /qiuyeqing/llama_prl/G-ARC
python3 outputs/late_aqp_frozen_cross_segment_v1/run_frozen_cross_segment.py
python3 outputs/late_aqp_frozen_cross_segment_v1/generate_reports.py
python3 outputs/late_aqp_frozen_cross_segment_v1/secondary_analysis.py
```

See `commands.sh` for the exact command sequence.
