# Safe Coverage SCAN — Method Specification

```text
FINAL_STATE = SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST
DEFAULT_RUNNABLE_POLICY = ANYTIME_LARGEST_GAP
YOLO_GUIDANCE = DISABLED_BY_FAILED_STATIC_GATE
POLICY_INPUT = PublicScanState only
TRAINING = NONE
REFERENCE_ACCESS = PROHIBITED
```

`SafeCoveragePolicy` is a thin audited package over the frozen Sequential,
Uniform-prefix, Anytime Largest-Gap, and Macro Largest-Gap implementations.
The default is Anytime Largest-Gap because it has an anytime geometric
coverage invariant and was the short-video full-horizon winner. The evidence
does not justify silently choosing a policy from video identity, so alternative
modes must be selected explicitly.

Evidence-specific choices: Sequential was strongest on the short video's
physical 60-second horizon; Uniform-prefix on the long video's physical
60-second horizon; Anytime Largest-Gap on the short full replay horizon; Macro
Largest-Gap on the long full replay horizon. These are development findings,
not general routing rules.
