# VLM32B Pseudo-GT Budget Simulation

This report treats the available VLM32B scan as pseudo-GT / pseudo-oracle. It does not measure true real-world danger detection accuracy.

## Data Overview

- number of clips in proxy_scores: 102
- budget ratios: 0.05, 0.10, 0.15, 0.20, 0.30, 0.50
- methods evaluated: random, uniform_time, top_count, top_naive, top_kinematic, ensemble_count_naive, ensemble_all_proxy, temporal_nms_count, temporal_nms_naive, temporal_nms_ensemble, uniform_expansion, proxy_then_expansion
- event_merge_gap_sec: 4.000
- broad label available: True
- strict label available: False (no usable risk_level rank or affected_ego/ego_related field in current raw 32B source)
- high-confidence label available: True (explicit yes/no relevance or confidence field available)

## Variant Overview

| variant | valid clips | positives | positive rate | events |
|---|---:|---:|---:|---:|
| broad | 98 | 62 | 0.633 | 5 |
| high_confidence | 98 | 62 | 0.633 | 5 |

## broad Label: Clip-Level Results

### Budget Ratio 0.05

Best clip recall: 0.081 by top_count, uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 5 | 0.081 | 1.000 | 0.149 | 5.00 | 0.200 | 1.00/5 |
| uniform_expansion | 5 | 0.081 | 1.000 | 0.149 | 5.00 | 0.200 | 1.00/5 |
| ensemble_all_proxy | 5 | 0.065 | 0.800 | 0.119 | 4.00 | 0.600 | 3.00/5 |
| ensemble_count_naive | 5 | 0.065 | 0.800 | 0.119 | 4.00 | 0.600 | 3.00/5 |
| temporal_nms_count | 5 | 0.065 | 0.800 | 0.119 | 4.00 | 0.400 | 2.00/5 |
| temporal_nms_ensemble | 5 | 0.065 | 0.800 | 0.119 | 4.00 | 0.600 | 3.00/5 |
| temporal_nms_naive | 5 | 0.065 | 0.800 | 0.119 | 4.00 | 0.600 | 3.00/5 |
| random | 5 | 0.049 ± 0.018 | 0.610 ± 0.229 | 0.091 ± 0.034 | 3.05 | 0.610 | 3.05/5 |
| proxy_then_expansion | 5 | 0.048 | 0.600 | 0.090 | 3.00 | 0.600 | 3.00/5 |
| top_naive | 5 | 0.048 | 0.600 | 0.090 | 3.00 | 0.600 | 3.00/5 |
| uniform_time | 5 | 0.048 | 0.600 | 0.090 | 3.00 | 0.400 | 2.00/5 |
| top_kinematic | 5 | 0.032 | 0.400 | 0.060 | 2.00 | 0.800 | 4.00/5 |

### Budget Ratio 0.10

Best clip recall: 0.161 by top_count, uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 10 | 0.161 | 1.000 | 0.278 | 10.00 | 0.200 | 1.00/5 |
| uniform_expansion | 10 | 0.161 | 1.000 | 0.278 | 10.00 | 0.200 | 1.00/5 |
| ensemble_all_proxy | 10 | 0.145 | 0.900 | 0.250 | 9.00 | 0.600 | 3.00/5 |
| ensemble_count_naive | 10 | 0.145 | 0.900 | 0.250 | 9.00 | 0.600 | 3.00/5 |
| temporal_nms_count | 10 | 0.145 | 0.900 | 0.250 | 9.00 | 0.600 | 3.00/5 |
| temporal_nms_ensemble | 10 | 0.145 | 0.900 | 0.250 | 9.00 | 0.600 | 3.00/5 |
| temporal_nms_naive | 10 | 0.129 | 0.800 | 0.222 | 8.00 | 0.800 | 4.00/5 |
| proxy_then_expansion | 10 | 0.113 | 0.700 | 0.194 | 7.00 | 0.800 | 4.00/5 |
| top_naive | 10 | 0.113 | 0.700 | 0.194 | 7.00 | 0.600 | 3.00/5 |
| random | 10 | 0.099 ± 0.026 | 0.615 ± 0.163 | 0.171 ± 0.045 | 6.15 | 0.740 | 3.70/5 |
| uniform_time | 10 | 0.065 | 0.400 | 0.111 | 4.00 | 0.800 | 4.00/5 |
| top_kinematic | 10 | 0.048 | 0.300 | 0.083 | 3.00 | 1.000 | 5.00/5 |

### Budget Ratio 0.15

