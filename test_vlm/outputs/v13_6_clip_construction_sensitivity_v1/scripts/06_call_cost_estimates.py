#!/usr/bin/env python3
"""Stage 6: Simulate full-video call costs for each construction policy.

Does NOT use VLM labels. Uses proxy features for proxy-guided anchors.
"""
import csv, os, math

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_6_clip_construction_sensitivity_v1"
V13_5 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_5_realcartest_oracle_relative_v1"
VIDEO_DURATION = 3987.104

os.makedirs(f"{ROOT}/tables", exist_ok=True)

# Load proxy features
proxies = {}
with open(f"{V13_5}/tables/proxy_features_5s.csv") as f:
    for row in csv.DictReader(f):
        proxies[row["clip_id"]] = row

clips = sorted(proxies.keys(), key=lambda c: float(proxies[c]["start_time"]))
print(f"Loaded {len(clips)} proxy feature rows")

# ── Fixed-grid policies ──
policies = []

# fixed_5s_nonoverlap
n = math.ceil(VIDEO_DURATION / 5.0)
policies.append({
    "policy_name": "fixed_5s_nonoverlap",
    "anchor_strategy": "uniform_grid",
    "anchor_interval_s": 5.0,
    "clip_duration_s": 5.0,
    "total_nonoverlap_clips": n,
    "total_overlap_clips": n,
    "estimated_vlm_calls": n,
    "notes": "Current V13.5 coarse oracle grid (798 clips for 3987s video)"
})

# fixed_10s_sliding_stride5
# Same number of windows as 5s nonoverlap (stride = 5s, window = 10s)
n_10s = math.ceil((VIDEO_DURATION - 10.0) / 5.0) + 1
policies.append({
    "policy_name": "fixed_10s_sliding_stride5",
    "anchor_strategy": "sliding_window",
    "anchor_interval_s": 5.0,
    "clip_duration_s": 10.0,
    "total_nonoverlap_clips": math.ceil(VIDEO_DURATION / 10.0),
    "total_overlap_clips": n_10s,
    "estimated_vlm_calls": n_10s,
    "notes": "10s window, 5s stride — same call count as 5s but longer context"
})

# uniform_anchor_10s_context
n_10a = math.ceil(VIDEO_DURATION / 10.0)
policies.append({
    "policy_name": "uniform_anchor_10s_context",
    "anchor_strategy": "uniform",
    "anchor_interval_s": 10.0,
    "clip_duration_s": 10.0,
    "total_nonoverlap_clips": n_10a,
    "total_overlap_clips": n_10a,
    "estimated_vlm_calls": n_10a,
    "notes": "Anchor every 10s, 10s context window (±5s)"
})

# uniform_anchor_15s_context
n_15a = math.ceil(VIDEO_DURATION / 15.0)
policies.append({
    "policy_name": "uniform_anchor_15s_context",
    "anchor_strategy": "uniform",
    "anchor_interval_s": 15.0,
    "clip_duration_s": 15.0,
    "total_nonoverlap_clips": n_15a,
    "total_overlap_clips": n_15a,
    "estimated_vlm_calls": n_15a,
    "notes": "Anchor every 15s, 15s context window (±7.5s)"
})

# uniform_anchor_20s_context
n_20a = math.ceil(VIDEO_DURATION / 20.0)
policies.append({
    "policy_name": "uniform_anchor_20s_context",
    "anchor_strategy": "uniform",
    "anchor_interval_s": 20.0,
    "clip_duration_s": 20.0,
    "total_nonoverlap_clips": n_20a,
    "total_overlap_clips": n_20a,
    "estimated_vlm_calls": n_20a,
    "notes": "Anchor every 20s, 20s context window (±10s)"
})

# ── Proxy-guided anchor policies ──
# Compute proxy scores: fusion = motion_energy_z + vehicle_count_z
motions = [float(proxies[c]["motion_energy_mean"]) for c in clips]
vehicles = [float(proxies[c]["vehicle_count_mean"]) for c in clips]
objects = [float(proxies[c]["object_count_mean"]) for c in clips]

import numpy as np
motion_z = (np.array(motions) - np.mean(motions)) / (np.std(motions) + 1e-8)
vehicle_z = (np.array(vehicles) - np.mean(vehicles)) / (np.std(vehicles) + 1e-8)
proxy_fusion = motion_z + vehicle_z

# Sort clips by proxy fusion score
sorted_indices = np.argsort(-proxy_fusion)  # descending

for top_pct in [10, 20, 30]:
    n_anchors = max(1, int(len(clips) * top_pct / 100))
    n_calls_5s = n_anchors
    n_calls_10s = n_anchors
    n_calls_15s = n_anchors

    for clip_dur, policy_suffix in [(5, "5s"), (10, "10s"), (15, "15s")]:
        policies.append({
            "policy_name": f"proxy_top{top_pct}pct_anchor_{policy_suffix}",
            "anchor_strategy": f"top_{top_pct}pct_proxy_fusion",
            "anchor_interval_s": "",
            "clip_duration_s": clip_dur,
            "total_nonoverlap_clips": n_anchors,
            "total_overlap_clips": n_anchors,
            "estimated_vlm_calls": n_anchors,
            "notes": f"Top {top_pct}% anchors by motion+vehicle proxy fusion, {clip_dur}s context"
        })

# ── Write table ──
fieldnames = list(policies[0].keys())
with open(f"{ROOT}/tables/full_video_call_cost_estimates.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(policies)

print(f"Written {len(policies)} call cost estimates")
for p in policies:
    print(f"  {p['policy_name']}: {p['estimated_vlm_calls']} calls, {p['clip_duration_s']}s clips")
