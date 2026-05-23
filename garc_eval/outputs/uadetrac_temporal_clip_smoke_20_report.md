# UA-DETRAC Clip-Level 20-Trial Smoke Follow-Up

Generated: 2026-05-23

## Scope

This report summarizes 20-trial clip-level metrics for the UA-DETRAC controlled local subset using the existing frame-to-clip path: `garc_eval/experiments/run_frame_clip_gap.py` and `garc_eval/metrics/frame_to_clip.py`.

This is engineering smoke evidence only. It is not research-valid evidence because labels and clips are derived from the YOLOv8x pseudo-oracle; YOLOv8x is not human ground truth.

## Exact Command Used

`clip_smoke_20` was not present before this run. The existing cached-source frame-to-clip command was run:

```bash
bash -lc 'source env_garc.sh && PYTHONPATH=. python -m garc_eval.experiments.run_frame_clip_gap --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv --frames-parquet garc_eval/outputs/uadetrac_temporal/frames.parquet --budget 1000 --gamma 0.9 --delta 0.05 --trials 20 --iou-threshold 0.5 --min-clip-frames 3 --methods SUPG-RT SUPG-PT --outdir garc_eval/outputs/uadetrac_temporal/clip_smoke_20'
```

This reused cached `supg_source.csv` and `frames.parquet`. It did not download data, run YOLO materialization, run a 100-trial experiment, or modify algorithm code.

## Dataset

- Dataset: UA-DETRAC controlled local subset.
- Source CSV: `garc_eval/outputs/uadetrac_temporal/supg_source.csv`.
- Frames parquet: `garc_eval/outputs/uadetrac_temporal/frames.parquet`.
- Output directory: `garc_eval/outputs/uadetrac_temporal/clip_smoke_20`.
- Predicate: `count_car(frame) >= 25`.
- Frames `N`: `13,932`.
- Positive frames: `1,519`.
- Positive rate: `0.109030`.
- Pseudo-oracle clips: `126`.
- Clip construction: contiguous pseudo-oracle-positive frame runs with `min_clip_frames=3`, `gap_tolerance=0`.
- Pseudo-oracle caveat: YOLOv8x is not human ground truth.

## SUPG-RT 20-Trial Clip-Level Metrics

| Metric | Mean | Min | Max |
|---|---:|---:|---:|
| Clip recall coverage | 0.997619 | 0.976190 | 1.000000 |
| Clip IoU recall | 0.980952 | 0.896825 | 1.000000 |
| Clip precision | 1.000000 | 1.000000 | 1.000000 |
| mIoU | 0.969980 | 0.884901 | 0.993564 |
| Frame recall | 0.971461 | 0.897301 | 0.994733 |
| Frame-to-clip gap | -0.026158 | -0.078890 | -0.005267 |

Additional summary:

- Trials: `20`.
- Errors: `0`.
- Mean selected_n: `8,134.6`.
- Mean GT clips hit by coverage: `125.7 / 126`.
- Mean fully missed pseudo-oracle clips: `0.0`.
- Mean consecutive-miss clips: `1.7`.
- GVR: not reported for this metric path. The current `run_frame_clip_gap.py` output has no GVR column, so this report does not mix it with the older `clip_metrics.py` evaluator.

## SUPG-PT 20-Trial Clip-Level Metrics

| Metric | Mean | Min | Max |
|---|---:|---:|---:|
| Clip recall coverage | 0.048810 | 0.015873 | 0.079365 |
| Clip IoU recall | 0.010714 | 0.000000 | 0.031746 |
| Clip precision | 1.000000 | 1.000000 | 1.000000 |
| mIoU | 0.020807 | 0.004473 | 0.042201 |
| Frame recall | 0.110039 | 0.098749 | 0.123107 |
| Frame-to-clip gap | 0.061230 | 0.024651 | 0.092751 |

Additional summary:

- Trials: `20`.
- Errors: `0`.
- Mean selected_n: `167.15`.
- Mean GT clips hit by coverage: `6.15 / 126`.
- Mean fully missed pseudo-oracle clips: `65.8`.
- Mean consecutive-miss clips: `39.4`.
- GVR: not reported for this metric path.

## Comparison With 5-Trial Clip Smoke

