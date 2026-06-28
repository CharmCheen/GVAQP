# 01 Baseline Lock and Input Audit

## Source

Canonical table: `/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv` (from `codex_recompute_proxy_budget_basa_v1`).
No new VLM/oracle calls. All subsequent replays read this table.

## Locked Counts

| quantity | value |
|---|---|
| total anchors | 347 |
| positives | 40 |
| negatives | 307 |
| positive rate | 0.1153 |
| event clusters | 27 |
| singleton clusters | 21 |
| multi-anchor clusters | 6 |
| largest cluster | 9 |

## Uniqueness

- `anchor_id` unique: True
- `anchor_index` unique: True
- `center_time_s` unique: True

## Boundary Fields

`event_start` / `event_end` present: True.
`boundary_reliable` count: 0.
**Boundary fields are UNRELIABLE and are NOT used for main metrics** (per prior audit).
Only `center_time_s` / `anchor_index` are used for temporal structure.

## Query Selectivity Fields

- `event_type` present: True; counts: {'none': 307, 'enter_ego_path': 40}
- `involved_object` present: True; counts: {'none': 307, 'pedestrian': 25, 'cyclist': 11, 'vehicle': 4}

These enable the query-level selectivity diagnostic in Task D.

## Candidate Proxy Columns

Detected 38 numeric proxy columns (no oracle/label/cluster/time/boundary fields).
All present with no missing values: False.

```
score_fusion_geometry_motion, object_count_mean, object_count_max, person_count_mean, person_count_max, bike_count_mean, bike_count_max, vehicle_count_mean, vehicle_count_max, motion_energy_mean, motion_energy_max, near_ego_vehicle_count_mean, near_ego_vehicle_count_max, bicycle_count_mean, motorcycle_count_mean, lateral_presence_mean, lateral_presence_max, bbox_cx_std_mean, bbox_cx_std_max, bbox_area_sum_mean, bbox_area_sum_max, center_roi_vehicle_count_mean, bottom_roi_vehicle_count_mean, score_yolo_count, score_yolo_geometry, score_motion, score_fusion_yolo_motion, score_fusion_ego_lateral, yolo_vehicle_mean, yolo_vehicle_max, yolo_vehicle_sum, max_bbox_area_mean, max_bbox_area_max, motion_energy_sum, z_yolo_vehicle_max, z_bbox_area_sum_max, z_motion_energy_max, z_ego_count_mean
```

## Cluster Composition (Codex-audit corrected)

21 singleton clusters + 6 multi-anchor clusters = 27 event clusters.
Multi-anchor cluster sizes: [2, 2, 9, 2, 2, 2].

See `tables/anchor_cluster_summary.csv` for per-cluster detail.

## Verdict

Canonical table is complete and reused as-is. No reconstruction needed.
All downstream replays (Task B/C/D) read from this locked table.

## Outputs

- `tables/input_column_inventory.csv`
- `tables/anchor_cluster_summary.csv`
- `tables/anchor_cluster_summary.json`
