# DATASET3_PROTOCOL — Frozen Data Entry & Experiment Plan

**Status:** FROZEN — do not modify without explicit re-authorization.
**Basis:** P0 New-Video Scout Gate (`garc_eval/outputs/new_video_scout_gate_v1/reports/SCOUT_GATE_REPORT.md`).
**Date:** 2026-06-25

---

## 1. Frozen Identity

| field | value |
|---|---|
| `video_id` | `dataset3` |
| `video_path` | `/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4` |
| `query_predicate` | `O_enter_ego_path_v0` |
| `primary_result_type` | `semantic event clip` |
| `dataset3_role` | **event-rich main candidate** (second long-video benchmark for Event-Native AQP) |

---

## 2. Video Properties (frozen from scout gate)

| property | value |
|---|---|
| resolution | 1920×1080 |
| fps | 30.000 |
| duration | 3462.866s (57.7min) |
| nb_frames | 103886 |
| bit_rate | 2.61 Mbps |
| codec | h264 High@50 |
| read success rate | 100.0% (0 / 103886 fail) |
| camera type | forward-facing dashcam (exterior, no cabin obstruction) |
| scene type | Chinese urban multi-lane roads, daytime, clear weather |
| vehicle density μ | 5.07 (comparable to realcartest 5.51) |
| person window% | 37.5% |
| bike/motorcycle window% | 12.3% (85 windows) |
| ego-band occupancy | 87.7% |

---

## 3. Anchor Grid (frozen, matches V13.7 convention)

| parameter | value | note |
|---|---|---|
| grid type | center10 | anchor at center of 10s window |
| anchor_interval | 10.0s | |
| half_window | 5.0s | each anchor covers [t-5, t+5] |
| n_5s_clips | 693 | coarse 5s clip grid |
| n_anchors | 346 | center10 anchors |
| first anchor | t=5.0s, window=[0, 10] | |
| last anchor | t=3455.0s, window=[3450, 3460] | |
| overlapping 5s clips/anchor | ~2 | except at boundaries |

---

## 4. Proxy Feature Schema (frozen, V13.5 superset)

Output CSV: `window_features_dataset3.csv` (693 rows, 5s windows).
Anchor-aggregated CSV: `center10_proxy_features.csv` (346 rows, to be built at P1).

### 5s window columns (scout gate output)

First 18 columns match V13.5 `proxy_features_5s.csv` exactly:

```
clip_id, video_id, start_time, end_time,
motion_energy_mean, motion_energy_max, motion_energy_std, motion_frames_sampled,
vehicle_count_mean, vehicle_count_max,
object_count_mean, object_count_max,
bbox_area_sum_mean, bbox_area_sum_max, max_bbox_area_mean,
center_roi_vehicle_count_mean, bottom_roi_vehicle_count_mean,
yolo_status
```

Extra scout columns (6):

```
person_count, bicycle_count, motorcycle_count,
near_ego_vehicle_count, bbox_cx_std, lateral_presence_count
```

### Anchor-aggregated columns (to be built at P1, matching V13.7 schema)

```
anchor_id, anchor_time, num_overlapping_5s_clips,
yolo_vehicle_mean, yolo_vehicle_max, yolo_vehicle_sum,
object_count_mean, object_count_max,
bbox_area_sum_mean, bbox_area_sum_max,
max_bbox_area_mean, max_bbox_area_max,
center_roi_vehicle_count_mean, bottom_roi_vehicle_count_mean,
motion_energy_mean, motion_energy_max, motion_energy_sum,
z_yolo_vehicle_max, z_bbox_area_sum_max, z_motion_energy_max, z_center_roi_count_mean,
score_yolo_count, score_yolo_geometry, score_motion,
score_fusion_yolo_motion, score_fusion_geometry_motion
```

---

## 5. Frozen ROI Definition

**ego-band ROI** (from kinematic proxy config, NOT V13.5 center-thirds):

| ROI | x range | y range | meaning |
|---|---|---|---|
| `near_ego` (PRIMARY) | [0.35w, 0.65w] | [0.45h, 1.0h] | lower-center ego-path band |
| `center_thirds` (V13.5, reference only) | [w/3, 2w/3] | [h/3, 2h/3] | broken on dataset3 (nz=1.9%) |
| `bottom_thirds` | — | [2h/3, 1.0h] | lower third |

**Rationale.** Scout gate showed V13.5 center-thirds ROI nz=1.9% on dataset3 (13/693 windows) vs ego-band nz=87.7% (608/693). The center-thirds ROI is unusable on this video. All anchor-aggregated ROI features should use the ego-band. The V13.5 center-thirds columns are retained in the 5s CSV for schema compatibility but should NOT be used as proxy features for ranking on dataset3.

**Bug fix vs V13.5.** ROI cy uses true bbox vertical center `(y1+y2)/2`, not the original V13.5 code which used `(y2+y2)/2` = bbox bottom. The scout gate numbers already reflect the fix.