| Method | Metric | 5-Trial | 20-Trial | Direction |
|---|---|---:|---:|---|
| SUPG-RT | Frame recall mean | 0.983410 | 0.971461 | slightly lower |
| SUPG-RT | Clip recall coverage mean | 1.000000 | 0.997619 | similar |
| SUPG-RT | Clip IoU recall mean | 0.990476 | 0.980952 | slightly lower |
| SUPG-RT | mIoU mean | 0.981160 | 0.969980 | slightly lower |
| SUPG-RT | Mean selected_n | 8,391.8 | 8,134.6 | lower |
| SUPG-RT | Mean fully missed clips | 0.0 | 0.0 | unchanged |
| SUPG-PT | Frame recall mean | 0.110994 | 0.110039 | similar |
| SUPG-PT | Clip recall coverage mean | 0.053968 | 0.048810 | slightly lower |
| SUPG-PT | Clip IoU recall mean | 0.011111 | 0.010714 | similar |
| SUPG-PT | mIoU mean | 0.024915 | 0.020807 | slightly lower |
| SUPG-PT | Mean selected_n | 168.6 | 167.15 | similar |
| SUPG-PT | Mean fully missed clips | 62.8 | 65.8 | slightly higher |

The 20-trial clip smoke confirms the 5-trial finding: SUPG-RT remains strong at clip level on this pseudo-oracle benchmark, while SUPG-PT remains high precision but very low clip recall.

## Frame-to-Clip Gap Assessment

For SUPG-RT, there is no evidence of a harmful frame-to-clip guarantee gap in this smoke setting. Mean clip recall coverage (`0.997619`) is higher than mean frame recall (`0.971461`), and mean fully missed pseudo-oracle clips is `0.0`.

For SUPG-PT, there is clear evidence that a sparse high-precision frame selection does not translate into broad clip coverage: mean frame recall is `0.110039`, but mean clip recall coverage is only `0.048810` and mean clip IoU recall is `0.010714`. This is an expected operating-point tradeoff, not evidence that SUPG-RT fails.

## Evidence Boundaries

Engineering smoke evidence:

- UA-DETRAC has enough local frames and temporal continuity for clip smoke.
- SUPG-RT remains non-vacuous and strong at clip level over 20 trials.
- SUPG-PT remains a sparse, high-precision, low-clip-recall selection mode.

Research-valid evidence:

- Not established here. The labels and clips are YOLOv8x pseudo-oracle outputs, not human annotations.
- The 20-trial run is still a smoke step, not a formal guarantee evaluation.

Speculation:

- A future G-ARC method might be motivated by settings where frame-level selections fragment clips, but this SUPG-RT smoke does not yet demonstrate a severe RT clip failure.
- More stressful settings may require different budgets, predicates, clip definitions, or human-labeled data; those are future experiments, not conclusions from this report.

## Final Recommendation

- Proceed to 100-trial formal experiments now: **no**. The current evidence is still pseudo-oracle engineering smoke.
- Inspect the single RT failure from the 20-trial frame-level SUPG report: **yes**, before any formal run. The clip smoke remains strong, but the nonzero frame-level failure rate should be understood.
- Calibrate budget/K: **not immediately required** for clip-level smoke, because `K=25`, positive rate `10.9%`, and SUPG-RT clip metrics are non-degenerate. Consider budget/K calibration only if the next goal is a stress regime or formal benchmark protocol.
- Start designing G-ARC now: **no**. Per `AGENTS.md`, stay in benchmark construction and SUPG/ARC reproduction until the benchmark protocol is settled.
- Best next step: inspect the RT failure seed and document whether it is an expected statistical miss or a pipeline/modeling issue.

## Reproducibility Files

- 20-trial clip summary: `garc_eval/outputs/uadetrac_temporal/clip_smoke_20/summary.csv`
- 20-trial clip per-trial results: `garc_eval/outputs/uadetrac_temporal/clip_smoke_20/per_trial_results.csv`
- Pseudo-oracle clip table: `garc_eval/outputs/uadetrac_temporal/clip_smoke_20/gt_clips.csv`
- 5-trial clip summary: `garc_eval/outputs/uadetrac_temporal/clip_smoke_5/summary.csv`
- 20-trial frame-level SUPG report: `garc_eval/outputs/uadetrac_temporal_supg_smoke_20_report.md`
