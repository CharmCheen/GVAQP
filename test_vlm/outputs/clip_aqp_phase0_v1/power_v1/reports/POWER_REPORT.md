# Phase 0.6 Power/Scaling Report

This simulation uses repaired Phase 0 outputs only. It does not run VLM, download data, train models, build a perception stack, modify `repair_v1`, or fabricate event boundaries.

## Input Validation

| missing_required_block_columns | UCB_M_ge_M_hat | LCB_Y_le_Y_hat | all_rows_certification | no_used_for_design | no_used_for_repair | validation_passed |
| --- | --- | --- | --- | --- | --- | --- |
|  | True | True | True | True | True | True |

## Empirical Block Model

| reference_theta | reference_block_size_seconds | reference_gamma | reference_delta | num_reference_blocks | number_of_pseudo_events | positive_block_rate | event_prevalence_per_block | miss_rate | reference_oracle_recall | current_true_oracle_recall_mean | current_LCB_recall_mean | current_LCB_recall_median | current_fraction_vacuous | current_cost_to_certificate_mean | proxy_stratification_fields_available | stratification_used_in_power_v1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.3 | 10 | 0.8 | 0.1 | 397 | 29 | 0.07305 | 0.07305 | 0.6897 | 0.3103 | 0.3103 | 0.002472 | 0 | 0.99 | 139 | False | video_id/source strata; no candidate/proxy-region field exists in block_audit_rows_v2.csv |

The reference model uses the repaired rows at theta=0.3, block_size=10s, gamma=0.8, delta=0.1 because that was the least conservative repaired condition and is the most favorable read for whether scaling alone helps.

## Power Scaling Summary

| mode | target_event_count | trials | actual_event_count_mean | population_blocks_mean | cost_to_certificate_mean | true_recall_mean | LCB_recall_mean | LCB_recall_median | LCB_recall_p10 | LCB_recall_p90 | GVR | coverage | tightness_mean | certificate_success_rate | fraction_vacuous |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bootstrap_diagnostic | 50 | 200 | 50 | 685 | 240 | 0.307 | 0.1285 | 0.1176 | 0 | 0.2366 | 0.02 | 0.98 | 0.1785 | 0 | 0.14 |
| bootstrap_diagnostic | 100 | 200 | 100 | 1369 | 480 | 0.3061 | 0.1845 | 0.1815 | 0.09221 | 0.2816 | 0.015 | 0.985 | 0.1216 | 0 | 0 |
| bootstrap_diagnostic | 200 | 200 | 200 | 2738 | 959 | 0.3088 | 0.2231 | 0.2237 | 0.1613 | 0.2881 | 0.02 | 0.98 | 0.08573 | 0 | 0 |
| bootstrap_diagnostic | 500 | 200 | 500 | 6845 | 2396 | 0.3093 | 0.2549 | 0.2532 | 0.2134 | 0.2958 | 0.015 | 0.985 | 0.05436 | 0 | 0 |
| bootstrap_diagnostic | 1000 | 200 | 1000 | 1.369e+04 | 4792 | 0.3107 | 0.2704 | 0.2691 | 0.2425 | 0.299 | 0.02 | 0.98 | 0.0403 | 0 | 0 |
| bootstrap_diagnostic | 2000 | 200 | 2000 | 2.738e+04 | 9583 | 0.3115 | 0.2847 | 0.2842 | 0.2614 | 0.3064 | 0.02 | 0.98 | 0.02682 | 0 | 0 |
| certified_srs | 50 | 200 | 50 | 685 | 240 | 0.307 | 0.004908 | 0 | 0 | 0 | 0 | 1 | 0.3021 | 0 | 0.93 |
| certified_srs | 100 | 200 | 100 | 1369 | 480 | 0.3061 | 0.01005 | 0 | 0 | 0.03986 | 0 | 1 | 0.2961 | 0 | 0.845 |
| certified_srs | 200 | 200 | 200 | 2738 | 959 | 0.3088 | 0.0476 | 0.03646 | 0 | 0.1186 | 0 | 1 | 0.2612 | 0 | 0.315 |
| certified_srs | 500 | 200 | 500 | 6845 | 2396 | 0.3093 | 0.1466 | 0.1475 | 0.09736 | 0.192 | 0 | 1 | 0.1627 | 0 | 0 |
| certified_srs | 1000 | 200 | 1000 | 1.369e+04 | 4792 | 0.3107 | 0.2012 | 0.202 | 0.1655 | 0.2336 | 0 | 1 | 0.1095 | 0 | 0 |
| certified_srs | 2000 | 200 | 2000 | 2.738e+04 | 9583 | 0.3115 | 0.234 | 0.2334 | 0.2123 | 0.2574 | 0 | 1 | 0.07756 | 0 | 0 |
| stratified_by_video | 50 | 200 | 50 | 685 | 240.1 | 0.307 | 0.001477 | 0 | 0 | 0 | 0 | 1 | 0.3055 | 0 | 0.97 |
| stratified_by_video | 100 | 200 | 100 | 1369 | 479.4 | 0.3061 | 0.009797 | 0 | 0 | 0.03756 | 0 | 1 | 0.2963 | 0 | 0.85 |
| stratified_by_video | 200 | 200 | 200 | 2738 | 958.1 | 0.3088 | 0.05165 | 0.04005 | 0 | 0.1287 | 0 | 1 | 0.2571 | 0 | 0.29 |
| stratified_by_video | 500 | 200 | 500 | 6845 | 2396 | 0.3093 | 0.1443 | 0.1475 | 0.09332 | 0.1968 | 0 | 1 | 0.165 | 0 | 0 |
| stratified_by_video | 1000 | 200 | 1000 | 1.369e+04 | 4791 | 0.3107 | 0.1983 | 0.1986 | 0.1591 | 0.2316 | 0 | 1 | 0.1124 | 0 | 0 |
| stratified_by_video | 2000 | 200 | 2000 | 2.738e+04 | 9583 | 0.3115 | 0.2352 | 0.2336 | 0.2127 | 0.2607 | 0 | 1 | 0.07637 | 0 | 0 |

