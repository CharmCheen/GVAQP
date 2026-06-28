# UA-DETRAC Boundary Stress Diagnosis

Generated: 2026-05-23

## Scope

This report runs a small controlled clip-level stress diagnosis using cached UA-DETRAC data and existing metric paths only. It does not modify algorithm code, download data, run YOLO materialization, run 100-trial experiments, or design a new G-ARC method.

This is engineering smoke evidence. It is not research-valid evidence because labels and clips are derived from the YOLOv8x pseudo-oracle; YOLOv8x is not human ground truth.

## Inputs

- Source CSV: `garc_eval/outputs/uadetrac_temporal/supg_source.csv`
- Frames parquet: `garc_eval/outputs/uadetrac_temporal/frames.parquet`
- Frame-level runner: `python -m garc_eval.experiments.run_supg_real_frames`
- Clip-level runner: `python -m garc_eval.experiments.run_frame_clip_gap`
- Metric implementation: `garc_eval/metrics/frame_to_clip.py`

Dataset:

- UA-DETRAC controlled local subset.
- Predicate: `count_car(frame) >= 25`.
- Frames `N`: `13,932`.
- Positive pseudo-oracle frames: `1,519`.
- Positive rate: `0.109030`.
- Pseudo-oracle clips: `126` with `min_clip_frames=3`, `gap_tolerance=0`.

## Exact Commands Run

Frame-level budget stress:

```bash
bash -lc 'source env_garc.sh && PYTHONPATH=. python -m garc_eval.experiments.run_supg_real_frames --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv --budget 500 --gamma 0.9 --delta 0.05 --trials 10 --outdir garc_eval/outputs/uadetrac_temporal/boundary_stress/supg_budget_500'

bash -lc 'source env_garc.sh && PYTHONPATH=. python -m garc_eval.experiments.run_supg_real_frames --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv --budget 250 --gamma 0.9 --delta 0.05 --trials 10 --outdir garc_eval/outputs/uadetrac_temporal/boundary_stress/supg_budget_250'
```

Clip-level budget and IoU stress:

```bash
bash -lc 'source env_garc.sh && PYTHONPATH=. python -m garc_eval.experiments.run_frame_clip_gap --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv --frames-parquet garc_eval/outputs/uadetrac_temporal/frames.parquet --budget 500 --gamma 0.9 --delta 0.05 --trials 10 --iou-threshold 0.5 --min-clip-frames 3 --methods SUPG-RT SUPG-PT --outdir garc_eval/outputs/uadetrac_temporal/boundary_stress/clip_budget_500_iou_0_5'

bash -lc 'source env_garc.sh && for spec in "500 0.7 0_7" "500 0.9 0_9" "250 0.5 0_5" "250 0.7 0_7" "250 0.9 0_9"; do set -- $spec; budget=$1; iou=$2; tag=$3; PYTHONPATH=. python -m garc_eval.experiments.run_frame_clip_gap --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv --frames-parquet garc_eval/outputs/uadetrac_temporal/frames.parquet --budget "$budget" --gamma 0.9 --delta 0.05 --trials 10 --iou-threshold "$iou" --min-clip-frames 3 --methods SUPG-RT SUPG-PT --outdir "garc_eval/outputs/uadetrac_temporal/boundary_stress/clip_budget_${budget}_iou_${tag}"; done'
```

Aggregation:

```bash
bash -lc 'source env_garc.sh && PYTHONPATH=. python - <<"PY" > /tmp/uadetrac_boundary_stress_summary.json
# Read boundary_stress summary.csv and per_trial_results.csv files,
# compute selected-all counts, selected fractions, worst seeds, and clip metrics.
PY'
```

## Stress Settings

- Budgets: `500`, `250`.
- Trials: `10` for each budget and clip metric setting.
- IoU thresholds: `0.5`, `0.7`, `0.9`.
- Methods evaluated by the clip runner: `SUPG-RT`, `SUPG-PT`.
- No 100-trial setting was run.

## Frame-Level SUPG-RT Budget Stress

| Budget | Mean selected_n | Mean selected_n / N | Min selected_n | Max selected_n | Selected-all count | Precision mean | Recall mean | Failure rate | Worst seed | Worst recall |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 500 | 11,283.5 | 0.809898 | 8,019 | 13,932 | 5 / 10 | 0.141601 | 0.994404 | 0.000000 | 5 | 0.972350 |
| 250 | 13,932.0 | 1.000000 | 13,932 | 13,932 | 10 / 10 | 0.109030 | 1.000000 | 0.000000 | 0 | 1.000000 |

Budget stress did not create an RT recall failure. Instead, reducing budget made SUPG-RT more conservative. At budget `250`, SUPG-RT selected all frames in every trial, which is vacuous for benchmarking.

## Clip-Level SUPG-RT Stress

