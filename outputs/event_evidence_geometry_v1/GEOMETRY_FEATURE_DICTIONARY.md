# Geometry feature dictionary

All trace features are derived from frozen query positions and cached outcomes. `POLICY_VISIBLE` features use timestamps/queried positions only. `ORACLE_OBSERVED_AFTER_QUERY` features additionally use verified outcomes. `OFFLINE_DIAGNOSTIC_ONLY` features join frozen reference event IDs and must never be policy-visible.

| Feature family | Features | Status | Definition |
|---|---|---|---|
| Yield | queried_units, verified_positive_count, positive_yield | ORACLE_OBSERVED_AFTER_QUERY | Query count, cached positives, and their ratio. |
| Temporal coverage | queried_temporal_span_sec, coverage_fraction, number_of_temporal_regions_touched, largest_unqueried_gap_units, median_unqueried_gap_units | POLICY_VISIBLE | Span/coverage of queried timestamps; regions are consecutive original-unit runs; holes include boundary holes. |
| Positive anchors | positive_anchor_*, median/max_positive_gap_sec, positive_cluster_count | ORACLE_OBSERVED_AFTER_QUERY | Geometry of queried relevant anchors; clusters split at a gap >10 s, exactly C1's threshold. |
| Redundancy | queries_per_local_region, near_duplicate_query_fraction, positive_redundancy | POLICY_VISIBLE / ORACLE_OBSERVED_AFTER_QUERY | Ten fixed temporal bins; adjacent-query rate; fraction of anchors beyond one per C1 cluster. |
| Reference aware | *_OFFLINE_DIAGNOSTIC_ONLY | OFFLINE_DIAGNOSTIC_ONLY | Frozen K3 reference-event join; used only as an explanatory upper diagnostic. |
