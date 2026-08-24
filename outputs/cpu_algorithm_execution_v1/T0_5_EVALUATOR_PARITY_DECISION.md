# T0.5 Historical Evaluator Parity Decision

## Verdict

`EVALUATOR_PARITY_UNRESOLVED`

## What passes

The cached public-state predictability screen uses one `expected_metrics` function
for every prediction method. In that screen, always-VERIFY is represented by a
zero probability of SCAN. The reported fold-level `decision_regret` for
`always_verify` and `best_fixed_action` is exactly equal in both held-out videos.
This establishes formula-level parity for the cached classification diagnostic.

## What does not pass

The diagnostic consumes cached branch-Q deltas. It does not replay the policy and
baseline on an identical action trace under identical budget accounting, oracle
calls, episode boundaries, and closed-loop event utility. The branch-Q producer,
the cached classifier, the current `garc_eval` utilities, and the new DATB replay
are not one demonstrated evaluator path.

Therefore the preregistered full parity condition cannot be established from the
available cache. Formula-level equality is not a substitute for trace-level
closed-loop parity.

## Claim consequence

All historical controller/MAB/RL negative claims that depend on this evaluator are
`RETIRED_FOR_CLAIM_USE`. The old results may support only this descriptive claim:

> On two cached source videos and abstract branch-Q costs, the tested public-state
> predictors did not beat the fixed always-VERIFY decision-regret diagnostic.

They do not establish that adaptive planning is intrinsically worse, better, or
unlearnable. `T0.5` does not block the new shared execution path; `T2` instead
depends on `T0` provenance and `M0` shared-evaluator parity.