Best clip recall: 0.242 by top_count, uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 15 | 0.242 | 1.000 | 0.390 | 15.00 | 0.200 | 1.00/5 |
| uniform_expansion | 15 | 0.242 | 1.000 | 0.390 | 15.00 | 0.200 | 1.00/5 |
| ensemble_count_naive | 15 | 0.226 | 0.933 | 0.364 | 14.00 | 0.600 | 3.00/5 |
| ensemble_all_proxy | 15 | 0.194 | 0.800 | 0.312 | 12.00 | 0.600 | 3.00/5 |
| proxy_then_expansion | 15 | 0.194 | 0.800 | 0.312 | 12.00 | 0.800 | 4.00/5 |
| temporal_nms_count | 15 | 0.194 | 0.800 | 0.312 | 12.00 | 0.800 | 4.00/5 |
| top_naive | 15 | 0.194 | 0.800 | 0.312 | 12.00 | 0.600 | 3.00/5 |
| temporal_nms_ensemble | 15 | 0.161 | 0.667 | 0.260 | 10.00 | 0.800 | 4.00/5 |
| temporal_nms_naive | 15 | 0.161 | 0.667 | 0.260 | 10.00 | 0.800 | 4.00/5 |
| uniform_time | 15 | 0.161 | 0.667 | 0.260 | 10.00 | 0.800 | 4.00/5 |
| random | 15 | 0.148 ± 0.031 | 0.610 ± 0.127 | 0.238 ± 0.049 | 9.15 | 0.820 | 4.10/5 |
| top_kinematic | 15 | 0.081 | 0.333 | 0.130 | 5.00 | 1.000 | 5.00/5 |

### Budget Ratio 0.20

Best clip recall: 0.323 by uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| uniform_expansion | 20 | 0.323 | 1.000 | 0.488 | 20.00 | 0.200 | 1.00/5 |
| ensemble_count_naive | 20 | 0.306 | 0.950 | 0.463 | 19.00 | 0.600 | 3.00/5 |
| top_count | 20 | 0.306 | 0.950 | 0.463 | 19.00 | 0.400 | 2.00/5 |
| ensemble_all_proxy | 20 | 0.274 | 0.850 | 0.415 | 17.00 | 0.600 | 3.00/5 |
| top_naive | 20 | 0.274 | 0.850 | 0.415 | 17.00 | 0.600 | 3.00/5 |
| proxy_then_expansion | 20 | 0.258 | 0.800 | 0.390 | 16.00 | 0.800 | 4.00/5 |
| temporal_nms_count | 20 | 0.226 | 0.700 | 0.341 | 14.00 | 0.800 | 4.00/5 |
| temporal_nms_ensemble | 20 | 0.226 | 0.700 | 0.341 | 14.00 | 0.800 | 4.00/5 |
| temporal_nms_naive | 20 | 0.210 | 0.650 | 0.317 | 13.00 | 0.800 | 4.00/5 |
| random | 20 | 0.197 ± 0.039 | 0.610 ± 0.122 | 0.298 ± 0.060 | 12.20 | 0.850 | 4.25/5 |
| uniform_time | 20 | 0.194 | 0.600 | 0.293 | 12.00 | 1.000 | 5.00/5 |
| top_kinematic | 20 | 0.161 | 0.500 | 0.244 | 10.00 | 1.000 | 5.00/5 |

### Budget Ratio 0.30

Best clip recall: 0.468 by ensemble_count_naive, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_count_naive | 30 | 0.468 | 0.967 | 0.630 | 29.00 | 0.600 | 3.00/5 |
| top_count | 30 | 0.468 | 0.967 | 0.630 | 29.00 | 0.400 | 2.00/5 |
| uniform_expansion | 30 | 0.452 | 0.933 | 0.609 | 28.00 | 0.400 | 2.00/5 |
| top_naive | 30 | 0.435 | 0.900 | 0.587 | 27.00 | 0.800 | 4.00/5 |
| ensemble_all_proxy | 30 | 0.419 | 0.867 | 0.565 | 26.00 | 0.600 | 3.00/5 |
| proxy_then_expansion | 30 | 0.419 | 0.867 | 0.565 | 26.00 | 0.800 | 4.00/5 |
| temporal_nms_count | 30 | 0.387 | 0.800 | 0.522 | 24.00 | 0.800 | 4.00/5 |
| temporal_nms_ensemble | 30 | 0.387 | 0.800 | 0.522 | 24.00 | 0.800 | 4.00/5 |
| temporal_nms_naive | 30 | 0.371 | 0.767 | 0.500 | 23.00 | 0.800 | 4.00/5 |
| random | 30 | 0.302 ± 0.037 | 0.623 ± 0.077 | 0.407 ± 0.050 | 18.70 | 0.940 | 4.70/5 |
| uniform_time | 30 | 0.290 | 0.600 | 0.391 | 18.00 | 1.000 | 5.00/5 |
| top_kinematic | 30 | 0.274 | 0.567 | 0.370 | 17.00 | 1.000 | 5.00/5 |

