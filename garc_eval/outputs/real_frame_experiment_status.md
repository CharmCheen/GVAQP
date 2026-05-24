# Real-Frame SUPG Experiment Status Report

## 1. Objective
This stage validated the real frame-level proxy/oracle pipeline and attempted to build a SUPG-style real-video reproduction workflow. The focus was not exact SUPG night-street reproduction, but a practical real-frame setup using public road-scene data, YOLO proxy/oracle materialization, calibrated frame labels, and SUPG-style selectors.

## 2. DRIV100 Attempt
DRIV100 Zenodo record 4389243 does not include original video files. The record contains JSON labels, metadata, and scripts, but not the raw videos needed by the current YOLO materialization pipeline.

Conclusion: DRIV100 stopped for this pipeline. It may still be useful if the original YouTube videos are obtained separately, but it cannot be used directly from the Zenodo package for this YOLO frame-scoring workflow.

## 3. KITTI 0005 Smoke
- sequence: 2011_09_26_drive_0005_sync
- N: 154
- contains_car positive rate: 96.1%
- count_car >= 5 positive rate: 42.9%
- outcome: real-frame extraction, YOLOv8n proxy scoring, YOLOv8x pseudo-oracle scoring, frame table building, and SUPG runner integration all succeeded

This run proved that the model/materialization pipeline works. However, N was too small and the predicates were not suitable enough for a non-degenerate SUPG-RT experiment. SUPG-RT selected all records, and early SUPG-PT runs exposed edge-case behavior including math domain errors.

## 4. Combined KITTI Smoke
Combined sequences:
- 2011_09_26_drive_0005_sync
- 2011_09_26_drive_0014_sync
- 2011_09_26_drive_0018_sync
- 2011_09_26_drive_0051_sync

Summary:
- total N: 1176
- selected_k: 15
- predicate: count_car >= 15
- label mean: 13.78%
- budget: 117

SUPG summary:
- U-NOCI-RT: failure_rate=0.2, mean_precision≈0.477
- U-CI-RT: selects all records
- SUPG-RT: selects all records
- U-NOCI-PT: failure_rate=1.0
- SUPG-PT: precision=1.0, recall≈0.228

The combined dataset reached a reasonable positive rate and fixed the earlier SUPG-PT math-domain failure, but SUPG-RT remained vacuous.

## 5. Proxy Score Ablation
Rules tested:
- count_ratio
- conf_sum_ratio
- conf_top5_ratio
- soft_count_exp
- count_conf_hybrid
- rank_percentile

The proxy score granularity improved substantially: count_ratio had 16 unique scores, while confidence-based rules reached 1102 unique scores. Saturation was also reduced or removed for most rules.

However, all rules still produced vacuous SUPG-RT behavior: `rt_supg_mean_selected_n = 1176` for every rule. SUPG-PT produced no errors across the ablation. `count_conf_hybrid` is the recommended default rule for future experiments because it improves score granularity, removes saturation, keeps SUPG-PT stable, and preserves some U-NOCI-RT failure as a baseline contrast. It does not solve RT vacuity on this dataset.

## 6. Interpretation
SUPG-RT vacuity is no longer explained only by coarse proxy scores.

More likely causes:
- small N=1176
- strict gamma=0.9
- delta=0.05
- conservative RT threshold estimation
- insufficient oracle budget relative to uncertainty

Current KITTI combined is a pipeline benchmark, not a usable non-degenerate SUPG-RT benchmark.

## 7. Decision
- Stop tuning KITTI combined.
- Keep `count_conf_hybrid` as the default proxy rule for future count-based experiments.
- Move to a larger real video dataset before running RT-focused experiments.

## 8. Next Dataset Requirements
- N >= 10,000 frames
- positive rate in the 1% to 20% range
- continuous proxy score
- enough negative and positive frames
- preferably traffic/road video
- ability to materialize proxy/oracle scores once and reuse them

## 9. Next Experimental Plan
1. Find/download a larger traffic video dataset.
2. Materialize YOLOv8n/YOLOv8x scores.
3. Calibrate the count threshold.
4. Run a 5-trial smoke.
5. If non-vacuous, run 20 trials.
6. Then run 100 trials.

## 10. BDD100K Smoke (2026-05-20)

### Dataset
- **Source**: BDD100K Hirundo validation subset (HuggingFace)
- **N**: 10,000 images (1280x720 JPEG, driving/dashcam scenes)
- **License**: BSD-3-Clause
- **Download**: Non-interactive via curl from HuggingFace CDN

