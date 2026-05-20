# BDD100K SUPG Smoke Report

Generated: 2026-05-20

## 1. Dataset

- **Dataset name**: BDD100K (Hirundo validation subset)
- **Source**: https://huggingface.co/datasets/hirundo-io/bdd100k-validation-only
- **License**: BSD-3-Clause
- **Selected subset**: All 10,000 validation images
- **Video/image sequence count**: 10,000 individual JPEG images (1280x720)
- **Frame count N**: 10,000
- **Sampling fps / stride**: N/A (image dataset, no temporal sampling)
- **Storage location**: /qiuyeqing/llama_prl/G-ARC/data/bdd100k/bdd100k/images/100k/val
- **Frame table**: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/bdd100k_smoke/frame_metadata.parquet

## 2. Query

- **Predicate**: count_car(frame) >= K
- **Calibrated K**: 13
- **Positive rate**: 9.92% (992 / 10,000)
- **Label counts**: positive=992, negative=9008
- **Calibration method**: target range [1%, 20%], selected by midpoint proximity
- **Calibration file**: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/bdd100k_smoke/count_calibration.json

## 3. Models

- **Proxy**: YOLOv8n (yolov8n.pt)
- **Oracle**: YOLOv8x pseudo-oracle (yolov8x.pt)
- **proxy_score_rule**: count_conf_hybrid
- **proxy_score unique count**: 9,287 / 10,000
- **proxy_score range**: [0.000000, 0.982582]
- **proxy_score mean**: 0.478615
- **proxy_score std**: 0.240626

## 4. SUPG Setting

- **gamma**: 0.9
- **delta**: 0.05
- **budget**: 1,000
- **budget_ratio**: 0.1
- **trials**: 20

## 5. Results (20 trials)

| method | qtype | failure_rate | mean_precision | mean_recall | mean_selected_n | selected_n / N | vacuous |
|--------|-------|-------------|----------------|-------------|-----------------|----------------|---------|
| U-NOCI-RT | rt | 0.50 | 0.343 | 0.903 | 2,723 | 0.272 | no |
| U-CI-RT | rt | 0.00 | 0.099 | 1.000 | 10,000 | 1.000 | yes (trivial) |
| SUPG-RT | rt | 0.00 | 0.196 | 0.973 | 5,048 | 0.505 | **no** |
| U-NOCI-PT | pt | 0.80 | 0.487 | 0.140 | 161 | 0.016 | no |
| SUPG-PT | pt | 0.00 | 1.000 | 0.274 | 272 | 0.027 | no |

### Detailed SUPG-RT statistics (20 trials):
- mean_selected_n: 5,048.15 (std across seeds)
- mean_recall: 0.9725
- mean_precision: 0.1959
- mean_sampled_n: 944.9
- failure_rate: 0.0

### Detailed SUPG-PT statistics (20 trials):
- mean_selected_n: 271.65
- mean_precision: 1.0000 (perfect)
- mean_recall: 0.2738
- failure_rate: 0.0
- Very stable across seeds (selected_n range: 258-287)

## 6. Judgment

- **SUPG-RT non-vacuous**: YES. selected_n/N = 0.505, well below 0.95 threshold.
  SUPG-RT selects ~50% of frames while achieving 97.3% recall.
  This is the first real-video benchmark where SUPG-RT demonstrates non-trivial selection.

- **SUPG-PT stable**: YES. Precision is consistently 1.0 across all 20 seeds.
  Selected count varies only between 258-287 (low variance).
  SUPG-PT provides perfect precision guarantee with ~27% recall.

- **Suitable as benchmark**: YES. This dataset provides a meaningful benchmark for SUPG:
  - Sufficient size (N=10,000)
  - Meaningful positive rate (9.92%)
  - High proxy score diversity (9,287 unique values)
  - Non-vacuous SUPG-RT behavior
  - Stable SUPG-PT behavior
  - Clear differentiation between methods

- **Comparison with KITTI combined**:
  - KITTI: N=1,176, SUPG-RT selected_n=N (vacuous)
  - BDD100K: N=10,000, SUPG-RT selected_n=5,048 (non-vacuous)
  - Key difference: larger N and higher proxy score diversity

## 7. Failure Notes

No failures at any stage:
- acquisition: SUCCESS (direct HuggingFace download)
- extraction: SUCCESS (standard unzip)
- materialization: SUCCESS (proxy YOLOv8n + oracle YOLOv8x)
- calibration: SUCCESS (K=13, rate=9.92%)
- SUPG smoke: SUCCESS (all methods completed without errors)

## 8. Data Files

- Frame metadata: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/bdd100k_smoke/frame_metadata.parquet
- Proxy scores: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/bdd100k_smoke/proxy_scores.parquet
- Oracle scores: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/bdd100k_smoke/oracle_scores.parquet
- Frames table: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/bdd100k_smoke/frames.parquet
- SUPG source: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/bdd100k_smoke/supg_source.csv
- 5-trial results: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/bdd100k_smoke/supg_results/
- 20-trial results: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/bdd100k_smoke/supg_results_20/
