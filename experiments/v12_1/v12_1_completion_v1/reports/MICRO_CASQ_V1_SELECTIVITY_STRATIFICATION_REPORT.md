# Micro-CASQ v1 Selectivity Stratification Report

Strata are reported for the oracle-relative sampled benchmark. Per-stratum true recall is computed for the best frozen deterministic heldout candidate configuration where applicable. NO_CERTIFICATE is reported for LCB strata because the reserved certification pool is underpowered and no non-vacuous certificate is claimed.

| field | value | rows | per_stratum_event_count | per_stratum_true_recall | per_stratum_LCB_recall | certificate_event_hits | limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sampling_stratum | hard_negative | 1 | 0 |  | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| sampling_stratum | label_disagreement | 15 | 15 | 0.4666666666666667 | NO_CERTIFICATE | 3 | pooled sampled benchmark; reserved-pool certificate underpowered |
| sampling_stratum | likely_positive | 33 | 16 | 0.5625 | NO_CERTIFICATE | 3 | pooled sampled benchmark; reserved-pool certificate underpowered |
| sampling_stratum | possible_false_negative | 120 | 7 | 0.14285714285714285 | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| candidate_source | nexar_candidate_windows | 33 | 2 | 0.5 | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| candidate_source | roadclip | 1 | 0 |  | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| candidate_source | vlm_micro_audit | 135 | 36 | 0.4444444444444444 | NO_CERTIFICATE | 6 | pooled sampled benchmark; reserved-pool certificate underpowered |
| boundary_source | clip_window_boundary_only | 1 | 0 |  | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| boundary_source | derived_event_end | 28 | 11 | 0.45454545454545453 | NO_CERTIFICATE | 3 | pooled sampled benchmark; reserved-pool certificate underpowered |
| boundary_source | derived_event_start | 20 | 20 | 0.55 | NO_CERTIFICATE | 3 | pooled sampled benchmark; reserved-pool certificate underpowered |
| boundary_source | derived_or_external_metadata_boundary | 87 | 5 | 0.0 | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| boundary_source | missing_or_unknown | 33 | 2 | 0.5 | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| involved_object | pedestrian | 12 | 12 | 0.9166666666666666 | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| involved_object | vehicle | 26 | 26 | 0.23076923076923078 | NO_CERTIFICATE | 6 | pooled sampled benchmark; reserved-pool certificate underpowered |
| involved_object | nan | 131 | 0 |  | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| negative_reason | dense_traffic_only | 3 | 0 |  | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| negative_reason | far_crossing_no_ego_conflict | 12 | 0 |  | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| negative_reason | none | 38 | 38 | 0.4473684210526316 | NO_CERTIFICATE | 6 | pooled sampled benchmark; reserved-pool certificate underpowered |
| negative_reason | normal_following | 106 | 0 |  | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| negative_reason | static_roadside | 10 | 0 |  | NO_CERTIFICATE | 0 | pooled sampled benchmark; reserved-pool certificate underpowered |
| confidence | high | 169 | 38 | 0.4473684210526316 | NO_CERTIFICATE | 6 | pooled sampled benchmark; reserved-pool certificate underpowered |
| old_label_source | vlm_derived | 169 | 38 | 0.4473684210526316 | NO_CERTIFICATE | 6 | pooled sampled benchmark; reserved-pool certificate underpowered |
