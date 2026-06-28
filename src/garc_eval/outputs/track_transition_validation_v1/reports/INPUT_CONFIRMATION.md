# INPUT_CONFIRMATION.md - Track-Transition Validation

## Input Inventory

| Required Input | Path | Status |
|----------------|------|--------|
| Raw bbox detections | garc_eval/outputs/dataset3_raw_bbox_materialization_v1/tables/raw_yolo_detections_dataset3_2fps.parquet | OK 44595 rows, 22 columns |
| Sampled frames | garc_eval/outputs/dataset3_raw_bbox_materialization_v1/tables/yolo_sampled_frames_dataset3_2fps.csv | OK 6926 rows |
| Anchor coverage | garc_eval/outputs/dataset3_raw_bbox_materialization_v1/tables/anchor_detection_coverage_dataset3_2fps.csv | OK 347 rows |
| Canonical anchor table | src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv | OK 347 rows |
| L3 baseline (object_count_mean + P=2.0 + greedy_maxmin_time) | src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/replay/selections/coverage_greedy_time_blocks_object_count_mean/B_*/deterministic.csv | OK B=10/20/30/40/60/80/100/150 |
| Top proxy (object_count_mean only) | src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/replay/selections/top_proxy_object_count_mean/B_*/deterministic.csv | OK |
| Diversity prefilter (best deployable reference) | src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/replay/selections/diversity_prefilter_object_count_mean/B_*/deterministic.csv | OK |
| Uniform random | src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/replay/selections/uniform_random/ | OK |
| Corridor / lateral region definition | scout_pipeline.py:239-251 (image-thirds ROIs) | WARNING crude (image-thirds only, not ego-lane geometry) |
| VLM oracle labels | src/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1/oracle_outputs/dataset3_full_center10_parsed.csv | OK read-only |
| event_cluster_id / singleton flag | in canonical table | OK |
| Cold-block flag | N/A (not present in repo) | SKIPPED |

## L3 Baseline Definition

The L3 baseline as referenced in AGENTS.md and prior cascade_eval reports is:
object_count_mean + P=2.0 + greedy_maxmin_time

This corresponds to the saved method coverage_greedy_time_blocks_object_count_mean (P=2.0 time-block coverage, deterministic). Selection files exist for B=20/30/40/60/80/100. Top-proxy-only (top_proxy_object_count_mean) is also saved for comparison.

## Corridor / ROI Definition (limitation note)

The corridor used in this validation is a CRUDE IMAGE-THIRDS APPROXIMATION, NOT a true ego-lane geometry. Reusing scout_pipeline.py:239-251:

| Region | Definition (pixel relative) |
|--------|------------------------------|
| Center (ego proxy) | cx in (w/3, 2w/3) and cy in (h/3, 2h/3) |
| Bottom | cy > 2h/3 |
| Near-ego (kinematic ROI) | cx in (0.35w, 0.65w) and cy > 0.45h |
| Lateral | cx < w/3 or cx > 2w/3 |

For this task, "inside corridor" = cx in (0.35w, 0.65w) and cy > 0.45h (the near-ego lower-center band, same as V13.5 ego ROI), and "outside corridor" = everything else (lateral thirds + top third). This is acknowledged in the report as a non-geometric proxy.

## Decision

All required inputs are present. Proceed to Phase 1 (track construction).

No new model will be called. No VLM. No new YOLO run. The 2 fps raw bbox materialization from the previous gate is the sole detection source.