### Budget Ratio 0.50

Best clip recall: 0.758 by uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| uniform_expansion | 49 | 0.758 | 0.959 | 0.847 | 47.00 | 0.400 | 2.00/5 |
| top_count | 49 | 0.742 | 0.939 | 0.829 | 46.00 | 0.800 | 4.00/5 |
| ensemble_count_naive | 49 | 0.726 | 0.918 | 0.811 | 45.00 | 0.800 | 4.00/5 |
| proxy_then_expansion | 49 | 0.726 | 0.918 | 0.811 | 45.00 | 0.800 | 4.00/5 |
| ensemble_all_proxy | 49 | 0.710 | 0.898 | 0.793 | 44.00 | 0.600 | 3.00/5 |
| top_naive | 49 | 0.694 | 0.878 | 0.775 | 43.00 | 0.800 | 4.00/5 |
| temporal_nms_count | 49 | 0.677 | 0.857 | 0.757 | 42.00 | 1.000 | 5.00/5 |
| temporal_nms_ensemble | 49 | 0.677 | 0.857 | 0.757 | 42.00 | 0.800 | 4.00/5 |
| temporal_nms_naive | 49 | 0.645 | 0.816 | 0.721 | 40.00 | 0.800 | 4.00/5 |
| uniform_time | 49 | 0.500 | 0.633 | 0.559 | 31.00 | 1.000 | 5.00/5 |
| random | 49 | 0.495 ± 0.042 | 0.627 ± 0.053 | 0.553 ± 0.047 | 30.70 | 0.990 | 4.95/5 |
| top_kinematic | 49 | 0.484 | 0.612 | 0.541 | 30.00 | 1.000 | 5.00/5 |


## broad Label: Event-Level Results

### Budget Ratio 0.05

Best event recall: 0.800 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 5 | 0.800 | 4.00/5 | 0.032 | 0.400 |
| random | 5 | 0.610 ± 0.189 | 3.05/5 | 0.049 | 0.610 |
| ensemble_all_proxy | 5 | 0.600 | 3.00/5 | 0.065 | 0.800 |
| ensemble_count_naive | 5 | 0.600 | 3.00/5 | 0.065 | 0.800 |
| temporal_nms_ensemble | 5 | 0.600 | 3.00/5 | 0.065 | 0.800 |
| temporal_nms_naive | 5 | 0.600 | 3.00/5 | 0.065 | 0.800 |
| proxy_then_expansion | 5 | 0.600 | 3.00/5 | 0.048 | 0.600 |
| top_naive | 5 | 0.600 | 3.00/5 | 0.048 | 0.600 |
| temporal_nms_count | 5 | 0.400 | 2.00/5 | 0.065 | 0.800 |
| uniform_time | 5 | 0.400 | 2.00/5 | 0.048 | 0.600 |
| top_count | 5 | 0.200 | 1.00/5 | 0.081 | 1.000 |
| uniform_expansion | 5 | 0.200 | 1.00/5 | 0.081 | 1.000 |

### Budget Ratio 0.10

Best event recall: 1.000 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 10 | 1.000 | 5.00/5 | 0.048 | 0.300 |
| temporal_nms_naive | 10 | 0.800 | 4.00/5 | 0.129 | 0.800 |
| proxy_then_expansion | 10 | 0.800 | 4.00/5 | 0.113 | 0.700 |
| uniform_time | 10 | 0.800 | 4.00/5 | 0.065 | 0.400 |
| random | 10 | 0.740 ± 0.173 | 3.70/5 | 0.099 | 0.615 |
| ensemble_all_proxy | 10 | 0.600 | 3.00/5 | 0.145 | 0.900 |
| ensemble_count_naive | 10 | 0.600 | 3.00/5 | 0.145 | 0.900 |
| temporal_nms_count | 10 | 0.600 | 3.00/5 | 0.145 | 0.900 |
| temporal_nms_ensemble | 10 | 0.600 | 3.00/5 | 0.145 | 0.900 |
| top_naive | 10 | 0.600 | 3.00/5 | 0.113 | 0.700 |
| top_count | 10 | 0.200 | 1.00/5 | 0.161 | 1.000 |
| uniform_expansion | 10 | 0.200 | 1.00/5 | 0.161 | 1.000 |

### Budget Ratio 0.15

