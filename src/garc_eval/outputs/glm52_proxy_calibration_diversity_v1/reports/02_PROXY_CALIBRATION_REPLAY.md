# 02 Proxy Calibration Replay

## Setup

- Budgets B in [20,30,40,60,80,100,150]; calibration budget c in [5,10,15,20,30] (skip c>=B).
- Execution budget = B - c; calibration anchors drawn from all anchors and excluded from execution pool.
- Calibration sampling: `calib_uniform_random`, `calib_temporal_grid`, `calib_stratified_time_blocks`.
- Proxy selection rules: `calib_auroc`, `calib_auprc`, `calib_top_quantile_positive_rate`, `calib_topk_yield`, `calib_spearman`.
- Selected proxy drives diversity prefilter (top-PB by proxy, P=2.0, linspace spread, B-c execution anchors).
- Calibration method uses seeds 0..99 (200 was too slow; per task spec reduction allowed with note).
- Random baselines use seeds 0..199. Calibration labels simulated from existing VLM oracle reference. No new VLM.
- Core calibration candidate set: 25 distinct cheap features.
- Fallback on degenerate calibration set (all-pos/all-neg): `object_count_mean`.

## Baseline ranking at B=80 (event-cluster recall)

| method | event_cluster_recall_mean | anchor_recall_mean | singleton_cluster_recall_mean | multi_anchor_cluster_recall_mean |
| --- | --- | --- | --- | --- |
| top_proxy_person_count_max_hindsight | 0.6296 | 0.6750 | 0.5714 | 0.8333 |
| diversity_prefilter_person_count_max_hindsight | 0.5556 | 0.4500 | 0.4762 | 0.8333 |
| diversity_prefilter_object_count_mean | 0.4815 | 0.3750 | 0.3333 | 1.0000 |
| diversity_prefilter_score_fusion_geometry_motion | 0.4444 | 0.3250 | 0.3333 | 0.8333 |
| calibration_selected_diversity_prefilter | 0.3849 | 0.3151 | 0.2788 | 0.7561 |
| top_proxy_object_count_mean | 0.3704 | 0.3750 | 0.2857 | 0.6667 |
| top_proxy_score_fusion_geometry_motion | 0.3704 | 0.2500 | 0.3333 | 0.5000 |
| random_proxy_selected_diversity_prefilter | 0.3017 | 0.2305 | 0.2298 | 0.5533 |
| uniform_random | 0.2846 | 0.2283 | 0.2333 | 0.4642 |
| uniform_temporal_grid | 0.2593 | 0.2000 | 0.1905 | 0.5000 |

## Best calibration config per budget

| budget | c | calib_policy | selection_rule | event_cluster_recall_mean | anchor_recall_mean | singleton_cluster_recall_mean | multi_anchor_cluster_recall_mean | top_selected_proxy | fallback_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | 5.0000 | calib_temporal_grid | calib_spearman | 0.2222 | 0.1500 | 0.1905 | 0.3333 | bike_count_mean | 0.0000 |
| 30 | 10.0000 | calib_temporal_grid | calib_top_quantile_positive_rate | 0.3333 | 0.2500 | 0.1905 | 0.8333 | person_count_max | 0.0000 |
| 40 | 10.0000 | calib_temporal_grid | calib_auprc | 0.4074 | 0.3500 | 0.2857 | 0.8333 | person_count_mean | 0.0000 |
| 60 | 30.0000 | calib_temporal_grid | calib_top_quantile_positive_rate | 0.4815 | 0.4250 | 0.4286 | 0.6667 | person_count_mean | 0.0000 |
| 80 | 10.0000 | calib_temporal_grid | calib_auprc | 0.5556 | 0.4750 | 0.4286 | 1.0000 | person_count_mean | 0.0000 |
| 100 | 15.0000 | calib_temporal_grid | calib_top_quantile_positive_rate | 0.6296 | 0.5000 | 0.5714 | 0.8333 | person_count_max | 0.0000 |
| 150 | 5.0000 | calib_temporal_grid | calib_topk_yield | 0.6667 | 0.5750 | 0.6190 | 0.8333 | score_fusion_geometry_motion | 0.0000 |

