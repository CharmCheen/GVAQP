# 04 Temporal And Cluster Audit

## Recomputed Cluster Structure

- Positive anchors: 40.
- Positive clusters: 27.
- Singleton clusters: 21.
- Multi-anchor clusters: 6.
- Largest cluster: 9 anchors.
- P(1->1): 0.325; base positive rate: 0.115; lift: 2.82x.

## Inconsistency

The final report states 18 singleton and 9 multi-anchor clusters. The CSV, JSON, and recomputation support 21 singleton and 6 multi-anchor clusters. The likely cause is report text drift, not data corruption.

## AQP Implication

Temporal correlation is real but not dominant: most clusters are singletons, while one cluster has 9 anchors. Temporal coverage and cluster-aware evaluation are motivated, but a naive expansion/refine strategy is not automatically supported.

Detailed metrics are in `tables/temporal_cluster_recomputed_metrics.csv`.
