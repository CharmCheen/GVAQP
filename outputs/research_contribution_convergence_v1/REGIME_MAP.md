# Regime Map: What Current P0 Actually Shows

All rows use the frozen V10 model-relative reference and P0 V3 same-trace replay. They are descriptive repeated-measure cells, not independent random samples.

| Regime | Observed evidence | Interpretation | Claim status |
|---|---|---|---|
| B=5 | median ΔF1 `0`; only 2/9 strict K3 improvements | Often no useful positives are exposed, so materialization cannot recover an event the trace has not observed. | SUPPORTED |
| B=10 | median ΔF1 `+0.0256`; 5/9 strict improvements | Small traces begin to expose sparse anchors but many cells still tie. | SUPPORTED |
| B=20 | median ΔF1 `+0.1218`; 7/9 strict improvements | Continuity-constrained grouping becomes material once multiple anchors exist. | SUPPORTED |
| B=50 | median ΔF1 `+0.2573`; 8/9 strict improvements | Strong positive materialization regime. | SUPPORTED |
| B=80,100 | 9/9 strict K3 improvements at each budget; median `+0.3253`, `+0.3623` | Large sparse-query budgets expose multiple anchors; naive global merging becomes increasingly destructive. | SUPPORTED |
| StaticProxyRank | median ΔF1 `+0.2704`, 17/18 strict improvements | Proxy ranking exposes enough positives for grouping; K3 benefit is large. | SUPPORTED |
| UniformTemporal | median ΔF1 `+0.1813`, 14/18 strict improvements | Effect remains positive across videos, though below proxy ranking. | SUPPORTED |
| TemporalCoverage | median ΔF1 `+0.0182`, 9/18 strict improvements, no regressions | Mainly low-yield/equality regime; it does not falsify K3 but blocks selector-agnostic or universal-effect wording. | SUPPORTED LIMIT |
| Queried-negative barrier | C2→C3 median `0`; only 5/54 changes | Current traces rarely make a selected negative decisive for a merge. | NOT MAIN MECHANISM |
| Unknown/parse state | 6 selected unknowns total, no bridge; no parse failures | No empirical basis for partial-information state algebra beyond code semantics. | UNTESTED |
| Selector vs materializer | median pairwise selector difference `0.0982` < median materializer difference `0.1457`, but median selector spread `0.1596` > it | Materializer is comparable to individual selector differences, not demonstrably the dominant error source. | INCONCLUSIVE |

The stable evidence-backed boundary is therefore: **when a trace exposes multiple temporally separated verified-positive anchors, replacing a global all-positive span by local continuity grouping is important.** It is not evidence that every K3 rule, verified negatives, or materialization in general dominates selection.
