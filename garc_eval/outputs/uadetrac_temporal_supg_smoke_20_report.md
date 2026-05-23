# UA-DETRAC SUPG 20-Trial Smoke Follow-Up

Generated: 2026-05-23

## Scope

This report summarizes a 20-trial frame-level SUPG smoke run on the UA-DETRAC controlled local subset. This is engineering smoke evidence only, not research-valid evidence. Labels are derived from the YOLOv8x pseudo-oracle and must not be described as human ground truth.

## Exact Command Used

The requested output directory was not present when checked, so the cached-source 20-trial smoke was run with:

```bash
bash -lc 'source env_garc.sh && PYTHONPATH=. python -m garc_eval.experiments.run_supg_real_frames --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv --budget 1000 --gamma 0.9 --delta 0.05 --trials 20 --outdir garc_eval/outputs/uadetrac_temporal/supg_smoke_20'
```

This command used the existing `supg_source.csv`; it did not download data, run YOLO materialization, or run a 100-trial formal experiment.

## Dataset and Predicate

- Dataset: UA-DETRAC controlled local subset.
- Source CSV: `garc_eval/outputs/uadetrac_temporal/supg_source.csv`.
- Output directory: `garc_eval/outputs/uadetrac_temporal/supg_smoke_20`.
- Predicate: `count_car(frame) >= 25`.
- Frames `N`: `13,932`.
- Positive count: `1,519`.
- Positive rate: `0.109030`.
- Proxy: YOLOv8n.
- Pseudo-oracle: YOLOv8x, not human ground truth.

## SUPG-RT 20-Trial Summary

| Metric | Value |
|---|---:|
| Trials | 20 |
| Budget | 1,000 |
| Gamma | 0.9 |
| Delta | 0.05 |
| Mean selected_n | 8,134.6 |
| Mean selected_n / N | 0.583879 |
| Min selected_n | 7,003 |
| Max selected_n | 8,900 |
| Precision mean | 0.181777 |
| Recall mean | 0.971461 |
| Failure rate | 0.050000 |
| Error count | 0 |
| Selected-all trials | 0 / 20 |

Selected-all did not occur. The maximum SUPG-RT selected set was `8,900 / 13,932 = 0.638817`, well below selecting all frames.

## SUPG-PT 20-Trial Summary

| Metric | Value |
|---|---:|
| Trials | 20 |
| Mean selected_n | 167.15 |
| Mean selected_n / N | 0.011998 |
| Min selected_n | 150 |
| Max selected_n | 187 |
| Precision mean | 1.000000 |
| Recall mean | 0.110039 |
| Failure rate | 0.000000 |
| Error count | 0 |
| Selected-all trials | 0 / 20 |

SUPG-PT remains a high-precision / low-recall operating point on this pseudo-oracle label set.

## Comparison With 5-Trial Smoke

| Method | Metric | 5-Trial | 20-Trial | Direction |
|---|---|---:|---:|---|
| SUPG-RT | Mean selected_n | 8,391.8 | 8,134.6 | lower |
| SUPG-RT | Mean selected_n / N | 0.602340 | 0.583879 | lower |
| SUPG-RT | Precision mean | 0.178195 | 0.181777 | slightly higher |
| SUPG-RT | Recall mean | 0.983410 | 0.971461 | slightly lower |
| SUPG-RT | Failure rate | 0.000000 | 0.050000 | higher |
| SUPG-PT | Mean selected_n | 168.6 | 167.15 | similar |
| SUPG-PT | Mean selected_n / N | 0.012102 | 0.011998 | similar |
| SUPG-PT | Precision mean | 1.000000 | 1.000000 | unchanged |
| SUPG-PT | Recall mean | 0.110994 | 0.110039 | similar |
| SUPG-PT | Failure rate | 0.000000 | 0.000000 | unchanged |

The 20-trial run confirms the 5-trial smoke finding that SUPG-RT is non-vacuous and does not select all frames. The expanded run adds one important caution: SUPG-RT failure rate is `0.05` over 20 trials, so the result is still smoke evidence and should not be overinterpreted as a formal guarantee evaluation.

## Non-Vacuity Assessment

SUPG-RT remains non-vacuous:

- Mean selected fraction: `0.583879 < 0.95`.
- Max selected fraction: `8,900 / 13,932 = 0.638817 < 0.95`.
- Selected-all trials: `0 / 20`.

This remains a valid engineering smoke benchmark for non-degenerate frame-level approximate selection.

## Recommendation

- Proceed to clip-level 20-trial metrics: **yes**, using the same cached UA-DETRAC source and frames parquet, because SUPG-RT remains non-vacuous and SUPG-PT remains stable.
- Proceed to 100-trial formal experiments now: **no**. The 20-trial run is still engineering smoke, uses YOLOv8x pseudo-oracle labels, and shows a nonzero SUPG-RT failure rate.
- Stop and inspect anomalies: **not required before clip-level 20-trial smoke**, but the `0.05` SUPG-RT failure rate should be documented and revisited before any formal experiment.

Suggested next command for clip-level 20-trial smoke:

```bash
source env_garc.sh && PYTHONPATH=. python -m garc_eval.experiments.run_frame_clip_gap --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv --frames-parquet garc_eval/outputs/uadetrac_temporal/frames.parquet --budget 1000 --gamma 0.9 --delta 0.05 --trials 20 --iou-threshold 0.5 --min-clip-frames 3 --methods SUPG-RT SUPG-PT --outdir garc_eval/outputs/uadetrac_temporal/clip_smoke_20
```

## Reproducibility Files

- 20-trial summary: `garc_eval/outputs/uadetrac_temporal/supg_smoke_20/summary.csv`
- 20-trial per-trial results: `garc_eval/outputs/uadetrac_temporal/supg_smoke_20/per_trial_results.csv`
- Previous 5-trial report: `garc_eval/outputs/nondegenerate_benchmark_smoke.md`
