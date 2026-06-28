# UA-DETRAC Narrow Budget Search Report

Date: 2026-05-23

This is an engineering smoke/stress report using cached UA-DETRAC frame-level data and existing SUPG and frame-to-clip metric paths. It is not research-valid evidence, and YOLOv8x is treated only as a pseudo-oracle, not human ground truth.

## Inputs

- Source CSV: `garc_eval/outputs/uadetrac_temporal/supg_source.csv`
- Frame sequence cache: `garc_eval/outputs/uadetrac_temporal/frames.parquet`
- Dataset: UA-DETRAC controlled local subset
- Predicate: `count_car(frame) >= 25`
- Frames: `N = 13,932`
- Positives: `1,519`
- Positive rate: `10.90%`
- Gamma: `0.9`
- Delta: `0.05`
- Trials per budget: `10`

## Commands Run

Frame-level SUPG search:

```bash
source env_garc.sh
for budget in 300 350 400; do
  PYTHONPATH=. python -m garc_eval.experiments.run_supg_real_frames \
    --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv \
    --budget "$budget" \
    --gamma 0.9 \
    --delta 0.05 \
    --trials 10 \
    --outdir "garc_eval/outputs/uadetrac_temporal/budget_search/supg_budget_${budget}"
done
```

Clip-level evaluation:

```bash
source env_garc.sh
for spec in "300 0.7 0_7" "300 0.9 0_9" "350 0.7 0_7" "350 0.9 0_9" "400 0.7 0_7" "400 0.9 0_9"; do
  set -- $spec
  budget=$1
  iou=$2
  tag=$3
  PYTHONPATH=. python -m garc_eval.experiments.run_frame_clip_gap \
    --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv \
    --frames-parquet garc_eval/outputs/uadetrac_temporal/frames.parquet \
    --budget "$budget" \
    --gamma 0.9 \
    --delta 0.05 \
    --trials 10 \
    --iou-threshold "$iou" \
    --min-clip-frames 3 \
    --methods SUPG-RT SUPG-PT \
    --outdir "garc_eval/outputs/uadetrac_temporal/budget_search/clip_budget_${budget}_iou_${tag}"
done
```

## Frame-Level Results

| Budget | Method | Mean selected_n | Mean selected_n / N | Min selected_n | Max selected_n | Selected-all count | Precision mean | Recall mean | Failure rate |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 300 | SUPG-RT | 13,932.0 | 1.0000 | 13,932 | 13,932 | 10 / 10 | 0.1090 | 1.0000 | 0.0000 |
| 300 | SUPG-PT | 53.2 | 0.0038 | 43 | 65 | 0 / 10 | 1.0000 | 0.0350 | 0.0000 |
| 350 | SUPG-RT | 13,932.0 | 1.0000 | 13,932 | 13,932 | 10 / 10 | 0.1090 | 1.0000 | 0.0000 |
| 350 | SUPG-PT | 60.3 | 0.0043 | 52 | 70 | 0 / 10 | 1.0000 | 0.0397 | 0.0000 |
| 400 | SUPG-RT | 13,932.0 | 1.0000 | 13,932 | 13,932 | 10 / 10 | 0.1090 | 1.0000 | 0.0000 |
| 400 | SUPG-PT | 65.4 | 0.0047 | 57 | 72 | 0 / 10 | 1.0000 | 0.0431 | 0.0000 |

The requested lower-budget region did not produce a hard-but-not-vacuous SUPG-RT setting. All three SUPG-RT budgets selected every frame in all 10 trials.

## Clip-Level Results

### IoU Threshold 0.7

| Budget | Method | Clip recall coverage mean | Clip IoU recall mean | Clip precision mean | mIoU mean | Worst trial seed | Worst clip IoU recall | Worst mIoU |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 300 | SUPG-RT | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | 1.0000 |
| 300 | SUPG-PT | 0.0040 | 0.0000 | 1.0000 | 0.0025 | 0 | 0.0000 | 0.0048 |
| 350 | SUPG-RT | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | 1.0000 |
| 350 | SUPG-PT | 0.0024 | 0.0000 | 1.0000 | 0.0021 | 0 | 0.0000 | 0.0032 |
| 400 | SUPG-RT | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | 1.0000 |
| 400 | SUPG-PT | 0.0079 | 0.0000 | 1.0000 | 0.0045 | 0 | 0.0000 | 0.0027 |

### IoU Threshold 0.9

| Budget | Method | Clip recall coverage mean | Clip IoU recall mean | Clip precision mean | mIoU mean | Worst trial seed | Worst clip IoU recall | Worst mIoU |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 300 | SUPG-RT | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | 1.0000 |
| 300 | SUPG-PT | 0.0040 | 0.0000 | 1.0000 | 0.0025 | 0 | 0.0000 | 0.0048 |
| 350 | SUPG-RT | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | 1.0000 |
| 350 | SUPG-PT | 0.0024 | 0.0000 | 1.0000 | 0.0021 | 0 | 0.0000 | 0.0032 |
| 400 | SUPG-RT | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | 1.0000 |
| 400 | SUPG-PT | 0.0079 | 0.0000 | 1.0000 | 0.0045 | 0 | 0.0000 | 0.0027 |

## Best Hard-But-Not-Vacuous Setting

No tested budget among `300`, `350`, and `400` qualifies as hard-but-not-vacuous for SUPG-RT. Each budget selected all `13,932` frames in all `10 / 10` trials, so the apparent perfect clip metrics are vacuous.

Among previously tested settings, `budget=500` remains the closest lower-budget stress point, but it was still partly degenerate because SUPG-RT selected all frames in `5 / 10` trials. The earlier default `budget=1000` setting is clearly non-vacuous with selected-all count `0 / 20` and mean selected fraction about `58.4%`, but its clip-level metrics remain strong and it does not expose a harmful frame-to-clip gap.

## Frame-to-Clip Gap Assessment

No meaningful harmful SUPG-RT frame-to-clip gap was found in this budget search. For SUPG-RT, the lower-budget settings collapsed to selected-all behavior, producing perfect frame recall and perfect clip metrics by construction. For SUPG-PT, clip IoU recall was `0.0` at both IoU thresholds because the selected frames are extremely sparse; this is an expected high-precision / very-low-recall behavior, not a G-ARC-style boundary or merge failure.

## Recommendation

Do not proceed to 100-trial experiments from this setting. The next controlled experiment should search the transition between the fully vacuous and partly non-vacuous regimes with budgets `425`, `450`, and `475`, again using `10` trials and IoU thresholds `0.7` and `0.9`. If that still selects all in most trials, return to the non-vacuous `budget=1000` baseline and vary the predicate `K` or dataset difficulty rather than continuing to lower the budget.
