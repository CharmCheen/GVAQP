# 02 Full Center10 Oracle Audit

## Recomputed Core Counts

- Total anchors: 347.
- Positive / negative / abstain / parse-error: 40 / 307 / 0 / 0.
- Positive rate: 0.115274.
- Positive objects: {'pedestrian': 25, 'cyclist': 11, 'vehicle': 4}.
- Positive event types: {'enter_ego_path': 40}.

## P1 Reuse

The full CSV contains all 50 P1 anchor IDs. The `raw_per_anchor_full` directory contains 297 JSON files. Therefore the arithmetic `297 new + 50 reused = 347` is supported by files.

## Boundary Template

Among 40 positives, 39 have `event_start=0.0` and `event_end=0.7`, and all positive `event_end` values are a single unique value. The boundary field is not usable for event IoU on dataset3.

## Source vs Recomputed

Detailed source/recomputed values are in `tables/full_center10_recomputed_metrics.csv`. No material count mismatch was found for full-scan labels. The main issue is boundary localization, not binary label completeness.
