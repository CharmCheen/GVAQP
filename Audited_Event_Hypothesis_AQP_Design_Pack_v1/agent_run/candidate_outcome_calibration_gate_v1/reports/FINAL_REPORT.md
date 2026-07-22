# Candidate and Outcome Calibration Gate v1

Decision: `CHEAP_CANDIDATE_CONSTRUCTION_REQUIRED`

## Strongest supported conclusion

Frozen facts reproduce exactly. H1 core candidates cover `0.461538` of the 26 VLM-defined pseudo-events; the full legal H1 action universe covers `0.769231`. Actual H1 AUC is `0.314990` and evaluator-only greedy reorder AUC is `0.664458`, versus MAP/M1 `0.388056` and best native `0.389659`.

The oracle reorder is an estimated greedy ceiling, not an exact optimum or runnable method. Low-budget ranking headroom is B5 `0.322581`, B10 `0.481481`, B20 `0.523810`.

## Static candidate ceilings

| ordering                   |   budget |   positive_units_in_top_b |   distinct_reference_events_touched |   event_candidate_recall |   materialized_event_f1 |
|:---------------------------|---------:|--------------------------:|------------------------------------:|-------------------------:|------------------------:|
| ACTUAL_H1_PUBLIC_ORDER     |        5 |                         0 |                                   0 |                0         |               0         |
| ACTUAL_H1_PUBLIC_ORDER     |       10 |                         1 |                                   1 |                0.0384615 |               0.0740741 |
| ACTUAL_H1_PUBLIC_ORDER     |       20 |                         2 |                                   2 |                0.0769231 |               0.142857  |
| ACTUAL_H1_PUBLIC_ORDER     |       50 |                         5 |                                   5 |                0.192308  |               0.322581  |
| ACTUAL_H1_PUBLIC_ORDER     |       80 |                         9 |                                   8 |                0.307692  |               0.457143  |
| ACTUAL_H1_PUBLIC_ORDER     |      100 |                        11 |                                  10 |                0.384615  |               0.540541  |
| PERFECT_UNIQUE_EVENT_ORDER |        5 |                         5 |                                   5 |                0.192308  |               0.322581  |
| PERFECT_UNIQUE_EVENT_ORDER |       10 |                        10 |                                  10 |                0.384615  |               0.555556  |
| PERFECT_UNIQUE_EVENT_ORDER |       20 |                        20 |                                  20 |                0.769231  |               0.869565  |
| PERFECT_UNIQUE_EVENT_ORDER |       50 |                        29 |                                  20 |                0.769231  |               0.833333  |
| PERFECT_UNIQUE_EVENT_ORDER |       80 |                        29 |                                  20 |                0.769231  |               0.833333  |
| PERFECT_UNIQUE_EVENT_ORDER |      100 |                        29 |                                  20 |                0.769231  |               0.833333  |

Six events are absent even from the full legal H1 universe: `vlm_event_0004, vlm_event_0007, vlm_event_0009, vlm_event_0016, vlm_event_0024, vlm_event_0025`. Fourteen events are absent from the core-only universe.

Of the 20 represented events, `2` first appear in the frozen public top 20, `8` at ranks 21–100, and `10` only after the formal B100 trace under the deterministic universe-audit append order.

## Oracle-informed reorder

|   budget |   unique_events_discovered |   event_precision |   event_recall |   event_f1 |   returned_seconds |   overmerge |   oversplit |
|---------:|---------------------------:|------------------:|---------------:|-----------:|-------------------:|------------:|------------:|
|        5 |                          5 |                 1 |       0.192308 |   0.322581 |                 50 |           0 |           0 |
|       10 |                         10 |                 1 |       0.384615 |   0.555556 |                100 |           0 |           0 |
|       20 |                         13 |                 1 |       0.5      |   0.666667 |                130 |           0 |           0 |
|       50 |                         13 |                 1 |       0.5      |   0.666667 |                130 |           0 |           0 |
|       80 |                         14 |                 1 |       0.538462 |   0.7      |                140 |           0 |           0 |
|      100 |                         15 |                 1 |       0.576923 |   0.731707 |                160 |           0 |           0 |

Its event-F1 AUC is `0.664458`. This is a greedy estimate, not a proven optimum.

## Headroom decomposition

|   budget |   candidate_headroom |   ranking_headroom |   materialization_gap |
|---------:|---------------------:|-------------------:|----------------------:|
|        5 |             0.192308 |           0.322581 |           5.55112e-17 |
|       10 |             0.346154 |           0.481481 |           0           |
|       20 |             0.692308 |           0.52381  |           0.202899    |
|       50 |             0.576923 |           0.344086 |           0.202899    |
|       80 |             0.461538 |           0.242857 |           0.169565    |
|      100 |             0.384615 |           0.191167 |           0.137858    |

`materialization_gap` in `FINAL_DECISION.csv` is the B20 combined greedy-reorder/K3 gap (`0.202899`); the decomposition is not treated as an additive identity.

## Calibration and feasibility