Best event recall: 1.000 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 15 | 1.000 | 5.00/5 | 0.081 | 0.333 |
| random | 15 | 0.820 ± 0.182 | 4.10/5 | 0.148 | 0.610 |
| proxy_then_expansion | 15 | 0.800 | 4.00/5 | 0.194 | 0.800 |
| temporal_nms_count | 15 | 0.800 | 4.00/5 | 0.194 | 0.800 |
| temporal_nms_ensemble | 15 | 0.800 | 4.00/5 | 0.161 | 0.667 |
| temporal_nms_naive | 15 | 0.800 | 4.00/5 | 0.161 | 0.667 |
| uniform_time | 15 | 0.800 | 4.00/5 | 0.161 | 0.667 |
| ensemble_count_naive | 15 | 0.600 | 3.00/5 | 0.226 | 0.933 |
| ensemble_all_proxy | 15 | 0.600 | 3.00/5 | 0.194 | 0.800 |
| top_naive | 15 | 0.600 | 3.00/5 | 0.194 | 0.800 |
| top_count | 15 | 0.200 | 1.00/5 | 0.242 | 1.000 |
| uniform_expansion | 15 | 0.200 | 1.00/5 | 0.242 | 1.000 |

### Budget Ratio 0.20

Best event recall: 1.000 by top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| uniform_time | 20 | 1.000 | 5.00/5 | 0.194 | 0.600 |
| top_kinematic | 20 | 1.000 | 5.00/5 | 0.161 | 0.500 |
| random | 20 | 0.850 ± 0.143 | 4.25/5 | 0.197 | 0.610 |
| proxy_then_expansion | 20 | 0.800 | 4.00/5 | 0.258 | 0.800 |
| temporal_nms_count | 20 | 0.800 | 4.00/5 | 0.226 | 0.700 |
| temporal_nms_ensemble | 20 | 0.800 | 4.00/5 | 0.226 | 0.700 |
| temporal_nms_naive | 20 | 0.800 | 4.00/5 | 0.210 | 0.650 |
| ensemble_count_naive | 20 | 0.600 | 3.00/5 | 0.306 | 0.950 |
| ensemble_all_proxy | 20 | 0.600 | 3.00/5 | 0.274 | 0.850 |
| top_naive | 20 | 0.600 | 3.00/5 | 0.274 | 0.850 |
| top_count | 20 | 0.400 | 2.00/5 | 0.306 | 0.950 |
| uniform_expansion | 20 | 0.200 | 1.00/5 | 0.323 | 1.000 |

### Budget Ratio 0.30

Best event recall: 1.000 by top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| uniform_time | 30 | 1.000 | 5.00/5 | 0.290 | 0.600 |
| top_kinematic | 30 | 1.000 | 5.00/5 | 0.274 | 0.567 |
| random | 30 | 0.940 ± 0.094 | 4.70/5 | 0.302 | 0.623 |
| top_naive | 30 | 0.800 | 4.00/5 | 0.435 | 0.900 |
| proxy_then_expansion | 30 | 0.800 | 4.00/5 | 0.419 | 0.867 |
| temporal_nms_count | 30 | 0.800 | 4.00/5 | 0.387 | 0.800 |
| temporal_nms_ensemble | 30 | 0.800 | 4.00/5 | 0.387 | 0.800 |
| temporal_nms_naive | 30 | 0.800 | 4.00/5 | 0.371 | 0.767 |
| ensemble_count_naive | 30 | 0.600 | 3.00/5 | 0.468 | 0.967 |
| ensemble_all_proxy | 30 | 0.600 | 3.00/5 | 0.419 | 0.867 |
| top_count | 30 | 0.400 | 2.00/5 | 0.468 | 0.967 |
| uniform_expansion | 30 | 0.400 | 2.00/5 | 0.452 | 0.933 |

### Budget Ratio 0.50

Best event recall: 1.000 by temporal_nms_count, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 49 | 1.000 | 5.00/5 | 0.677 | 0.857 |
| uniform_time | 49 | 1.000 | 5.00/5 | 0.500 | 0.633 |
| top_kinematic | 49 | 1.000 | 5.00/5 | 0.484 | 0.612 |
| random | 49 | 0.990 ± 0.045 | 4.95/5 | 0.495 | 0.627 |
| top_count | 49 | 0.800 | 4.00/5 | 0.742 | 0.939 |
| ensemble_count_naive | 49 | 0.800 | 4.00/5 | 0.726 | 0.918 |
| proxy_then_expansion | 49 | 0.800 | 4.00/5 | 0.726 | 0.918 |
| top_naive | 49 | 0.800 | 4.00/5 | 0.694 | 0.878 |
| temporal_nms_ensemble | 49 | 0.800 | 4.00/5 | 0.677 | 0.857 |
| temporal_nms_naive | 49 | 0.800 | 4.00/5 | 0.645 | 0.816 |
| ensemble_all_proxy | 49 | 0.600 | 3.00/5 | 0.710 | 0.898 |
| uniform_expansion | 49 | 0.400 | 2.00/5 | 0.758 | 0.959 |


## high_confidence Label: Clip-Level Results

### Budget Ratio 0.05

