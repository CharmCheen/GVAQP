# Non-Degenerate Benchmark Smoke Report

Generated: 2026-05-23

## Status

Selected dataset: **UA-DETRAC controlled local subset**.

This is an engineering smoke result, not research-valid evidence. Labels are derived from YOLOv8x pseudo-oracle counts and must not be described as human ground truth.

## Exact Commands Run

Frame-level SUPG smoke:

```bash
bash -lc 'source env_garc.sh && python -m garc_eval.experiments.run_supg_real_frames --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv --budget 1000 --gamma 0.9 --delta 0.05 --trials 5 --outdir garc_eval/outputs/uadetrac_temporal/supg_smoke_5'
```

Clip merge smoke:

```bash
bash -lc 'source env_garc.sh && python -m garc_eval.experiments.run_frame_clip_gap --source-csv garc_eval/outputs/uadetrac_temporal/supg_source.csv --frames-parquet garc_eval/outputs/uadetrac_temporal/frames.parquet --budget 1000 --gamma 0.9 --delta 0.05 --trials 5 --iou-threshold 0.5 --min-clip-frames 3 --methods SUPG-RT SUPG-PT --outdir garc_eval/outputs/uadetrac_temporal/clip_smoke_5'
```

Summary metric extraction:

```bash
bash -lc 'source env_garc.sh && python - <<\"PY\"
import pandas as pd
src=pd.read_csv(\"garc_eval/outputs/uadetrac_temporal/supg_source.csv\")
proxy=pd.read_parquet(\"garc_eval/outputs/uadetrac_temporal/proxy_scores.parquet\")
oracle=pd.read_parquet(\"garc_eval/outputs/uadetrac_temporal/oracle_scores.parquet\")
frames=pd.read_parquet(\"garc_eval/outputs/uadetrac_temporal/frames.parquet\")
print(\"N\", len(src))
print(\"positive_rate\", src.label.mean())
print(\"positive_count\", int(src.label.sum()))
print(\"proxy_unique\", src.proxy_score.nunique())
print(\"proxy_unique_rate\", src.proxy_score.nunique()/len(src))
print(\"proxy_oracle_count_spearman\", src[\"proxy_score\"].corr(oracle.set_index(\"id\").loc[src[\"id\"], \"oracle_count\"].reset_index(drop=True), method=\"spearman\"))
print(\"proxy_oracle_count_pearson\", src[\"proxy_score\"].corr(oracle.set_index(\"id\").loc[src[\"id\"], \"oracle_count\"].reset_index(drop=True), method=\"pearson\"))
print(\"sequences\", frames.video_id.nunique())
print(\"rows_by_video\", frames.groupby(\"video_id\").size().to_dict())
PY'
```

## Dataset and Subset

- Dataset: UA-DETRAC.
- Subset: 8 extracted traffic surveillance sequences.
- Frames: `N = 13,932`.
- Sequence counts:
  - `mvi_20032`: 437
  - `mvi_20033`: 784
  - `mvi_20051`: 906
  - `mvi_40172`: 2,635
  - `mvi_40191`: 2,495
  - `mvi_40192`: 2,195
  - `mvi_40241`: 2,320
  - `mvi_40992`: 2,160
- Temporal continuity: yes, 25 fps image sequences.
- Proxy: YOLOv8n.
- Pseudo-oracle: YOLOv8x.

## Predicate and Calibration

- Predicate: `count_car(frame) >= K`.
- Selected `K`: `25`.
- Selected by: target range.
- Positive frames: `1,519 / 13,932`.
- Positive rate: `0.109030`.

Calibration table excerpt:

| K | Positive Rate | Positive Count |
|---:|---:|---:|
| 21 | 0.372165 | 5,185 |
| 22 | 0.304264 | 4,239 |
| 23 | 0.234999 | 3,274 |
| 24 | 0.169897 | 2,367 |
| 25 | 0.109030 | 1,519 |
| 26 | 0.065174 | 908 |
| 27 | 0.032946 | 459 |
| 28 | 0.016724 | 233 |
| 29 | 0.006819 | 95 |
| 30 | 0.002082 | 29 |

