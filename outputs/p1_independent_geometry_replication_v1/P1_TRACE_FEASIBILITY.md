# P1-A trace-diversity feasibility audit

## Decision

`P1_TRACE_FEASIBILITY = PASS`

The outcome-blind population has **1008** trace-query instances from 504 frozen trace identities. It covers 3 independent videos × 2 queries × 2 natural proxies × 6 budgets and 7 generator families. B0/B1/B2 are also the exact B4 historical frozen-policy lineages and are represented once, avoiding duplicate pseudo-replication.

- Exact-yield, geometry-varying strata: **198**.
- Near-yield (difference ≤1) secondary pairs: **262**.
- Independent video-query clusters: **6/6**.
- Natural proxies: **2/2**.
- Budgets represented: **6/6**.
- Pair endpoint generator families: **5**.
- Median exact-pair region contrast: **3.0** regions.
- Effective independent comparison count: **6 video-query clusters**, not 198 trace strata.
- Proxy-collapsed unique exact trace contrasts: **145**; proxy-blind duplicates are not independent replication.

Exact strata by video-query: `{('DALI', 'Q_DRIVER_RESPONSE_V1'): 37, ('DALI', 'Q_VULNERABLE_ROAD_USER_CONFLICT_V1'): 27, ('HANGZHOU', 'Q_DRIVER_RESPONSE_V1'): 31, ('HANGZHOU', 'Q_VULNERABLE_ROAD_USER_CONFLICT_V1'): 37, ('WUHAN', 'Q_DRIVER_RESPONSE_V1'): 33, ('WUHAN', 'Q_VULNERABLE_ROAD_USER_CONFLICT_V1'): 33}`.

Exact strata by proxy: `{'PROXY_A_YOLOV8N_OBJECT_MOTION': 105, 'PROXY_B_OPTICAL_FLOW_VISUAL_DYNAMICS': 93}`.

## Frozen gate

```json
{
  "checks": {
    "all_six_video_query_clusters": true,
    "both_natural_proxies": true,
    "median_region_contrast": true,
    "minimum_budgets_per_video_query_proxy": true,
    "minimum_exact_pairs": true,
    "minimum_exact_pairs_per_video_query_proxy": true,
    "multiple_generator_families": true
  },
  "rule": {
    "interpretation": "trace-identifiability gate only; within-cluster strata are not independent samples",
    "minimum_budgets_per_video_query_proxy": 4,
    "minimum_exact_pairs": 48,
    "minimum_exact_pairs_per_video_query_proxy": 6,
    "minimum_median_region_contrast": 2.0,
    "minimum_pair_endpoint_generator_families": 4,
    "required_proxy_families": 2,
    "required_video_query_clusters": 6
  }
}
```

Pairs were selected only after exact/near yield matching, using public geometry contrast and fixed public tie-breaks. Human/reference outcomes were not available. This PASS establishes experimental contrast and identification capacity only; it is not evidence that geometry improves independent event recovery.