## Key Finding 1 — `calib_temporal_grid` is deterministic and "lucky"

The temporal-grid calibration sample is seed-independent (linspace by anchor_index), so proxy
selection is fixed across all 100 seeds. Standard deviation is ~1e-16 (effectively zero):

| calib_policy | selection_rule | event_cluster_recall_mean | event_cluster_recall_std | top_selected_proxy | top_proxy_freq |
| --- | --- | --- | --- | --- | --- |
| calib_stratified_time_blocks | calib_auprc | 0.4059 | 0.0909 | object_count_mean | 39.0000 |
| calib_stratified_time_blocks | calib_auroc | 0.4070 | 0.0973 | object_count_mean | 35.0000 |
| calib_stratified_time_blocks | calib_spearman | 0.3911 | 0.1101 | object_count_mean | 26.0000 |
| calib_stratified_time_blocks | calib_top_quantile_positive_rate | 0.4059 | 0.0688 | object_count_mean | 47.0000 |
| calib_stratified_time_blocks | calib_topk_yield | 0.3852 | 0.0521 | score_fusion_geometry_motion | 75.0000 |
| calib_temporal_grid | calib_auprc | 0.5556 | 0.0000 | person_count_mean | 100.0000 |
| calib_temporal_grid | calib_auroc | 0.4815 | 0.0000 | person_count_max | 100.0000 |
| calib_temporal_grid | calib_spearman | 0.4815 | 0.0000 | person_count_max | 100.0000 |
| calib_temporal_grid | calib_top_quantile_positive_rate | 0.4815 | 0.0000 | person_count_max | 100.0000 |
| calib_temporal_grid | calib_topk_yield | 0.3333 | 0.0000 | score_fusion_geometry_motion | 100.0000 |
| calib_uniform_random | calib_auprc | 0.3981 | 0.0880 | object_count_mean | 33.0000 |
| calib_uniform_random | calib_auroc | 0.4056 | 0.0888 | object_count_mean | 33.0000 |
| calib_uniform_random | calib_spearman | 0.3819 | 0.1047 | object_count_mean | 27.0000 |
| calib_uniform_random | calib_top_quantile_positive_rate | 0.3978 | 0.0729 | object_count_mean | 42.0000 |
| calib_uniform_random | calib_topk_yield | 0.3663 | 0.0529 | score_fusion_geometry_motion | 74.0000 |

At c=10, temporal_grid + auprc deterministically selects `person_count_mean` and reaches
event recall 0.5556 at B=80 — matching the hindsight `person_count_max` diversity prefilter
(0.5556) and exceeding the `object_count_mean` diversity default (0.4815).

**This is a single deterministic outcome, not a distribution over 100 independent runs.**
The temporal grid happens to land on a calibration set that captures the pedestrian-heavy
positives, so AUROC/AUPRC reliably identifies the person-count proxy. This is suggestive but
not a robust deployable claim — it is one favorable sample, equivalent to a hindsight-informed
choice on this specific video.

## Key Finding 2 — random/stratified calibration at small c is unstable

At c=10, `calib_uniform_random` + `calib_auroc` selects `object_count_mean` only 33% of the
time, `person_count_mean` 20%, and scatters across 9+ other proxies:

| calib_policy | selection_rule | c | proxy | seeds_selected |
| --- | --- | --- | --- | --- |
| calib_uniform_random | calib_auroc | 10 | object_count_mean | 231 |
| calib_uniform_random | calib_auroc | 10 | person_count_mean | 140 |
| calib_uniform_random | calib_auroc | 10 | score_fusion_geometry_motion | 56 |
| calib_uniform_random | calib_auroc | 10 | object_count_max | 49 |
| calib_uniform_random | calib_auroc | 10 | motorcycle_count_mean | 42 |
| calib_uniform_random | calib_auroc | 10 | person_count_max | 42 |

