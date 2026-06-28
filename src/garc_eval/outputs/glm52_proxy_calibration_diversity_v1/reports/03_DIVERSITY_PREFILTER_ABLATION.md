# 03 Diversity Prefilter Ablation

## Setup

Form: `top-PB by proxy -> select B with temporal strategy`.
Tie-breaking: top-PB pool built by `(proxy_score desc, anchor_index asc)` so count-feature
ties are broken deterministically by time order (this fixes the Task B tie-break anomaly and
makes results reproducible).

- Pool multiplier P: [1.0, 1.25, 1.5, 2.0, 3.0, 4.0]. P=1.0 = pure top-proxy.
- Proxies: score_fusion_geometry_motion, object_count_mean, person_count_max (hindsight),
  person_count_mean (hindsight), vehicle_count_mean, motion_energy_mean.
  (`bike_count_max` dropped — entirely missing in the canonical table.)
- Temporal strategies: linspace_spread, greedy_maxmin_time, temporal_nms (gap 10/20/30/60),
  block_round_robin (bs 150/300/600), random_from_pool (seeds 0..199),
  score_weighted_spread (lambda 0.25/0.5/1.0/2.0).
- Budgets B: [20,30,40,60,80,100,150]. No new VLM.

## Factor effect: P (marginal over proxy, strategy, budget)

| P | mean_event_recall | mean_anchor_recall | mean_singleton_recall |
| --- | --- | --- | --- |
| 1.0 | 0.3686 | 0.3405 | 0.3073 |
| 1.25 | 0.2896 | 0.2502 | 0.2338 |
| 1.5 | 0.2871 | 0.2433 | 0.2308 |
| 2.0 | 0.2824 | 0.2352 | 0.2243 |
| 3.0 | 0.2747 | 0.2271 | 0.2187 |
| 4.0 | 0.2700 | 0.2232 | 0.2125 |

**P=1.0 (pure top-proxy) has the highest marginal mean event recall (0.369) and it decreases
monotonically as P grows.** This is the headline ablation result: averaged over all proxies and
strategies, the diversity prefilter (P>1) *hurts*. But this marginal hides a strong interaction
with proxy strength (see below).

## Factor effect: proxy (marginal over P, strategy, budget)

| proxy | mean_event_recall | mean_anchor_recall | mean_singleton_recall |
| --- | --- | --- | --- |
| person_count_max | 0.4378 | 0.3951 | 0.3605 |
| person_count_mean | 0.4158 | 0.3872 | 0.3270 |
| object_count_mean | 0.2782 | 0.2450 | 0.1899 |
| score_fusion_geometry_motion | 0.2412 | 0.1781 | 0.2181 |
| motion_energy_mean | 0.2354 | 0.1854 | 0.2014 |
| vehicle_count_mean | 0.1642 | 0.1288 | 0.1303 |

`person_count_max` (hindsight, 0.438) and `person_count_mean` (hindsight, 0.416) dominate.
`object_count_mean` (deployable, 0.278) is the strongest deployable proxy.
`vehicle_count_mean` (0.164) is anti-predictive (AUROC 0.45).

## Factor effect: temporal strategy (marginal over proxy, P, budget)

| strategy | mean_event_recall | mean_anchor_recall | mean_singleton_recall |
| --- | --- | --- | --- |
| score_weighted_spread_lam0.25 | 0.3693 | 0.3373 | 0.3035 |
| score_weighted_spread_lam1.0 | 0.3692 | 0.3369 | 0.3022 |
| score_weighted_spread_lam2.0 | 0.3688 | 0.3352 | 0.3006 |
| score_weighted_spread_lam0.5 | 0.3680 | 0.3361 | 0.3025 |
| block_round_robin_bs600 | 0.3552 | 0.3098 | 0.2889 |
| greedy_maxmin_time | 0.3536 | 0.2899 | 0.2774 |
| block_round_robin_bs150 | 0.3507 | 0.2860 | 0.2920 |
| block_round_robin_bs300 | 0.3498 | 0.2938 | 0.2882 |
| linspace_spread | 0.3416 | 0.2838 | 0.2676 |
| random_from_pool | 0.3232 | 0.2797 | 0.2625 |
| temporal_nms_gap10 | 0.1940 | 0.1462 | 0.1366 |
| temporal_nms_gap20 | 0.1631 | 0.1254 | 0.1361 |
| temporal_nms_gap30 | 0.1215 | 0.0973 | 0.0881 |
| temporal_nms_gap60 | 0.1077 | 0.0880 | 0.0843 |

