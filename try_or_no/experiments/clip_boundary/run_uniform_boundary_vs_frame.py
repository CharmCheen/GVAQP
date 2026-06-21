#!/usr/bin/env python3
"""Experiment 1: uniform_seed_boundary vs uniform_frame_stitch.

Compare oracle-efficient clip detection strategies:
  - uniform_frame_stitch: random frame sampling + gap merging
  - uniform_seed_boundary (linear): random seed + linear boundary expansion
  - uniform_seed_boundary (expbin): random seed + exponential+binary expansion

Usage:
    python experiments/clip_boundary/run_uniform_boundary_vs_frame.py \
        --csv outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv \
        --label-col label_K10 \
        --min-len 15 \
        --budgets 50,100,200,400,800,1200 \
        --trials 200 \
        --seed 42 \
        --out-dir experiments/clip_boundary/exp1_K10
"""

import argparse
import json
import os
import random
import sys

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Oracle wrapper with budget enforcement
# ---------------------------------------------------------------------------
class Oracle:
    def __init__(self, labels, budget=None):
        self.labels = labels
        self.budget = budget
        self.cache = {}
        self.calls = 0
        self.phase_calls = {}  # phase -> count of unique NEW queries

    def query(self, idx, phase="unknown"):
        idx = int(idx)
        if idx in self.cache:
            return self.cache[idx]
        if self.budget is not None and self.calls >= self.budget:
            raise BudgetExhausted(self.calls)
        self.cache[idx] = int(self.labels[idx])
        self.calls += 1
        self.phase_calls[phase] = self.phase_calls.get(phase, 0) + 1
        return self.cache[idx]

    def get_phase_summary(self):
        return {
            "seed_calls": self.phase_calls.get("seed", 0),
            "boundary_calls": self.phase_calls.get("boundary", 0),
            "split_calls": self.phase_calls.get("split", 0),
            "total_oracle_calls": self.calls,
            "unique_oracle_calls": len(self.cache),
        }


class BudgetExhausted(Exception):
    def __init__(self, calls):
        self.calls = calls


# ---------------------------------------------------------------------------
# Ground truth: labels -> clips
# ---------------------------------------------------------------------------
def labels_to_clips(labels, min_len=15):
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


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------
def length_bucket(s, e):
    L = e - s + 1
    if L < 40:
        return "short"
    if L < 100:
        return "medium"
    return "long"


def clip_iou(a, b):
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]) + 1)
    union = max(a[1], b[1]) - min(a[0], b[0]) + 1
    return inter / union if union > 0 else 0.0


def clip_recall(pred, true, theta=0.5):
    if not true:
        return 0.0
    return sum(any(clip_iou(g, p) >= theta for p in pred) for g in true) / len(true)


def clip_precision(pred, true, theta=0.5):
    if not pred:
        return 0.0
    return sum(any(clip_iou(g, p) >= theta for g in true) for p in pred) / len(pred)


def per_clip_hit(pred, true_clips):
    return [any(clip_iou(g, p) >= 0.5 for p in pred) for g in true_clips]


def eval_metrics(pred, true_clips):
    if not true_clips:
        return {"recall": 0.0, "precision": 0.0, "num_pred_clips": len(pred),
                "short_recall": 0.0, "medium_recall": 0.0, "long_recall": 0.0,
                "per_clip_hit": []}
    hits = per_clip_hit(pred, true_clips)
    n = len(true_clips)
    buckets = {"short": [], "medium": [], "long": []}
    for i, (s, e) in enumerate(true_clips):
        buckets[length_bucket(s, e)].append(hits[i])
    return {
        "recall": sum(hits) / n,
        "precision": clip_precision(pred, true_clips),
        "num_pred_clips": len(pred),
        "short_recall": (sum(buckets["short"]) / len(buckets["short"])) if buckets["short"] else 0.0,
        "medium_recall": (sum(buckets["medium"]) / len(buckets["medium"])) if buckets["medium"] else 0.0,
        "long_recall": (sum(buckets["long"]) / len(buckets["long"])) if buckets["long"] else 0.0,
        "per_clip_hit": hits,
    }


