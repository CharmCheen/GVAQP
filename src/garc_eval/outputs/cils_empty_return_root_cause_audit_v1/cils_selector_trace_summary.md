# CILS Selector Trace Summary

Focus cells:

| budget | tau | rejection_reason | count | total | fraction |
| --- | --- | --- | --- | --- | --- |
| 40 | 0.6 | p_answer_too_low | 120000 | 120000 | 1 |
| 80 | 0.5 | p_answer_too_low | 240000 | 240000 | 1 |
| 80 | 0.6 | p_answer_too_low | 240000 | 240000 | 1 |
| 80 | 0.7 | p_answer_too_low | 240000 | 240000 | 1 |
| 80 | 0.8 | p_answer_too_low | 240000 | 240000 | 1 |

Across audited clean v2 main cells, rejection is dominated by `p_answer_too_low` / `below_precision_constraint` when calibrated probabilities never reach the requested `tau_p`.
