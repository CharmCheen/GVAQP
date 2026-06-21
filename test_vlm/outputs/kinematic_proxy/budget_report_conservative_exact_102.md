# VLM32B Pseudo-GT Budget Simulation

This report treats the available VLM32B scan as pseudo-GT / pseudo-oracle. It does not measure true real-world danger detection accuracy.

## Data Overview

- number of clips in proxy_scores: 102
- budget ratios: 0.05, 0.10, 0.15, 0.20, 0.30, 0.50
- methods evaluated: random, uniform_time, top_count, top_naive, top_kinematic, ensemble_count_naive, ensemble_all_proxy, temporal_nms_count, temporal_nms_naive, temporal_nms_ensemble, uniform_expansion, proxy_then_expansion_count, proxy_then_expansion_naive, proxy_then_expansion_ensemble
- event_merge_gap_sec: 4.000
- broad label available: False
- ego-relevant label available: False
- strict label available: False (old strict reconstructed from old exact VLM fields)
- high-confidence label available: False (not used for conservative evaluation)

## Variant Overview

| variant | valid clips | positives | positive rate | events |
|---|---:|---:|---:|---:|
| old_strict | 102 | 68 | 0.667 | 7 |
| conservative | 102 | 22 | 0.216 | 7 |

## Conservative Predicate Answers

- old_strict positive rate=0.667 (68/102); conservative positive rate=0.216 (22/102).
- positive events: old_strict=7, conservative=7.
- average positive run length: old_strict=8.500, conservative=3.143 clips.
- old_strict: low-budget 5%-20% best clip recall `top_count` (0.199); best event recall `top_kinematic` (0.893).
- conservative: low-budget 5%-20% best clip recall `top_count` (0.398); best event recall `temporal_nms_naive` (0.786).
- old_strict: best low-budget clip recall vs random=0.199/0.131; temporal-NMS best avg event recall=0.857; proxy-anchor sweep avg event recall=0.371 vs uniform-anchor=0.190.
- conservative: best low-budget clip recall vs random=0.398/0.128; temporal-NMS best avg event recall=0.810; proxy-anchor sweep avg event recall=0.452 vs uniform-anchor=0.214.
- Temporal-aware allocation remains supported under conservative pseudo-GT because clip recovery and event coverage prefer different policies.

## old_strict Label: Clip-Level Results

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


## old_strict Label: Event-Level Results

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


## conservative Label: Clip-Level Results

### Budget Ratio 0.05

Best clip recall: 0.182 by temporal_nms_ensemble, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| temporal_nms_ensemble | 6 | 0.182 | 0.667 | 0.286 | 4.00 | 0.571 | 4.00/7 |
| top_count | 6 | 0.182 | 0.667 | 0.286 | 4.00 | 0.143 | 1.00/7 |
| ensemble_all_proxy | 6 | 0.136 | 0.500 | 0.214 | 3.00 | 0.571 | 4.00/7 |
| ensemble_count_naive | 6 | 0.136 | 0.500 | 0.214 | 3.00 | 0.429 | 3.00/7 |
| proxy_then_expansion_count | 6 | 0.136 | 0.500 | 0.214 | 3.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_ensemble | 6 | 0.091 | 0.333 | 0.143 | 2.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_naive | 6 | 0.091 | 0.333 | 0.143 | 2.00 | 0.143 | 1.00/7 |
| temporal_nms_count | 6 | 0.091 | 0.333 | 0.143 | 2.00 | 0.286 | 2.00/7 |
| temporal_nms_naive | 6 | 0.091 | 0.333 | 0.143 | 2.00 | 0.571 | 4.00/7 |
| top_naive | 6 | 0.091 | 0.333 | 0.143 | 2.00 | 0.143 | 1.00/7 |
| random | 6 | 0.057 ± 0.041 | 0.208 ± 0.152 | 0.089 ± 0.065 | 1.25 | 0.379 | 2.65/7 |
| top_kinematic | 6 | 0.045 | 0.167 | 0.071 | 1.00 | 0.429 | 3.00/7 |
| uniform_expansion | 6 | 0.045 | 0.167 | 0.071 | 1.00 | 0.143 | 1.00/7 |
| uniform_time | 6 | 0.000 | 0.000 | 0.000 | 0.00 | 0.143 | 1.00/7 |

