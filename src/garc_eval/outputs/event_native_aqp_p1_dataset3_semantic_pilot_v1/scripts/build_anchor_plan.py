#!/usr/bin/env python3
"""Build dataset3 center10 anchor grid + proxy features + stratified pilot selection.

Stage 1: center10 anchor grid (346 anchors, 10s spacing, 5s half-window).
Stage 2: aggregate 5s scout features up to anchor level (V13.7 convention).
Stage 3: z-scores + fusion scores (V13.7 schema, ego-band ROI variant added).
Stage 4: select 50 anchors stratified by score_fusion_geometry_motion quartiles
         (12-13 per quartile) + 5 random fillers for coverage.

No VLM labels used. No oracle labels. Proxy features only.
"""
import csv, json, math, os, random
import numpy as np

OUT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1"
SCOUT_CSV = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/new_video_scout_gate_v1/tables/window_features_dataset3.csv"
VIDEO_PATH = "/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4"
VIDEO_DURATION = 3462.866
VIDEO_ID = "dataset3"
ANCHOR_INTERVAL = 10.0
HALF_WINDOW = 5.0
N_PILOT = 50
SEED = 20260625

os.makedirs(f"{OUT}/metadata", exist_ok=True)
os.makedirs(f"{OUT}/logs", exist_ok=True)

log = open(f"{OUT}/logs/anchor_build.log", "w")
def p(msg):
    print(msg, flush=True)
    log.write(msg + "\n"); log.flush()

# ---- Stage 1: anchor grid ----
p(f"=== Stage 1: center10 anchor grid (duration={VIDEO_DURATION:.3f}s) ===")
n_anchors = math.ceil(VIDEO_DURATION / ANCHOR_INTERVAL)
anchors = []
for i in range(n_anchors):
    at = i * ANCHOR_INTERVAL + ANCHOR_INTERVAL / 2
    if at > VIDEO_DURATION:
        at = VIDEO_DURATION
    start = max(0.0, at - HALF_WINDOW)
    end = min(VIDEO_DURATION, at + HALF_WINDOW)
    anchors.append({
        "anchor_id": f"center10_anchor_{i:04d}",
        "video_id": VIDEO_ID,
        "anchor_time": f"{at:.3f}",
        "start_time": f"{start:.3f}",
        "end_time": f"{end:.3f}",
        "duration": f"{end - start:.3f}",
        "source_video_path": VIDEO_PATH,
        "construction_policy": "center_10s",
    })
anchor_grid_path = f"{OUT}/metadata/center10_anchor_grid.csv"
with open(anchor_grid_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(anchors[0].keys()))
    w.writeheader(); w.writerows(anchors)
p(f"  wrote {len(anchors)} anchors -> {anchor_grid_path}")

# ---- Stage 2: aggregate 5s features to anchor level ----
p(f"\n=== Stage 2: aggregate 5s scout features to anchor level ===")
clips = []
with open(SCOUT_CSV) as f:
    for row in csv.DictReader(f):
        clips.append(row)
p(f"  loaded {len(clips)} 5s clips from scout gate")

def cf(row, key, cast=float):
    v = row.get(key, "")
    if v in ("", None): return 0.0 if cast is float else 0
    try: return cast(float(v)) if cast is int else cast(v)
    except: return 0.0 if cast is float else 0

