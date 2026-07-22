# MF-PSVR Cycle-0 Implementation Audit

`AUDIT_DECISION = PASS_WITH_MANDATORY_LEGACY_INVALIDATIONS`

## Strongest supported conclusion

The frozen unit-level oracle labels and reference events are internally aligned,
but legacy traces are not admissible as track-witness MF-PSVR training data or
strict publication-deadline comparisons. The current code now binds each unit
VERIFY opportunity to one immutable track witness and starts the publication
clock before oracle-session setup, proxy initialization, and detector warm-up.

## Observed evidence

- Label/reference audit: `PASS`; checked
  744 physical query results with
  0 label mismatches.
- Historical candidate identity: 100
  run-unit histories changed top track behind one unit candidate identity.
- Historical deadline accounting: 24
  runs marked deadline-met exceed the deadline under recorded total-service time.
- Snapshot audit: 20 unique completed run
  records point to a missing final snapshot.
- Physical repeats: 12 of
  140 comparable groups changed VERIFY
  signature; repeats are latency observations only.
- B1/B2 verdict: `ALIAS_NOT_INDEPENDENT_BASELINES`.
- SUPG variant verdict: `DISTINCT_SELECTIONS_EFFECTIVELY_ALIAS_AFTER_K3`.
- Score routing: `PASS_WITH_LEGACY_EXCLUSION`.

## Derived conclusions

1. The admissible first target is the probability that verifying a unit-level
   opportunity returns an oracle-positive result. A track is a frozen causal
   witness, not track-specific ground truth.
2. All methods in the new physical table must be rerun under the repaired full
   clock. Historical negative rule-search conclusions remain preserved within
   their legacy contract.
3. B2 cannot count separately from B1, and the two SUPG-RT views cannot count as
   two effective baselines after K3 collapse.
4. Existing DrivingDojo models are useful pipeline evidence only; tag-based
   labels cannot support the MF-PSVR semantic-refiner claim.

## Main competing explanation

The historical implementation intentionally treated a candidate as an entire
10-second unit and stored the current top track only as explanatory evidence.
That interpretation preserves its unit-level endpoint metrics, but it does not
permit track-level candidate-value or temporal-refiner claims. The new contract
keeps the unit target while freezing the witness identity.

## Unresolved uncertainty

Whether independent, frozen-oracle-labeled training sessions contain enough Q1
and Q2 positives to identify semantic value across sources remains untested.
Repository-wide held-out enforcement also lacks a cryptographic access log;
Cycle 0 therefore proves only that this audit and the new program do not open
held-out semantics.

## Next highest-value action

Build the independent DrivingDojo session manifest, generate immutable
track-witness candidates, and measure the frozen-oracle Q1/Q2 class balance
before choosing a model family or launching a large physical matrix.
