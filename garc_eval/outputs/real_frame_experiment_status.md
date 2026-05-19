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
