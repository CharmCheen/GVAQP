# 03 Corrected Budget Replay

## Method Coverage

Replay uses budgets [10, 20, 30, 40, 60, 80, 100, 150] and seeds 0..199 for random/hybrid/audit/calibrated methods. Every method/B/seed selection is saved under `replay/selections/`.

## Key Winners

| budget | best_overall_method | best_overall_event_recall | best_deployable_method | best_deployable_event_recall | best_deployable_anchor_recall |
| --- | --- | --- | --- | --- | --- |
| 30 | cluster_aware_upper_bound | 1.0000 | uniform_temporal_grid | 0.2593 | 0.1750 |
| 40 | cluster_aware_upper_bound | 1.0000 | diversity_prefilter_object_count_mean | 0.2593 | 0.2000 |
| 60 | cluster_aware_upper_bound | 1.0000 | top_proxy_object_count_mean | 0.3333 | 0.3000 |
| 80 | cluster_aware_upper_bound | 1.0000 | diversity_prefilter_object_count_mean | 0.4444 | 0.3500 |

## Average Rank

Best deployable average rank across budgets: `diversity_prefilter_object_count_mean`.

At B=80, best deployable corrected replay method is `diversity_prefilter_object_count_mean` with event-cluster recall 0.444 and anchor recall 0.350.

`cluster_aware_upper_bound` is oracle-informed and excluded from deployable winners. `top_proxy_best_hindsight` is diagnostic and excluded from deployable winners.

See `replay/budget_replay_corrected_long.csv`, `replay/budget_replay_corrected_summary.csv`, and `replay/method_by_budget_winners.csv`.
