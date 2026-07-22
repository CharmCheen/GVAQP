# BCM-AQP v2 Research State

## Objective

Determine whether a public-input-only binary counterfactual, materialization-aware scheduler improves event-level discovery under the frozen strict VLM-defined pseudo-oracle benchmark without changing oracle, baseline, materializer, matcher, or budget semantics.

## Established findings

- Strict benchmark `cbbv2_514c0d360fd5b2a4b5fe` is frozen and independently audited.
- BCM v2 is leakage-safe under the audited surfaces, uses 1,060 logical cache calls across 24 runs, and makes zero physical VLM calls.
- Canonical BCM/M1 event-F1 AUC is `0.294270`; best frozen baseline is `0.389659`; current MAP/M1 is `0.388056`.
- The public candidate set covers every VLM-defined pseudo-event and the full-oracle M1 recall ceiling is 1.0, so candidate coverage and materializer recall ceiling do not explain the observed deficit.
- The builder creates 141 hypotheses. All first 100 canonical actions are `DISCOVER_CORE`; no `PROBE_STRUCTURE` or `AUDIT_UNCOVERED` action is activated.
- All weight ablations have identical event curves. Their query order is identical through budget 50 and diverges only after call 63 without metric effect.
- Selected surrogate score has Spearman correlation `0.0597` with realized one-step event-F1 change; 92% of positive-score selected queries have zero or negative immediate F1 change.
- On the same canonical trace, M1 outperforms M0 at budgets 50, 80, and 100, supporting bridge-safe materialization for this diagnostic.

## Rejected hypotheses

- **Canonical BCM v2 beats the frozen best baseline:** rejected by AUC delta `-0.095389`.
- **Current structural-risk weights materially change retrieval:** rejected by outcome-equivalent ablations.
- **The configured run tests structure-probe value:** rejected because structure probes have zero activation.
- **Candidate or full-oracle materializer ceiling is the dominant bottleneck:** rejected by ceiling recall 1.0.

## Active hypotheses

- Overfragmented owner hypotheses prevent follow-up/structure actions from competing within budget.
- Uncalibrated existence priors and likelihoods dominate the score and poorly rank realized event discovery.
- A development-video-calibrated action model with a mechanism-activation gate may test counterfactual structure probing fairly.

## Important failure and lesson

Passing unit tests does not establish that the intended mechanism is exercised in the formal operating regime. Future protocols must include a pre-evaluation activation gate and held-out score-versus-realized-utility/regret checks.

## Unresolved uncertainty

The current run cannot distinguish whether counterfactual structure probing is ineffective or merely unreachable under the candidate partition. Single-video VLM-defined pseudo-events also do not establish human safety-event validity or cross-video generalization.

## Next highest-value action

On separate development videos only, compare coarse/disjoint candidate partitions and calibrated outcome models under a preregistered requirement that `PROBE_STRUCTURE` and follow-up actions activate before budget 100. Reject revisions that do not improve held-out score/realized-utility correlation and one-step regret; do not tune another candidate on this frozen test reference.

