"""
Audit: Why is naive_oracle ClipF1 not 1.0?

For naive_oracle, predicted == labels, so predicted clips should exactly match GT clips.
If they don't, there's a bug.
"""

import csv
import json
import os
from collections import defaultdict

import numpy as np

AUDIT_DIR = os.path.dirname(os.path.abspath(__file__))
FEAS_DIR = os.path.join(os.path.dirname(AUDIT_DIR), "nuscenes_mini_feasibility")
TABLE_PATH = os.path.join(FEAS_DIR, "real_3d_query_table.csv")
CLIPS_PATH = os.path.join(FEAS_DIR, "ground_truth_clips.jsonl")


def load_query_table():
    rows = []
    with open(TABLE_PATH, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["id"] = int(row["id"])
            row["timestamp"] = int(row["timestamp"])
            row["in_fov_label"] = int(row["in_fov_label"])
            row["within_30m_label"] = int(row["within_30m_label"])
            row["ego_front_label"] = int(row["ego_front_label"])
            row["is_valid"] = int(row["is_valid"])
            rows.append(row)
    return rows


def build_instance_sequences(rows):
    instance_rows = defaultdict(list)
    for row in rows:
        instance_rows[row["instance_token"]].append(row)
    sequences = {}
    for instance_token, irows in instance_rows.items():
        irows.sort(key=lambda r: r["timestamp"])
        sequences[instance_token] = irows
    return sequences


def build_clips_for_sequence(irows, label_key, tau):
    """Build clips - must match GT construction exactly."""
    clips = []
    run_start = None
    run_length = 0
    for i, row in enumerate(irows):
        if row[label_key] == 1:
            if run_start is None:
                run_start = i
                run_length = 1
            else:
                run_length += 1
        else:
            if run_start is not None and run_length >= tau:
                clips.append((run_start, run_start + run_length - 1, run_length))
            run_start = None
            run_length = 0
    if run_start is not None and run_length >= tau:
        clips.append((run_start, run_start + run_length - 1, run_length))
    return clips


def main():
    print("=" * 60)
    print("AUDIT: Naive Oracle Consistency Check")
    print("=" * 60)

    rows = load_query_table()
    sequences = build_instance_sequences(rows)

    # Load GT clips
    gt_clips = []
    with open(CLIPS_PATH, "r") as f:
        for line in f:
            gt_clips.append(json.loads(line))

    queries = [
        ("in_fov", "in_fov_label"),
        ("within_30m", "within_30m_label"),
        ("ego_front", "ego_front_label"),
    ]
    tau_values = [2, 3, 5]

    all_audit_rows = []
    all_mismatches = []

    for query_name, label_key in queries:
        for tau in tau_values:
            print(f"\n--- {query_name}, tau={tau} ---")

            # Get GT clips for this query/tau
            gt_for_qt = [c for c in gt_clips if c["query"] == query_name and c["tau"] == tau]
            gt_set = set()
            for c in gt_for_qt:
                gt_set.add((c["instance_token"], c["start_local"], c["end_local"]))

            # Reconstruct clips from oracle labels (same as naive_oracle predicted)
            naive_set = set()
            for instance_token, irows in sequences.items():
                n = len(irows)
                if n < tau:
                    continue
                labels = [r[label_key] for r in irows]
                clips = build_clips_for_sequence(irows, label_key, tau)
                for start, end, length in clips:
                    naive_set.add((instance_token, start, end))

            # Compare
            exact_match = gt_set & naive_set
            missing_in_naive = gt_set - naive_set
            extra_in_naive = naive_set - gt_set

            print(f"  GT clips: {len(gt_set)}")
            print(f"  Naive clips: {len(naive_set)}")
            print(f"  Exact match: {len(exact_match)}")
            print(f"  Missing in naive: {len(missing_in_naive)}")
            print(f"  Extra in naive: {len(extra_in_naive)}")

            # Record mismatches
            for item in list(missing_in_naive)[:20]:
                inst, start, end = item
                all_mismatches.append({
                    "query": query_name, "tau": tau, "instance": inst,
                    "type": "missing_in_naive", "start": start, "end": end,
                })
            for item in list(extra_in_naive)[:20]:
                inst, start, end = item
                all_mismatches.append({
                    "query": query_name, "tau": tau, "instance": inst,
                    "type": "extra_in_naive", "start": start, "end": end,
                })

            all_audit_rows.append({
                "query": query_name, "tau": tau,
                "n_gt": len(gt_set), "n_naive": len(naive_set),
                "n_exact_match": len(exact_match),
                "n_missing": len(missing_in_naive),
                "n_extra": len(extra_in_naive),
                "match_rate": len(exact_match) / len(gt_set) if gt_set else 1.0,
            })

    # Write audit CSV
    audit_path = os.path.join(AUDIT_DIR, "naive_consistency.csv")
    with open(audit_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_audit_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_audit_rows)
    print(f"\nWrote audit to {audit_path}")

    # Write mismatches
    mismatch_path = os.path.join(AUDIT_DIR, "mismatch_examples.jsonl")
    with open(mismatch_path, "w") as f:
        for m in all_mismatches:
            f.write(json.dumps(m) + "\n")
    print(f"Wrote {len(all_mismatches)} mismatches to {mismatch_path}")

    # Now let's look at the actual evaluate_instance logic more carefully
    # The issue might be in the IoU matching, not the clip construction
    print("\n" + "=" * 60)
    print("DEEP DIVE: IoU Matching Analysis")
    print("=" * 60)

    # For within_30m, tau=3, pick a few instances and trace through
    query_name, label_key = "within_30m", "within_30m_label"
    tau = 3
    gt_for_qt = [c for c in gt_clips if c["query"] == query_name and c["tau"] == tau]

    # Group GT by instance
    gt_by_inst = defaultdict(list)
    for c in gt_for_qt:
        gt_by_inst[c["instance_token"]].append(c)

    # Check a few instances with clips
    instances_with_clips = [inst for inst, clips in gt_by_inst.items() if len(clips) > 0]

    for inst in instances_with_clips[:5]:
        irows = sequences[inst]
        n = len(irows)
        if n < tau:
            continue

        labels = [r[label_key] for r in irows]
        gt_clips_inst = gt_by_inst[inst]

        # Build predicted clips from labels (naive_oracle)
        pred_clips = []
        run_start = None
        run_len = 0
        for i, p in enumerate(labels):
            if p == 1:
                if run_start is None:
                    run_start = i
                    run_len = 1
                else:
                    run_len += 1
            else:
                if run_start is not None and run_len >= tau:
                    pred_clips.append((run_start, run_start + run_len - 1, run_len))
                run_start = None
                run_len = 0
        if run_start is not None and run_len >= tau:
            pred_clips.append((run_start, run_start + run_len - 1, run_len))

        gt_intervals = [(c["start_local"], c["end_local"]) for c in gt_clips_inst]

        print(f"\nInstance: {inst[:20]}..., n={n}, labels_len={len(labels)}")
        print(f"  GT clips: {gt_intervals}")
        print(f"  Pred clips: {pred_clips}")

        # Check IoU for each pred clip
        for ps, pe, pl in pred_clips:
            best_iou = 0
            best_gt = None
            for gs, ge in gt_intervals:
                inter = max(0, min(pe, ge) - max(ps, gs) + 1)
                union = max(pe, ge) - min(ps, gs) + 1
                iou = inter / union if union > 0 else 0
                if iou > best_iou:
                    best_iou = iou
                    best_gt = (gs, ge)
            print(f"  Pred ({ps},{pe}) -> best_iou={best_iou:.4f}, best_gt={best_gt}")

        # Now check the evaluate_instance logic exactly
        # This is the key: in the original code, gt_clips is a list of dicts
        # but in the audit, we're using tuples. Let me check if there's a mismatch.
        print(f"  GT clips from JSONL (local indices):")
        for c in gt_clips_inst:
            print(f"    start_local={c['start_local']}, end_local={c['end_local']}, length={c['length']}")


if __name__ == "__main__":
    main()
