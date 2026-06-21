# VLM32B Pseudo-GT Budget Simulation

This report treats the available VLM32B scan as pseudo-GT / pseudo-oracle. It does not measure true real-world danger detection accuracy.

## Data Overview

- number of clips in proxy_scores: 102
- budget ratios: 0.05, 0.10, 0.15, 0.20, 0.30, 0.50
- methods evaluated: random, uniform_time, top_count, top_naive, top_kinematic, ensemble_count_naive, ensemble_all_proxy, temporal_nms_count, temporal_nms_naive, temporal_nms_ensemble, uniform_expansion, proxy_then_expansion_count, proxy_then_expansion_naive, proxy_then_expansion_ensemble
- event_merge_gap_sec: 4.000
- broad label available: True
- ego-relevant label available: True
- strict label available: True (strict variants include pre-derived labels from exact VLM fields)
- high-confidence label available: False (not used as a separate variant for strict-variant evaluation)

## Variant Overview

| variant | valid clips | positives | positive rate | events |
|---|---:|---:|---:|---:|
| broad | 102 | 96 | 0.941 | 2 |
| ego_relevant | 102 | 82 | 0.804 | 4 |
| strict | 102 | 68 | 0.667 | 7 |
| strict_v2 | 102 | 68 | 0.667 | 7 |
| strict_v3 | 102 | 68 | 0.667 | 7 |

## Strict Variant Answers

1. strict_v2 positive rate=0.667 (68/102); strict_v3 positive rate=0.667 (68/102).
2. Neither strict_v2 nor strict_v3 reaches the target 10%-30% range.
3. If still high, the likely cause is that the source VLM already marks many clips as high-confidence L2 ego-relevant cut_in/crossing events; field-level post-processing has little remaining leverage.
4. positive events: strict_v2=7, strict_v3=7.
5. average positive run length: strict_v2=8.500, strict_v3=8.500 clips.
6-7. strict_v2: low-budget 5%-20% best clip recall is `top_count` (0.199); best event recall is `top_kinematic` (0.893).
6-7. strict_v3: low-budget 5%-20% best clip recall is `top_count` (0.199); best event recall is `top_kinematic` (0.893).
8-12. strict_v2: temporal-NMS best avg event recall=0.857 vs top/ensemble best=0.571; expansion avg best clip/event recall=0.314/0.476; proxy-anchor sweep avg event recall=0.371 vs uniform-anchor=0.190; top_count/top_naive/ensemble avg clip recall=0.324/0.275/0.314; top_kinematic avg clip/event recall=0.213/0.929.
8-12. strict_v3: temporal-NMS best avg event recall=0.857 vs top/ensemble best=0.571; expansion avg best clip/event recall=0.314/0.476; proxy-anchor sweep avg event recall=0.371 vs uniform-anchor=0.190; top_count/top_naive/ensemble avg clip recall=0.324/0.275/0.314; top_kinematic avg clip/event recall=0.213/0.929.
13. Temporal-aware budget allocation is supported because dense clip recovery and event coverage prefer different policies: strict_v2: clip `top_count` vs event `top_kinematic`; strict_v3: clip `top_count` vs event `top_kinematic`.
14. More kinematic-v0 tuning is not justified; focus on proxy anchors, temporal diversity, and predicate definition.
15. A re-prompted 32B pass is needed for a truly rare predicate; post-processing these fields does not make the workload sparse enough.

## broad Label: Clip-Level Results

### Budget Ratio 0.05

Best clip recall: 0.062 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, proxy_then_expansion_naive, temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_count, top_kinematic, top_naive.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 6 | 0.062 | 1.000 | 0.118 | 6.00 | 1.000 | 2.00/2 |
| ensemble_count_naive | 6 | 0.062 | 1.000 | 0.118 | 6.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_ensemble | 6 | 0.062 | 1.000 | 0.118 | 6.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_naive | 6 | 0.062 | 1.000 | 0.118 | 6.00 | 1.000 | 2.00/2 |
| temporal_nms_count | 6 | 0.062 | 1.000 | 0.118 | 6.00 | 0.500 | 1.00/2 |
| temporal_nms_ensemble | 6 | 0.062 | 1.000 | 0.118 | 6.00 | 1.000 | 2.00/2 |
| temporal_nms_naive | 6 | 0.062 | 1.000 | 0.118 | 6.00 | 1.000 | 2.00/2 |
| top_count | 6 | 0.062 | 1.000 | 0.118 | 6.00 | 0.500 | 1.00/2 |
| top_kinematic | 6 | 0.062 | 1.000 | 0.118 | 6.00 | 1.000 | 2.00/2 |
| top_naive | 6 | 0.062 | 1.000 | 0.118 | 6.00 | 1.000 | 2.00/2 |
| random | 6 | 0.060 ± 0.005 | 0.958 ± 0.074 | 0.113 ± 0.009 | 5.75 | 1.000 | 2.00/2 |
| proxy_then_expansion_count | 6 | 0.052 | 0.833 | 0.098 | 5.00 | 0.500 | 1.00/2 |
| uniform_expansion | 6 | 0.052 | 0.833 | 0.098 | 5.00 | 0.500 | 1.00/2 |
| uniform_time | 6 | 0.042 | 0.667 | 0.078 | 4.00 | 1.000 | 2.00/2 |

### Budget Ratio 0.10

Best clip recall: 0.115 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, proxy_then_expansion_naive, temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_count, top_kinematic, top_naive.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 11 | 0.115 | 1.000 | 0.206 | 11.00 | 1.000 | 2.00/2 |
| ensemble_count_naive | 11 | 0.115 | 1.000 | 0.206 | 11.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_ensemble | 11 | 0.115 | 1.000 | 0.206 | 11.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_naive | 11 | 0.115 | 1.000 | 0.206 | 11.00 | 1.000 | 2.00/2 |
| temporal_nms_count | 11 | 0.115 | 1.000 | 0.206 | 11.00 | 1.000 | 2.00/2 |
| temporal_nms_ensemble | 11 | 0.115 | 1.000 | 0.206 | 11.00 | 1.000 | 2.00/2 |
| temporal_nms_naive | 11 | 0.115 | 1.000 | 0.206 | 11.00 | 1.000 | 2.00/2 |
| top_count | 11 | 0.115 | 1.000 | 0.206 | 11.00 | 0.500 | 1.00/2 |
| top_kinematic | 11 | 0.115 | 1.000 | 0.206 | 11.00 | 1.000 | 2.00/2 |
| top_naive | 11 | 0.115 | 1.000 | 0.206 | 11.00 | 1.000 | 2.00/2 |
| random | 11 | 0.108 ± 0.007 | 0.945 ± 0.062 | 0.194 ± 0.013 | 10.40 | 1.000 | 2.00/2 |
| proxy_then_expansion_count | 11 | 0.104 | 0.909 | 0.187 | 10.00 | 0.500 | 1.00/2 |
| uniform_expansion | 11 | 0.104 | 0.909 | 0.187 | 10.00 | 0.500 | 1.00/2 |
| uniform_time | 11 | 0.094 | 0.818 | 0.168 | 9.00 | 1.000 | 2.00/2 |

### Budget Ratio 0.15

Best clip recall: 0.167 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, proxy_then_expansion_naive, temporal_nms_count, temporal_nms_ensemble, top_count, top_kinematic, top_naive.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 16 | 0.167 | 1.000 | 0.286 | 16.00 | 1.000 | 2.00/2 |
| ensemble_count_naive | 16 | 0.167 | 1.000 | 0.286 | 16.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_ensemble | 16 | 0.167 | 1.000 | 0.286 | 16.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_naive | 16 | 0.167 | 1.000 | 0.286 | 16.00 | 1.000 | 2.00/2 |
| temporal_nms_count | 16 | 0.167 | 1.000 | 0.286 | 16.00 | 1.000 | 2.00/2 |
| temporal_nms_ensemble | 16 | 0.167 | 1.000 | 0.286 | 16.00 | 1.000 | 2.00/2 |
| top_count | 16 | 0.167 | 1.000 | 0.286 | 16.00 | 0.500 | 1.00/2 |
| top_kinematic | 16 | 0.167 | 1.000 | 0.286 | 16.00 | 1.000 | 2.00/2 |
| top_naive | 16 | 0.167 | 1.000 | 0.286 | 16.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_count | 16 | 0.156 | 0.938 | 0.268 | 15.00 | 0.500 | 1.00/2 |
| temporal_nms_naive | 16 | 0.156 | 0.938 | 0.268 | 15.00 | 1.000 | 2.00/2 |
| uniform_expansion | 16 | 0.156 | 0.938 | 0.268 | 15.00 | 0.500 | 1.00/2 |
| random | 16 | 0.155 ± 0.010 | 0.931 ± 0.060 | 0.266 ± 0.017 | 14.90 | 1.000 | 2.00/2 |
| uniform_time | 16 | 0.146 | 0.875 | 0.250 | 14.00 | 1.000 | 2.00/2 |

### Budget Ratio 0.20

Best clip recall: 0.219 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, proxy_then_expansion_naive, top_count, top_kinematic, top_naive.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 21 | 0.219 | 1.000 | 0.359 | 21.00 | 1.000 | 2.00/2 |
| ensemble_count_naive | 21 | 0.219 | 1.000 | 0.359 | 21.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_ensemble | 21 | 0.219 | 1.000 | 0.359 | 21.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_naive | 21 | 0.219 | 1.000 | 0.359 | 21.00 | 1.000 | 2.00/2 |
| top_count | 21 | 0.219 | 1.000 | 0.359 | 21.00 | 0.500 | 1.00/2 |
| top_kinematic | 21 | 0.219 | 1.000 | 0.359 | 21.00 | 1.000 | 2.00/2 |
| top_naive | 21 | 0.219 | 1.000 | 0.359 | 21.00 | 1.000 | 2.00/2 |
| random | 21 | 0.210 ± 0.009 | 0.960 ± 0.042 | 0.344 ± 0.015 | 20.15 | 1.000 | 2.00/2 |
| proxy_then_expansion_count | 21 | 0.208 | 0.952 | 0.342 | 20.00 | 0.500 | 1.00/2 |
| temporal_nms_count | 21 | 0.208 | 0.952 | 0.342 | 20.00 | 1.000 | 2.00/2 |
| temporal_nms_ensemble | 21 | 0.208 | 0.952 | 0.342 | 20.00 | 1.000 | 2.00/2 |
| temporal_nms_naive | 21 | 0.208 | 0.952 | 0.342 | 20.00 | 1.000 | 2.00/2 |
| uniform_expansion | 21 | 0.208 | 0.952 | 0.342 | 20.00 | 0.500 | 1.00/2 |
| uniform_time | 21 | 0.198 | 0.905 | 0.325 | 19.00 | 1.000 | 2.00/2 |

### Budget Ratio 0.30

Best clip recall: 0.323 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, proxy_then_expansion_naive, top_count, top_kinematic, top_naive.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 31 | 0.323 | 1.000 | 0.488 | 31.00 | 1.000 | 2.00/2 |
| ensemble_count_naive | 31 | 0.323 | 1.000 | 0.488 | 31.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_ensemble | 31 | 0.323 | 1.000 | 0.488 | 31.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_naive | 31 | 0.323 | 1.000 | 0.488 | 31.00 | 1.000 | 2.00/2 |
| top_count | 31 | 0.323 | 1.000 | 0.488 | 31.00 | 0.500 | 1.00/2 |
| top_kinematic | 31 | 0.323 | 1.000 | 0.488 | 31.00 | 1.000 | 2.00/2 |
| top_naive | 31 | 0.323 | 1.000 | 0.488 | 31.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_count | 31 | 0.312 | 0.968 | 0.472 | 30.00 | 0.500 | 1.00/2 |
| temporal_nms_count | 31 | 0.312 | 0.968 | 0.472 | 30.00 | 1.000 | 2.00/2 |
| temporal_nms_ensemble | 31 | 0.312 | 0.968 | 0.472 | 30.00 | 1.000 | 2.00/2 |
| temporal_nms_naive | 31 | 0.312 | 0.968 | 0.472 | 30.00 | 1.000 | 2.00/2 |
| uniform_expansion | 31 | 0.312 | 0.968 | 0.472 | 30.00 | 0.500 | 1.00/2 |
| random | 31 | 0.301 ± 0.015 | 0.932 ± 0.045 | 0.455 ± 0.022 | 28.90 | 1.000 | 2.00/2 |
| uniform_time | 31 | 0.292 | 0.903 | 0.441 | 28.00 | 1.000 | 2.00/2 |

