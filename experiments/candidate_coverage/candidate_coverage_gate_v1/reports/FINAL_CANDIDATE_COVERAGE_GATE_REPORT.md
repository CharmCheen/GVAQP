# Candidate Coverage Gate V1 Report

This is a VLM-defined pseudo-event development experiment. Conservative VLM labels are used only for evaluation.

## Inputs

- clips: 1000
- conservative VLM positives: 61
- source video groups: 11
- full runtime seconds: 18.17
- K grid: [5, 10, 20, 50, 100, 200, 500]
- random seeds: 100

## Primary Gap 4s Results

| method | k_requested | k_actual | micro_event_coverage_mean | macro_source_event_coverage_mean | tail_source_event_coverage_mean | candidate_source_hhi_mean |
| --- | --- | --- | --- | --- | --- | --- |
| cheap_union_upper_bound | 50 | 179 | 0.469 | 0.475 | 0.333 | 0.420 |
| random | 50 | 50 | 0.098 | 0.096 | 0.115 | 0.292 |
| rank_fusion_proxy | 50 | 50 | 0.344 | 0.354 | 0.333 | 0.430 |
| rule_like_conjunction | 50 | 50 | 0.188 | 0.071 | 0.000 | 0.411 |
| score_union_proxy | 50 | 50 | 0.219 | 0.378 | 0.333 | 0.286 |
| temporal_nms_count | 50 | 50 | 0.250 | 0.389 | 0.333 | 0.690 |
| top_count | 50 | 50 | 0.188 | 0.367 | 0.333 | 0.482 |
| top_ego_path | 50 | 50 | 0.156 | 0.356 | 0.333 | 0.534 |
| top_kinematic | 50 | 50 | 0.062 | 0.022 | 0.000 | 0.346 |
| cheap_union_upper_bound | 100 | 296 | 0.625 | 0.538 | 0.333 | 0.385 |
| random | 100 | 100 | 0.176 | 0.168 | 0.193 | 0.281 |
| rank_fusion_proxy | 100 | 100 | 0.469 | 0.479 | 0.333 | 0.362 |
| rule_like_conjunction | 100 | 100 | 0.438 | 0.395 | 0.333 | 0.387 |
| score_union_proxy | 100 | 100 | 0.344 | 0.422 | 0.333 | 0.388 |
| temporal_nms_count | 100 | 100 | 0.438 | 0.468 | 0.333 | 0.358 |
| top_count | 100 | 100 | 0.406 | 0.444 | 0.333 | 0.690 |
| top_ego_path | 100 | 100 | 0.375 | 0.433 | 0.333 | 0.723 |
| top_kinematic | 100 | 100 | 0.125 | 0.048 | 0.000 | 0.329 |
| cheap_union_upper_bound | 200 | 503 | 0.844 | 0.709 | 0.500 | 0.322 |
| random | 200 | 200 | 0.316 | 0.294 | 0.312 | 0.280 |
| rank_fusion_proxy | 200 | 200 | 0.562 | 0.516 | 0.333 | 0.356 |
| rule_like_conjunction | 200 | 200 | 0.656 | 0.554 | 0.333 | 0.345 |
| score_union_proxy | 200 | 200 | 0.500 | 0.490 | 0.333 | 0.388 |
| temporal_nms_count | 200 | 200 | 0.562 | 0.520 | 0.333 | 0.327 |
| top_count | 200 | 200 | 0.625 | 0.551 | 0.333 | 0.347 |
| top_ego_path | 200 | 200 | 0.500 | 0.494 | 0.333 | 0.355 |
| top_kinematic | 200 | 200 | 0.406 | 0.384 | 0.500 | 0.305 |

## Sanity Checks

| check | passes | detail |
| --- | --- | --- |
| full_candidate_pool_recall_one | True | min_event=1.000000; min_clip=1.000000 |
| event_count_nonincreasing_with_gap | True | counts=[61, 32, 29] |
| temporal_nms_no_suppression_matches_top_count | True | gap=-1 disables suppression |
| candidate_sets_unique_and_match_k | True | failures=[] |
| union_coverage_not_below_components | True | failures=[] |
| static_candidate_functions_do_not_reference_labels | True | top_by:none; temporal_nms_count:none; rule_like_conjunction:none; rank_fusion_proxy:none; score_union_proxy:none; random_order:none; proposal:none |
| runtime_selection_view_has_no_label_columns | True | selection view checked |
| learned_methods_marked_reference_only | True | learned scores were trained from pseudo-labels; excluded from decision |

## Interpretation

- Main candidate construction uses only `proxy_scores.csv` and source/time metadata.
- Learned proxy rows are reference-only because the existing learned scores were trained from conservative pseudo-labels.
- Micro coverage measures event reachability; macro and tail coverage diagnose source-video concentration.
- `cheap_union_upper_bound` is the union of non-learned proposal primitives and estimates reachable coverage from the current cheap family.

## Decision Evidence

- gap=0, K=50: best=rank_fusion_proxy top_delta=0.115, macro_delta=-0.115, tail_delta=-0.167, union_delta_vs_best_count_or_nms=0.279
- gap=0, K=100: best=rank_fusion_proxy top_delta=-0.066, macro_delta=0.016, tail_delta=0.000, union_delta_vs_best_count_or_nms=0.164
- gap=0, K=200: best=rule_like_conjunction top_delta=-0.033, macro_delta=-0.015, tail_delta=0.000, union_delta_vs_best_count_or_nms=0.131
- gap=4, K=50: best=rank_fusion_proxy top_delta=0.156, macro_delta=-0.013, tail_delta=0.000, union_delta_vs_best_count_or_nms=0.219
- gap=4, K=100: best=rank_fusion_proxy top_delta=0.062, macro_delta=0.034, tail_delta=0.000, union_delta_vs_best_count_or_nms=0.188
- gap=4, K=200: best=rule_like_conjunction top_delta=0.031, macro_delta=0.003, tail_delta=0.000, union_delta_vs_best_count_or_nms=0.219
- gap=8, K=50: best=rank_fusion_proxy top_delta=0.103, macro_delta=-0.027, tail_delta=0.000, union_delta_vs_best_count_or_nms=0.172
- gap=8, K=100: best=rank_fusion_proxy top_delta=0.103, macro_delta=0.045, tail_delta=0.000, union_delta_vs_best_count_or_nms=0.172
- gap=8, K=200: best=rule_like_conjunction top_delta=0.034, macro_delta=0.011, tail_delta=0.000, union_delta_vs_best_count_or_nms=0.241

## Decision: WEAK GO

- `GO`: strong non-learned coverage gains over `top_count`, better macro/tail coverage, and complementary union coverage at practical K.
- `WEAK GO`: gains exist but are source-concentrated, gap-sensitive, or require large K.
- `NO-GO`: `top_count`/`temporal_nms_count` already matches the cheap union or tail coverage remains poor.

This decision is pseudo-oracle development evidence only; it is not evidence of true risk-event ground-truth recovery.
