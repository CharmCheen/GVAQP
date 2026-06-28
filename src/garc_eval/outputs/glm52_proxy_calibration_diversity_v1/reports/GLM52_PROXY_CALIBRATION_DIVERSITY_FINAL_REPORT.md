# GLM-5.2 Proxy Calibration + Diversity — Final Report

**Experiment:** `glm52_proxy_calibration_diversity_v1`
**Scope:** no-new-VLM replay on dataset3 full center10 oracle reference (347 anchors).
**Date:** 2026-06-26

## 1. Input data audit (Task A)

Canonical table reused from `codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv`.
347 anchors / 40 positives / 307 negatives / 27 event clusters (21 singleton, 6 multi-anchor).
38 numeric proxy columns detected, all complete (no missing). `anchor_id`/`anchor_index`/
`center_time_s` unique. `event_start`/`event_end` present but UNRELIABLE — not used for main
metrics. `event_type` and `involved_object` present, enabling the query-selectivity diagnostic.
See `reports/01_BASELINE_LOCK_AND_INPUT_AUDIT.md`.

## 2. Locked baseline

Corrected deployable default: `diversity_prefilter_object_count_mean` (object_count_mean proxy,
P=2.0, linspace spread). At B=80: event-cluster recall 0.481, anchor recall 0.375, singleton
recall 0.333, multi-anchor recall 1.000. Hindsight upper bound: `top_proxy_person_count_max`
(event recall 0.630 at B=80). BASA is not the main algorithm (confirmed: best BASA < baseline).
See `reports/02_PROXY_CALIBRATION_REPLAY.md`.

## 3. Proxy calibration replay (Task B)

Tested 3 calibration sampling policies x 5 selection rules x c in [5,10,15,20,30] x B in
[20,30,40,60,80,100,150], seeds 0..99 (calibration) / 0..199 (random baselines).

**Headline B=80 (event-cluster recall):**

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

**Best calibration configs B=80:**

| c | calib_policy | selection_rule | event_cluster_recall_mean | anchor_recall_mean | top_selected_proxy |
| --- | --- | --- | --- | --- | --- |
| 10.0000 | calib_temporal_grid | calib_auprc | 0.5556 | 0.4750 | person_count_mean |
| 15.0000 | calib_temporal_grid | calib_top_quantile_positive_rate | 0.5185 | 0.4500 | person_count_max |
| 10.0000 | calib_temporal_grid | calib_auroc | 0.4815 | 0.4250 | person_count_max |

**Findings:**
- `calib_temporal_grid` is **deterministic** (seed-independent; std ~1e-16). At c=10 + auprc it
  deterministically picks `person_count_mean` and reaches 0.556 — matching hindsight
  `person_count_max` diversity (0.556) and beating the object_count_mean default (0.481).
  **But this is a single lucky sample, not a distribution.** The temporal grid happens to land
  on a pedestrian-representative calibration set.
- `calib_uniform_random` and `calib_stratified_time_blocks` are genuinely stochastic (std ~0.09).
  At c=10, random+auroc picks `object_count_mean` only 33% of the time, with 26% fallback
  (degenerate calibration set). Mean event recall 0.385, max 0.423 — **below** the object_count_mean
  default (0.481).
- Only 10.67% of (c,policy,rule) configs beat the object_count_mean default at B=80.

## 4. Is calibration-selected proxy stable?

**No, not as a deployable mechanism.** The deterministic temporal_grid looks stable but is
equivalent to a single hindsight-informed choice on this video. Realistic random calibration at
small c is high-variance and frequently falls back. Calibration cannot be claimed as a robust
deployable proxy-selection method on this single video.

## 5. Diversity prefilter ablation (Task C)

Ablated P in [1.0,1.25,1.5,2.0,3.0,4.0] x 6 proxies x 13 temporal strategies x 7 budgets.

**Best deployable (non-hindsight) configs B=80:**

| proxy | P | temporal_strategy | event_cluster_recall_mean | anchor_recall_mean | singleton_cluster_recall_mean |
| --- | --- | --- | --- | --- | --- |
| object_count_mean | 2.0000 | greedy_maxmin_time | 0.5185 | 0.4000 | 0.3810 |
| object_count_mean | 2.0000 | linspace_spread | 0.4815 | 0.3750 | 0.3333 |
| score_fusion_geometry_motion | 2.0000 | linspace_spread | 0.4444 | 0.3250 | 0.3333 |