### Budget Ratio 0.50

Best clip recall: 0.531 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, proxy_then_expansion_naive, top_count, top_kinematic, top_naive.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 51 | 0.531 | 1.000 | 0.694 | 51.00 | 1.000 | 2.00/2 |
| ensemble_count_naive | 51 | 0.531 | 1.000 | 0.694 | 51.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_ensemble | 51 | 0.531 | 1.000 | 0.694 | 51.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_naive | 51 | 0.531 | 1.000 | 0.694 | 51.00 | 1.000 | 2.00/2 |
| top_count | 51 | 0.531 | 1.000 | 0.694 | 51.00 | 1.000 | 2.00/2 |
| top_kinematic | 51 | 0.531 | 1.000 | 0.694 | 51.00 | 1.000 | 2.00/2 |
| top_naive | 51 | 0.531 | 1.000 | 0.694 | 51.00 | 1.000 | 2.00/2 |
| proxy_then_expansion_count | 51 | 0.521 | 0.980 | 0.680 | 50.00 | 1.000 | 2.00/2 |
| temporal_nms_count | 51 | 0.521 | 0.980 | 0.680 | 50.00 | 1.000 | 2.00/2 |
| temporal_nms_ensemble | 51 | 0.521 | 0.980 | 0.680 | 50.00 | 1.000 | 2.00/2 |
| temporal_nms_naive | 51 | 0.521 | 0.980 | 0.680 | 50.00 | 1.000 | 2.00/2 |
| uniform_expansion | 51 | 0.521 | 0.980 | 0.680 | 50.00 | 0.500 | 1.00/2 |
| random | 51 | 0.500 ± 0.014 | 0.941 ± 0.025 | 0.653 ± 0.018 | 48.00 | 1.000 | 2.00/2 |
| uniform_time | 51 | 0.500 | 0.941 | 0.653 | 48.00 | 1.000 | 2.00/2 |


## broad Label: Event-Level Results

### Budget Ratio 0.05

Best event recall: 1.000 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, proxy_then_expansion_naive, random, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, top_naive, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 6 | 1.000 | 2.00/2 | 0.062 | 1.000 |
| ensemble_count_naive | 6 | 1.000 | 2.00/2 | 0.062 | 1.000 |
| proxy_then_expansion_ensemble | 6 | 1.000 | 2.00/2 | 0.062 | 1.000 |
| proxy_then_expansion_naive | 6 | 1.000 | 2.00/2 | 0.062 | 1.000 |
| temporal_nms_ensemble | 6 | 1.000 | 2.00/2 | 0.062 | 1.000 |
| temporal_nms_naive | 6 | 1.000 | 2.00/2 | 0.062 | 1.000 |
| top_kinematic | 6 | 1.000 | 2.00/2 | 0.062 | 1.000 |
| top_naive | 6 | 1.000 | 2.00/2 | 0.062 | 1.000 |
| random | 6 | 1.000 ± 0.000 | 2.00/2 | 0.060 | 0.958 |
| uniform_time | 6 | 1.000 | 2.00/2 | 0.042 | 0.667 |
| temporal_nms_count | 6 | 0.500 | 1.00/2 | 0.062 | 1.000 |
| top_count | 6 | 0.500 | 1.00/2 | 0.062 | 1.000 |
| proxy_then_expansion_count | 6 | 0.500 | 1.00/2 | 0.052 | 0.833 |
| uniform_expansion | 6 | 0.500 | 1.00/2 | 0.052 | 0.833 |

### Budget Ratio 0.10

Best event recall: 1.000 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, proxy_then_expansion_naive, random, temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, top_naive, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 11 | 1.000 | 2.00/2 | 0.115 | 1.000 |
| ensemble_count_naive | 11 | 1.000 | 2.00/2 | 0.115 | 1.000 |
| proxy_then_expansion_ensemble | 11 | 1.000 | 2.00/2 | 0.115 | 1.000 |
| proxy_then_expansion_naive | 11 | 1.000 | 2.00/2 | 0.115 | 1.000 |
| temporal_nms_count | 11 | 1.000 | 2.00/2 | 0.115 | 1.000 |
| temporal_nms_ensemble | 11 | 1.000 | 2.00/2 | 0.115 | 1.000 |
| temporal_nms_naive | 11 | 1.000 | 2.00/2 | 0.115 | 1.000 |
| top_kinematic | 11 | 1.000 | 2.00/2 | 0.115 | 1.000 |
| top_naive | 11 | 1.000 | 2.00/2 | 0.115 | 1.000 |
| random | 11 | 1.000 ± 0.000 | 2.00/2 | 0.108 | 0.945 |
| uniform_time | 11 | 1.000 | 2.00/2 | 0.094 | 0.818 |
| top_count | 11 | 0.500 | 1.00/2 | 0.115 | 1.000 |
| proxy_then_expansion_count | 11 | 0.500 | 1.00/2 | 0.104 | 0.909 |
| uniform_expansion | 11 | 0.500 | 1.00/2 | 0.104 | 0.909 |

### Budget Ratio 0.15

Best event recall: 1.000 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, proxy_then_expansion_naive, random, temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, top_naive, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 16 | 1.000 | 2.00/2 | 0.167 | 1.000 |
| ensemble_count_naive | 16 | 1.000 | 2.00/2 | 0.167 | 1.000 |
| proxy_then_expansion_ensemble | 16 | 1.000 | 2.00/2 | 0.167 | 1.000 |
| proxy_then_expansion_naive | 16 | 1.000 | 2.00/2 | 0.167 | 1.000 |
| temporal_nms_count | 16 | 1.000 | 2.00/2 | 0.167 | 1.000 |
| temporal_nms_ensemble | 16 | 1.000 | 2.00/2 | 0.167 | 1.000 |
| top_kinematic | 16 | 1.000 | 2.00/2 | 0.167 | 1.000 |
| top_naive | 16 | 1.000 | 2.00/2 | 0.167 | 1.000 |
| temporal_nms_naive | 16 | 1.000 | 2.00/2 | 0.156 | 0.938 |
| random | 16 | 1.000 ± 0.000 | 2.00/2 | 0.155 | 0.931 |
| uniform_time | 16 | 1.000 | 2.00/2 | 0.146 | 0.875 |
| top_count | 16 | 0.500 | 1.00/2 | 0.167 | 1.000 |
| proxy_then_expansion_count | 16 | 0.500 | 1.00/2 | 0.156 | 0.938 |
| uniform_expansion | 16 | 0.500 | 1.00/2 | 0.156 | 0.938 |

### Budget Ratio 0.20

Best event recall: 1.000 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, proxy_then_expansion_naive, random, temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, top_naive, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 21 | 1.000 | 2.00/2 | 0.219 | 1.000 |
| ensemble_count_naive | 21 | 1.000 | 2.00/2 | 0.219 | 1.000 |
| proxy_then_expansion_ensemble | 21 | 1.000 | 2.00/2 | 0.219 | 1.000 |
| proxy_then_expansion_naive | 21 | 1.000 | 2.00/2 | 0.219 | 1.000 |
| top_kinematic | 21 | 1.000 | 2.00/2 | 0.219 | 1.000 |
| top_naive | 21 | 1.000 | 2.00/2 | 0.219 | 1.000 |
| random | 21 | 1.000 ± 0.000 | 2.00/2 | 0.210 | 0.960 |
| temporal_nms_count | 21 | 1.000 | 2.00/2 | 0.208 | 0.952 |
| temporal_nms_ensemble | 21 | 1.000 | 2.00/2 | 0.208 | 0.952 |
| temporal_nms_naive | 21 | 1.000 | 2.00/2 | 0.208 | 0.952 |
| uniform_time | 21 | 1.000 | 2.00/2 | 0.198 | 0.905 |
| top_count | 21 | 0.500 | 1.00/2 | 0.219 | 1.000 |
| proxy_then_expansion_count | 21 | 0.500 | 1.00/2 | 0.208 | 0.952 |
| uniform_expansion | 21 | 0.500 | 1.00/2 | 0.208 | 0.952 |

### Budget Ratio 0.30

Best event recall: 1.000 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, proxy_then_expansion_naive, random, temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, top_naive, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 31 | 1.000 | 2.00/2 | 0.323 | 1.000 |
| ensemble_count_naive | 31 | 1.000 | 2.00/2 | 0.323 | 1.000 |
| proxy_then_expansion_ensemble | 31 | 1.000 | 2.00/2 | 0.323 | 1.000 |
| proxy_then_expansion_naive | 31 | 1.000 | 2.00/2 | 0.323 | 1.000 |
| top_kinematic | 31 | 1.000 | 2.00/2 | 0.323 | 1.000 |
| top_naive | 31 | 1.000 | 2.00/2 | 0.323 | 1.000 |
| temporal_nms_count | 31 | 1.000 | 2.00/2 | 0.312 | 0.968 |
| temporal_nms_ensemble | 31 | 1.000 | 2.00/2 | 0.312 | 0.968 |
| temporal_nms_naive | 31 | 1.000 | 2.00/2 | 0.312 | 0.968 |
| random | 31 | 1.000 ± 0.000 | 2.00/2 | 0.301 | 0.932 |
| uniform_time | 31 | 1.000 | 2.00/2 | 0.292 | 0.903 |
| top_count | 31 | 0.500 | 1.00/2 | 0.323 | 1.000 |
| proxy_then_expansion_count | 31 | 0.500 | 1.00/2 | 0.312 | 0.968 |
| uniform_expansion | 31 | 0.500 | 1.00/2 | 0.312 | 0.968 |

### Budget Ratio 0.50

Best event recall: 1.000 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_count, proxy_then_expansion_ensemble, proxy_then_expansion_naive, random, temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_count, top_kinematic, top_naive, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 51 | 1.000 | 2.00/2 | 0.531 | 1.000 |
| ensemble_count_naive | 51 | 1.000 | 2.00/2 | 0.531 | 1.000 |
| proxy_then_expansion_ensemble | 51 | 1.000 | 2.00/2 | 0.531 | 1.000 |
| proxy_then_expansion_naive | 51 | 1.000 | 2.00/2 | 0.531 | 1.000 |
| top_count | 51 | 1.000 | 2.00/2 | 0.531 | 1.000 |
| top_kinematic | 51 | 1.000 | 2.00/2 | 0.531 | 1.000 |
| top_naive | 51 | 1.000 | 2.00/2 | 0.531 | 1.000 |
| proxy_then_expansion_count | 51 | 1.000 | 2.00/2 | 0.521 | 0.980 |
| temporal_nms_count | 51 | 1.000 | 2.00/2 | 0.521 | 0.980 |
| temporal_nms_ensemble | 51 | 1.000 | 2.00/2 | 0.521 | 0.980 |
| temporal_nms_naive | 51 | 1.000 | 2.00/2 | 0.521 | 0.980 |
| random | 51 | 1.000 ± 0.000 | 2.00/2 | 0.500 | 0.941 |
| uniform_time | 51 | 1.000 | 2.00/2 | 0.500 | 0.941 |
| uniform_expansion | 51 | 0.500 | 1.00/2 | 0.521 | 0.980 |


## ego_relevant Label: Clip-Level Results

### Budget Ratio 0.05

