# Calibration Audit

Verdict: **FAIL**

- Calibration target labels observed: `['answer_iou_0_3']`
- Recomputed Brier mismatches: `1890`
- Empty return sets counted as precision violations: `True`
- Top-score max p_answer range by budget:

| budget | mean_max_p | min_max_p | mean_sample_positive_rate |
| --- | --- | --- | --- |
| 5 | 0.142857 | 0.142857 | 0 |
| 10 | 0.0833333 | 0.0833333 | 0 |
| 20 | 0.166667 | 0.166667 | 0 |
| 40 | 0.25 | 0.25 | 0.05 |
| 80 | 0.25 | 0.25 | 0.1 |

This audit reports 5-bin ECE as requested. The v2 artifact appears to use a 10-bin ECE, so ECE is not treated as an exact mismatch gate.
