# Frozen Online Activity Replication Contract

```text
CURRENT_METHOD = M8_SAFE_ENGINEERING_BASELINE
ONLINE_MACRO_ACTIVITY = NOT_ESTABLISHED
M10_FIXED_COVERAGE_DEBT = NOT_IMPLEMENTED
M11_ADAPTIVE_DEBT = PROHIBITED
FORMAL_METHOD_RANKING = BLOCKED_PENDING_EXTERNAL_RUNTIME_ATTESTATION
```

## Validation design

The two existing complete videos remain design/debug-only. Before any result,
pseudo-reference event count, or activity outcome is inspected, add at least
two independent complete videos as development-validation inputs. Four or more
new videos are the preferred scale. Video selection is based only on complete
timeline access, seekability, hash-freezability, duration, session/source
independence, and diversity of road/traffic/visual condition — never event
density or apparent cut-in frequency.

Each selected video must materialize: video manifest; complete unit timeline;
frozen unit-local SCAN outputs; determinism audit; full-context Oracle
pseudo-reference; reference-independence audit; visible-subset replay;
candidate-event mapping; full-scan exposure ceiling; and controlled-warm cost
sample. A low full-scan exposure ceiling blocks mechanism interpretation.

## Frozen confirmatory matrix

```text
B0 = ANYTIME_LARGEST_GAP
A1 = ONLINE_COMBINED_ACTIVITY
A2 = SHUFFLED_ACTIVITY
A3 = TIME_INDEX_ONLY
A4 = NO_SHRINKAGE_ACTIVITY
```

Region length, microchunk length, online activity components, shrinkage formula,
minimum support, budget, checkpoints, evaluator metrics, and all controls are
frozen before new references or results are examined. Run leave-best-region-out,
region-contribution concentration, per-video paired comparisons, and 1/2/4/8
action low-budget prefixes. Do not run M0–M9 again, M10/M11, RL/Bandit/SMDP,
CONFIRM, M6, M9, or time-index as a policy candidate.

## Progression gates for M10

All gates must pass on validation videos:

1. Activity minus Largest-Gap exposure AUC has positive macro-average and is
   nonnegative on a majority; with exactly two validation videos, both must be
   positive.
2. Combined activity exceeds shuffled activity on macro-average and on a
   majority of videos.
3. Combined activity exceeds time-index-only on macro-average.
4. Leave-best-region-out remains positive over Largest-Gap and no single region
   supplies 50% or more of total positive contribution.
5. Shrunk activity exceeds raw activity on multiple videos.
6. At 1/2/4/8 actions activity does not systematically underperform
   Largest-Gap.

Only after all gates pass may `M10_FIXED_COVERAGE_DEBT = ALLOWED`. If activity
beats shuffled but not time-index, branch to `TEMPORAL_PRIOR_ANALYSIS`. If
leave-best-region-out fails, branch to `HOTSPOT_DIAGNOSTICS`. If the gates fail,
freeze `ONLINE_MACRO_ACTIVITY = REJECTED_UNDER_CURRENT_OBSERVATION_MODEL`.