### Query
- **Predicate**: count_car(frame) >= 13
- **Calibrated K**: 13 (from oracle counts)
- **Positive rate**: 9.92% (992 / 10,000)
- **proxy_score unique**: 9,287 / 10,000

### SUPG Results (20 trials, gamma=0.9, delta=0.05, budget=1000)

| method | qtype | failure_rate | mean_precision | mean_recall | mean_selected_n | selected_n/N | vacuous |
|--------|-------|-------------|----------------|-------------|-----------------|-------------|---------|
| U-NOCI-RT | rt | 0.50 | 0.343 | 0.903 | 2,723 | 0.272 | no |
| U-CI-RT | rt | 0.00 | 0.099 | 1.000 | 10,000 | 1.000 | yes |
| **SUPG-RT** | **rt** | **0.00** | **0.196** | **0.973** | **5,048** | **0.505** | **no** |
| U-NOCI-PT | pt | 0.80 | 0.487 | 0.140 | 161 | 0.016 | no |
| SUPG-PT | pt | 0.00 | 1.000 | 0.274 | 272 | 0.027 | no |

### Key Outcome
**SUPG-RT is non-vacuous on BDD100K.** This is the first real-video benchmark where SUPG-RT
demonstrates non-trivial selection behavior:
- selected_n/N = 0.505 (selects ~50% of frames)
- recall = 97.3% (well above gamma=0.9)
- failure_rate = 0.0 (no guarantee violations)

SUPG-PT is also stable: precision = 1.0, recall = 27.4%, low variance across seeds.

### Comparison with KITTI Combined
| Metric | KITTI combined | BDD100K |
|--------|---------------|---------|
| N | 1,176 | 10,000 |
| K | 15 | 13 |
| positive rate | 13.78% | 9.92% |
| proxy_score unique | 1,102 | 9,287 |
| SUPG-RT selected_n/N | 1.000 (vacuous) | 0.505 (non-vacuous) |
| SUPG-PT precision | 1.0 | 1.0 |

### Conclusion
BDD100K is a suitable benchmark for G-ARC SUPG experiments. The larger N and higher proxy
score diversity enable non-vacuous SUPG-RT behavior. Recommended as the primary real-frame
benchmark going forward.

Full report: [bdd100k_smoke/report.md](bdd100k_smoke/report.md)

## 11. BDD100K Formal 100-Trial Run (2026-05-20)

100-trial formal experiment confirming the 20-trial smoke results.

### SUPG Results (100 trials, gamma=0.9, delta=0.05, budget=1000)

| method | qtype | failure_rate | mean_precision | mean_recall | mean_selected_n | selected_n/N | vacuous |
|--------|-------|-------------|----------------|-------------|-----------------|-------------|---------|
| U-NOCI-RT | rt | 0.40 | 0.336 | 0.907 | 2,769 | 0.277 | no |
| U-CI-RT | rt | 0.00 | 0.099 | 1.000 | 10,000 | 1.000 | yes |
| **SUPG-RT** | **rt** | **0.00** | **0.185** | **0.977** | **5,417** | **0.542** | **no** |
| U-NOCI-PT | pt | 0.85 | 0.440 | 0.128 | 148 | 0.015 | no |
| SUPG-PT | pt | 0.00 | 1.000 | 0.275 | 273 | 0.027 | no |

### Key Confirmations
- **SUPG-RT non-vacuous**: selected_n/N = 0.542 over 100 trials (consistent with 20-trial 0.505)
- **SUPG-RT recall guarantee**: failure_rate = 0.0, mean_recall = 0.977 > gamma = 0.9
- **SUPG-PT stable**: precision = 1.0, recall = 0.275, low variance
- **No errors**: error_count = 0 across all 500 method-trial combinations

### Status
BDD100K is now the primary frame-level real-road benchmark for G-ARC.
The non-vacuous SUPG-RT frame-level benchmark problem is resolved on BDD100K (image-level, no temporal continuity).

**Limitation**: BDD100K val is an image-level benchmark. Temporal video/clip-level
benchmarking still requires UA-DETRAC or other continuous video datasets.

Full report: [bdd100k_formal_100trials/report.md](bdd100k_formal_100trials/report.md)

## 12. ABae Side Reproduction Note

ABae (Aggregation with Expensive Predicates) minimal reproduction was completed as a
side track using the same cached BDD100K data. ABae is for aggregation queries
(AVG/COUNT WHERE predicate), not selection queries (SUPG). The ABae modules, synthetic
experiments, and BDD100K real-frame experiments are documented separately in
[abae_reproduction_status.md](abae_reproduction_status.md). No SUPG results were modified.