### Budget Ratio 0.10

Best clip recall: 0.409 by top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 11 | 0.409 | 0.818 | 0.545 | 9.00 | 0.143 | 1.00/7 |
| proxy_then_expansion_count | 11 | 0.364 | 0.727 | 0.485 | 8.00 | 0.143 | 1.00/7 |
| ensemble_all_proxy | 11 | 0.318 | 0.636 | 0.424 | 7.00 | 0.571 | 4.00/7 |
| uniform_expansion | 11 | 0.273 | 0.545 | 0.364 | 6.00 | 0.143 | 1.00/7 |
| ensemble_count_naive | 11 | 0.227 | 0.455 | 0.303 | 5.00 | 0.571 | 4.00/7 |
| proxy_then_expansion_ensemble | 11 | 0.227 | 0.455 | 0.303 | 5.00 | 0.286 | 2.00/7 |
| proxy_then_expansion_naive | 11 | 0.182 | 0.364 | 0.242 | 4.00 | 0.286 | 2.00/7 |
| temporal_nms_ensemble | 11 | 0.182 | 0.364 | 0.242 | 4.00 | 0.714 | 5.00/7 |
| temporal_nms_naive | 11 | 0.182 | 0.364 | 0.242 | 4.00 | 0.857 | 6.00/7 |
| temporal_nms_count | 11 | 0.136 | 0.273 | 0.182 | 3.00 | 0.714 | 5.00/7 |
| top_naive | 11 | 0.136 | 0.273 | 0.182 | 3.00 | 0.571 | 4.00/7 |
| random | 11 | 0.107 ± 0.054 | 0.214 ± 0.107 | 0.142 ± 0.072 | 2.35 | 0.514 | 3.60/7 |
| uniform_time | 11 | 0.091 | 0.182 | 0.121 | 2.00 | 0.571 | 4.00/7 |
| top_kinematic | 11 | 0.045 | 0.091 | 0.061 | 1.00 | 0.714 | 5.00/7 |

### Budget Ratio 0.15

Best clip recall: 0.500 by proxy_then_expansion_count, top_count, uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| proxy_then_expansion_count | 16 | 0.500 | 0.688 | 0.579 | 11.00 | 0.143 | 1.00/7 |
| top_count | 16 | 0.500 | 0.688 | 0.579 | 11.00 | 0.143 | 1.00/7 |
| uniform_expansion | 16 | 0.500 | 0.688 | 0.579 | 11.00 | 0.143 | 1.00/7 |
| ensemble_count_naive | 16 | 0.364 | 0.500 | 0.421 | 8.00 | 0.571 | 4.00/7 |
| ensemble_all_proxy | 16 | 0.318 | 0.438 | 0.368 | 7.00 | 0.571 | 4.00/7 |
| proxy_then_expansion_ensemble | 16 | 0.318 | 0.438 | 0.368 | 7.00 | 0.571 | 4.00/7 |
| proxy_then_expansion_naive | 16 | 0.227 | 0.312 | 0.263 | 5.00 | 0.571 | 4.00/7 |
| temporal_nms_naive | 16 | 0.227 | 0.312 | 0.263 | 5.00 | 0.857 | 6.00/7 |
| temporal_nms_count | 16 | 0.182 | 0.250 | 0.211 | 4.00 | 0.857 | 6.00/7 |
| temporal_nms_ensemble | 16 | 0.182 | 0.250 | 0.211 | 4.00 | 0.857 | 6.00/7 |
| top_naive | 16 | 0.182 | 0.250 | 0.211 | 4.00 | 0.571 | 4.00/7 |
| random | 16 | 0.143 ± 0.058 | 0.197 ± 0.079 | 0.166 ± 0.067 | 3.15 | 0.614 | 4.30/7 |
| top_kinematic | 16 | 0.091 | 0.125 | 0.105 | 2.00 | 0.714 | 5.00/7 |
| uniform_time | 16 | 0.091 | 0.125 | 0.105 | 2.00 | 0.857 | 6.00/7 |

