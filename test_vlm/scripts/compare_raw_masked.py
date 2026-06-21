#!/usr/bin/env python3
"""Compare raw vs masked VLM results side-by-side.

Example:
    python test_vlm/scripts/compare_raw_masked.py \
        --raw test_vlm/outputs/qwen3_vl_32b_round2_5k_raw_fps1.jsonl \
        --masked test_vlm/outputs/qwen3_vl_32b_round2_5k_masked_fps1.jsonl \
        --out test_vlm/outputs/compare_32b_raw_vs_masked.csv \
        --label 32b
"""

import argparse
import csv
import json
import sys
from pathlib import Path


def load_jsonl(path: Path) -> dict:
    rows = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                rows[obj["clip_id"]] = obj
            except (json.JSONDecodeError, KeyError):
                pass
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--masked", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", type=str, default="", help="Label prefix for columns.")
    args = parser.parse_args()

    raw = load_jsonl(args.raw)
    masked = load_jsonl(args.masked)

    all_ids = sorted(set(raw.keys()) | set(masked.keys()))

    fieldnames = [
        "clip_id", "start_sec", "end_sec",
        f"{args.label}_raw_relevant", f"{args.label}_masked_relevant",
        f"{args.label}_agree",
        f"{args.label}_raw_risk_type", f"{args.label}_masked_risk_type",
        f"{args.label}_raw_risk_level", f"{args.label}_masked_risk_level",
        f"{args.label}_raw_evidence", f"{args.label}_masked_evidence",
        f"{args.label}_raw_latency", f"{args.label}_masked_latency",
    ]

    agree_count = 0
    disagree_count = 0
    raw_yes_masked_no = 0
    raw_no_masked_yes = 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cid in all_ids:
            r = raw.get(cid, {})
            m = masked.get(cid, {})
            r_rel = r.get("vlm_relevant", "missing")
            m_rel = m.get("vlm_relevant", "missing")
            agree = "YES" if r_rel == m_rel else "NO"

            if r_rel == m_rel:
                agree_count += 1
            else:
                disagree_count += 1
                if r_rel == "yes" and m_rel == "no":
                    raw_yes_masked_no += 1
                elif r_rel == "no" and m_rel == "yes":
                    raw_no_masked_yes += 1

            writer.writerow({
                "clip_id": cid,
                "start_sec": r.get("start_sec", m.get("start_sec", "")),
                "end_sec": r.get("end_sec", m.get("end_sec", "")),
                f"{args.label}_raw_relevant": r_rel,
                f"{args.label}_masked_relevant": m_rel,
                f"{args.label}_agree": agree,
                f"{args.label}_raw_risk_type": r.get("vlm_risk_type", ""),
                f"{args.label}_masked_risk_type": m.get("vlm_risk_type", ""),
                f"{args.label}_raw_risk_level": r.get("vlm_risk_level", ""),
                f"{args.label}_masked_risk_level": m.get("vlm_risk_level", ""),
                f"{args.label}_raw_evidence": r.get("vlm_evidence", ""),
                f"{args.label}_masked_evidence": m.get("vlm_evidence", ""),
                f"{args.label}_raw_latency": r.get("latency_sec", ""),
                f"{args.label}_masked_latency": m.get("latency_sec", ""),
            })

    print(f"Comparison written: {args.out}")
    print(f"  Total: {len(all_ids)}")
    print(f"  Agree: {agree_count} ({100*agree_count/len(all_ids):.1f}%)")
    print(f"  Disagree: {disagree_count} ({100*disagree_count/len(all_ids):.1f}%)")
    print(f"  raw=yes, masked=no: {raw_yes_masked_no}")
    print(f"  raw=no, masked=yes: {raw_no_masked_yes}")


if __name__ == "__main__":
    main()