Best clip recall: 0.073 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, temporal_nms_count, temporal_nms_ensemble, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 6 | 0.073 | 1.000 | 0.136 | 6.00 | 0.500 | 2.00/4 |
| ensemble_count_naive | 6 | 0.073 | 1.000 | 0.136 | 6.00 | 0.500 | 2.00/4 |
| proxy_then_expansion_ensemble | 6 | 0.073 | 1.000 | 0.136 | 6.00 | 0.500 | 2.00/4 |
| temporal_nms_count | 6 | 0.073 | 1.000 | 0.136 | 6.00 | 0.250 | 1.00/4 |
| temporal_nms_ensemble | 6 | 0.073 | 1.000 | 0.136 | 6.00 | 0.500 | 2.00/4 |
| top_count | 6 | 0.073 | 1.000 | 0.136 | 6.00 | 0.250 | 1.00/4 |
| random | 6 | 0.063 ± 0.011 | 0.858 ± 0.156 | 0.117 ± 0.021 | 5.15 | 0.662 | 2.65/4 |
| proxy_then_expansion_count | 6 | 0.061 | 0.833 | 0.114 | 5.00 | 0.250 | 1.00/4 |
| proxy_then_expansion_naive | 6 | 0.061 | 0.833 | 0.114 | 5.00 | 0.500 | 2.00/4 |
| temporal_nms_naive | 6 | 0.061 | 0.833 | 0.114 | 5.00 | 0.750 | 3.00/4 |
| top_kinematic | 6 | 0.061 | 0.833 | 0.114 | 5.00 | 0.750 | 3.00/4 |
| top_naive | 6 | 0.061 | 0.833 | 0.114 | 5.00 | 0.750 | 3.00/4 |
| uniform_expansion | 6 | 0.061 | 0.833 | 0.114 | 5.00 | 0.250 | 1.00/4 |
| uniform_time | 6 | 0.049 | 0.667 | 0.091 | 4.00 | 0.750 | 3.00/4 |

### Budget Ratio 0.10

Best clip recall: 0.134 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, temporal_nms_count, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 11 | 0.134 | 1.000 | 0.237 | 11.00 | 0.500 | 2.00/4 |
| ensemble_count_naive | 11 | 0.134 | 1.000 | 0.237 | 11.00 | 0.500 | 2.00/4 |
| proxy_then_expansion_ensemble | 11 | 0.134 | 1.000 | 0.237 | 11.00 | 0.500 | 2.00/4 |
| temporal_nms_count | 11 | 0.134 | 1.000 | 0.237 | 11.00 | 0.500 | 2.00/4 |
| top_count | 11 | 0.134 | 1.000 | 0.237 | 11.00 | 0.250 | 1.00/4 |
| proxy_then_expansion_count | 11 | 0.122 | 0.909 | 0.215 | 10.00 | 0.250 | 1.00/4 |
| proxy_then_expansion_naive | 11 | 0.122 | 0.909 | 0.215 | 10.00 | 0.750 | 3.00/4 |
| temporal_nms_ensemble | 11 | 0.122 | 0.909 | 0.215 | 10.00 | 0.750 | 3.00/4 |
| uniform_expansion | 11 | 0.122 | 0.909 | 0.215 | 10.00 | 0.250 | 1.00/4 |
| temporal_nms_naive | 11 | 0.110 | 0.818 | 0.194 | 9.00 | 1.000 | 4.00/4 |
| top_naive | 11 | 0.110 | 0.818 | 0.194 | 9.00 | 0.750 | 3.00/4 |
| uniform_time | 11 | 0.110 | 0.818 | 0.194 | 9.00 | 0.750 | 3.00/4 |
| random | 11 | 0.107 ± 0.013 | 0.795 ± 0.097 | 0.188 ± 0.023 | 8.75 | 0.762 | 3.05/4 |
| top_kinematic | 11 | 0.085 | 0.636 | 0.151 | 7.00 | 0.750 | 3.00/4 |

### Budget Ratio 0.15

Best clip recall: 0.195 by ensemble_count_naive, proxy_then_expansion_ensemble, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_count_naive | 16 | 0.195 | 1.000 | 0.327 | 16.00 | 0.500 | 2.00/4 |
| proxy_then_expansion_ensemble | 16 | 0.195 | 1.000 | 0.327 | 16.00 | 0.500 | 2.00/4 |
| top_count | 16 | 0.195 | 1.000 | 0.327 | 16.00 | 0.250 | 1.00/4 |
| ensemble_all_proxy | 16 | 0.183 | 0.938 | 0.306 | 15.00 | 0.500 | 2.00/4 |
| proxy_then_expansion_count | 16 | 0.183 | 0.938 | 0.306 | 15.00 | 0.250 | 1.00/4 |
| proxy_then_expansion_naive | 16 | 0.183 | 0.938 | 0.306 | 15.00 | 0.750 | 3.00/4 |
| temporal_nms_count | 16 | 0.183 | 0.938 | 0.306 | 15.00 | 1.000 | 4.00/4 |
| uniform_expansion | 16 | 0.183 | 0.938 | 0.306 | 15.00 | 0.250 | 1.00/4 |
| top_naive | 16 | 0.171 | 0.875 | 0.286 | 14.00 | 0.750 | 3.00/4 |
| temporal_nms_ensemble | 16 | 0.159 | 0.812 | 0.265 | 13.00 | 1.000 | 4.00/4 |
| temporal_nms_naive | 16 | 0.159 | 0.812 | 0.265 | 13.00 | 1.000 | 4.00/4 |
| random | 16 | 0.154 ± 0.021 | 0.791 ± 0.106 | 0.258 ± 0.035 | 12.65 | 0.950 | 3.80/4 |
| uniform_time | 16 | 0.146 | 0.750 | 0.245 | 12.00 | 1.000 | 4.00/4 |
| top_kinematic | 16 | 0.122 | 0.625 | 0.204 | 10.00 | 1.000 | 4.00/4 |

### Budget Ratio 0.20

Best clip recall: 0.256 by ensemble_count_naive, proxy_then_expansion_ensemble, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_count_naive | 21 | 0.256 | 1.000 | 0.408 | 21.00 | 0.500 | 2.00/4 |
| proxy_then_expansion_ensemble | 21 | 0.256 | 1.000 | 0.408 | 21.00 | 0.500 | 2.00/4 |
| top_count | 21 | 0.256 | 1.000 | 0.408 | 21.00 | 0.250 | 1.00/4 |
| ensemble_all_proxy | 21 | 0.244 | 0.952 | 0.388 | 20.00 | 0.500 | 2.00/4 |
| proxy_then_expansion_count | 21 | 0.244 | 0.952 | 0.388 | 20.00 | 0.250 | 1.00/4 |
| uniform_expansion | 21 | 0.244 | 0.952 | 0.388 | 20.00 | 0.250 | 1.00/4 |
| proxy_then_expansion_naive | 21 | 0.232 | 0.905 | 0.369 | 19.00 | 0.750 | 3.00/4 |
| top_naive | 21 | 0.232 | 0.905 | 0.369 | 19.00 | 0.750 | 3.00/4 |
| temporal_nms_count | 21 | 0.220 | 0.857 | 0.350 | 18.00 | 1.000 | 4.00/4 |
| temporal_nms_ensemble | 21 | 0.207 | 0.810 | 0.330 | 17.00 | 1.000 | 4.00/4 |
| temporal_nms_naive | 21 | 0.207 | 0.810 | 0.330 | 17.00 | 1.000 | 4.00/4 |
| uniform_time | 21 | 0.207 | 0.810 | 0.330 | 17.00 | 1.000 | 4.00/4 |
| random | 21 | 0.205 ± 0.022 | 0.802 ± 0.086 | 0.327 ± 0.035 | 16.85 | 0.950 | 3.80/4 |
| top_kinematic | 21 | 0.183 | 0.714 | 0.291 | 15.00 | 1.000 | 4.00/4 |

### Budget Ratio 0.30

Best clip recall: 0.378 by ensemble_count_naive, proxy_then_expansion_ensemble, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_count_naive | 31 | 0.378 | 1.000 | 0.549 | 31.00 | 0.500 | 2.00/4 |
| proxy_then_expansion_ensemble | 31 | 0.378 | 1.000 | 0.549 | 31.00 | 0.500 | 2.00/4 |
| top_count | 31 | 0.378 | 1.000 | 0.549 | 31.00 | 0.250 | 1.00/4 |
| ensemble_all_proxy | 31 | 0.366 | 0.968 | 0.531 | 30.00 | 0.500 | 2.00/4 |
| proxy_then_expansion_count | 31 | 0.366 | 0.968 | 0.531 | 30.00 | 0.250 | 1.00/4 |
| uniform_expansion | 31 | 0.366 | 0.968 | 0.531 | 30.00 | 0.250 | 1.00/4 |
| proxy_then_expansion_naive | 31 | 0.354 | 0.935 | 0.513 | 29.00 | 0.750 | 3.00/4 |
| temporal_nms_count | 31 | 0.341 | 0.903 | 0.496 | 28.00 | 1.000 | 4.00/4 |
| top_naive | 31 | 0.341 | 0.903 | 0.496 | 28.00 | 1.000 | 4.00/4 |
| temporal_nms_ensemble | 31 | 0.329 | 0.871 | 0.478 | 27.00 | 1.000 | 4.00/4 |
| temporal_nms_naive | 31 | 0.317 | 0.839 | 0.460 | 26.00 | 1.000 | 4.00/4 |
| uniform_time | 31 | 0.305 | 0.806 | 0.442 | 25.00 | 1.000 | 4.00/4 |
| random | 31 | 0.298 ± 0.021 | 0.789 ± 0.057 | 0.433 ± 0.031 | 24.45 | 0.975 | 3.90/4 |
| top_kinematic | 31 | 0.293 | 0.774 | 0.425 | 24.00 | 1.000 | 4.00/4 |

### Budget Ratio 0.50

Best clip recall: 0.622 by proxy_then_expansion_ensemble.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| proxy_then_expansion_ensemble | 51 | 0.622 | 1.000 | 0.767 | 51.00 | 0.500 | 2.00/4 |
| ensemble_count_naive | 51 | 0.610 | 0.980 | 0.752 | 50.00 | 0.500 | 2.00/4 |
| top_count | 51 | 0.610 | 0.980 | 0.752 | 50.00 | 0.500 | 2.00/4 |
| uniform_expansion | 51 | 0.610 | 0.980 | 0.752 | 50.00 | 0.250 | 1.00/4 |
| proxy_then_expansion_count | 51 | 0.585 | 0.941 | 0.722 | 48.00 | 0.750 | 3.00/4 |
| temporal_nms_count | 51 | 0.585 | 0.941 | 0.722 | 48.00 | 1.000 | 4.00/4 |
| ensemble_all_proxy | 51 | 0.573 | 0.922 | 0.707 | 47.00 | 1.000 | 4.00/4 |
| proxy_then_expansion_naive | 51 | 0.573 | 0.922 | 0.707 | 47.00 | 1.000 | 4.00/4 |
| temporal_nms_ensemble | 51 | 0.561 | 0.902 | 0.692 | 46.00 | 1.000 | 4.00/4 |
| top_naive | 51 | 0.549 | 0.882 | 0.677 | 45.00 | 1.000 | 4.00/4 |
| temporal_nms_naive | 51 | 0.537 | 0.863 | 0.662 | 44.00 | 1.000 | 4.00/4 |
| top_kinematic | 51 | 0.524 | 0.843 | 0.647 | 43.00 | 1.000 | 4.00/4 |
| uniform_time | 51 | 0.500 | 0.804 | 0.617 | 41.00 | 1.000 | 4.00/4 |
| random | 51 | 0.495 ± 0.024 | 0.796 ± 0.039 | 0.611 ± 0.030 | 40.60 | 1.000 | 4.00/4 |


## ego_relevant Label: Event-Level Results

### Budget Ratio 0.05

Best event recall: 0.750 by temporal_nms_naive, top_kinematic, top_naive, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_naive | 6 | 0.750 | 3.00/4 | 0.061 | 0.833 |
| top_kinematic | 6 | 0.750 | 3.00/4 | 0.061 | 0.833 |
| top_naive | 6 | 0.750 | 3.00/4 | 0.061 | 0.833 |
| uniform_time | 6 | 0.750 | 3.00/4 | 0.049 | 0.667 |
| random | 6 | 0.662 ± 0.147 | 2.65/4 | 0.063 | 0.858 |
| ensemble_all_proxy | 6 | 0.500 | 2.00/4 | 0.073 | 1.000 |
| ensemble_count_naive | 6 | 0.500 | 2.00/4 | 0.073 | 1.000 |
| proxy_then_expansion_ensemble | 6 | 0.500 | 2.00/4 | 0.073 | 1.000 |
| temporal_nms_ensemble | 6 | 0.500 | 2.00/4 | 0.073 | 1.000 |
| proxy_then_expansion_naive | 6 | 0.500 | 2.00/4 | 0.061 | 0.833 |
| temporal_nms_count | 6 | 0.250 | 1.00/4 | 0.073 | 1.000 |
| top_count | 6 | 0.250 | 1.00/4 | 0.073 | 1.000 |
| proxy_then_expansion_count | 6 | 0.250 | 1.00/4 | 0.061 | 0.833 |
| uniform_expansion | 6 | 0.250 | 1.00/4 | 0.061 | 0.833 |