Mean event recall for random/stratified calibration at B=80 is ~0.40 (std ~0.09), with
max ~0.42 — **below** the `object_count_mean` diversity default (0.4815). Fallback rate is
~26% (calibration set all-positive or all-negative at c=10).

## Key Finding 3 — calibration rarely beats the deployable default

| budget | frac_beat_default | best_calib_event_recall | default_event_recall | hindsight_event_recall |
| --- | --- | --- | --- | --- |
| 20.0000 | 0.5111 | 0.2222 | 0.1481 | 0.3333 |
| 30.0000 | 0.5833 | 0.3333 | 0.1852 | 0.3333 |
| 40.0000 | 0.2400 | 0.4074 | 0.2593 | 0.3333 |
| 60.0000 | 0.2400 | 0.4815 | 0.3333 | 0.5185 |
| 80.0000 | 0.1067 | 0.5556 | 0.4815 | 0.5556 |
| 100.0000 | 0.9733 | 0.6296 | 0.3333 | 0.5185 |
| 150.0000 | 0.1733 | 0.6667 | 0.6667 | 0.5185 |

At B=40-80, only 10-24% of (c, policy, rule) configurations beat the `object_count_mean`
diversity default. The exceptions are B=100 (where the default itself drops to 0.333 due to a
linspace/tie-breaking anomaly — see Task C) and the deterministic temporal_grid peaks.

## Proxy selection frequency highlights

- `calib_temporal_grid` c=10 + auroc → `person_count_max` 700/700 (100%).
- `calib_temporal_grid` c=10 + auprc → `person_count_mean` 700/700 (100%).
- `calib_uniform_random` c=5 + auroc → `object_count_mean` 469/700 (67%), then scattered.

Full table: `tables/proxy_selection_frequency.csv`.

## Regret vs hindsight and default

- Best calibration (temporal_grid c=10 auprc, B=80): regret_vs_hindsight = 0.0000 (matches
  hindsight person proxy diversity); regret_vs_default = -0.0741 (beats default).
- Worst calibration (temporal_grid c=5 spearman, B=80): regret_vs_default = +0.370 (picks a
  bad proxy deterministically).
- Random calibration mean regret_vs_default at B=80 ≈ +0.08 (worse than default on average).

Full table: `tables/proxy_calibration_regret.csv`.

## Answers to core questions (Task B)

1. **Can a small calibration set auto-select an effective cheap proxy?**
   Only with a *representative* calibration set. The deterministic temporal grid does, but
   realistic random sampling at c=5-15 is unstable (33-67% top-proxy agreement, 26% fallback)
   and on average does NOT beat the `object_count_mean` default.
2. **Does calibration-selected diversity beat the corrected baseline?**
   The single best deterministic config matches hindsight and beats the default, but the
   *expected* calibration outcome (random sampling) underperforms the `object_count_mean`
   diversity default at B=40-80.
3. **Is calibration stable enough to deploy?**
   No — on this single video, random calibration is too noisy at small c. The temporal_grid
   result is deterministic but equivalent to a lucky single sample, not a robust method.

## Limitations

- Single video (dataset3); calibration stability may differ on a second video.
- Calibration labels are the existing VLM pseudo-oracle, not human truth.
- Core candidate set excludes redundant duplicates but still has 25 features; small-c
  AUROC over 25 candidates is high-variance.
- The `object_count_mean` diversity default at B=100 in this replay is 0.333 (vs 0.481 in the
  codex replay) due to proxy-score tie-breaking in top-PB pool construction — a robustness
  issue for linspace spread, documented in Task C.

## Outputs

- `replay/proxy_calibration_replay_long.csv` (per-run, 50849 rows)
- `replay/proxy_calibration_replay_summary.csv`
- `tables/proxy_selection_frequency.csv`
- `tables/proxy_calibration_regret.csv`
- `replay/selections/proxy_calibration/...` (saved per-method selections)