## Mode Comparison

| target_event_count | certified_lcb_median | certified_fraction_vacuous | certified_tightness | stratified_lcb_median | stratified_fraction_vacuous | stratified_tightness | bootstrap_lcb_median | bootstrap_fraction_vacuous | bootstrap_tightness | stratified_minus_certified_lcb | bootstrap_minus_certified_lcb |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 50 | 0 | 0.93 | 0.3021 | 0 | 0.97 | 0.3055 | 0.1176 | 0.14 | 0.1785 | 0 | 0.1176 |
| 100 | 0 | 0.845 | 0.2961 | 0 | 0.85 | 0.2963 | 0.1815 | 0 | 0.1216 | 0 | 0.1815 |
| 200 | 0.03646 | 0.315 | 0.2612 | 0.04005 | 0.29 | 0.2571 | 0.2237 | 0 | 0.08573 | 0.003589 | 0.1872 |
| 500 | 0.1475 | 0 | 0.1627 | 0.1475 | 0 | 0.165 | 0.2532 | 0 | 0.05436 | -2.556e-05 | 0.1057 |
| 1000 | 0.202 | 0 | 0.1095 | 0.1986 | 0 | 0.1124 | 0.2691 | 0 | 0.0403 | -0.003443 | 0.06707 |
| 2000 | 0.2334 | 0 | 0.07756 | 0.2336 | 0 | 0.07637 | 0.2842 | 0 | 0.02682 | 0.0001649 | 0.05072 |

Mode C (`bootstrap_diagnostic`) is practical diagnostic only. It is not a certified proof and must not be described as a valid recall certificate.

## Answers

- Is current UNDERPOWERED likely caused by only 29 pseudo-events? Certified mode becomes non-vacuous around target event count `200` under the synthetic pseudo-event assumptions, so event count is a major contributor if that value is finite. The result remains pseudo-event based.
- Around how many events are needed before LCB_recall becomes non-vacuous? See `tables/power_scaling_summary.csv`; the first certified event count with fraction_vacuous < 0.5 is reported above.
- Does repaired certified bound become useful at 100 / 200 / 500 / 1000 events? Certified-mode details:

| target_event_count | LCB_recall_median | fraction_vacuous | tightness_mean | GVR |
| --- | --- | --- | --- | --- |
| 100 | 0 | 0.845 | 0.2961 | 0 |
| 200 | 0.03646 | 0.315 | 0.2612 | 0 |
| 500 | 0.1475 | 0 | 0.1627 | 0 |
| 1000 | 0.202 | 0 | 0.1095 | 0 |

- Does stratification materially improve tightness? Median stratified-minus-certified LCB ranges from `-0.003` to `0.004`; this is source/video stratification because no candidate/proxy region field exists in `block_audit_rows_v2.csv`.
- Is practical bootstrap much tighter than certified mode? Bootstrap-minus-certified median LCB ranges from `0.051` to `0.187`, but bootstrap is diagnostic only.
- Should the next step be expanding benchmark, changing bound, or collecting clean event boundaries? The safest next action is to collect/construct clean event boundaries or expand the benchmark only as a pseudo-event stress test; do not treat this as human-ground-truth certificate evidence.

## Limitations

- Synthetic populations are bootstrapped from repaired sampled block rows, not new real videos.
- Event boundaries remain pseudo-events; this can dominate the conclusion.
- Stratified mode uses `video_id` because candidate/proxy region fields are not available in the repaired block rows.
- Bootstrap mode is not certified proof.

POWER_DECISION: EXPAND_BENCHMARK_TO_N_EVENTS
