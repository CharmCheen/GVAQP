# P1 REFINE Gate — Asset Map

**Date:** 2026-06-25
**Task:** P1 REFINE Gate for Event-Native Budgeted AQP
**Scope:** Read-only inventory of existing V13.x artifacts relevant to boundary refinement evaluation.

---

## 1. Key File Paths and Purpose

### 1.1 V13.8 Full Oracle Reference (PRIMARY)

| File | Path | Purpose |
|---|---|---|
| Full oracle labels | `experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv` | 399 center10 anchor VLM labels (94 positive / 305 negative) with event_start/end boundaries |
| Stitched events | `experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv` | 51 stitched events (reference boundaries) merged from consecutive positive anchors |
| Stitching trace | `experiments/v13/v13_8_full_oracle/tables/center10_event_stitching_trace.csv` | Step-by-step stitching log (anchor → event mapping) |
| Raw VLM responses | `experiments/v13/v13_8_full_oracle/raw_vlm_responses/*.json` | 399 raw JSON responses from Qwen3-VL-32B |
| Final report | `experiments/v13/v13_8_full_oracle/reports/FINAL_REPORT.md` | V13.8 summary: 399 calls, 0% abstain, 51 events |

### 1.2 V13.7 Multi-Method Replay

| File | Path | Purpose |
|---|---|---|
| Anchor grid | `experiments/v13/v13_7_multimethod_replay/tables/center10_anchor_grid.csv` | 399 center10 anchor definitions (time, duration, source) |
| Proxy features | `experiments/v13/v13_7_multimethod_replay/tables/center10_proxy_features.csv` | YOLO/motion/geometry proxy scores for all 399 anchors |
| Labeled eval subset | `experiments/v13/v13_7_multimethod_replay/tables/center10_labeled_eval_subset.csv` | 52 VLM labels at shifted center times (NOT overlapping V13.8 anchors) |

### 1.3 V13.6 Clip Construction Sensitivity

| File | Path | Purpose |
|---|---|---|
| VLM labels | `experiments/v13/v13_6_clip_construction/tables/clip_construction_vlm_labels.csv` | 416 labels (52 samples × 8 policies: 4s/5s/6s/10s/15s/20s/contact sheets) |
| Pairwise comparison | `experiments/v13/v13_6_clip_construction/tables/clip_construction_pairwise_comparison.csv` | Clip construction policy comparison |
| Policy summary | `experiments/v13/v13_6_clip_construction/tables/clip_construction_policy_summary.csv` | Center_10s vs fixed_5s positive rate comparison |
| Anchor expand dry run | `experiments/v13/v13_6_clip_construction/tables/anchor_expand_dry_run.csv` | Center_10s anchor expansion plan |

### 1.4 V13.5 Pilot

| File | Path | Purpose |
|---|---|---|
| Coarse 5s grid | `experiments/v13/v13_5_pilot/tables/coarse_5s_clip_grid.csv` | 5s coarse clip definitions |
| Proxy features 5s | `experiments/v13/v13_5_pilot/tables/proxy_features_5s.csv` | YOLO/motion features for 5s clips |
| VLM pilot labels | `experiments/v13/v13_5_pilot/tables/vlm_pilot_labels.csv` | 100 pilot labels (18 yes / 16 no / 66 abstain), NO event boundaries |

### 1.5 V13.9/V13.10 Budget Simulation

| File | Path | Purpose |
|---|---|---|
| Method budget results | `experiments/v13/v13_9_aqp_sim/tables/method_budget_results.csv` | 19 methods × 5 budgets, event recall (overlap/IoU 0.3/IoU 0.5) |
| Event hit trace | `experiments/v13/v13_9_aqp_sim/tables/event_hit_trace.csv` | Per-method per-budget event hit details |
| Adaptive simulation | `experiments/v13/v13_10_adaptive/tables/adaptive_simulation_v13_10.csv` | V13.10 adaptive boost/expand results |
| Oracle upper bound | `experiments/v13/v13_10_adaptive/tables/oracle_upper_bound_v13_10.csv` | OracleBest@B = min(B,51)/51 |

### 1.6 Diversity Prefilter Replay (AQP positive result)

| File | Path | Purpose |
|---|---|---|
| Final report | `experiments/diversity_prefilter/diversity_prefilter_replay_v1/reports/FINAL_REPORT.md` | Budget decomposition WEAK_GO result |
| Method results | `experiments/diversity_prefilter/diversity_prefilter_replay_v1/tables/method_budget_results.csv` | H1/H2/H3 method results |
| H3 results | `experiments/diversity_prefilter/diversity_prefilter_replay_v1/tables/h_method_results.csv` | H3 confirmed-positive refine (FAILED) |

### 1.7 Project State and Audit

