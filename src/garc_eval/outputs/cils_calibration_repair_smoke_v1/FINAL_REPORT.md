# FINAL REPORT: CILS Calibration Repair Smoke V1

## 1. Executive Summary

- Smoke ran through: **yes**.
- BLOCKER: **no**.
- Fixed policy makes CILS non-empty: **yes**.
- Best interval_eval IoU@0.3 recall / precision: `0.167` / `1.000`.
- Best empty_return_rate: `0.000` at B=`80`, tau=`0.5`.
- Decision: **WEAK GO**. This is smoke evidence only, not final algorithm validation.

## 2. Protocol

Fixed `answer_quality_proxy_top + beta_bin_strata_lower`; budgets `[5, 10, 20, 40, 80]`; tau `[0.5, 0.6, 0.7, 0.8, 0.9]`; seeds `0..99`. Primary interval-IoU evaluation uses only interval_eval events. Point-anchor events are excluded from the main interval claim.

## 3. Pilot And Calibration

Pilot summary:

| budget | mean_positive_rate | zero_positive_rate | mean_interval_eval_positive_rate |
| --- | --- | --- | --- |
| 5 | 0 | 1 | 0 |
| 10 | 0 | 1 | 0 |
| 20 | 0.05 | 0 | 0.05 |
| 40 | 0.05 | 0 | 0.05 |
| 80 | 0.125 | 0 | 0.125 |

Calibration summary:

| budget | mean_brier | mean_ece | mean_max_p | mean_p |
| --- | --- | --- | --- | --- |
| 5 | 0.0907872 | 0.0294234 | 0.0714286 | 0.0704175 |
| 10 | 0.093472 | 0.0593782 | 0.0416667 | 0.0404626 |
| 20 | 0.0931888 | 0.0554765 | 0.135643 | 0.0443644 |
| 40 | 0.0946414 | 0.0669026 | 0.215973 | 0.0346733 |
| 80 | 0.0939073 | 0.039445 | 0.666667 | 0.0726247 |

## 4. CILS Smoke Results

Best interval_eval rows:

| budget | tau | interval_recall | interval_recall_iou_0_5 | precision | expected_precision | empty_return_rate | mean_returned | avg_duration | p95_duration | duplicate_rate | background_duration_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 80 | 0.5 | 0.166667 | 0 | 1 | 0.666667 | 0 | 1 | 16 | 16 | 0 | 0 |
| 80 | 0.6 | 0.166667 | 0 | 1 | 0.666667 | 0 | 1 | 16 | 16 | 0 | 0 |
| 5 | 0.5 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 5 | 0.6 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 5 | 0.7 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 5 | 0.8 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 5 | 0.9 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 10 | 0.5 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 10 | 0.6 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 10 | 0.7 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 10 | 0.8 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 10 | 0.9 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 20 | 0.5 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 20 | 0.6 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 20 | 0.7 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 20 | 0.8 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 20 | 0.9 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 40 | 0.5 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 40 | 0.6 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 40 | 0.7 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 40 | 0.8 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 40 | 0.9 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 80 | 0.7 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 80 | 0.8 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 80 | 0.9 | 0 | 0 | nan | 0 | 1 | 0 | 0 | 0 | 0 | 0 |

## 5. Baseline Comparison

See `smoke_vs_baseline_comparison.csv` and `smoke_baseline_report.md`. Main comparison is interval_eval only; oracle p-answer is diagnostic only.

## 6. Point-Anchor Separate Metrics

| budget | tau | point_any_overlap | point_center_hit | point_containment |
| --- | --- | --- | --- | --- |
| 5 | 0.5 | 0 | 0 | 0 |
| 5 | 0.6 | 0 | 0 | 0 |
| 5 | 0.7 | 0 | 0 | 0 |
| 5 | 0.8 | 0 | 0 | 0 |
| 5 | 0.9 | 0 | 0 | 0 |
| 10 | 0.5 | 0 | 0 | 0 |
| 10 | 0.6 | 0 | 0 | 0 |
| 10 | 0.7 | 0 | 0 | 0 |
| 10 | 0.8 | 0 | 0 | 0 |
| 10 | 0.9 | 0 | 0 | 0 |
| 20 | 0.5 | 0 | 0 | 0 |
| 20 | 0.6 | 0 | 0 | 0 |
| 20 | 0.7 | 0 | 0 | 0 |
| 20 | 0.8 | 0 | 0 | 0 |
| 20 | 0.9 | 0 | 0 | 0 |
| 40 | 0.5 | 0 | 0 | 0 |
| 40 | 0.6 | 0 | 0 | 0 |
| 40 | 0.7 | 0 | 0 | 0 |
| 40 | 0.8 | 0 | 0 | 0 |
| 40 | 0.9 | 0 | 0 | 0 |

## 7. Sanity/Leakage

Sanity and leakage checks are in `sanity_checks.md` and `leakage_audit.md`. BLOCKER: `no`.

## 8. Research Implication

Calibration repair is worth continuing as a smoke-tested fix for empty return, but the evidence is weak because interval_eval has only six events and the best recall remains about one event. The selector remains worth continuing under fixed no-leak calibration, not as a final CILS validation. A true interval reference remains needed, and audited proposal repair should remain a baseline before elevating CILS as the main AQP route.

## 9. Next Actions

1. Run one formal no-leak replication on a larger true-interval reference before claiming stability.
2. Keep interval_eval and point-anchor metrics split in every CILS report.
3. Compare fixed repaired CILS against audited proposal repair using the same interval_eval subset.
