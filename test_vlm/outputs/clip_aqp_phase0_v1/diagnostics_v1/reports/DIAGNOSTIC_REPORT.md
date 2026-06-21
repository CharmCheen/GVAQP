# Phase 0 NO_GO Diagnostic Report

This diagnostic stage re-analyzes existing Phase 0 outputs only. It does not build new systems, collect new data, or call any VLM.

## Human Review Flag

`git status` shows `AGENTS.md` is modified. Per instruction, this diagnostic does not investigate or revert it.

```text
M AGENTS.md
?? docs/clip_aqp/CASQ_CODEX_BRIEF_V11.md
```

## 1. Sample-size accounting (Stage A)

| scope | total_units | total_oracle_positive_units | total_pseudo_events | pseudo_events_in_certification_sample | blocks_sampled | blocks_with_at_least_one_event_in_sample | exact_blocks_with_event_available | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_dataset | 1000 | 61 | 29 |  |  |  | False | Full-dataset pseudo-event count is available from phase0_pseudo_events.csv. |

Certification-sample summary by configured condition:

| theta | block_size_seconds | gamma | delta | trials | population_blocks | blocks_sampled | pseudo_events_in_certification_sample_mean | pseudo_events_in_certification_sample_min | pseudo_events_in_certification_sample_median | pseudo_events_in_certification_sample_max | blocks_with_at_least_one_event_in_sample | exact_blocks_with_event_available |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.3 | 10 | 0.8 | 0.05 | 100 | 397 | 139 | 10.24 | 4 | 10 | 15 |  | False |
| 0.3 | 10 | 0.8 | 0.1 | 100 | 397 | 139 | 10.41 | 5 | 10 | 18 |  | False |
| 0.3 | 10 | 0.9 | 0.05 | 100 | 397 | 139 | 10.43 | 6 | 10 | 15 |  | False |
| 0.3 | 10 | 0.9 | 0.1 | 100 | 397 | 139 | 9.97 | 3 | 10 | 16 |  | False |
| 0.3 | 15 | 0.8 | 0.05 | 100 | 272 | 96 | 10.14 | 6 | 10 | 17 |  | False |
| 0.3 | 15 | 0.8 | 0.1 | 100 | 272 | 96 | 10.28 | 5 | 10 | 17 |  | False |
| 0.3 | 15 | 0.9 | 0.05 | 100 | 272 | 96 | 10.04 | 4 | 10 | 18 |  | False |
| 0.3 | 15 | 0.9 | 0.1 | 100 | 272 | 96 | 10.38 | 5 | 10 | 17 |  | False |
| 0.3 | 30 | 0.8 | 0.05 | 100 | 139 | 49 | 10.11 | 5 | 10 | 15 |  | False |
| 0.3 | 30 | 0.8 | 0.1 | 100 | 139 | 49 | 10.1 | 4 | 10 | 14 |  | False |
| 0.3 | 30 | 0.9 | 0.05 | 100 | 139 | 49 | 9.95 | 4 | 10 | 16 |  | False |
| 0.3 | 30 | 0.9 | 0.1 | 100 | 139 | 49 | 10.55 | 5 | 10 | 16 |  | False |
| 0.5 | 10 | 0.8 | 0.05 | 100 | 397 | 139 | 9.94 | 5 | 10 | 17 |  | False |
| 0.5 | 10 | 0.8 | 0.1 | 100 | 397 | 139 | 10.08 | 1 | 10 | 15 |  | False |
| 0.5 | 10 | 0.9 | 0.05 | 100 | 397 | 139 | 10.09 | 4 | 10 | 16 |  | False |
| 0.5 | 10 | 0.9 | 0.1 | 100 | 397 | 139 | 9.78 | 4 | 10 | 16 |  | False |
| 0.5 | 15 | 0.8 | 0.05 | 100 | 272 | 96 | 10.37 | 6 | 10 | 16 |  | False |
| 0.5 | 15 | 0.8 | 0.1 | 100 | 272 | 96 | 10.27 | 6 | 10 | 18 |  | False |
| 0.5 | 15 | 0.9 | 0.05 | 100 | 272 | 96 | 10.39 | 4 | 10 | 16 |  | False |
| 0.5 | 15 | 0.9 | 0.1 | 100 | 272 | 96 | 10.45 | 4 | 10.5 | 16 |  | False |
| 0.5 | 30 | 0.8 | 0.05 | 100 | 139 | 49 | 10.22 | 4 | 10 | 16 |  | False |
| 0.5 | 30 | 0.8 | 0.1 | 100 | 139 | 49 | 10.42 | 6 | 10 | 16 |  | False |
| 0.5 | 30 | 0.9 | 0.05 | 100 | 139 | 49 | 10.16 | 5 | 10 | 15 |  | False |
| 0.5 | 30 | 0.9 | 0.1 | 100 | 139 | 49 | 10.06 | 4 | 10 | 14 |  | False |

Phase 0 mandated caveat sentence check:

