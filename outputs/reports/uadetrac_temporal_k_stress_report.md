# UA-DETRAC Predicate-Difficulty K-Stress Report

Date: 2026-05-23

This is an engineering smoke/stress diagnosis using existing cached UA-DETRAC data. It does not rerun YOLO, does not download data, and is not research-valid evidence. YOLOv8x is used only as a pseudo-oracle, not as human ground truth.

## Inputs and Cached Columns

- Baseline source CSV: `garc_eval/outputs/uadetrac_temporal/supg_source.csv`
- Cached frame table: `garc_eval/outputs/uadetrac_temporal/frames.parquet`
- Dataset: UA-DETRAC controlled local subset
- Frame count: `N = 13,932`
- Baseline predicate: `count_car(frame) >= 25`

The baseline source CSV contains only:

```text
id, label, proxy_score
```

By itself, the source CSV is not enough to vary `K`. The cached frame table does contain the needed count fields:

```text
id, video_id, frame_idx, timestamp, image_path, proxy_score_raw,
proxy_max_conf, proxy_count, proxy_conf_sum, proxy_conf_mean,
proxy_conf_top3_sum, proxy_conf_top5_sum, oracle_score,
oracle_count, proxy_score, label
```

The K-stress sources were derived from `frames.parquet` without rerunning YOLO:

- Label rule: `label = 1[oracle_count >= K]`
- Proxy score rule: `count_conf_hybrid`
- Recomputed proxy score: `0.7 * min(proxy_count / K, 1.0) + 0.3 * proxy_max_conf`

This reuses cached YOLOv8n proxy counts/confidence and cached YOLOv8x pseudo-oracle counts. The derived CSV/parquet files are local output artifacts and should not be committed.

## Exact Commands Run

Derive K-specific cached sources:

```bash
source env_garc.sh
PYTHONPATH=. python - <<'PY'
from pathlib import Path
import pandas as pd

base = Path('garc_eval/outputs/uadetrac_temporal')
frames = pd.read_parquet(base / 'frames.parquet')
outbase = base / 'k_stress'
outbase.mkdir(parents=True, exist_ok=True)

rows = []
for k in range(25, 32):
    pos = int((frames['oracle_count'] >= k).sum())
    rows.append({'K': k, 'positives': pos, 'N': len(frames), 'positive_rate': pos / len(frames)})
pd.DataFrame(rows).to_csv(outbase / 'k_calibration.csv', index=False)

for k in [27, 28]:
    out = outbase / f'k{k}'
    out.mkdir(parents=True, exist_ok=True)
    df = frames.copy()
    df['label'] = (df['oracle_count'] >= k).astype(int)
    df['proxy_score'] = 0.7 * (df['proxy_count'] / k).clip(upper=1.0) + 0.3 * df['proxy_max_conf']
    df[['id', 'label', 'proxy_score']].to_csv(out / 'supg_source.csv', index=False)
    df.to_parquet(out / 'frames.parquet', index=False)
PY
```

Frame-level SUPG smoke:

```bash
source env_garc.sh
for k in 27 28; do
  PYTHONPATH=. python -m garc_eval.experiments.run_supg_real_frames \
    --source-csv "garc_eval/outputs/uadetrac_temporal/k_stress/k${k}/supg_source.csv" \
    --budget 1000 \
    --gamma 0.9 \
    --delta 0.05 \
    --trials 10 \
    --outdir "garc_eval/outputs/uadetrac_temporal/k_stress/k${k}/supg_budget_1000"
done
```

Clip-level metrics:

```bash
source env_garc.sh
for spec in "27 0.7 0_7" "27 0.9 0_9" "28 0.7 0_7" "28 0.9 0_9"; do
  set -- $spec
  k=$1
  iou=$2
  tag=$3
  PYTHONPATH=. python -m garc_eval.experiments.run_frame_clip_gap \
    --source-csv "garc_eval/outputs/uadetrac_temporal/k_stress/k${k}/supg_source.csv" \
    --frames-parquet "garc_eval/outputs/uadetrac_temporal/k_stress/k${k}/frames.parquet" \
    --budget 1000 \
    --gamma 0.9 \
    --delta 0.05 \
    --trials 10 \
    --iou-threshold "$iou" \
    --min-clip-frames 3 \
    --methods SUPG-RT SUPG-PT \
    --outdir "garc_eval/outputs/uadetrac_temporal/k_stress/k${k}/clip_budget_1000_iou_${tag}"
done
```

## K Calibration

| K | Positives | N | Positive rate |
|---:|---:|---:|---:|
| 25 | 1,519 | 13,932 | 10.90% |
| 26 | 908 | 13,932 | 6.52% |
| 27 | 459 | 13,932 | 3.29% |
| 28 | 233 | 13,932 | 1.67% |
| 29 | 95 | 13,932 | 0.68% |
| 30 | 29 | 13,932 | 0.21% |
| 31 | 6 | 13,932 | 0.04% |

Selected settings:

- `K=27`: moderate-hard setting in the requested 3%-5% positive-rate band.
- `K=28`: hard setting in the requested 1%-3% positive-rate band.

`K=29` and above were not selected because they fall below 1% positives and would make the pseudo-oracle-positive clips very sparse.

## Frame-Level Results

