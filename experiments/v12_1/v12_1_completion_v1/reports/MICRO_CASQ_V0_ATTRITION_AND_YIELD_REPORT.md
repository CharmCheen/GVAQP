# Micro-CASQ v0 Attrition and Yield Report

All labels are 32B-oracle-relative, not human truth.

- Raw positives: `31` -> eligible positives: `23`.
- Raw negatives: `112` -> eligible negatives: `51`.
- Main positive attrition drivers are invalid/missing positive boundaries, low confidence, uncertain/truncated boundaries, or sanity-check flags.
- Main negative attrition drivers are needs_human_sanity_check flags, confidence/boundary filters, abstain rows, and run failures.

## Attrition Table
| stage | count | notes |
| --- | --- | --- |
| materializable_selected | 153 | v0 materializable samples |
| successful_parse | 149 | 32B oracle parsed |
| raw_positive | 31 | label == positive |
| eligible_positive | 23 | positive, high/medium confidence, ok boundary, valid times, no sanity flag |
| raw_negative | 112 | label == negative |
| eligible_negative | 51 | negative, high/medium confidence, not_applicable boundary, no sanity flag |
| excluded_or_needs_sanity_check | 79 | excluded from headline benchmark |

## Exclusion Reasons
| subset | exclusion_reason | count |
| --- | --- | --- |
| all_excluded | low_confidence | 6 |
| all_excluded | uncertain_boundary | 4 |
| all_excluded | truncated_boundary | 0 |
| all_excluded | abstain | 6 |
| all_excluded | parse_failure | 4 |
| all_excluded | run_failure | 4 |
| all_excluded | invalid_boundary | 3 |
| all_excluded | needs_human_sanity_check | 73 |
| raw_positive_not_eligible | low_confidence | 0 |
| raw_positive_not_eligible | uncertain_boundary | 0 |
| raw_positive_not_eligible | truncated_boundary | 0 |
| raw_positive_not_eligible | abstain | 0 |
| raw_positive_not_eligible | parse_failure | 0 |
| raw_positive_not_eligible | run_failure | 0 |
| raw_positive_not_eligible | invalid_boundary | 3 |
| raw_positive_not_eligible | needs_human_sanity_check | 6 |
| raw_negative_not_eligible | low_confidence | 0 |
| raw_negative_not_eligible | uncertain_boundary | 0 |
| raw_negative_not_eligible | truncated_boundary | 0 |
| raw_negative_not_eligible | abstain | 0 |
| raw_negative_not_eligible | parse_failure | 0 |
| raw_negative_not_eligible | run_failure | 0 |
| raw_negative_not_eligible | invalid_boundary | 0 |
| raw_negative_not_eligible | needs_human_sanity_check | 61 |

## Highest Positive-Yield Strata
| sampling_stratum | rows | raw_positive | eligible_positive | raw_negative | eligible_negative | eligible_positive_yield | eligible_negative_yield |
| --- | --- | --- | --- | --- | --- | --- | --- |
| likely_positive | 29 | 9 | 8 | 16 | 0 | 0.2758620689655172 | 0.0 |
| label_disagreement | 60 | 15 | 15 | 45 | 0 | 0.25 | 0.0 |
| possible_false_negative | 60 | 6 | 0 | 50 | 50 | 0.0 | 0.8333333333333334 |
| hard_negative | 4 | 1 | 0 | 1 | 1 | 0.0 | 0.25 |

## Highest Positive-Yield Candidate Sources
| candidate_source | rows | raw_positive | eligible_positive | raw_negative | eligible_negative | eligible_positive_yield | eligible_negative_yield |
| --- | --- | --- | --- | --- | --- | --- | --- |
| vlm_micro_audit | 135 | 29 | 23 | 102 | 41 | 0.1703703703703703 | 0.3037037037037037 |
| nexar_candidate_windows | 9 | 0 | 0 | 9 | 9 | 0.0 | 1.0 |
| vlm_labels_conservative | 3 | 0 | 0 | 0 | 0 | 0.0 | 0.0 |
| human_audit | 2 | 1 | 0 | 0 | 0 | 0.0 | 0.0 |
| kinematic_proxy | 2 | 1 | 0 | 0 | 0 | 0.0 | 0.0 |
| roadclip | 2 | 0 | 0 | 1 | 1 | 0.0 | 0.5 |

## Highest Positive-Yield Source Assets
| source_asset | rows | raw_positive | eligible_positive | raw_negative | eligible_negative | eligible_positive_yield | eligible_negative_yield |
| --- | --- | --- | --- | --- | --- | --- | --- |
| test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/audits/vlm_micro_audit_results.csv | 18 | 6 | 6 | 12 | 0 | 0.3333333333333333 | 0.0 |
| test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1/audits/vlm_micro_audit_samples.csv | 20 | 4 | 4 | 16 | 0 | 0.2 | 0.0 |
| test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1/audits/vlm_micro_audit_results.csv | 97 | 19 | 13 | 74 | 41 | 0.134020618556701 | 0.422680412371134 |
| test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/tables/nexar_candidate_windows_v2.csv | 9 | 0 | 0 | 9 | 9 | 0.0 | 1.0 |
| test_vlm/outputs/roadclip_budget_v2/vlm_labels_conservative.csv | 3 | 0 | 0 | 0 | 0 | 0.0 | 0.0 |
| test_vlm/outputs/kinematic_proxy/human_audit_conservative_vlm_68clips/audit_manifest.csv | 2 | 1 | 0 | 0 | 0 | 0.0 | 0.0 |
| test_vlm/outputs/roadclip_budget_v2/clips.csv | 2 | 0 | 0 | 1 | 1 | 0.0 | 0.5 |
| test_vlm/outputs/kinematic_proxy/clips.csv | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.0 |
| test_vlm/outputs/kinematic_proxy/conservative_calibration_set.csv | 1 | 1 | 0 | 0 | 0 | 0.0 | 0.0 |

## Expansion Strategy
Prioritize remaining materializable rows from likely_positive, label_disagreement, possible_false_negative, old positive/VLM-derived provenance, human-audit provenance, and source assets with observed eligible-positive yield, while retaining enough hard/likely negatives to approach the eligible-negative gate.
