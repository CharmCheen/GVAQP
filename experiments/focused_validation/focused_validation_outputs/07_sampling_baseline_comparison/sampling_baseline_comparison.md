# Sampling Baseline Comparison

All metrics are relative to the full conservative VLM pseudo-oracle, not human ground truth.

- labels_csv: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv`
- proxy_csv: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores_with_learned.csv`
- learned RF score field: `score_learned_rf`
- skipped methods: `[]`
- event conversion: gap_threshold_seconds=3, iou_threshold=0.3

## 20% Budget Ranking
| method | mean_oracle_event_recall | mean_oracle_clip_recall | mean_event_precision | mean_event_iou | num_trials |
| --- | --- | --- | --- | --- | --- |
| oracle_positive_first | 1.000 | 1.000 | 1.000 | 1.000 | 1 |
| top_learned_rf | 0.655 | 0.656 | 0.864 | 0.919 | 1 |
| segment_balanced_top_learned_rf | 0.621 | 0.590 | 0.857 | 0.901 | 1 |
| top_count | 0.586 | 0.738 | 1.000 | 0.974 | 1 |
| temporal_nms_count | 0.517 | 0.426 | 0.938 | 0.807 | 1 |
| segment_balanced_top_count | 0.414 | 0.607 | 1.000 | 0.963 | 1 |
| segment_equal_random | 0.296 | 0.286 | 0.922 | 0.963 | 100 |
| uniform_time | 0.276 | 0.230 | 0.571 | 0.868 | 1 |
| segment_length_random | 0.250 | 0.212 | 0.663 | 0.777 | 100 |
| random | 0.243 | 0.206 | 0.657 | 0.782 | 100 |
| shuffled_count | 0.227 | 0.195 | 0.642 | 0.798 | 100 |
| shuffled_learned_rf | 0.225 | 0.190 | 0.657 | 0.788 | 100 |
| temporal_uniform_nms | 0.103 | 0.164 | 0.300 | 0.647 | 1 |

## 10% Budget Ranking
| method | mean_oracle_event_recall | mean_oracle_clip_recall | mean_event_precision | mean_event_iou | num_trials |
| --- | --- | --- | --- | --- | --- |
| oracle_positive_first | 1.000 | 1.000 | 1.000 | 1.000 | 1 |
| segment_balanced_top_learned_rf | 0.483 | 0.393 | 0.737 | 0.826 | 1 |
| top_learned_rf | 0.483 | 0.361 | 1.000 | 0.813 | 1 |
| temporal_nms_count | 0.414 | 0.361 | 0.923 | 0.852 | 1 |
| top_count | 0.345 | 0.574 | 1.000 | 1.000 | 1 |
| segment_balanced_top_count | 0.172 | 0.164 | 1.000 | 0.877 | 1 |
| segment_equal_random | 0.144 | 0.126 | 0.908 | 0.959 | 100 |
| segment_length_random | 0.118 | 0.109 | 0.562 | 0.787 | 100 |
| random | 0.118 | 0.103 | 0.567 | 0.750 | 100 |
| shuffled_count | 0.115 | 0.134 | 0.495 | 0.764 | 100 |
| shuffled_learned_rf | 0.104 | 0.092 | 0.557 | 0.749 | 100 |
| temporal_uniform_nms | 0.034 | 0.082 | 0.200 | 0.385 | 1 |
| uniform_time | 0.034 | 0.049 | 0.333 | 1.000 | 1 |

## Q1. Proxy vs Random
- 10%: top_count 0.345 vs random 0.118.
- 10%: top_learned_rf 0.483 vs random 0.118.
- 10%: top_count 0.345 vs uniform_time 0.034.
- 20%: top_count 0.586 vs random 0.243.
- 20%: top_learned_rf 0.655 vs random 0.243.
- 20%: top_count 0.586 vs uniform_time 0.276.

## Q2. Proxy vs Uniform Temporal Sampling
- top_count vs uniform_time at 20%: 0.586 vs 0.276.
- temporal_nms_count vs temporal_uniform_nms at 20%: 0.517 vs 0.103.

## Q3. Proxy vs Segment-stratified Random
- segment_balanced_top_count vs segment_length_random at 20%: 0.414 vs 0.250.
- segment_balanced_top_count vs segment_equal_random at 20%: 0.414 vs 0.296.

## Q4. Shuffled Proxy Controls
| score_type | budget_fraction | original_method | shuffled_method | original_event_recall | shuffled_event_recall_mean | absolute_drop | relative_drop |
| --- | --- | --- | --- | --- | --- | --- | --- |
| count | 0.100 | top_count | shuffled_count | 0.345 | 0.115 | 0.230 | 0.666 |
| count | 0.200 | top_count | shuffled_count | 0.586 | 0.227 | 0.360 | 0.614 |
| learned_rf | 0.100 | top_learned_rf | shuffled_learned_rf | 0.483 | 0.104 | 0.378 | 0.784 |
| learned_rf | 0.200 | top_learned_rf | shuffled_learned_rf | 0.655 | 0.225 | 0.430 | 0.656 |

## Q5. Segment-balanced Proxy
| method_a | method_b | budget_fraction | event_recall_a | event_recall_b | delta_a_minus_b |
| --- | --- | --- | --- | --- | --- |
| top_count | segment_balanced_top_count | 0.100 | 0.345 | 0.172 | 0.172 |
| top_count | segment_balanced_top_count | 0.200 | 0.586 | 0.414 | 0.172 |
| top_learned_rf | segment_balanced_top_learned_rf | 0.100 | 0.483 | 0.483 | 0.000 |
| top_learned_rf | segment_balanced_top_learned_rf | 0.200 | 0.655 | 0.621 | 0.034 |
| segment_balanced_top_count | segment_length_random | 0.100 | 0.172 | 0.118 | 0.054 |
| segment_balanced_top_count | segment_length_random | 0.200 | 0.414 | 0.250 | 0.164 |
| segment_balanced_top_learned_rf | segment_length_random | 0.100 | 0.483 | 0.118 | 0.365 |
| segment_balanced_top_learned_rf | segment_length_random | 0.200 | 0.621 | 0.250 | 0.371 |

## Q6. Diagnostic Conclusion
- Diagnostic conclusion: proxy contains useful ranking signal on this pilot/dev set.
- If proxy methods beat random, uniform, segment-stratified, and shuffled controls, the proxy is carrying ranking signal beyond time coverage and segment prior.
- However, because the pilot positives are temporally/segment concentrated, this remains a pilot/dev diagnostic and should not become the formal 100-trial main evaluation.
- A new, less concentrated video source remains the necessary next step.