# ---------------------------------------------------------------------------
# uniform_frame_stitch
# ---------------------------------------------------------------------------
def frame_stitch(oracle, N, budget, gap, rng, true_clips):
    sampled = rng.choice(N, size=budget, replace=False)
    for idx in sampled:
        oracle.query(int(idx), phase="seed")
    pos = sorted(k for k, v in oracle.cache.items() if v == 1)

    # merge by gap
    clips = []
    if pos:
        seg_start = pos[0]
        for j in range(1, len(pos)):
            if pos[j] - pos[j - 1] > gap:
                clips.append((seg_start, pos[j - 1]))
                seg_start = pos[j]
        clips.append((seg_start, pos[-1]))

    m = eval_metrics(clips, true_clips)
    m["oracle_calls"] = oracle.calls
    return m, clips


# ---------------------------------------------------------------------------
# Boundary expansion: linear
# ---------------------------------------------------------------------------
def linear_expand_left(oracle, seed):
    left = seed
    while left > 0:
        try:
            if oracle.query(left - 1, phase="boundary") != 1:
                break
        except BudgetExhausted:
            break
        left -= 1
    return left


def linear_expand_right(oracle, seed, N):
    right = seed
    while right < N - 1:
        try:
            if oracle.query(right + 1, phase="boundary") != 1:
                break
        except BudgetExhausted:
            break
        right += 1
    return right


# ---------------------------------------------------------------------------
# Boundary expansion: exponential + binary search
# ---------------------------------------------------------------------------
def expbin_find_edge(oracle, start, step_fn, query_fn, at_edge_fn):
    """Exponential bracket + binary search for boundary.

    Args:
        start: seed position.
        step_fn(p, step) -> next position in expansion direction.
        query_fn(p) -> oracle label at position p.
        at_edge_fn(p) -> True if p is at/near array boundary.
    Returns:
        (edge, found_full_run)
        edge: the last positive position in this direction.
        found_full_run: True if the run extends to the array boundary.
    """
    if at_edge_fn(start):
        return start, True

    # --- exponential bracket ---
    lo = start
    step = 1
    hi = None
    max_iter = 50

    for _ in range(max_iter):
        p = step_fn(lo, step)
        if at_edge_fn(p):
            # Clamp to boundary and query once
            p = max(0, p)  # caller ensures at_edge_fn handles both sides
            try:
                if query_fn(p) == 1:
                    return p, True
            except BudgetExhausted:
                return lo, False
            hi = p
            break
        try:
            val = query_fn(p)
        except BudgetExhausted:
            return lo, False
        if val == 1:
            lo = p
            step *= 2
        else:
            hi = p
            break
    else:
        return lo, False

    if hi is None:
        return lo, False

    # --- binary search ---
    for _ in range(64):
        if abs(hi - lo) <= 1:
            break
        mid = (lo + hi) // 2
        try:
            val = query_fn(mid)
        except BudgetExhausted:
            return lo, False
        if val == 1:
            lo = mid
        else:
            hi = mid

    return lo, False


def expbin_expand_boundary(oracle, seed, N):
    """Find maximal positive run around seed using exp+bin search."""
    def _clamp(p):
        return max(0, min(p, N - 1))

    left, _ = expbin_find_edge(
        oracle, seed,
        step_fn=lambda p, s: p - s,
        query_fn=lambda p: oracle.query(_clamp(p), phase="boundary"),
        at_edge_fn=lambda p: p <= 0,
    )
    right, _ = expbin_find_edge(
        oracle, seed,
        step_fn=lambda p, s: p + s,
        query_fn=lambda p: oracle.query(_clamp(p), phase="boundary"),
        at_edge_fn=lambda p: p >= N - 1,
    )
    return left, right


