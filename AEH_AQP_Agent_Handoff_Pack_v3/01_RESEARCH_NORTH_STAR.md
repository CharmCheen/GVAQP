# Research North Star

## Core research question

Given a long video partitioned into public temporal units, cheap public evidence, an expensive exact-on-query semantic oracle and a finite budget, how should a query processor discover, verify, partition and audit **all distinct events** satisfying an event predicate while minimizing oracle cost and controlling missed-event risk?

The database object is an event relation:

```text
EventRelation(
  event_id,
  start_time,
  end_time,
  event_type,
  actor_or_identity,
  supporting_queries,
  confidence_or_status,
  lineage,
  audit_status
)
```

It is not a bag of positive clips.

## Desired paper claim

The strongest defensible target is:

> A budgeted multi-event semantic query processor for long video that explicitly separates search, semantic verification, event materialization and independent audit, and that improves the cost–event-quality frontier under a fixed expensive-oracle budget.

## Contribution stack

### C1 — Event-object query semantics

Formalize why record/clip-level AQP cannot directly optimize an event set with temporal dependence, duplicates, boundaries and merge/split errors.

### C2 — Event-aware physical operators

Typed operators such as `DISCOVER_CORE`, `VERIFY_CORE`, `EXPAND_BOUNDARY`, `LINK_OR_SPLIT`, `DISAMBIGUATE_TYPE` and `AUDIT_REGION`, each with cost, state transition and output consequences.

### C3 — Bounded, barrier-aware event materialization

BB-EM/K3-safe maps queried evidence into bounded events and treats queried negatives as hard barriers. This is currently the strongest empirically supported component.

### C4 — Budget-aware event-state planning

The original target used saturation, event novelty, exploration and counterfactual materialization risk. The sealed mechanism gate supports saturation only with ideal/event-aligned hypotheses, rejects exploration, and finds counterfactual effects negligible. Only one public representation-transfer test remains; otherwise this contribution is removed.

### C5 — Independent residual audit

Separate discovery from audit, sample canonical-anchor blocks with known inclusion probabilities and estimate missing events/stopping risk. This remains a target, not an achieved guarantee.

## Claim levels

| Level | Status | Meaning |
|---|---|---|
| L0 | Frozen evidence | Strict benchmark and completed experiment facts |
| L1 | Supported module | BB-EM/K3-safe; competitive MAP/M1; weak H1 source semantics |
| L2 | Candidate mechanism | Public event-cell saturation, pending one-shot S2 transfer gate |
| L3 | Target system | Full AEH-AQP with audit and stopping |
| L4 | Prohibited claim | Statistical completeness guarantee or cross-video generalization without evidence |

## Current paper-safe fallback

The sealed mechanism gate did not justify the original planner. The retained mainline is:

```text
EventRelation semantics
+ selector-agnostic BB-EM/K3-safe
+ strong retrieval/search baselines
+ cost and event-partition error decomposition
+ empirical audit diagnostics
```

Only if the frozen S2 representation gate passes may the stronger route include:

```text
public event-cell EVENT_SEARCH
+ event-saturating acquisition
+ BB-EM
+ independent audit
```
