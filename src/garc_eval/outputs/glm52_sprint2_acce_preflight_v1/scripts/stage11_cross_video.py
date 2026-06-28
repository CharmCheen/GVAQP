#!/usr/bin/env python3
"""Stage 11 / Task 2: Query-aware proxy prior cross-video generalization check.

Compare proxy AUROC direction between dataset3 (n=4 vehicle pos) and realcartest
(n=67 vehicle pos). realcartest V13.7 proxy features do NOT include person_count,
bike_count, lateral_presence, bbox_cx_std — only vehicle/object/motion/bbox.
So person proxy cross-video check CANNOT be done; only vehicle/object/motion
features are compared cross-video.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import common as C

C.ensure_dirs()
ds3 = C.load_dataset3()
rc = C.load_realcartest()

# Common features available in BOTH videos
common_features = [
    "score_fusion_geometry_motion",
    "object_count_mean",
    "object_count_max",
    "yolo_vehicle_mean",  # same as vehicle_count_mean in ds3; rc uses this name
    "motion_energy_mean",
    "motion_energy_max",
    "bbox_area_sum_mean",
    "center_roi_vehicle_count_mean",
]
common_features = [f for f in common_features if f in ds3.columns and f in rc.columns]

def query_aurocs(df, features, query_name):
    """Compute AUROC for all_event, vehicle_event, pedestrian_event, cyclist_event."""
    inv = df["involved_object"].astype(str)
    is_pos = df["is_positive"]
    queries = {
        "all_event": is_pos.astype(int),
        "vehicle_event": ((inv == "vehicle") & is_pos).astype(int),
    }
    if "pedestrian" in inv.unique():
        queries["pedestrian_event"] = ((inv == "pedestrian") & is_pos).astype(int)
    if "cyclist" in inv.unique():
        queries["cyclist_event"] = ((inv == "cyclist") & is_pos).astype(int)
    if "motorcycle" in inv.unique():
        queries["motorcycle_event"] = ((inv == "motorcycle") & is_pos).astype(int)
    rows = []
    for qname, y in queries.items():
        n_pos = int(y.sum())
        for feat in features:
            s = df[feat].astype(float).to_numpy()
            auc = C.tie_aware_auroc(s, y.astype(float))
            rows.append({"video": df["video_id"].iloc[0] if "video_id" in df.columns else "unknown", "query": qname, "feature": feat, "auroc": auc, "n_pos": n_pos})
    return pd.DataFrame(rows)

ds3_res = query_aurocs(ds3, common_features, "dataset3")
rc_res = query_aurocs(rc, common_features, "realcartest")
both = pd.concat([ds3_res, rc_res], ignore_index=True)
both.to_csv(C.TABLES / "stage11_cross_video_auroc.csv", index=False)

# Pivot for comparison: feature x query x video
piv = both.pivot_table(index=["feature", "query"], columns="video", values="auroc").reset_index()
piv["direction_consistent"] = ""

# Check direction consistency for vehicle_event (the key query)
veh = both[both["query"] == "vehicle_event"].sort_values("auroc", ascending=False)
veh_piv = veh.pivot(index="feature", columns="video", values="auroc").reset_index()
veh_piv["diff"] = veh_piv.iloc[:, 1] - veh_piv.iloc[:, 2]  # approximate
# rank correlation
from scipy.stats import spearmanr
ds3_veh = ds3_res[ds3_res["query"] == "vehicle_event"].set_index("feature")["auroc"]
rc_veh = rc_res[rc_res["query"] == "vehicle_event"].set_index("feature")["auroc"]
shared = [f for f in ds3_veh.index if f in rc_veh.index and not np.isnan(ds3_veh[f]) and not np.isnan(rc_veh[f])]
if len(shared) >= 3:
    rho, pval = spearmanr([ds3_veh[f] for f in shared], [rc_veh[f] for f in shared])
else:
    rho, pval = float("nan"), float("nan")

# Direction check: is score_fusion > vehicle_count_mean in BOTH videos?
ds3_sf = float(ds3_veh.get("score_fusion_geometry_motion", float("nan")))
ds3_vc = float(ds3_veh.get("yolo_vehicle_mean", float("nan")))  # vehicle_count_mean == yolo_vehicle_mean
rc_sf = float(rc_veh.get("score_fusion_geometry_motion", float("nan")))
rc_vc = float(rc_veh.get("yolo_vehicle_mean", float("nan")))

ds3_dir = ds3_sf > ds3_vc  # True if geometric > vehicle_count
rc_dir = rc_sf > rc_vc

if ds3_dir and rc_dir:
    decision = "QUERY_PRIOR_CROSS_VIDEO_CONSISTENT"
elif not ds3_dir and not rc_dir:
    decision = "QUERY_PRIOR_CROSS_VIDEO_CONSISTENT"
else:
    decision = "QUERY_PRIOR_CROSS_VIDEO_INCONSISTENT"

# Also check all_event direction (sanity)
ds3_all = ds3_res[ds3_res["query"] == "all_event"].set_index("feature")["auroc"]
rc_all = rc_res[rc_res["query"] == "all_event"].set_index("feature")["auroc"]
shared_all = [f for f in ds3_all.index if f in rc_all.index and not np.isnan(ds3_all[f]) and not np.isnan(rc_all[f])]
rho_all, pval_all = spearmanr([ds3_all[f] for f in shared_all], [rc_all[f] for f in shared_all]) if len(shared_all) >= 3 else (float("nan"), float("nan"))

# Person proxy: dataset3 only (realcartest has no person_count features)
person_note = "person_count_mean/max NOT available in realcartest V13.7 proxy features. Person proxy cross-video check CANNOT be performed. The person proxy finding (AUROC 0.81 on dataset3 all_event) remains dataset3-only."

report = f"""# Stage 11: Query-Aware Proxy Prior Cross-Video Generalization Check