Positive belief: Brier `0.158060`, ECE `0.219794`. New-event belief: Brier `0.149916`, ECE `0.234503`. Fixed blocked-crossfit F2 AUROC is positive `0.5482815057283144` and certifiable-event `0.5482815057283144`. Preregistered stable-signal gate: `False`.

| target    |    brier |      ece |    auroc |   average_precision |   top20_hits |
|:----------|---------:|---------:|---------:|--------------------:|-------------:|
| positive  | 0.15806  | 0.219794 | 0.546143 |            0.14225  |            0 |
| new_event | 0.149916 | 0.234503 | 0.502504 |            0.115319 |            0 |

### Fixed blocked-cross-validation feasibility

| target                | feature_set      |   prevalence |    brier |    auroc |   average_precision |
|:----------------------|:-----------------|-------------:|---------:|---------:|--------------------:|
| can_certify_any_event | F0_proxy_only    |     0.121495 | 0.109985 | 0.382979 |            0.100172 |
| can_certify_any_event | F1_proxy_source  |     0.121495 | 0.110334 | 0.405892 |            0.10497  |
| can_certify_any_event | F2_all_public_H1 |     0.121495 | 0.110175 | 0.548282 |            0.18681  |
| is_positive           | F0_proxy_only    |     0.121495 | 0.109985 | 0.382979 |            0.100172 |
| is_positive           | F1_proxy_source  |     0.121495 | 0.110334 | 0.405892 |            0.10497  |
| is_positive           | F2_all_public_H1 |     0.121495 | 0.110175 | 0.548282 |            0.18681  |

All defined F2 temporal-fold AUROCs are below `0.5`; one fold contains no positives, so its AUROC is correctly undefined. The current public features therefore do not pass the stable-signal gate.

## H1 / MAP / ARC ranking divergence

|   k | left_method   | right_method      |   unit_overlap |   jaccard_overlap |   left_unique_events |   right_unique_events |   first_ranking_divergence |
|----:|:--------------|:------------------|---------------:|------------------:|---------------------:|----------------------:|---------------------------:|
|   5 | H1            | MAP_M1            |              4 |         0.666667  |                    0 |                     0 |                          3 |
|   5 | H1            | ARC_NATIVE        |              0 |         0         |                    0 |                     0 |                          1 |
|   5 | H1            | ORACLE_H1_REORDER |              0 |         0         |                    0 |                     5 |                          1 |
|  10 | H1            | MAP_M1            |              9 |         0.818182  |                    1 |                     1 |                          3 |
|  10 | H1            | ARC_NATIVE        |              0 |         0         |                    1 |                     1 |                          1 |
|  10 | H1            | ORACLE_H1_REORDER |              1 |         0.0526316 |                    1 |                    10 |                          1 |
|  20 | H1            | MAP_M1            |             16 |         0.666667  |                    2 |                     3 |                          3 |
|  20 | H1            | ARC_NATIVE        |              0 |         0         |                    2 |                     3 |                          1 |
|  20 | H1            | ORACLE_H1_REORDER |              9 |         0.290323  |                    2 |                    13 |                          1 |

ARC ranking uses the frozen seed-0 trace only for unit-order comparison; best-native AUC uses the benchmark's authoritative cross-seed aggregation.

## Candidate source quality

| hypothesis_source   |   hypothesis_count |   positive_hypothesis_rate |   event_containing_rate |   unique_events_represented |   unique_events_with_certifying_core |   mean_first_public_rank |   mean_proxy_percentile |   top20_presence |   top50_presence |   false_burden |   fragmentation_contribution |
|:--------------------|-------------------:|---------------------------:|------------------------:|----------------------------:|-------------------------------------:|-------------------------:|------------------------:|-----------------:|-----------------:|---------------:|-----------------------------:|
| high_proxy_island   |                 55 |                   0.145455 |                0.181818 |                          11 |                                    8 |                     28   |                0.87385  |               20 |               50 |       0.818182 |                      1.09091 |
| orphan_local_peak   |                 32 |                   0.125    |                0.25     |                           8 |                                    4 |                     71.5 |                0.442843 |                0 |                0 |       0.75     |                      1       |

## Interpretation

Primary bottleneck: `candidate_absence_and_weak_public_separability`. This is single-video VLM-defined pseudo-oracle diagnostic evidence. No baseline was rerun, H1 was not modified, and no VLM/physical oracle inference occurred.

Perfect ordering proves ranking headroom but does **not** justify calibration: six events remain absent from the legal universe and the preregistered blocked-crossfit feature gate fails. Candidate/cheap-feature repair is therefore primary; K3 is not the low-budget bottleneck because oracle reorder reaches F1 `0.322581/0.555556/0.666667` at B5/10/20 with precision `1.0`.

## Exact next action

Run `Cheap Primitive Candidate Construction Gate v1`: on separate development videos, add or revise public-only cheap primitives, freeze the candidate rule, and require legal-universe event coverage plus blocked-cross-video separability before any planner work. Do not train a planner on this strict video.
