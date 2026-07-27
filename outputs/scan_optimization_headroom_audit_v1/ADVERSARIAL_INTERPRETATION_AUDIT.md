# Adversarial Interpretation Audit

## Consequential claim under review

The current SCAN operator has real temporal-allocation headroom, but the tested
handcrafted causal policies do not yet provide a stable cross-video scheduler.

## Evidence that survives attempted falsification

- All 110 Replay runs used common within-video absolute deadlines and 50 random
  seeds. The offset-0 denominator is 263 exposable events; recall against all
  268 references is reported separately.
- Fast unit-map exposure and full visible-subset replay agreed exactly on all
  880 Replay checkpoint records (`max absolute delta = 0`).
- Full visible-subset replay was applied at all 1,478 completed physical
  prefixes; its accumulated exposure agreed exactly with the fast map at every
  prefix.
- All 32 controlled-warm trace hashes were captured. Replaying each trace with
  the frozen trusted policy code produced zero selected-action mismatches.
- The initial invalid comparison between full-horizon Replay AUC and 60-second
  Physical AUC was rejected. H3 uses matched 60-second horizons.
- On the long video, Uniform's physical advantage over Sequential is positive
  in all four balanced blocks. On the short video, every non-Sequential method
  is worse than Sequential in all four blocks.

## Claims that do not survive

- **Universal Largest-Gap superiority:** rejected. It improves geometry at all
  pre-full Replay checkpoints, but not event AUC consistently and not the
  60-second short-video outcome.
- **Seek cost is the dominant bottleneck:** not supported in this controlled-
  warm setup. Q90 costs are 1.285 s for backward/long seeks and 1.297 s for
  contiguous steps; the observed differences are too small to explain the
  policy reversal.
- **Any positive local trigger association justifies refinement:** rejected.
  Lateral motion predicts neighbor novelty, yet no fixed refinement policy
  improves the strongest coverage baseline on both videos.
- **The offline greedy result is an optimal upper bound:** rejected wording.
  It is a feasible hidden-information greedy witness, not a proven optimum.
- **The two videos support generalization or a final paper ranking:** rejected.

## Main alternative explanations

1. The short video has a favorable early event cluster: 21.4% of its exposable
   events first occur in the first 10% of units, with no additional first
   exposures from 10–20%. Sequential therefore has an accidental low-budget
   advantage that geometric coverage cannot assume on new videos.
2. The large offline gap may partly reflect full-scan mapping labels that an
   online predictor cannot infer from the current visible signals.
3. Selecting `lateral_motion_signal` from several predeclared components still
   risks development-set selection bias; it requires independent videos.
4. Grid AUC uses eight frozen checkpoints, not the continuous Replay curve.
5. Macro-region Largest-Gap has Replay evidence only; it was not one of the
   existing 32 physical policies.

## Reviewer decision

```text
TEMPORAL_ALLOCATION_HEADROOM = OBSERVED_BUT_VIDEO_DEPENDENT
HIDDEN_INFORMATION_HEADROOM_WITNESS = LARGE
PATH_COST_DOMINANCE = NOT_SUPPORTED
FIXED_REFINEMENT_STABILITY = FAIL
GUARDED_MARGINAL_IMPLEMENTATION = NOT_JUSTIFIED
CROSS_VIDEO_GENERALIZATION = UNRESOLVED
```

The next result that would revise this decision is a causal region-value model
or simple refinement rule that improves the strongest coverage baseline on
independent complete videos under matched controlled-warm wall-clock.

