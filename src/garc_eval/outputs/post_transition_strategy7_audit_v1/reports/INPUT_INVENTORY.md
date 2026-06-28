# INPUT_INVENTORY.md - Post-Transition Strategy 7 Audit

## Phase 1: Strategy 7 Special Audit - Inputs

### Clean Pool Revalidation (N=100, no tuning overlap)

| File | Path | Rows | Key Fields | Status |
|------|------|------|------------|--------|
| Clean pool anchor IDs | prompt_tuning_v1/heldout_cascade_eval_v1/clean_pool_anchor_ids.csv | 100 | anchor_id | OK |
| Clean cascade results | prompt_tuning_v1/heldout_cascade_eval_v1/tables/cascade_simulation_results_clean.csv | 36 | strategy, B, mean_recall, mean_tp, mean_cluster_recall, mean_singleton_recall, mean_glm_fn_lost, n_seeds=500 | OK |
| Original cascade results | prompt_tuning_v1/heldout_cascade_eval_v1/tables/cascade_simulation_results.csv | 36 | same schema, N=123 | OK |
| Cascade decision summary | prompt_tuning_v1/heldout_cascade_eval_v1/tables/cascade_decision_summary.csv | 36 | strategy, B, mean_recall, mean_precision, mean_cluster_recall, mean_singleton_recall, mean_cold_block_recall, mean_glm_fn_lost | OK |
| Cluster/singleton recall | prompt_tuning_v1/heldout_cascade_eval_v1/tables/cluster_singleton_recall_clean.csv | 5 (B values) | n_clusters, n_singletons, cluster_recall, singleton_recall | OK |
| Clean pool report | prompt_tuning_v1/heldout_cascade_eval_v1/reports/CLEAN_POOL_REVALIDATION.md | - | Text analysis | OK |
| Cascade decision script | prompt_tuning_v1/scripts/cascade_simulation_clean.py | - | Defines Strategy 1-7 logic | OK |

### Clean Pool Composition

| Metric | Old N=123 Pool | Clean N=100 Pool |
|--------|----------------|------------------|
| N | 123 | 100 |
| Total positives | 40 | 28 |
| Total clusters (positive) | 27 | 11 |
| Total singleton clusters | 21 | 5 |
| Positive rate | 32.5% | 28.0% |

The 23/123 removed anchors had 12 Qwen-positives (66.7% positive rate vs 32.5% base). This was the source of the cleanup finding in the prior CLEAN_POOL_REVALIDATION.md.

### Strategy 7 vs Strategy 6 - Clean Pool Numbers

| Budget | S6 anchor_recall | S7 anchor_recall | Gap (pp) | S6 cluster | S7 cluster | S6 singleton | S7 singleton |
|--------|------------------|------------------|----------|------------|------------|--------------|--------------|
| 20 | 0.170 | 0.214 | +4.4 | 0.214 | 0.273 | 0.245 | 0.250 |
| 30 | 0.242 | 0.250 | +0.8 | 0.301 | 0.318 | 0.340 | 0.3125 |
| 40 | 0.315 | 0.393 | +7.7 | 0.388 | 0.455 | 0.430 | 0.500 |
| 60 | 0.528 | 0.786 | +25.7 | 0.593 | 0.818 | 0.610 | 0.8125 |
| 80 | 0.789 | 0.857 | +6.9 | 0.837 | 0.909 | 0.803 | 0.875 |
| 100 | 1.000 | 1.000 | 0.0 | 1.000 | 1.000 | 1.000 | 1.000 |

### Determinism Note

- Strategy 7 in cascade_simulation_clean.py (line 124-136) creates rng = np.random.RandomState(seed) but never uses rng; the audit selection is fully deterministic (sort by disagreement_score then take top-K). This explains why std_recall=0 for S7 in the clean pool results.
- Strategy 6 IS stochastic (uses rng.choice).
- Strategies 1-5 are deterministic.

## Phase 2: Strategy 7 Budget Alignment - Inputs

| File | Path | N | B range | Status |
|------|------|---|---------|--------|
| Original cascade results | prompt_tuning_v1/heldout_cascade_eval_v1/tables/cascade_simulation_results.csv | 123 | 30,40,60,80,100 | OK |
| Clean cascade results | prompt_tuning_v1/heldout_cascade_eval_v1/tables/cascade_simulation_results_clean.csv | 100 | 20,30,40,60,80,100 | OK |