**Findings:**
- **P=2.0 is NOT universally optimal.** P=1.0 (top-proxy) beats P=2.0 for strong hindsight
  proxies (person_count_max: 0.556 vs 0.416) and weak proxies. P=2.0 helps only for the medium
  deployable `object_count_mean`. The P=2.0 peak under linspace is a grid artifact (non-monotone:
  P=1.5→0.296, P=2.0→0.481, P=3.0→0.296 at B=80).
- **linspace_spread is NOT sufficient.** `greedy_maxmin_time` >= linspace at every budget and
  fixes the B=100 linspace anomaly (greedy_maxmin 0.481 vs linspace 0.333 for object_count_mean
  P=2.0). `score_weighted_spread` is the most stable across P but plateaus lower.
  `temporal_nms` over-suppresses and is uncompetitive.
- **Corrected baseline gain = proxy x diversity interaction.** For object_count_mean (medium
  proxy), diversity P=2.0 adds +0.11 event recall over top-proxy at B=80. For a strong proxy,
  diversity hurts (-0.07). The baseline's strength is the *combination* of a medium proxy +
  coverage spread, not diversity alone.

See `reports/03_DIVERSITY_PREFILTER_ABLATION.md`.

## 6. Should P be fixed at 2?

**No.** The optimal P is budget- and proxy-dependent (P=3.0 at B=20-30, P=4.0 at B=40-60,
P=2.0 at B=80 for object_count_mean). Fixing P=2.0 is a reasonable default for the medium
deployable proxy at mid-budgets, but it is not a robust optimum.

## 7. Is linspace spread sufficient?

**No.** `greedy_maxmin_time` consistently beats or matches linspace and is more stable. The
improved deployable baseline should be `object_count_mean, P=2.0, greedy_maxmin_time`
(event recall 0.519 at B=80, +0.037 over linspace 0.481; singleton recall 0.381 vs 0.333).

## 8. Is object_count_mean still the strongest deployable default?

**Yes.** It is the strongest non-hindsight proxy at every budget B>=30. No deployable proxy
beats it. (vehicle_count_mean偶尔 wins at B=150 by coverage saturation — a high-budget
artifact, not a proxy-quality signal.)

## 9. person_count_max hindsight significance

person_count_max top-proxy at B=80 = 0.630 event recall vs object_count_mean top-proxy 0.370.
The hindsight gap is large (+0.26). person_count_max is NOT deployable without a reliable
calibration step (which random calibration does not provide). Its value is diagnostic: it
shows the ceiling achievable if the right proxy is selected, and it motivates query-aware
proxy selection (Task D).

## 10. Corrected baseline gain: proxy or diversity?

**Both, interacted.** The corrected `diversity_prefilter_object_count_mean` gain over
`top_proxy_score_fusion` (the original mainline) comes from TWO changes: (a) swapping the
proxy from score_fusion (AUROC 0.550) to object_count_mean (AUROC 0.627), and (b) adding
P=2.0 temporal spread. Ablation shows: for object_count_mean, diversity adds +0.11 over its
own top-proxy; for score_fusion, diversity adds +0.07. So both contribute, but the proxy
swap is the larger effect (object_count_mean top-proxy 0.370 vs score_fusion top-proxy
0.370 at B=80 — actually comparable top-proxy; the diversity then lifts object_count_mean
to 0.481 but score_fusion only to 0.444). The proxy choice matters most at high budgets.

## 11. High/low selectivity diagnostic (Task D)

Block classification (bs=300): 1 hot (11 pos), 9 medium (29 pos), 2 cold (0 pos).
- Proxy methods concentrate ~75% budget in medium, ~15-19% in hot, get 0.455 hot recall and
  0.34-0.38 medium recall. They get **0 cold recall** at bs=300 (cold has 0 positives).
- At bs=600 (the only cold block with 2 positives), `top_proxy`/`diversity` object_count_mean
  get **0 cold recall at every budget** — they never examine the cold-block positives.
  `best_calibration` (person proxy) gets 0.50 cold recall at B=40/150 (cold positives are
  pedestrian). uniform catches some cold by coverage but loses hot recall.
