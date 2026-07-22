# Synthetic Smoke Report

## Scope

This is synthetic sanity evidence only. It is not a real-data result, performance claim, MEPP result, or identifiability proof.

Configuration: six regimes, seeds 0-19, budgets 5/10/20/40, six deterministic planners, M0 and the real K3 adapter. Total lineage rows: 108,000. Expensive model calls: 0.

## Required Sanity Outcomes

- **P4 relation trigger:** in R2, P4 averages at least one relation call at B=5 for both materializers. M0 lineage contains `DISTINCT` transitions from 2 to 3 predicted events with matched-event delta +1 and no new positive anchor.
- **Relation value:** 255 of the 720 R2/P4/M0 relation actions returned `DISTINCT`; an audited B=5 example splits anchors `u0012/u0021` and improves matched count by one.
- **Unsafe gap counterexample:** R3/P5 emits hard-gap actions. In M0, 140 lineage records split a same-GT event after a binary `NEGATIVE`; mean oversplit rate is 0.5 at B=5 and 1.0 at higher budgets.
- **Proxy-zero reachability:** in R4 at B=20 with K3, P0 open coverage reaches recall 1.0 using 20 explore actions, while P1 top-prior remains at 2/3 recall with no explore action.
- **Sequence diversity:** for R2 seed 0/B5/M0, six planners produce five distinct sequences. P4 contains relation actions and P5 contains hard-gap actions.
- **Lineage completeness:** every row records pre/post partitions, event counts, matched delta, returned-seconds delta and selection reason.

## Materializer Caveats

K3 ignores typed relation observations because its real interface has no relation input. It can still oversplit R3 from ordinary negative core observations before P5's explicit hard-gap action. M0 can overmerge at high action counts because it is a deliberately simple fixed-gap scaffold. These behaviors are diagnostic failures, not algorithm comparisons.

## Non-Claims

The smoke does not establish that P4 is superior, that relation probes help on real data, that coverage is optimally allocated, or that a posterior model is identifiable. It establishes only that the infrastructure can express and reproduce the target causal transitions.