Relative budget alignment: B_equiv = round(B * 100/123)
| Original B | Equiv clean B | Match in clean? |
|------------|----------------|------------------|
| 30 | 24 | closest 20,30 |
| 40 | 33 | closest 30,40 |
| 60 | 49 | closest 40,60 |
| 80 | 65 | closest 60,80 |
| 100 | 81 | closest 80,100 |

## Phase 3: Track-Transition Consistency - Inputs

| File | Path | Content | Status |
|------|------|---------|--------|
| Track-transition FINAL | track_transition_validation_v1/FINAL_SUMMARY.md | 44595 raw / 34814 vehicle-like | OK |
| Track stats JSON | track_transition_validation_v1/tables/track_stats.json | total_vehicle_detections=34814, total_tracks=8787 | OK |
| Transition summary JSON | track_transition_validation_v1/tables/transition_summary.json | 290/347 anchors with transition, 26/40 positives, 4/9 low-proxy singletons | OK |
| Raw bbox FULL_RUN | dataset3_raw_bbox_materialization_v1/reports/FULL_RUN_REPORT.md | Total detections 44595, vehicle-like 34814 (78.1%) | OK |
| Raw bbox parquet | dataset3_raw_bbox_materialization_v1/tables/raw_yolo_detections_dataset3_2fps.parquet | 44595 rows | OK |
| Track CSV | track_transition_validation_v1/tables/object_tracks_dataset3_2fps.csv | 34814 rows | OK |
| Anchor features | track_transition_validation_v1/tables/track_transition_anchor_features.csv | 347 rows | OK |

### Cross-verification

- raw_detections_dataset3_2fps.parquet: 44595 rows
- after filter to vehicle-like (class_id in {2,3,5,7}): 34814 rows
- 34814/44595 = 0.7806 = 78.1% vehicle-like
- track_input_used = 34814 (matches vehicle-like count)
- tracks_constructed = 8787 (mean length 3.96)
- transition_anchors = 290/347 (83.6%)

The 4459 vs 34814 was a reading error: actual raw is 44,595, vehicle-like is 34,814. The track-transition script used the correct filtered count.

## Phase 4: High-Selectivity Scout - Inputs

### dataset3

| File | Path | Rows | Has labels? | Has cluster_id? |
|------|------|------|-------------|-----------------|
| Canonical anchor | codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv | 347 | YES (Qwen) | YES |
| Center10 proxy features | event_native_aqp_p1_dataset3_semantic_pilot_v1/metadata/center10_proxy_features.csv | 348 | YES (p1 partial) | YES |
| Window features | new_video_scout_gate_v1/tables/window_features_dataset3.csv | 694 | NO | NO |
| Raw bbox 2fps | dataset3_raw_bbox_materialization_v1/tables/raw_yolo_detections_dataset3_2fps.parquet | 44595 | N/A | N/A |
| Track transitions | track_transition_validation_v1/tables/track_transition_anchor_features.csv | 347 | YES (per-anchor) | YES |

### realcartest (V13)

| File | Path | Rows | Has labels? | Has cluster_id? |
|------|------|------|-------------|-----------------|
| Center10 oracle | v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv | 399 | YES (Qwen) | NO |
| V13 events | v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv | 51 | YES | NO (event-level) |
| Kinematic proxy | experiments/kinematic_proxy/kinematic_proxy/proxy_scores.csv | 103 | YES | NO |
| Tracks (realcartest_5k) | experiments/kinematic_proxy/kinematic_proxy/tracks.csv | 74784 | N/A | N/A |
| V13.9 AQP sim | v13/v13_9_aqp_sim/tables/method_budget_results.csv | - | YES | NO |

### candidate predicates available in both videos

| Predicate | dataset3 | realcartest | source |
|-----------|----------|-------------|--------|
| object_count_mean > 0 | YES (per anchor) | YES (per anchor) | proxy |
| object_count_mean >= k | YES | YES | proxy |
| vehicle_count_mean > 0 | YES | YES | proxy |
| bbox_cx_std > threshold | YES (anchor) | NO direct | dataset3 only |
| track transition feature | YES (n_transition_tracks>0) | NO (no track features computed) | track-transition |
| event_cluster_id | YES | NO (need to derive from event_id) | clustering |
| Qwen positive label | YES | YES | oracle |

## Sufficiency Assessment

All required inputs for Phases 1-4 are present. No missing files. No new model calls required. No new data downloads required.