Best clip recall: 0.081 by top_count, uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 5 | 0.081 | 1.000 | 0.149 | 5.00 | 0.200 | 1.00/5 |
| uniform_expansion | 5 | 0.081 | 1.000 | 0.149 | 5.00 | 0.200 | 1.00/5 |
| ensemble_all_proxy | 5 | 0.065 | 0.800 | 0.119 | 4.00 | 0.600 | 3.00/5 |
| ensemble_count_naive | 5 | 0.065 | 0.800 | 0.119 | 4.00 | 0.600 | 3.00/5 |
| temporal_nms_count | 5 | 0.065 | 0.800 | 0.119 | 4.00 | 0.400 | 2.00/5 |
| temporal_nms_ensemble | 5 | 0.065 | 0.800 | 0.119 | 4.00 | 0.600 | 3.00/5 |
| temporal_nms_naive | 5 | 0.065 | 0.800 | 0.119 | 4.00 | 0.600 | 3.00/5 |
| random | 5 | 0.049 ± 0.018 | 0.610 ± 0.229 | 0.091 ± 0.034 | 3.05 | 0.610 | 3.05/5 |
| proxy_then_expansion | 5 | 0.048 | 0.600 | 0.090 | 3.00 | 0.600 | 3.00/5 |
| top_naive | 5 | 0.048 | 0.600 | 0.090 | 3.00 | 0.600 | 3.00/5 |
| uniform_time | 5 | 0.048 | 0.600 | 0.090 | 3.00 | 0.400 | 2.00/5 |
| top_kinematic | 5 | 0.032 | 0.400 | 0.060 | 2.00 | 0.800 | 4.00/5 |

### Budget Ratio 0.10

Best clip recall: 0.161 by top_count, uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 10 | 0.161 | 1.000 | 0.278 | 10.00 | 0.200 | 1.00/5 |
| uniform_expansion | 10 | 0.161 | 1.000 | 0.278 | 10.00 | 0.200 | 1.00/5 |
| ensemble_all_proxy | 10 | 0.145 | 0.900 | 0.250 | 9.00 | 0.600 | 3.00/5 |
| ensemble_count_naive | 10 | 0.145 | 0.900 | 0.250 | 9.00 | 0.600 | 3.00/5 |
| temporal_nms_count | 10 | 0.145 | 0.900 | 0.250 | 9.00 | 0.600 | 3.00/5 |
| temporal_nms_ensemble | 10 | 0.145 | 0.900 | 0.250 | 9.00 | 0.600 | 3.00/5 |
| temporal_nms_naive | 10 | 0.129 | 0.800 | 0.222 | 8.00 | 0.800 | 4.00/5 |
| proxy_then_expansion | 10 | 0.113 | 0.700 | 0.194 | 7.00 | 0.800 | 4.00/5 |
| top_naive | 10 | 0.113 | 0.700 | 0.194 | 7.00 | 0.600 | 3.00/5 |
| random | 10 | 0.099 ± 0.026 | 0.615 ± 0.163 | 0.171 ± 0.045 | 6.15 | 0.740 | 3.70/5 |
| uniform_time | 10 | 0.065 | 0.400 | 0.111 | 4.00 | 0.800 | 4.00/5 |
| top_kinematic | 10 | 0.048 | 0.300 | 0.083 | 3.00 | 1.000 | 5.00/5 |

### Budget Ratio 0.15

Best clip recall: 0.242 by top_count, uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_count | 15 | 0.242 | 1.000 | 0.390 | 15.00 | 0.200 | 1.00/5 |
| uniform_expansion | 15 | 0.242 | 1.000 | 0.390 | 15.00 | 0.200 | 1.00/5 |
| ensemble_count_naive | 15 | 0.226 | 0.933 | 0.364 | 14.00 | 0.600 | 3.00/5 |
| ensemble_all_proxy | 15 | 0.194 | 0.800 | 0.312 | 12.00 | 0.600 | 3.00/5 |
| proxy_then_expansion | 15 | 0.194 | 0.800 | 0.312 | 12.00 | 0.800 | 4.00/5 |
| temporal_nms_count | 15 | 0.194 | 0.800 | 0.312 | 12.00 | 0.800 | 4.00/5 |
| top_naive | 15 | 0.194 | 0.800 | 0.312 | 12.00 | 0.600 | 3.00/5 |
| temporal_nms_ensemble | 15 | 0.161 | 0.667 | 0.260 | 10.00 | 0.800 | 4.00/5 |
| temporal_nms_naive | 15 | 0.161 | 0.667 | 0.260 | 10.00 | 0.800 | 4.00/5 |
| uniform_time | 15 | 0.161 | 0.667 | 0.260 | 10.00 | 0.800 | 4.00/5 |
| random | 15 | 0.148 ± 0.031 | 0.610 ± 0.127 | 0.238 ± 0.049 | 9.15 | 0.820 | 4.10/5 |
| top_kinematic | 15 | 0.081 | 0.333 | 0.130 | 5.00 | 1.000 | 5.00/5 |

