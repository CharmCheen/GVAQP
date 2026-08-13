# Materializer interaction

The 54 reported interaction cells reproduce exactly from the frozen traces; their subgroup median C1−C0 range is **0.2573**. C0 collapses all positive anchors into one span, whereas C1 splits anchor groups separated by more than 10 seconds. Across all 378 C1 traces, the strongest descriptive geometry association with C1 gain is `positive_cluster_count` (Spearman 0.967). This is an outcome-preserving mechanism explanation, not a causal estimate.

```text
video_id           policy   median     mean  count
    DALI  StaticProxyRank 0.169161 0.194300     42
    DALI TemporalCoverage 0.070730 0.105245     42
    DALI  UniformTemporal 0.137703 0.157751     42
HANGZHOU  StaticProxyRank 0.166455 0.209849     42
HANGZHOU TemporalCoverage 0.025304 0.077937     42
HANGZHOU  UniformTemporal 0.133124 0.146133     42
   WUHAN  StaticProxyRank 0.247489 0.273264     42
   WUHAN TemporalCoverage 0.032768 0.080694     42
   WUHAN  UniformTemporal 0.181064 0.230091     42

                           feature  spearman_with_DeltaMaterializer  p_value_descriptive
            positive_cluster_count                         0.967235        5.888319e-226
 positive_anchor_temporal_span_sec                         0.774351         9.756978e-77
number_of_temporal_regions_touched                         0.759935         2.441793e-72
        positive_anchor_dispersion                         0.735801         1.245397e-65
          queries_per_local_region                         0.665200         1.216313e-49
       largest_unqueried_gap_units                        -0.522191         7.893764e-28
              max_positive_gap_sec                         0.518175         2.334467e-27
        median_unqueried_gap_units                        -0.464027         1.397962e-21
                    positive_yield                         0.451002         2.445467e-20
           median_positive_gap_sec                         0.396244         1.160930e-15
                 coverage_fraction                         0.354875         1.165370e-12
               positive_redundancy                         0.328210         6.066134e-11
         queried_temporal_span_sec                         0.309459         7.836121e-10
     near_duplicate_query_fraction                         0.149989         3.466715e-03
```
