# 02 Proxy Oracle Recompute

## Corrected Ranking

- Best hindsight proxy by AUROC: `person_count_max`.
- Deployable corrected default used for calibrated/simple baselines: `object_count_mean`.
- `object_count_mean` AUROC: 0.627.
- `score_fusion_geometry_motion` AUROC: 0.550.

## GLM AUROC Bug Diagnosis

The likely source is the custom AUROC implementation in `stage3_5_analysis_replay.py`, not a join mismatch. The canonical join has 347/347 aligned anchors and no duplicate IDs. The GLM function over-counts pair contributions and reports percent-like values; tie-aware Mann-Whitney AUROC and top-k yield show `object_count_mean` is positive, not anti-predictive.

## Direction And Deployment

`object_count_mean` is a hindsight-corrected strong simple proxy on dataset3, but it was known from prior realcartest work and is deployable as a cheap feature. `top_proxy_best_hindsight` remains diagnostic because selecting the best feature after full labels leaks evaluation labels.

See `tables/proxy_oracle_metrics_corrected.csv`, `tables/proxy_quartile_positive_rates.csv`, and `tables/proxy_topk_yield.csv`.
