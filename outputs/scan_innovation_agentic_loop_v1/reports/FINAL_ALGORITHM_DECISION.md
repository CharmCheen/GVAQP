# Final Algorithm Decision

```text
FINAL_STATE = SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST
SELECTED_YOLO_GUIDED_SCAN_ALGORITHM = NONE
RUNNABLE_FALLBACK = garc_eval.scan_scheduler.SafeCoveragePolicy
SCHEDULER_LAYER = PROHIBITED
NEW_PHYSICAL_VALIDATION = NOT_ALLOWED_AFTER_STATIC_GATE_FAILURE
```

The runnable fallback is delivered and tested. It is not presented as a new
YOLO-guided innovation. The experimental contribution is a falsified design:
low-rate YOLO has ranking signal, but selective high-rate detection and
directional motion do not make that signal robust or cost-effective enough to
control SCAN on both videos.
