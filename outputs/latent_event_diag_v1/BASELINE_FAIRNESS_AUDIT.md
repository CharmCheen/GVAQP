# Baseline Fairness Audit

Detailed machine-readable findings are in `baseline_equivalence_audit.csv`.

## SUPG

**VERIFIED.** Across 30 paired budget/seed runs, all-selected and confirmed-only have different native selected sets (mean Jaccard 0.0781), but queried IDs, positive anchors and binary-negative sets have Jaccard 1.0. Their K3 segment hashes and metrics are identical in all 30 pairs. Equivalence begins when K3 projects both variants to queried positive/negative anchors; it is not a file alias.

## ABae

**VERIFIED.** Strata use normalized proxy score plus deterministic time/video tie order. Pilot labels are online observations and determine remaining allocation. Pilot samples remain in the final sampled set and can contribute confirmed anchors; there is no double oracle charge, but pilot evidence is reused for output. No oracle-informed failure strata were found.

**LIKELY risk.** The code labels itself `ABae-inspired`; its stratified aggregation allocation is being interpreted as event discovery after confirmed-positive materialization. This is an adapter experiment, not native ABae event-discovery semantics.

## MAP

**VERIFIED.** Component threshold is q0.70 (top 30% proxy), audit windows are 60s, budget splits are 80/20 for B<=20 and 70/30 above. Anchor ties are deterministic by component iteration then proxy/unit ID. `seed` is written but never used in selection. Stage 1B high budgets use 60/20/20 confirm/audit/barrier quotas.

**VERIFIED risk.** K3 cannot distinguish Stage 1B PLACE_BARRIER negatives from normal negative observations. B=100 lineage is recoverable from action traces and `source_frame_ids`, but its barrier semantics are not relation semantics.

## ARC

**VERIFIED.** Native ARC emits `cand_clips`. The strengthened K3 adapter ignores those native boundaries and rematerializes only queried binary anchors. This can remove ARC's native coverage/boundary behavior. ARC's clip binary label is not an explicit event identity field; unit multiplicity cannot be expressed.

## Missing Comparison Families

**BLOCKED_BY_MISSING_ARTIFACT.** No common realcartest per-budget logs/segments were located for uniform/random/top-proxy under the same K3/event evaluator. MAP component-first exists. Absence of shared materialization or SEHS hypothesis leakage for the missing families cannot be verified.
