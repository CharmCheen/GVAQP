# 04 Selectivity Diagnostic

## 6.1 Block-level selectivity

Block classification by positive rate: hot (>=20%), medium (5-20%), cold (<5%).

| block_size | selectivity_class | n_blocks | n_anchors | n_positives | mean_positive_rate |
| --- | --- | --- | --- | --- | --- |
| 150 | hot | 6 | 90 | 25 | 0.2778 |
| 150 | medium | 8 | 120 | 15 | 0.1250 |
| 150 | cold | 10 | 137 | 0 | 0.0000 |
| 300 | hot | 1 | 30 | 11 | 0.3667 |
| 300 | medium | 9 | 257 | 29 | 0.1102 |
| 300 | cold | 2 | 60 | 0 | 0.0000 |
| 600 | hot | 1 | 60 | 14 | 0.2333 |
| 600 | medium | 4 | 227 | 24 | 0.1046 |
| 600 | cold | 1 | 60 | 2 | 0.0333 |

At block_size=300 there is 1 hot block (30 anchors, 11 positives, 36.7% rate), 9 medium blocks
(257 anchors, 29 positives), and 2 cold blocks (60 anchors, **0 positives**). At block_size=600
the single cold block has 2 positives (3.3% rate) — the only cold-block positives in the video.

### Budget share by selectivity class (bs=300, B=80)

| method | cold | hot | medium |
| --- | --- | --- | --- |
| best_calibration_selected_diversity | 0.0750 | 0.1500 | 0.7750 |
| diversity_prefilter_object_count_mean | 0.1250 | 0.1380 | 0.7380 |
| top_proxy_object_count_mean | 0.0620 | 0.1880 | 0.7500 |
| uniform_random | 0.1690 | 0.0880 | 0.7420 |
| uniform_temporal_grid | 0.1750 | 0.0880 | 0.7380 |

Proxy-based methods (top_proxy, diversity, best_calibration) put ~75% of budget in medium
blocks, ~14-19% in hot, ~6-12% in cold. uniform_random/temporal_grid put ~17% in cold (wasted,
since cold blocks at bs=300 have 0 positives) and only ~9% in hot.

### Recall by selectivity class (bs=300, B=80)

| method | cold | hot | medium |
| --- | --- | --- | --- |
| best_calibration_selected_diversity | 0.0000 | 0.4550 | 0.3790 |
| diversity_prefilter_object_count_mean | 0.0000 | 0.4550 | 0.3450 |
| top_proxy_object_count_mean | 0.0000 | 0.4550 | 0.3450 |
| uniform_random | 0.0000 | 0.2380 | 0.2340 |
| uniform_temporal_grid | 0.0000 | 0.2730 | 0.1720 |

- All methods get **0 recall in cold blocks** at bs=300 (cold blocks have 0 positives — a
  coverage ceiling, not a method failure).
- Proxy methods get 0.455 hot-block recall and 0.34-0.38 medium recall.
- uniform methods get only 0.17-0.27 hot recall — they under-allocate to the dense hot block.

### Cold-block recall at bs=600 (the only cold block with positives)

| method | budget | budget_share | recall_in_cls | singleton_recall_in_cls |
| --- | --- | --- | --- | --- |
| best_calibration_selected_diversity | 40 | 0.1750 | 0.5000 | 0.5000 |
| best_calibration_selected_diversity | 80 | 0.1500 | 0.0000 | 0.0000 |
| best_calibration_selected_diversity | 150 | 0.3070 | 0.5000 | 0.5000 |
| diversity_prefilter_object_count_mean | 40 | 0.0750 | 0.0000 | 0.0000 |
| diversity_prefilter_object_count_mean | 80 | 0.1000 | 0.0000 | 0.0000 |
| diversity_prefilter_object_count_mean | 150 | 0.1730 | 0.0000 | 0.0000 |
| top_proxy_object_count_mean | 40 | 0.0000 | 0.0000 | 0.0000 |
| top_proxy_object_count_mean | 80 | 0.0620 | 0.0000 | 0.0000 |
| top_proxy_object_count_mean | 150 | 0.0870 | 0.0000 | 0.0000 |
| uniform_random | 40 | 0.1680 | 0.0700 | 0.0700 |
| uniform_random | 80 | 0.1690 | 0.2400 | 0.2400 |
| uniform_random | 150 | 0.1710 | 0.4500 | 0.4500 |
| uniform_temporal_grid | 40 | 0.1750 | 0.0000 | 0.0000 |
| uniform_temporal_grid | 80 | 0.1750 | 0.0000 | 0.0000 |
| uniform_temporal_grid | 150 | 0.1730 | 1.0000 | 1.0000 |

