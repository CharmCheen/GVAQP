# Sequential unknown-video adversarial audit

Audit status: `PASS_FOR_CACHED_CAUSAL_MECHANISM_STUDY_WITH_LIMITATIONS`

This audit challenges the result in
`SEQUENTIAL_UNKNOWN_VIDEO_STUDY_FINDINGS.md`.  It is not evidence for a
physical-deadline deployment claim.

## 1. Claims under review

The study may support only these claims:

1. the implementation executes a sequential `SCAN -> state update -> choose`
   or `VERIFY -> state/K3 update -> choose` loop;
2. its public policy state does not contain unrevealed oracle labels or
   evaluator reference events;
3. a candidate frozen on the development derivatives improves cached
   early-event recovery over current two-stage and ARC comparators;
4. the observed gain does not establish a universal dynamic selector.

It may not support measured wall-clock safety, physical pipeline parity,
32B-call savings, or cross-video generalization.

## 2. Leakage attacks and outcomes

| Attack | Evidence checked | Outcome |
| --- | --- | --- |
| Read a label during SCAN | `SequentialObservation.revealed_label` is `None`; test asserts the verified-label map remains empty | blocked |
| VERIFY an unscanned unit | environment raises before spending or revealing | blocked |
| Reveal more than the selected unit | VERIFY observation contains one scalar label and the public map adds one key | blocked |
| Put evaluator fields in policy state | public-state schema and fail-closed forbidden-field validator | blocked |
| Change action when only hidden labels change | paired test uses opposite private label tables with identical public state | action invariant |
| Fit the posterior on the primary video | profile construction uses only the two named development derivatives | blocked by execution order |
| Select a method after primary evaluation | `FROZEN_SELECTION.json` is written before `run_grid(... phase="primary_heldout")` | blocked by code order |
| Treat `unknown`/`parse_failure` as positive | strict K3 admits explicit `positive` only | blocked |
| Verify the same unit twice or exceed budget | environment fails closed | blocked |

The evaluator and policy execute in one Python process, but the policy receives
only an immutable `PublicSequentialState`; it is not passed the `Domain`,
oracle map, or reference relation.  This is a tested logical isolation
boundary, not an OS security boundary.  A future physical runner should retain
the repository's process/filesystem evaluator isolation rather than treating
this cached harness as a security sandbox.

## 3. Comparator and metric attacks

- All methods use the same action costs, budget grid, K3 materializer, and
  evaluator.
- ARC is wrapped progressively because its cached selector normally expects a
  complete proxy table.  Therefore `ARC_TWO_STAGE_COMMON` is a shared-runtime
  ARC comparator, not a claim that the historical physical ARC runner was
  executed.
- Deterministic non-ARC policies are not credited with pseudo-replication from
  repeated seeds.  ARC's stochastic rows retain their seed identity.
- Every reported VERIFY target was previously scanned, every admitted action
  completed within its abstract budget, and no probable event was emitted.
- A clean rerun reproduced the complete 385-row artifact inventory and its
  aggregate hash.

## 4. Falsification result

The strongest challenge succeeded: `FIXED_SCAN1_VERIFY1` beat the
development-selected `DYNAMIC_ADAPTIVE_K3_VALUE_V3` on primary mean Anytime
event recall AUC (`0.133` versus `0.122`).  It also beat V3 at SCAN costs
`0.05`, `0.10`, and `0.20`.

This falsifies the strong hypothesis that the current adaptive value function
is the best or universal selector.  It does not falsify the narrower mechanism
that early, broad, label-blind interleaving helps: fixed 1:1 improved mean
Anytime event recall AUC over current two-stage by about 64% and ARC by about
227% in the cached primary replay.

The scientifically valid decision is therefore:

```text
REVISE_STATE
```

`FIXED_SCAN1_VERIFY1` is the strongest observed operational fallback.  V3 is
the strongest valid pre-primary selected dynamic method, but it is not the
strongest observed method.

## 5. Residual uncertainty and rejection rule

The development derivatives are two slices of one source video and do not
carry complete prompt/parser identity.  Costs are abstract, and only one
query-bound primary video is available.  These facts leave domain transfer and
physical cost safety unresolved.

The next dynamic method must learn a conservative advantage over fixed 1:1
from multiple independent, query-identical videos, freeze before a new
held-out video, and use measured action costs.  Reject the dynamic-selector
hypothesis if its lower-confidence advantage fails to exceed fixed 1:1 on that
new holdout without a precision or deadline regression.
