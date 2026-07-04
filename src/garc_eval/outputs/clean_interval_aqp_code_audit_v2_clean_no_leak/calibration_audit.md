# Calibration Audit

Verdict: **PASS**

- Calibration target labels observed: `['answer_iou_0_3']`
- Recomputed Brier mismatches: `0`
- Empty return sets separated from precision satisfaction: `True`
- Top-score max p_answer range by budget:

| budget | mean_max_p | min_max_p | mean_sample_positive_rate |
| --- | --- | --- | --- |
| 5 | 0.142857 | 0.142857 | 0 |
| 10 | 0.0833333 | 0.0833333 | 0 |
| 20 | 0.25 | 0.25 | 0 |
| 40 | 0.25 | 0.25 | 0.05 |
| 80 | 0.214286 | 0.214286 | 0.1 |

This audit reports 5-bin ECE and clean v2 emits per-bin calibration details in `calibration_bins_v2_clean.csv`.
