# Internal-consistency repair assessment

## Result

`R1_STATE = BLOCKED_SCIENTIFIC_SPEC_CONFLICT`.

The development-only seed visibility leak has a direct implementation repair:
remove the seed-bearing `episode_id` from `VisibleState` while retaining an
evaluator-private pairing identity. That repair alone cannot unblock R1.

The decision-critical M1 defect is not an implementation bug. D4 requires a
non-clairvoyant exact expectation conditional on the complete visible history.
Frozen D3 specifies a deterministic seed-to-complete-episode construction and
post-execution evaluator truth, but does not specify an observation likelihood,
posterior state, conditional transition sampler, or the latent/visible status
of seed, split index, parameters, and RNG state. The existing proposal records
these as an amendment requiring explicit authorization.

Choosing any conditional sampler now would add a scientific model assumption.
Using the realized episode is explicitly rejected as clairvoyant; exposing a
seed/episode parameter changes the information structure. Therefore this
assessment does not repair, re-preregister, smoke-test, or freeze R1.

## Required authorized next action

An explicit result-blind D3/D4 amendment must select and freeze a Bayesian
visible-history kernel (observation likelihood, posterior state, independent
conditional sampler, RNG draw order, and visibility classification), followed
by an independent conformance implementation. Only then can split isolation and
R1 preregistration be completed without silently changing the hypothesis.
