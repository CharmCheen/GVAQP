# P0 V3 Materializer Validation V2

## Executive decision

`MATERIALIZATION_MAINLINE_DECISION = REVISE`

There is a non-uniform or insufficiently robust effect; report the observed regime boundary rather than promote a universal materialization mainline.

This is a **cached semantic-oracle replay under QUERY_BUDGET**, not a physical wall-clock or hard-deadline experiment.  It evaluates recovery of a frozen **model-relative** reference relation.  The reference events were constructed by full-grid current-V3 K3, so all event-level conclusions carry the qualified reference-construction interaction stated in the V10 circularity audit.

## Frozen experimental contract

- Protocol: `ad619c84aaa396c727982fa554232c54243bc78008048c174eff6202c68c59f2`.
- Videos: DALI, HANGZHOU, WUHAN (three independent source videos).
- Candidate/proxy source: prospective frozen protocol `089f44f5e27dc398f2b10018b39ddb00eff1c7f277ad023af7015d4fac5e34f1`.
- Reference: V10 1475/1475 release `53bceb8be451e8ac853810bdde75ad25f6e0f89477621260d178d2dfbbef6ed2`.
- Selectors: UniformTemporal, StaticProxyRank, TemporalCoverage; all deterministic, no seeds beyond `0`.
- Budgets: [5, 10, 20, 50, 80, 100] semantic/oracle invocation calls per video/query.
- Primary matcher: strict positive temporal overlap; one-to-one maximum cardinality, then tIoU. Sensitivity uses tIoU > 0.30.
- Controlled invariant: K0/K3 consume byte-identical recorded query order and outcomes in every valid pair.

## Controlled matrix

Valid controlled pairs: `54` of `54`.  K3 better/equal/worse: `40 / 14 / 0` (`74.1%` strictly better).

Mean ΔF1: `0.1840` (bootstrap 95% CI `0.1405` to `0.2286`).  Median ΔF1: `0.1457` (bootstrap 95% CI `0.0832` to `0.2573`).

### Per independent video

- DALI: median ΔF1 `0.1377`, mean `0.1756`, K3-better `77.8%` (18 cells).
- HANGZHOU: median ΔF1 `0.1441`, mean `0.1682`, K3-better `72.2%` (18 cells).
- WUHAN: median ΔF1 `0.1675`, mean `0.2082`, K3-better `72.2%` (18 cells).

### Selector robustness

- UniformTemporal: median ΔF1 `0.1813`, K3-better `77.8%` (18 cells).
- StaticProxyRank: median ΔF1 `0.2704`, K3-better `94.4%` (18 cells).
- TemporalCoverage: median ΔF1 `0.0182`, K3-better `50.0%` (18 cells).

## Materializer versus selector effect

- Median `|K3-K0|`: `0.1457`.
- Median pairwise `|selector A-selector B|` at fixed K3: `0.0982`.
- Descriptive ratio: `1.4825`.
- Result: `MATERIALIZER_EFFECT_GREATER`.

## Mechanism diagnostics

Mean selected-negative units inside a multi-anchor prediction: K0 `24.370`, K3 `0.000`.  This diagnostic is trace-local rather than human-ground-truth causal evidence; detailed largest gains/regressions are in `failure_taxonomy.csv`.

## Allowed claim

Only the conditional mechanism claim supported by the recorded statistics: under sparse cached semantic verification, this experiment compares reconstruction of the frozen full-grid **model-relative K3-defined event relation**.  It does not establish human semantic correctness, universal event-boundary superiority, or hard-deadline superiority.