### Budget Ratio 0.10

Best event recall: 1.000 by temporal_nms_naive.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_naive | 11 | 1.000 | 4.00/4 | 0.110 | 0.818 |
| random | 11 | 0.762 ± 0.099 | 3.05/4 | 0.107 | 0.795 |
| proxy_then_expansion_naive | 11 | 0.750 | 3.00/4 | 0.122 | 0.909 |
| temporal_nms_ensemble | 11 | 0.750 | 3.00/4 | 0.122 | 0.909 |
| top_naive | 11 | 0.750 | 3.00/4 | 0.110 | 0.818 |
| uniform_time | 11 | 0.750 | 3.00/4 | 0.110 | 0.818 |
| top_kinematic | 11 | 0.750 | 3.00/4 | 0.085 | 0.636 |
| ensemble_all_proxy | 11 | 0.500 | 2.00/4 | 0.134 | 1.000 |
| ensemble_count_naive | 11 | 0.500 | 2.00/4 | 0.134 | 1.000 |
| proxy_then_expansion_ensemble | 11 | 0.500 | 2.00/4 | 0.134 | 1.000 |
| temporal_nms_count | 11 | 0.500 | 2.00/4 | 0.134 | 1.000 |
| top_count | 11 | 0.250 | 1.00/4 | 0.134 | 1.000 |
| proxy_then_expansion_count | 11 | 0.250 | 1.00/4 | 0.122 | 0.909 |
| uniform_expansion | 11 | 0.250 | 1.00/4 | 0.122 | 0.909 |

### Budget Ratio 0.15

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 16 | 1.000 | 4.00/4 | 0.183 | 0.938 |
| temporal_nms_ensemble | 16 | 1.000 | 4.00/4 | 0.159 | 0.812 |
| temporal_nms_naive | 16 | 1.000 | 4.00/4 | 0.159 | 0.812 |
| uniform_time | 16 | 1.000 | 4.00/4 | 0.146 | 0.750 |
| top_kinematic | 16 | 1.000 | 4.00/4 | 0.122 | 0.625 |
| random | 16 | 0.950 ± 0.103 | 3.80/4 | 0.154 | 0.791 |
| proxy_then_expansion_naive | 16 | 0.750 | 3.00/4 | 0.183 | 0.938 |
| top_naive | 16 | 0.750 | 3.00/4 | 0.171 | 0.875 |
| ensemble_count_naive | 16 | 0.500 | 2.00/4 | 0.195 | 1.000 |
| proxy_then_expansion_ensemble | 16 | 0.500 | 2.00/4 | 0.195 | 1.000 |
| ensemble_all_proxy | 16 | 0.500 | 2.00/4 | 0.183 | 0.938 |
| top_count | 16 | 0.250 | 1.00/4 | 0.195 | 1.000 |
| proxy_then_expansion_count | 16 | 0.250 | 1.00/4 | 0.183 | 0.938 |
| uniform_expansion | 16 | 0.250 | 1.00/4 | 0.183 | 0.938 |

### Budget Ratio 0.20

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 21 | 1.000 | 4.00/4 | 0.220 | 0.857 |
| temporal_nms_ensemble | 21 | 1.000 | 4.00/4 | 0.207 | 0.810 |
| temporal_nms_naive | 21 | 1.000 | 4.00/4 | 0.207 | 0.810 |
| uniform_time | 21 | 1.000 | 4.00/4 | 0.207 | 0.810 |
| top_kinematic | 21 | 1.000 | 4.00/4 | 0.183 | 0.714 |
| random | 21 | 0.950 ± 0.103 | 3.80/4 | 0.205 | 0.802 |
| proxy_then_expansion_naive | 21 | 0.750 | 3.00/4 | 0.232 | 0.905 |
| top_naive | 21 | 0.750 | 3.00/4 | 0.232 | 0.905 |
| ensemble_count_naive | 21 | 0.500 | 2.00/4 | 0.256 | 1.000 |
| proxy_then_expansion_ensemble | 21 | 0.500 | 2.00/4 | 0.256 | 1.000 |
| ensemble_all_proxy | 21 | 0.500 | 2.00/4 | 0.244 | 0.952 |
| top_count | 21 | 0.250 | 1.00/4 | 0.256 | 1.000 |
| proxy_then_expansion_count | 21 | 0.250 | 1.00/4 | 0.244 | 0.952 |
| uniform_expansion | 21 | 0.250 | 1.00/4 | 0.244 | 0.952 |

### Budget Ratio 0.30

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, top_naive, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 31 | 1.000 | 4.00/4 | 0.341 | 0.903 |
| top_naive | 31 | 1.000 | 4.00/4 | 0.341 | 0.903 |
| temporal_nms_ensemble | 31 | 1.000 | 4.00/4 | 0.329 | 0.871 |
| temporal_nms_naive | 31 | 1.000 | 4.00/4 | 0.317 | 0.839 |
| uniform_time | 31 | 1.000 | 4.00/4 | 0.305 | 0.806 |
| top_kinematic | 31 | 1.000 | 4.00/4 | 0.293 | 0.774 |
| random | 31 | 0.975 ± 0.077 | 3.90/4 | 0.298 | 0.789 |
| proxy_then_expansion_naive | 31 | 0.750 | 3.00/4 | 0.354 | 0.935 |
| ensemble_count_naive | 31 | 0.500 | 2.00/4 | 0.378 | 1.000 |
| proxy_then_expansion_ensemble | 31 | 0.500 | 2.00/4 | 0.378 | 1.000 |
| ensemble_all_proxy | 31 | 0.500 | 2.00/4 | 0.366 | 0.968 |
| top_count | 31 | 0.250 | 1.00/4 | 0.378 | 1.000 |
| proxy_then_expansion_count | 31 | 0.250 | 1.00/4 | 0.366 | 0.968 |
| uniform_expansion | 31 | 0.250 | 1.00/4 | 0.366 | 0.968 |

### Budget Ratio 0.50

Best event recall: 1.000 by ensemble_all_proxy, proxy_then_expansion_naive, random, temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, top_naive, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 51 | 1.000 | 4.00/4 | 0.585 | 0.941 |
| ensemble_all_proxy | 51 | 1.000 | 4.00/4 | 0.573 | 0.922 |
| proxy_then_expansion_naive | 51 | 1.000 | 4.00/4 | 0.573 | 0.922 |
| temporal_nms_ensemble | 51 | 1.000 | 4.00/4 | 0.561 | 0.902 |
| top_naive | 51 | 1.000 | 4.00/4 | 0.549 | 0.882 |
| temporal_nms_naive | 51 | 1.000 | 4.00/4 | 0.537 | 0.863 |
| top_kinematic | 51 | 1.000 | 4.00/4 | 0.524 | 0.843 |
| uniform_time | 51 | 1.000 | 4.00/4 | 0.500 | 0.804 |
| random | 51 | 1.000 ± 0.000 | 4.00/4 | 0.495 | 0.796 |
| proxy_then_expansion_count | 51 | 0.750 | 3.00/4 | 0.585 | 0.941 |
| proxy_then_expansion_ensemble | 51 | 0.500 | 2.00/4 | 0.622 | 1.000 |
| ensemble_count_naive | 51 | 0.500 | 2.00/4 | 0.610 | 0.980 |
| top_count | 51 | 0.500 | 2.00/4 | 0.610 | 0.980 |
| uniform_expansion | 51 | 0.250 | 1.00/4 | 0.610 | 0.980 |


## strict Label: Clip-Level Results

### Budget Ratio 0.05

Best clip recall: 0.088 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, temporal_nms_count, temporal_nms_ensemble, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_ensemble | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.286 | 2.00/7 |
| temporal_nms_count | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.286 | 2.00/7 |
| temporal_nms_ensemble | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.429 | 3.00/7 |
| top_count | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_count | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_naive | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.286 | 2.00/7 |
| temporal_nms_naive | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.429 | 3.00/7 |
| top_naive | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.429 | 3.00/7 |
| uniform_expansion | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.143 | 1.00/7 |
| random | 6 | 0.061 ± 0.016 | 0.692 ± 0.182 | 0.112 ± 0.029 | 4.15 | 0.500 | 3.50/7 |
| uniform_time | 6 | 0.059 | 0.667 | 0.108 | 4.00 | 0.571 | 4.00/7 |
| top_kinematic | 6 | 0.044 | 0.500 | 0.081 | 3.00 | 0.714 | 5.00/7 |

### Budget Ratio 0.10

Best clip recall: 0.162 by ensemble_all_proxy, ensemble_count_naive, temporal_nms_count, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.429 | 3.00/7 |
| top_count | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_count | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_ensemble | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_naive | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.429 | 3.00/7 |
| temporal_nms_ensemble | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.571 | 4.00/7 |
| uniform_expansion | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.143 | 1.00/7 |
| temporal_nms_naive | 11 | 0.132 | 0.818 | 0.228 | 9.00 | 0.714 | 5.00/7 |
| top_naive | 11 | 0.132 | 0.818 | 0.228 | 9.00 | 0.429 | 3.00/7 |
| uniform_time | 11 | 0.118 | 0.727 | 0.203 | 8.00 | 0.714 | 5.00/7 |
| random | 11 | 0.109 ± 0.018 | 0.673 ± 0.112 | 0.187 ± 0.031 | 7.40 | 0.629 | 4.40/7 |
| top_kinematic | 11 | 0.074 | 0.455 | 0.127 | 5.00 | 0.857 | 6.00/7 |

### Budget Ratio 0.15

Best clip recall: 0.235 by top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 16 | 0.235 | 1.000 | 0.381 | 16.00 | 0.143 | 1.00/7 |
| ensemble_all_proxy | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.429 | 3.00/7 |
| proxy_then_expansion_count | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_ensemble | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_naive | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.857 | 6.00/7 |
| uniform_expansion | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.143 | 1.00/7 |
| temporal_nms_ensemble | 16 | 0.176 | 0.750 | 0.286 | 12.00 | 1.000 | 7.00/7 |
| temporal_nms_naive | 16 | 0.176 | 0.750 | 0.286 | 12.00 | 1.000 | 7.00/7 |
| top_naive | 16 | 0.176 | 0.750 | 0.286 | 12.00 | 0.571 | 4.00/7 |
| uniform_time | 16 | 0.162 | 0.688 | 0.262 | 11.00 | 1.000 | 7.00/7 |
| random | 16 | 0.153 ± 0.031 | 0.650 ± 0.132 | 0.248 ± 0.050 | 10.40 | 0.836 | 5.85/7 |
| top_kinematic | 16 | 0.118 | 0.500 | 0.190 | 8.00 | 1.000 | 7.00/7 |

### Budget Ratio 0.20

Best clip recall: 0.309 by top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 21 | 0.309 | 1.000 | 0.472 | 21.00 | 0.286 | 2.00/7 |
| ensemble_all_proxy | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.429 | 3.00/7 |
| proxy_then_expansion_count | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_ensemble | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.429 | 3.00/7 |
| uniform_expansion | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_naive | 21 | 0.279 | 0.905 | 0.427 | 19.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 21 | 0.250 | 0.810 | 0.382 | 17.00 | 1.000 | 7.00/7 |
| top_naive | 21 | 0.250 | 0.810 | 0.382 | 17.00 | 0.571 | 4.00/7 |
| temporal_nms_ensemble | 21 | 0.235 | 0.762 | 0.360 | 16.00 | 1.000 | 7.00/7 |
| temporal_nms_naive | 21 | 0.221 | 0.714 | 0.337 | 15.00 | 1.000 | 7.00/7 |
| uniform_time | 21 | 0.221 | 0.714 | 0.337 | 15.00 | 1.000 | 7.00/7 |
| random | 21 | 0.201 ± 0.036 | 0.650 ± 0.116 | 0.307 ± 0.055 | 13.65 | 0.871 | 6.10/7 |
| top_kinematic | 21 | 0.191 | 0.619 | 0.292 | 13.00 | 1.000 | 7.00/7 |