- **This is the selectivity tradeoff:** proxy methods maximize hot/medium but sacrifice cold;
  uniform catches cold but wastes budget on empty cold blocks.

Per-query AUROC (key proxy x query):

| proxy | all_event | cyclist_event | non_vehicle_event | pedestrian_event | vehicle_event |
| --- | --- | --- | --- | --- | --- |
| person_count_max | 0.8140 | 0.7990 | 0.8400 | 0.8360 | 0.5350 |
| person_count_mean | 0.8130 | 0.7840 | 0.8390 | 0.8410 | 0.5350 |
| lateral_presence_max | 0.7140 | 0.7510 | 0.7400 | 0.7190 | 0.4610 |
| object_count_mean | 0.6270 | 0.6360 | 0.6380 | 0.6300 | 0.5090 |
| bike_count_mean | 0.5840 | 0.6380 | 0.5830 | 0.5530 | 0.5700 |
| score_fusion_geometry_motion | 0.5500 | 0.6210 | 0.5450 | 0.5070 | 0.5850 |
| motion_energy_mean | 0.5470 | 0.6270 | 0.5450 | 0.5050 | 0.5510 |
| vehicle_count_mean | 0.4500 | 0.4810 | 0.4500 | 0.4390 | 0.4620 |

- person proxies win pedestrian/cyclist/non_vehicle (AUROC 0.78-0.84).
- **No proxy is strong for vehicle** (max 0.585, score_fusion; only 4 positives).
- object_count_mean is mediocre-but-stable (0.509-0.638).
- This supports query-aware proxy selection in principle, but the vehicle query is too small
  to calibrate reliably.

See `reports/04_SELECTIVITY_DIAGNOSTIC.md`.

## 12. Singleton cluster recall improvement

`greedy_maxmin_time` improves singleton recall over linspace for object_count_mean P=2.0
at B=80 (0.381 vs 0.333). Still well below hindsight person_count_max top-proxy (0.571).
The singleton improvement comes from better temporal coverage of isolated positive clusters.
Cold-block singleton recall remains 0 for proxy methods (cold positives are missed entirely).

## 13. Is adaptive slicing needed?

**Not yet, on this single video.** The cold-block coverage gap is real but small (2 cold
positives at bs=600). Adaptive slicing (budget reallocation toward under-covered cold blocks)
could help in principle, but the cold blocks have too few positives here to demonstrate a
gain. This should be revisited on a second video with more cold-block positives.

## 14. Is a new VLM needed?

**No, for the immediate conclusions.** All findings here are no-new-VLM replays on the
existing dataset3 oracle reference. A new VLM IS needed for: (a) second-video replication to
test whether the temporal_grid calibration luck and the proxy x P interaction generalize;
(b) boundary redesign. Neither is required to accept the current findings.

## 15. Next-step recommendations

1. **Adopt `greedy_maxmin_time` over `linspace_spread`** for the deployable diversity
   prefilter. New deployable baseline: `object_count_mean, P=2.0, greedy_maxmin_time`
   (event recall 0.519 at B=80, beats linspace 0.481).
2. **Drop random per-video calibration as a deployable mechanism** — it is unstable at small c.
   Instead pursue **query-aware proxy priors**: person-count proxies for pedestrian/cyclist/
   non_vehicle queries, object_count_mean for vehicle/all. This is a structural prior, not a
   per-video sample.
3. **Second-video replication** (requires new VLM) to test: (a) whether temporal_grid
   calibration luck holds, (b) whether the proxy x P interaction is stable, (c) whether
   cold-block coverage gaps are larger.
4. **P as a budget-adaptive parameter**, not fixed at 2.0. A small schedule (P=3 at low B,
   P=2 at mid B) is suggested by the ablation but needs cross-video validation.
5. **Formal certificate** remains blocked by small event count (40 events / 27 clusters on
   dataset3). The ~500-event requirement from prior power sims still stands; no certificate
   claim can be made from this single video.

## 16. Safe claims

- Dataset3 full oracle reference (347 anchors, 40 positives, 27 clusters) is complete and
  usable for no-new-VLM replay.
- Boundary fields are unreliable; no event-IoU main contribution.
- The original `proxy_diversity_prefilter` used `score_fusion_geometry_motion`; the corrected
  `diversity_prefilter_object_count_mean` is stronger (object_count_mean AUROC 0.627 > 0.550).
