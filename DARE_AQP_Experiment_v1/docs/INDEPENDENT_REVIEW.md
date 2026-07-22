# Independent adversarial review

Review date: 2026-07-11.  Scope: statistical bound, leakage boundary, cost
semantics, gate decision, reproducibility, and oracle-ceiling interpretation.

## Verdict

No fatal issue was found that reverses the core result:

> Public Gate B is NO_GO under the registered pseudo-event design.

The reviewer independently reproduced all output hashes, verified the raw-row
algebra, and found the exact hypergeometric inversion and remaining-residual
coverage semantics correct.

## Findings and resolutions

1. **Audit identity/certification cost was ambiguous.**  The simulator used an
   audited anchor as a discovered event without a second certification charge.
   Resolution: the contract now explicitly defines complete `AuditUnit` as
   returning event identity on a positive result, with identification included
   in its unit cost.  This remains a pilot assumption requiring real cost data.
2. **Dense cost had ambiguous output semantics.**  Resolution: dense is now
   defined as 347 complete `AuditUnit` operations, matching event-identifying
   output semantics; code uses the registered audit-unit cost.
3. **Oracle-ceiling interpretation was too causal.**  Resolution: it is now an
   idealized feasibility region only.  Budgets 21–30 were added; the first GO
   occurs only at B=24 after evaluator-perfect discovery of 24/26 events.

## Coverage diagnostic

The lowest empirical fixed-cell coverage is 0.938 at proxy-top, discovery
budget 20, audit n=40.  The reviewer computed exact expected coverage 0.95606
for that fixed population/design, so the 469/500 empirical outcome is
consistent with Monte Carlo variation rather than evidence of a bound bug.
The below-0.94 observation remains reported because it triggered the audit.

## Remaining non-claims

This review does not validate the equal-unit-cost assumption, a real typed
oracle, sequential stopping, a semantic index, or cross-video guarantees.