## Proxy Quality

- Proxy score uniqueness: `13,912 / 13,932 = 0.998564`.
- Spearman correlation between proxy score and YOLOv8x oracle count: `0.841073`.
- Pearson correlation between proxy score and YOLOv8x oracle count: `0.889742`.

This is nontrivial ranking behavior, but the proxy is strong because both proxy and pseudo-oracle are YOLO models.

## Frame-Level 5-Trial SUPG Smoke

Budget: `1000`, gamma: `0.9`, delta: `0.05`, trials: `5`.

| Method | Failure Rate | Mean Selected N | Selected N / N | Mean Precision | Mean Recall |
|---|---:|---:|---:|---:|---:|
| SUPG-RT | 0.000000 | 8,391.8 | 0.602333 | 0.178195 | 0.983410 |
| SUPG-PT | 0.000000 | 168.6 | 0.012102 | 1.000000 | 0.110994 |
| U-CI-RT | 0.000000 | 13,926.8 | 0.999627 | 0.109070 | 1.000000 |
| U-NOCI-RT | 1.000000 | 6,692.2 | 0.480349 | 0.197668 | 0.870836 |
| U-NOCI-PT | 0.400000 | 76.4 | 0.005483 | 0.569018 | 0.047663 |

SUPG-RT is non-vacuous under the target criterion because `8391.8 / 13932 = 0.602333 < 0.95`.

SUPG-PT gives a high-precision / lower-recall tradeoff: mean precision `1.0`, mean recall `0.110994`, and mean selected fraction `0.012102`.

## Clip Merge Metrics

Clip smoke configuration: 5 trials, `min_clip_frames=3`, `iou_threshold=0.5`.

Ground-truth pseudo-oracle clips:

- Clip count: `126`.
- Mean duration: `0.32s`.
- Min duration: `0.08s`.
- Max duration: `6.64s`.

| Method | Errors | Mean Frame Recall | Clip Recall Coverage | Clip Recall IoU | Mean Clip Precision | mIoU | Mean Coverage | Mean Selected N |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| SUPG-RT | 0 | 0.983410 | 1.000000 | 0.990476 | 1.000000 | 0.981160 | 0.992685 | 8,391.8 |
| SUPG-PT | 0 | 0.110994 | 0.053968 | 0.011111 | 1.000000 | 0.024915 | 0.126603 | 168.6 |

GVR was not found in the current clip metric implementation, so it is not reported.

## Non-Degeneracy Assessment

Verdict: **non-degenerate engineering smoke benchmark**.

Reasons:

- `N = 13,932`, meeting the target minimum.
- Calibrated positive rate is `10.9%`, inside the 1% to 20% target range.
- Proxy score uniqueness is very high.
- SUPG-RT selects `60.2%` of frames on average, not all frames.
- SUPG-PT shows a meaningful high-precision / low-recall operating point.
- Temporal continuity is present and clip merge metrics can be computed.

This is suitable for a 20-trial next step. It is not yet research-valid evidence because labels are YOLOv8x pseudo-oracle labels and the subset was selected from cached local materialization.

## Limitations and Uncertainty

- YOLOv8x pseudo-oracle is not human ground truth.
- YOLOv8n and YOLOv8x are related models, so proxy/pseudo-oracle agreement may overstate benchmark tractability.
- The selected subset has many short positive clips; this may make some clip-level conclusions sensitive to `min_clip_frames` and gap tolerance.
- The smoke run used 5 trials only. It is enough to reject obvious degeneracy, not enough for formal claims.
- Existing pipeline output files include CSV/parquet caches that must not be staged or committed.

## Reproducibility Files

- Frame-level summary: `garc_eval/outputs/uadetrac_temporal/supg_smoke_5/summary.csv`
- Frame-level per-trial results: `garc_eval/outputs/uadetrac_temporal/supg_smoke_5/per_trial_results.csv`
- Clip summary: `garc_eval/outputs/uadetrac_temporal/clip_smoke_5/summary.csv`
- Clip per-trial results: `garc_eval/outputs/uadetrac_temporal/clip_smoke_5/per_trial_results.csv`
