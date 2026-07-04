# Video Signal Quality Audit v1 Final Report

Date: 2026-07-03

## Scope

This audit reads generated cheap-score tables and A0 runtime candidates only. It runs no VLM and reads no oracle/probe labels.

## Split Conclusions

- Pipeline execution success: `GO`.
- Prior signal non-degenerate: `WEAK GO`.
- Time-axis coverage: `GO`.

## A0 Baseline Archive

- A0 baseline: `score_topk + temporal NMS + duration cap`, no CILS, no oracle confirmation.
- Budget: `40` candidate clips.
- NMS gap: `20.0` seconds.
- Budget/gap source: carried over from `default_selector_score_sweep_v1` / `query_runtime_v1` dev operating point; not a fairness-tuned CILS comparison setting.

## Score Quality

| Score | Unique Values | Top Tie Fraction | Zero Fraction | Status |
|---|---:|---:|---:|---|
| `yolo_vehicle_max` | 18 | 0.141 | 0.017 | PASS |
| `motion_energy_max` | 347 | 0.003 | 0.000 | PASS |
| `score_fusion_yolo_motion` | 347 | 0.003 | 0.000 | PASS |
| `bbox_area_sum_max` | 346 | 0.006 | 0.000 | PASS |
| `center_roi_vehicle_count_mean` | 3 | 0.994 | 0.994 | WARN |

## Time-Axis Coverage

- Coarse 5s grid: `693` rows, gap_count `0`, max_gap_seconds `0.000000`.
- Center10 grid: `347` rows, gap_count `0`, max_gap_seconds `0.000000`.

## A0 Candidate Time Distribution

- Candidate count: `40`.
- Selected time span: `0.000` to `3440.000` seconds.
- Top 10min bucket fraction: `0.250000`.
- Distribution status: `PASS`.

## Figures

- `figures/yolo_vehicle_max_histogram.svg`
- `figures/motion_energy_max_histogram.svg`
- `figures/score_fusion_yolo_motion_histogram.svg`
- `figures/a0_candidate_time_distribution.svg`

## Files

- `tables/score_quality_summary.csv`
- `tables/score_histograms.csv`
- `tables/time_axis_coverage.csv`
- `tables/a0_candidate_time_buckets.csv`
- `tables/a0_candidate_distribution_summary.csv`

FINAL_DECISION: WEAK GO