### Budget Ratio 0.20

Best clip recall: 0.323 by uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| uniform_expansion | 20 | 0.323 | 1.000 | 0.488 | 20.00 | 0.200 | 1.00/5 |
| ensemble_count_naive | 20 | 0.306 | 0.950 | 0.463 | 19.00 | 0.600 | 3.00/5 |
| top_count | 20 | 0.306 | 0.950 | 0.463 | 19.00 | 0.400 | 2.00/5 |
| ensemble_all_proxy | 20 | 0.274 | 0.850 | 0.415 | 17.00 | 0.600 | 3.00/5 |
| top_naive | 20 | 0.274 | 0.850 | 0.415 | 17.00 | 0.600 | 3.00/5 |
| proxy_then_expansion | 20 | 0.258 | 0.800 | 0.390 | 16.00 | 0.800 | 4.00/5 |
| temporal_nms_count | 20 | 0.226 | 0.700 | 0.341 | 14.00 | 0.800 | 4.00/5 |
| temporal_nms_ensemble | 20 | 0.226 | 0.700 | 0.341 | 14.00 | 0.800 | 4.00/5 |
| temporal_nms_naive | 20 | 0.210 | 0.650 | 0.317 | 13.00 | 0.800 | 4.00/5 |
| random | 20 | 0.197 ± 0.039 | 0.610 ± 0.122 | 0.298 ± 0.060 | 12.20 | 0.850 | 4.25/5 |
| uniform_time | 20 | 0.194 | 0.600 | 0.293 | 12.00 | 1.000 | 5.00/5 |
| top_kinematic | 20 | 0.161 | 0.500 | 0.244 | 10.00 | 1.000 | 5.00/5 |

### Budget Ratio 0.30

Best clip recall: 0.468 by ensemble_count_naive, top_count.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble_count_naive | 30 | 0.468 | 0.967 | 0.630 | 29.00 | 0.600 | 3.00/5 |
| top_count | 30 | 0.468 | 0.967 | 0.630 | 29.00 | 0.400 | 2.00/5 |
| uniform_expansion | 30 | 0.452 | 0.933 | 0.609 | 28.00 | 0.400 | 2.00/5 |
| top_naive | 30 | 0.435 | 0.900 | 0.587 | 27.00 | 0.800 | 4.00/5 |
| ensemble_all_proxy | 30 | 0.419 | 0.867 | 0.565 | 26.00 | 0.600 | 3.00/5 |
| proxy_then_expansion | 30 | 0.419 | 0.867 | 0.565 | 26.00 | 0.800 | 4.00/5 |
| temporal_nms_count | 30 | 0.387 | 0.800 | 0.522 | 24.00 | 0.800 | 4.00/5 |
| temporal_nms_ensemble | 30 | 0.387 | 0.800 | 0.522 | 24.00 | 0.800 | 4.00/5 |
| temporal_nms_naive | 30 | 0.371 | 0.767 | 0.500 | 23.00 | 0.800 | 4.00/5 |
| random | 30 | 0.302 ± 0.037 | 0.623 ± 0.077 | 0.407 ± 0.050 | 18.70 | 0.940 | 4.70/5 |
| uniform_time | 30 | 0.290 | 0.600 | 0.391 | 18.00 | 1.000 | 5.00/5 |
| top_kinematic | 30 | 0.274 | 0.567 | 0.370 | 17.00 | 1.000 | 5.00/5 |

### Budget Ratio 0.50

Best clip recall: 0.758 by uniform_expansion.

| method | budget | clip recall | precision | F1 | positives found | event recall | events hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| uniform_expansion | 49 | 0.758 | 0.959 | 0.847 | 47.00 | 0.400 | 2.00/5 |
| top_count | 49 | 0.742 | 0.939 | 0.829 | 46.00 | 0.800 | 4.00/5 |
| ensemble_count_naive | 49 | 0.726 | 0.918 | 0.811 | 45.00 | 0.800 | 4.00/5 |
| proxy_then_expansion | 49 | 0.726 | 0.918 | 0.811 | 45.00 | 0.800 | 4.00/5 |
| ensemble_all_proxy | 49 | 0.710 | 0.898 | 0.793 | 44.00 | 0.600 | 3.00/5 |
| top_naive | 49 | 0.694 | 0.878 | 0.775 | 43.00 | 0.800 | 4.00/5 |
| temporal_nms_count | 49 | 0.677 | 0.857 | 0.757 | 42.00 | 1.000 | 5.00/5 |
| temporal_nms_ensemble | 49 | 0.677 | 0.857 | 0.757 | 42.00 | 0.800 | 4.00/5 |
| temporal_nms_naive | 49 | 0.645 | 0.816 | 0.721 | 40.00 | 0.800 | 4.00/5 |
| uniform_time | 49 | 0.500 | 0.633 | 0.559 | 31.00 | 1.000 | 5.00/5 |
| random | 49 | 0.495 ± 0.042 | 0.627 ± 0.053 | 0.553 ± 0.047 | 30.70 | 0.990 | 4.95/5 |
| top_kinematic | 49 | 0.484 | 0.612 | 0.541 | 30.00 | 1.000 | 5.00/5 |