## Setup

Compare proxy AUROC direction between dataset3 (347 anchors, 40 positives, 4 vehicle)
and realcartest V13.8 (399 anchors, 94 positives, 67 vehicle).

**Critical limitation:** realcartest V13.7 proxy features do NOT include
`person_count_mean`, `person_count_max`, `bike_count_mean`, `lateral_presence_max`,
`bbox_cx_std_mean`. Only vehicle/object/motion/bbox features are available in both
videos. **The person proxy cross-video check CANNOT be performed.**

## Common features compared

{", ".join(common_features)}

## Vehicle sub-query AUROC comparison (key query)

| feature | dataset3 (n_pos=4) | realcartest (n_pos=67) | direction |
|---|---|---|---|
"""
for feat in common_features:
    d3 = float(ds3_veh.get(feat, float("nan")))
    r = float(rc_veh.get(feat, float("nan")))
    d3_str = f"{d3:.4f}" if not np.isnan(d3) else "N/A"
    r_str = f"{r:.4f}" if not np.isnan(r) else "N/A"
    if not np.isnan(d3) and not np.isnan(r):
        dir_str = "same" if (d3 > 0.5) == (r > 0.5) else "DIFFERENT"
    else:
        dir_str = "N/A"
    report += f"| {feat} | {d3_str} | {r_str} | {dir_str} |\n"

report += f"""
## Spearman rank correlation of feature AUROC rankings (vehicle query)

Shared features: {len(shared)}. Spearman rho = {rho:.4f} (p={pval:.4f}).
For all_event query: rho = {rho_all:.4f} (p={pval_all:.4f}).

## Key directional test

- `score_fusion_geometry_motion` > `yolo_vehicle_mean` (vehicle_count proxy) on vehicle query?
  - dataset3: {ds3_sf:.4f} > {ds3_vc:.4f} = {ds3_dir}
  - realcartest: {rc_sf:.4f} > {rc_vc:.4f} = {rc_dir}

## All-event AUROC comparison (sanity check)

| feature | dataset3 (n_pos=40) | realcartest (n_pos=94) |
|---|---|---|
"""
for feat in common_features:
    d3 = float(ds3_all.get(feat, float("nan")))
    r = float(rc_all.get(feat, float("nan")))
    d3_str = f"{d3:.4f}" if not np.isnan(d3) else "N/A"
    r_str = f"{r:.4f}" if not np.isnan(r) else "N/A"
    report += f"| {feat} | {d3_str} | {r_str} |\n"

report += f"""
## Person proxy: dataset3-only finding

{person_note}

## DECISION

`{decision}`

## Interpretation and guardrails

- The vehicle-query direction (`score_fusion > yolo_vehicle_mean`) is
  {"CONSISTENT across both videos" if ds3_dir == rc_dir else "INCONSISTENT across videos"}.
- **BUT**: dataset3 vehicle n=4 is too small to trust the direction. The realcartest
  result (n=67) is the stronger signal. If realcartest alone shows score_fusion > 
  vehicle_count, that is the more reliable directional signal.
- Person proxy CANNOT be validated cross-video due to missing features in realcartest.
  The paper must state "person proxy prior is validated on dataset3 only" unless
  person-count features are recomputed for realcartest (requires YOLO reprocessing,
  which is outside the no-new-VLM constraint).
- The all-event Spearman rho={rho_all:.4f} shows feature ranking
  {"consistency" if rho_all > 0.3 else "inconsistency"} across videos at the all-event level.
- Do NOT claim "query-aware proxy prior is a universal rule" from this check alone.

## Outputs

- `tables/stage11_cross_video_auroc.csv`
"""
(C.REPORTS / "STAGE11_QUERY_PRIOR_CROSS_VIDEO_CHECK.md").write_text(report, encoding="utf-8")
print(f"Stage 11 done. decision={decision}")
print(f"dataset3 vehicle: sf={ds3_sf:.4f} vc={ds3_vc:.4f} dir={ds3_dir}")
print(f"realcartest vehicle: sf={rc_sf:.4f} vc={rc_vc:.4f} dir={rc_dir}")
print(f"Spearman rho (vehicle): {rho:.4f}")
