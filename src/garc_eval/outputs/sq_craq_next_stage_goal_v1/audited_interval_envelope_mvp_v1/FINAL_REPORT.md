# Audited Interval Envelope MVP V1

## Answers

1. Can outside-envelope audit detect systematic cheap-signal misses? **Partially, diagnostically.** Replay finds outside positive candidates and raises `CANNOT_CERTIFY` when residual positives remain.
2. Does repair improve envelope recall or lower miss risk? **Sometimes, diagnostic only.** Label-informed repair can add missed positives, but this is not a formal guarantee.
3. Current diagnostic certificate? **Only `CERTIFIED_DIAGNOSTIC` for low estimated residual-risk cases; no formal certificate.**
4. Stress cases triggering cannot-certify: `proxy_accurate, proxy_blinded_low_density, proxy_hard_negative_boost, proxy_randomized`
5. Should this become SQ-CRAQ mainline? **Yes, as the next diagnostic mainline**, because it addresses miss risk directly instead of continuing CILS tuning.

## Best Envelope Rows

| envelope_baseline | candidate_count_budget | mean_recall_iou_0_3 | mean_recall_iou_0_5 | mean_candidate_count | mean_total_duration | mean_coverage_per_duration | mean_miss_upper | cannot_certify_rate | audit_oracle_budget | coverage_per_duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1_top_score_envelope | 20 | 0.666667 | 0.5 | 20 | 374 | 0.666667 | 0.263305 | 1 | 1 | 0.00178253 |
| E0_threshold_merge | 20 | 0.5 | 0.166667 | 20 | 1772 | 0.5 | 0.203023 | 1 | 1 | 0.000282167 |
| E0_threshold_merge | 400 | 0.5 | 0.333333 | 325 | 3628 | 0.5 | 0.233596 | 1 | 1 | 0.000137817 |
| E3_craq_stratified_repair | 20 | 0.383333 | 0.133333 | 15.7 | 196.9 | 0.383333 | 0.17712 | 0.95 | 20 | 0.00194684 |
| E0_threshold_merge | 50 | 0.333333 | 0.333333 | 50 | 1956 | 0.333333 | 0.13821 | 1 | 1 | 0.000170416 |
| E0_threshold_merge | 200 | 0.333333 | 0 | 200 | 3124 | 0.333333 | 0.13821 | 1 | 1 | 0.000106701 |
| E1_top_score_envelope | 100 | 0.333333 | 0.166667 | 100 | 2700 | 0.333333 | 0.13821 | 1 | 1 | 0.000123457 |
| E0_threshold_merge | 100 | 0.333333 | 0 | 100 | 2580 | 0.333333 | 0.171356 | 1 | 1 | 0.000129199 |
| E1_top_score_envelope | 50 | 0.333333 | 0.166667 | 50 | 2028 | 0.333333 | 0.171356 | 1 | 1 | 0.000164366 |
| E3_craq_stratified_repair | 50 | 0.191667 | 0.0666667 | 33.25 | 1841.8 | 0.191667 | 0.118941 | 0.8 | 20 | 0.000104065 |

All outputs are `DIAGNOSTIC_ONLY`; `E2_dense_lattice_upper` and repair positives use labels and are not deployable selectors.
