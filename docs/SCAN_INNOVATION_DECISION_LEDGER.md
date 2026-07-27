# SCAN Innovation Decision Ledger

```text
CONTRACT = YOLO_GUIDED_SCAN_AUTONOMOUS_RESEARCH_V1
STATUS = FROZEN_BEFORE_NEW_EXPERIMENTS
MAX_AGENTIC_CYCLES = 12
MAX_ALGORITHM_HYPOTHESES = 8
CURRENT_CYCLE = 4
CURRENT_HYPOTHESIS = NONE
RESEARCH_LOOP_STATUS = COMPLETE
LEGAL_FINAL_STATE = SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST
```

No scheduler, batching, novelty-exit, or physical branch may start before the
static observability Gate passes.

## Cycle 1 — YGS-H000

```text
OBSERVED = Parent replay has 110 runs/880 checkpoints; controlled-warm physical has 32 runs.
DERIVED = The strongest causal comparator depends on video and horizon. M8 is not strongest.
DECISION = ACCEPTED; freeze per-video/per-horizon baselines.
MAIN_ALTERNATIVE = A single universal policy could be preferred for deployment simplicity, but would be a weaker scientific comparator.
UNCERTAINTY = Macro Largest-Gap has no prior physical run.
NEXT_ACTION = Reverify frozen Q1-L semantics, determinism, leakage boundary, and actual cost.
```

## Cycle 2 — YGS-H001

```text
OBSERVED = Q1-L two-run byte determinism PASS; leakage audit PASS; cost ratio 0.032730.
OBSERVED = Independently recomputed Recall@20 0.328571/0.321244 and AUC 0.593571/0.612979 exactly match parent metrics.
DERIVED = Low-rate YOLO has stable but insufficient static region-value observability.
DECISION = ACCEPT sensing primitive; scheduler remains prohibited.
MAIN_ALTERNATIVE = The Recall deficit may reflect non-identifiability rather than insufficient sampling.
KEY_UNCERTAINTY = Whether higher-rate detections resolve ambiguity specifically near the allocation boundary.
NEXT_ACTION = Run capped, uncertainty/boundary-selected Q2 preview with actual cost accounting.
```

## Cycle 3 — YGS-H002

```text
OBSERVED = Q2 two-run deterministic; combined Q1+Q2 cost ratio 0.052925.
OBSERVED = Recall@20 0.328571/0.316062; AUC 0.593571/0.609145.
DERIVED = Raising YOLO detection rate near the allocation boundary does not add stable residual event information.
DECISION = REJECT; scheduler prohibited.
MAIN_ALTERNATIVE = Directional motion, not detection sampling density, may be the missing observable.
KEY_UNCERTAINTY = Whether high-rate lateral/expansion flow has cross-video value.
NEXT_ACTION = One final materially different selected-motion hypothesis (YGS-H003); otherwise freeze safe coverage.
```

## Cycle 4 — YGS-H003

```text
OBSERVED = Two-run deterministic 5-FPS directional motion; combined cost ratio 0.070582.
OBSERVED = Recall@20 0.328571/0.326425; AUC 0.593571/0.614326.
DERIVED = Motion helps the long video marginally but does not improve the short video or cross the static observability threshold.
DECISION = REJECT; do not build scheduler, batching, novelty, or new physical branch.
MAIN_ALTERNATIVE = A different task-aligned observable or more diverse frozen videos may identify value, but that is a new research program.
KEY_UNCERTAINTY = Results are development-only on two videos and pseudo-reference events.
NEXT_ACTION = Deliver and audit a runnable public-state-only safe coverage package.
```

## Finalization

```text
RUNNABLE_FALLBACK = garc_eval.scan_scheduler.SafeCoveragePolicy
CONFIG = configs/safe_coverage_scan.yaml
INDEPENDENT_FINAL_AUDIT = PASS (12/12 checks)
RELEVANT_TESTS = PASS (14)
ARTIFACT_MANIFEST = 65 files, all hashes verified
NEW_SCHEDULER = NOT_IMPLEMENTED_BY_FAILED_STATIC_GATE
NEW_PHYSICAL_RUNS = NOT_RUN_BY_FAILED_STATIC_GATE
```