### Budget Ratio 0.30

Best clip recall: 0.456 by top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 31 | 0.456 | 1.000 | 0.626 | 31.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_count | 31 | 0.441 | 0.968 | 0.606 | 30.00 | 0.286 | 2.00/7 |
| ensemble_count_naive | 31 | 0.426 | 0.935 | 0.586 | 29.00 | 0.429 | 3.00/7 |
| proxy_then_expansion_ensemble | 31 | 0.426 | 0.935 | 0.586 | 29.00 | 0.429 | 3.00/7 |
| ensemble_all_proxy | 31 | 0.412 | 0.903 | 0.566 | 28.00 | 0.429 | 3.00/7 |
| uniform_expansion | 31 | 0.412 | 0.903 | 0.566 | 28.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_naive | 31 | 0.397 | 0.871 | 0.545 | 27.00 | 0.571 | 4.00/7 |
| temporal_nms_count | 31 | 0.397 | 0.871 | 0.545 | 27.00 | 1.000 | 7.00/7 |
| top_naive | 31 | 0.382 | 0.839 | 0.525 | 26.00 | 0.714 | 5.00/7 |
| temporal_nms_ensemble | 31 | 0.368 | 0.806 | 0.505 | 25.00 | 1.000 | 7.00/7 |
| temporal_nms_naive | 31 | 0.338 | 0.742 | 0.465 | 23.00 | 1.000 | 7.00/7 |
| top_kinematic | 31 | 0.309 | 0.677 | 0.424 | 21.00 | 1.000 | 7.00/7 |
| uniform_time | 31 | 0.309 | 0.677 | 0.424 | 21.00 | 1.000 | 7.00/7 |
| random | 31 | 0.293 ± 0.031 | 0.644 ± 0.067 | 0.403 ± 0.042 | 19.95 | 0.936 | 6.55/7 |

### Budget Ratio 0.50

Best clip recall: 0.706 by proxy_then_expansion_count, proxy_then_expansion_ensemble, uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| proxy_then_expansion_count | 51 | 0.706 | 0.941 | 0.807 | 48.00 | 0.571 | 4.00/7 |
| proxy_then_expansion_ensemble | 51 | 0.706 | 0.941 | 0.807 | 48.00 | 0.429 | 3.00/7 |
| uniform_expansion | 51 | 0.706 | 0.941 | 0.807 | 48.00 | 0.286 | 2.00/7 |
| ensemble_count_naive | 51 | 0.691 | 0.922 | 0.790 | 47.00 | 0.429 | 3.00/7 |
| top_count | 51 | 0.691 | 0.922 | 0.790 | 47.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 51 | 0.676 | 0.902 | 0.773 | 46.00 | 1.000 | 7.00/7 |
| ensemble_all_proxy | 51 | 0.662 | 0.882 | 0.756 | 45.00 | 0.714 | 5.00/7 |
| proxy_then_expansion_naive | 51 | 0.662 | 0.882 | 0.756 | 45.00 | 0.714 | 5.00/7 |
| temporal_nms_ensemble | 51 | 0.632 | 0.843 | 0.723 | 43.00 | 1.000 | 7.00/7 |
| top_naive | 51 | 0.632 | 0.843 | 0.723 | 43.00 | 0.714 | 5.00/7 |
| temporal_nms_naive | 51 | 0.603 | 0.804 | 0.689 | 41.00 | 1.000 | 7.00/7 |
| top_kinematic | 51 | 0.544 | 0.725 | 0.622 | 37.00 | 1.000 | 7.00/7 |
| random | 51 | 0.496 ± 0.028 | 0.661 ± 0.038 | 0.566 ± 0.032 | 33.70 | 0.993 | 6.95/7 |
| uniform_time | 51 | 0.485 | 0.647 | 0.555 | 33.00 | 1.000 | 7.00/7 |


## strict Label: Event-Level Results

### Budget Ratio 0.05

Best event recall: 0.714 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 6 | 0.714 | 5.00/7 | 0.044 | 0.500 |
| uniform_time | 6 | 0.571 | 4.00/7 | 0.059 | 0.667 |
| random | 6 | 0.500 ± 0.109 | 3.50/7 | 0.061 | 0.692 |
| ensemble_all_proxy | 6 | 0.429 | 3.00/7 | 0.088 | 1.000 |
| temporal_nms_ensemble | 6 | 0.429 | 3.00/7 | 0.088 | 1.000 |
| temporal_nms_naive | 6 | 0.429 | 3.00/7 | 0.074 | 0.833 |
| top_naive | 6 | 0.429 | 3.00/7 | 0.074 | 0.833 |
| ensemble_count_naive | 6 | 0.286 | 2.00/7 | 0.088 | 1.000 |
| proxy_then_expansion_ensemble | 6 | 0.286 | 2.00/7 | 0.088 | 1.000 |
| temporal_nms_count | 6 | 0.286 | 2.00/7 | 0.088 | 1.000 |
| proxy_then_expansion_naive | 6 | 0.286 | 2.00/7 | 0.074 | 0.833 |
| top_count | 6 | 0.143 | 1.00/7 | 0.088 | 1.000 |
| proxy_then_expansion_count | 6 | 0.143 | 1.00/7 | 0.074 | 0.833 |
| uniform_expansion | 6 | 0.143 | 1.00/7 | 0.074 | 0.833 |

### Budget Ratio 0.10

Best event recall: 0.857 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 11 | 0.857 | 6.00/7 | 0.074 | 0.455 |
| temporal_nms_naive | 11 | 0.714 | 5.00/7 | 0.132 | 0.818 |
| uniform_time | 11 | 0.714 | 5.00/7 | 0.118 | 0.727 |
| random | 11 | 0.629 ± 0.134 | 4.40/7 | 0.109 | 0.673 |
| temporal_nms_ensemble | 11 | 0.571 | 4.00/7 | 0.147 | 0.909 |
| ensemble_all_proxy | 11 | 0.429 | 3.00/7 | 0.162 | 1.000 |
| ensemble_count_naive | 11 | 0.429 | 3.00/7 | 0.162 | 1.000 |
| temporal_nms_count | 11 | 0.429 | 3.00/7 | 0.162 | 1.000 |
| proxy_then_expansion_naive | 11 | 0.429 | 3.00/7 | 0.147 | 0.909 |
| top_naive | 11 | 0.429 | 3.00/7 | 0.132 | 0.818 |
| proxy_then_expansion_ensemble | 11 | 0.286 | 2.00/7 | 0.147 | 0.909 |
| top_count | 11 | 0.143 | 1.00/7 | 0.162 | 1.000 |
| proxy_then_expansion_count | 11 | 0.143 | 1.00/7 | 0.147 | 0.909 |
| uniform_expansion | 11 | 0.143 | 1.00/7 | 0.147 | 0.909 |

### Budget Ratio 0.15

Best event recall: 1.000 by temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_ensemble | 16 | 1.000 | 7.00/7 | 0.176 | 0.750 |
| temporal_nms_naive | 16 | 1.000 | 7.00/7 | 0.176 | 0.750 |
| uniform_time | 16 | 1.000 | 7.00/7 | 0.162 | 0.688 |
| top_kinematic | 16 | 1.000 | 7.00/7 | 0.118 | 0.500 |
| temporal_nms_count | 16 | 0.857 | 6.00/7 | 0.221 | 0.938 |
| random | 16 | 0.836 ± 0.133 | 5.85/7 | 0.153 | 0.650 |
| top_naive | 16 | 0.571 | 4.00/7 | 0.176 | 0.750 |
| ensemble_all_proxy | 16 | 0.429 | 3.00/7 | 0.221 | 0.938 |
| ensemble_count_naive | 16 | 0.429 | 3.00/7 | 0.221 | 0.938 |
| proxy_then_expansion_naive | 16 | 0.429 | 3.00/7 | 0.221 | 0.938 |
| proxy_then_expansion_ensemble | 16 | 0.286 | 2.00/7 | 0.221 | 0.938 |
| top_count | 16 | 0.143 | 1.00/7 | 0.235 | 1.000 |
| proxy_then_expansion_count | 16 | 0.143 | 1.00/7 | 0.221 | 0.938 |
| uniform_expansion | 16 | 0.143 | 1.00/7 | 0.221 | 0.938 |

### Budget Ratio 0.20

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 21 | 1.000 | 7.00/7 | 0.250 | 0.810 |
| temporal_nms_ensemble | 21 | 1.000 | 7.00/7 | 0.235 | 0.762 |
| temporal_nms_naive | 21 | 1.000 | 7.00/7 | 0.221 | 0.714 |
| uniform_time | 21 | 1.000 | 7.00/7 | 0.221 | 0.714 |
| top_kinematic | 21 | 1.000 | 7.00/7 | 0.191 | 0.619 |
| random | 21 | 0.871 ± 0.079 | 6.10/7 | 0.201 | 0.650 |
| top_naive | 21 | 0.571 | 4.00/7 | 0.250 | 0.810 |
| ensemble_all_proxy | 21 | 0.429 | 3.00/7 | 0.294 | 0.952 |
| ensemble_count_naive | 21 | 0.429 | 3.00/7 | 0.294 | 0.952 |
| proxy_then_expansion_ensemble | 21 | 0.429 | 3.00/7 | 0.294 | 0.952 |
| proxy_then_expansion_naive | 21 | 0.429 | 3.00/7 | 0.279 | 0.905 |
| top_count | 21 | 0.286 | 2.00/7 | 0.309 | 1.000 |
| proxy_then_expansion_count | 21 | 0.286 | 2.00/7 | 0.294 | 0.952 |
| uniform_expansion | 21 | 0.143 | 1.00/7 | 0.294 | 0.952 |

### Budget Ratio 0.30

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 31 | 1.000 | 7.00/7 | 0.397 | 0.871 |
| temporal_nms_ensemble | 31 | 1.000 | 7.00/7 | 0.368 | 0.806 |
| temporal_nms_naive | 31 | 1.000 | 7.00/7 | 0.338 | 0.742 |
| top_kinematic | 31 | 1.000 | 7.00/7 | 0.309 | 0.677 |
| uniform_time | 31 | 1.000 | 7.00/7 | 0.309 | 0.677 |
| random | 31 | 0.936 ± 0.098 | 6.55/7 | 0.293 | 0.644 |
| top_naive | 31 | 0.714 | 5.00/7 | 0.382 | 0.839 |
| proxy_then_expansion_naive | 31 | 0.571 | 4.00/7 | 0.397 | 0.871 |
| ensemble_count_naive | 31 | 0.429 | 3.00/7 | 0.426 | 0.935 |
| proxy_then_expansion_ensemble | 31 | 0.429 | 3.00/7 | 0.426 | 0.935 |
| ensemble_all_proxy | 31 | 0.429 | 3.00/7 | 0.412 | 0.903 |
| top_count | 31 | 0.286 | 2.00/7 | 0.456 | 1.000 |
| proxy_then_expansion_count | 31 | 0.286 | 2.00/7 | 0.441 | 0.968 |
| uniform_expansion | 31 | 0.286 | 2.00/7 | 0.412 | 0.903 |

### Budget Ratio 0.50

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 51 | 1.000 | 7.00/7 | 0.676 | 0.902 |
| temporal_nms_ensemble | 51 | 1.000 | 7.00/7 | 0.632 | 0.843 |
| temporal_nms_naive | 51 | 1.000 | 7.00/7 | 0.603 | 0.804 |
| top_kinematic | 51 | 1.000 | 7.00/7 | 0.544 | 0.725 |
| uniform_time | 51 | 1.000 | 7.00/7 | 0.485 | 0.647 |
| random | 51 | 0.993 ± 0.032 | 6.95/7 | 0.496 | 0.661 |
| ensemble_all_proxy | 51 | 0.714 | 5.00/7 | 0.662 | 0.882 |
| proxy_then_expansion_naive | 51 | 0.714 | 5.00/7 | 0.662 | 0.882 |
| top_naive | 51 | 0.714 | 5.00/7 | 0.632 | 0.843 |
| proxy_then_expansion_count | 51 | 0.571 | 4.00/7 | 0.706 | 0.941 |
| proxy_then_expansion_ensemble | 51 | 0.429 | 3.00/7 | 0.706 | 0.941 |
| ensemble_count_naive | 51 | 0.429 | 3.00/7 | 0.691 | 0.922 |
| top_count | 51 | 0.429 | 3.00/7 | 0.691 | 0.922 |
| uniform_expansion | 51 | 0.286 | 2.00/7 | 0.706 | 0.941 |