anchor_features = []
for a in anchors:
    a_start = float(a["start_time"])
    a_end = float(a["end_time"])
    overlap = [c for c in clips if float(c["end_time"]) > a_start and float(c["start_time"]) < a_end]
    if not overlap:
        anchor_features.append({**a, "num_overlapping_5s_clips": 0,
            "yolo_vehicle_mean": 0, "yolo_vehicle_max": 0, "yolo_vehicle_sum": 0,
            "object_count_mean": 0, "object_count_max": 0,
            "bbox_area_sum_mean": 0, "bbox_area_sum_max": 0,
            "max_bbox_area_mean": 0, "max_bbox_area_max": 0,
            "center_roi_vehicle_count_mean": 0, "bottom_roi_vehicle_count_mean": 0,
            "near_ego_vehicle_count_mean": 0, "near_ego_vehicle_count_max": 0,
            "motion_energy_mean": 0, "motion_energy_max": 0, "motion_energy_sum": 0,
            "person_count_mean": 0, "person_count_max": 0,
            "bicycle_count_mean": 0, "motorcycle_count_mean": 0,
            "bbox_cx_std_mean": 0, "bbox_cx_std_max": 0,
            "lateral_presence_mean": 0, "lateral_presence_max": 0})
        continue
    vc = [cf(c, "vehicle_count_mean", int) for c in overlap]
    oc = [cf(c, "object_count_mean", int) for c in overlap]
    bas = [cf(c, "bbox_area_sum_mean") for c in overlap]
    mba = [cf(c, "max_bbox_area_mean") for c in overlap]
    cr = [cf(c, "center_roi_vehicle_count_mean", int) for c in overlap]
    br = [cf(c, "bottom_roi_vehicle_count_mean", int) for c in overlap]
    ego = [cf(c, "near_ego_vehicle_count", int) for c in overlap]
    me = [cf(c, "motion_energy_mean") for c in overlap]
    pc = [cf(c, "person_count", int) for c in overlap]
    bc = [cf(c, "bicycle_count", int) for c in overlap]
    mc = [cf(c, "motorcycle_count", int) for c in overlap]
    cxstd = [cf(c, "bbox_cx_std") for c in overlap]
    latpres = [cf(c, "lateral_presence_count", int) for c in overlap]
    anchor_features.append({**a,
        "num_overlapping_5s_clips": len(overlap),
        "yolo_vehicle_mean": float(np.mean(vc)), "yolo_vehicle_max": int(np.max(vc)), "yolo_vehicle_sum": int(np.sum(vc)),
        "object_count_mean": float(np.mean(oc)), "object_count_max": int(np.max(oc)),
        "bbox_area_sum_mean": float(np.mean(bas)), "bbox_area_sum_max": float(np.max(bas)),
        "max_bbox_area_mean": float(np.mean(mba)), "max_bbox_area_max": float(np.max(mba)),
        "center_roi_vehicle_count_mean": float(np.mean(cr)), "bottom_roi_vehicle_count_mean": float(np.mean(br)),
        "near_ego_vehicle_count_mean": float(np.mean(ego)), "near_ego_vehicle_count_max": int(np.max(ego)),
        "motion_energy_mean": float(np.mean(me)), "motion_energy_max": float(np.max(me)), "motion_energy_sum": float(np.sum(me)),
        "person_count_mean": float(np.mean(pc)), "person_count_max": int(np.max(pc)),
        "bicycle_count_mean": float(np.mean(bc)), "motorcycle_count_mean": float(np.mean(mc)),
        "bbox_cx_std_mean": float(np.mean(cxstd)), "bbox_cx_std_max": float(np.max(cxstd)),
        "lateral_presence_mean": float(np.mean(latpres)), "lateral_presence_max": int(np.max(latpres)),
    })

# ---- Stage 3: z-scores + fusion scores ----
p(f"\n=== Stage 3: z-scores + fusion scores ===")
def zscore(values):
    arr = np.array(values, float)
    mu, sd = arr.mean(), arr.std()
    if sd < 1e-9: return [0.0] * len(arr)
    return ((arr - mu) / sd).tolist()

z_veh_max = zscore([a["yolo_vehicle_max"] for a in anchor_features])
z_bas_max = zscore([a["bbox_area_sum_max"] for a in anchor_features])
z_me_max = zscore([a["motion_energy_max"] for a in anchor_features])
z_ego_mean = zscore([a["near_ego_vehicle_count_mean"] for a in anchor_features])
z_cxstd_max = zscore([a["bbox_cx_std_max"] for a in anchor_features])

for i, a in enumerate(anchor_features):
    a["z_yolo_vehicle_max"] = z_veh_max[i]
    a["z_bbox_area_sum_max"] = z_bas_max[i]
    a["z_motion_energy_max"] = z_me_max[i]
    a["z_ego_count_mean"] = z_ego_mean[i]
    a["z_cxstd_max"] = z_cxstd_max[i]
    # V13.7 fusion scores (primary)
    a["score_yolo_count"] = z_veh_max[i]
    a["score_yolo_geometry"] = z_veh_max[i] + z_bas_max[i]
    a["score_motion"] = z_me_max[i]
    a["score_fusion_yolo_motion"] = z_veh_max[i] + z_me_max[i]
    a["score_fusion_geometry_motion"] = z_bas_max[i] + z_me_max[i]
    # dataset3-specific fusion: ego-band + lateral (AQP-side, per DATASET3_PROTOCOL)
    a["score_fusion_ego_lateral"] = z_ego_mean[i] + z_cxstd_max[i]

