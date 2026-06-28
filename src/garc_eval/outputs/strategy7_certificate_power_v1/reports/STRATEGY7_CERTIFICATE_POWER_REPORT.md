# Strategy 7 Certificate Power Report

- Timestamp: 2026-06-27T15:21:58Z
- Mode: `full`; seeds per stochastic policy: 500.
- No Qwen, GLM, YOLO, GPT, human oracle, frame extraction, downloads, or training were run.
- Delta for exact hypergeometric upper bound: 0.05.
- Target lower-bound grid: [0.1, 0.2, 0.3, 0.5].
- Certificate design: non-random L3/Strategy7 selections are retrieval observations; only the final uniform random audit is used for the exact residual hypergeometric bound.
- Decision: `WEAK_GO_MIXED_CERTIFICATE_POWER`.

## Input Audit

| dataset | rows | positive_count | negative_count | glm_counts | score_column | source_tables | leakage_note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dataset3_clean_pool | 100 | 28 | 72 | {'negative': 72, 'positive': 28} | object_count_mean | see config/experiment_config.yaml | labels/event clusters used only for evaluation and simulated oracle outcomes |
| realcartest_v13 | 399 | 94 | 305 | {'negative': 292, 'positive': 106, 'parse_error': 1} | object_count_mean | see config/experiment_config.yaml | labels/event clusters used only for evaluation and simulated oracle outcomes |

## Dataset3 Clean Pool Comparison

| B | eff B | S7-L3 mean R_lower | S7-L3 width-to-1 | S7-L3 audit positives | S7-L3 L3-missed recovered | gamma0.2 rate gap | gamma0.3 rate gap |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 20 | -0.002128 | 0.002128 | 1.886 | 1.912 | 0.000 | 0.000 |
| 30 | 30 | -0.004089 | 0.004089 | 2.254 | 2.412 | -0.040 | 0.000 |
| 40 | 40 | 0.010161 | -0.010161 | 3.506 | 3.622 | 0.000 | 0.270 |
| 60 | 60 | 0.025589 | -0.025589 | 3.876 | 3.134 | 0.000 | 0.000 |
| 80 | 80 | 0.028429 | -0.028429 | 2.606 | 0.230 | 0.000 | 0.000 |
| 100 | 100 | 0.000000 | 0.000000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 150 | 100 | 0.000000 | 0.000000 | 0.000 | 0.000 | 0.000 | 0.000 |

## Realcartest Comparison

| B | eff B | S7-L3 mean R_lower | S7-L3 width-to-1 | S7-L3 audit positives | S7-L3 L3-missed recovered | gamma0.2 rate gap | gamma0.3 rate gap |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 20 | -0.014714 | 0.014714 | 0.102 | 0.156 | 0.000 | 0.000 |
| 30 | 30 | -0.027006 | 0.027006 | 0.754 | 0.852 | 0.000 | 0.000 |
| 40 | 40 | -0.034536 | 0.034536 | 1.440 | 1.556 | -0.076 | 0.000 |
| 60 | 60 | -0.051728 | 0.051728 | 1.886 | 2.202 | -0.356 | -0.024 |
| 80 | 80 | -0.049915 | 0.049915 | 3.214 | 3.836 | -0.380 | -0.158 |
| 100 | 100 | -0.057077 | 0.057077 | 3.892 | 4.294 | 0.000 | -0.326 |
| 150 | 150 | -0.055298 | 0.055298 | 3.734 | 4.358 | 0.000 | 0.000 |

## Target Budget Summary

