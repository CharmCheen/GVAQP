# TRACK_TRANSITION_CONSISTENCY_AUDIT.md

## Scope

Verify the track-transition negative result is **clean and referenceable**, including:
1. Reconcile the suspected 4459 vs 34814 inconsistency in counts
2. Verify track input source (correct video, no double counting)
3. Verify the negative conclusion is still valid

## 1. Count Reconciliation: 4459 vs 34814

**The "4459" was a reading error. The actual numbers are 44,595 (raw) and 34,814 (vehicle-like). They are consistent.**

| Source | Total rows | Notes |
|--------|-----------|-------|
| `raw_yolo_detections_dataset3_2fps.parquet` | 44,595 | All COCO classes, all confidences |
| `raw_yolo_detections_dataset3_2fps.csv` | 44,595 | Same as parquet |
| `yolo_sampled_frames_dataset3_2fps.csv` | 6,926 | Unique frame_index after dedup |
| Parquet filtered to vehicle-like (class_id in {2,3,5,7}) | **34,814** | car + bus + truck + motorcycle |
| Vehicle-like / raw ratio | **78.07%** | Matches "78.1%" claim in FINAL_SUMMARY.md |
| Track input (`object_tracks_dataset3_2fps.csv`) | 34,814 | **Correctly used vehicle-like, not raw** |

The track-transition script applied `class_id.isin([2,3,5,7])` filter to drop person, traffic light, bicycle, etc. This is the correct approach: pedestrians and traffic lights are not relevant to a vehicle-corridor transition analysis.

## 2. Track Input Source Verification

| Check | Expected | Actual | Pass? |
|-------|----------|--------|-------|
| Total track rows | == vehicle-like count (34,814) | 34,814 | YES |
| Unique track_id | > 0 | 8,787 | YES |
| Duplicate detection_id | 0 | 0 | YES |
| Duplicate rows | 0 | 0 | YES |
| video_id values | ['dataset3'] | ['dataset3'] | YES |
| Min frame_index | near 0 | 75 (skip first few no-detection frames) | YES |
| Max frame_index | ~103,886 | 103,875 | YES |
| Unique frames in tracks | ~6,602 | 6,602 | YES |

The track input is clean, comes from dataset3, and uses the correct count.

## 3. Track Construction Sanity

| Metric | Value | Source |
|--------|-------|--------|
| Total vehicle-like detections | 34,814 | track_stats.json |
| Total tracks | 8,787 | track_stats.json |
| Mean track length (frames) | 3.96 | track_stats.json |
| Median track length | 1.0 | track_stats.json |
| Max track length | 310 | track_stats.json |
| Tracks length >= 2 | 3,676 (41.8%) | track_stats.json |
| Tracks length >= 3 | 2,303 (26.2%) | track_stats.json |

Heavy-tailed distribution is expected at 2 fps (0.5s gap): many objects appear once and are missed on next sample.

## 4. Transition Features

| Metric | Value | Source |
|--------|-------|--------|
| Anchors with o->i transition | 290/347 (83.6%) | transition_summary.json |
| Qwen positives with transition | 26/40 (65.0%) | transition_summary.json |
| Singleton positives with transition | 14/21 (66.7%) | transition_summary.json |
| Low-proxy singleton positives with transition | 4/9 (44.4%) | see below |

The low-proxy singleton positive (n=9) is computed as singleton-cluster positives with `object_count_mean <= median(=6.5)`. With 9 anchors, a 4/9 transition rate (44.4%) is meaningfully different from the 290/347 base rate (83.6%).

## 5. INCONSISTENCY FOUND: Stale top-level FINAL_SUMMARY.md

**This is the only material inconsistency.** Two outputs disagree:

