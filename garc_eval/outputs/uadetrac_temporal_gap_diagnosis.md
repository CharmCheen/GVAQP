# UA-DETRAC 20-Trial Gap Diagnosis

Generated: 2026-05-23

## Scope

This report diagnoses the UA-DETRAC 20-trial frame-level and clip-level smoke outputs. It uses cached CSV/parquet outputs only; no data download, YOLO materialization, 100-trial experiment, algorithm-code change, or new G-ARC method design was performed.

This is engineering smoke evidence. It is not research-valid evidence because labels and clips are derived from the YOLOv8x pseudo-oracle; YOLOv8x is not human ground truth.

## Inputs Inspected

- Source CSV: `garc_eval/outputs/uadetrac_temporal/supg_source.csv`
- Frame-level 20-trial output: `garc_eval/outputs/uadetrac_temporal/supg_smoke_20`
- Clip-level 20-trial output: `garc_eval/outputs/uadetrac_temporal/clip_smoke_20`
- Existing frame report: `garc_eval/outputs/uadetrac_temporal_supg_smoke_20_report.md`
- Existing clip report: `garc_eval/outputs/uadetrac_temporal_clip_smoke_20_report.md`

Dataset summary:

- Dataset: UA-DETRAC controlled local subset.
- Predicate: `count_car(frame) >= 25`.
- Frames: `13,932`.
- Positive pseudo-oracle frames: `1,519`.
- Positive rate: `0.109030`.
- Pseudo-oracle clips: `126` using `min_clip_frames=3`, `gap_tolerance=0`.

## Commands Used

Read existing reports and outputs:

```bash
sed -n '1,220p' AGENTS.md
sed -n '1,220p' garc_eval/outputs/uadetrac_temporal_supg_smoke_20_report.md
sed -n '1,260p' garc_eval/outputs/uadetrac_temporal_clip_smoke_20_report.md
```

Report-only diagnostic reconstruction:

```bash
bash -lc 'source env_garc.sh && PYTHONPATH=. python - <<"PY" > /tmp/uadetrac_gap_diag.json
# Loaded supg_source.csv, frames.parquet, supg_smoke_20/per_trial_results.csv,
# and clip_smoke_20/per_trial_results.csv; reconstructed SUPG selected_ids
# for relevant seeds using garc_eval.adapters.supg_adapter and computed
# per-clip best IoU/coverage with garc_eval.metrics.frame_to_clip helpers.
PY'
```

Adapter metadata check for failed RT seed:

```bash
bash -lc 'source env_garc.sh && PYTHONPATH=. python - <<"PY"
import pandas as pd
from garc_eval.adapters.supg_adapter import run_supg_rt
src = pd.read_csv("garc_eval/outputs/uadetrac_temporal/supg_source.csv")
r = run_supg_rt(df=src, budget=1000, gamma=0.9, delta=0.05, seed=15)
print(r.keys())
print(r["metadata"])
PY'
```

## Frame-Level RT Failure

Exactly one SUPG-RT trial missed the frame-level recall target `gamma=0.9`.

| Trial | selected_n | precision | recall | true positives | total positives | sampled_n | threshold |
|---:|---:|---:|---:|---:|---:|---:|---|
| 15 | 7,003 | 0.194631 | 0.897301 | 1,363 | 1,519 | 970 | not exposed by adapter metadata |

The existing adapter metadata for this seed contains only method, query type, budget, gamma, delta, and seed. It does not expose an internal selection threshold, so no threshold is reported here.

### Clip Impact Of Failed RT Trial

The same seed is also the worst SUPG-RT clip-level trial.

| Trial | frame recall | frame precision | clip recall coverage | clip IoU recall | mIoU | selected_n | coverage hits | IoU hits | fully missed clips |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | 0.897301 | 0.194631 | 0.976190 | 0.896825 | 0.884901 | 7,003 | 123 / 126 | 113 / 126 | 0 |

The frame-level failure did degrade clip IoU recall and mIoU, but it did not create fully missed pseudo-oracle clips under the coverage metric. The main damage is fragmented or boundary-shifted selected runs inside otherwise partially covered clips.

## Worst Clip-Level Trials

| Method | Criterion | Trial | Frame recall | Frame precision | Clip coverage recall | Clip IoU recall | mIoU | selected_n | Diagnosis |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| SUPG-RT | Lowest clip IoU recall | 15 | 0.897301 | 0.194631 | 0.976190 | 0.896825 | 0.884901 | 7,003 | Same as frame-level RT failure; boundary shifts and fragmentation. |
| SUPG-RT | Lowest mIoU | 15 | 0.897301 | 0.194631 | 0.976190 | 0.896825 | 0.884901 | 7,003 | Same failure mode. |
| SUPG-RT | Lowest clip coverage recall | 15 | 0.897301 | 0.194631 | 0.976190 | 0.896825 | 0.884901 | 7,003 | Same failure mode. |
| SUPG-PT | Lowest clip IoU recall | 1 | 0.102041 | 1.000000 | 0.023810 | 0.000000 | 0.012046 | 155 | Sparse high-precision selection misses most short clips. |
| SUPG-PT | Lowest mIoU | 19 | 0.108624 | 1.000000 | 0.015873 | 0.000000 | 0.004473 | 165 | Sparse high-precision selection misses most short clips. |
| SUPG-PT | Lowest clip coverage recall | 12 | 0.104674 | 1.000000 | 0.015873 | 0.007937 | 0.017810 | 159 | Sparse high-precision selection misses most short clips. |

## Worst Affected Clips

### SUPG-RT Seed 15

These are the lowest-IoU pseudo-oracle clips in the failed RT trial.