---

## 6. YOLO Configuration (frozen)

| role | model | path | COCO classes |
|---|---|---|---|
| proxy scorer | YOLOv8n | `models/yolo/yolov8n.pt` | vehicle=[2,3,5,7], person=0, bicycle=1 |
| frame-level pseudo-oracle | YOLOv8x | `models/yolo/yolov8x.pt` | (same, higher confidence) |

Per-window: 1 midpoint frame, batched inference on A800 GPU.
Per-anchor (P1): aggregate overlapping 5s clips (same as V13.7 `v13_7_pipeline.py:97-145`).

---

## 7. Phased Usage Plan (frozen)

| phase | code name | description | VLM calls | status |
|---|---|---|---|---|
| P0 | scout gate | cheap-signal screening (this document) | 0 | **DONE** |
| P1 | semantic pilot | small VLM pilot (~40 anchors stratified by proxy score) to check positive rate is 1–25% and non-degenerate | ~40 | **FROZEN, NOT YET AUTHORIZED** |
| P1b | boundary oracle | full center10 VLM oracle on 346 anchors (Qwen3-VL-32B), then boundary refinement | 346 + boundary | **FROZEN, NOT YET AUTHORIZED** |
| P2 | budget-quality curve | budget-decomposition experiments (set-cover, α-penalty, diversity-prefilter replay) on dataset3 | 0 (uses P1b labels) | **FROZEN, NOT YET AUTHORIZED** |
| later | audit / certificate | clip-level recall certificate test, audit package | 0 (uses P1b labels) | **FROZEN, NOT YET AUTHORIZED** |

**P1 pilot design.** 40 anchors stratified by `score_fusion_geometry_motion` quartiles (10 per quartile), VLM query = `O_enter_ego_path_v0`, same prompt template as V13.8. Goal: confirm positive rate is non-vacuous (1–25%), not to claim event density or proxy AUC.

**P1b full oracle.** 346 anchors, Qwen3-VL-32B, same protocol as V13.8 (`run_full_center10_oracle.py`). Result: `center10_full_oracle_labels.csv` (346 rows) + `center10_vlm_oracle_events.csv` (stitched events). Labels are VLM-ORACLE-RELATIVE, not human truth.

**P2 budget-quality.** Reuse V13.9/V13.10/diversity_prefilter scripts with dataset3's `center10_proxy_features.csv` as input. Budget decomposition (set-cover greedy, not just α-penalty) as the primary AQP method.

---

## 8. Hard Invariants (same as V13.5)

| invariant | value |
|---|---|
| `uses_oracle_annotation_for_generation` | **false** |
| `uses_event_boundary_for_generation` | **false** |
| proxy features contain VLM labels | **false** |
| VLM label type | `VLM_ORACLE_RELATIVE` |
| human-truth claims | **none** |
| conservative VLM labels used for ranking | **forbidden** |
| conservative VLM labels used for candidate construction | **forbidden** |
| conservative VLM labels used for hyperparameter selection | **forbidden** |
| learned proxy training on VLM labels | **forbidden** |

---

## 9. Output Directory Convention

All dataset3 experiments must write to independent output directories:

```
garc_eval/outputs/dataset3_{experiment_name}/
```

Existing frozen outputs from the scout gate:

```
garc_eval/outputs/new_video_scout_gate_v1/
  tables/window_features_dataset3.csv        ← 693-row 5s proxy (scout gate output)
  tables/summary_dataset3.json               ← summary stats
  figures/contact_sheet_dataset3.jpg          ← 1-frame/60s montage (needs human visual check)
  figures/scout_timeline_dataset3.png         ← motion/class/ego timelines
```

---

## 10. Reproducible Commands

```bash
cd /qiuyeqing/llama_prl/G-ARC && source env_garc.sh

# scout gate (already run, output frozen)
python garc_eval/outputs/new_video_scout_gate_v1/scripts/scout_pipeline.py --mode full --videos d3

# P1 semantic pilot (NOT YET AUTHORIZED)
# python garc_eval/outputs/dataset3_{pilot_name}/scripts/run_pilot.py ...

# P1b full oracle (NOT YET AUTHORIZED)
# python garc_eval/outputs/dataset3_{oracle_name}/scripts/run_full_center10_oracle.py ...

# P2 budget-quality (NOT YET AUTHORIZED)
# python garc_eval/outputs/dataset3_{budget_name}/scripts/run_budget_experiment.py ...
```

---

## 11. What This Protocol Does NOT Authorize

- No VLM / LLM oracle calls (P1/P1b require explicit authorization)
- No new VLM inference beyond the scout gate (which used zero VLM calls)
- No interpretation of proxy high-score windows as real events
- No human-truth claims
- No modification of the frozen video_path, video_id, query_predicate, or primary_result_type
- No dataset switching (dataset3 is locked in as the second benchmark)
