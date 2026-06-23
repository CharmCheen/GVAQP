#!/usr/bin/env python3
"""Stage 3: Create VLM pilot sample of 100 clips from coarse_5s_clip_grid."""
import csv
import random
import os

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_5_realcartest_oracle_relative_v1"
random.seed(42)

# Load proxy features
proxy = {}
with open(f"{ROOT}/tables/proxy_features_5s.csv") as f:
    for row in csv.DictReader(f):
        proxy[row["clip_id"]] = row

clips = sorted(proxy.keys())
n = len(clips)
print(f"Total clips: {n}")

# 1. 25 uniform temporal
step = n // 25
uniform_ids = [clips[i] for i in range(0, n, step)][:25]

# 2. 25 random (excluding already selected)
remaining = [c for c in clips if c not in uniform_ids]
random.shuffle(remaining)
random_ids = remaining[:25]
selected = set(uniform_ids + random_ids)

# 3. 25 high motion_energy
remaining2 = [c for c in clips if c not in selected]
by_motion = sorted(remaining2, key=lambda c: float(proxy[c]["motion_energy_mean"]), reverse=True)
motion_ids = by_motion[:25]
selected.update(motion_ids)

# 4. 25 high YOLO vehicle count
remaining3 = [c for c in clips if c not in selected]
by_vehicle = sorted(remaining3, key=lambda c: float(proxy[c]["vehicle_count_mean"]), reverse=True)
vehicle_ids = by_vehicle[:25]
selected.update(vehicle_ids)

print(f"Uniform: {len(uniform_ids)}, Random: {len(random_ids)}, Motion: {len(motion_ids)}, Vehicle: {len(vehicle_ids)}")
print(f"Total unique: {len(selected)}")

# Write pilot sample table
pilot_rows = []
for i, cid in enumerate(uniform_ids):
    r = proxy[cid]
    pilot_rows.append({"clip_id": cid, "start_time": r["start_time"], "end_time": r["end_time"],
                        "sample_source": "uniform_temporal", "sample_rank": i+1, "used_for_pilot": "true"})
for i, cid in enumerate(random_ids):
    r = proxy[cid]
    pilot_rows.append({"clip_id": cid, "start_time": r["start_time"], "end_time": r["end_time"],
                        "sample_source": "random", "sample_rank": i+1, "used_for_pilot": "true"})
for i, cid in enumerate(motion_ids):
    r = proxy[cid]
    pilot_rows.append({"clip_id": cid, "start_time": r["start_time"], "end_time": r["end_time"],
                        "sample_source": "high_motion_energy", "sample_rank": i+1, "used_for_pilot": "true"})
for i, cid in enumerate(vehicle_ids):
    r = proxy[cid]
    pilot_rows.append({"clip_id": cid, "start_time": r["start_time"], "end_time": r["end_time"],
                        "sample_source": "high_yolo_vehicle_count", "sample_rank": i+1, "used_for_pilot": "true"})

with open(f"{ROOT}/tables/vlm_pilot_sample_100.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=pilot_rows[0].keys())
    writer.writeheader()
    writer.writerows(pilot_rows)
print(f"Written {len(pilot_rows)} rows to vlm_pilot_sample_100.csv")

# Print summary by source
from collections import Counter
sources = Counter(r["sample_source"] for r in pilot_rows)
for s, c in sources.most_common():
    print(f"  {s}: {c}")
