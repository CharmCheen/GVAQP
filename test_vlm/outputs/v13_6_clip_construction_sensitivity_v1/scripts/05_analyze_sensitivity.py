#!/usr/bin/env python3
"""Stage 5: Analyze construction sensitivity from VLM labels."""
import csv, os, json, sys
from collections import Counter, defaultdict

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_6_clip_construction_sensitivity_v1"
LABELS_CSV = f"{ROOT}/tables/clip_construction_vlm_labels.csv"

if not os.path.exists(LABELS_CSV):
    print("ERROR: VLM labels not yet available. Run Stage 4 first.")
    print(f"Expected: {LABELS_CSV}")
    sys.exit(1)

rows = list(csv.DictReader(open(LABELS_CSV)))
ok_rows = [r for r in rows if r.get("vlm_call_status","") == "ok"]
print(f"Loaded {len(rows)} total rows, {len(ok_rows)} ok")

os.makedirs(f"{ROOT}/tables", exist_ok=True)

# ── Group by construction_policy ──
policies = sorted(set(r["construction_policy"] for r in ok_rows))
source_clips = sorted(set(r["source_pilot_clip_id"] for r in ok_rows))

# 1. Per-policy summary
policy_summary = []
for policy in policies:
    pr = [r for r in ok_rows if r["construction_policy"] == policy]
    n = len(pr)
    labels = Counter(r["label"] for r in pr)
    pos = labels.get("positive", 0)
    neg = labels.get("negative", 0)
    abst = labels.get("abstain", 0)

    # Among positives: completeness metrics
    pos_rows = [r for r in pr if r["label"] == "positive"]
    complete = sum(1 for r in pos_rows if r.get("complete_event_visible","").lower() == "true" and r.get("boundary_status","") == "ok")
    truncated = sum(1 for r in pos_rows if "truncated" in r.get("boundary_status",""))
    event_start_null = sum(1 for r in pos_rows if r.get("event_start","") in ("", "None", "null", "none"))
    event_end_null = sum(1 for r in pos_rows if r.get("event_end","") in ("", "None", "null", "none"))

    # Runtime
    runtimes = [float(r["runtime_seconds"]) for r in pr if r.get("runtime_seconds","")]
    mean_rt = sum(runtimes)/len(runtimes) if runtimes else 0
    median_rt = sorted(runtimes)[len(runtimes)//2] if runtimes else 0

    policy_summary.append({
        "construction_policy": policy,
        "num_inputs": n,
        "positive_count": pos,
        "negative_count": neg,
        "abstain_count": abst,
        "positive_rate": pos/n if n else 0,
        "negative_rate": neg/n if n else 0,
        "abstain_rate": abst/n if n else 0,
        "complete_event_count": complete,
        "complete_event_rate": complete/pos if pos else 0,
        "truncation_count": truncated,
        "truncation_rate": truncated/pos if pos else 0,
        "event_start_null_count": event_start_null,
        "event_start_null_rate": event_start_null/pos if pos else 0,
        "event_end_null_count": event_end_null,
        "event_end_null_rate": event_end_null/pos if pos else 0,
        "mean_runtime_seconds": f"{mean_rt:.1f}",
        "median_runtime_seconds": f"{median_rt:.1f}",
    })

with open(f"{ROOT}/tables/clip_construction_policy_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=policy_summary[0].keys())
    writer.writeheader()
    writer.writerows(policy_summary)
print(f"Policy summary: {len(policy_summary)} policies")

# 2. Pairwise comparison vs fixed_5s
fixed_map = {}
for r in ok_rows:
    if r["construction_policy"] == "fixed_5s_original":
        fixed_map[r["source_pilot_clip_id"]] = r

pairwise = []
for policy in policies:
    if policy == "fixed_5s_original":
        continue
    pr = [r for r in ok_rows if r["construction_policy"] == policy]
    flips = 0
    agreements = 0
    total = 0
    pos_ret = 0
    pos_lost = 0
    fixed_pos = 0
    for r in pr:
        cid = r["source_pilot_clip_id"]
        if cid not in fixed_map:
            continue
        fixed = fixed_map[cid]
        total += 1
        if r["label"] == fixed["label"]:
            agreements += 1
        else:
            flips += 1
        if fixed["label"] == "positive":
            fixed_pos += 1
            if r["label"] == "positive":
                pos_ret += 1
            else:
                pos_lost += 1

    pairwise.append({
        "construction_policy": policy,
        "comparison_baseline": "fixed_5s_original",
        "num_paired": total,
        "label_agreements": agreements,
        "label_flips": flips,
        "label_flip_rate": flips/total if total else 0,
        "positive_retention_vs_fixed_5s": pos_ret/fixed_pos if fixed_pos else 0,
        "positive_lost_vs_fixed_5s": pos_lost/fixed_pos if fixed_pos else 0,
        "fixed_5s_positive_count": fixed_pos,
    })

with open(f"{ROOT}/tables/clip_construction_pairwise_comparison.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=pairwise[0].keys())
    writer.writeheader()
    writer.writerows(pairwise)
print(f"Pairwise comparison: {len(pairwise)} policies vs fixed_5s")

# Print key results
print("\n=== KEY FINDINGS ===")
for ps in policy_summary:
    print(f"{ps['construction_policy']:30s} pos={ps['positive_count']:2d}/{ps['num_inputs']:2d} "
          f"({ps['positive_rate']:.2f}) neg={ps['negative_count']:2d} ({ps['negative_rate']:.2f}) "
          f"abst={ps['abstain_count']:2d} ({ps['abstain_rate']:.2f}) "
          f"complete={ps['complete_event_rate']:.2f} trunc={ps['truncation_rate']:.2f}")

for pw in pairwise:
    print(f"vs fixed_5s: {pw['construction_policy']:30s} flip={pw['label_flip_rate']:.2f} "
          f"pos_retention={pw['positive_retention_vs_fixed_5s']:.2f}")
