# Proposed D3/D4 consistency amendment — not activated

Status: `PROPOSED_REQUIRES_EXPLICIT_AUTHORIZATION`.

This proposal is result-blind: no development policy metric, held-out toy
metric, physical result, Oracle call, GPU job, or real held-out datum exists.
It is not part of the current freeze and does not authorize any runner.

## Decision-critical uncertainty

The frozen D3 law defines a ratio draw but omits it from the ordered SplitMix64
schedule. D4 then requires M1 to compute a conditional expectation given the
policy-visible history, while D3 supplies only a complete seeded latent episode
and post-execution evaluator truth. Neither choice is recoverable uniquely from
the frozen artifacts.

Offline grouping is not necessarily contradictory. It can be treated as a
pre-sampled latent partition: SCAN reveals only assignments for newly emitted
witnesses, never future members or correctness. Because witness IDs are ordered
by region and creation order, the minimum-member hypothesis ID does not need to
be renamed by a later region. Closing a group may suppress its still-hidden
future members, which is the preregistered over-merge opportunity loss.

Likewise, lazy action-ledger costs can be retained as a common response tape:
each paired policy begins from the same post-construction RNG state and consumes
the next cost draw when it starts an action. This defines a stochastic episode,
although it should replace the inaccurate phrase that a seed identifies a
fully materialized action-cost table.

## Competing amendments

### A. Bayesian visible-history kernel — recommended

Insert `ratio_draw` immediately after `cost_variance`, matching the parameter
declaration order. Freeze seed and RNG state as latent-only. Preserve the
existing event, parameter, seed, grouping, and lazy-cost laws. Define M1 value
as the posterior expectation over complete latent worlds and future response
tapes conditional only on the exact visible action/observation history.

The implementation must specify an observation likelihood and a convergent
conditional sampler. Candidate-specific model streams remain keyed by
`(episode opaque id, decision, action, sample)` and cannot reuse the realized
episode's future tape. The existing 99% CI threshold and numerical-block cap
remain unchanged. This preserves the scientific question but requires a new
inference-kernel specification and may often end in `NUMERICAL_BLOCK`.

Reject A if a conformance implementation cannot reproduce the same conditional
law independently, or if the sampler reads the realized seed/future tape.

### B. Make episode parameters/seed public — not recommended

This makes conditional rollout easy but lets continuous observations or the
seed identify future pseudorandom outcomes. It changes the information
structure and can make M1 effectively clairvoyant. Reject unless the scientific
question is explicitly changed and C0 separation is redesigned.

### C. Clone the realized latent episode — rejected

This is the current prototype's former behavior. It evaluates candidate actions
on actual future witnesses, outcomes, and costs, violating `no future access`
and `no evaluator leakage`; it collapses M1 toward C0.

## Required amendment contents

Before implementation resumes, an authorized result-blind amendment must:

1. place every omitted RNG draw, including ratio and witness nominal cost;
2. state whether the seed, split index, episode parameters, and RNG state are
   latent, visible, or evaluator-only;
3. formalize the visible-history observation likelihood and posterior state;
4. define model-rollout randomness independently of the realized future tape;
5. clarify that offline group membership is latent and incrementally exposed;
6. preserve all D1 utilities, D2-T bounds, parameter marginals, seed lists,
   named scenarios, methods, gates, and forbidden post-hoc rules;
7. reissue and rehash D3/D4 before any development policy result is produced.

Until then, `PREIMPLEMENTATION_FREEZE_FOR_TOY` remains
`BLOCKED_INTERNAL_INCONSISTENCY`.

## Unfrozen implementation readiness

`src/garc_eval/psvr_rollout_toy/conditional.py` now provides an experimental
information firewall. Its M1 evaluator owns no realized Episode, rejects any
sampler declaring realized-truth access, requires every sampled model world to
match the immutable visible decision state, applies the same B1 continuation
to the full horizon, and enforces the frozen 99% CI/numerical-block rule. Seven
protocol/firewall tests pass. This does not supply or activate the missing
posterior kernel and is not part of the toy freeze. The broader unfrozen test
suite currently reports 36 passes and one strict expected failure: policy
VisibleState exposes the seed-bearing identifier `development_11000`. An
authorized amendment must remove construction seed identity from the policy
projection, not merely rename the field.
