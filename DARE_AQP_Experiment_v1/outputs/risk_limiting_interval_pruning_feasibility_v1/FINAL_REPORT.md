# Risk-Limiting Audited Interval Pruning Feasibility Gate v1

## Decision

**`RISK_LIMITING_INTERVAL_NO_GO`.** Physical VLM calls: **0**.

No random-only or robust joint-feasible grid cell exists among 56,448 aggregate
cells, each evaluated with 500 audit seeds. Empirical confidence coverage is
1.0 for both conservative estimators, so the failure is not caused by bound
undercoverage.

## Decisive evidence

Even the evaluator-only exact-ANY ceiling requires 217 interval calls plus 26
certifications: cost 243, or 0.700288 dense, which fails the strict `<0.70`
target before any probability audit. Risk-limiting B2/B3 must additionally
audit provisional negatives. Cells that simultaneously achieve recall,
coverage and at least 0.9 certificate rate have minimum p95 cost 350
(1.008646 dense) for a single placement. The minimum configuration satisfying
those quality conditions across every placement costs 550 (1.5850 dense) and
audits all provisional blocks.

Some zero-audit hard-pruning diagnostics have empirical recall and cost below
the gates—for example 227 calls and recall 24/26—but their certificate rate is
zero. They are B1 evaluator diagnostics, not formal feasibility.

## Estimators and robustness

SRS HT and stratified HT are conditionally unbiased by design. Serfling and
Bonferroni-Serfling bounds have empirical coverage 1.0. Stratification reduces
median bound width from 324.595 to 106.426 anchors, but not enough to overcome
the full-block audit cost. Every random, boundary, multi-event, long-event,
low-proxy, adversarial, sibling-correlated and level-correlated configuration
fails the joint cost/recall/confidence gate.

B4 dual cover was not run because no overlap assignment/inclusion design had
been frozen before outcome simulation. COUNT only affected priority. No
independent-error or parametric VLM-error assumption supports the decision.

## Consequence

There is no finite physical-validation contract to derive because the robust
simulation region is empty. The provisional-pruning route is closed under the
frozen 80% recall, 70% dense-cost and unit-audit contract.
