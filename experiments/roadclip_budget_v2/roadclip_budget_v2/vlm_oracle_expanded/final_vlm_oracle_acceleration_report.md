# Final VLM-as-Oracle Acceleration Report

Evaluation target: approximating the full conservative Qwen3-VL scan. These labels are VLM pseudo-oracle labels, not human ground truth.

## Dataset

- clips: 1000
- conservative VLM positives: 61 / 1000 = 0.061
- positive events: 32
- average positive run length: 1.906
- event_merge_gap_sec: 4.0

## Learned Proxy

- segment-level GroupKFold learned proxy completed: folds=5/5, features=13
- Learned scores use segment-level GroupKFold out-of-fold predictions, so clips from the same segment do not appear in both train and test folds.

## Low-Budget Results

- best 5%-20% clip recall method: `top_learned_logreg` = 0.504
- random 5%-20% clip recall: 0.130
- best clip uplift over random: 3.88x
- best 5%-20% event recall method: `top_learned_logreg` = 0.500
- random 5%-20% event recall: 0.207
- best event uplift over random: 2.42x

## Budget Curve

| method | budget | recall | precision | F1 | event_recall | calls_saved |
|---|---:|---:|---:|---:|---:|---:|
| adaptive_count_nms_expand | 0.02 | 0.115 | 0.350 | 0.173 | 0.062 | 0.980 |
| proxy_then_expansion_count | 0.02 | 0.098 | 0.300 | 0.148 | 0.031 | 0.980 |
| random | 0.02 | 0.028 | 0.085 | 0.042 | 0.050 | 0.980 |
| temporal_nms_count | 0.02 | 0.066 | 0.200 | 0.099 | 0.062 | 0.980 |
| top_count | 0.02 | 0.115 | 0.350 | 0.173 | 0.062 | 0.980 |
| top_learned_logreg | 0.02 | 0.131 | 0.400 | 0.198 | 0.188 | 0.980 |
| top_learned_rf | 0.02 | 0.115 | 0.350 | 0.173 | 0.156 | 0.980 |
| top_naive | 0.02 | 0.082 | 0.250 | 0.123 | 0.125 | 0.980 |
| uniform_time | 0.02 | 0.098 | 0.300 | 0.148 | 0.031 | 0.980 |
| adaptive_count_nms_expand | 0.05 | 0.131 | 0.160 | 0.144 | 0.094 | 0.950 |
| proxy_then_expansion_count | 0.05 | 0.131 | 0.160 | 0.144 | 0.094 | 0.950 |
| random | 0.05 | 0.054 | 0.066 | 0.059 | 0.097 | 0.950 |
| temporal_nms_count | 0.05 | 0.230 | 0.280 | 0.252 | 0.219 | 0.950 |
| top_count | 0.05 | 0.180 | 0.220 | 0.198 | 0.125 | 0.950 |
| top_learned_logreg | 0.05 | 0.328 | 0.400 | 0.360 | 0.344 | 0.950 |
| top_learned_rf | 0.05 | 0.180 | 0.220 | 0.198 | 0.250 | 0.950 |
| top_naive | 0.05 | 0.131 | 0.160 | 0.144 | 0.219 | 0.950 |
| uniform_time | 0.05 | 0.131 | 0.160 | 0.144 | 0.094 | 0.950 |
| adaptive_count_nms_expand | 0.10 | 0.475 | 0.290 | 0.360 | 0.312 | 0.900 |
| proxy_then_expansion_count | 0.10 | 0.492 | 0.300 | 0.373 | 0.344 | 0.900 |
| random | 0.10 | 0.108 | 0.066 | 0.082 | 0.178 | 0.900 |
| temporal_nms_count | 0.10 | 0.328 | 0.200 | 0.248 | 0.375 | 0.900 |
| top_count | 0.10 | 0.475 | 0.290 | 0.360 | 0.312 | 0.900 |
| top_learned_logreg | 0.10 | 0.492 | 0.300 | 0.373 | 0.500 | 0.900 |
| top_learned_rf | 0.10 | 0.361 | 0.220 | 0.273 | 0.438 | 0.900 |
| top_naive | 0.10 | 0.197 | 0.120 | 0.149 | 0.344 | 0.900 |
| uniform_time | 0.10 | 0.131 | 0.080 | 0.099 | 0.094 | 0.900 |
| adaptive_count_nms_expand | 0.15 | 0.607 | 0.247 | 0.351 | 0.438 | 0.850 |
| proxy_then_expansion_count | 0.15 | 0.557 | 0.227 | 0.322 | 0.438 | 0.850 |
| random | 0.15 | 0.154 | 0.063 | 0.089 | 0.242 | 0.850 |
| temporal_nms_count | 0.15 | 0.410 | 0.167 | 0.237 | 0.500 | 0.850 |
| top_count | 0.15 | 0.590 | 0.240 | 0.341 | 0.438 | 0.850 |
| top_learned_logreg | 0.15 | 0.557 | 0.227 | 0.322 | 0.562 | 0.850 |
| top_learned_rf | 0.15 | 0.541 | 0.220 | 0.313 | 0.594 | 0.850 |
| top_naive | 0.15 | 0.213 | 0.087 | 0.123 | 0.344 | 0.850 |
| uniform_time | 0.15 | 0.164 | 0.067 | 0.095 | 0.125 | 0.850 |
| adaptive_count_nms_expand | 0.20 | 0.754 | 0.230 | 0.352 | 0.594 | 0.800 |
| proxy_then_expansion_count | 0.20 | 0.689 | 0.210 | 0.322 | 0.594 | 0.800 |
| random | 0.20 | 0.203 | 0.062 | 0.095 | 0.309 | 0.800 |
| temporal_nms_count | 0.20 | 0.426 | 0.130 | 0.199 | 0.531 | 0.800 |
| top_count | 0.20 | 0.738 | 0.225 | 0.345 | 0.625 | 0.800 |
| top_learned_logreg | 0.20 | 0.639 | 0.195 | 0.299 | 0.594 | 0.800 |
| top_learned_rf | 0.20 | 0.656 | 0.200 | 0.307 | 0.688 | 0.800 |
| top_naive | 0.20 | 0.279 | 0.085 | 0.130 | 0.469 | 0.800 |
| uniform_time | 0.20 | 0.180 | 0.055 | 0.084 | 0.156 | 0.800 |
| adaptive_count_nms_expand | 0.30 | 0.852 | 0.173 | 0.288 | 0.750 | 0.700 |
| proxy_then_expansion_count | 0.30 | 0.902 | 0.183 | 0.305 | 0.812 | 0.700 |
| random | 0.30 | 0.306 | 0.062 | 0.103 | 0.423 | 0.700 |
| temporal_nms_count | 0.30 | 0.459 | 0.093 | 0.155 | 0.594 | 0.700 |
| top_count | 0.30 | 0.836 | 0.170 | 0.283 | 0.750 | 0.700 |
| top_learned_logreg | 0.30 | 0.787 | 0.160 | 0.266 | 0.750 | 0.700 |
| top_learned_rf | 0.30 | 0.820 | 0.167 | 0.277 | 0.781 | 0.700 |
| top_naive | 0.30 | 0.459 | 0.093 | 0.155 | 0.562 | 0.700 |
| uniform_time | 0.30 | 0.393 | 0.080 | 0.133 | 0.344 | 0.700 |
| adaptive_count_nms_expand | 0.50 | 0.951 | 0.116 | 0.207 | 0.906 | 0.500 |
| proxy_then_expansion_count | 0.50 | 0.934 | 0.114 | 0.203 | 0.875 | 0.500 |
| random | 0.50 | 0.516 | 0.063 | 0.112 | 0.620 | 0.500 |
| temporal_nms_count | 0.50 | 0.705 | 0.086 | 0.153 | 0.688 | 0.500 |
| top_count | 0.50 | 0.951 | 0.116 | 0.207 | 0.906 | 0.500 |
| top_learned_logreg | 0.50 | 0.918 | 0.112 | 0.200 | 0.844 | 0.500 |
| top_learned_rf | 0.50 | 0.869 | 0.106 | 0.189 | 0.812 | 0.500 |
| top_naive | 0.50 | 0.721 | 0.088 | 0.157 | 0.781 | 0.500 |
| uniform_time | 0.50 | 0.623 | 0.076 | 0.135 | 0.531 | 0.500 |

