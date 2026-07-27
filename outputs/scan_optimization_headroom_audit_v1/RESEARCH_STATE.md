# Persistent Research State

## Objective

Identify and quantify remaining fixed-fidelity SCAN scheduling headroom, then
advance only mechanisms supported by causal, matched-wall-clock evidence.

## Established findings

- Trusted frozen-policy mode is valid for controlled research; arbitrary policy
  submission remains unsupported.
- A large feasible hidden-information scheduling witness exists on both videos.
- Simple coverage gains are video- and horizon-dependent.
- Matched 60-second Replay and Physical winners agree on both videos.
- Controlled-warm transition path costs are nearly flat after initialization.
- Lateral motion has neighbor-novelty association, but fixed refinement does not
  improve the strongest coverage baseline consistently.

## Rejected hypotheses

- Largest-Gap is a universal event-exposure improvement.
- Real seek cost erases the observed logical benefit in this setup.
- Candidate/composite triggers robustly predict neighbor novelty.
- Positive trigger association is sufficient for a useful scheduler.
- Current evidence justifies full guarded marginal scheduling.

## Active hypotheses

- A calibrated causal macro-region new-event posterior can recover part of the
  offline greedy gap while coverage recoverability prevents catastrophic focus.
- A phase-adaptive coverage backbone may dominate fixed micro- or macro-batching
  across budget horizons, but requires independent videos.

## Important failures and lessons

- Comparing full-horizon Replay gain to 60-second Physical gain produced an
  invalid retention estimate; all final H3 claims use matched 60-second horizons.
- Broad triggers were nearly saturated and misleading; component-wise controls
  exposed a long-video reversal.
- Refinement association did not survive opportunity-cost comparison against the
  strongest coverage policy.

## Unresolved uncertainties

- Only two complete videos are available; no cross-video validation is possible.
- Macro-region Largest-Gap lacks direct physical runs.
- Offline greedy is not an optimal upper bound and may exploit structure that
  current public observations cannot predict.

## Next highest-value action

Add independent complete videos and evaluate a causal region new-event model
against shuffle, time-index, and coverage-only controls. Reopen guarded marginal
scheduling only after a simple relative-opportunity-cost refinement improves the
strongest coverage baseline on independent videos.
