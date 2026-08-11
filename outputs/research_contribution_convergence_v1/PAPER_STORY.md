# Candidate Paper Story — Not Yet Submission-Ready

## Motivation

Long-video semantic queries often use a cheap proxy to decide which temporal units receive an expensive VLM. If the requested answer is an event interval relation rather than a frame-level selection, sparse verified labels leave a separate unresolved question: how should the engine materialize anchors into events?

## Observation

On three frozen independent driving videos, holding the exact semantic trace fixed, global merging of all observed positives produces one broad event and loses most event recall. Local temporal continuity grouping recovers many more model-relative reference events.

## Problem formulation

Input is a time-indexed partial observation relation with queried positive, queried negative, unknown, and parse-failure states. Output is an EventRelation. The current empirical paper can only evaluate reconstruction of a frozen full-grid model-relative relation.

## Key insight

The observed P0 failure is not primarily selector choice or a sophisticated anti-overmerge rule: it is the invalid assumption that temporally distant verified positives belong to one event. A local continuity constraint is sufficient for most measured gain.

## Design

Use a frozen candidate/proxy substrate, cached semantic verification trace, continuity-constrained materialization, and explicit provenance. Current K3 is a conservative realization; the paper must separate its code-level negative/unknown semantics from its empirically demonstrated gap rule.

## Implementation

V10 multi-seal complete reference release, deterministic V3 candidate/proxy tables, P0 same-trace replay runner, matching implementation, and component lineage ablation are available as reproducible artifacts.

## Evaluation questions

1. Does materialization change event recovery under an identical trace? Yes, model-relatively.
2. Which rule explains the change? The local gap constraint, not the queried-negative barrier.
3. Does it exceed selector variability? Not conclusively; pairwise comparison favors materializer while full selector spread does not.
4. Does it agree with independent human events? Unknown — this is the paper-deciding missing test.

## Main results presently usable

54 same-trace pairs: mean ΔF1 `+0.1840`, median `+0.1457`, 40 positive / 14 equal / 0 negative. The stricter tIoU sensitivity retains the effect. Gap-only C1 accounts for mean `+0.1738` of it.

## Limitations

Model-relative K3-defined reference relation; one predicate; simple selectors; no physical-deadline P0; unknown/parse states unexercised; simple continuity rule has high prior-art/obviousness risk.

## Narrative decision

Do not write a paper claiming a novel K3 or negative-evidence algebra now. The viable story, if P0 human/independent continuity validation succeeds, is a **query-execution measurement finding and operator contract**: sparse semantic verification needs explicit event relation materialization, and a global-positive coalescing baseline is invalid.
