#!/usr/bin/env python3
"""Generate a human-review CSV from manifest + VLM JSONL.

Example:
    python test_vlm/scripts/make_review_sheet.py \
        --manifest test_vlm/manifests/round1_stride10_manifest.csv \
        --pred test_vlm/outputs/qwen3_vl_round1_stride10_fps1.jsonl \
        --out test_vlm/outputs/round1_review_sheet.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Generate review sheet from manifest + JSONL.")
    parser.add_argument("--manifest", type=Path, required=True, help="Manifest CSV.")
    parser.add_argument("--pred", type=Path, required=True, help="VLM predictions JSONL.")
    parser.add_argument("--out", type=Path, required=True, help="Output review CSV.")
    args = parser.parse_args()

    # Load manifest
    manifest_rows = {}
    if args.manifest.is_file():
        with open(args.manifest, newline="") as f:
            for row in csv.DictReader(f):
                manifest_rows[row["clip_id"]] = row

    # Load predictions
    pred_rows = {}
    if args.pred.is_file():
        with open(args.pred) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    pred_rows[obj["clip_id"]] = obj
                except (json.JSONDecodeError, KeyError):
                    pass

    # Merge
    all_ids = list(manifest_rows.keys())
    # Add any pred-only ids
    for pid in pred_rows:
        if pid not in manifest_rows:
            all_ids.append(pid)

    # Detect ego_risk fields
    sample_pred = next(iter(pred_rows.values()), {})
    has_ego_fields = "vlm_risk_level" in sample_pred

    base_fields = [
        "clip_id", "video_path", "start_sec", "end_sec", "query_type",
        "human_label", "vlm_relevant",
    ]
    ego_fields = ["vlm_risk_level", "vlm_risk_type", "vlm_ego_motion", "vlm_affected_ego"] if has_ego_fields else ["vlm_risk_type"]
    tail_fields = ["vlm_confidence", "vlm_evidence", "latency_sec", "manual_note"]

    fieldnames = base_fields + ego_fields + tail_fields

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for cid in all_ids:
            m = manifest_rows.get(cid, {})
            p = pred_rows.get(cid, {})
            row = {
                "clip_id": cid,
                "video_path": m.get("video_path", p.get("video_path", "")),
                "start_sec": m.get("start_sec", p.get("start_sec", "")),
                "end_sec": m.get("end_sec", p.get("end_sec", "")),
                "query_type": m.get("query_type", p.get("query_type", "")),
                "human_label": m.get("human_label", "unknown"),
                "vlm_relevant": p.get("vlm_relevant", ""),
                "vlm_risk_type": p.get("vlm_risk_type", ""),
                "vlm_confidence": p.get("vlm_confidence", ""),
                "vlm_evidence": p.get("vlm_evidence", ""),
                "latency_sec": p.get("latency_sec", ""),
                "manual_note": "",
            }
            if has_ego_fields:
                row["vlm_risk_level"] = p.get("vlm_risk_level", "")
                row["vlm_ego_motion"] = p.get("vlm_ego_motion", "")
                row["vlm_affected_ego"] = p.get("vlm_affected_ego", "")
            writer.writerow(row)

    print(f"Review sheet written: {args.out} ({len(all_ids)} rows)")


if __name__ == "__main__":
    main()
