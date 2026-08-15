# ACTION_VALUE_TABLE schema

rows=695796 generated=2026-08-14 06:46:37 UTC

| column | dtype | semantics |
|---|---|---|
| video_id | str | see prompt Phase 2 §4/§5 |
| query_id | str | see prompt Phase 2 §4/§5 |
| state_id | str | see prompt Phase 2 §4/§5 |
| decision_idx | int64 | see prompt Phase 2 §4/§5 |
| budget | int64 | see prompt Phase 2 §4/§5 |
| action_set_kind | str | see prompt Phase 2 §4/§5 |
| materializer_version | str | see prompt Phase 2 §4/§5 |
| reference_type | str | see prompt Phase 2 §4/§5 |
| action_id | str | see prompt Phase 2 §4/§5 |
| action_type | str | see prompt Phase 2 §4/§5 |
| candidate_start | float64 | see prompt Phase 2 §4/§5 |
| candidate_end | float64 | see prompt Phase 2 §4/§5 |
| context_length | float64 | see prompt Phase 2 §4/§5 |
| visible_proxy_score | float64 | see prompt Phase 2 §4/§5 |
| visible_proxy_rank | int64 | see prompt Phase 2 §4/§5 |
| visible_distance_to_positive | float64 | see prompt Phase 2 §4/§5 |
| visible_distance_to_negative | float64 | see prompt Phase 2 §4/§5 |
| remaining_budget | int64 | see prompt Phase 2 §4/§5 |
| remaining_budget_fraction | float64 | see prompt Phase 2 §4/§5 |
| queried_fraction | float64 | see prompt Phase 2 §4/§5 |
| verified_positive_count | int64 | see prompt Phase 2 §4/§5 |
| verified_negative_count | int64 | see prompt Phase 2 §4/§5 |
| region_coverage_fraction | float64 | see prompt Phase 2 §4/§5 |
| current_component_count | int64 | see prompt Phase 2 §4/§5 |
| observed_outcome | str | see prompt Phase 2 §4/§5 |
| actual_or_cached_cost | float64 | see prompt Phase 2 §4/§5 |
| visible_new_component_gain | float64 | see prompt Phase 2 §4/§5 |
| visible_redundancy | float64 | see prompt Phase 2 §4/§5 |
| visible_merge_risk | float64 | see prompt Phase 2 §4/§5 |
| visible_boundary_uncertainty | float64 | see prompt Phase 2 §4/§5 |
| visible_uncovered_region_change | float64 | see prompt Phase 2 §4/§5 |
| visible_reward_r0 | float64 | see prompt Phase 2 §4/§5 |
| visible_reward_r1 | float64 | see prompt Phase 2 §4/§5 |
| visible_reward_r2 | float64 | see prompt Phase 2 §4/§5 |
| visible_reward_r3 | float64 | see prompt Phase 2 §4/§5 |
| visible_reward_r4 | float64 | see prompt Phase 2 §4/§5 |
| oracle_eventf1_delta_1step | float64 | see prompt Phase 2 §4/§5 |
| oracle_terminal_delta_topproxy | float64 | see prompt Phase 2 §4/§5 |
| oracle_terminal_delta_relation_greedy | float64 | see prompt Phase 2 §4/§5 |
| oracle_depth2_delta | float64 | see prompt Phase 2 §4/§5 |

## Isolation notes
- visible_* columns are policy-visible; oracle_* columns are evaluator-only.
- observed_outcome comes from the frozen cached label grid (full-information table); online policies never see it.
- reference_type MODEL_RELATIVE = Q_VULNERABLE full-grid C1 reference (validated 252/252);
  MODEL_RELATIVE_PARTIAL_UNION = Q_DRIVER union-known labels, partial reference (diagnostic only).
- No 2s/5s semantic outcomes exist; all units are 10s (context_length=10).