| mandated_sentence | sentence_present_in_phase0_report | total_pseudo_events | constraint_violation | violation_reason |
| --- | --- | --- | --- | --- |
| Sample size insufficient for robust GVR estimation; results indicate direction only and must not be treated as sufficient evidence for GO/NO_GO. | False | 29 | True | Phase0 total pseudo-events < 30 and mandated caveat sentence is absent. |

Diagnostic finding: the full dataset has 29 pseudo-events, below the 30-event bar. The Phase 0 report did not contain the exact mandated caveat sentence, so this is a reporting constraint violation. Exact `blocks_with_at_least_one_event_in_sample` cannot be audited from the produced CSVs because Phase 0 persisted trial-level aggregates rather than per-block sampled rows.

## 2. Bound decomposition and power curve (Stage B)

Aggregate decomposition:

| theta | block_size_seconds | delta | sampled_blocks | point_estimate_recall_mean | LCB_recall_O_mean | M_concentration_term_median | Y_concentration_term_median | has_negative_UCB_M_margin | point_minus_LCB_gap_mean | true_oracle_recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.3 | 10 | 0.05 | 139 | 0.3091 | 0 | -5.186 | 13.8 | True | 0.3091 | 0.3103 |
| 0.3 | 10 | 0.1 | 139 | 0.3253 | 0.001236 | -2.46 | 11.58 | True | 0.3241 | 0.3103 |
| 0.3 | 15 | 0.05 | 96 | 0.3173 | 0 | -4.195 | 13.44 | True | 0.3173 | 0.3103 |
| 0.3 | 15 | 0.1 | 96 | 0.3246 | 0.0003774 | -1.302 | 11.28 | True | 0.3243 | 0.3103 |
| 0.3 | 30 | 0.05 | 49 | 0.3217 | 0 | -4.074 | 12.75 | True | 0.3217 | 0.3103 |
| 0.3 | 30 | 0.1 | 49 | 0.3212 | 0 | -1.305 | 10.7 | True | 0.3212 | 0.3103 |
| 0.5 | 10 | 0.05 | 139 | 0.2163 | 0 | -7.428 | 13.8 | True | 0.2163 | 0.2069 |
| 0.5 | 10 | 0.1 | 139 | 0.1989 | 0 | -6.06 | 11.58 | True | 0.1989 | 0.2069 |
| 0.5 | 15 | 0.05 | 96 | 0.2018 | 0 | -7.774 | 13.44 | True | 0.2018 | 0.2069 |
| 0.5 | 15 | 0.1 | 96 | 0.2119 | 0 | -5.614 | 11.28 | True | 0.2119 | 0.2069 |
| 0.5 | 30 | 0.05 | 49 | 0.1912 | 0 | -7.529 | 12.75 | True | 0.1912 | 0.2069 |
| 0.5 | 30 | 0.1 | 49 | 0.2116 | 0 | -5.03 | 10.7 | True | 0.2116 | 0.2069 |

Power curve using the same bound construction and observed aggregate variance structure:

| theta | block_size_seconds | delta | target_LCB | observed_point_estimate_recall_median | observed_LCB_recall_O_mean | current_blocks_sampled | population_blocks | required_blocks_sampled | required_blocks_multiple_vs_used | required_certification_events_approx | projected_LCB_at_full_scan | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.3 | 10 | 0.05 | 0.3 | 0.3 | 0 | 139 | 397 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 10 | 0.05 | 0.5 | 0.3 | 0 | 139 | 397 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 10 | 0.05 | 0.7 | 0.3 | 0 | 139 | 397 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 10 | 0.1 | 0.3 | 0.3 | 0.001236 | 139 | 397 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 10 | 0.1 | 0.5 | 0.3 | 0.001236 | 139 | 397 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 10 | 0.1 | 0.7 | 0.3 | 0.001236 | 139 | 397 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 15 | 0.05 | 0.3 | 0.3 | 0 | 96 | 272 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 15 | 0.05 | 0.5 | 0.3 | 0 | 96 | 272 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 15 | 0.05 | 0.7 | 0.3 | 0 | 96 | 272 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 15 | 0.1 | 0.3 | 0.3 | 0.0003774 | 96 | 272 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 15 | 0.1 | 0.5 | 0.3 | 0.0003774 | 96 | 272 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 15 | 0.1 | 0.7 | 0.3 | 0.0003774 | 96 | 272 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 30 | 0.05 | 0.3 | 0.3 | 0 | 49 | 139 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 30 | 0.05 | 0.5 | 0.3 | 0 | 49 | 139 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 30 | 0.05 | 0.7 | 0.3 | 0 | 49 | 139 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 30 | 0.1 | 0.3 | 0.3 | 0 | 49 | 139 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 30 | 0.1 | 0.5 | 0.3 | 0 | 49 | 139 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.3 | 30 | 0.1 | 0.7 | 0.3 | 0 | 49 | 139 |  |  |  | 0.3 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 10 | 0.05 | 0.3 | 0.2 | 0 | 139 | 397 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 10 | 0.05 | 0.5 | 0.2 | 0 | 139 | 397 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 10 | 0.05 | 0.7 | 0.2 | 0 | 139 | 397 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 10 | 0.1 | 0.3 | 0.2 | 0 | 139 | 397 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 10 | 0.1 | 0.5 | 0.2 | 0 | 139 | 397 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 10 | 0.1 | 0.7 | 0.2 | 0 | 139 | 397 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 15 | 0.05 | 0.3 | 0.2 | 0 | 96 | 272 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 15 | 0.05 | 0.5 | 0.2 | 0 | 96 | 272 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 15 | 0.05 | 0.7 | 0.2 | 0 | 96 | 272 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 15 | 0.1 | 0.3 | 0.2 | 0 | 96 | 272 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 15 | 0.1 | 0.5 | 0.2 | 0 | 96 | 272 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 15 | 0.1 | 0.7 | 0.2 | 0 | 96 | 272 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 30 | 0.05 | 0.3 | 0.2 | 0 | 49 | 139 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 30 | 0.05 | 0.5 | 0.2 | 0 | 49 | 139 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 30 | 0.05 | 0.7 | 0.2 | 0 | 49 | 139 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 30 | 0.1 | 0.3 | 0.2 | 0 | 49 | 139 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 30 | 0.1 | 0.5 | 0.2 | 0 | 49 | 139 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |
| 0.5 | 30 | 0.1 | 0.7 | 0.2 | 0 | 49 | 139 |  |  |  | 0.2 | DIAGNOSTIC_ONLY_BOUND_INCONSISTENT |

