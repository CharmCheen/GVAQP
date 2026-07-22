# System and Algorithm Specification

## Current implemented, defensible flow

```text
video
→ fixed 10-second units
→ public cheap proxies
→ MAP-anchor-only acquisition
→ budgeted OracleAccessor
→ queried positives + queried negatives
→ BB-EM / K3-safe
→ EventRelation
```

### MAP-anchor-only

- Candidate sources: high-proxy islands, uncovered local peaks and 60-second audit representatives.
- Budget split: approximately 80/20 anchor/audit at low budget and 70/30 at high budget.
- It is a deterministic component/diversity heuristic, not a validated materialization-aware VOI planner.

### OracleAccessor

- The planner may ask for a unit label only after selecting that unit.
- It enforces budget and duplicate-query checks.
- Logical calls are charged even when a frozen raw VLM response is reused.
- Dense labels and evaluator reference remain evaluator-only.

### BB-EM / K3-safe

- Positive queried units are event anchors.
- Queried negatives are hard merge barriers.
- M1 bridge-safe only merges directly adjacent positive anchors.
- The implementation’s exact behavior must be taken from strict benchmark source and its theory/code audit—not reconstructed from prose.
- The 40-second and 60-second caps must be reported only where they actually bind in code.

## Target AEH-AQP flow

```text
event predicate/schema
→ public multi-resolution search index
→ actor-/event-centric hypotheses
→ typed probes
→ budgeted cost-aware planner
→ BB-EM event materialization
→ independent audit ledger
→ residual estimate / stop decision
```

## Query-time hypothesis state

A hypothesis node should carry only public or queried evidence:

```text
hypothesis_id
source_type
candidate_interval
actor_or_track_key (if public)
cheap_evidence
queried_evidence
uncertainty
event_saturation
legal_actions
executed_actions
merge/split lineage
materialized_event_ids
certification_status
```

The event graph is useful only if it changes execution decisions. A generic knowledge graph is not the contribution.

## Typed actions

| Action | Purpose | Expected output effect |
|---|---|---|
| `DISCOVER_CORE` | find an initial event anchor | create/confirm event evidence |
| `VERIFY_CORE` | confirm a candidate | change existence belief |
| `EXPAND_BOUNDARY` | refine start/end | boundary quality |
| `LINK_OR_SPLIT` | adjudicate fragments/gaps | merge/split partition |
| `DISAMBIGUATE_TYPE` | resolve event semantics | typed EventRelation |
| `AUDIT_REGION` | sample uncovered space | missed-event estimate |

## Planner objective status

The normative objective remains expected event-level loss reduction per cost. The historical BCM surrogate combined:

```text
new-event probability
+ event saturation penalty
+ uncovered-region value
+ counterfactual materialization change
+ audit value
− query cost
```

No submodularity, constant-factor approximation, exact F1-VOI or calibrated residual guarantee has been proven. The mathematical reference is a design constraint and counterexample catalog, not empirical validation.

The sealed mechanism gate does not justify exploration or counterfactual terms in a runnable planner. They remain historical/theoretical items. Only event-cell saturation receives one final representation-transfer test.

## Current bottleneck decomposition

```text
candidate/proposal miss
→ ranking/query miss
→ oracle semantic error
→ boundary/materialization error
→ merge/split error
→ certification/audit miss
```

Under the strict single-video oracle, candidate coverage and ranking are the measured leading bottlenecks. Under the user’s AQP abstraction the oracle may be treated as exact, but paper experiments should still distinguish oracle-relative from real-world validity.
