# PSVR Two-Video Autonomous Loop

`TWO_VIDEO_DEV_BENCHMARK = PASS`

`SELECTED_PROXY_FAMILY = YOLOV8`

`SELECTED_PROXY_CONFIG = Y8`

`PROXY_REGIME_REVALIDATION = PASS`

`H_EXPOSE2_REVISION = R3_FIXED_10_SECOND_TEMPORAL_NMS_COMPLETE`

`H_EXPOSE2_DECISION = REJECT`

`H_EXPOSE2_ABLATION = NOT_RUN_HYPOTHESIS_REJECTED`

`TWO_VIDEO_CORE_SIGNAL = ABSENT`

`MACRO_ANYTIME_AUC = 0.045006628`

`MACRO_F1 = 0.054166667`

`TOTAL_UNIQUE_CONFIRMED_EVENTS = 2.000000`

`MACRO_TTFC = 110.820895`

`TOTAL_GPU_SECONDS = 20125.517495`

`DEV_SOURCE_VIDEOS = 2`

`DEV_QUERIES = 2`

`DEV_VIDEO_QUERIES = 4`

`EVIDENCE_LEVEL = E4_TWO_VIDEO_DEVELOPMENT_NEGATIVE_OR_NONMECHANISTIC`

`HELD_OUT_OPENED = false`

`CURRENT_BEST_PSVR_METHOD = fifo`

`PSVR_METHOD_USABILITY = NOT_YET`

`AUTONOMOUS_RESEARCH_STATUS = PAUSED_INPUT_REQUIRED`

`NEXT_EXACT_COMMAND = NONE_INPUT_REQUIRED__PROVIDE_THIRD_INDEPENDENT_SOURCE_VIDEO`

## Decision basis

R3 improves 0/4 tasks over the task-specific best baseline, passes none of the
four preregistered substantive thresholds, and has no V1 quality contribution.
The 72-cell physical and correctness gates pass, so this is `REJECT`, not
`BLOCKED`. The mechanism ablation was not run because the hypothesis was
rejected after its only permitted revision.

The reported macro quality and event values are for the current descriptive
best method, FIFO. Its advantage is driven by one true-positive V0_Q1 event and
does not establish a cross-video method. `TOTAL_GPU_SECONDS` is the audited
end-to-end two-video loop cost, including reference construction, profiling,
proxy pilot, initial H-EXPOSE2, and R3.

## Evidence boundary

This is development evidence from two independent source videos and four
video-query tasks. It does not satisfy the three-video usability gate, does
not open held-out data, and does not support a paper-ready claim.
Candidate exposure has completed its original design and only allowed revision
on these two videos. Evaluating another core route now requires a third
independent source video to avoid further adaptive search on V0/V1.
