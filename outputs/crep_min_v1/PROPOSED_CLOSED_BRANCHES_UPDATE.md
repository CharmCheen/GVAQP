# PROPOSED CLOSED_BRANCHES UPDATE (CREP-Min v1; proposal only — NOT applied)

Per the audit mandate, `CLOSED_BRANCHES.md` and all root state files are NOT
modified. This document proposes the rows the project owner may add after
reviewing the three CPU gate packages.

## Proposed new closed branches

| Branch | Status | Decisive reason | Reopen condition |
|---|---|---|---|
| MAB / contextual TS controller (fixed-candidate universe) | NO-GO / CLOSED (local evidence) | MAB gate: G_oracle=0.474 but TS closed-loop gain <= +0.009 AUC with unstable direction (MAB_NOT_CORE); learned regret 0.0097 vs fixed 0.0009 | Faithful endogenous substrate (P4) shows non-rare, material, cross-video predictable action regret AFTER measured physical costs |
| Relation-aware greedy / ERAEA algorithm claim | NO-GO / CLOSED (local evidence) | ERAEA gate: equal-yield residual median 0.0 (3/3 clusters); G_generic -0.0194; R1=R2=R3=R4 exactly; K0/C3/gap sensitivity cannot rescue; harmful rate 14-16% | Matched-yield residual >= 0.03 in >= 4/6 clusters AND >= 0.03 gain over strongest generic baseline on an INDEPENDENT human reference (single preregistered audit; no reward re-tuning) |
| Relation-specific reward terms (redundancy/merge-risk/boundary) as mechanism | NO-GO / CLOSED (local evidence) | R-terms never change the greedy's action choice on this substrate (R1==R2==R3==R4 identical at every budget/cluster) | Any new substrate where a relation term demonstrably changes actions and adds >= 0.01 AUC independently |
| Complex K3 as selector-gain mechanism | NO-GO / CLOSED (retained) | k3_aware scoring == gap_aware scoring exactly; mechanism ablation marginals 0.0 | Independent-human failure that C1 cannot handle and a complex component independently fixes |
| Generic coverage/MMR as a NEW algorithm claim | NOT ALLOWED (baseline only) | Generic coverage/stratification/region-UCB explain >= 100% of any observed gain; they are strong BASELINES, not contributions | None — any paper must present them as baselines, never as the novelty |
| ERAEA old paper package (EventRelation objective + relation-value acquisition + equal-yield evidence) | CLOSED | All three core contributions failed their preregistered gates | See relation-greedy reopen condition above |

## Unchanged (for reference)
- Coverage-Debt controller: NO-GO / CLOSED (unchanged)
- Dynamic V3 controller: NO-GO / CLOSED (unchanged)
- Selective-deviation classifier: NO-GO / CLOSED (unchanged)
- P4 faithful SCAN: DEFERRED / NOT AUTHORIZED (unchanged)
- P5 controller: CLOSED (unchanged)

## Proposed retained lines
- Fixed deterministic coverage + proxy ordering executor: RETAIN AS STRONG
  BASELINE (never as a new-algorithm claim).
- CREP (certified replay / non-identifiability certificates): new mainline,
  gated GO_CREP_PAPER_CANDIDATE by crep_min_v1.
- PC-CAQP: CONDITIONAL_NOT_STARTED — starts only if a future faithful
  substrate shows candidate support changing with actions / cache-vs-causal
  rank reversals / completion-commit deadline effects.
