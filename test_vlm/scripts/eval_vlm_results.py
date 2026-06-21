#!/usr/bin/env python3
"""Evaluate VLM batch results from JSONL.

Example:
    python test_vlm/scripts/eval_vlm_results.py \
        --pred test_vlm/outputs/qwen3_vl_smoke_fps1.jsonl
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Evaluate VLM JSONL results.")
    parser.add_argument("--pred", type=Path, required=True, help="Predictions JSONL file.")
    args = parser.parse_args()

    if not args.pred.is_file():
        print(f"ERROR: file not found: {args.pred}", file=sys.stderr)
        sys.exit(1)

    rows = []
    with open(args.pred) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"WARN: skipping malformed line", file=sys.stderr)

    total = len(rows)
    if total == 0:
        print("No rows found.")
        return

    # --- Basic stats ---
    json_ok_count = sum(1 for r in rows if r.get("json_ok"))
    relevant_dist = {}
    latency_list = []
    for r in rows:
        rel = r.get("vlm_relevant", "unknown")
        relevant_dist[rel] = relevant_dist.get(rel, 0) + 1
        lat = r.get("latency_sec")
        if isinstance(lat, (int, float)) and lat > 0:
            latency_list.append(lat)

    print("=" * 60)
    print(f"Total clips:      {total}")
    print(f"JSON OK:          {json_ok_count} / {total} ({100*json_ok_count/total:.1f}%)")

    if latency_list:
        print(f"Avg latency:      {sum(latency_list)/len(latency_list):.2f}s")
        sorted_lat = sorted(latency_list)
        print(f"Median latency:   {sorted_lat[len(sorted_lat)//2]:.2f}s")
        print(f"Min latency:      {sorted_lat[0]:.2f}s")
        print(f"Max latency:      {sorted_lat[-1]:.2f}s")
    else:
        print("Avg latency:      N/A")

    print()
    print("vlm_relevant distribution:")
    for k in sorted(relevant_dist.keys()):
        print(f"  {k:20s} : {relevant_dist[k]}")

    # --- ego_risk specific fields ---
    has_risk_level = any(r.get("vlm_risk_level") for r in rows)
    if has_risk_level:
        risk_level_dist = {}
        risk_type_dist = {}
        ego_motion_dist = {}
        affected_ego_dist = {}
        for r in rows:
            rl = r.get("vlm_risk_level", "unknown")
            risk_level_dist[rl] = risk_level_dist.get(rl, 0) + 1
            rt = r.get("vlm_risk_type", "unknown")
            risk_type_dist[rt] = risk_type_dist.get(rt, 0) + 1
            em = r.get("vlm_ego_motion", "unknown")
            ego_motion_dist[em] = ego_motion_dist.get(em, 0) + 1
            ae = r.get("vlm_affected_ego", "unknown")
            affected_ego_dist[ae] = affected_ego_dist.get(ae, 0) + 1

        print()
        print("vlm_risk_level distribution:")
        for k in sorted(risk_level_dist.keys()):
            print(f"  {k:20s} : {risk_level_dist[k]}")
        print()
        print("vlm_risk_type distribution:")
        for k in sorted(risk_type_dist.keys()):
            print(f"  {k:35s} : {risk_type_dist[k]}")
        print()
        print("vlm_ego_motion distribution:")
        for k in sorted(ego_motion_dist.keys()):
            print(f"  {k:20s} : {ego_motion_dist[k]}")
        print()
        print("vlm_affected_ego distribution:")
        for k in sorted(affected_ego_dist.keys()):
            print(f"  {k:20s} : {affected_ego_dist[k]}")

    # --- Classification metrics (only if human_label has 0/1) ---
    labeled = [r for r in rows if r.get("human_label") in ("0", "1", 0, 1)]
    if not labeled:
        print("\nNo human labels (0/1) found — skipping precision/recall.")
        print("=" * 60)
        return

    print(f"\nLabeled clips: {len(labeled)}")

    tp = fp = fn = tn = 0
    uncertain_count = 0
    fn_cases = []
    fp_cases = []

    for r in labeled:
        human = int(r["human_label"])
        vlm = r.get("vlm_relevant", "parse_error")

        if vlm == "yes":
            pred = 1
        elif vlm == "no":
            pred = 0
        else:
            uncertain_count += 1
            continue

        if pred == 1 and human == 1:
            tp += 1
        elif pred == 1 and human == 0:
            fp += 1
            fp_cases.append(r)
        elif pred == 0 and human == 1:
            fn += 1
            fn_cases.append(r)
        elif pred == 0 and human == 0:
            tn += 1

    classified = tp + fp + fn + tn
    print(f"Classified (yes/no): {classified}")
    print(f"Uncertain/skipped:   {uncertain_count}")
    print()
    print(f"  TP = {tp}")
    print(f"  FP = {fp}")
    print(f"  FN = {fn}")
    print(f"  TN = {tn}")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print()
    print(f"  Precision = {precision:.3f}")
    print(f"  Recall    = {recall:.3f}")
    print(f"  F1        = {f1:.3f}")

    if fn_cases:
        print(f"\n--- False Negatives ({len(fn_cases)}) ---")
        for r in fn_cases:
            print(f"  clip_id={r.get('clip_id')} "
                  f"start={r.get('start_sec')}s "
                  f"evidence={r.get('vlm_evidence', '')} "
                  f"raw={r.get('raw_output', '')[:120]}")

    if fp_cases:
        print(f"\n--- False Positives ({len(fp_cases)}) ---")
        for r in fp_cases:
            print(f"  clip_id={r.get('clip_id')} "
                  f"start={r.get('start_sec')}s "
                  f"evidence={r.get('vlm_evidence', '')} "
                  f"raw={r.get('raw_output', '')[:120]}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