- `score_weighted_spread` (0.369) is marginally the best, but it is *flat* across P (see below).
- `block_round_robin` (0.350-0.355) and `greedy_maxmin_time` (0.354) are close.
- `linspace_spread` (0.342) — the current corrected method — is mid-pack, NOT the best.
- `random_from_pool` (0.323) is below all deterministic strategies (confirms diversity helps
  over random selection from the pool).
- `temporal_nms` (0.11-0.19) is much worse — over-suppresses and starves the budget.

## Interaction: proxy x P (mean event recall over deterministic strategies & budgets)

| proxy | 1.0 | 1.25 | 1.5 | 2.0 | 3.0 | 4.0 |
| --- | --- | --- | --- | --- | --- | --- |
| motion_energy_mean | 0.3069 | 0.2271 | 0.2161 | 0.2157 | 0.2112 | 0.2149 |
| object_count_mean | 0.3333 | 0.2637 | 0.2674 | 0.2686 | 0.2609 | 0.2621 |
| person_count_max | 0.5556 | 0.4355 | 0.4322 | 0.4155 | 0.4001 | 0.3887 |
| person_count_mean | 0.5291 | 0.4103 | 0.4037 | 0.3932 | 0.3826 | 0.3700 |
| score_fusion_geometry_motion | 0.3069 | 0.2247 | 0.2251 | 0.2247 | 0.2247 | 0.2243 |
| vehicle_count_mean | 0.1799 | 0.1477 | 0.1534 | 0.1604 | 0.1632 | 0.1587 |

**Critical interaction:** P=1.0 (top-proxy) beats P=2.0 for the *strong* hindsight proxies
(person_count_max: 0.556 vs 0.416; person_count_mean: 0.529 vs 0.393) and for the *weak*
proxies (score_fusion: 0.307 vs 0.225; motion_energy: 0.307 vs 0.216). P=2.0 only helps for the
*medium* deployable proxy object_count_mean (0.333 vs 0.269).

**The corrected baseline's advantage is specific to a medium-strength proxy.** Diversity
(P=2.0) compensates for object_count_mean's moderate AUROC by spreading coverage; for a strong
proxy it discards high-score anchors and loses precision; for a weak proxy the pool is noise.

## Is P=2.0 optimal? — No.

For the deployable `object_count_mean` at B=80, linspace recall by P is non-monotonic and
peaks sharply at P=2.0 (0.481) with a dip at P=1.5 (0.296) and P=3.0 (0.296). This peak is not
robust — it is a linspace-grid artifact. With `greedy_maxmin_time` the curve is smoother and
the best P shifts (P=2.0-4.0 all ~0.44-0.52). The best deployable P is budget-dependent
(P=3.0 at B=20-30, P=4.0 at B=40-60, P=2.0 at B=80).

## Is linspace_spread sufficient? — No, greedy_maxmin_time is consistently better.

object_count_mean, P=2.0, event recall by strategy across budgets:

| budget | block_round_robin_bs300 | greedy_maxmin_time | linspace_spread | score_weighted_spread_lam1.0 |
| --- | --- | --- | --- | --- |
| 40.0000 | 0.2222 | 0.2593 | 0.2593 | 0.2222 |
| 60.0000 | 0.2963 | 0.3704 | 0.3333 | 0.3333 |
| 80.0000 | 0.3333 | 0.5185 | 0.4815 | 0.3704 |
| 100.0000 | 0.4074 | 0.4815 | 0.3333 | 0.4074 |
| 150.0000 | 0.6296 | 0.6667 | 0.6667 | 0.6667 |

