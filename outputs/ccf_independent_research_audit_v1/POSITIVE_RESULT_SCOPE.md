# Positive-result scope

Which "positive" results are robust, and which are reference-, evaluator-,
materializer-, proxy-, budget-, or substrate-sensitive.

## 1. Materialization gain (K3 vs K0, median Delta F1 +0.1457)

- Robust: direction and magnitude are consistent across 3 videos and 3
  selectors (54/54 >=, 40/54 >, 0 worse).
- Sensitive to reference: the reference is K3-defined/model-relative
  (circularity-qualified). It tests reconstruction of the frozen K3-defined
  relation, not independent event truth.
- Sensitive to materializer: mechanism ablation shows it is almost entirely
  C1 gap-only, so K3 "complexity" is not the cause.
- Verdict: bounded, model-relative, conditional; not a general superiority claim.

## 2. Geometry explanatory power (LOVO R2 0.006 -> 0.795)

- Robust within the model-relative K3 world: hold-out R2 and Pearson are large
  and stable across the 378-cell split.
- Sensitive to reference: the strong signal is likely induced by the C1-shaped,
  K3-defined reference (positive_cluster_count Spearman 0.967 with materializer
  gain, a near-definitional overlap).
- Not replicated on the VLM shadow (R2 0.071, MAE gain 0.000665).
- Verdict: an artifact-prone model-relative association, not an established
  independent mechanism.

## 3. StaticProxyRank as robust policy

- Robust within the frozen matrix under the lexicographic worst-proxy rule.
- Sensitive to proxy: it depends on Proxy A (YOLOv8n); Proxy B (optical flow)
  is weakly correlated and weak for labels, and the P2 audit shows
  relevance+coverage ties it.
- Verdict: a proxy-specific strong default, not a general solution.

## 4. Resource monotonicity (0.48% violations)

- Robust for nested policies over oracle-call budgets.
- Sensitive to budget semantics: query-count, not physical wall-clock or hard
  deadline.
- Verdict: a clean reliability finding with a bounded scope.

## 5. Fixed SCAN1-to-VERIFY1 default (mean anytime recall AUC 0.13323)

- Robust within the cached sequential study.
- Sensitive to costs (abstract 0.1/1.0) and reference (older query/reference).
- Verdict: bounded default, not universal optimum.

## 6. Physical Guangzhou deadline-safe B result

- Robust for repeatability on the same source (one event at ~224 s in both runs).
- Sensitive to source (single video), event (single event), and reference.
- Verdict: exploratory, single-source/single-event, scoped systems observation.

## Cross-cutting sensitivity table

| Positive result | Reference | Evaluator | Materializer | Proxy | Budget | Substrate |
|---|---|---|---|---|---|---|
| Materialization gain | HIGH | MEDIUM | HIGH (C1) | LOW | MEDIUM | MEDIUM |
| Geometry R2 | HIGH | MEDIUM | HIGH | LOW | MEDIUM | MEDIUM |
| StaticProxyRank win | MEDIUM | MEDIUM | LOW | HIGH | MEDIUM | MEDIUM |
| Monotonicity | MEDIUM | MEDIUM | LOW | LOW | HIGH | MEDIUM |
| SCAN1-VERIFY1 default | MEDIUM | MEDIUM | LOW | MEDIUM | MEDIUM | HIGH |
| Guangzhou B | MEDIUM | MEDIUM | LOW | LOW | MEDIUM | HIGH |

HIGH = the result depends strongly on this axis. LOW = weakly dependent.

## Summary

No current positive result survives contact with an independent (non-K3,
non-model-relative) reference. The strongest positives are bounded system
findings: the C1 gap operator and the ranking-vs-exposure identifiability
result. These are publishable only as components of a scoped systems/design
story, not as a general algorithmic contribution.
