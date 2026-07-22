# PSVR autonomous research synthesis

`AUTONOMOUS_RESEARCH_STATUS = COMPLETE_NO_GO`

`PSVR_TWO_VIDEO_SEARCH = NO_GO`

`PSVR_CORE_METHOD_CANDIDATE = NONE`

`CURRENT_BEST_SIMPLE_BASELINE = FIFO`

`CURRENT_BEST_VALIDATED_CORE_METHOD = NONE`

`DEV_SOURCE_VIDEOS = 2`

`DEV_QUERIES = 2`

`DEV_VIDEO_QUERIES = 4`

`HELD_OUT_OPENED = false`

`NEXT_EXACT_COMMAND = NONE_TERMINAL_NO_GO`

## Strongest conclusion

Under the frozen two-video, two-query, YOLOv8/Y8 physical workload, the permitted rule-based scan, candidate, and VERIFY routes do not produce a stable cross-video gain. H-BOTTLE2 is a valid 96-cell null factorial. The only branch-specific controller, H-STAGE1, was physically valid in 48/48 cells but recovered no event on either V1 task in 12/12 cells, won only V0_Q2, and failed every preregistered substantive quality threshold. The search therefore terminates as `NO_GO`; no method is frozen for generalization.

## Bottleneck evidence

H-RECOVER1 found heterogeneous losses: V0_Q1 is VERIFY-order limited, V0_Q2 and V1_Q1 are scan-exposure limited, and V1_Q2 is a deadline floor only under the original fixed action count. H-STAGE1 exposed reference-positive units on V1 but did not recover events. Actual lifecycle accounting localizes the residual V1_Q1 loss to frontier retention/admission and V1_Q2 to VERIFY order/budget after partial frontier entry.

## Final branch result

Compared with fixed max-gap plus FIFO, ST1 changed macro AnytimeAUC from 0.044962 to 0.047547 (+5.75%), macro F1 from 0.054167 to 0.073333 (+0.019167), total median unique events from 2 to 3, and macro TTFC from 110.906 s to 116.743 s. These miss the frozen thresholds and are confined to one task on V0. The descriptive ST1 result is rejected, not a weak candidate.

## Validity qualification

All formal cells have zero deadline miss, replay, future access, visibility violation, missing snapshot, and invalid ledger. H-STAGE1 exact repeat query signatures agree in only 14/16 method-task-deadline cells, so its stricter preregistered correctness gate fails. Two validity repairs were also required before the valid smoke. These limitations weaken any positive interpretation but do not rescue the negative cross-video result.

The scoped valid Cycle-2, Cycle-3, and fresh latency-profile oracle inference cost is 9546.174106 GPU-seconds. Invalidated interrupted diagnostics are retained but excluded because complete GPU totals are unavailable.

Authoritative terminal artifacts are `outputs/psvr_bottleneck_research/AUDITED_DECISION.json`, `FINAL_REPORT.md`, `ADVERSARIAL_REVIEW.md`, and `COMPLETION_AUDIT.json`.