## strict_v2 Label: Clip-Level Results

### Budget Ratio 0.05

Best clip recall: 0.088 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, temporal_nms_count, temporal_nms_ensemble, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_ensemble | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.286 | 2.00/7 |
| temporal_nms_count | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.286 | 2.00/7 |
| temporal_nms_ensemble | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.429 | 3.00/7 |
| top_count | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_count | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_naive | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.286 | 2.00/7 |
| temporal_nms_naive | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.429 | 3.00/7 |
| top_naive | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.429 | 3.00/7 |
| uniform_expansion | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.143 | 1.00/7 |
| random | 6 | 0.061 ± 0.016 | 0.692 ± 0.182 | 0.112 ± 0.029 | 4.15 | 0.500 | 3.50/7 |
| uniform_time | 6 | 0.059 | 0.667 | 0.108 | 4.00 | 0.571 | 4.00/7 |
| top_kinematic | 6 | 0.044 | 0.500 | 0.081 | 3.00 | 0.714 | 5.00/7 |

### Budget Ratio 0.10

Best clip recall: 0.162 by ensemble_all_proxy, ensemble_count_naive, temporal_nms_count, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.429 | 3.00/7 |
| top_count | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_count | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_ensemble | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_naive | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.429 | 3.00/7 |
| temporal_nms_ensemble | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.571 | 4.00/7 |
| uniform_expansion | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.143 | 1.00/7 |
| temporal_nms_naive | 11 | 0.132 | 0.818 | 0.228 | 9.00 | 0.714 | 5.00/7 |
| top_naive | 11 | 0.132 | 0.818 | 0.228 | 9.00 | 0.429 | 3.00/7 |
| uniform_time | 11 | 0.118 | 0.727 | 0.203 | 8.00 | 0.714 | 5.00/7 |
| random | 11 | 0.109 ± 0.018 | 0.673 ± 0.112 | 0.187 ± 0.031 | 7.40 | 0.629 | 4.40/7 |
| top_kinematic | 11 | 0.074 | 0.455 | 0.127 | 5.00 | 0.857 | 6.00/7 |

### Budget Ratio 0.15

Best clip recall: 0.235 by top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 16 | 0.235 | 1.000 | 0.381 | 16.00 | 0.143 | 1.00/7 |
| ensemble_all_proxy | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.429 | 3.00/7 |
| proxy_then_expansion_count | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_ensemble | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_naive | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.857 | 6.00/7 |
| uniform_expansion | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.143 | 1.00/7 |
| temporal_nms_ensemble | 16 | 0.176 | 0.750 | 0.286 | 12.00 | 1.000 | 7.00/7 |
| temporal_nms_naive | 16 | 0.176 | 0.750 | 0.286 | 12.00 | 1.000 | 7.00/7 |
| top_naive | 16 | 0.176 | 0.750 | 0.286 | 12.00 | 0.571 | 4.00/7 |
| uniform_time | 16 | 0.162 | 0.688 | 0.262 | 11.00 | 1.000 | 7.00/7 |
| random | 16 | 0.153 ± 0.031 | 0.650 ± 0.132 | 0.248 ± 0.050 | 10.40 | 0.836 | 5.85/7 |
| top_kinematic | 16 | 0.118 | 0.500 | 0.190 | 8.00 | 1.000 | 7.00/7 |

### Budget Ratio 0.20

Best clip recall: 0.309 by top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 21 | 0.309 | 1.000 | 0.472 | 21.00 | 0.286 | 2.00/7 |
| ensemble_all_proxy | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.429 | 3.00/7 |
| proxy_then_expansion_count | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_ensemble | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.429 | 3.00/7 |
| uniform_expansion | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_naive | 21 | 0.279 | 0.905 | 0.427 | 19.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 21 | 0.250 | 0.810 | 0.382 | 17.00 | 1.000 | 7.00/7 |
| top_naive | 21 | 0.250 | 0.810 | 0.382 | 17.00 | 0.571 | 4.00/7 |
| temporal_nms_ensemble | 21 | 0.235 | 0.762 | 0.360 | 16.00 | 1.000 | 7.00/7 |
| temporal_nms_naive | 21 | 0.221 | 0.714 | 0.337 | 15.00 | 1.000 | 7.00/7 |
| uniform_time | 21 | 0.221 | 0.714 | 0.337 | 15.00 | 1.000 | 7.00/7 |
| random | 21 | 0.201 ± 0.036 | 0.650 ± 0.116 | 0.307 ± 0.055 | 13.65 | 0.871 | 6.10/7 |
| top_kinematic | 21 | 0.191 | 0.619 | 0.292 | 13.00 | 1.000 | 7.00/7 |

### Budget Ratio 0.30

Best clip recall: 0.456 by top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 31 | 0.456 | 1.000 | 0.626 | 31.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_count | 31 | 0.441 | 0.968 | 0.606 | 30.00 | 0.286 | 2.00/7 |
| ensemble_count_naive | 31 | 0.426 | 0.935 | 0.586 | 29.00 | 0.429 | 3.00/7 |
| proxy_then_expansion_ensemble | 31 | 0.426 | 0.935 | 0.586 | 29.00 | 0.429 | 3.00/7 |
| ensemble_all_proxy | 31 | 0.412 | 0.903 | 0.566 | 28.00 | 0.429 | 3.00/7 |
| uniform_expansion | 31 | 0.412 | 0.903 | 0.566 | 28.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_naive | 31 | 0.397 | 0.871 | 0.545 | 27.00 | 0.571 | 4.00/7 |
| temporal_nms_count | 31 | 0.397 | 0.871 | 0.545 | 27.00 | 1.000 | 7.00/7 |
| top_naive | 31 | 0.382 | 0.839 | 0.525 | 26.00 | 0.714 | 5.00/7 |
| temporal_nms_ensemble | 31 | 0.368 | 0.806 | 0.505 | 25.00 | 1.000 | 7.00/7 |
| temporal_nms_naive | 31 | 0.338 | 0.742 | 0.465 | 23.00 | 1.000 | 7.00/7 |
| top_kinematic | 31 | 0.309 | 0.677 | 0.424 | 21.00 | 1.000 | 7.00/7 |
| uniform_time | 31 | 0.309 | 0.677 | 0.424 | 21.00 | 1.000 | 7.00/7 |
| random | 31 | 0.293 ± 0.031 | 0.644 ± 0.067 | 0.403 ± 0.042 | 19.95 | 0.936 | 6.55/7 |

### Budget Ratio 0.50

Best clip recall: 0.706 by proxy_then_expansion_count, proxy_then_expansion_ensemble, uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| proxy_then_expansion_count | 51 | 0.706 | 0.941 | 0.807 | 48.00 | 0.571 | 4.00/7 |
| proxy_then_expansion_ensemble | 51 | 0.706 | 0.941 | 0.807 | 48.00 | 0.429 | 3.00/7 |
| uniform_expansion | 51 | 0.706 | 0.941 | 0.807 | 48.00 | 0.286 | 2.00/7 |
| ensemble_count_naive | 51 | 0.691 | 0.922 | 0.790 | 47.00 | 0.429 | 3.00/7 |
| top_count | 51 | 0.691 | 0.922 | 0.790 | 47.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 51 | 0.676 | 0.902 | 0.773 | 46.00 | 1.000 | 7.00/7 |
| ensemble_all_proxy | 51 | 0.662 | 0.882 | 0.756 | 45.00 | 0.714 | 5.00/7 |
| proxy_then_expansion_naive | 51 | 0.662 | 0.882 | 0.756 | 45.00 | 0.714 | 5.00/7 |
| temporal_nms_ensemble | 51 | 0.632 | 0.843 | 0.723 | 43.00 | 1.000 | 7.00/7 |
| top_naive | 51 | 0.632 | 0.843 | 0.723 | 43.00 | 0.714 | 5.00/7 |
| temporal_nms_naive | 51 | 0.603 | 0.804 | 0.689 | 41.00 | 1.000 | 7.00/7 |
| top_kinematic | 51 | 0.544 | 0.725 | 0.622 | 37.00 | 1.000 | 7.00/7 |
| random | 51 | 0.496 ± 0.028 | 0.661 ± 0.038 | 0.566 ± 0.032 | 33.70 | 0.993 | 6.95/7 |
| uniform_time | 51 | 0.485 | 0.647 | 0.555 | 33.00 | 1.000 | 7.00/7 |


## strict_v2 Label: Event-Level Results

### Budget Ratio 0.05

Best event recall: 0.714 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 6 | 0.714 | 5.00/7 | 0.044 | 0.500 |
| uniform_time | 6 | 0.571 | 4.00/7 | 0.059 | 0.667 |
| random | 6 | 0.500 ± 0.109 | 3.50/7 | 0.061 | 0.692 |
| ensemble_all_proxy | 6 | 0.429 | 3.00/7 | 0.088 | 1.000 |
| temporal_nms_ensemble | 6 | 0.429 | 3.00/7 | 0.088 | 1.000 |
| temporal_nms_naive | 6 | 0.429 | 3.00/7 | 0.074 | 0.833 |
| top_naive | 6 | 0.429 | 3.00/7 | 0.074 | 0.833 |
| ensemble_count_naive | 6 | 0.286 | 2.00/7 | 0.088 | 1.000 |
| proxy_then_expansion_ensemble | 6 | 0.286 | 2.00/7 | 0.088 | 1.000 |
| temporal_nms_count | 6 | 0.286 | 2.00/7 | 0.088 | 1.000 |
| proxy_then_expansion_naive | 6 | 0.286 | 2.00/7 | 0.074 | 0.833 |
| top_count | 6 | 0.143 | 1.00/7 | 0.088 | 1.000 |
| proxy_then_expansion_count | 6 | 0.143 | 1.00/7 | 0.074 | 0.833 |
| uniform_expansion | 6 | 0.143 | 1.00/7 | 0.074 | 0.833 |

### Budget Ratio 0.10

Best event recall: 0.857 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 11 | 0.857 | 6.00/7 | 0.074 | 0.455 |
| temporal_nms_naive | 11 | 0.714 | 5.00/7 | 0.132 | 0.818 |
| uniform_time | 11 | 0.714 | 5.00/7 | 0.118 | 0.727 |
| random | 11 | 0.629 ± 0.134 | 4.40/7 | 0.109 | 0.673 |
| temporal_nms_ensemble | 11 | 0.571 | 4.00/7 | 0.147 | 0.909 |
| ensemble_all_proxy | 11 | 0.429 | 3.00/7 | 0.162 | 1.000 |
| ensemble_count_naive | 11 | 0.429 | 3.00/7 | 0.162 | 1.000 |
| temporal_nms_count | 11 | 0.429 | 3.00/7 | 0.162 | 1.000 |
| proxy_then_expansion_naive | 11 | 0.429 | 3.00/7 | 0.147 | 0.909 |
| top_naive | 11 | 0.429 | 3.00/7 | 0.132 | 0.818 |
| proxy_then_expansion_ensemble | 11 | 0.286 | 2.00/7 | 0.147 | 0.909 |
| top_count | 11 | 0.143 | 1.00/7 | 0.162 | 1.000 |
| proxy_then_expansion_count | 11 | 0.143 | 1.00/7 | 0.147 | 0.909 |
| uniform_expansion | 11 | 0.143 | 1.00/7 | 0.147 | 0.909 |

### Budget Ratio 0.15