### Budget Ratio 0.20

Best clip recall: 0.500 by proxy_then_expansion_count, top_count, uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| proxy_then_expansion_count | 21 | 0.500 | 0.524 | 0.512 | 11.00 | 0.143 | 1.00/7 |
| top_count | 21 | 0.500 | 0.524 | 0.512 | 11.00 | 0.143 | 1.00/7 |
| uniform_expansion | 21 | 0.500 | 0.524 | 0.512 | 11.00 | 0.143 | 1.00/7 |
| ensemble_all_proxy | 21 | 0.455 | 0.476 | 0.465 | 10.00 | 0.571 | 4.00/7 |
| ensemble_count_naive | 21 | 0.455 | 0.476 | 0.465 | 10.00 | 0.714 | 5.00/7 |
| proxy_then_expansion_ensemble | 21 | 0.455 | 0.476 | 0.465 | 10.00 | 0.571 | 4.00/7 |
| top_naive | 21 | 0.318 | 0.333 | 0.326 | 7.00 | 0.714 | 5.00/7 |
| proxy_then_expansion_naive | 21 | 0.273 | 0.286 | 0.279 | 6.00 | 0.714 | 5.00/7 |
| temporal_nms_count | 21 | 0.227 | 0.238 | 0.233 | 5.00 | 0.857 | 6.00/7 |
| temporal_nms_ensemble | 21 | 0.227 | 0.238 | 0.233 | 5.00 | 0.857 | 6.00/7 |
| temporal_nms_naive | 21 | 0.227 | 0.238 | 0.233 | 5.00 | 0.857 | 6.00/7 |
| top_kinematic | 21 | 0.227 | 0.238 | 0.233 | 5.00 | 0.857 | 6.00/7 |
| uniform_time | 21 | 0.227 | 0.238 | 0.233 | 5.00 | 1.000 | 7.00/7 |
| random | 21 | 0.207 ± 0.090 | 0.217 ± 0.095 | 0.212 ± 0.092 | 4.55 | 0.771 | 5.40/7 |

### Budget Ratio 0.30

Best clip recall: 0.682 by proxy_then_expansion_ensemble, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| proxy_then_expansion_ensemble | 31 | 0.682 | 0.484 | 0.566 | 15.00 | 0.714 | 5.00/7 |
| top_count | 31 | 0.682 | 0.484 | 0.566 | 15.00 | 0.429 | 3.00/7 |
| ensemble_count_naive | 31 | 0.636 | 0.452 | 0.528 | 14.00 | 0.714 | 5.00/7 |
| proxy_then_expansion_count | 31 | 0.636 | 0.452 | 0.528 | 14.00 | 0.429 | 3.00/7 |
| proxy_then_expansion_naive | 31 | 0.591 | 0.419 | 0.491 | 13.00 | 0.714 | 5.00/7 |
| temporal_nms_count | 31 | 0.591 | 0.419 | 0.491 | 13.00 | 0.857 | 6.00/7 |
| ensemble_all_proxy | 31 | 0.545 | 0.387 | 0.453 | 12.00 | 0.571 | 4.00/7 |
| uniform_expansion | 31 | 0.500 | 0.355 | 0.415 | 11.00 | 0.143 | 1.00/7 |
| temporal_nms_ensemble | 31 | 0.455 | 0.323 | 0.377 | 10.00 | 0.857 | 6.00/7 |
| top_naive | 31 | 0.409 | 0.290 | 0.340 | 9.00 | 0.857 | 6.00/7 |
| temporal_nms_naive | 31 | 0.364 | 0.258 | 0.302 | 8.00 | 0.857 | 6.00/7 |
| top_kinematic | 31 | 0.364 | 0.258 | 0.302 | 8.00 | 0.857 | 6.00/7 |
| random | 31 | 0.298 ± 0.076 | 0.211 ± 0.054 | 0.247 ± 0.063 | 6.55 | 0.893 | 6.25/7 |
| uniform_time | 31 | 0.227 | 0.161 | 0.189 | 5.00 | 1.000 | 7.00/7 |

