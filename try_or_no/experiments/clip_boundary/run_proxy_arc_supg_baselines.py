#!/usr/bin/env python3
"""Proxy / ARC-like / SUPG baselines for clip detection.

Compares:
  1. proxy_only_threshold_merge — pure proxy, no oracle
  2. arc_like_proxy_candidate_oracle_refine — proxy candidates + oracle verify
  3. supg_lite_proxy_ranked_stitch — proxy-ranked oracle selection + stitch
  4. defensive_proxy_uniform_stitch — proxy-ranked + uniform split budget

Usage:
    python experiments/clip_boundary/run_proxy_arc_supg_baselines.py \
        --csv outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv \
        --label-col label_K10 \
        --min-len 15 \
        --budgets 50,100,200,400,800,1200 \
        --trials 200 \
        --seed 42 \
        --out-dir experiments/clip_boundary/proxy_baselines_K10
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Unified evaluation
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


def clip_iou(a, b):
    s1, e1 = a
    s2, e2 = b
    inter = max(0, min(e1, e2) - max(s1, s2) + 1)
    union = max(e1, e2) - min(s1, s2) + 1
    return inter / union if union > 0 else 0.0


def length_bucket(s, e):
    L = e - s + 1
    if L < 40:
        return "short"
    if L < 100:
        return "medium"
    return "long"


def eval_clips(pred_clips, true_clips, labels):
    """Unified clip evaluation with invalid_clip_rate."""
    if not true_clips:
        return {"recall": 0.0, "precision": 0.0, "invalid_rate": 0.0,
                "avg_iou": 0.0, "num_pred_clips": len(pred_clips),
                "short_recall": 0.0, "medium_recall": 0.0, "long_recall": 0.0,
                "per_clip_hit": []}

    # Invalid rate: predicted clip contains any label==0
    invalid_count = 0
    for s, e in pred_clips:
        for k in range(s, e + 1):
            if labels[k] == 0:
                invalid_count += 1
                break
    invalid_rate = invalid_count / len(pred_clips) if pred_clips else 0.0

    # Recall
    hits = []
    for tc in true_clips:
        hit = any(clip_iou(tc, pc) >= 0.5 for pc in pred_clips)
        hits.append(hit)
    recall = sum(hits) / len(true_clips)

    # Precision
    prec_hits = 0
    for pc in pred_clips:
        if any(clip_iou(tc, pc) >= 0.5 for tc in true_clips):
            prec_hits += 1
    precision = prec_hits / len(pred_clips) if pred_clips else 0.0

    # Avg IoU
    ious = []
    for pc in pred_clips:
        best = max((clip_iou(tc, pc) for tc in true_clips), default=0.0)
        ious.append(best)
    avg_iou = np.mean(ious) if ious else 0.0

    # Length bucket recall
    buckets = {"short": [], "medium": [], "long": []}
    for i, (s, e) in enumerate(true_clips):
        buckets[length_bucket(s, e)].append(hits[i])
    short_r = np.mean(buckets["short"]) if buckets["short"] else 0.0
    med_r = np.mean(buckets["medium"]) if buckets["medium"] else 0.0
    long_r = np.mean(buckets["long"]) if buckets["long"] else 0.0

    return {
        "recall": recall, "precision": precision, "invalid_rate": invalid_rate,
        "avg_iou": avg_iou, "num_pred_clips": len(pred_clips),
        "short_recall": short_r, "medium_recall": med_r, "long_recall": long_r,
        "per_clip_hit": hits,
    }


# ---------------------------------------------------------------------------
# Oracle
# ---------------------------------------------------------------------------
class Oracle:
    def __init__(self, labels):
        self._labels = labels
        self.cache = {}
        self.phase_calls = {}

    def query(self, idx, phase="oracle"):
        idx = int(idx)
        if idx not in self.cache:
            self.cache[idx] = int(self._labels[idx])
            self.phase_calls[phase] = self.phase_calls.get(phase, 0) + 1
        return self.cache[idx]

    @property
    def calls(self):
        return len(self.cache)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def merge_pos_frames(pos_frames, gap):
    """Merge sorted positive frames into clips with gap tolerance."""
    if not pos_frames:
        return []
    clips = []
    seg_start = pos_frames[0]
    for j in range(1, len(pos_frames)):
        if pos_frames[j] - pos_frames[j - 1] > gap:
            clips.append((seg_start, pos_frames[j - 1]))
            seg_start = pos_frames[j]
    clips.append((seg_start, pos_frames[-1]))
    return clips


# ---------------------------------------------------------------------------
# Method 1: proxy_only_threshold_merge
# ---------------------------------------------------------------------------
def run_proxy_only(df, proxy_col, threshold_val, gap, min_len, labels, true_clips, N):
    """Pure proxy threshold + merge. No oracle calls."""
    if proxy_col.startswith("proxy_positive_"):
        # Binary proxy
        mask = df[proxy_col].values == 1
    else:
        # Continuous proxy
        mask = df[proxy_col].values >= threshold_val

    pos_frames = sorted(np.where(mask)[0].tolist())
    raw_clips = merge_pos_frames(pos_frames, gap)
    pred_clips = [(s, e) for s, e in raw_clips if e - s + 1 >= min_len]

    ev = eval_clips(pred_clips, true_clips, labels)
    return {
        "method": f"proxy_only_{proxy_col}",
        "proxy_col": proxy_col,
        "threshold_desc": str(threshold_val) if not proxy_col.startswith("proxy_positive_") else "binary",
        "gap": gap,
        "trial": 0,
        "recall": ev["recall"], "precision": ev["precision"],
        "invalid_rate": ev["invalid_rate"],
        "avg_iou": ev["avg_iou"],
        "num_pred_clips": ev["num_pred_clips"],
        "candidate_frame_fraction": mask.sum() / N,
        "oracle_calls": 0, "proxy_calls": N,
        "short_recall": ev["short_recall"],
        "medium_recall": ev["medium_recall"],
        "long_recall": ev["long_recall"],
        "per_clip_hit": ev["per_clip_hit"],
    }


# ---------------------------------------------------------------------------
# Method 2: arc_like_proxy_candidate_oracle_refine
# ---------------------------------------------------------------------------
def run_arc_like(df, proxy_col, threshold_val, gap, min_len, oracle, budget, N):
    """Proxy candidates → merge → oracle dense verify in candidate regions."""
    if proxy_col.startswith("proxy_positive_"):
        mask = df[proxy_col].values == 1
    else:
        mask = df[proxy_col].values >= threshold_val

    pos_frames = sorted(np.where(mask)[0].tolist())
    raw_clips = merge_pos_frames(pos_frames, gap)

    # Oracle verify within candidate regions
    pred_clips = []
    for s, e in raw_clips:
        if oracle.calls >= budget:
            break
        # Query oracle for all frames in candidate region
        region_pos = []
        for k in range(s, e + 1):
            if oracle.calls >= budget:
                break
            try:
                val = oracle.query(k, phase="refine")
            except Exception:
                break
            if val == 1:
                region_pos.append(k)
        # Split at gaps within oracle-confirmed positives
        region_clips = merge_pos_frames(region_pos, 0)
        for rc in region_clips:
            if rc[1] - rc[0] + 1 >= min_len:
                pred_clips.append(rc)

    return pred_clips, oracle.calls, mask.sum() / N


# ---------------------------------------------------------------------------
# Method 3: supg_lite_proxy_ranked_stitch
# ---------------------------------------------------------------------------
def run_supg_lite(df, proxy_col, budget, gap, min_len, oracle, N, rng):
    """Rank by proxy score, query top-budget oracle, stitch positive frames."""
    scores = df[proxy_col].values.astype(float)
    ranked = np.argsort(-scores)  # descending

    selected = ranked[:budget]
    for idx in selected:
        oracle.query(int(idx), phase="select")

    pos = sorted(k for k, v in oracle.cache.items() if v == 1)
    pred_clips = merge_pos_frames(pos, gap)
    pred_clips = [(s, e) for s, e in pred_clips if e - s + 1 >= min_len]

    return pred_clips, oracle.calls, len(selected) / N


# ---------------------------------------------------------------------------
# Method 4: defensive_proxy_uniform_stitch
# ---------------------------------------------------------------------------
def run_defensive(df, proxy_col, alpha, budget, gap, min_len, oracle, N, rng):
    """Split budget between proxy-ranked and uniform random."""
    n_proxy = int(alpha * budget)
    n_uniform = budget - n_proxy

    # Proxy-ranked portion
    scores = df[proxy_col].values.astype(float)
    ranked = np.argsort(-scores)
    proxy_selected = ranked[:n_proxy]
    for idx in proxy_selected:
        oracle.query(int(idx), phase="proxy")

    # Uniform random portion (sample from frames not yet queried)
    already_queried = set(oracle.cache.keys())
    candidates = [i for i in range(N) if i not in already_queried]
    if candidates and n_uniform > 0:
        uniform_selected = rng.choice(candidates, size=min(n_uniform, len(candidates)), replace=False)
        for idx in uniform_selected:
            oracle.query(int(idx), phase="uniform")

    pos = sorted(k for k, v in oracle.cache.items() if v == 1)
    pred_clips = merge_pos_frames(pos, gap)
    pred_clips = [(s, e) for s, e in pred_clips if e - s + 1 >= min_len]

    return pred_clips, oracle.calls, (n_proxy + n_uniform) / N


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--label-col", required=True)
    parser.add_argument("--min-len", type=int, default=15)
    parser.add_argument("--budgets", required=True)
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    budgets = [int(b) for b in args.budgets.split(",")]
    df = pd.read_csv(args.csv)
    labels = df[args.label_col].astype(int).tolist()
    N = len(labels)
    true_clips = labels_to_clips(labels, args.min_len)

    # Proxy configs
    continuous_proxies = ["proxy_score", "proxy_vehicle_count",
                          "proxy_vehicle_conf_max", "proxy_vehicle_conf_mean",
                          "proxy_vehicle_conf_sum"]
    binary_proxies = ["proxy_positive_K5", "proxy_positive_K10", "proxy_positive_K20"]
    quantiles = [0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50]
    gaps = [0, 1, 3, 5, 10, 15, 30]

    print(f"Loaded {N} frames, {len(true_clips)} true clips")
    print(f"Budgets: {budgets}, Trials: {args.trials}")
    print()

    os.makedirs(args.out_dir, exist_ok=True)

    all_rows = []
    proxy_detail_rows = []

    # -----------------------------------------------------------------------
    # Method 1: proxy_only_threshold_merge
    # -----------------------------------------------------------------------
    print("  Method 1: proxy_only_threshold_merge ...", flush=True)

    # Continuous proxies
    for pcol in continuous_proxies:
        if pcol not in df.columns:
            continue
        vals = df[pcol].values
        for q in quantiles:
            thr = np.quantile(vals, 1 - q)  # top q fraction
            for gap in gaps:
                row = run_proxy_only(df, pcol, thr, gap, args.min_len, labels, true_clips, N)
                row["threshold_desc"] = f"top{q:.0%}"
                row["budget"] = 0  # no budget dependency
                all_rows.append(row)
                proxy_detail_rows.append(row)

    # Binary proxies
    for pcol in binary_proxies:
        if pcol not in df.columns:
            continue
        for gap in gaps:
            row = run_proxy_only(df, pcol, None, gap, args.min_len, labels, true_clips, N)
            row["threshold_desc"] = "binary"
            row["budget"] = 0
            all_rows.append(row)
            proxy_detail_rows.append(row)

    print("    proxy_only done")

    # -----------------------------------------------------------------------
    # Method 2: arc_like_proxy_candidate_oracle_refine
    # -----------------------------------------------------------------------
    print("  Method 2: arc_like_proxy_candidate_oracle_refine ...", flush=True)

    arc_configs = []
    # proxy_score
    for pcol in ["proxy_score"]:
        for q in [0.05, 0.10, 0.20, 0.30]:
            thr = np.quantile(df[pcol].values, 1 - q)
            for gap in [1, 5, 10, 15]:
                arc_configs.append((pcol, thr, f"top{q:.0%}", gap))
    # proxy_vehicle_count
    for pcol in ["proxy_vehicle_count"]:
        for q in [0.05, 0.10, 0.20, 0.30]:
            thr = np.quantile(df[pcol].values, 1 - q)
            for gap in [1, 5, 10, 15]:
                arc_configs.append((pcol, thr, f"top{q:.0%}", gap))
    # proxy_positive_K10
    for gap in [1, 5, 10, 15]:
        arc_configs.append(("proxy_positive_K10", None, "binary", gap))

    for budget in budgets:
        for t in range(args.trials):
            rng = np.random.RandomState(args.seed + t)
            for pcol, thr, thr_desc, gap in arc_configs:
                oracle = Oracle(labels)
                pred_clips, calls, cand_frac = run_arc_like(
                    df, pcol, thr, gap, args.min_len, oracle, budget, N)
                ev = eval_clips(pred_clips, true_clips, labels)
                all_rows.append({
                    "method": f"arc_like_{pcol}",
                    "budget": budget, "trial": t,
                    "proxy_col": pcol, "threshold_desc": thr_desc, "gap": gap,
                    "recall": ev["recall"], "precision": ev["precision"],
                    "invalid_rate": ev["invalid_rate"], "avg_iou": ev["avg_iou"],
                    "num_pred_clips": ev["num_pred_clips"],
                    "candidate_frame_fraction": cand_frac,
                    "oracle_calls": calls, "proxy_calls": N,
                    "short_recall": ev["short_recall"],
                    "medium_recall": ev["medium_recall"],
                    "long_recall": ev["long_recall"],
                    "per_clip_hit": ev["per_clip_hit"],
                })

    print("    arc_like done")

    # -----------------------------------------------------------------------
    # Method 3: supg_lite_proxy_ranked_stitch
    # -----------------------------------------------------------------------
    print("  Method 3: supg_lite_proxy_ranked_stitch ...", flush=True)

    supg_proxies = ["proxy_score", "proxy_vehicle_count", "proxy_vehicle_conf_max"]
    for budget in budgets:
        for t in range(args.trials):
            rng = np.random.RandomState(args.seed + t)
            for pcol in supg_proxies:
                if pcol not in df.columns:
                    continue
                for gap in [1, 5, 10, 15, 30]:
                    oracle = Oracle(labels)
                    pred_clips, calls, cand_frac = run_supg_lite(
                        df, pcol, budget, gap, args.min_len, oracle, N, rng)
                    ev = eval_clips(pred_clips, true_clips, labels)
                    all_rows.append({
                        "method": "supg_lite_proxy_ranked_stitch",
                        "budget": budget, "trial": t,
                        "proxy_col": pcol, "threshold_desc": "ranked",
                        "gap": gap,
                        "recall": ev["recall"], "precision": ev["precision"],
                        "invalid_rate": ev["invalid_rate"], "avg_iou": ev["avg_iou"],
                        "num_pred_clips": ev["num_pred_clips"],
                        "candidate_frame_fraction": cand_frac,
                        "oracle_calls": calls, "proxy_calls": N,
                        "short_recall": ev["short_recall"],
                        "medium_recall": ev["medium_recall"],
                        "long_recall": ev["long_recall"],
                        "per_clip_hit": ev["per_clip_hit"],
                    })

    print("    supg_lite done")

    # -----------------------------------------------------------------------
    # Method 4: defensive_proxy_uniform_stitch
    # -----------------------------------------------------------------------
    print("  Method 4: defensive_proxy_uniform_stitch ...", flush=True)

    def_proxies = ["proxy_score", "proxy_vehicle_count"]
    alphas = [0.5, 0.7, 0.9]
    for budget in budgets:
        for t in range(args.trials):
            rng = np.random.RandomState(args.seed + t)
            for pcol in def_proxies:
                if pcol not in df.columns:
                    continue
                for alpha in alphas:
                    for gap in [1, 5, 10, 15, 30]:
                        oracle = Oracle(labels)
                        pred_clips, calls, cand_frac = run_defensive(
                            df, pcol, alpha, budget, gap, args.min_len, oracle, N, rng)
                        ev = eval_clips(pred_clips, true_clips, labels)
                        all_rows.append({
                            "method": "defensive_proxy_uniform_stitch",
                            "budget": budget, "trial": t,
                            "proxy_col": pcol,
                            "threshold_desc": f"alpha{alpha}",
                            "gap": gap, "alpha": alpha,
                            "recall": ev["recall"], "precision": ev["precision"],
                            "invalid_rate": ev["invalid_rate"], "avg_iou": ev["avg_iou"],
                            "num_pred_clips": ev["num_pred_clips"],
                            "candidate_frame_fraction": cand_frac,
                            "oracle_calls": calls, "proxy_calls": N,
                            "short_recall": ev["short_recall"],
                            "medium_recall": ev["medium_recall"],
                            "long_recall": ev["long_recall"],
                            "per_clip_hit": ev["per_clip_hit"],
                        })

    print("    defensive done")

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    trials_df = pd.DataFrame(all_rows)
    # Drop per_clip_hit for CSV (too wide)
    save_cols = [c for c in trials_df.columns if c != "per_clip_hit"]
    trials_df[save_cols].to_csv(os.path.join(args.out_dir, "trials.csv"), index=False)

    # Proxy detail (method 1 only)
    if proxy_detail_rows:
        pd.DataFrame(proxy_detail_rows).to_csv(
            os.path.join(args.out_dir, "proxy_threshold_details.csv"), index=False)

    # Summary — group by method, budget, proxy_col, threshold_desc, gap, alpha
    # Fill NaN in key columns to avoid groupby issues
    trials_df["budget"] = trials_df["budget"].fillna(0).astype(int)
    trials_df["trial"] = trials_df["trial"].fillna(0).astype(int)
    if "alpha" in trials_df.columns:
        trials_df["alpha"] = trials_df["alpha"].fillna(-1)  # sentinel for non-defensive

    group_cols = ["method", "budget", "proxy_col", "threshold_desc", "gap"]
    if "alpha" in trials_df.columns:
        group_cols = group_cols + ["alpha"]

    group_cols_actual = [c for c in group_cols if c in trials_df.columns]

    summary = (trials_df.groupby(group_cols_actual)
               .agg(mean_recall=("recall", "mean"),
                    std_recall=("recall", "std"),
                    mean_precision=("precision", "mean"),
                    std_precision=("precision", "std"),
                    mean_invalid_rate=("invalid_rate", "mean"),
                    mean_avg_iou=("avg_iou", "mean"),
                    mean_num_pred_clips=("num_pred_clips", "mean"),
                    mean_candidate_frame_fraction=("candidate_frame_fraction", "mean"),
                    mean_oracle_calls=("oracle_calls", "mean"),
                    mean_proxy_calls=("proxy_calls", "mean"),
                    mean_short_recall=("short_recall", "mean"),
                    mean_medium_recall=("medium_recall", "mean"),
                    mean_long_recall=("long_recall", "mean"))
               .reset_index())
    summary["is_official_supg"] = False
    summary.to_csv(os.path.join(args.out_dir, "summary.csv"), index=False)

    # Config
    config = {
        "csv": os.path.abspath(args.csv),
        "label_col": args.label_col,
        "min_len": args.min_len,
        "budgets": budgets,
        "trials": args.trials,
        "seed": args.seed,
        "num_frames": N,
        "num_true_clips": len(true_clips),
        "positive_ratio": round(sum(labels) / N, 6),
    }
    with open(os.path.join(args.out_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    # -----------------------------------------------------------------------
    # Terminal output: Table 1 — proxy-only best configs
    # -----------------------------------------------------------------------
    print()
    print("=" * 100)
    print("TABLE 1: Proxy-only best configs (top 5 by recall per proxy_col)")
    print("=" * 100)
    proxy_only = summary[summary["method"].str.startswith("proxy_only")]
    if not proxy_only.empty:
        for pcol in proxy_only["proxy_col"].unique():
            sub = proxy_only[proxy_only["proxy_col"] == pcol].sort_values("mean_recall", ascending=False).head(5)
            for _, r in sub.iterrows():
                print(f"  {r['proxy_col']:<30s}  thr={r['threshold_desc']:<10s}  gap={int(r['gap']):>3d}  "
                      f"recall={r['mean_recall']:.3f}  prec={r['mean_precision']:.3f}  "
                      f"invalid={r['mean_invalid_rate']:.1%}  cand_frac={r['mean_candidate_frame_fraction']:.3f}")

    # -----------------------------------------------------------------------
    # Terminal output: Table 2 — main baselines by budget
    # -----------------------------------------------------------------------
    print()
    print("=" * 100)
    print("TABLE 2: Main baselines by budget")
    print("=" * 100)

    hdr = (f"{'method':<45s}  {'budget':>6s}  {'recall':>7s}  {'prec':>6s}  "
           f"{'invld':>6s}  {'calls':>6s}  {'proxy':>6s}")
    print(hdr)
    print("-" * len(hdr))

    # Select representative configs for each method
    # proxy_only: best overall
    if not proxy_only.empty:
        best_proxy = proxy_only.sort_values("mean_recall", ascending=False).iloc[0]
        for b in budgets:
            print(f"  {'proxy_only_best':<43s}  {b:>6d}  "
                  f"{best_proxy['mean_recall']:>7.3f}  {best_proxy['mean_precision']:>6.3f}  "
                  f"{best_proxy['mean_invalid_rate']:>6.1%}  "
                  f"{best_proxy['mean_oracle_calls']:>6.0f}  {best_proxy['mean_proxy_calls']:>6.0f}")

    # arc_like: best per budget
    arc_like = summary[summary["method"].str.startswith("arc_like")]
    if not arc_like.empty:
        for b in budgets:
            sub = arc_like[arc_like["budget"] == b]
            if sub.empty:
                continue
            best = sub.sort_values("mean_recall", ascending=False).iloc[0]
            label = f"arc_like_{best['proxy_col']}"
            print(f"  {label:<43s}  {b:>6d}  "
                  f"{best['mean_recall']:>7.3f}  {best['mean_precision']:>6.3f}  "
                  f"{best['mean_invalid_rate']:>6.1%}  "
                  f"{best['mean_oracle_calls']:>6.0f}  {best['mean_proxy_calls']:>6.0f}")

    # supg_lite: best per budget
    supg = summary[summary["method"] == "supg_lite_proxy_ranked_stitch"]
    if not supg.empty:
        for b in budgets:
            sub = supg[supg["budget"] == b]
            if sub.empty:
                continue
            best = sub.sort_values("mean_recall", ascending=False).iloc[0]
            print(f"  {'supg_lite_' + best['proxy_col']:<43s}  {b:>6d}  "
                  f"{best['mean_recall']:>7.3f}  {best['mean_precision']:>6.3f}  "
                  f"{best['mean_invalid_rate']:>6.1%}  "
                  f"{best['mean_oracle_calls']:>6.0f}  {best['mean_proxy_calls']:>6.0f}")

    # defensive: best per budget
    defn = summary[summary["method"] == "defensive_proxy_uniform_stitch"]
    if not defn.empty:
        for b in budgets:
            sub = defn[defn["budget"] == b]
            if sub.empty:
                continue
            best = sub.sort_values("mean_recall", ascending=False).iloc[0]
            print(f"  {'defensive_' + best['proxy_col'] + '_a' + str(best.get('alpha', '')):<43s}  {b:>6d}  "
                  f"{best['mean_recall']:>7.3f}  {best['mean_precision']:>6.3f}  "
                  f"{best['mean_invalid_rate']:>6.1%}  "
                  f"{best['mean_oracle_calls']:>6.0f}  {best['mean_proxy_calls']:>6.0f}")

    # -----------------------------------------------------------------------
    # Terminal output: Table 3 — budget needed for recall thresholds
    # -----------------------------------------------------------------------
    print()
    print("=" * 100)
    print("TABLE 3: Budget needed for recall thresholds")
    print("=" * 100)
    print(f"  {'method':<45s}  {'>=0.5':>10s}  {'>=0.8':>10s}  {'>=0.9':>10s}")
    print("-" * 80)

    for method_prefix in ["arc_like", "supg_lite", "defensive"]:
        method_sub = summary[summary["method"].str.startswith(method_prefix)]
        if method_sub.empty:
            continue
        # Find best config overall
        best_config = method_sub.sort_values("mean_recall", ascending=False).iloc[0]
        config_key = {c: best_config[c] for c in ["proxy_col", "threshold_desc", "gap"]
                      if c in best_config.index and pd.notna(best_config.get(c))}
        # Filter to this config using query
        config_sub = method_sub.copy()
        for k, v in config_key.items():
            config_sub = config_sub[config_sub[k] == v]
        config_sub = config_sub.sort_values("budget")

        targets = {}
        for thr in [0.5, 0.8, 0.9]:
            hit = config_sub[config_sub["mean_recall"] >= thr]
            targets[thr] = int(hit.iloc[0]["budget"]) if len(hit) > 0 else None

        def fmt_b(v):
            return str(v) if v is not None else "not reached"

        method_label = f"{method_prefix}_{best_config.get('proxy_col', '')}"
        print(f"  {method_label:<45s}  {fmt_b(targets[0.5]):>10s}  "
              f"{fmt_b(targets[0.8]):>10s}  {fmt_b(targets[0.9]):>10s}")

    print(f"\nResults saved to {args.out_dir}/")


if __name__ == "__main__":
    main()