Best event recall: 1.000 by temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_ensemble | 16 | 1.000 | 7.00/7 | 0.176 | 0.750 |
| temporal_nms_naive | 16 | 1.000 | 7.00/7 | 0.176 | 0.750 |
| uniform_time | 16 | 1.000 | 7.00/7 | 0.162 | 0.688 |
| top_kinematic | 16 | 1.000 | 7.00/7 | 0.118 | 0.500 |
| temporal_nms_count | 16 | 0.857 | 6.00/7 | 0.221 | 0.938 |
| random | 16 | 0.836 ± 0.133 | 5.85/7 | 0.153 | 0.650 |
| top_naive | 16 | 0.571 | 4.00/7 | 0.176 | 0.750 |
| ensemble_all_proxy | 16 | 0.429 | 3.00/7 | 0.221 | 0.938 |
| ensemble_count_naive | 16 | 0.429 | 3.00/7 | 0.221 | 0.938 |
| proxy_then_expansion_naive | 16 | 0.429 | 3.00/7 | 0.221 | 0.938 |
| proxy_then_expansion_ensemble | 16 | 0.286 | 2.00/7 | 0.221 | 0.938 |
| top_count | 16 | 0.143 | 1.00/7 | 0.235 | 1.000 |
| proxy_then_expansion_count | 16 | 0.143 | 1.00/7 | 0.221 | 0.938 |
| uniform_expansion | 16 | 0.143 | 1.00/7 | 0.221 | 0.938 |

### Budget Ratio 0.20

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 21 | 1.000 | 7.00/7 | 0.250 | 0.810 |
| temporal_nms_ensemble | 21 | 1.000 | 7.00/7 | 0.235 | 0.762 |
| temporal_nms_naive | 21 | 1.000 | 7.00/7 | 0.221 | 0.714 |
| uniform_time | 21 | 1.000 | 7.00/7 | 0.221 | 0.714 |
| top_kinematic | 21 | 1.000 | 7.00/7 | 0.191 | 0.619 |
| random | 21 | 0.871 ± 0.079 | 6.10/7 | 0.201 | 0.650 |
| top_naive | 21 | 0.571 | 4.00/7 | 0.250 | 0.810 |
| ensemble_all_proxy | 21 | 0.429 | 3.00/7 | 0.294 | 0.952 |
| ensemble_count_naive | 21 | 0.429 | 3.00/7 | 0.294 | 0.952 |
| proxy_then_expansion_ensemble | 21 | 0.429 | 3.00/7 | 0.294 | 0.952 |
| proxy_then_expansion_naive | 21 | 0.429 | 3.00/7 | 0.279 | 0.905 |
| top_count | 21 | 0.286 | 2.00/7 | 0.309 | 1.000 |
| proxy_then_expansion_count | 21 | 0.286 | 2.00/7 | 0.294 | 0.952 |
| uniform_expansion | 21 | 0.143 | 1.00/7 | 0.294 | 0.952 |

### Budget Ratio 0.30

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 31 | 1.000 | 7.00/7 | 0.397 | 0.871 |
| temporal_nms_ensemble | 31 | 1.000 | 7.00/7 | 0.368 | 0.806 |
| temporal_nms_naive | 31 | 1.000 | 7.00/7 | 0.338 | 0.742 |
| top_kinematic | 31 | 1.000 | 7.00/7 | 0.309 | 0.677 |
| uniform_time | 31 | 1.000 | 7.00/7 | 0.309 | 0.677 |
| random | 31 | 0.936 ± 0.098 | 6.55/7 | 0.293 | 0.644 |
| top_naive | 31 | 0.714 | 5.00/7 | 0.382 | 0.839 |
| proxy_then_expansion_naive | 31 | 0.571 | 4.00/7 | 0.397 | 0.871 |
| ensemble_count_naive | 31 | 0.429 | 3.00/7 | 0.426 | 0.935 |
| proxy_then_expansion_ensemble | 31 | 0.429 | 3.00/7 | 0.426 | 0.935 |
| ensemble_all_proxy | 31 | 0.429 | 3.00/7 | 0.412 | 0.903 |
| top_count | 31 | 0.286 | 2.00/7 | 0.456 | 1.000 |
| proxy_then_expansion_count | 31 | 0.286 | 2.00/7 | 0.441 | 0.968 |
| uniform_expansion | 31 | 0.286 | 2.00/7 | 0.412 | 0.903 |

### Budget Ratio 0.50

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 51 | 1.000 | 7.00/7 | 0.676 | 0.902 |
| temporal_nms_ensemble | 51 | 1.000 | 7.00/7 | 0.632 | 0.843 |
| temporal_nms_naive | 51 | 1.000 | 7.00/7 | 0.603 | 0.804 |
| top_kinematic | 51 | 1.000 | 7.00/7 | 0.544 | 0.725 |
| uniform_time | 51 | 1.000 | 7.00/7 | 0.485 | 0.647 |
| random | 51 | 0.993 ± 0.032 | 6.95/7 | 0.496 | 0.661 |
| ensemble_all_proxy | 51 | 0.714 | 5.00/7 | 0.662 | 0.882 |
| proxy_then_expansion_naive | 51 | 0.714 | 5.00/7 | 0.662 | 0.882 |
| top_naive | 51 | 0.714 | 5.00/7 | 0.632 | 0.843 |
| proxy_then_expansion_count | 51 | 0.571 | 4.00/7 | 0.706 | 0.941 |
| proxy_then_expansion_ensemble | 51 | 0.429 | 3.00/7 | 0.706 | 0.941 |
| ensemble_count_naive | 51 | 0.429 | 3.00/7 | 0.691 | 0.922 |
| top_count | 51 | 0.429 | 3.00/7 | 0.691 | 0.922 |
| uniform_expansion | 51 | 0.286 | 2.00/7 | 0.706 | 0.941 |


## strict_v3 Label: Clip-Level Results

### Budget Ratio 0.05

Best clip recall: 0.088 by ensemble_all_proxy, ensemble_count_naive, proxy_then_expansion_ensemble, temporal_nms_count, temporal_nms_ensemble, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_ensemble | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.286 | 2.00/7 |
| temporal_nms_count | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.286 | 2.00/7 |
| temporal_nms_ensemble | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.429 | 3.00/7 |
| top_count | 6 | 0.088 | 1.000 | 0.162 | 6.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_count | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_naive | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.286 | 2.00/7 |
| temporal_nms_naive | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.429 | 3.00/7 |
| top_naive | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.429 | 3.00/7 |
| uniform_expansion | 6 | 0.074 | 0.833 | 0.135 | 5.00 | 0.143 | 1.00/7 |
| random | 6 | 0.061 ± 0.016 | 0.692 ± 0.182 | 0.112 ± 0.029 | 4.15 | 0.500 | 3.50/7 |
| uniform_time | 6 | 0.059 | 0.667 | 0.108 | 4.00 | 0.571 | 4.00/7 |
| top_kinematic | 6 | 0.044 | 0.500 | 0.081 | 3.00 | 0.714 | 5.00/7 |

### Budget Ratio 0.10

Best clip recall: 0.162 by ensemble_all_proxy, ensemble_count_naive, temporal_nms_count, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_all_proxy | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.429 | 3.00/7 |
| top_count | 11 | 0.162 | 1.000 | 0.278 | 11.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_count | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_ensemble | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_naive | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.429 | 3.00/7 |
| temporal_nms_ensemble | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.571 | 4.00/7 |
| uniform_expansion | 11 | 0.147 | 0.909 | 0.253 | 10.00 | 0.143 | 1.00/7 |
| temporal_nms_naive | 11 | 0.132 | 0.818 | 0.228 | 9.00 | 0.714 | 5.00/7 |
| top_naive | 11 | 0.132 | 0.818 | 0.228 | 9.00 | 0.429 | 3.00/7 |
| uniform_time | 11 | 0.118 | 0.727 | 0.203 | 8.00 | 0.714 | 5.00/7 |
| random | 11 | 0.109 ± 0.018 | 0.673 ± 0.112 | 0.187 ± 0.031 | 7.40 | 0.629 | 4.40/7 |
| top_kinematic | 11 | 0.074 | 0.455 | 0.127 | 5.00 | 0.857 | 6.00/7 |

### Budget Ratio 0.15

Best clip recall: 0.235 by top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 16 | 0.235 | 1.000 | 0.381 | 16.00 | 0.143 | 1.00/7 |
| ensemble_all_proxy | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.429 | 3.00/7 |
| proxy_then_expansion_count | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_ensemble | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_naive | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.857 | 6.00/7 |
| uniform_expansion | 16 | 0.221 | 0.938 | 0.357 | 15.00 | 0.143 | 1.00/7 |
| temporal_nms_ensemble | 16 | 0.176 | 0.750 | 0.286 | 12.00 | 1.000 | 7.00/7 |
| temporal_nms_naive | 16 | 0.176 | 0.750 | 0.286 | 12.00 | 1.000 | 7.00/7 |
| top_naive | 16 | 0.176 | 0.750 | 0.286 | 12.00 | 0.571 | 4.00/7 |
| uniform_time | 16 | 0.162 | 0.688 | 0.262 | 11.00 | 1.000 | 7.00/7 |
| random | 16 | 0.153 ± 0.031 | 0.650 ± 0.132 | 0.248 ± 0.050 | 10.40 | 0.836 | 5.85/7 |
| top_kinematic | 16 | 0.118 | 0.500 | 0.190 | 8.00 | 1.000 | 7.00/7 |

### Budget Ratio 0.20

Best clip recall: 0.309 by top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 21 | 0.309 | 1.000 | 0.472 | 21.00 | 0.286 | 2.00/7 |
| ensemble_all_proxy | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.429 | 3.00/7 |
| proxy_then_expansion_count | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_ensemble | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.429 | 3.00/7 |
| uniform_expansion | 21 | 0.294 | 0.952 | 0.449 | 20.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_naive | 21 | 0.279 | 0.905 | 0.427 | 19.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 21 | 0.250 | 0.810 | 0.382 | 17.00 | 1.000 | 7.00/7 |
| top_naive | 21 | 0.250 | 0.810 | 0.382 | 17.00 | 0.571 | 4.00/7 |
| temporal_nms_ensemble | 21 | 0.235 | 0.762 | 0.360 | 16.00 | 1.000 | 7.00/7 |
| temporal_nms_naive | 21 | 0.221 | 0.714 | 0.337 | 15.00 | 1.000 | 7.00/7 |
| uniform_time | 21 | 0.221 | 0.714 | 0.337 | 15.00 | 1.000 | 7.00/7 |
| random | 21 | 0.201 ± 0.036 | 0.650 ± 0.116 | 0.307 ± 0.055 | 13.65 | 0.871 | 6.10/7 |
| top_kinematic | 21 | 0.191 | 0.619 | 0.292 | 13.00 | 1.000 | 7.00/7 |

### Budget Ratio 0.30

Best clip recall: 0.456 by top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 31 | 0.456 | 1.000 | 0.626 | 31.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_count | 31 | 0.441 | 0.968 | 0.606 | 30.00 | 0.286 | 2.00/7 |
| ensemble_count_naive | 31 | 0.426 | 0.935 | 0.586 | 29.00 | 0.429 | 3.00/7 |
| proxy_then_expansion_ensemble | 31 | 0.426 | 0.935 | 0.586 | 29.00 | 0.429 | 3.00/7 |
| ensemble_all_proxy | 31 | 0.412 | 0.903 | 0.566 | 28.00 | 0.429 | 3.00/7 |
| uniform_expansion | 31 | 0.412 | 0.903 | 0.566 | 28.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_naive | 31 | 0.397 | 0.871 | 0.545 | 27.00 | 0.571 | 4.00/7 |
| temporal_nms_count | 31 | 0.397 | 0.871 | 0.545 | 27.00 | 1.000 | 7.00/7 |
| top_naive | 31 | 0.382 | 0.839 | 0.525 | 26.00 | 0.714 | 5.00/7 |
| temporal_nms_ensemble | 31 | 0.368 | 0.806 | 0.505 | 25.00 | 1.000 | 7.00/7 |
| temporal_nms_naive | 31 | 0.338 | 0.742 | 0.465 | 23.00 | 1.000 | 7.00/7 |
| top_kinematic | 31 | 0.309 | 0.677 | 0.424 | 21.00 | 1.000 | 7.00/7 |
| uniform_time | 31 | 0.309 | 0.677 | 0.424 | 21.00 | 1.000 | 7.00/7 |
| random | 31 | 0.293 ± 0.031 | 0.644 ± 0.067 | 0.403 ± 0.042 | 19.95 | 0.936 | 6.55/7 |

