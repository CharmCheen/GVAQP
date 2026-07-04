# Implementation Bugfix Report

V2 fixes four implementation-level issues found in v1:

1. Calibration label alignment: CILS now calibrates `answer_iou_0_3` by default, not discovery positivity.
2. Candidate upper bound: dense multiscale, peak multiscale, threshold-merge-v2, blindspot, and boundary-refined proposal families were added.
3. Quota stratification: `quota_stratified` and `uncertainty_stratified` allocate explicit per-stratum quotas and never concat-truncate.
4. Stress score handling: stress tests pass `active_score` through calibration/optimization without later overwrite.
