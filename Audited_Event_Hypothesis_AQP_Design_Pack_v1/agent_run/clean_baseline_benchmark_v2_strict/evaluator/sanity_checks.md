# Sanity Checks

| check                                               | status         | detail                                                                                                                                                    |
|:----------------------------------------------------|:---------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------|
| 100pct_top_proxy_event_recall                       | PASS           | recall=1.0                                                                                                                                                |
| 100pct_component_first_event_recall                 | PASS           | recall=1.0                                                                                                                                                |
| random_mean_recall_broadly_monotonic                | PASS           | {5: 0.019230769230769208, 10: 0.0442307692307692, 20: 0.08923076923076918, 50: 0.2092307692307692, 80: 0.29769230769230764, 100: 0.36192307692307696}     |
| no_duplicate_queries                                | PASS           | failed_runs=0                                                                                                                                             |
| logical_calls_within_budget                         | PASS           | failed_runs=0                                                                                                                                             |
| event_count_nonincrease_with_more_permissive_bridge | PASS           | bridge-safe groups cannot be fewer than original K3 groups by construction                                                                                |
| temporal_nms_disabled_degeneracy                    | NOT_APPLICABLE | no temporal NMS in frozen benchmark                                                                                                                       |
| coverage_novelty_disabled_degeneracy                | NOT_APPLICABLE | coverage variant not frozen and not run                                                                                                                   |
| selector_label_leakage_static_runtime               | PASS           | random/top-proxy/component-first use frozen cheap scores only; adapters expose labels only through audited replay access; MAP selects before label reveal |
| oracle_raw_cache_complete                           | PASS           | raw=347 units=347                                                                                                                                         |
