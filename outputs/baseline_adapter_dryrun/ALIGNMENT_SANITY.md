# Proxy / Reference Alignment Sanity

Input files:

- `outputs/baseline_adapter_dryrun/frame_scores_adapter_ready.csv`
- `outputs/baseline_adapter_dryrun/reference_segments_adapter_ready.csv`

Generated tables:

- `outputs/baseline_adapter_dryrun/proxy_reference_alignment.csv`
- `outputs/baseline_adapter_dryrun/frame_scores_with_reference_overlap.csv`
- `outputs/baseline_adapter_dryrun/reference_event_unit_coverage.csv`
- `outputs/baseline_adapter_dryrun/topk_proxy_coverage.csv`

## Proxy Distribution Summary

| group                               |   count |   proxy_min |   proxy_p10 |   proxy_p25 |   proxy_median |   proxy_mean |   proxy_p75 |   proxy_p90 |   proxy_max |   oracle_positive_units |   covered_reference_events |
|:------------------------------------|--------:|------------:|------------:|------------:|---------------:|-------------:|------------:|------------:|------------:|------------------------:|---------------------------:|
| all_units                           |     600 |   0.0263832 |    0.113567 |    0.164511 |       0.231951 |     0.239023 |    0.308783 |    0.368834 |    0.520573 |                      80 |                        nan |
| oracle_positive_units               |      80 |   0.105834  |    0.205969 |    0.245637 |       0.299948 |     0.30604  |    0.36194  |    0.424269 |    0.49719  |                      80 |                        nan |
| oracle_negative_units               |     520 |   0.0263832 |    0.109827 |    0.153021 |       0.21836  |     0.228712 |    0.292167 |    0.356354 |    0.520573 |                       0 |                        nan |
| reference_covered_units_any_overlap |      80 |   0.105834  |    0.205969 |    0.245637 |       0.299948 |     0.30604  |    0.36194  |    0.424269 |    0.49719  |                      80 |                        nan |
| not_reference_covered_units         |     520 |   0.0263832 |    0.109827 |    0.153021 |       0.21836  |     0.228712 |    0.292167 |    0.356354 |    0.520573 |                       0 |                        nan |

## Top-K Proxy Coverage

| group                |   top_k |   selected_units |   oracle_positive_units_in_top_k |   oracle_positive_unit_recall |   reference_overlap_units_in_top_k |   reference_events_covered_any_overlap |   reference_event_recall_any_overlap |   min_proxy_in_top_k |   mean_proxy_in_top_k |
|:---------------------|--------:|-----------------:|---------------------------------:|------------------------------:|-----------------------------------:|---------------------------------------:|-------------------------------------:|---------------------:|----------------------:|
| top_k_proxy_coverage |       5 |                5 |                                2 |                        0.025  |                                  2 |                                      1 |                                 0.05 |             0.480377 |              0.498883 |
| top_k_proxy_coverage |      10 |               10 |                                5 |                        0.0625 |                                  5 |                                      2 |                                 0.1  |             0.472064 |              0.486914 |
| top_k_proxy_coverage |      20 |               20 |                                7 |                        0.0875 |                                  7 |                                      2 |                                 0.1  |             0.431084 |              0.470199 |
| top_k_proxy_coverage |      50 |               50 |                               15 |                        0.1875 |                                 15 |                                      4 |                                 0.2  |             0.381368 |              0.429434 |
| top_k_proxy_coverage |     100 |              100 |                               28 |                        0.35   |                                 28 |                                      9 |                                 0.45 |             0.340804 |              0.394183 |
| top_k_proxy_coverage |     200 |              200 |                               47 |                        0.5875 |                                 47 |                                     11 |                                 0.55 |             0.278501 |              0.35131  |

## Reference Event Unit Coverage

Each reference event overlaps at least one adapter unit. Summary:

```text
reference_events=20
reference_events_with_any_units=20
reference_events_with_positive_units=20
reference_covered_units=80
reference_covered_oracle_positive_units=80
```

## Initial Interpretation

- Oracle-positive units have higher proxy scores on average than negatives, but the top-k proxy prefix covers only a small fraction of the 20 reference events at low k.
- Reference events are represented in the unit grid, so an all-positive-unit upper bound should be checked before blaming the IoU protocol.
- The low baseline scores in the dry-run are plausibly a mix of weak low-budget proxy ranking and segment formation mismatch, not an immediate reference-file absence problem.
