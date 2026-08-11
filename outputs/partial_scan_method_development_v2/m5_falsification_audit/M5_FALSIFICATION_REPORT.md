# M5 falsification audit

All macro scores use completed units only. Pseudo-reference events are
evaluator-side metrics only.

## Result: hypothesis not supported for M10 progression

On `PSP_V0_SHORT`, combined activity and shuffled activity have identical AUC
(`244.85`); time-index-only is higher (`363.12`). Thus the activity signal is
not distinguishable from the controls on this video.

On `PSP_V1_LONG`, combined activity exceeds shuffled (`701.82` vs `622.37`),
but leave-best-region-out drops to `366.49`. The apparent gain is consequently
not robust to removal of the most contributing region. Shrinkage is also only
slightly above no-shrinkage (`701.82` vs `681.22`).

```text
ACTIVITY_SHUFFLE_GATE = FAIL_ACROSS_VIDEOS
TIME_INDEX_GATE = FAIL_ON_SHORT_VIDEO
LEAVE_BEST_REGION_OUT_GATE = FAIL_ON_LONG_VIDEO
M10_FIXED_COVERAGE_DEBT = NOT_IMPLEMENTED
M11_ADAPTIVE_DEBT = PROHIBITED
NEXT_REQUIREMENT = ADD_INDEPENDENT_DEVELOPMENT_VALIDATION_VIDEOS
```