| K | Method | Positives | Positive rate | Proxy unique | Mean selected_n / N | Precision | Recall | Failure rate | Selected-all |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 27 | SUPG-RT | 459 | 3.29% | 13,912 / 13,932 | 1.0000 | 0.0329 | 1.0000 | 0.0000 | 10 / 10 |
| 27 | SUPG-PT | 459 | 3.29% | 13,912 / 13,932 | 0.0032 | 1.0000 | 0.0974 | 0.0000 | 0 / 10 |
| 28 | SUPG-RT | 233 | 1.67% | 13,912 / 13,932 | 1.0000 | 0.0167 | 1.0000 | 0.0000 | 10 / 10 |
| 28 | SUPG-PT | 233 | 1.67% | 13,912 / 13,932 | 0.0015 | 1.0000 | 0.0906 | 0.0000 | 0 / 10 |

At budget `1000`, increasing `K` made the predicate rarer but caused SUPG-RT to become vacuous: it selected all frames in every trial for both selected K settings.

## Clip-Level Results

Clip construction used `min_clip_frames=3` and `gap_tolerance=0`.

| K | Pseudo-oracle clips | IoU threshold | Method | Clip recall coverage | Clip IoU recall | Clip precision | mIoU | Worst trial seed |
|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 27 | 42 | 0.7 | SUPG-RT | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| 27 | 42 | 0.7 | SUPG-PT | 0.0976 | 0.0238 | 1.0000 | 0.0494 | 2 |
| 27 | 42 | 0.9 | SUPG-RT | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| 27 | 42 | 0.9 | SUPG-PT | 0.0976 | 0.0190 | 1.0000 | 0.0494 | 2 |
| 28 | 18 | 0.7 | SUPG-RT | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| 28 | 18 | 0.7 | SUPG-PT | 0.0389 | 0.0167 | 1.0000 | 0.0261 | 5 |
| 28 | 18 | 0.9 | SUPG-RT | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| 28 | 18 | 0.9 | SUPG-PT | 0.0389 | 0.0111 | 1.0000 | 0.0261 | 5 |

Worst-trial details:

| K | Method | IoU | Worst seed | Worst selected_n | Worst frame recall | Min clip IoU recall | Min mIoU | Mean fully missed clips | Mean boundary misses |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 27 | SUPG-RT | 0.7 | 0 | 13,932 | 1.0000 | 1.0000 | 1.0000 | 0.0 | 0.0 |
| 27 | SUPG-RT | 0.9 | 0 | 13,932 | 1.0000 | 1.0000 | 1.0000 | 0.0 | 0.0 |
| 27 | SUPG-PT | 0.7 | 2 | 45 | 0.0980 | 0.0000 | 0.0167 | 29.1 | 0.7 |
| 27 | SUPG-PT | 0.9 | 2 | 45 | 0.0980 | 0.0000 | 0.0167 | 29.1 | 0.7 |
| 28 | SUPG-RT | 0.7 | 0 | 13,932 | 1.0000 | 1.0000 | 1.0000 | 0.0 | 0.0 |
| 28 | SUPG-RT | 0.9 | 0 | 13,932 | 1.0000 | 1.0000 | 1.0000 | 0.0 | 0.0 |
| 28 | SUPG-PT | 0.7 | 5 | 26 | 0.1116 | 0.0000 | 0.0000 | 13.1 | 0.8 |
| 28 | SUPG-PT | 0.9 | 5 | 26 | 0.1116 | 0.0000 | 0.0000 | 13.1 | 0.8 |

## Gap Diagnosis

This K-stress did not create a meaningful harmful SUPG-RT frame-to-clip gap. For SUPG-RT, frame recall and clip recall were perfect only because every frame was selected in every trial. The difficulty increase therefore produced vacuity, not a useful boundary-degradation case.

SUPG-PT did show poor clip recall and low mIoU, especially at `K=28`, but this is caused by intentionally sparse high-precision selection:

- `K=27`: mean selected fraction `0.32%`, mean frame recall `9.74%`, mean clip IoU recall `1.90%`-`2.38%`.
- `K=28`: mean selected fraction `0.15%`, mean frame recall `9.06%`, mean clip IoU recall `1.11%`-`1.67%`.

That is a useful baseline contrast, but it is not evidence of a frame-level guarantee failing after clip merging.

## Interpretation

- `K=27` and `K=28` are valid cached predicate-difficulty stress settings.
- At budget `1000`, both settings are degenerate for SUPG-RT because selected-all occurs in `10 / 10` trials.
- The observed clip-level degradation belongs to sparse SUPG-PT behavior, not to a harmful SUPG-RT frame-to-clip guarantee gap.
- This does not by itself suggest a real G-ARC research opening on the current UA-DETRAC subset and budget. It strengthens the conclusion that UA-DETRAC is useful as a baseline and pipeline benchmark, but weak for demonstrating clip-level advantage unless a non-vacuous harder setting is found.

## Recommendation

Do not run 100-trial experiments from these K-stress settings. The next controlled experiment should combine predicate difficulty with a budget that prevents selected-all behavior, for example:

- `K=27`, `budget=500`, `trials=10`, IoU thresholds `0.7` and `0.9`.
- `K=28`, `budget=500`, `trials=10`, IoU thresholds `0.7` and `0.9`.

If those still select all for SUPG-RT, try a different dataset or a larger/more varied UA-DETRAC subset before designing a G-ARC method.