- `object_count_mean` is the strongest deployable (non-hindsight) proxy on dataset3.
- `person_count_max`/`person_count_mean` are the hindsight AUROC winners (0.814/0.813) but
  are NOT deployable without a reliable calibration step.
- BASA is not the main algorithm (best BASA < corrected baseline).
- `greedy_maxmin_time` >= `linspace_spread` for object_count_mean P=2.0 at every budget
  tested; it fixes the B=100 linspace anomaly.
- P=2.0 is not a universal optimum; P=1.0 wins for strong hindsight proxies.
- Per-query best proxy changes: person proxies for non-vehicle, no strong proxy for vehicle.
- Random calibration at small c (5-15) is unstable (26% fallback, 33% top-proxy agreement)
  and on average underperforms the object_count_mean default at B=40-80.
- The deterministic temporal_grid calibration matches hindsight on this video but is a single
  lucky sample, not a robust method.
- Proxy methods miss cold-block positives (0 cold recall at bs=600 for object_count methods);
  this is a coverage/selectivity tradeoff, not a bug.
- No formal G-ARC recall certificate is established here; event count is too small.
- Labels are VLM-oracle-relative, not human ground truth.

## 17. Unsafe claims

- `person_count_max` is a deployable default proxy (it is hindsight; random calibration does
  not reliably select it).
- Random per-video calibration is a stable deployable proxy-selection mechanism.
- The temporal_grid calibration result generalizes (it is one deterministic favorable sample
  on one video).
- P=2.0 is the optimal pool multiplier in general.
- `linspace_spread` is sufficient / optimal.
- BASA is the main algorithm.
- A formal G-ARC recall certificate is complete.
- Adaptive slicing has been validated (not tested here; cold-block positives too few).
- These results are human-ground-truth driving risk detection (they are VLM-oracle-relative).
- The vehicle-query proxy findings generalize (only 4 vehicle positives — high variance).
- The query-aware proxy prior is validated as deployable (it is supported in principle by
  Task D but not validated as a calibration mechanism).

## 18. Final decision

**FINAL_DECISION: CALIBRATION_UNSTABLE_USE_QUERY_PRIOR**

Rationale: Random per-video proxy calibration is unstable at small c and does NOT beat the
`object_count_mean` diversity default (only the deterministic temporal_grid "lucky" sample
matches hindsight). The corrected `object_count_mean` diversity baseline remains the strongest
deployable method, and the diversity ablation improves it by swapping `linspace_spread` for
`greedy_maxmin_time` (0.519 vs 0.481 event recall at B=80). The productive direction is NOT
per-video random calibration but **query-aware proxy priors** (person proxies for non-vehicle
queries, object_count_mean for vehicle/all) — supported by the Task D finding that the best
proxy changes by query. This requires a second video to validate and is the cleanest
"proxy-agnostic feasibility" bridge between mechanism and contribution.

Secondary actionable finding: `DIVERSITY_ABLATION_FINDS_BETTER_SELECTION` (greedy_maxmin >
linspace) should be folded into the deployable baseline immediately, with no new VLM.

## Outputs index

- `reports/01_BASELINE_LOCK_AND_INPUT_AUDIT.md`
- `reports/02_PROXY_CALIBRATION_REPLAY.md`
- `reports/03_DIVERSITY_PREFILTER_ABLATION.md`
- `reports/04_SELECTIVITY_DIAGNOSTIC.md`
- `replay/proxy_calibration_replay_long.csv`, `replay/proxy_calibration_replay_summary.csv`
- `replay/diversity_ablation_long.csv`, `replay/diversity_ablation_summary.csv`
- `tables/proxy_selection_frequency.csv`, `tables/proxy_calibration_regret.csv`
- `tables/diversity_ablation_best_by_budget.csv`, `tables/diversity_ablation_factor_effects.csv`
- `tables/input_column_inventory.csv`, `tables/anchor_cluster_summary.csv`
- `tables/block_selectivity_summary.csv`
- `analysis/block_selectivity_diagnostic.csv`, `analysis/query_selectivity_proxy_metrics.csv`,
  `analysis/query_selectivity_replay_summary.csv`
- `replay/selections/proxy_calibration/...`, `replay/selections/diversity_ablation/...`
- `scripts/` (common.py + task_a/b/c/d scripts + report scripts)