### Budget Ratio 0.50

Best clip recall: 0.909 by ensemble_count_naive, proxy_then_expansion_count, proxy_then_expansion_ensemble, temporal_nms_count, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_count_naive | 51 | 0.909 | 0.392 | 0.548 | 20.00 | 0.714 | 5.00/7 |
| proxy_then_expansion_count | 51 | 0.909 | 0.392 | 0.548 | 20.00 | 0.714 | 5.00/7 |
| proxy_then_expansion_ensemble | 51 | 0.909 | 0.392 | 0.548 | 20.00 | 0.714 | 5.00/7 |
| temporal_nms_count | 51 | 0.909 | 0.392 | 0.548 | 20.00 | 0.857 | 6.00/7 |
| top_count | 51 | 0.909 | 0.392 | 0.548 | 20.00 | 0.714 | 5.00/7 |
| ensemble_all_proxy | 51 | 0.818 | 0.353 | 0.493 | 18.00 | 0.714 | 5.00/7 |
| proxy_then_expansion_naive | 51 | 0.818 | 0.353 | 0.493 | 18.00 | 0.857 | 6.00/7 |
| temporal_nms_ensemble | 51 | 0.818 | 0.353 | 0.493 | 18.00 | 0.857 | 6.00/7 |
| top_naive | 51 | 0.773 | 0.333 | 0.466 | 17.00 | 0.857 | 6.00/7 |
| uniform_expansion | 51 | 0.773 | 0.333 | 0.466 | 17.00 | 0.571 | 4.00/7 |
| temporal_nms_naive | 51 | 0.727 | 0.314 | 0.438 | 16.00 | 0.857 | 6.00/7 |
| uniform_time | 51 | 0.545 | 0.235 | 0.329 | 12.00 | 1.000 | 7.00/7 |
| random | 51 | 0.493 ± 0.080 | 0.213 ± 0.034 | 0.297 ± 0.048 | 10.85 | 1.000 | 7.00/7 |
| top_kinematic | 51 | 0.455 | 0.196 | 0.274 | 10.00 | 1.000 | 7.00/7 |


## conservative Label: Event-Level Results

### Budget Ratio 0.05

Best event recall: 0.571 by ensemble_all_proxy, temporal_nms_ensemble, temporal_nms_naive.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_ensemble | 6 | 0.571 | 4.00/7 | 0.182 | 0.667 |
| ensemble_all_proxy | 6 | 0.571 | 4.00/7 | 0.136 | 0.500 |
| temporal_nms_naive | 6 | 0.571 | 4.00/7 | 0.091 | 0.333 |
| ensemble_count_naive | 6 | 0.429 | 3.00/7 | 0.136 | 0.500 |
| top_kinematic | 6 | 0.429 | 3.00/7 | 0.045 | 0.167 |
| random | 6 | 0.379 ± 0.156 | 2.65/7 | 0.057 | 0.208 |
| temporal_nms_count | 6 | 0.286 | 2.00/7 | 0.091 | 0.333 |
| top_count | 6 | 0.143 | 1.00/7 | 0.182 | 0.667 |
| proxy_then_expansion_count | 6 | 0.143 | 1.00/7 | 0.136 | 0.500 |
| proxy_then_expansion_ensemble | 6 | 0.143 | 1.00/7 | 0.091 | 0.333 |
| proxy_then_expansion_naive | 6 | 0.143 | 1.00/7 | 0.091 | 0.333 |
| top_naive | 6 | 0.143 | 1.00/7 | 0.091 | 0.333 |
| uniform_expansion | 6 | 0.143 | 1.00/7 | 0.045 | 0.167 |
| uniform_time | 6 | 0.143 | 1.00/7 | 0.000 | 0.000 |

