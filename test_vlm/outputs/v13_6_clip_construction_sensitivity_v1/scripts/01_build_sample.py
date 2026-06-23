#!/usr/bin/env python3
"""Stage 1: Build clip construction evaluation sample from V13.5 pilot data."""
import csv, os, json, random
from collections import Counter

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_6_clip_construction_sensitivity_v1"
V13_5 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_5_realcartest_oracle_relative_v1"
VIDEO_DURATION = 3987.104
random.seed(42)

# Load V13.5 pilot labels
pilot = []
with open(f"{V13_5}/tables/vlm_pilot_labels.csv") as f:
    pilot = list(csv.DictReader(f))
print(f"Loaded {len(pilot)} pilot labels")

# Count by label and source
positives = [r for r in pilot if r["conservative_positive"] == "yes"]
negatives = [r for r in pilot if r["conservative_positive"] == "no"]
abstain_high_yolo = [r for r in pilot if r["conservative_positive"] == "abstain" and r.get("sample_source","") == "high_yolo_vehicle_count"]
abstain_other = [r for r in pilot if r["conservative_positive"] == "abstain" and r.get("sample_source","") != "high_yolo_vehicle_count"]

print(f"Positives: {len(positives)}")
print(f"Negatives: {len(negatives)}")
print(f"Abstain high_yolo: {len(abstain_high_yolo)}")
print(f"Abstain other (random+uniform): {len(abstain_other)}")

# Select
selected_negatives = random.sample(negatives, min(10, len(negatives)))
selected_abstain_yolo = random.sample(abstain_high_yolo, min(15, len(abstain_high_yolo)))
selected_abstain_other = random.sample(abstain_other, min(15, len(abstain_other)))

selected = positives + selected_negatives + selected_abstain_yolo + selected_abstain_other
print(f"\nSelected {len(selected)} base clips:")
print(f"  Positives: {len(positives)}")
print(f"  Negatives: {len(selected_negatives)}")
print(f"  Abstain high_yolo: {len(selected_abstain_yolo)}")
print(f"  Abstain other: {len(selected_abstain_other)}")

# Deviations
if len(selected_negatives) < 10:
    print(f"  DEVIATION: only {len(negatives)} negatives available, selected all")
if len(selected_abstain_yolo) < 15:
    print(f"  DEVIATION: only {len(abstain_high_yolo)} abstain high_yolo, selected all")

# Construction policies
CONSTRUCTION_POLICIES = [
    ("fixed_5s_original", "video", None, None, None),
    ("center_4s", "video", 4.0, 2.0, None),
    ("center_6s", "video", 6.0, 3.0, None),
    ("center_10s", "video", 10.0, 5.0, None),
    ("center_15s", "video", 15.0, 7.5, None),
    ("center_20s", "video", 20.0, 10.0, None),
    ("contact_sheet_10s_5frames", "contact_sheet", 10.0, 5.0, 5),
    ("contact_sheet_10s_8frames", "contact_sheet", 10.0, 5.0, 8),
]

# Build samples
sample_rows = []
for i, base in enumerate(selected):
    start_t = float(base["start_time"])
    end_t = float(base["end_time"])
    center_t = (start_t + end_t) / 2.0

    for policy_name, input_mode, window_dur, half_span, n_frames in CONSTRUCTION_POLICIES:
        if policy_name == "fixed_5s_original":
            clip_start = start_t
            clip_end = end_t
        else:
            clip_start = max(0.0, center_t - half_span)
            clip_end = min(VIDEO_DURATION, center_t + half_span)

        duration = clip_end - clip_start
        sample_rows.append({
            "sample_id": f"v13_6_sample_{i:04d}_{policy_name}",
            "source_pilot_clip_id": base["clip_id"],
            "source_pilot_label": base["conservative_positive"],
            "source_sample_source": base.get("sample_source", ""),
            "construction_policy": policy_name,
            "input_mode": input_mode,
            "center_time": f"{center_t:.3f}",
            "start_time": f"{clip_start:.3f}",
            "end_time": f"{clip_end:.3f}",
            "duration": f"{duration:.3f}",
            "num_frames_if_contact_sheet": str(n_frames) if n_frames else "",
            "source_video_path": "/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4",
        })

os.makedirs(f"{ROOT}/tables", exist_ok=True)
with open(f"{ROOT}/tables/clip_construction_samples.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=sample_rows[0].keys())
    writer.writeheader()
    writer.writerows(sample_rows)

# Summary
by_policy = Counter(r["construction_policy"] for r in sample_rows)
print(f"\nWrote {len(sample_rows)} samples to clip_construction_samples.csv")
for p, c in sorted(by_policy.items()):
    print(f"  {p}: {c}")
n_video = sum(1 for r in sample_rows if r["input_mode"] == "video")
n_cs = sum(1 for r in sample_rows if r["input_mode"] == "contact_sheet")
print(f"Video-mode calls needed: {n_video}")
print(f"Contact-sheet-mode calls needed: {n_cs}")
print(f"Total VLM calls: {len(sample_rows)}")

# Also write input inventory
inv = [
    {"input_file": "vlm_pilot_labels.csv", "rows": len(pilot), "used_for": "base clip selection", "status": "loaded"},
    {"input_file": "coarse_5s_clip_grid.csv", "rows": 798, "used_for": "reference only", "status": "available"},
    {"input_file": "proxy_features_5s.csv", "rows": 798, "used_for": "Stage 6 proxy-guided anchor selection", "status": "available"},
    {"input_file": "raw_vlm_responses/pilot/", "rows": 100, "used_for": "reference only", "status": "available"},
]
with open(f"{ROOT}/tables/input_inventory.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=inv[0].keys())
    writer.writeheader()
    writer.writerows(inv)
print(f"Input inventory written")