## high_confidence Label: Event-Level Results

### Budget Ratio 0.05

Best event recall: 0.800 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 5 | 0.800 | 4.00/5 | 0.032 | 0.400 |
| random | 5 | 0.610 ± 0.189 | 3.05/5 | 0.049 | 0.610 |
| ensemble_all_proxy | 5 | 0.600 | 3.00/5 | 0.065 | 0.800 |
| ensemble_count_naive | 5 | 0.600 | 3.00/5 | 0.065 | 0.800 |
| temporal_nms_ensemble | 5 | 0.600 | 3.00/5 | 0.065 | 0.800 |
| temporal_nms_naive | 5 | 0.600 | 3.00/5 | 0.065 | 0.800 |
| proxy_then_expansion | 5 | 0.600 | 3.00/5 | 0.048 | 0.600 |
| top_naive | 5 | 0.600 | 3.00/5 | 0.048 | 0.600 |
| temporal_nms_count | 5 | 0.400 | 2.00/5 | 0.065 | 0.800 |
| uniform_time | 5 | 0.400 | 2.00/5 | 0.048 | 0.600 |
| top_count | 5 | 0.200 | 1.00/5 | 0.081 | 1.000 |
| uniform_expansion | 5 | 0.200 | 1.00/5 | 0.081 | 1.000 |

### Budget Ratio 0.10

Best event recall: 1.000 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 10 | 1.000 | 5.00/5 | 0.048 | 0.300 |
| temporal_nms_naive | 10 | 0.800 | 4.00/5 | 0.129 | 0.800 |
| proxy_then_expansion | 10 | 0.800 | 4.00/5 | 0.113 | 0.700 |
| uniform_time | 10 | 0.800 | 4.00/5 | 0.065 | 0.400 |
| random | 10 | 0.740 ± 0.173 | 3.70/5 | 0.099 | 0.615 |
| ensemble_all_proxy | 10 | 0.600 | 3.00/5 | 0.145 | 0.900 |
| ensemble_count_naive | 10 | 0.600 | 3.00/5 | 0.145 | 0.900 |
| temporal_nms_count | 10 | 0.600 | 3.00/5 | 0.145 | 0.900 |
| temporal_nms_ensemble | 10 | 0.600 | 3.00/5 | 0.145 | 0.900 |
| top_naive | 10 | 0.600 | 3.00/5 | 0.113 | 0.700 |
| top_count | 10 | 0.200 | 1.00/5 | 0.161 | 1.000 |
| uniform_expansion | 10 | 0.200 | 1.00/5 | 0.161 | 1.000 |

### Budget Ratio 0.15

Best event recall: 1.000 by top_kinematic.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| top_kinematic | 15 | 1.000 | 5.00/5 | 0.081 | 0.333 |
| random | 15 | 0.820 ± 0.182 | 4.10/5 | 0.148 | 0.610 |
| proxy_then_expansion | 15 | 0.800 | 4.00/5 | 0.194 | 0.800 |
| temporal_nms_count | 15 | 0.800 | 4.00/5 | 0.194 | 0.800 |
| temporal_nms_ensemble | 15 | 0.800 | 4.00/5 | 0.161 | 0.667 |
| temporal_nms_naive | 15 | 0.800 | 4.00/5 | 0.161 | 0.667 |
| uniform_time | 15 | 0.800 | 4.00/5 | 0.161 | 0.667 |
| ensemble_count_naive | 15 | 0.600 | 3.00/5 | 0.226 | 0.933 |
| ensemble_all_proxy | 15 | 0.600 | 3.00/5 | 0.194 | 0.800 |
| top_naive | 15 | 0.600 | 3.00/5 | 0.194 | 0.800 |
| top_count | 15 | 0.200 | 1.00/5 | 0.242 | 1.000 |
| uniform_expansion | 15 | 0.200 | 1.00/5 | 0.242 | 1.000 |

### Budget Ratio 0.20