| dataset | policy | target_lower_bound_gamma | min_effective_budget_mean_reaches_gamma | min_requested_budget_mean_reaches_gamma | min_effective_budget_95pct_seeds_reach_gamma | min_requested_budget_95pct_seeds_reach_gamma | max_mean_recall_lower_bound | max_certificate_rate_for_gamma |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dataset3_clean_pool | L3_uniform_certificate | 0.100000 | 20 | 20 | 20 | 20 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L3_uniform_certificate | 0.200000 | 40 | 40 | 40 | 40 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L3_uniform_certificate | 0.300000 | 60 | 60 | 60 | 60 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L3_uniform_certificate | 0.500000 | 80 | 80 | 80 | 80 | 1.000000 | 1.000000 |
| dataset3_clean_pool | Strategy7_certificate | 0.100000 | 20 | 20 | 20 | 20 | 1.000000 | 1.000000 |
| dataset3_clean_pool | Strategy7_certificate | 0.200000 | 40 | 40 | 40 | 40 | 1.000000 | 1.000000 |
| dataset3_clean_pool | Strategy7_certificate | 0.300000 | 60 | 60 | 60 | 60 | 1.000000 | 1.000000 |
| dataset3_clean_pool | Strategy7_certificate | 0.500000 | 80 | 80 | 80 | 80 | 1.000000 | 1.000000 |
| realcartest_v13 | L3_uniform_certificate | 0.100000 | 40 | 40 | 60 | 60 | 0.498437 | 1.000000 |
| realcartest_v13 | L3_uniform_certificate | 0.200000 | 60 | 60 | 80 | 80 | 0.498437 | 1.000000 |
| realcartest_v13 | L3_uniform_certificate | 0.300000 | 100 | 100 | 150 | 150 | 0.498437 | 1.000000 |
| realcartest_v13 | L3_uniform_certificate | 0.500000 |  |  |  |  | 0.498437 | 0.420000 |
| realcartest_v13 | Strategy7_certificate | 0.100000 | 60 | 60 | 60 | 60 | 0.443140 | 1.000000 |
| realcartest_v13 | Strategy7_certificate | 0.200000 | 80 | 80 | 100 | 100 | 0.443140 | 1.000000 |
| realcartest_v13 | Strategy7_certificate | 0.300000 | 100 | 100 | 150 | 150 | 0.443140 | 1.000000 |
| realcartest_v13 | Strategy7_certificate | 0.500000 |  |  |  |  | 0.443140 | 0.138000 |

## Non-Vacuous And Target Certificate Rates

| dataset | policy | min_non_vacuous_rate | max_gamma_0_3_rate | max_gamma_0_5_rate | max_mean_recall_lower_bound |
| --- | --- | --- | --- | --- | --- |
| dataset3_clean_pool | L3_uniform_certificate | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| dataset3_clean_pool | Strategy7_certificate | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| realcartest_v13 | L3_uniform_certificate | 1.000000 | 1.000000 | 0.420000 | 0.498437 |
| realcartest_v13 | Strategy7_certificate | 1.000000 | 1.000000 | 0.138000 | 0.443140 |

- Non-vacuous means `recall_lower_bound > 0`; all rows are non-vacuous under this weak definition because every budget policy finds at least one positive in the simulated oracle labels.
- Target-specific certificate rates are more informative: on realcartest, Strategy7 reaches gamma=0.3 by B=150 but has lower gamma=0.5 rate than L3+uniform at the largest budget tested.

## Interpretation

- Positive `S7-L3 mean R_lower` means Strategy 7 improves certificate tightness for recall lower bound, not only selected-positive recovery.
- Negative `width-to-1` gap means Strategy 7 narrows the lower-bound interval to the trivial upper endpoint 1.
- If Strategy 7 uses 20% targeted audit and only 10% uniform random audit, a gain is meaningful because the random certificate sample is smaller; the targeted observations must compensate by increasing observed positives and shrinking the residual population.
- Result: Strategy7 clears that bar on dataset3 only in mid-budget regimes, but not on realcartest. On realcartest it recovers more L3-missed positives while producing a looser exact hypergeometric recall lower bound, because the smaller uniform random audit leaves a larger residual upper bound.
- AQP implication: current Strategy7 is a recovery mechanism, not yet a robust certificate-power mechanism. It should enter the AQP layer only through a design that preserves enough random audit mass or uses a valid stratified certificate.
- Dataset3 B=150 is clipped to effective B=100 because the clean pool has N=100; this row is exhaustive and should not be treated as a real 150-call budget on dataset3.

## Limitations

- Labels are existing pseudo-oracle/VLM-defined labels, not human truth.
- The exact hypergeometric bound is clip-level and assumes the random audit is sampled uniformly from the remaining residual population. It does not solve temporal correlation at event level.
- Strategy7's disagreement audit is not used as a random sample for certification; using it that way would be invalid.
- Dataset3 clean pool has only 100 anchors and is not directly comparable in scale to realcartest's 399 anchors.