# forbidden-field invariant
feature_cols = [k for k in anchor_features[0].keys() if k not in
    ("anchor_id","video_id","anchor_time","start_time","end_time","duration",
     "source_video_path","construction_policy")]
forbidden = any(kw in c.lower() for c in feature_cols for kw in ("vlm","oracle","label","event_start","event_end","positive","negative"))
p(f"  INVARIANT no-forbidden-fields: {'PASS' if not forbidden else 'FAIL'}")

proxy_csv = f"{OUT}/metadata/center10_proxy_features.csv"
all_cols = list(anchor_features[0].keys())
with open(proxy_csv, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=all_cols)
    w.writeheader(); w.writerows(anchor_features)
p(f"  wrote {len(anchor_features)} anchor features -> {proxy_csv}")

# ---- Stage 4: stratified pilot selection ----
p(f"\n=== Stage 4: stratified pilot selection (N={N_PILOT}, seed={SEED}) ===")
random.seed(SEED)
scores = [a["score_fusion_geometry_motion"] for a in anchor_features]
q25, q50, q75 = np.percentile(scores, [25, 50, 75])
p(f"  score_fusion_geometry_motion quartiles: q25={q25:.3f} q50={q50:.3f} q75={q75:.3f}")

quartiles = {0: [], 1: [], 2: [], 3: []}
for i, s in enumerate(scores):
    if s < q25: quartiles[0].append(i)
    elif s < q50: quartiles[1].append(i)
    elif s < q75: quartiles[2].append(i)
    else: quartiles[3].append(i)
p(f"  quartile sizes: Q1={len(quartiles[0])} Q2={len(quartiles[1])} Q3={len(quartiles[2])} Q4={len(quartiles[3])}")

# 12 per quartile = 48, +2 random from full pool for coverage = 50
per_q = N_PILOT // 4  # 12
extra = N_PILOT - per_q * 4  # 2
selected = []
for q in range(4):
    pool = quartiles[q]
    random.shuffle(pool)
    selected.extend(pool[:per_q])
# extra: random from remaining
remaining = [i for i in range(len(anchor_features)) if i not in selected]
random.shuffle(remaining)
selected.extend(remaining[:extra])
selected.sort()
p(f"  selected {len(selected)} anchors: {selected[:10]}...{selected[-5:]}")

# write anchor plan
plan_rows = []
for rank, idx in enumerate(selected):
    a = anchor_features[idx]
    plan_rows.append({
        "selection_rank": rank,
        "anchor_id": a["anchor_id"],
        "video_id": VIDEO_ID,
        "anchor_time": a["anchor_time"],
        "start_time": a["start_time"],
        "end_time": a["end_time"],
        "duration": a["duration"],
        "score_fusion_geometry_motion": f"{a['score_fusion_geometry_motion']:.4f}",
        "score_fusion_yolo_motion": f"{a['score_fusion_yolo_motion']:.4f}",
        "score_fusion_ego_lateral": f"{a['score_fusion_ego_lateral']:.4f}",
        "score_yolo_count": f"{a['score_yolo_count']:.4f}",
        "yolo_vehicle_max": a["yolo_vehicle_max"],
        "near_ego_vehicle_count_max": a["near_ego_vehicle_count_max"],
        "person_count_max": a["person_count_max"],
        "bbox_cx_std_max": f"{a['bbox_cx_std_max']:.4f}",
        "quartile": sum(idx >= q_start for q_start in [0, len(quartiles[0]), len(quartiles[0])+len(quartiles[1]), len(quartiles[0])+len(quartiles[1])+len(quartiles[2])]),
    })

plan_path = f"{OUT}/metadata/dataset3_anchor_plan.csv"
plan_cols = list(plan_rows[0].keys())
with open(plan_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=plan_cols)
    w.writeheader(); w.writerows(plan_rows)
p(f"  wrote anchor plan -> {plan_path}")

# distribution check
q_counts = {0:0, 1:0, 2:0, 3:0}
for r in plan_rows:
    q_counts[r["quartile"]] = q_counts.get(r["quartile"], 0) + 1
p(f"  quartile distribution: {q_counts}")
time_range = (float(plan_rows[0]["anchor_time"]), float(plan_rows[-1]["anchor_time"]))
p(f"  time range: {time_range[0]:.1f}s - {time_range[-1]:.1f}s")
p(f"\n=== DONE ===")
log.close()
