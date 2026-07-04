# Top p_answer Bin Summary

**Diagnostic only.** Reference gate FAIL (6 true interval events).

Configuration reconstructed:
- pilot_policy = answer_quality_proxy_top
- calibration_model = beta_bin_strata_lower
- budget = 80, seed = 0
- source: cils_calibration_repair_smoke_v1/smoke_candidate_p_answer.csv

Top bin p_answer = 0.666667

| stat | value |
| --- | --- |
| n candidates in bin | 87 |
| n answer_iou_0_3 = True (TP) | 16 |
| n answer_iou_0_5 = True | 10 |
| n matches true interval event | 21 |
| n point-anchor only | 14 |
| n background (no event match) | 52 |
| bin precision (TP / n) | 0.1839 |

All candidates share overlap_group_id = ['og2_00000'].

True interval events represented in bin: ['realcartest_event_0022', 'realcartest_event_0028', 'realcartest_event_0029', 'realcartest_event_0033', 'realcartest_event_0034', 'realcartest_event_0037']
