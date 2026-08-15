# Decisive experiment recommendation

This is a recommendation only. It does not authorize execution and it does not
read or alter any human-annotation output. No model training, tuning, or GPU
work is proposed here.

## Why this experiment and not the human P1 reference

The human P1 reference is the gated confirmatory test for H1 (geometry), but H1
has already been heavily discounted by the VLM-direct shadow (LOW) and the
model-relative P2 diagnostic (semantic-state residual ABSENT). Even a P1 PASS
would most likely leave a generic-coverage explanation standing, so it is not
the highest-information action.

The highest-information action targets the one assumption the entire original
program depends on and that has never been observed: does faithful endogenous
cheap sensing actually produce natural exposure false negatives and
non-rare, material, predictable action regret? On the current substrate this is
structurally impossible to observe (exposure recall is forced to 1.0). If that
assumption is false in reality, the original theory is dead regardless of P1.

## The experiment

Name: Natural-exposure and action-regret prevalence probe (minimal faithful
substrate).

- Claim tested: on real long video, the cheap sensing step (a) generates
  fallible candidate evidence with non-negligible natural exposure false
  negatives, and (b) the resulting online process visits non-rare, material,
  policy-visible states where a state-dependent SCAN/VERIFY choice beats the
  fixed deterministic default.
- Estimand: the population prevalence and magnitude of hindsight action regret
  (value of the best reachable next action minus the fixed default's action),
  and the natural candidate-exposure recall against an independent reference.
- Treatment / control: state-dependent deviation (the best legal one-step
  deviation from the fixed schedule) vs the fixed SCAN1-to-VERIFY1 temporal
  coverage default, evaluated as hindsight regret on the same logged states.
- Independent experimental unit: held-out source video (not a unit, trace, or
  budget cell). Require at least 2-3 held-out videos with no label leakage.
- Reference / ground truth: an independent semantic event reference (human or,
  as a weaker proxy, a fresh high-agreement VLM), constructed before the probe
  and never used to design the cheap detector or the fixed policy.
- Confounds to control: detector/model leakage into the reference; behavior-policy
  selection bias in which states are logged (use randomized or coverage-rich
  behavior and record propensities); cost-model mismatch (measure real per-action
  latency/cost); single-video single-event luck; penalty/discontinuity
  dominance in the utility (use a smooth utility).
- Success gate: natural exposure recall < 1.0 by a non-trivial margin AND
  hindsight regret that is non-rare (e.g., present in a material fraction of
  logged states), practically large, and predictable from legal state across
  held-out videos, with positive value after measured physical costs.
- Failure gate: exposure recall near 1.0, or regret is rare, small,
  unpredictable, or vanishes after physical costs.
- What result would change the direction: a FAILURE falsifies the original
  endogenous-SCAN theory and closes the adaptive-allocation program (not the
  bounded systems findings). A SUCCESS reopens P5 controller work with a real
  substrate and converts the theory from NOT ESTABLISHED to SUPPORTED.

## Why this is the smallest decisive test

It is a measurement, not a new algorithm. It requires no learned controller, no
MAB, and no tuning. It answers the two sub-questions that determine whether the
original formulation has any life: (1) does natural exposure failure exist and
matter, and (2) does it create exploitable regret. A clean negative here
terminates the most expensive future branch (P4/P5) at minimal cost; a clean
positive is the only result that would justify further investment.

## Ordering and authorization

Per NEXT_STAGE_STATE_MACHINE.md, this corresponds to the future P4 faithful
substrate and is currently NOT authorized. It should only run after an explicit
gate decision, and it must not be conflated with the human P1 gate. This
document recommends it as the highest-value next scientific action; it does not
launch it.