| File | Path | Purpose |
|---|---|---|
| Current state audit | `outputs/reports/CURRENT_PROJECT_STATE_READONLY_AUDIT.md` | Read-only handover report |
| V13.8→V13.9 agent loop | `outputs/reports/agent_loop_center10_v13_8_to_v13_9_FINAL.md` | Mentions boundary refinement as untested (line 71) |

---

## 2. Key CSV/JSON Field Overview

### 2.1 `center10_full_oracle_labels.csv` (V13.8, 399 rows)

| Field | Type | Description |
|---|---|---|
| anchor_id | str | `center10_anchor_0000` … `center10_anchor_0398` |
| video_id | str | `realcartest` |
| anchor_time | float | Anchor center time in seconds (5.0, 15.0, 25.0, …) |
| start_time | float | Clip start = anchor_time − 5.0 |
| end_time | float | Clip end = anchor_time + 5.0 |
| duration | float | 10.0 (constant) |
| label | str | `positive` / `negative` |
| event_start | float | Event start relative to clip start (0.0, 0.5) |
| event_end | float | Event end relative to clip start (0.7, 1.0, 0.2) |
| event_start_absolute | float | Event start in video time |
| event_end_absolute | float | Event end in video time |
| event_type | str | `enter_ego_path` / `none` |
| involved_object | str | `vehicle` / `pedestrian` / `cyclist` / `motorcycle` / `none` |
| boundary_status | str | `ok` |
| complete_event_visible | bool | `True` for all |
| confidence | str | `high` |
| evidence | str | VLM evidence text (Chinese/English) |
| negative_reason | str | Reason for negative label |
| parse_status | str | `ok` |

### 2.2 `center10_vlm_oracle_events.csv` (V13.8, 51 rows)

| Field | Type | Description |
|---|---|---|
| event_id | str | `realcartest_event_0000` … `realcartest_event_0050` |
| event_start | float | Stitched event start (absolute) |
| event_end | float | Stitched event end (absolute) |
| event_duration | float | Stitched event duration |
| num_supporting_anchors | int | 1 (single) or 2–10 (multi) |
| supporting_anchor_ids | str | Pipe-separated anchor IDs |
| event_type_majority | str | `enter_ego_path` |
| involved_object_majority | str | `vehicle` / `pedestrian` / `cyclist` |

### 2.3 `center10_proxy_features.csv` (V13.7, 399 rows)

| Field | Type | Description |
|---|---|---|
| anchor_id | str | Same as V13.8 |
| anchor_time | float | Same as V13.8 |
| object_count_mean | float | Best single-feature proxy (AUC 0.738) |
| yolo_vehicle_mean | float | YOLO vehicle count |
| motion_energy_mean | float | Motion energy |
| center_roi_vehicle_count_mean | float | Center ROI vehicle count (AUC 0.535, broken) |
| score_fusion_yolo_motion | float | Fused YOLO+motion score |
| score_fusion_geometry_motion | float | Fused geometry+motion score |

### 2.4 `clip_construction_vlm_labels.csv` (V13.6, 416 rows)

| Field | Type | Description |
|---|---|---|
| sample_id | str | `v13_6_sample_XXXX_policy` |
| construction_policy | str | `fixed_5s_original` / `center_4s` / `center_6s` / `center_10s` / `center_15s` / `center_20s` / `contact_sheet_10s_5frames` / `contact_sheet_10s_8frames` |
| center_time | float | Sample center time |
| start_time / end_time | float | Clip boundaries |
| label | str | `positive` / `negative` |
| event_start / event_end | float | Event boundary relative to clip |

---

## 3. Oracle Label Statistics

### V13.8 Full Oracle (399 anchors)

| Metric | Value |
|---|---|
| Total anchors | 399 |
| Successful calls | 399 (100%) |
| Positive | 94 (23.6%) |
| Negative | 305 (76.4%) |
| Abstain | 0 (0.0%) |
| Parse errors | 0 |
| Stitched events | 51 |
| Single-anchor events | 32 |
| Multi-anchor events | 19 |
| Mean event duration | 5.2s (individual), 9.0s (stitched) |

### V13.6 Clip Construction (416 labels)

| Metric | Value |
|---|---|
| Total labels | 416 (52 samples × 8 policies) |
| Positive | 228 |
| Negative | 188 |
| Abstain | 0 |

### V13.5 Pilot (100 labels)

| Metric | Value |
|---|---|
| Total | 100 |
| Yes (positive) | 18 |
| No (negative) | 16 |
| Abstain | 66 |
| Event boundary fields | **NONE** (no event_start/event_end) |

---

## 4. Event Boundary Degeneracy Analysis

**Critical finding:** The V13.8 event boundaries are highly degenerate:

| Pattern | Count | Percentage |
|---|---|---|
| event_start = 0.0, event_end = 0.7 | 85 / 94 | **90.4%** |
| event_start = 0.5, event_end = 0.7 | 8 / 94 | 8.5% |
| event_start = 0.5, event_end = 1.0 | 1 / 94 | 1.1% |
| event_start_absolute == clip start_time | 85 / 94 | 90.4% |