### Budget Ratio 0.10

Best event recall: 0.857 by temporal_nms_naive.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_naive | 11 | 0.857 | 6.00/7 | 0.182 | 0.364 |
| temporal_nms_ensemble | 11 | 0.714 | 5.00/7 | 0.182 | 0.364 |
| temporal_nms_count | 11 | 0.714 | 5.00/7 | 0.136 | 0.273 |
| top_kinematic | 11 | 0.714 | 5.00/7 | 0.045 | 0.091 |
| ensemble_all_proxy | 11 | 0.571 | 4.00/7 | 0.318 | 0.636 |
| ensemble_count_naive | 11 | 0.571 | 4.00/7 | 0.227 | 0.455 |
| top_naive | 11 | 0.571 | 4.00/7 | 0.136 | 0.273 |
| uniform_time | 11 | 0.571 | 4.00/7 | 0.091 | 0.182 |
| random | 11 | 0.514 ± 0.134 | 3.60/7 | 0.107 | 0.214 |
| proxy_then_expansion_ensemble | 11 | 0.286 | 2.00/7 | 0.227 | 0.455 |
| proxy_then_expansion_naive | 11 | 0.286 | 2.00/7 | 0.182 | 0.364 |
| top_count | 11 | 0.143 | 1.00/7 | 0.409 | 0.818 |
| proxy_then_expansion_count | 11 | 0.143 | 1.00/7 | 0.364 | 0.727 |
| uniform_expansion | 11 | 0.143 | 1.00/7 | 0.273 | 0.545 |

### Budget Ratio 0.15

Best event recall: 0.857 by temporal_nms_count, temporal_nms_ensemble, temporal_nms_naive, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_naive | 16 | 0.857 | 6.00/7 | 0.227 | 0.312 |
| temporal_nms_count | 16 | 0.857 | 6.00/7 | 0.182 | 0.250 |
| temporal_nms_ensemble | 16 | 0.857 | 6.00/7 | 0.182 | 0.250 |
| uniform_time | 16 | 0.857 | 6.00/7 | 0.091 | 0.125 |
| top_kinematic | 16 | 0.714 | 5.00/7 | 0.091 | 0.125 |
| random | 16 | 0.614 ± 0.174 | 4.30/7 | 0.143 | 0.197 |
| ensemble_count_naive | 16 | 0.571 | 4.00/7 | 0.364 | 0.500 |
| ensemble_all_proxy | 16 | 0.571 | 4.00/7 | 0.318 | 0.438 |
| proxy_then_expansion_ensemble | 16 | 0.571 | 4.00/7 | 0.318 | 0.438 |
| proxy_then_expansion_naive | 16 | 0.571 | 4.00/7 | 0.227 | 0.312 |
| top_naive | 16 | 0.571 | 4.00/7 | 0.182 | 0.250 |
| proxy_then_expansion_count | 16 | 0.143 | 1.00/7 | 0.500 | 0.688 |
| top_count | 16 | 0.143 | 1.00/7 | 0.500 | 0.688 |
| uniform_expansion | 16 | 0.143 | 1.00/7 | 0.500 | 0.688 |

### Budget Ratio 0.20

Best event recall: 1.000 by uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| uniform_time | 21 | 1.000 | 7.00/7 | 0.227 | 0.238 |
| temporal_nms_count | 21 | 0.857 | 6.00/7 | 0.227 | 0.238 |
| temporal_nms_ensemble | 21 | 0.857 | 6.00/7 | 0.227 | 0.238 |
| temporal_nms_naive | 21 | 0.857 | 6.00/7 | 0.227 | 0.238 |
| top_kinematic | 21 | 0.857 | 6.00/7 | 0.227 | 0.238 |
| random | 21 | 0.771 ± 0.170 | 5.40/7 | 0.207 | 0.217 |
| ensemble_count_naive | 21 | 0.714 | 5.00/7 | 0.455 | 0.476 |
| top_naive | 21 | 0.714 | 5.00/7 | 0.318 | 0.333 |
| proxy_then_expansion_naive | 21 | 0.714 | 5.00/7 | 0.273 | 0.286 |
| ensemble_all_proxy | 21 | 0.571 | 4.00/7 | 0.455 | 0.476 |
| proxy_then_expansion_ensemble | 21 | 0.571 | 4.00/7 | 0.455 | 0.476 |
| proxy_then_expansion_count | 21 | 0.143 | 1.00/7 | 0.500 | 0.524 |
| top_count | 21 | 0.143 | 1.00/7 | 0.500 | 0.524 |
| uniform_expansion | 21 | 0.143 | 1.00/7 | 0.500 | 0.524 |

