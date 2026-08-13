# P1-A Trace-diversity feasibility audit

- **status**: `PASS_SINGLE_QUERY_TRACE_FEASIBILITY`
- **trace_population**: `251`
- **exact_equal_yield_matched_strata**: `49`
- **video_query_clusters_represented**: `3`
- **matched_strata_by_video**: `{'DALI': 17, 'HANGZHOU': 16, 'WUHAN': 16}`
- **effective_independent_comparison_count**: `49`
- **median_primary_geometry_range**: `3.0`
- **rule**: `PASS requires >=12 exact-yield geometry-varying strata, all 3 available video-query clusters represented, and >=3 strata/video; this certifies only trace feasibility, never P1 scientific success.`
- **outcome_blind_generation**: `True`
- **caveat**: `Only one released semantic query and Proxy A are available. Passing this audit does not satisfy P1's six video-query clusters or two-natural-proxy requirements.`

Trace generators were fixed before cached outcomes were joined: UniformTemporal, StaticProxyRank, CoverageFirst, three fixed MMR weights, and eight seeded temporal hashes. Outcomes never choose or rank a trace. Exact verified-positive count is the primary matched-yield stratum; no near-yield relaxation is used here.
