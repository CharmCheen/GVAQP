# 03 Proxy Oracle Relation Audit

## Verdict

GLM's proxy analysis contains a material AUROC bug. The best tie-aware AUROC is `object_count_mean` = 0.627. `score_fusion_geometry_motion`, the score used in replay, is only 0.550. `object_count_mean` is not anti-predictive; it is the strongest audited single feature with AUROC=0.627.

## Evidence

- High-score negatives in the top score quartile: 77, matching the GLM claim of 77.
- Low-score positives below the median score: 17, matching the GLM claim of 17 / 40 = 42.5%.
- Quartile positive rates are non-monotone: Q1=0.081, Q2=0.116, Q3=0.151, Q4=0.112.
- B=80 top-proxy finds 10/40 positives; the random expectation is close because base rate is 11.5%.
- B=80 top-`object_count_mean` finds 15/40 positives, beating both score-fusion top-proxy and the reported score-fusion diversity prefilter.

## Interpretation

`score_fusion != semantic event` is supported, and score-fusion direct ranking is weak/non-monotone. The stronger claim that `object_count_mean` is anti-predictive is false. Stage 3 and Stage 5 should be recomputed with corrected AUROC and object-count baselines before paper-level method claims.

Detailed metrics are in `tables/proxy_oracle_recomputed_metrics.csv`.
