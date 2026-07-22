# PSVR bottleneck-resolution final report

## Final state

```text
H_RECOVER1_DECISION = COMPLETE_HETEROGENEOUS_BOTTLENECK
TASK_BOTTLENECK_MAP = V0_Q1 VERIFY order; V0_Q2 scan exposure recovered;
                      V1_Q1 frontier retention/admission;
                      V1_Q2 VERIFY order/budget after frontier entry

H_BOTTLE2_DECISION = REJECT_FIXED_FACTORIAL_HETEROGENEOUS_BOTTLENECK
SCAN_RECOVERY_SIGNAL = ABSENT
VERIFY_SELECTION_SIGNAL = ABSENT
SCAN_VERIFY_INTERACTION = ABSENT
PROXY_CANDIDATE_GENERATION_BOTTLENECK = ABSENT
CURRENT_DEADLINE_FLOOR = NOT_GLOBAL

BRANCH_HYPOTHESIS = H-STAGE1
BRANCH_DECISION = REJECT_NO_CROSS_VIDEO_QUALITY_SIGNAL
KEY_ABLATION_OR_REVISION = NOT_RUN_BRANCH_REJECTED

CURRENT_BEST_SIMPLE_BASELINE = FIFO
CURRENT_BEST_PSVR_METHOD = NONE

MACRO_ANYTIME_AUC = 0.04754672840190052  # rejected ST1 descriptive result
MACRO_F1 = 0.07333333333333333
TOTAL_UNIQUE_CONFIRMED_EVENTS = 3
MACRO_TTFC = 116.74327754148936
TOTAL_GPU_SECONDS = 9546.174105757

PSVR_CORE_METHOD_CANDIDATE = NONE
PSVR_TWO_VIDEO_SEARCH = NO_GO
AUTONOMOUS_RESEARCH_STATUS = COMPLETE_NO_GO

DEV_SOURCE_VIDEOS = 2
DEV_QUERIES = 2
DEV_VIDEO_QUERIES = 4
HELD_OUT_OPENED = false
NEXT_EXACT_COMMAND = NONE_TWO_VIDEO_RULE_SEARCH_TERMINAL
```

## Evidence and decisions

H-RECOVER1 reconstructed 2,772 execution-chain rows from 72 valid H-EXPOSE2 traces with zero
new physical calls. It found V0_Q1 VERIFY-order regret, V0_Q2 scan headroom, V1_Q1 alternative
scan recoverability, and a V1_Q2 floor only at the original 12-scan action ceiling. The global
candidate conversion ratios were diagnostic for already exposed positives and were not assumed to
generalize to V1.

H-BOTTLE2 completed 96/96 physical cells. C00 reproduced all 24 historical FIFO cells; there were
zero failures, deadline misses, replays, future accesses, visibility violations, missing snapshots,
or invalid ledgers. C10/C01/C11 had the same macro F1 and unique-event outcome as C00. Their AUC
differences were about 1–1.6%, below every threshold, and none improved a V1 task.

H-STAGE1 completed 48/48 valid cells after a fresh same-topology profile. F0 reproduced 24/24 C10
behavioral endpoints. ST1 converted large unused deadlines into 29–50 scans on V0 and 33–45 scans
on V1, with 4–9 physical VERIFY calls. It recovered two V0_Q2 events in 6/6 cells, one V0_Q1 event
in 6/6, and zero events for both V1 tasks in 12/12.

| Task | F0 events | ST1 events | ST1 positive units | Actual residual bottleneck |
|---|---:|---:|---:|---|
| V0_Q1 | 1 | 1 | 2.0 | Extra allocation worsens AUC; VERIFY-order signal not improved |
| V0_Q2 | 1 | 2 | 5.0 | Scan exposure successfully recovers the second event |
| V1_Q1 | 0 | 0 | 2.5 | Candidates created, median frontier entry 0: retention/admission |
| V1_Q2 | 0 | 0 | 4.0 | Median 2 candidates enter/survive, none verified: order/budget |

ST1 versus F0: macro AUC 0.044962→0.047547 (+5.75%), macro F1 0.05417→0.07333
(+0.01917), censored TTFC 110.91→116.74 seconds (worse), and total unique events 2→3.
It wins only V0_Q2. Consequently it fails cross-video direction and all four substantive
thresholds; this is not eligible for the single revision.

## Validity, cost, and uncertainty

Formal H-BOTTLE2 plus H-STAGE1 used 9,223.428 GPU-seconds. The 20-sample fresh latency profile
adds 322.746 oracle-inference GPU-seconds, yielding the reported 9,546.174 seconds. Invalidated
pre-gate diagnostics are retained separately and excluded from this formal total; interrupted
diagnostics lack a complete total-GPU summary and are not used in any comparison.

Physical safety/durability passed. The stricter preregistered exact-repeat condition failed in
ST1/V1_Q1/T_transition and ST1/V1_Q2/T_transition because remaining-time variation produced 8
versus 9 queries. All 16 semantic event cells were repeat-consistent, so the negative conclusion is
robust, but a positive method claim would be invalid. The cycle also required two validity repairs
(profile freshness and restoration of historical action targets), a disclosed procedural deviation.

The main competing explanation is that a learned or materially different scheduler could predict
which visible frontier candidate deserves VERIFY. That route is outside the frozen search contract
and cannot be used to avoid this NO_GO.