This is the key high/low-selectivity tradeoff:
- `top_proxy_object_count_mean` and `diversity_prefilter_object_count_mean` get **0 cold-block
  recall at every budget** — they rank the 2 cold-block positives low and never examine them.
- `best_calibration_selected_diversity` (person_count_mean proxy) gets 0.50 cold recall at
  B=40 and B=150 (the cold-block positives are pedestrian, which the person proxy ranks high),
  but 0 at B=80.
- `uniform_random` catches 0.24-0.45 of cold positives by chance; `uniform_temporal_grid`
  catches all 2 at B=150 (full coverage).

**Interpretation:** proxy methods maximize hot/medium recall but sacrifice cold coverage.
Uniform methods catch some cold positives but waste budget on empty cold blocks and lose hot
recall. The best_calibration (person proxy) is the only proxy method that recovers cold-block
positives, and only because those positives happen to be pedestrian. This is query/proxy-
dependent, not a general cold-block recovery mechanism.

### Singleton recall in cold blocks

At bs=150 (cold blocks have 0 positives) and bs=300, singleton recall in cold is 0 for all
methods (no cold positives exist). At bs=600, singleton cold recall equals cold recall (the 2
cold positives are singletons). No method improves cold singleton recall beyond the cold recall
pattern above.

See `analysis/block_selectivity_diagnostic.csv`, `analysis/block_selectivity_diagnostic_agg.csv`,
`tables/block_selectivity_summary.csv`.

## 6.2 Query-level selectivity

Sub-queries by `involved_object` (field present in canonical table): all_event (40 positives),
pedestrian_event (25), cyclist_event (11), vehicle_event (4), non_vehicle_event (36).

### Per-query proxy AUROC

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

**The best proxy changes by query:**
- pedestrian / non_vehicle / cyclist: `person_count_max`/`person_count_mean` dominate
  (AUROC 0.78-0.84). `lateral_presence_max` is a strong second for non_vehicle (0.74).
- vehicle: **no proxy is strong**. Best is `score_fusion_geometry_motion` (0.585),
  `motion_energy_mean` (0.551), `object_count_mean` (0.509). person proxies are weak (0.535).
- `object_count_mean` is mediocre-but-stable across all queries (0.509-0.638).
- `vehicle_count_mean` is anti-predictive for every query (AUROC 0.43-0.48).

### Per-query replay (best deployable)