## Target-Recall Cost Saving

| method | target_type | target_recall | mean_calls | budget_ratio | calls_saved_fraction |
|---|---|---:|---:|---:|---:|
| proxy_then_expansion_count | clip | 0.50 | 105.0 | 0.105 | 0.895 |
| top_learned_rf | clip | 0.50 | 124.0 | 0.124 | 0.876 |
| top_learned_logreg | clip | 0.50 | 126.0 | 0.126 | 0.874 |
| top_count | clip | 0.50 | 129.0 | 0.129 | 0.871 |
| adaptive_count_nms_expand | clip | 0.50 | 135.0 | 0.135 | 0.865 |
| uniform_time | clip | 0.50 | 311.0 | 0.311 | 0.689 |
| top_naive | clip | 0.50 | 320.0 | 0.320 | 0.680 |
| temporal_nms_count | clip | 0.50 | 454.0 | 0.454 | 0.546 |
| random | clip | 0.50 | 483.4 | 0.483 | 0.517 |
| adaptive_count_nms_expand | clip | 0.60 | 147.0 | 0.147 | 0.853 |
| top_count | clip | 0.60 | 151.0 | 0.151 | 0.849 |
| top_learned_rf | clip | 0.60 | 173.0 | 0.173 | 0.827 |
| top_learned_logreg | clip | 0.60 | 182.0 | 0.182 | 0.818 |
| proxy_then_expansion_count | clip | 0.60 | 185.0 | 0.185 | 0.815 |
| top_naive | clip | 0.60 | 391.0 | 0.391 | 0.609 |
| uniform_time | clip | 0.60 | 443.0 | 0.443 | 0.557 |
| temporal_nms_count | clip | 0.60 | 473.0 | 0.473 | 0.527 |
| random | clip | 0.60 | 577.5 | 0.578 | 0.422 |
| top_count | clip | 0.70 | 176.0 | 0.176 | 0.824 |
| adaptive_count_nms_expand | clip | 0.70 | 184.0 | 0.184 | 0.816 |
| proxy_then_expansion_count | clip | 0.70 | 207.0 | 0.207 | 0.793 |
| top_learned_rf | clip | 0.70 | 218.0 | 0.218 | 0.782 |
| top_learned_logreg | clip | 0.70 | 229.0 | 0.229 | 0.771 |
| top_naive | clip | 0.70 | 448.0 | 0.448 | 0.552 |
| temporal_nms_count | clip | 0.70 | 484.0 | 0.484 | 0.516 |
| uniform_time | clip | 0.70 | 679.0 | 0.679 | 0.321 |
| random | clip | 0.70 | 685.0 | 0.685 | 0.315 |
| top_count | clip | 0.80 | 227.0 | 0.227 | 0.773 |
| proxy_then_expansion_count | clip | 0.80 | 232.0 | 0.232 | 0.768 |
| adaptive_count_nms_expand | clip | 0.80 | 233.0 | 0.233 | 0.767 |
| top_learned_rf | clip | 0.80 | 264.0 | 0.264 | 0.736 |
| top_learned_logreg | clip | 0.80 | 327.0 | 0.327 | 0.673 |
| temporal_nms_count | clip | 0.80 | 525.0 | 0.525 | 0.475 |
| top_naive | clip | 0.80 | 644.0 | 0.644 | 0.356 |
| uniform_time | clip | 0.80 | 712.0 | 0.712 | 0.288 |
| random | clip | 0.80 | 790.1 | 0.790 | 0.210 |
| top_learned_logreg | event | 0.50 | 94.0 | 0.094 | 0.906 |
| top_learned_rf | event | 0.50 | 103.0 | 0.103 | 0.897 |
| temporal_nms_count | event | 0.50 | 127.0 | 0.127 | 0.873 |
| top_count | event | 0.50 | 167.0 | 0.167 | 0.833 |
| adaptive_count_nms_expand | event | 0.50 | 177.0 | 0.177 | 0.823 |
| proxy_then_expansion_count | event | 0.50 | 180.0 | 0.180 | 0.820 |
| top_naive | event | 0.50 | 206.0 | 0.206 | 0.794 |
| random | event | 0.50 | 351.0 | 0.351 | 0.649 |
| uniform_time | event | 0.50 | 443.0 | 0.443 | 0.557 |
| top_learned_rf | event | 0.60 | 168.0 | 0.168 | 0.832 |
| top_count | event | 0.60 | 187.0 | 0.187 | 0.813 |
| adaptive_count_nms_expand | event | 0.60 | 202.0 | 0.202 | 0.798 |
| proxy_then_expansion_count | event | 0.60 | 207.0 | 0.207 | 0.793 |
| top_learned_logreg | event | 0.60 | 213.0 | 0.213 | 0.787 |
| top_naive | event | 0.60 | 383.0 | 0.383 | 0.617 |
| temporal_nms_count | event | 0.60 | 460.0 | 0.460 | 0.540 |
| random | event | 0.60 | 482.9 | 0.483 | 0.517 |
| uniform_time | event | 0.60 | 677.0 | 0.677 | 0.323 |
| top_learned_rf | event | 0.70 | 214.0 | 0.214 | 0.786 |
| top_count | event | 0.70 | 227.0 | 0.227 | 0.773 |
| proxy_then_expansion_count | event | 0.70 | 229.0 | 0.229 | 0.771 |
| adaptive_count_nms_expand | event | 0.70 | 247.0 | 0.247 | 0.753 |
| top_learned_logreg | event | 0.70 | 249.0 | 0.249 | 0.751 |
| top_naive | event | 0.70 | 394.0 | 0.394 | 0.606 |
| temporal_nms_count | event | 0.70 | 504.0 | 0.504 | 0.496 |
| random | event | 0.70 | 594.2 | 0.594 | 0.406 |
| uniform_time | event | 0.70 | 712.0 | 0.712 | 0.288 |
| proxy_then_expansion_count | event | 0.80 | 273.0 | 0.273 | 0.727 |
| top_learned_rf | event | 0.80 | 389.0 | 0.389 | 0.611 |
| top_learned_logreg | event | 0.80 | 416.0 | 0.416 | 0.584 |
| top_count | event | 0.80 | 440.0 | 0.440 | 0.560 |
| adaptive_count_nms_expand | event | 0.80 | 443.0 | 0.443 | 0.557 |
| temporal_nms_count | event | 0.80 | 545.0 | 0.545 | 0.455 |
| top_naive | event | 0.80 | 576.0 | 0.576 | 0.424 |
| random | event | 0.80 | 705.5 | 0.705 | 0.295 |
| uniform_time | event | 0.80 | 893.0 | 0.893 | 0.107 |

## Interpretation

- `top_count` tests pure proxy ranking.
- `temporal_nms_count` tests proxy ranking with time diversity.
- `proxy_then_expansion_count` tests dense local recovery around proxy anchors.
- `adaptive_count_nms_expand` first calls count+NMS anchors, then spends local expansion calls only after an anchor is VLM-positive.
- Learned proxy results are feasibility checks using existing proxy/track features, not a separate anomaly model.
- cheapest 0.80 event recall method: `proxy_then_expansion_count` with 273.0/1000 calls, saving 0.727.

## Decision

- This benchmark supports or rejects acceleration only relative to the full conservative VLM scan.
- It does not prove true traffic-risk accuracy without human GT.
- If a method substantially beats random in target-recall cost, it is a candidate budget allocation strategy for larger VLM-as-oracle experiments.
