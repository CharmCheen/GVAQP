# Persistent research state

## Objective

At each fixed budget `B`, use exactly `B` expensive oracle observations and return a shared-K3 EventRelation with higher event recall/F1 and normalized event-F1 AUC than ARC, without winning through a broader materializer.

## Established findings

- Native ARC and controlled exact-B K3 curves are different experimental contracts. Native values are descriptive only.
- CLIP top-k is a strong controlled baseline on dataset3 (`0.538949`) but not uniformly strong across realcartest.
- BSEC (`0.524155` development AUC), QTPC (held-out `0.593589`), and PNIR (confirmatory `0.524589`) each failed their relevant stronger-baseline gate.
- The frozen DASR v3 calculation is mechanically correct, uses exactly `B` observations, and passes its narrow local rule. It is not the strongest method: pure proxy top-k beats it on the rich final interval.
- ARC seed randomness is consequential. Over seeds 0–999 on the rich interval, mean ARC AUC is `0.655448`, SD `0.032759`, and 48.1% of seeds exceed DASR.
- PSTR-5:4 retrospectively beats both pure proxy and shared-K3 ARC on four opened domains and ties them on the sparse domain. Five-domain leave-one-domain-out overhead selection produces four controlled-ARC wins, one tie, and no losses. Dataset3 still places PSTR below CLIP, NMS, DASR, and descriptive native ARC.
- All controlled results use cached VLM pseudo-oracle observations; no new physical VLM calls were made.

## Active hypothesis

Temporal concentration of high proxy scores, rather than semantic duplicate hits, is the dominant avoidable source of fixed-budget event loss on realcartest. A small surplus of temporal cells (`B + floor(B/4)`) may preserve relevance while increasing distinct event opportunities.

Prediction: on a new independently sourced video, PSTR will exceed both pure proxy top-k and expected shared-K3 ARC AUC, especially at low and middle budgets, without larger per-event K3 spans.

## Rejected hypotheses

- “Low-budget CLIP mostly wastes calls on duplicate events.” Rejected because duplicate burden was zero at budgets 5, 10, and 20 in development.
- “The monotone-submodular BSEC surrogate is a stronger event selector.” Rejected by development AUC below CLIP and MMR.
- “Local CLIP peak contrast generalizes.” Rejected by the 2000–3200 reversal.
- “A 1:3 peak/NMS portfolio is robust.” Rejected on 0–1570.
- “DASR's NMS exploitation component is independently helpful.” Unsupported: DASR and stratified-only curves are identical on both final intervals.

## Important failures and lessons

- A locally preregistered pass can still be scientifically weak when the comparator has high seed variance and an omitted deterministic baseline is stronger.
- “Disjoint” did not mean “globally unseen”; pre-existing labels and evaluations must be audited before using untouched-test language.
- Exact-call adaptation must name the fill rule. ARC itself frequently stopped after zero to two calls; proxy fill supplied the remaining budget.
- Normalized AUC and the unweighted mean over budget points can reverse a conclusion. Both must be shown.
- Complexity should follow a demonstrated failure. The simple proxy-stratification branch is currently better supported than semantic clustering, peak contrast, or hybrid exploitation.

## Unresolved uncertainty

- External cross-video and human-ground-truth validity.
- Whether PSTR gains survive exact-B SUPG and DPP/diversified baselines.
- Whether the fitted one-quarter cell overhead transfers without retuning.
- Whether gains persist under other query predicates, unit widths, proxy models, and event densities.
- Native ARC comparison under a genuinely equivalent relation-output contract.

## Frozen next action

`config/frozen_external_confirmation_v5.json` supersedes v4 and fixes PSTR-5:4, the public proxy pipeline, label-blind sealer, exact comparator implementations, video-macro aggregation, seed sets, bootstrap, and rejection rule before any future domain is acquired. New oracle or human-annotation expenditure requires explicit authorization.