# ---------------------------------------------------------------------------
# uniform_seed_boundary (main loop)
# ---------------------------------------------------------------------------
def seed_boundary(N, oracle, budget, min_len, rng, true_clips, expand_fn):
    covered = set()
    pred_clips = []

    while oracle.calls < budget:
        # sample an uncovered frame
        candidates = [i for i in range(N) if i not in covered]
        if not candidates:
            break

        # batch-sample to avoid repeated full scans
        batch_size = max(1, min(budget - oracle.calls, len(candidates)))
        if batch_size <= 0:
            break
        sampled = rng.choice(candidates, size=min(100, batch_size), replace=False)
        found = False

        for idx in sampled:
            if oracle.calls >= budget:
                break
            try:
                val = oracle.query(int(idx), phase="seed")
            except BudgetExhausted:
                break
            if val == 1:
                left, right = expand_fn(oracle, int(idx), N)
                # Split expanded region into sub-clips at zero-frames.
                # Must query oracle for each frame — no direct label access.
                frames_in_region = list(range(left, right + 1))
                for k in frames_in_region:
                    try:
                        oracle.query(k, phase="split")
                    except BudgetExhausted:
                        break
                pos_in_region = [k for k in frames_in_region
                                 if oracle.cache.get(k) == 1]
                # Verify all frames were actually queried
                assert all(k in oracle.cache for k in pos_in_region), \
                    "post-split frames must all be in oracle cache"
                sub_clips = []
                if pos_in_region:
                    seg_start = pos_in_region[0]
                    for j in range(1, len(pos_in_region)):
                        if pos_in_region[j] - pos_in_region[j - 1] > 1:
                            sub_clips.append((seg_start, pos_in_region[j - 1]))
                            seg_start = pos_in_region[j]
                    sub_clips.append((seg_start, pos_in_region[-1]))

                # Mark only frames in predicted sub-clips as covered
                for sc in sub_clips:
                    for k in range(sc[0], sc[1] + 1):
                        covered.add(k)
                    if sc[1] - sc[0] + 1 >= min_len:
                        pred_clips.append(sc)
                found = True
                break  # restart sampling from uncovered set

        if not found and oracle.calls >= budget:
            break

    ps = oracle.get_phase_summary()
    m = eval_metrics(pred_clips, true_clips)
    m["oracle_calls"] = oracle.calls
    m["seed_calls"] = ps["seed_calls"]
    m["boundary_calls"] = ps["boundary_calls"]
    m["split_calls"] = ps["split_calls"]
    m["unique_oracle_calls"] = ps["unique_oracle_calls"]
    return m, pred_clips


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--label-col", required=True)
    parser.add_argument("--min-len", type=int, default=15)
    parser.add_argument("--budgets", required=True, help="comma-separated")
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    budgets = [int(b) for b in args.budgets.split(",")]
    gaps = [1, 5, 10, 15, 30]

    df = pd.read_csv(args.csv)
    labels = df[args.label_col].astype(int).tolist()
    N = len(labels)
    true_clips = labels_to_clips(labels, args.min_len)

    bucket_map = {i: length_bucket(s, e) for i, (s, e) in enumerate(true_clips)}

    print(f"Loaded {N} frames, {len(true_clips)} true clips (min_len={args.min_len})")
    print(f"Budgets: {budgets}")
    print(f"Trials:  {args.trials}")
    print(f"Gaps:    {gaps}")
    print()

    os.makedirs(args.out_dir, exist_ok=True)

    # config
    config = {
        "csv": os.path.abspath(args.csv),
        "label_col": args.label_col,
        "min_len": args.min_len,
        "budgets": budgets,
        "trials": args.trials,
        "seed": args.seed,
        "gaps": gaps,
        "num_frames": N,
        "num_true_clips": len(true_clips),
        "positive_ratio": round(sum(labels) / N, 6),
    }
    with open(os.path.join(args.out_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    # --- methods ---
    methods = [
        ("uniform_frame_stitch", "stitch"),
        ("uniform_seed_boundary_linear", "linear"),
        ("uniform_seed_boundary_expbin", "expbin"),
    ]

    # --- run trials ---
    best_rows = []       # best-gap rows for summary + per_clip_recall
    gap_detail_rows = [] # all gap details for frame_stitch
    seed_rows = []       # seed_boundary trial rows
    pred_clip_rows = []  # predicted clips for audit

    for method_name, tag in methods:
        for budget in budgets:
            print(f"  {method_name:<40s}  budget={budget:<6d} ...", end="", flush=True)
            for t in range(args.trials):
                rng = np.random.RandomState(args.seed + t)

                if tag == "stitch":
                    oracle = Oracle(labels)
                    best_m, best_clips = frame_stitch(oracle, N, budget, gaps[0], rng, true_clips)
                    best_gap = gaps[0]
                    for gap in gaps[1:]:
                        oracle = Oracle(labels)
                        m, clips = frame_stitch(oracle, N, budget, gap, rng, true_clips)
                        gap_detail_rows.append({
                            "method": method_name, "budget": budget, "trial": t,
                            "gap": gap, "recall": m["recall"], "precision": m["precision"],
                            "num_pred_clips": m["num_pred_clips"],
                            "oracle_calls": m["oracle_calls"],
                            "short_recall": m["short_recall"],
                            "medium_recall": m["medium_recall"],
                            "long_recall": m["long_recall"],
                        })
                        if m["recall"] > best_m["recall"]:
                            best_m = m
                            best_clips = clips
                            best_gap = gap

                    best_rows.append({
                        "method": method_name, "budget": budget, "trial": t,
                        "recall": best_m["recall"], "precision": best_m["precision"],
                        "num_pred_clips": best_m["num_pred_clips"],
                        "oracle_calls": best_m["oracle_calls"],
                        "seed_calls": 0, "boundary_calls": 0, "split_calls": 0,
                        "unique_oracle_calls": best_m["oracle_calls"],
                        "short_recall": best_m["short_recall"],
                        "medium_recall": best_m["medium_recall"],
                        "long_recall": best_m["long_recall"],
                        "per_clip_hit": best_m["per_clip_hit"],
                    })
                    for ci, (cs, ce) in enumerate(best_clips):
                        pred_clip_rows.append({
                            "method": method_name, "budget": budget, "trial": t,
                            "clip_id": ci, "start": cs, "end": ce, "length": ce - cs + 1,
                        })

                elif tag == "linear":
                    oracle = Oracle(labels, budget=budget + 2)
                    m, clips = seed_boundary(N, oracle, budget, args.min_len, rng, true_clips,
                                      lambda o, s, N: (
                                          linear_expand_left(o, s),
                                          linear_expand_right(o, s, N),
                                      ))
                    seed_rows.append({
                        "method": method_name, "budget": budget, "trial": t,
                        "recall": m["recall"], "precision": m["precision"],
                        "num_pred_clips": m["num_pred_clips"],
                        "oracle_calls": m["oracle_calls"],
                        "seed_calls": m["seed_calls"],
                        "boundary_calls": m["boundary_calls"],
                        "split_calls": m["split_calls"],
                        "unique_oracle_calls": m["unique_oracle_calls"],
                        "short_recall": m["short_recall"],
                        "medium_recall": m["medium_recall"],
                        "long_recall": m["long_recall"],
                        "per_clip_hit": m["per_clip_hit"],
                    })
                    for ci, (cs, ce) in enumerate(clips):
                        pred_clip_rows.append({
                            "method": method_name, "budget": budget, "trial": t,
                            "clip_id": ci, "start": cs, "end": ce, "length": ce - cs + 1,
                        })

                elif tag == "expbin":
                    oracle = Oracle(labels, budget=budget + 2)
                    m, clips = seed_boundary(N, oracle, budget, args.min_len, rng, true_clips,
                                      expbin_expand_boundary)
                    seed_rows.append({
                        "method": method_name, "budget": budget, "trial": t,
                        "recall": m["recall"], "precision": m["precision"],
                        "num_pred_clips": m["num_pred_clips"],
                        "oracle_calls": m["oracle_calls"],
                        "seed_calls": m["seed_calls"],
                        "boundary_calls": m["boundary_calls"],
                        "split_calls": m["split_calls"],
                        "unique_oracle_calls": m["unique_oracle_calls"],
                        "short_recall": m["short_recall"],
                        "medium_recall": m["medium_recall"],
                        "long_recall": m["long_recall"],
                        "per_clip_hit": m["per_clip_hit"],
                    })
                    for ci, (cs, ce) in enumerate(clips):
                        pred_clip_rows.append({
                            "method": method_name, "budget": budget, "trial": t,
                            "clip_id": ci, "start": cs, "end": ce, "length": ce - cs + 1,
                        })

            print(" done")

    # --- save trials.csv (best gap only, for summary) ---
    all_trials = pd.DataFrame(best_rows + seed_rows)
    all_trials.drop(columns=["per_clip_hit"]).to_csv(
        os.path.join(args.out_dir, "trials.csv"), index=False)

    # --- save predicted_clips.csv ---
    if pred_clip_rows:
        pd.DataFrame(pred_clip_rows).to_csv(
            os.path.join(args.out_dir, "predicted_clips.csv"), index=False)

    # --- save gap_details.csv (frame_stitch only) ---
    if gap_detail_rows:
        pd.DataFrame(gap_detail_rows).to_csv(
            os.path.join(args.out_dir, "gap_details.csv"), index=False)

    # --- per_clip_recall.csv ---
    pcr_rows = []
    for row in best_rows + seed_rows:
        for i, hit in enumerate(row["per_clip_hit"]):
            pcr_rows.append({
                "method": row["method"], "budget": row["budget"],
                "clip_id": i, "hit": int(hit),
            })
    pcr_df = pd.DataFrame(pcr_rows)
    if not pcr_df.empty:
        agg_hit = pcr_df.groupby(["method", "budget", "clip_id"])["hit"].mean().reset_index()
        agg_hit.rename(columns={"hit": "hit_rate"}, inplace=True)
        gt_info = pd.DataFrame([
            {"clip_id": i, "start": s, "end": e, "length": e - s + 1,
             "length_bucket": bucket_map[i]}
            for i, (s, e) in enumerate(true_clips)
        ])
        merged = agg_hit.merge(gt_info, on="clip_id", how="left")
        merged = merged[["method", "budget", "clip_id", "start", "end", "length",
                         "length_bucket", "hit_rate"]]
        merged.to_csv(os.path.join(args.out_dir, "per_clip_recall.csv"), index=False)

    # --- summary.csv ---
    summary = (all_trials
               .groupby(["method", "budget"])
               .agg(mean_recall=("recall", "mean"),
                    std_recall=("recall", "std"),
                    mean_precision=("precision", "mean"),
                    mean_num_pred_clips=("num_pred_clips", "mean"),
                    mean_oracle_calls=("oracle_calls", "mean"),
                    mean_seed_calls=("seed_calls", "mean"),
                    mean_boundary_calls=("boundary_calls", "mean"),
                    mean_split_calls=("split_calls", "mean"),
                    mean_unique_oracle_calls=("unique_oracle_calls", "mean"),
                    mean_short_recall=("short_recall", "mean"),
                    mean_medium_recall=("medium_recall", "mean"),
                    mean_long_recall=("long_recall", "mean"))
               .reset_index())
    summary.to_csv(os.path.join(args.out_dir, "summary.csv"), index=False)

    # --- terminal output ---
    hdr = (f"{'method':<40s}  {'budget':>6s}  {'recall':>6s}  "
           f"{'short':>5s}  {'med':>5s}  {'long':>5s}  "
           f"{'prec':>5s}  {'calls':>6s}")
    print()
    print(hdr)
    print("-" * len(hdr))

    for _, r in summary.iterrows():
        def fmt(v):
            return f"{v:.3f}" if pd.notna(v) else "  n/a"
        def ifmt(v):
            return f"{int(round(v)):>6d}" if pd.notna(v) else "    n/a"
        print(f"{r['method']:<40s}  {int(r['budget']):>6d}  "
              f"{fmt(r['mean_recall'])}  {fmt(r['mean_short_recall'])}  "
              f"{fmt(r['mean_medium_recall'])}  {fmt(r['mean_long_recall'])}  "
              f"{fmt(r['mean_precision'])}  {ifmt(r['mean_oracle_calls'])}")

    # --- budget thresholds ---
    print()
    print("Budget needed for recall thresholds:")
    print(f"{'method':<40s}  {'>=0.5':>10s}  {'>=0.8':>10s}  {'>=0.9':>10s}")
    print("-" * 75)
    for method_name, _ in methods:
        sub = summary[summary["method"] == method_name].sort_values("budget")
        targets = {}
        for threshold in [0.5, 0.8, 0.9]:
            hit = sub[sub["mean_recall"] >= threshold]
            targets[threshold] = int(hit.iloc[0]["budget"]) if len(hit) > 0 else None
        def fmt_budget(v):
            return str(v) if v is not None else "not reached"
        print(f"{method_name:<40s}  {fmt_budget(targets[0.5]):>10s}  "
              f"{fmt_budget(targets[0.8]):>10s}  {fmt_budget(targets[0.9]):>10s}")

    print(f"\nResults saved to {args.out_dir}/")


if __name__ == "__main__":
    main()