| File | Decision Label | Notes |
|------|---------------|-------|
| `track_transition_validation_v1/FINAL_SUMMARY.md` (top-level) | `TRACK_TRANSITION_INPUT_MISSING` | Dated 04:24, from FIRST attempt before raw bbox materialization |
| `track_transition_validation_v1/track_transition_validation_complete` | `TRACK_TRANSITION_NOT_USEFUL` | Updated after SECOND attempt |
| `track_transition_validation_v1/tables/final_decision.csv` | `TRACK_TRANSITION_INPUT_MISSING` | Dated 04:24, NOT UPDATED |
| `track_transition_validation_v1/reports/FINAL_SUMMARY.md`-equivalent (TRANSITION_DIAGNOSTICS.md, etc.) | `TRACK_TRANSITION_NOT_USEFUL` | From SECOND attempt, in reports/ subdirectory |
| `track_transition_validation_v1/tables/transition_replay_results.csv` (36 rows, 5 strategies x 6 budgets + 6 audit averages) | `TRACK_TRANSITION_NOT_USEFUL` | From SECOND attempt, has all the actual analysis |

**The top-level FINAL_SUMMARY.md and tables/final_decision.csv still report the FIRST-attempt decision (`INPUT_MISSING`) and were never updated after the SECOND attempt produced the actual negative result.**

The second attempt wrote:
- `reports/INPUT_CONFIRMATION.md`
- `reports/TRACK_CONSTRUCTION_REPORT.md`
- `reports/TRANSITION_FEATURE_REPORT.md`
- `reports/TRANSITION_DIAGNOSTICS.md`
- `reports/TRANSITION_REPLAY_REPORT.md`
- `tables/object_tracks_dataset3_2fps.csv`
- `tables/track_features_per_track.csv`
- `tables/track_transition_anchor_features.csv`
- `tables/transition_diagnostics.csv`
- `tables/transition_diagnostics_per_budget.csv`
- `tables/transition_replay_results.csv`
- `tables/detections_with_track_transitions.csv`
- `tables/transition_diagnostics_summary.json`
- `tables/track_stats.json`
- `tables/transition_summary.json`

But did NOT update:
- `FINAL_SUMMARY.md` (top-level)
- `tables/final_decision.csv`

This is a minor bug, not a methodology error. The actual numbers in all reports and tables are consistent (raw 44,595, vehicle-like 34,814, 78.1% ratio). The negative conclusion (`TRACK_TRANSITION_NOT_USEFUL`) is correctly supported by the data.

## 6. Verify Negative Conclusion Still Holds

| Key number | Value | Used in conclusion? |
|------------|-------|---------------------|
| Transition base rate 290/347 | 83.6% | YES (high base rate = non-selective) |
| Qwen positive transition coverage 26/40 | 65.0% | YES (under-enriched for positives) |
| Low-proxy singleton coverage 4/9 | 44.4% | YES (target failure mode not covered) |
| Best recall gain +0.037 (cluster, B=100) | within n=27 sample noise | YES |
| Best singleton gain +0.048 (B=100) | within n=21 sample noise | YES |

All numbers used in the `TRACK_TRANSITION_NOT_USEFUL` conclusion are consistent and reproducible from the saved tables.

## Decision

**`TRACK_TRANSITION_NEGATIVE_RESULT_VALID_WITH_COUNT_CORRECTION`**

Conditions met:
- Counts are internally consistent (raw 44,595, vehicle-like 34,814, ratio 78.1%)
- Track input source is correct (dataset3, no double counting, no wrong video)
- Negative conclusion is still supported by the data
- BUT: the top-level FINAL_SUMMARY.md and tables/final_decision.csv have a STALE `INPUT_MISSING` decision from the first attempt. This should be corrected.

**Recommended action**: append a correction patch to `track_transition_validation_v1/FINAL_SUMMARY.md` and update `tables/final_decision.csv` to reflect the second attempt's `TRACK_TRANSITION_NOT_USEFUL` decision. The reports/ and tables/ contents are correct; only the top-level summary and decision file are stale.
