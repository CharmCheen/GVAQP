# Micro-CASQ Candidate Feasibility Report

This is candidate-signal feasibility over an adjudicated sampled benchmark, not full-video retrieval. Event boundaries were not used to generate candidates. Configurations are pre-registered cheap baselines; no YOLO, embeddings, downloads, or training were run. Random baselines use 100 repeats and report mean recall with 95% intervals.

| candidate_generator | configuration | split | repeat_count | true_oracle_recall | recall_std | recall_ci95_low | recall_ci95_high | precision | returned_duration | duration_fraction | event_hit_count | positive_event_count | negative_window_coverage | runtime_seconds | candidate_generation_cost | source_diversity_hhi |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_baseline | top_fraction=0.25 | heldout_eval | 100 | 0.24882352941176467 | 0.09342249220375871 | 0.23051272093982797 | 0.2671343378837014 | 0.24882352941176467 |  | 0.25 | 4.23 | 17 | 12.77 | 0.0 | metadata_only |  |
| random_baseline | top_fraction=0.5 | heldout_eval | 100 | 0.5011764705882353 | 0.11689599833150878 | 0.4782648549152596 | 0.5240880862612111 | 0.24342857142857138 |  | 0.5 | 8.52 | 17 | 26.48 | 0.0 | metadata_only |  |
| random_baseline | top_fraction=0.75 | heldout_eval | 100 | 0.7541176470588234 | 0.0939912996255433 | 0.735695352332217 | 0.77253994178543 | 0.24188679245283018 |  | 0.75 | 12.82 | 17 | 40.18 | 0.0 | metadata_only |  |
| fixed_temporal_coverage | top_fraction=0.25 | heldout_eval | 1 | 0.8235294117647058 | 0.0 | 0.8235294117647058 | 0.8235294117647058 | 0.8235294117647058 | 85.0 | 0.23943661971830985 | 14.0 | 17 | 3.0 | 0.0 | metadata_only | 0.19031141868512108 |
| fixed_temporal_coverage | top_fraction=0.5 | heldout_eval | 1 | 0.9411764705882353 | 0.0 | 0.9411764705882353 | 0.9411764705882353 | 0.45714285714285713 | 148.0 | 0.49295774647887325 | 16.0 | 17 | 19.0 | 0.0 | metadata_only | 0.07591836734693876 |
| fixed_temporal_coverage | top_fraction=0.75 | heldout_eval | 1 | 1.0 | 0.0 | 1.0 | 1.0 | 0.32075471698113206 | 211.0 | 0.7464788732394366 | 17.0 | 17 | 36.0 | 0.0 | metadata_only | 0.04378782484870061 |
| provenance_priority | top_fraction=0.25 | heldout_eval | 1 | 0.5294117647058824 | 0.0 | 0.5294117647058824 | 0.5294117647058824 | 0.5294117647058824 | 85.0 | 0.23943661971830985 | 9.0 | 17 | 8.0 | 0.0 | metadata_only | 0.09342560553633217 |
| provenance_priority | top_fraction=0.5 | heldout_eval | 1 | 0.9411764705882353 | 0.0 | 0.9411764705882353 | 0.9411764705882353 | 0.45714285714285713 | 166.0 | 0.49295774647887325 | 16.0 | 17 | 19.0 | 0.0 | metadata_only | 0.06775510204081629 |
| provenance_priority | top_fraction=0.75 | heldout_eval | 1 | 0.9411764705882353 | 0.0 | 0.9411764705882353 | 0.9411764705882353 | 0.3018867924528302 | 251.5 | 0.7464788732394366 | 16.0 | 17 | 37.0 | 0.0 | metadata_only | 0.041651833392666426 |

REPRESENTATION_CANDIDATE_NOT_AVAILABLE

MICRO_CASQ_CANDIDATE_DECISION: CANDIDATE_READY_FOR_CERTIFICATE
