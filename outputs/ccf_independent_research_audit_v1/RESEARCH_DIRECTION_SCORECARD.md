# Research direction scorecard

Scores are 1 (worst) to 10 (best), each with evidence and uncertainty. They
score the CURRENT reconstructed direction (budgeted model-relative
EventRelation reconstruction under imperfect proxy ranking), not the aspirational
original formulation. The aspirational formulation is scored separately where
noted.

## 1. Problem importance — 6

- Evidence: querying long video under cheap+expensive computation budgets is a
  real, growing systems problem (Seiden, ARC, DIVA, ThalamusDB all target it).
  The narrowed instantiated problem (ranking + gap materialization) is less
  important than the original.
- Uncertainty: moderate. Importance would rise if the endogenous-acquisition
  formulation were actually tested.

## 2. Theoretical clarity — 5

- Evidence: the original state/action/budget/utility formulation is crisp
  (ORIGINAL_PROBLEM_FORMULATION.md), but the empirical substrate does not
  instantiate it, so theory and test are disjoint.
- Uncertainty: low. The gap between formulation and instrumentation is well
  documented.

## 3. Empirical support — 3

- Evidence: the two live hypotheses (H1 geometry/human, H2 endogenous regret)
  are NOT ESTABLISHED. Positives are bounded and model-relative; negatives are
  substrate-bounded.
- Uncertainty: low for the current state; the missing decisive evidence is the
  key unknown.

## 4. Construct validity — 2

- Evidence: candidate acquisition is precomputed (exposure recall 1.0), SCAN
  does not sense, VERIFY reveals cached labels, and the event reference is
  K3/model-relative. The core constructs of the original theory are not
  realized.
- Uncertainty: low. This is the most defensible low score.

## 5. External validity — 2

- Evidence: 3 videos, 1-2 queries, model-relative reference, synthetic proxy
  degradation, no human truth, abstract costs, query-count budgets.
- Uncertainty: low.

## 6. Algorithmic novelty — 2

- Evidence: gap-constrained merge is a standard temporal-localization primitive;
  bandit/RL/adaptive-sampling novelty is crowded (LAVA, ARC, Seiden, ExSample,
  AQUAPRO). No supported novel algorithm remains.
- Uncertainty: low.

## 7. Systems novelty — 4

- Evidence: the single-physical-clock, causal-exposure, durable EventRelation
  contract (DATB-SV) is a real but narrow systems idea, backed by a
  single-source/single-event physical run.
- Uncertainty: moderate. Could rise to 5-6 with cross-video physical
  replication, but that evidence does not exist.

## 8. Evaluation quality — 7

- Evidence: unusually strong process discipline — preregistration, protocol
  hashes, outcome-blind regimes, controlled pairs (54/54 valid), 10k
  bootstraps, leave-one-out, cluster-as-unit. This is a genuine strength.
- Uncertainty: low on process; the residual weakness (model-relative reference)
  is captured in dimensions 4 and 5, not here.

## 9. Publication potential — 3

- Evidence: no supported main algorithm contribution; the strongest honest
  artifact is a bounded systems/design story plus a strong negative-result
  audit. Crowded related work and no independent reference.
- Uncertainty: moderate. A decisive positive (human P1 PASS or faithful P4
  regret) could raise this to 5-6; current evidence does not.

## 10. Cost to obtain decisive evidence — 4

- Interpretation: lower = more expensive, higher = cheaper to get a decisive
  answer.
- Evidence: the human P1 reference is already designed and frozen (relatively
  cheap annotation), but the faithful P4 substrate (raw-video online sensing,
  measured costs, prospective logging) is expensive and currently unauthorized.
- Uncertainty: moderate. The cheapest decisive measurement (natural exposure
  false-negative rate) has not been scoped or costed.

## Aggregate

- Mean of the 10 scores = 3.8.
- Weighted toward the two decisive dimensions (construct validity 2, empirical
  support 3), the current direction is a WEAK_CURRENTLY / PIVOT_REQUIRED state,
  consistent with the repository's own contribution scorecard
  (TOP_CANDIDATE_BUT_NOT_READY for the materialization problem framing).

## Verdict

Do not treat this as a paper-ready direction. The single salvageable ingredient
is the systems contract (single-clock causal durable EventRelation) plus the
evaluation/provenance discipline. The highest-value next step is not more
experiments on the current substrate; it is a cheap falsification measurement
of the one untested load-bearing assumption (natural exposure failure), because
that determines whether the original formulation has any life.