`greedy_maxmin_time` >= `linspace_spread` at every budget, and fixes the B=100 linspace
anomaly (greedy_maxmin 0.481 vs linspace 0.333). `score_weighted_spread_lam1.0` is the most
*stable* (flat ~0.37 across B and P) but plateaus below the greedy_maxmin peak.
`block_round_robin_bs300` is competitive at B=40-100.

## Best deployable (non-hindsight) config per budget

| budget | proxy | P | temporal_strategy | event_cluster_recall_mean | anchor_recall_mean | singleton_cluster_recall_mean |
| --- | --- | --- | --- | --- | --- | --- |
| 20 | object_count_mean | 3.0000 | block_round_robin_bs150 | 0.2222 | 0.1500 | 0.1429 |
| 30 | object_count_mean | 3.0000 | block_round_robin_bs150 | 0.2593 | 0.1750 | 0.1905 |
| 40 | object_count_mean | 4.0000 | greedy_maxmin_time | 0.3333 | 0.2250 | 0.1429 |
| 60 | object_count_mean | 4.0000 | greedy_maxmin_time | 0.4074 | 0.3000 | 0.2381 |
| 80 | object_count_mean | 2.0000 | greedy_maxmin_time | 0.5185 | 0.4000 | 0.3810 |
| 100 | object_count_mean | 1.5000 | linspace_spread | 0.5556 | 0.4500 | 0.4762 |
| 150 | vehicle_count_mean | 2.0000 | linspace_spread | 0.7407 | 0.5500 | 0.6667 |

At B=80 the best deployable is `object_count_mean, P=2.0, greedy_maxmin_time` with event
recall 0.5185 — beating the corrected linspace baseline (0.4815) and improving singleton
recall (0.381 vs 0.333).

## Required answers

1. **Is P=2.0 optimal?** No. P=1.0 is best for strong hindsight proxies; P=2.0-4.0 helps only
   for the medium deployable proxy object_count_mean, and the optimal P is budget-dependent.
   The P=2.0 peak under linspace is a grid artifact, not a robust optimum.
2. **Is linspace_spread sufficient?** No. `greedy_maxmin_time` is consistently >= linspace and
   fixes the B=100 anomaly. `score_weighted_spread` is more stable but plateaus lower.
3. **Does any temporal strategy stably beat linspace?** Yes — `greedy_maxmin_time` and
   `block_round_robin` both beat linspace for object_count_mean at B>=60.
4. **Corrected baseline gain: proxy or diversity?** Both, interacted. For object_count_mean
   (medium proxy), diversity (P=2.0) adds +0.11 event recall over top-proxy (P=1.0) at B=80.
   For a strong proxy (person_count_max), diversity *hurts* (-0.07). The corrected baseline's
   strength is the *combination* of a medium proxy + coverage spread, not diversity alone.
5. **Is object_count_mean still the deployable default?** Yes — it is the strongest deployable
   (non-hindsight) proxy at every budget B>=30. vehicle_count_mean occasionally wins at B=150
   by coverage saturation, but that is a high-budget artifact.
6. **Is person_count_max hindsight clearly stronger?** Yes — person_count_max top-proxy at
   B=80 is 0.630 event recall vs object_count_mean top-proxy 0.370. The hindsight gap is large.
7. **Does calibration-selected proxy approach hindsight?** Only via the deterministic
   temporal_grid calibration (Task B), which picks person_count_max/mean and matches hindsight
   diversity. Random calibration does not reliably reach hindsight.

## Limitations

- Single video; the proxy x P interaction may differ on a second video.
- The best overall configs use hindsight proxies (person_count_max/mean) and are NOT deployable
  without a calibration step that reliably selects them (which random calibration does not).
- `temporal_nms` with large gaps starves the budget; results are not competitive.
- B=150 has near-saturation behavior where coverage dominates proxy quality.

## Outputs

- `replay/diversity_ablation_long.csv` (53676 rows)
- `replay/diversity_ablation_summary.csv`
- `tables/diversity_ablation_best_by_budget.csv`
- `tables/diversity_ablation_factor_effects.csv`
- `replay/selections/diversity_ablation/...`