| Budget | IoU threshold | Clip coverage recall | Clip IoU recall | Clip precision | mIoU | Worst seed | Worst frame recall | Worst clip IoU recall | Worst mIoU |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 500 | 0.5 | 1.000000 | 0.997619 | 1.000000 | 0.993662 | 5 | 0.972350 | 0.976190 | 0.964584 |
| 500 | 0.7 | 1.000000 | 0.988889 | 1.000000 | 0.993662 | 5 | 0.972350 | 0.944444 | 0.964584 |
| 500 | 0.9 | 1.000000 | 0.985714 | 1.000000 | 0.993662 | 5 | 0.972350 | 0.936508 | 0.964584 |
| 250 | 0.5 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0 | 1.000000 | 1.000000 | 1.000000 |
| 250 | 0.7 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0 | 1.000000 | 1.000000 | 1.000000 |
| 250 | 0.9 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0 | 1.000000 | 1.000000 | 1.000000 |

At budget `500`, stricter IoU thresholds reduce SUPG-RT IoU recall slightly, but the result remains strong. At budget `250`, metrics are perfect only because SUPG-RT selected all frames.

## Clip-Level SUPG-PT Stress

| Budget | IoU threshold | Frame recall | Clip coverage recall | Clip IoU recall | Clip precision | mIoU | Mean selected_n | Fully missed clips | Consecutive miss clips |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 500 | 0.5 | 0.057538 | 0.007937 | 0.003175 | 1.000000 | 0.006087 | 87.4 | 85.3 | 29.4 |
| 500 | 0.7 | 0.057538 | 0.007937 | 0.000000 | 1.000000 | 0.006087 | 87.4 | 85.3 | 29.4 |
| 500 | 0.9 | 0.057538 | 0.007937 | 0.000000 | 1.000000 | 0.006087 | 87.4 | 85.3 | 29.4 |
| 250 | 0.5 | 0.027650 | 0.003175 | 0.001587 | 1.000000 | 0.001158 | 42.0 | 102.7 | 18.5 |
| 250 | 0.7 | 0.027650 | 0.003175 | 0.000000 | 1.000000 | 0.001158 | 42.0 | 102.7 | 18.5 |
| 250 | 0.9 | 0.027650 | 0.003175 | 0.000000 | 1.000000 | 0.001158 | 42.0 | 102.7 | 18.5 |

SUPG-PT degrades sharply under lower budget, but this is expected from the sparse high-precision operating point. It is not an RT guarantee failure.

## Meaningful Frame-To-Clip Gap Check

A meaningful harmful RT frame-to-clip gap would look like high frame recall near target while clip IoU recall collapses, or many short clips disappearing despite apparently adequate frame recall.

This stress pass did **not** find that for SUPG-RT:

- Budget `500` worst RT seed has frame recall `0.972350`, clip coverage recall `1.000000`, and clip IoU recall `0.936508` even at IoU threshold `0.9`.
- Budget `500` has no fully missed pseudo-oracle clips on average.
- Budget `250` is not a useful gap case because SUPG-RT selected all frames in all trials.

Failure modes observed:

- Short clips missed: observed mainly for SUPG-PT, not SUPG-RT.
- Fragmentation: mild for SUPG-RT at budget `500` but not enough to create low clip recall.
- Boundary shift: visible only as stricter IoU recall decreases from `0.997619` at IoU `0.5` to `0.985714` at IoU `0.9` for budget `500`.
- Over-merge: no meaningful over-merge issue observed in these summary metrics.

## Research Opening Assessment

This stress experiment does **not** yet establish a strong G-ARC research opening on the current UA-DETRAC setting.

What it does show:

- UA-DETRAC remains a useful non-degenerate baseline when budget is `500` or `1000`.
- SUPG-RT can become vacuous when budget is too low (`250`) because the confidence interval forces selection of all frames.
- Stricter IoU thresholds create only mild RT clip degradation at budget `500`.
- SUPG-PT is a useful negative/sparse-selection contrast, but not a direct argument for G-ARC.

## Recommendation

Next experiment should be **harder UA-DETRAC setting with non-vacuous RT**, not 100-trial formalization and not method design.

Recommended next step:

1. Try an intermediate or lower-but-nonvacuous budget search, for example `budget=350` and `budget=400`, to find the boundary between non-vacuous RT and selected-all behavior.
2. Keep IoU thresholds `0.7` and `0.9`, since boundary shifts are only visible under stricter IoU.
3. Vary `min_clip_frames` after the budget boundary is identified, because current short clips make PT collapse easy but do not stress RT enough.
4. Do not change `K` yet; `K=25` gives a good positive rate and should remain the baseline setting.
5. Consider a harder dataset only if UA-DETRAC cannot produce non-vacuous RT clip failures without pathological selected-all behavior.
6. Do not run 100-trial experiments until the stress setting produces a real non-vacuous gap case.
7. Do not start G-ARC method design yet; this is still benchmark diagnosis.

## Reproducibility Files

- Frame stress budget 500: `garc_eval/outputs/uadetrac_temporal/boundary_stress/supg_budget_500/summary.csv`
- Frame stress budget 250: `garc_eval/outputs/uadetrac_temporal/boundary_stress/supg_budget_250/summary.csv`
- Clip stress outputs: `garc_eval/outputs/uadetrac_temporal/boundary_stress/clip_budget_*_iou_*/summary.csv`
- Aggregation scratch file: `/tmp/uadetrac_boundary_stress_summary.json`