Best event recall: 1.000 by top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| uniform_time | 20 | 1.000 | 5.00/5 | 0.194 | 0.600 |
| top_kinematic | 20 | 1.000 | 5.00/5 | 0.161 | 0.500 |
| random | 20 | 0.850 ± 0.143 | 4.25/5 | 0.197 | 0.610 |
| proxy_then_expansion | 20 | 0.800 | 4.00/5 | 0.258 | 0.800 |
| temporal_nms_count | 20 | 0.800 | 4.00/5 | 0.226 | 0.700 |
| temporal_nms_ensemble | 20 | 0.800 | 4.00/5 | 0.226 | 0.700 |
| temporal_nms_naive | 20 | 0.800 | 4.00/5 | 0.210 | 0.650 |
| ensemble_count_naive | 20 | 0.600 | 3.00/5 | 0.306 | 0.950 |
| ensemble_all_proxy | 20 | 0.600 | 3.00/5 | 0.274 | 0.850 |
| top_naive | 20 | 0.600 | 3.00/5 | 0.274 | 0.850 |
| top_count | 20 | 0.400 | 2.00/5 | 0.306 | 0.950 |
| uniform_expansion | 20 | 0.200 | 1.00/5 | 0.323 | 1.000 |

### Budget Ratio 0.30

Best event recall: 1.000 by top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| uniform_time | 30 | 1.000 | 5.00/5 | 0.290 | 0.600 |
| top_kinematic | 30 | 1.000 | 5.00/5 | 0.274 | 0.567 |
| random | 30 | 0.940 ± 0.094 | 4.70/5 | 0.302 | 0.623 |
| top_naive | 30 | 0.800 | 4.00/5 | 0.435 | 0.900 |
| proxy_then_expansion | 30 | 0.800 | 4.00/5 | 0.419 | 0.867 |
| temporal_nms_count | 30 | 0.800 | 4.00/5 | 0.387 | 0.800 |
| temporal_nms_ensemble | 30 | 0.800 | 4.00/5 | 0.387 | 0.800 |
| temporal_nms_naive | 30 | 0.800 | 4.00/5 | 0.371 | 0.767 |
| ensemble_count_naive | 30 | 0.600 | 3.00/5 | 0.468 | 0.967 |
| ensemble_all_proxy | 30 | 0.600 | 3.00/5 | 0.419 | 0.867 |
| top_count | 30 | 0.400 | 2.00/5 | 0.468 | 0.967 |
| uniform_expansion | 30 | 0.400 | 2.00/5 | 0.452 | 0.933 |

### Budget Ratio 0.50

Best event recall: 1.000 by temporal_nms_count, top_kinematic, uniform_time.

| method | budget | event recall | events hit | clip recall | precision |
|---|---:|---:|---:|---:|---:|
| temporal_nms_count | 49 | 1.000 | 5.00/5 | 0.677 | 0.857 |
| uniform_time | 49 | 1.000 | 5.00/5 | 0.500 | 0.633 |
| top_kinematic | 49 | 1.000 | 5.00/5 | 0.484 | 0.612 |
| random | 49 | 0.990 ± 0.045 | 4.95/5 | 0.495 | 0.627 |
| top_count | 49 | 0.800 | 4.00/5 | 0.742 | 0.939 |
| ensemble_count_naive | 49 | 0.800 | 4.00/5 | 0.726 | 0.918 |
| proxy_then_expansion | 49 | 0.800 | 4.00/5 | 0.726 | 0.918 |
| top_naive | 49 | 0.800 | 4.00/5 | 0.694 | 0.878 |
| temporal_nms_ensemble | 49 | 0.800 | 4.00/5 | 0.677 | 0.857 |
| temporal_nms_naive | 49 | 0.800 | 4.00/5 | 0.645 | 0.816 |
| ensemble_all_proxy | 49 | 0.600 | 3.00/5 | 0.710 | 0.898 |
| uniform_expansion | 49 | 0.400 | 2.00/5 | 0.758 | 0.959 |


## Key Diagnostics

- Broad low-budget best clip recall: `uniform_expansion` at 0.202.
- Broad low-budget best event recall: `top_kinematic` at 0.950.
- Broad high-budget best clip recall: `uniform_expansion` at 0.605.
- Broad high-budget best event recall: `top_kinematic` at 1.000.
- temporal_nms_count vs top_count broad clip recall avg: 0.282 vs 0.333.
- temporal_nms_count vs top_count broad event recall avg: 0.733 vs 0.367.
- uniform_expansion broad clip/event recall avg: 0.336 / 0.267.
- top_kinematic broad clip/event recall avg: 0.180 / 0.967.
- uniform_expansion event recall tracks clip recall closely enough to suggest it is not only harvesting duplicate windows.

## Failure Conditions

- If VLM labels are missing, this script writes `vlm_labels_template.csv` and `BLOCKED_missing_vlm_labels.md` instead of fabricating results.
- If VLM-positive clips are fewer than 5, treat curves as unstable.
- These results are pseudo-oracle recovery results, not validated human-GT danger detection results.
