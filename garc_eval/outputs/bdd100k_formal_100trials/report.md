# BDD100K Formal 100-Trial SUPG Report

Generated: 2026-05-20

## 1. Dataset

- **Dataset name**: BDD100K (Hirundo validation subset)
- **Source**: https://huggingface.co/datasets/hirundo-io/bdd100k-validation-only
- **License**: BSD-3-Clause
- **Note**: This is a community mirror of the BDD100K validation split hosted on HuggingFace.
  The original BDD100K dataset is from Berkeley DeepDrive (bdd-data.berkeley.edu).
- **N**: 10,000 images (1280x720 JPEG)
- **Scene type**: Driving/dashcam road scenes (urban, highway, residential)
- **Frame table**: garc_eval/outputs/bdd100k_smoke/frame_metadata.parquet
- **SUPG source**: garc_eval/outputs/bdd100k_smoke/supg_source.csv

## 2. Query

- **Predicate**: count_car(frame) >= K
- **Calibrated K**: 13
- **Positive rate**: 9.92% (992 / 10,000)
- **Label counts**: positive=992, negative=9,008
- **Calibration**: oracle_count from YOLOv8x, target range [1%, 20%]

## 3. Models

- **Proxy**: YOLOv8n (yolov8n.pt)
- **Oracle**: YOLOv8x pseudo-oracle (yolov8x.pt)
- **proxy_score_rule**: count_conf_hybrid
- **proxy_score unique count**: 9,287 / 10,000
- **proxy_score range**: [0.000000, 0.982582]

## 4. SUPG Setting

- **gamma**: 0.9
- **delta**: 0.05
- **budget**: 1,000
- **budget_ratio**: 0.1
- **trials**: 100

## 5. Results (100 trials)

| method | qtype | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | selected_n / N | vacuous |
|--------|-------|-------------|----------------|------------------|-------------|---------------|-----------------|----------------|---------|
| U-NOCI-RT | rt | 0.40 | 0.336 | 0.325 | 0.907 | 0.912 | 2,769 | 0.277 | no |
| U-CI-RT | rt | 0.00 | 0.099 | 0.099 | 1.000 | 1.000 | 10,000 | 1.000 | yes (trivial) |
| **SUPG-RT** | **rt** | **0.00** | **0.185** | **0.178** | **0.977** | **0.980** | **5,417** | **0.542** | **no** |
| U-NOCI-PT | pt | 0.85 | 0.440 | 0.390 | 0.128 | 0.043 | 148 | 0.015 | no |
| SUPG-PT | pt | 0.00 | 1.000 | 1.000 | 0.275 | 0.275 | 273 | 0.027 | no |

### SUPG-RT detailed (100 trials):
- mean_selected_n: 5,417.47
- median_selected_n: 5,459.5
- mean_recall: 0.9770
- median_recall: 0.9803
- mean_precision: 0.1849
- mean_sampled_n: 946.32
- failure_rate: 0.0
- error_count: 0

### SUPG-PT detailed (100 trials):
- mean_selected_n: 272.66
- median_selected_n: 272.5
- mean_precision: 1.0000
- mean_recall: 0.2749
- failure_rate: 0.0
- error_count: 0

## 6. Judgment

### SUPG-RT: NON-VACUOUS
- selected_n / N = 0.542, well below the 0.95 vacuity threshold
- failure_rate = 0.0 across all 100 trials: the gamma=0.9 recall guarantee holds
- mean_recall = 0.977 > gamma = 0.9
- SUPG-RT selects roughly half the dataset while capturing 97.7% of positive frames
- This is a genuine non-trivial selection, not a degenerate all-select

### SUPG-PT: STABLE
- precision = 1.000 across all 100 trials (perfect)
- recall = 0.275 with low variance (selected_n range: ~260-289)
- failure_rate = 0.0
- SUPG-PT provides a reliable high-precision subset

### Benchmark quality
BDD100K val is a suitable frame-level real-road benchmark for G-ARC:
- Sufficient scale (N=10,000)
- Meaningful positive rate (9.92%)
- High proxy score diversity (9,287 unique)
- Non-vacuous SUPG-RT behavior confirmed over 100 trials
- Stable SUPG-PT behavior confirmed over 100 trials
- Clear method differentiation (U-NOCI-RT vs SUPG-RT vs SUPG-PT)

## 7. Comparison with KITTI Combined

| Metric | KITTI combined | BDD100K |
|--------|---------------|---------|
| N | 1,176 | 10,000 |
| K | 15 | 13 |
| positive rate | 13.78% | 9.92% |
| proxy_score unique | 1,102 | 9,287 |
| budget | 117 | 1,000 |
| SUPG-RT selected_n/N | 1.000 (vacuous) | 0.542 (non-vacuous) |
| SUPG-RT failure_rate | 0.0 | 0.0 |
| SUPG-PT precision | 1.0 | 1.0 |

The key difference enabling non-vacuous SUPG-RT is the larger N (10x) and higher proxy score
diversity (8.4x), which gives the sampling-based RT threshold estimation enough resolution
to produce a meaningful selection boundary.

## 8. Limitations

1. **Image-level, not clip-level**: BDD100K val consists of individual images, not temporal
   video clips. This benchmark validates frame-level SUPG selection but does NOT demonstrate
   clip-level guaranteed approximate relevant clip query processing. Temporal video benchmarks
   (e.g., UA-DETRAC) are needed for clip-level evaluation.

2. **Pseudo-oracle**: The oracle is YOLOv8x, not ground-truth human annotation. The
   "failure_rate" measures consistency between proxy and pseudo-oracle, not true accuracy.

3. **Single predicate**: Only count_car >= K is tested. Other predicates (e.g., contains_class,
   count_person, multi-class) are not evaluated.

4. **Driving perspective**: BDD100K images are from a dashcam perspective, which differs from
   surveillance/surveillance overhead views. Car counts are generally lower than in traffic
   surveillance footage.

## 9. Files

- Per-trial results: garc_eval/outputs/bdd100k_formal_100trials/per_trial_results.csv
- Summary CSV: garc_eval/outputs/bdd100k_formal_100trials/summary.csv
- Summary MD: garc_eval/outputs/bdd100k_formal_100trials/summary.md
- Config: garc_eval/outputs/bdd100k_formal_100trials/config.json
- RT recall boxplot: garc_eval/outputs/bdd100k_formal_100trials/boxplot_rt_recall.png
- PT precision boxplot: garc_eval/outputs/bdd100k_formal_100trials/boxplot_pt_precision.png