All event durations are < 1s (min=0.2s, max=1.0s, mean=0.66s) within 10s clips.
The V13.6 data shows the same pattern: 191/228 (83.8%) positives have event_start = 0.0.

**Interpretation:** The VLM reports events as starting at the clip beginning with ~0.7s duration regardless of actual event timing. This is a VLM behavior artifact, not a precise boundary measurement.

---

## 5. P1 REFINE Gate Usability Assessment

### 5.1 Which files are usable for P1 REFINE Gate?

| File | Usable for REFINE? | Reason |
|---|---|---|
| V13.8 full oracle labels | **Partially** | Has all 399 anchor labels (neighbors available), but event boundaries are degenerate |
| V13.8 stitched events | **Partially** | Provides reference boundaries, but over-expanded (merges consecutive 0.7s events into up to 90.7s spans) |
| V13.7 proxy features | **Yes** | Proxy scores for candidate generation |
| V13.7 labeled eval subset | **No** | 52 labels at shifted center times; 0/52 overlap with V13.8 anchor times; same degenerate boundary pattern |
| V13.6 clip construction | **No** | 416 labels at different center times (23/52 within 5s of V13.8 positives); same degenerate boundary pattern; different clip window sizes don't resolve boundaries |
| V13.5 pilot labels | **No** | No event boundary fields; only binary labels on 5s clips |
| V13.9/V13.10 budget results | **Context only** | Shows IoU=0 at all thresholds, confirming clip-level IoU is not meaningful |
| Diversity prefilter H3 | **Context only** | H3 (confirmed-positive refine ±30/±60s) already FAILED — expanding around positives re-hits same neighborhoods |

### 5.2 Which candidates have neighborhood labels?

**All 94 positive anchors have left and right neighbor labels** (full oracle scan covers all 399 anchors at 10s stride). This is the only dataset where neighborhood observations exist.

### 5.3 Which candidates have only center labels?

All candidates have center labels. Additionally, all have neighbor labels (because V13.8 is a full scan, not a budgeted scan). However, the neighbor labels are binary (positive/negative) — they do NOT provide sub-clip boundary information.

### 5.4 Is there a usable reference boundary?

**Yes, but with a major caveat.** The 51 stitched events provide reference boundaries. However:
- 32 single-anchor events: reference = the anchor's own 0.7s event (degenerate)
- 19 multi-anchor events: reference = over-expanded span (e.g., 90.7s for 10 × 0.7s events)

The reference boundaries are not "true" event boundaries — they are stitching artifacts.

### 5.5 Do boundary refinement old products exist?

**No.** The `agent_loop_center10_v13_8_to_v13_9_FINAL.md` (line 71) mentions: "Boundary refinement: For the 94 positive anchors, run 2s refinement VLM to get tighter event boundaries. This won't help with the budgeted recall problem but would improve returned-duration efficiency." — but this was **never executed**.

The `CURRENT_PROJECT_STATE_READONLY_AUDIT.md` (line 178) confirms: "boundary 2s 精修未测" (boundary 2s refinement not tested).

No sub-clip (e.g., 2s) VLM observations exist anywhere in the repository.

### 5.6 Is it sufficient for no-new-VLM REFINE replay?

**Technically yes, but the replay cannot meaningfully answer the REFINE question.** A replay is possible because all 399 anchors are labeled (neighbors available for all positives). However:

1. **Event boundaries are degenerate** (90.4% have 0.0–0.7 pattern) — there is no meaningful boundary variation to refine.
2. **The only "refinement" possible with neighbor labels** is extending the candidate to include adjacent positive anchors, which is exactly what stitching already does.
3. **This extension creates over-expansion** (e.g., 0.7s event → 90.7s stitched span), not precision improvement.
4. **No sub-clip boundary observations exist** to test whether boundaries can be made more precise.
5. **IoU at clip-level is always 0** (V13.9 confirms: events_hit_iou_0p3 = 0 for all methods at all budgets), making clip-level IoU meaningless.
6. **H3 (confirmed-positive refine ±30/±60s) already failed** in the diversity_prefilter replay, showing that neighborhood expansion around confirmed positives re-hits already-hit events.

---

## 6. ASSET_DECISION

```
ASSET_DECISION: INSUFFICIENT_LABELS_NEED_MINIMAL_ORACLE_PLAN
```

**Rationale:** While a no-new-VLM replay is technically possible (all 399 anchors labeled), the existing data cannot meaningfully answer whether boundary observations improve event clip quality because:
- Event boundaries are degenerate (VLM artifact: 90.4% have 0.0–0.7 pattern)
- The only available "refinement" (neighbor label extension) creates over-expansion, not precision
- No sub-clip (2s) boundary observations exist to test true boundary refinement
- The reference boundaries (stitched events) are over-expanded artifacts, not true event boundaries
- A minimal oracle plan is needed to generate sub-clip boundary observations
