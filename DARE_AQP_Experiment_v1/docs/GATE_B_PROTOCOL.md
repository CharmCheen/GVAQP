# Gate B protocol: audit identifiability and coverage

## Decision-critical question

Can an independent audit provide a 95% lower confidence bound on pseudo-event
recall at materially lower total cost than querying all 347 units?

## Competing hypotheses

- **H-B1 (useful certificate):** for at least one public discovery control,
  a preregistered fixed audit stage certifies 80% recall in at least 90% of
  seeds with median total logical cost below 70% of a dense complete audit
  (243 calls under the v1 equal-unit-cost assumption).
- **H-B0 (certificate bottleneck):** meeting the same certification rate costs
  at least 70% of dense scan, or no tested fixed stage reaches it.
- **H-Balt (search-limited):** proxy-top differs materially from uniform, so a
  better Gate-A signal could move Gate B across the cost threshold.

The 70% threshold is a pilot engineering gate, not a theorem or publication
standard.

## Design

For each discovery policy, discovery budget, and seed:

1. execute discovery without reference-informed ranking;
2. certify distinct pseudo-events returned by positive units;
3. define residual canonical-anchor indicators on the remaining unit frame;
4. draw a simple random sample without replacement using an audit-only RNG;
5. invert the hypergeometric CDF for an exact one-sided upper bound on the
   pre-audit residual count;
6. add audited anchors to the discovered set and compute
   `recall_lb = D_after / (D_after + U_remaining)`.

Each audit size is a separately interpreted **fixed stage**.  Selecting a
stage after inspecting the same run's outcomes would require alpha spending or
an anytime-valid confidence sequence and is outside v1.

## Estimands

- empirical coverage of `R_remaining <= U_remaining` over 500 seeds;
- certification rate `P(recall_lb >= target)` at each fixed audit size;
- median and p90 total logical cost;
- true pseudo-event recall (evaluator only);
- discovery events per presence call.

An evaluator-only `oracle_anchor_ceiling` orders one distinct canonical anchor
per event before non-anchors.  It is reported separately and cannot make the
public Gate B decision pass.  Its sole purpose is to distinguish a weak-search
failure from a certificate that remains costly even under ideal discovery.
Budgets 21–30 are included only for this diagnostic to locate the idealized
feasibility threshold; they are not public-method tuning points.

## Gate decision

For each method/budget and target, choose the smallest *population-level fixed
stage* whose certification rate is at least 90%.  Gate B passes for 80% recall
only if its median total logical cost is below 243 and empirical coverage is at
least 0.94.  The coverage tolerance is diagnostic; the exact method's nominal
guarantee follows from the registered sampling model, not from 500 trials.

## Falsifiers and interpretation limits

- Any empirical undercoverage below 0.94 triggers an implementation audit.
- Duplicate canonical anchors invalidate the binary hypergeometric model.
- Audit/discovery RNG coupling invalidates the conditional-independence claim.
- Results concern one VLM-defined pseudo-event video only.
- Cost conclusions change if real `CertifyEvent` or `AuditBlock` costs differ.