### Budget Ratio 0.30

Best event recall: 1.000 by uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| uniform_time | 31 | 1.000 | 7.00/7 | 0.227 | 0.161 |
| random | 31 | 0.893 ± 0.102 | 6.25/7 | 0.298 | 0.211 |
| temporal_nms_count | 31 | 0.857 | 6.00/7 | 0.591 | 0.419 |
| temporal_nms_ensemble | 31 | 0.857 | 6.00/7 | 0.455 | 0.323 |
| top_naive | 31 | 0.857 | 6.00/7 | 0.409 | 0.290 |
| temporal_nms_naive | 31 | 0.857 | 6.00/7 | 0.364 | 0.258 |
| top_kinematic | 31 | 0.857 | 6.00/7 | 0.364 | 0.258 |
| proxy_then_expansion_ensemble | 31 | 0.714 | 5.00/7 | 0.682 | 0.484 |
| ensemble_count_naive | 31 | 0.714 | 5.00/7 | 0.636 | 0.452 |
| proxy_then_expansion_naive | 31 | 0.714 | 5.00/7 | 0.591 | 0.419 |
| ensemble_all_proxy | 31 | 0.571 | 4.00/7 | 0.545 | 0.387 |
| top_count | 31 | 0.429 | 3.00/7 | 0.682 | 0.484 |
| proxy_then_expansion_count | 31 | 0.429 | 3.00/7 | 0.636 | 0.452 |
| uniform_expansion | 31 | 0.143 | 1.00/7 | 0.500 | 0.355 |

### Budget Ratio 0.50

Best event recall: 1.000 by random, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| uniform_time | 51 | 1.000 | 7.00/7 | 0.545 | 0.235 |
| random | 51 | 1.000 ± 0.000 | 7.00/7 | 0.493 | 0.213 |
| top_kinematic | 51 | 1.000 | 7.00/7 | 0.455 | 0.196 |
| temporal_nms_count | 51 | 0.857 | 6.00/7 | 0.909 | 0.392 |
| proxy_then_expansion_naive | 51 | 0.857 | 6.00/7 | 0.818 | 0.353 |
| temporal_nms_ensemble | 51 | 0.857 | 6.00/7 | 0.818 | 0.353 |
| top_naive | 51 | 0.857 | 6.00/7 | 0.773 | 0.333 |
| temporal_nms_naive | 51 | 0.857 | 6.00/7 | 0.727 | 0.314 |
| ensemble_count_naive | 51 | 0.714 | 5.00/7 | 0.909 | 0.392 |
| proxy_then_expansion_count | 51 | 0.714 | 5.00/7 | 0.909 | 0.392 |
| proxy_then_expansion_ensemble | 51 | 0.714 | 5.00/7 | 0.909 | 0.392 |
| top_count | 51 | 0.714 | 5.00/7 | 0.909 | 0.392 |
| ensemble_all_proxy | 51 | 0.714 | 5.00/7 | 0.818 | 0.353 |
| uniform_expansion | 51 | 0.571 | 4.00/7 | 0.773 | 0.333 |


## Key Diagnostics


## Failure Conditions

- If VLM labels are missing, this script writes `vlm_labels_template.csv` and `BLOCKED_missing_vlm_labels.md` instead of fabricating results.
- If VLM-positive clips are fewer than 5, treat curves as unstable.
- These results are pseudo-oracle recovery results, not validated human-GT danger detection results.
