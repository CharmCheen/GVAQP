# Event Evidence Geometry Audit

## Scope and evidence status

This audit consumes the frozen 378 C1 cells (3 videos × 7 proxy regimes × 3 policies × 6 budgets), replays only cached outcomes, and evaluates C0 on the exact same traces. No semantic inference, selector, policy, MAB, or RL was run. C1 is fixed GAP-ONLY. Reference-aware columns are explicitly **OFFLINE_DIAGNOSTIC_ONLY** and cannot be policy inputs.

## Result

- EVENT_EVIDENCE_GEOMETRY: **PARTIAL**
- Positive yield alone: **INSUFFICIENT**
- LOVO macro R²: yield-only 0.006; yield + public/online geometry 0.795; reference-aware upper diagnostic 0.980.
- Equal-yield top-20 counterexamples include 1 pairs with F1 difference ≥0.15, spanning 1/3 videos.
- Strongest matched-stratum online geometry signal: `number_of_temporal_regions_touched` (median within-stratum Spearman 1.000, 13 varying strata).
- C1−C0 interaction range reproduced exactly: 0.2573.

## Interpretation

C1 gain changes with the geometry of positive anchors because C0 converts every positive into one temporal span, while GAP-ONLY C1 preserves separations larger than 10 seconds. Thus selector/proxy choice matters not only through how many positives it finds, but through where the acquired anchors lie. This is descriptive evidence under a model-relative K3 reference, not a causal mediation result and not independent human-continuity validation.

StaticProxyRank remains the robust winner because it has higher acquired semantic yield and higher diagnostic event coverage on this frozen matrix. Whether its additional geometry advantage is independently actionable is qualified by the small three-video sample and synthetic ranking stress.

## Research decision

ROBUST_EVENT_POLICY_OPPORTUNITY: **WEAK**. MAB REOPEN: **NO**. A future policy, if pursued after independent validation, should optimize an Event Evidence Utility concept: semantic yield + event/temporal coverage − redundant local anchors − large evidence holes. We do not fit weights or train a policy here.

Primary algorithmic gap: establish whether online, policy-visible temporal geometry transfers beyond this frozen model-relative three-video benchmark.

Updated project thesis: Event-query optimization should be evaluated as acquisition of temporally structured semantic evidence, not just as maximization of positive predicates; current evidence is **PARTIAL**, with the stated model-relative qualification.

Next single decisive experiment: preregister a second independent reference/proxy replication, then compare equal-yield traces prospectively using only online-available geometry.
