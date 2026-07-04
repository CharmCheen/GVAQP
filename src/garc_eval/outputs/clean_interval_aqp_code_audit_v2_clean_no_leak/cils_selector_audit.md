# CILS Selector Audit

Verdict: **PASS**

- Recomputed selected count in audited CILS sample: `0`
- Max calibrated `p_answer` in audited top-score trials: `0.250000`
- Minimum tau in main curve: `0.500`

Primary rejection reason counts:

| budget | tau | rejection_reason | count |
| --- | --- | --- | --- |
| 5 | 0.5 | below_precision_constraint | 1500 |
| 5 | 0.6 | below_precision_constraint | 1500 |
| 5 | 0.7 | below_precision_constraint | 1500 |
| 5 | 0.8 | below_precision_constraint | 1500 |
| 5 | 0.9 | below_precision_constraint | 1500 |
| 10 | 0.5 | below_precision_constraint | 1500 |
| 10 | 0.6 | below_precision_constraint | 1500 |
| 10 | 0.7 | below_precision_constraint | 1500 |
| 10 | 0.8 | below_precision_constraint | 1500 |
| 10 | 0.9 | below_precision_constraint | 1500 |
| 20 | 0.5 | below_precision_constraint | 3000 |
| 20 | 0.6 | below_precision_constraint | 3000 |
| 20 | 0.7 | below_precision_constraint | 3000 |
| 20 | 0.8 | below_precision_constraint | 3000 |
| 20 | 0.9 | below_precision_constraint | 3000 |
| 40 | 0.5 | below_precision_constraint | 6000 |
| 40 | 0.6 | below_precision_constraint | 6000 |
| 40 | 0.7 | below_precision_constraint | 6000 |
| 40 | 0.8 | below_precision_constraint | 6000 |
| 40 | 0.9 | below_precision_constraint | 6000 |
| 80 | 0.5 | below_precision_constraint | 12000 |
| 80 | 0.6 | below_precision_constraint | 12000 |
| 80 | 0.7 | below_precision_constraint | 12000 |
| 80 | 0.8 | below_precision_constraint | 12000 |
| 80 | 0.9 | below_precision_constraint | 12000 |

Conclusion: CILS max recall 0 is a real consequence of the selector/calibration combination in this artifact, not evidence of a metric recomputation bug. It is still not a trustworthy research conclusion while the feature-only leakage BLOCKER remains.