Stage B classification:

| stage_b_classification | reason |
| --- | --- |
| INCONCLUSIVE_NEEDS_CODE_REVIEW | The decomposition found negative UCB_M_O - M_hat margins, so reported UCB(M^O) is below the uncorrected point estimate in some conditions. That is inconsistent with interpreting UCB_M_O as an upper confidence bound and requires code/formula review before accepting the LCB diagnosis. |

Interpretation: Stage B is not clean enough to accept as a statistical power finding. The decomposition found negative `UCB_M_O - M_hat` margins, meaning the reported UCB for missed events can be lower than the uncorrected point estimate. That is inconsistent with the documented upper-bound interpretation and should be reviewed before using the LCB to diagnose method viability. Separately, the fixed returned clips have low point recall, so high LCB targets would remain impossible unless candidate recall improves.

## 3. Oracle stability detail (Stage C)

| comparison_name | agreement_rate | flip_rate | positive_to_negative_flip | negative_to_positive_flip | stability_classification | actual_oracle_sources_used_for_Y_M | involves_actual_oracle_contract_used_for_certification | oracle_contract_relation | certificate_threat_level | consistent_with_prior_prompt_strictness_nonmonotonicity | prior_prompt_sensitivity_reference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8b_raw_vs_masked | 0.8209 | 0.1791 | 0 | 12 | ambiguous | conservative_vlm_pseudo_oracle | False | not_the_certification_oracle_table | not_first_order_for_existing_B1_certificate | True | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/prompt_sensitivity_report.md |
| 32b_raw_vs_masked | 0.791 | 0.209 | 2 | 12 | unstable | conservative_vlm_pseudo_oracle | False | not_the_certification_oracle_table | not_first_order_for_existing_B1_certificate | True | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/prompt_sensitivity_report.md |

| unstable_comparisons | ambiguous_comparisons | actual_oracle_contract_unstable | stage_c_finding |
| --- | --- | --- | --- |
| 32b_raw_vs_masked | 8b_raw_vs_masked | False | unstable comparison exists but Phase 0 stability table does not show it is the same table/contract used for Y_i^O/M_i^O |

The unstable comparison is `32b_raw_vs_masked`; the ambiguous comparison is `8b_raw_vs_masked`. These are raw-vs-masked comparison checks and are not shown by the Phase 0 stability table to be the exact conservative VLM pseudo-oracle table used for `Y_i^O/M_i^O` in B1. They do not directly invalidate the already computed Stage B arithmetic, but they remain a warning for any future oracle/prompt change. This is consistent with the prior prompt-sensitivity finding that 32B L2/L3 behavior was non-monotonic under different prompt wording.

## 4. Revised classification

`INCONCLUSIVE_NEEDS_CODE_REVIEW`

Reason: Stage B surfaces a bound-construction inconsistency rather than a clean statistical power result. Stage C does not prove that the exact certification oracle contract is unstable, but it does flag nearby oracle sensitivity.

## 5. Recommended next action

Do not accept the original NO_GO as final evidence that the whole G-ClipAQP direction is impossible. First review the Stage B bound implementation/formula and require per-block certification-sample outputs so the sample design can be audited exactly. Also treat the current pseudo-event benchmark as under the 30-event reporting threshold.

Before deciding whether to scale up the benchmark, change the oracle, or abandon the certificate construction, manually read Stage B's power-curve table and Stage C's per-comparison numbers directly rather than relying on the revised classification label alone.