### Budget Ratio 0.50

Best clip recall: 0.706 by proxy_then_expansion_count, proxy_then_expansion_ensemble, uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| proxy_then_expansion_count | 51 | 0.706 | 0.941 | 0.807 | 48.00 | 0.571 | 4.00/7 |
| proxy_then_expansion_ensemble | 51 | 0.706 | 0.941 | 0.807 | 48.00 | 0.429 | 3.00/7 |
| uniform_expansion | 51 | 0.706 | 0.941 | 0.807 | 48.00 | 0.286 | 2.00/7 |
| ensemble_count_naive | 51 | 0.691 | 0.922 | 0.790 | 47.00 | 0.429 | 3.00/7 |
| top_count | 51 | 0.691 | 0.922 | 0.790 | 47.00 | 0.429 | 3.00/7 |
| temporal_nms_count | 51 | 0.676 | 0.902 | 0.773 | 46.00 | 1.000 | 7.00/7 |
| ensemble_all_proxy | 51 | 0.662 | 0.882 | 0.756 | 45.00 | 0.714 | 5.00/7 |
| proxy_then_expansion_naive | 51 | 0.662 | 0.882 | 0.756 | 45.00 | 0.714 | 5.00/7 |
| temporal_nms_ensemble | 51 | 0.632 | 0.843 | 0.723 | 43.00 | 1.000 | 7.00/7 |
| top_naive | 51 | 0.632 | 0.843 | 0.723 | 43.00 | 0.714 | 5.00/7 |
| temporal_nms_naive | 51 | 0.603 | 0.804 | 0.689 | 41.00 | 1.000 | 7.00/7 |
| top_kinematic | 51 | 0.544 | 0.725 | 0.622 | 37.00 | 1.000 | 7.00/7 |
| random | 51 | 0.496 ± 0.028 | 0.661 ± 0.038 | 0.566 ± 0.032 | 33.70 | 0.993 | 6.95/7 |
| uniform_time | 51 | 0.485 | 0.647 | 0.555 | 33.00 | 1.000 | 7.00/7 |


## strict_v3 Label: Event-Level Results

### Budget Ratio 0.05

Best event recall: 0.714 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 6 | 0.714 | 5.00/7 | 0.044 | 0.500 |
| uniform_time | 6 | 0.571 | 4.00/7 | 0.059 | 0.667 |
| random | 6 | 0.500 ± 0.109 | 3.50/7 | 0.061 | 0.692 |
| ensemble_all_proxy | 6 | 0.429 | 3.00/7 | 0.088 | 1.000 |
| temporal_nms_ensemble | 6 | 0.429 | 3.00/7 | 0.088 | 1.000 |
| temporal_nms_naive | 6 | 0.429 | 3.00/7 | 0.074 | 0.833 |
| top_naive | 6 | 0.429 | 3.00/7 | 0.074 | 0.833 |
| ensemble_count_naive | 6 | 0.286 | 2.00/7 | 0.088 | 1.000 |
| proxy_then_expansion_ensemble | 6 | 0.286 | 2.00/7 | 0.088 | 1.000 |
| temporal_nms_count | 6 | 0.286 | 2.00/7 | 0.088 | 1.000 |
| proxy_then_expansion_naive | 6 | 0.286 | 2.00/7 | 0.074 | 0.833 |
| top_count | 6 | 0.143 | 1.00/7 | 0.088 | 1.000 |
| proxy_then_expansion_count | 6 | 0.143 | 1.00/7 | 0.074 | 0.833 |
| uniform_expansion | 6 | 0.143 | 1.00/7 | 0.074 | 0.833 |

### Budget Ratio 0.10

Best event recall: 0.857 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 11 | 0.857 | 6.00/7 | 0.074 | 0.455 |
| temporal_nms_naive | 11 | 0.714 | 5.00/7 | 0.132 | 0.818 |
| uniform_time | 11 | 0.714 | 5.00/7 | 0.118 | 0.727 |
| random | 11 | 0.629 ± 0.134 | 4.40/7 | 0.109 | 0.673 |
| temporal_nms_ensemble | 11 | 0.571 | 4.00/7 | 0.147 | 0.909 |
| ensemble_all_proxy | 11 | 0.429 | 3.00/7 | 0.162 | 1.000 |
| ensemble_count_naive | 11 | 0.429 | 3.00/7 | 0.162 | 1.000 |
| temporal_nms_count | 11 | 0.429 | 3.00/7 | 0.162 | 1.000 |
| proxy_then_expansion_naive | 11 | 0.429 | 3.00/7 | 0.147 | 0.909 |
| top_naive | 11 | 0.429 | 3.00/7 | 0.132 | 0.818 |
| proxy_then_expansion_ensemble | 11 | 0.286 | 2.00/7 | 0.147 | 0.909 |
| top_count | 11 | 0.143 | 1.00/7 | 0.162 | 1.000 |
| proxy_then_expansion_count | 11 | 0.143 | 1.00/7 | 0.147 | 0.909 |
| uniform_expansion | 11 | 0.143 | 1.00/7 | 0.147 | 0.909 |

### Budget Ratio 0.15

Best event recall: 1.000 by temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_ensemble | 16 | 1.000 | 7.00/7 | 0.176 | 0.750 |
| temporal_nms_naive | 16 | 1.000 | 7.00/7 | 0.176 | 0.750 |
| uniform_time | 16 | 1.000 | 7.00/7 | 0.162 | 0.688 |
| top_kinematic | 16 | 1.000 | 7.00/7 | 0.118 | 0.500 |
| temporal_nms_count | 16 | 0.857 | 6.00/7 | 0.221 | 0.938 |
| random | 16 | 0.836 ± 0.133 | 5.85/7 | 0.153 | 0.650 |
| top_naive | 16 | 0.571 | 4.00/7 | 0.176 | 0.750 |
| ensemble_all_proxy | 16 | 0.429 | 3.00/7 | 0.221 | 0.938 |
| ensemble_count_naive | 16 | 0.429 | 3.00/7 | 0.221 | 0.938 |
| proxy_then_expansion_naive | 16 | 0.429 | 3.00/7 | 0.221 | 0.938 |
| proxy_then_expansion_ensemble | 16 | 0.286 | 2.00/7 | 0.221 | 0.938 |
| top_count | 16 | 0.143 | 1.00/7 | 0.235 | 1.000 |
| proxy_then_expansion_count | 16 | 0.143 | 1.00/7 | 0.221 | 0.938 |
| uniform_expansion | 16 | 0.143 | 1.00/7 | 0.221 | 0.938 |

### Budget Ratio 0.20

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 21 | 1.000 | 7.00/7 | 0.250 | 0.810 |
| temporal_nms_ensemble | 21 | 1.000 | 7.00/7 | 0.235 | 0.762 |
| temporal_nms_naive | 21 | 1.000 | 7.00/7 | 0.221 | 0.714 |
| uniform_time | 21 | 1.000 | 7.00/7 | 0.221 | 0.714 |
| top_kinematic | 21 | 1.000 | 7.00/7 | 0.191 | 0.619 |
| random | 21 | 0.871 ± 0.079 | 6.10/7 | 0.201 | 0.650 |
| top_naive | 21 | 0.571 | 4.00/7 | 0.250 | 0.810 |
| ensemble_all_proxy | 21 | 0.429 | 3.00/7 | 0.294 | 0.952 |
| ensemble_count_naive | 21 | 0.429 | 3.00/7 | 0.294 | 0.952 |
| proxy_then_expansion_ensemble | 21 | 0.429 | 3.00/7 | 0.294 | 0.952 |
| proxy_then_expansion_naive | 21 | 0.429 | 3.00/7 | 0.279 | 0.905 |
| top_count | 21 | 0.286 | 2.00/7 | 0.309 | 1.000 |
| proxy_then_expansion_count | 21 | 0.286 | 2.00/7 | 0.294 | 0.952 |
| uniform_expansion | 21 | 0.143 | 1.00/7 | 0.294 | 0.952 |

### Budget Ratio 0.30

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 31 | 1.000 | 7.00/7 | 0.397 | 0.871 |
| temporal_nms_ensemble | 31 | 1.000 | 7.00/7 | 0.368 | 0.806 |
| temporal_nms_naive | 31 | 1.000 | 7.00/7 | 0.338 | 0.742 |
| top_kinematic | 31 | 1.000 | 7.00/7 | 0.309 | 0.677 |
| uniform_time | 31 | 1.000 | 7.00/7 | 0.309 | 0.677 |
| random | 31 | 0.936 ± 0.098 | 6.55/7 | 0.293 | 0.644 |
| top_naive | 31 | 0.714 | 5.00/7 | 0.382 | 0.839 |
| proxy_then_expansion_naive | 31 | 0.571 | 4.00/7 | 0.397 | 0.871 |
| ensemble_count_naive | 31 | 0.429 | 3.00/7 | 0.426 | 0.935 |
| proxy_then_expansion_ensemble | 31 | 0.429 | 3.00/7 | 0.426 | 0.935 |
| ensemble_all_proxy | 31 | 0.429 | 3.00/7 | 0.412 | 0.903 |
| top_count | 31 | 0.286 | 2.00/7 | 0.456 | 1.000 |
| proxy_then_expansion_count | 31 | 0.286 | 2.00/7 | 0.441 | 0.968 |
| uniform_expansion | 31 | 0.286 | 2.00/7 | 0.412 | 0.903 |

### Budget Ratio 0.50

Best event recall: 1.000 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 51 | 1.000 | 7.00/7 | 0.676 | 0.902 |
| temporal_nms_ensemble | 51 | 1.000 | 7.00/7 | 0.632 | 0.843 |
| temporal_nms_naive | 51 | 1.000 | 7.00/7 | 0.603 | 0.804 |
| top_kinematic | 51 | 1.000 | 7.00/7 | 0.544 | 0.725 |
| uniform_time | 51 | 1.000 | 7.00/7 | 0.485 | 0.647 |
| random | 51 | 0.993 ± 0.032 | 6.95/7 | 0.496 | 0.661 |
| ensemble_all_proxy | 51 | 0.714 | 5.00/7 | 0.662 | 0.882 |
| proxy_then_expansion_naive | 51 | 0.714 | 5.00/7 | 0.662 | 0.882 |
| top_naive | 51 | 0.714 | 5.00/7 | 0.632 | 0.843 |
| proxy_then_expansion_count | 51 | 0.571 | 4.00/7 | 0.706 | 0.941 |
| proxy_then_expansion_ensemble | 51 | 0.429 | 3.00/7 | 0.706 | 0.941 |
| ensemble_count_naive | 51 | 0.429 | 3.00/7 | 0.691 | 0.922 |
| top_count | 51 | 0.429 | 3.00/7 | 0.691 | 0.922 |
| uniform_expansion | 51 | 0.286 | 2.00/7 | 0.706 | 0.941 |


## Key Diagnostics

- Broad low-budget best clip recall: `ensemble_all_proxy` at 0.141.
- Broad low-budget best event recall: `ensemble_all_proxy` at 1.000.
- Broad high-budget best clip recall: `ensemble_all_proxy` at 0.427.
- Broad high-budget best event recall: `ensemble_all_proxy` at 1.000.
- temporal_nms_count vs top_count broad clip recall avg: 0.231 vs 0.236.
- temporal_nms_count vs top_count broad event recall avg: 0.917 vs 0.583.
- uniform_expansion broad clip/event recall avg: 0.226 / 0.500.
- top_kinematic broad clip/event recall avg: 0.236 / 1.000.
- uniform_expansion event recall tracks clip recall closely enough to suggest it is not only harvesting duplicate windows.

## Failure Conditions

- If VLM labels are missing, this script writes `vlm_labels_template.csv` and `BLOCKED_missing_vlm_labels.md` instead of fabricating results.
- If VLM-positive clips are fewer than 5, treat curves as unstable.
- These results are pseudo-oracle recovery results, not validated human-GT danger detection results.
