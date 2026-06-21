#!/usr/bin/env python3
"""Minimal probe: read oracle labels from CSV, merge consecutive positives
into true clips, and output clip-length distribution statistics.

Usage:
    python experiments/clip_boundary/probe_clip_lengths.py \
        --csv path/to/oracle.csv \
        --label-col oracle_label \
        --min-len 15 \
        --out-dir experiments/clip_boundary/results
"""

import argparse
import csv
import json
import os
import statistics
import sys


def labels_to_clips(labels, min_len=15):
    """Merge consecutive positive frames into clips.

    Args:
        labels: list/array of 0/1 values.
        min_len: minimum clip length to keep.

    Returns:
        list of (start, end) tuples (inclusive indices).
    """
    clips = []
    start = None

    for i, y in enumerate(labels):
        if y == 1 and start is None:
            start = i

        is_end = (y == 0) or (i == len(labels) - 1)
        if is_end and start is not None:
            end = i - 1 if y == 0 else i
            if end - start + 1 >= min_len:
                clips.append((start, end))
            start = None

    return clips


def percentile(data, p):
    """Compute the p-th percentile (0-100) of a non-empty list."""
    if not data:
        return float("nan")
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100.0
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def main():
    parser = argparse.ArgumentParser(description="Probe oracle clip lengths")
    parser.add_argument("--csv", required=True, help="Path to oracle CSV")
    parser.add_argument("--label-col", required=True, help="Column name for oracle labels")
    parser.add_argument("--min-len", type=int, default=15, help="Minimum clip length (default: 15)")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    args = parser.parse_args()

    # --- Read CSV ----------------------------------------------------------
    if not os.path.isfile(args.csv):
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    with open(args.csv, "r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            print("ERROR: CSV has no header row.", file=sys.stderr)
            sys.exit(1)

        if args.label_col not in fieldnames:
            print(f"ERROR: column '{args.label_col}' not found.", file=sys.stderr)
            print(f"Available columns: {fieldnames}", file=sys.stderr)
            sys.exit(1)

        rows = list(reader)

    # --- Extract labels ----------------------------------------------------
    labels = []
    for row in rows:
        val = row[args.label_col]
        labels.append(int(val))

    num_frames = len(labels)
    num_positive = sum(labels)
    positive_ratio = num_positive / num_frames if num_frames > 0 else 0.0

    # --- Merge into clips --------------------------------------------------
    clips = labels_to_clips(labels, min_len=args.min_len)
    clip_lengths = [end - start + 1 for start, end in clips]

    # --- Statistics --------------------------------------------------------
    if clip_lengths:
        len_mean = statistics.mean(clip_lengths)
        len_median = statistics.median(clip_lengths)
        len_p25 = percentile(clip_lengths, 25)
        len_p75 = percentile(clip_lengths, 75)
        len_p90 = percentile(clip_lengths, 90)
        len_p95 = percentile(clip_lengths, 95)
        len_max = max(clip_lengths)
    else:
        len_mean = len_median = len_p25 = len_p75 = len_p90 = len_p95 = len_max = 0

    # --- Print to terminal ------------------------------------------------
    print(f"N frames:              {num_frames}")
    print(f"positive frames:       {num_positive}")
    print(f"positive frame ratio:  {positive_ratio:.4f}")
    print(f"true clip count:       {len(clips)}")
    print(f"clip length mean:      {len_mean:.1f}")
    print(f"clip length median:    {len_median:.1f}")
    print(f"clip length p25:       {len_p25:.1f}")
    print(f"clip length p75:       {len_p75:.1f}")
    print(f"clip length p90:       {len_p90:.1f}")
    print(f"clip length p95:       {len_p95:.1f}")
    print(f"clip length max:       {len_max}")

    # Top 20 longest clips
    if clips:
        ranked = sorted(zip(clips, clip_lengths), key=lambda x: -x[1])
        top_n = ranked[:20]
        print(f"\ntop {len(top_n)} longest clips:")
        print(f"  {'clip_id':>7s}  {'start':>7s}  {'end':>7s}  {'length':>7s}")
        for idx, ((s, e), l) in enumerate(top_n):
            print(f"  {idx:>7d}  {s:>7d}  {e:>7d}  {l:>7d}")

    # --- Save results ------------------------------------------------------
    os.makedirs(args.out_dir, exist_ok=True)

    # clip_lengths.csv
    clip_csv_path = os.path.join(args.out_dir, "clip_lengths.csv")
    with open(clip_csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["clip_id", "start", "end", "length"])
        for idx, ((s, e), l) in enumerate(zip(clips, clip_lengths)):
            writer.writerow([idx, s, e, l])
    print(f"\nSaved: {clip_csv_path}")

    # clip_length_summary.json
    summary = {
        "csv_path": os.path.abspath(args.csv),
        "label_col": args.label_col,
        "num_frames": num_frames,
        "num_positive_frames": num_positive,
        "positive_frame_ratio": round(positive_ratio, 6),
        "min_len": args.min_len,
        "num_true_clips": len(clips),
        "length_mean": round(len_mean, 2),
        "length_median": round(len_median, 2),
        "length_p25": round(len_p25, 2),
        "length_p75": round(len_p75, 2),
        "length_p90": round(len_p90, 2),
        "length_p95": round(len_p95, 2),
        "length_max": len_max,
    }
    summary_path = os.path.join(args.out_dir, "clip_length_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved: {summary_path}")


if __name__ == "__main__":
    main()