| GT clip | Video | GT frames | Duration | Selected positives | Coverage | Pred frames | Best IoU | Issue |
|---:|---|---|---:|---:|---:|---|---:|---|
| 17 | mvi_20032 | 344-348 | 5 | 1 | 0.200000 | none | 0.000000 | fragmentation |
| 15 | mvi_20032 | 183-189 | 7 | 2 | 0.285714 | none | 0.000000 | fragmentation |
| 3 | mvi_20032 | 52-54 | 3 | 1 | 0.333333 | none | 0.000000 | fragmentation |
| 24 | mvi_20033 | 295-297 | 3 | 2 | 0.666667 | none | 0.000000 | fragmentation |
| 27 | mvi_20033 | 358-405 | 48 | 26 | 0.541667 | 371-379 | 0.170213 | boundary shift |
| 21 | mvi_20033 | 101-267 | 167 | 120 | 0.718563 | 143-172 | 0.174699 | boundary shift |
| 43 | mvi_20033 | 676-686 | 11 | 8 | 0.727273 | 680-682 | 0.200000 | boundary shift |
| 28 | mvi_20033 | 408-427 | 20 | 13 | 0.650000 | 414-419 | 0.263158 | boundary shift |
| 40 | mvi_20033 | 589-655 | 67 | 62 | 0.925373 | 589-618 | 0.439394 | boundary shift |

Interpretation: this is not a complete clip disappearance case for SUPG-RT. The worst RT trial still has high coverage recall (`123 / 126` clips hit), but some selected positive frames do not form candidate clips with enough temporal overlap. Short clips fragment, and longer clips can be represented by interior sub-runs rather than full boundaries.

### SUPG-PT Worst Cases

For SUPG-PT, the worst affected clips are mostly short pseudo-oracle clips that receive no selected positive frames.

| Trial | GT clip | Video | GT frames | Duration | Coverage | Best IoU | Issue |
|---:|---:|---|---|---:|---:|---:|---|
| 1 | 0 | mvi_20032 | 4-6 | 3 | 0.000000 | 0.000000 | missing short clip |
| 1 | 2 | mvi_20032 | 33-35 | 3 | 0.000000 | 0.000000 | missing short clip |
| 1 | 3 | mvi_20032 | 52-54 | 3 | 0.000000 | 0.000000 | missing short clip |
| 1 | 5 | mvi_20032 | 90-92 | 3 | 0.000000 | 0.000000 | missing short clip |
| 1 | 6 | mvi_20032 | 100-102 | 3 | 0.000000 | 0.000000 | missing short clip |
| 1 | 24 | mvi_20033 | 295-297 | 3 | 0.000000 | 0.000000 | missing short clip |
| 19 | 0 | mvi_20032 | 4-6 | 3 | 0.000000 | 0.000000 | missing short clip |
| 12 | 0 | mvi_20032 | 4-6 | 3 | 0.000000 | 0.000000 | missing short clip |

Interpretation: this is an expected consequence of the SUPG-PT operating point. PT selects very few frames with precision `1.0`; it is not intended to cover most clips.

## Frame-To-Clip Gap Diagnosis

Under the current UA-DETRAC setting, there is **no meaningful harmful frame-to-clip gap for SUPG-RT**.

Evidence:

- Mean SUPG-RT frame recall over 20 trials: `0.971461`.
- Mean SUPG-RT clip coverage recall: `0.997619`.
- Mean SUPG-RT clip IoU recall: `0.980952`.
- Mean fully missed pseudo-oracle clips: `0.0`.
- The only RT frame-level failure, seed 15, also has the worst clip metrics, but still hits `123 / 126` clips by coverage and fully misses zero clips.

The observed RT issue is better described as a **frame-level recall miss with local temporal boundary/fragmentation effects**, not as a strong G-ARC-style failure case.

For SUPG-PT, there is a clear frame-to-clip coverage gap, but it is tied to the PT objective and sparse high-precision selection:

- Mean PT frame recall: `0.110039`.
- Mean PT clip coverage recall: `0.048810`.
- Mean PT clip IoU recall: `0.010714`.
- PT precision remains `1.0`, but many short clips receive no selected frames.

## Benchmark Suitability

Current UA-DETRAC setting is:

- **Good for non-degenerate SUPG benchmark**: yes. It has `N=13,932`, positive rate `10.9%`, non-vacuous SUPG-RT selection, and stable 20-trial smoke behavior.
- **Weak for proving G-ARC advantage**: yes. SUPG-RT already performs very well at clip level, so this setting does not strongly expose a frame-to-clip guarantee failure.
- **Useful as a baseline benchmark only**: yes. It should be kept as a baseline non-degenerate traffic benchmark and a sanity check before harder clip-level settings.

## Recommended Next Experiment

Recommended next step: **boundary/clip-definition stress using existing code paths, not new method design**.

Priority order:

1. Inspect seed 15 more directly as a failure case in reports: it is the only SUPG-RT frame-recall failure and the worst clip seed.
2. Vary minimum clip length and gap tolerance using existing frame-to-clip metrics to see whether current short pseudo-oracle clips are driving the diagnosis.
3. Lower budget below `1000` to create a harder RT regime; this is more likely to reveal clip degradation than immediately changing methods.
4. Vary `K` only after budget stress, because `K=25` already gives a good non-degenerate positive rate.
5. Consider a harder dataset only if UA-DETRAC budget/clip-definition stress still fails to produce meaningful RT clip failures.
6. Do not run 100-trial formal experiments until gap cases are clearer and the seed-15 behavior is documented.
7. Do not start designing G-ARC yet; this benchmark currently supports baseline construction more than method invention.