| query | budget | best_method | best_recall | best_proxy | best_deployable_method | best_deployable_recall | best_deployable_proxy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all_event | 40 | top_proxy_person_count_mean | 0.4750 | person_count_mean | top_proxy_object_count_mean | 0.2250 | object_count_mean |
| all_event | 80 | top_proxy_person_count_max | 0.6750 | person_count_max | top_proxy_object_count_mean | 0.3750 | object_count_mean |
| all_event | 150 | top_proxy_person_count_max | 0.8500 | person_count_max | top_proxy_object_count_mean | 0.6250 | object_count_mean |
| cyclist_event | 40 | top_proxy_person_count_max | 0.4545 | person_count_max | diversity_prefilter_object_count_mean | 0.3636 | object_count_mean |
| cyclist_event | 80 | top_proxy_person_count_max | 0.7273 | person_count_max | top_proxy_object_count_mean | 0.5455 | object_count_mean |
| cyclist_event | 150 | top_proxy_person_count_max | 0.9091 | person_count_max | top_proxy_object_count_mean | 0.6364 | object_count_mean |
| non_vehicle_event | 40 | top_proxy_person_count_mean | 0.5278 | person_count_mean | top_proxy_object_count_mean | 0.2500 | object_count_mean |
| non_vehicle_event | 80 | top_proxy_person_count_max | 0.7222 | person_count_max | top_proxy_object_count_mean | 0.3889 | object_count_mean |
| non_vehicle_event | 150 | top_proxy_person_count_max | 0.8611 | person_count_max | top_proxy_object_count_mean | 0.6389 | object_count_mean |
| pedestrian_event | 40 | top_proxy_person_count_mean | 0.5600 | person_count_mean | top_proxy_object_count_mean | 0.2800 | object_count_mean |
| pedestrian_event | 80 | top_proxy_person_count_max | 0.7200 | person_count_max | top_proxy_object_count_mean | 0.3200 | object_count_mean |
| pedestrian_event | 150 | top_proxy_person_count_max | 0.8400 | person_count_max | top_proxy_object_count_mean | 0.6400 | object_count_mean |
| vehicle_event | 40 | diversity_prefilter_object_count_mean | 0.2500 | object_count_mean | diversity_prefilter_object_count_mean | 0.2500 | object_count_mean |
| vehicle_event | 80 | diversity_prefilter_object_count_mean | 0.5000 | object_count_mean | diversity_prefilter_object_count_mean | 0.5000 | object_count_mean |
| vehicle_event | 150 | diversity_prefilter_object_count_mean | 0.7500 | object_count_mean | diversity_prefilter_object_count_mean | 0.7500 | object_count_mean |

- For pedestrian/cyclist/non_vehicle, the hindsight person proxies dominate; the deployable
  fallback is `object_count_mean` (top or diversity).
- For **vehicle_event**, the best method (including hindsight) is
  `diversity_prefilter_object_count_mean` — person proxies are weak for vehicles, so the
  object-count diversity prefilter is the deployable winner AND the overall winner. No hindsight
  proxy improves on it for the vehicle query.

## Required answers

1. **Does the best proxy change by query selectivity?** Yes, strongly. person proxies win for
   pedestrian/cyclist/non_vehicle; score_fusion/motion win weakly for vehicle; object_count_mean
   is the stable mediocre default.
2. **Do pedestrian/cyclist queries depend more on person/bike/object count?** Yes —
   person_count proxies have AUROC 0.78-0.84 for pedestrian/cyclist/non_vehicle.
3. **Does vehicle query depend more on vehicle/motion/geometry proxy?** Partially — vehicle
   is the hardest query (only 4 positives, max AUROC 0.585). No proxy is genuinely strong;
   score_fusion and motion_energy edge out vehicle_count (which is anti-predictive).
4. **Does this support proxy calibration?** Yes — in principle. Different queries need
   different proxies, so a single fixed default is suboptimal. BUT on this single video the
   deployable `object_count_mean` remains the safest single default because it is mediocre-but-
   stable, while person proxies are excellent for non-vehicle but useless for vehicle. A
   query-aware calibration that picks person proxies for non-vehicle and object_count for
   vehicle would be the ideal, but the vehicle query is too small (4 positives) to calibrate
   reliably.

## Limitations

- Vehicle query has only 4 positives — AUROC/replay for it is high-variance and not generalizable.
- Cold-block analysis depends on block size; at bs=300 cold=0 positives, at bs=600 cold=2.
- Single video; the hot/cold split is specific to this video's event distribution.
- Labels are VLM-oracle-relative, not human truth.

## Outputs

- `analysis/block_selectivity_diagnostic.csv`, `analysis/block_selectivity_diagnostic_agg.csv`
- `analysis/block_selectivity_blocks_bs(150, 300, 600).csv`
- `tables/block_selectivity_summary.csv`
- `analysis/query_selectivity_proxy_metrics.csv`
- `analysis/query_selectivity_replay_long.csv`, `analysis/query_selectivity_replay_summary.csv`
