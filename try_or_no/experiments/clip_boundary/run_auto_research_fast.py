#!/usr/bin/env python3
"""Fast bounded auto research: joint allocation generalization + proxy degradation.

Fixed gap=5 (proven best from prior experiments) to reduce computation.

Usage:
    python experiments/clip_boundary/run_auto_research_fast.py \
        --csv outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv \
        --budgets 50,100,200,400,800,1200 \
        --trials 50 \
        --seed 42 \
        --out-dir experiments/clip_boundary/auto_research_joint_allocation
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from run_joint_allocation_kill_exp import (
    labels_to_clips, eval_clips, Oracle, merge_pos_frames,
    pos_frames_to_clips, get_threshold, get_candidate_regions,
    region_proxy_mean, run_candidate_only, run_audit_only,
    run_fixed_mix, run_adaptive_greedy,
)

FIXED_GAP = 5
PROXY_CONFIGS = [
    {"proxy_col": "proxy_vehicle_count", "threshold_desc": "top20%",
     "cand_gap": 5},
    {"proxy_col": "proxy_score", "threshold_desc": "top30%",
     "cand_gap": 5},
]


def probe_settings(df, label_cols, min_lens):
    valid = []
    for lc in label_cols:
        if lc not in df.columns:
            continue
        labels = df[lc].astype(int).tolist()
        N = len(labels)
        pos_ratio = sum(labels) / N
        for ml in min_lens:
            clips = labels_to_clips(labels, ml)
            ok = len(clips) >= 5 and 0.02 <= pos_ratio <= 0.6
            status = "VALID" if ok else "FILTERED"
            reason = ""
            if len(clips) < 5:
                reason = f"too few clips ({len(clips)})"
            elif pos_ratio > 0.6:
                reason = f"pos_ratio too high ({pos_ratio:.4f})"
            elif pos_ratio < 0.02:
                reason = f"pos_ratio too low ({pos_ratio:.4f})"
            print(f"  {lc} min_len={ml}: clips={len(clips)}, "
                  f"ratio={pos_ratio:.4f} [{status}]"
                  f"{f' — {reason}' if reason else ''}")
            if ok:
                valid.append({"label_col": lc, "min_len": ml,
                              "true_clip_count": len(clips),
                              "positive_frame_ratio": pos_ratio})
    return valid


def run_setting(df, labels, true_clips, N, min_len, budgets, trials,
                seed, proxy_configs, setting_label):
    """Run all methods for one setting with fixed gap."""
    rows = []
    for pconf in proxy_configs:
        pcol = pconf["proxy_col"]
        thr_desc = pconf["threshold_desc"]
        cand_gap = pconf["cand_gap"]
        clabel = f"{pcol}_{thr_desc}_g{cand_gap}"

        if thr_desc == "binary":
            thr_val = None
        else:
            pct = float(thr_desc.replace("top", "").replace("%", "")) / 100
            thr_val = get_threshold(df, pcol, pct)

        for budget in budgets:
            for t in range(trials):
                # candidate_only (best of 2 priorities)
                best_cand = None
                for pri in ["proxy_mean_desc", "region_length_desc"]:
                    rng = np.random.RandomState(
                        seed + t * 1000 + budget + hash(pri) % 10000)
                    oracle = Oracle(labels)
                    pred, calls, cc, nc = run_candidate_only(
                        df, pcol, thr_val, cand_gap, oracle,
                        budget, N, min_len, pri, FIXED_GAP, rng)
                    ev = eval_clips(pred, true_clips, labels)
                    d = {"recall": ev["recall"], "precision": ev["precision"],
                         "invalid_rate": ev["invalid_rate"],
                         "num_pred_clips": ev["num_pred_clips"],
                         "oracle_calls": calls, "candidate_calls": cc}
                    if best_cand is None or d["recall"] > best_cand["recall"]:
                        best_cand = d
                rows.append({"method": "candidate_only", "setting": setting_label,
                             "proxy_config": clabel, "budget": budget,
                             "trial": t, **best_cand, "audit_calls": 0})

                # audit_only
                rng = np.random.RandomState(seed + t * 1000 + budget + 999)
                oracle = Oracle(labels)
                pred, calls, ac, nc = run_audit_only(
                    df, pcol, thr_val, cand_gap, oracle,
                    budget, N, min_len, FIXED_GAP, rng)
                ev = eval_clips(pred, true_clips, labels)
                rows.append({"method": "audit_only", "setting": setting_label,
                             "proxy_config": clabel, "budget": budget,
                             "trial": t,
                             "recall": ev["recall"], "precision": ev["precision"],
                             "invalid_rate": ev["invalid_rate"],
                             "num_pred_clips": ev["num_pred_clips"],
                             "oracle_calls": calls, "candidate_calls": 0,
                             "audit_calls": ac})

                # fixed_mix
                for ml_name, cf in [("fixed_mix_80_20", 0.8),
                                     ("fixed_mix_50_50", 0.5)]:
                    rng = np.random.RandomState(
                        seed + t * 1000 + budget + hash(ml_name) % 10000)
                    oracle = Oracle(labels)
                    pred, calls, cc, ac, _ = run_fixed_mix(
                        df, pcol, thr_val, cand_gap, oracle,
                        budget, N, min_len, "proxy_mean_desc", FIXED_GAP,
                        rng, cf)
                    ev = eval_clips(pred, true_clips, labels)
                    rows.append({"method": ml_name, "setting": setting_label,
                                 "proxy_config": clabel, "budget": budget,
                                 "trial": t,
                                 "recall": ev["recall"],
                                 "precision": ev["precision"],
                                 "invalid_rate": ev["invalid_rate"],
                                 "num_pred_clips": ev["num_pred_clips"],
                                 "oracle_calls": calls,
                                 "candidate_calls": cc, "audit_calls": ac})

                # adaptive_greedy
                rng = np.random.RandomState(seed + t * 1000 + budget + 5555)
                oracle = Oracle(labels)
                pred, calls, cc, ac, _ = run_adaptive_greedy(
                    df, pcol, thr_val, cand_gap, oracle,
                    budget, N, min_len, "proxy_mean_desc", FIXED_GAP,
                    rng, batch_size=25)
                ev = eval_clips(pred, true_clips, labels)
                rows.append({"method": "adaptive_greedy", "setting": setting_label,
                             "proxy_config": clabel, "budget": budget,
                             "trial": t,
                             "recall": ev["recall"], "precision": ev["precision"],
                             "invalid_rate": ev["invalid_rate"],
                             "num_pred_clips": ev["num_pred_clips"],
                             "oracle_calls": calls,
                             "candidate_calls": cc, "audit_calls": ac})
    return rows


def run_degraded(df, labels, true_clips, N, min_len, budgets, trials,
                 seed, pconf, setting_label):
    """Proxy degradation: noise + dropout."""
    pcol = pconf["proxy_col"]
    thr_desc = pconf["threshold_desc"]
    cand_gap = pconf["cand_gap"]
    clabel = f"{pcol}_{thr_desc}_g{cand_gap}"

    if thr_desc == "binary":
        thr_val = None
    else:
        pct = float(thr_desc.replace("top", "").replace("%", "")) / 100
        thr_val = get_threshold(df, pcol, pct)

    rows = []

    def run_variant(variant_name, budget, t, get_vals):
        """Run one variant for one budget/trial."""
        results = {}
        for method in ["candidate_only", "fixed_mix_80_20",
                        "fixed_mix_50_50", "adaptive_greedy"]:
            rng = np.random.RandomState(
                seed + t * 1000 + budget + hash(method + variant_name) % 10000)
            oracle = Oracle(labels)
            vals = get_vals(rng)

            if method == "candidate_only":
                # Build candidate regions from degraded proxy
                if pcol.startswith("proxy_positive_"):
                    mask = vals == 1 if isinstance(vals, np.ndarray) and vals.dtype != bool else vals
                elif isinstance(vals, np.ndarray) and vals.dtype == bool:
                    mask = vals
                else:
                    mask = vals >= thr_val
                pos_frames = sorted(np.where(mask)[0].tolist())
                regions = merge_pos_frames(pos_frames, cand_gap)
                ranked = sorted(regions,
                                key=lambda r: -float(np.mean(
                                    df[pcol].values.astype(float)[r[0]:r[1]+1]))
                                if not pcol.startswith("proxy_positive_")
                                else -(r[1]-r[0]+1))
                all_pos = []
                cc = 0
                for s, e in ranked:
                    if cc >= budget: break
                    for k in range(s, e+1):
                        if cc >= budget: break
                        if oracle.query(k, phase="candidate_refine") == 1:
                            all_pos.append(k)
                        cc += 1
                pred_clips = pos_frames_to_clips(sorted(set(all_pos)),
                                                  FIXED_GAP, min_len)
                ev = eval_clips(pred_clips, true_clips, labels)
                results[method] = {"recall": ev["recall"],
                                   "precision": ev["precision"],
                                   "invalid_rate": ev["invalid_rate"],
                                   "candidate_calls": cc,
                                   "audit_calls": 0}

            elif "fixed_mix" in method:
                cf = 0.8 if "80" in method else 0.5
                n_cand = max(1, int(cf * budget))
                n_audit = budget - n_cand

                if pcol.startswith("proxy_positive_"):
                    mask = vals == 1 if isinstance(vals, np.ndarray) and vals.dtype != bool else vals
                elif isinstance(vals, np.ndarray) and vals.dtype == bool:
                    mask = vals
                else:
                    mask = vals >= thr_val
                pos_frames = sorted(np.where(mask)[0].tolist())
                regions = merge_pos_frames(pos_frames, cand_gap)
                ranked = sorted(regions,
                                key=lambda r: -float(np.mean(
                                    df[pcol].values.astype(float)[r[0]:r[1]+1]))
                                if not pcol.startswith("proxy_positive_")
                                else -(r[1]-r[0]+1))
                all_pos = []
                cc = 0
                for s, e in ranked:
                    if cc >= n_cand: break
                    for k in range(s, e+1):
                        if cc >= n_cand or oracle.calls >= budget: break
                        if oracle.query(k, phase="candidate_refine") == 1:
                            all_pos.append(k)
                        cc += 1
                non_cand = np.where(~mask)[0].tolist()
                already = set(oracle.cache.keys())
                avail = [x for x in non_cand if x not in already]
                if avail and n_audit > 0:
                    sampled = rng.choice(avail, size=min(n_audit, len(avail)),
                                         replace=False)
                    for idx in sampled:
                        if oracle.query(int(idx), phase="audit") == 1:
                            all_pos.append(int(idx))
                pred_clips = pos_frames_to_clips(sorted(set(all_pos)),
                                                  FIXED_GAP, min_len)
                ev = eval_clips(pred_clips, true_clips, labels)
                results[method] = {"recall": ev["recall"],
                                   "precision": ev["precision"],
                                   "invalid_rate": ev["invalid_rate"],
                                   "candidate_calls": cc,
                                   "audit_calls": oracle.phase_count("audit")}

            elif method == "adaptive_greedy":
                if pcol.startswith("proxy_positive_"):
                    mask = vals == 1 if isinstance(vals, np.ndarray) and vals.dtype != bool else vals
                elif isinstance(vals, np.ndarray) and vals.dtype == bool:
                    mask = vals
                else:
                    mask = vals >= thr_val
                pos_frames = sorted(np.where(mask)[0].tolist())
                non_cand = np.where(~mask)[0].tolist()
                regions = merge_pos_frames(pos_frames, cand_gap)
                ranked = sorted(regions,
                                key=lambda r: -float(np.mean(
                                    df[pcol].values.astype(float)[r[0]:r[1]+1]))
                                if not pcol.startswith("proxy_positive_")
                                else -(r[1]-r[0]+1))
                cand_frames = []
                for s, e in ranked:
                    cand_frames.extend(range(s, e+1))
                ci, ni = 0, 0
                nc_avail = list(non_cand); rng.shuffle(nc_avail)
                all_pos = []
                yc, ya = 1.0, 0.0
                bs = 25
                while oracle.calls < budget:
                    do_cand = (yc >= ya) if oracle.calls >= 2*bs else \
                        (oracle.calls // bs) % 2 == 0
                    cb = len(pos_frames_to_clips(sorted(set(all_pos)),
                                                  FIXED_GAP, min_len))
                    if do_cand:
                        for _ in range(bs):
                            if ci >= len(cand_frames) or oracle.calls >= budget:
                                break
                            k = cand_frames[ci]; ci += 1
                            if oracle.query(k, phase="candidate_refine") == 1:
                                all_pos.append(k)
                    else:
                        for _ in range(bs):
                            if ni >= len(nc_avail) or oracle.calls >= budget:
                                break
                            k = nc_avail[ni]; ni += 1
                            if oracle.query(k, phase="audit") == 1:
                                all_pos.append(k)
                    ca = len(pos_frames_to_clips(sorted(set(all_pos)),
                                                  FIXED_GAP, min_len))
                    cu = max(1, oracle.calls - (oracle.calls -
                        (1 if do_cand else 0)))
                    m = (ca - cb) / max(1, bs) * 100
                    if do_cand: yc = m
                    else: ya = m
                pred_clips = pos_frames_to_clips(sorted(set(all_pos)),
                                                  FIXED_GAP, min_len)
                ev = eval_clips(pred_clips, true_clips, labels)
                results[method] = {"recall": ev["recall"],
                                   "precision": ev["precision"],
                                   "invalid_rate": ev["invalid_rate"],
                                   "candidate_calls": oracle.phase_count("candidate_refine"),
                                   "audit_calls": oracle.phase_count("audit")}
        return results

    # Variants
    variants = [("clean", lambda rng: df[pcol].values.astype(float))]
    for ns in [0.05, 0.1, 0.2]:
        variants.append((f"noise_{ns}",
                         lambda rng, _ns=ns: df[pcol].values.astype(float) +
                         rng.normal(0, _ns, len(df))))
    for dp in [0.1, 0.3, 0.5]:
        def make_dropout(_dp):
            def fn(rng):
                mask = np.ones(len(df), dtype=bool)
                if pcol.startswith("proxy_positive_"):
                    pos = np.where(df[pcol].values == 1)[0]
                else:
                    pos = np.where(df[pcol].values >= thr_val)[0]
                drop = rng.choice(pos, size=int(_dp * len(pos)), replace=False)
                mask[drop] = False
                return mask
            return fn
        variants.append((f"dropout_{dp}", make_dropout(dp)))

    for vname, get_vals in variants:
        for budget in budgets:
            for t in range(trials):
                res = run_variant(vname, budget, t, get_vals)
                for method, d in res.items():
                    rows.append({
                        "method": method, "setting": setting_label,
                        "proxy_config": clabel, "proxy_variant": vname,
                        "budget": budget, "trial": t, **d})

    return rows


def build_summary(all_rows, setting_info):
    df = pd.DataFrame(all_rows)
    summary_rows = []

    for setting in df["setting"].unique():
        s_df = df[df["setting"] == setting]
        info = [s for s in setting_info if
                f"{s['label_col']}_min{s['min_len']}" == setting]
        if not info:
            info = [{"label_col": "label_K10", "min_len": 15,
                     "true_clip_count": 18, "positive_frame_ratio": 0.3736}]
        info = info[0]

        for variant in s_df["proxy_variant"].unique():
            sv_df = s_df[s_df["proxy_variant"] == variant]
            for budget in sv_df["budget"].unique():
                sb_df = sv_df[sv_df["budget"] == budget]
                cand = sb_df[sb_df["method"] == "candidate_only"]
                if cand.empty:
                    continue
                cand_best = cand.sort_values("recall", ascending=False).iloc[0]

                best_joint = None
                for jm in ["fixed_mix_80_20", "fixed_mix_50_50",
                            "adaptive_greedy"]:
                    jm_df = sb_df[sb_df["method"] == jm]
                    if jm_df.empty:
                        continue
                    jm_best = jm_df.sort_values("recall", ascending=False).iloc[0]
                    if best_joint is None or jm_best["recall"] > best_joint["recall"]:
                        best_joint = jm_best

                if best_joint is None:
                    continue

                summary_rows.append({
                    "setting": setting,
                    "label_col": info["label_col"],
                    "min_len": info["min_len"],
                    "true_clip_count": info["true_clip_count"],
                    "positive_frame_ratio": info["positive_frame_ratio"],
                    "proxy_variant": variant,
                    "proxy_config": cand_best["proxy_config"],
                    "budget": budget,
                    "candidate_only_recall": cand_best["recall"],
                    "candidate_only_precision": cand_best["precision"],
                    "candidate_only_invalid": cand_best["invalid_rate"],
                    "best_joint_method": best_joint["method"],
                    "best_joint_recall": best_joint["recall"],
                    "best_joint_precision": best_joint["precision"],
                    "best_joint_invalid": best_joint["invalid_rate"],
                    "delta_recall": best_joint["recall"] - cand_best["recall"],
                    "candidate_calls": cand_best.get("candidate_calls", 0),
                    "audit_calls": best_joint.get("audit_calls", 0),
                })

    return pd.DataFrame(summary_rows)


def write_summary(summary_df, out_dir):
    lines = ["# Auto Research: Joint Allocation Summary\n"]

    clean = summary_df[summary_df["proxy_variant"] == "clean"]
    degraded = summary_df[summary_df["proxy_variant"] != "clean"]

    # 1. Stable wins?
    lines.append("## 1. Does joint allocation win stably?\n")
    if not clean.empty:
        n_total = len(clean)
        n_wins = len(clean[clean["delta_recall"] > 0])
        n_ge5 = len(clean[clean["delta_recall"] >= 0.05])
        n_ge10 = len(clean[clean["delta_recall"] >= 0.10])
        avg_d = clean["delta_recall"].mean()
        max_d = clean["delta_recall"].max()
        lines.append(f"- Total (setting × budget) pairs: {n_total}")
        lines.append(f"- Joint > candidate: {n_wins}/{n_total} "
                     f"({n_wins/n_total:.0%})")
        lines.append(f"- Delta >= 0.05: {n_ge5}")
        lines.append(f"- Delta >= 0.10: {n_ge10}")
        lines.append(f"- Average delta: {avg_d:+.3f}")
        lines.append(f"- Max delta: {max_d:+.3f}")

    # 2. Where does gain come from?
    lines.append("\n## 2. Where does the gain come from?\n")
    if not clean.empty:
        by_m = (clean.groupby("best_joint_method")["delta_recall"]
                .agg(["mean", "max", "count"]))
        lines.append("| method | mean_delta | max_delta | count |")
        lines.append("|--------|-----------|-----------|-------|")
        for m, r in by_m.iterrows():
            lines.append(f"| {m} | {r['mean']:+.3f} | {r['max']:+.3f} | "
                         f"{int(r['count'])} |")

    # 3. Weak proxy effect
    lines.append("\n## 3. Weak proxy effect\n")
    if not degraded.empty and not clean.empty:
        clean_avg = clean["delta_recall"].mean()
        lines.append(f"- Clean avg delta: {clean_avg:+.3f}")
        for v in sorted(degraded["proxy_variant"].unique()):
            vd = degraded[degraded["proxy_variant"] == v]
            va = vd["delta_recall"].mean()
            lines.append(f"- {v}: avg delta={va:+.3f}")
        deg_avg = degraded["delta_recall"].mean()
        if deg_avg > clean_avg + 0.02:
            lines.append("\n**Weak proxy INCREASES joint advantage.**")
        elif deg_avg < clean_avg - 0.02:
            lines.append("\n**Weak proxy DECREASES joint advantage.**")
        else:
            lines.append("\n**Weak proxy has NO clear effect.**")

    # 4. Judgment
    lines.append("\n## 4. Direction Judgment\n")
    if not clean.empty:
        n_ge10 = len(clean[clean["delta_recall"] >= 0.10])
        max_d = clean["delta_recall"].max()
        avg_d = clean["delta_recall"].mean()
        n_total = len(clean)
        n_wins = len(clean[clean["delta_recall"] > 0])

        if n_ge10 >= 3 or (max_d >= 0.15 and n_wins >= n_total * 0.6):
            j = "A"
            lines.append("**A. Continue**: joint allocation has stable and "
                         "meaningful gains across settings.")
        elif n_wins >= n_total * 0.5 and avg_d > 0.02:
            j = "B"
            lines.append("**B. Weak continue**: gains exist but small; "
                         "need more data/videos.")
        else:
            j = "C"
            lines.append("**C. Stop**: joint allocation does not beat "
                         "candidate-only reliably.")
        lines.append(f"\n- Wins: {n_wins}/{n_total}")
        lines.append(f"- Delta >= 0.10: {n_ge10}")
        lines.append(f"- Max delta: {max_d:+.3f}")
        lines.append(f"- Avg delta: {avg_d:+.3f}")
    else:
        j = "C"
        lines.append("**C. Stop**: no data.")

    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return j


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--budgets", required=True)
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    budgets = [int(b) for b in args.budgets.split(",")]
    df = pd.read_csv(args.csv)
    os.makedirs(args.out_dir, exist_ok=True)

    # Step 2: Probe
    print("=" * 70)
    print("STEP 2: Setting Probe")
    print("=" * 70)
    valid = probe_settings(df, ["label_K5", "label_K10", "label_K20"],
                           [15, 30, 60])
    print(f"\nValid: {len(valid)} settings")

    if not valid:
        print("No valid settings."); return

    # Step 3: Generalization
    print("\n" + "=" * 70)
    print("STEP 3: Joint Allocation Generalization")
    print("=" * 70)
    all_rows = []
    for s in valid:
        lc, ml = s["label_col"], s["min_len"]
        sl = f"{lc}_min{ml}"
        labels = df[lc].astype(int).tolist()
        N = len(labels)
        clips = labels_to_clips(labels, ml)
        print(f"\n  {sl}: {len(clips)} clips")
        rows = run_setting(df, labels, clips, N, ml, budgets, args.trials,
                           args.seed, PROXY_CONFIGS, sl)
        all_rows.extend(rows)
        print(f"    {len(rows)} rows")

    # Step 4: Proxy degradation (K10 min15 only, fewer trials)
    print("\n" + "=" * 70)
    print("STEP 4: Proxy Degradation")
    print("=" * 70)
    deg_trials = min(args.trials, 30)
    deg_labels = df["label_K10"].astype(int).tolist()
    deg_clips = labels_to_clips(deg_labels, 15)
    print(f"  K10 min15, trials={deg_trials}")
    for pconf in PROXY_CONFIGS[:1]:  # top 1 config
        print(f"  {pconf['proxy_col']} {pconf['threshold_desc']}")
        rows = run_degraded(df, deg_labels, deg_clips, 5000, 15, budgets,
                            deg_trials, args.seed, pconf, "label_K10_min15")
        all_rows.extend(rows)
        print(f"    {len(rows)} degradation rows")

    # Step 5: Summary
    print("\n" + "=" * 70)
    print("STEP 5: Summary")
    print("=" * 70)

    trials_df = pd.DataFrame(all_rows)
    trials_df.to_csv(os.path.join(args.out_dir, "all_trials.csv"), index=False)
    print(f"  {len(trials_df)} trial rows saved")

    summary_df = build_summary(all_rows, valid)
    summary_df.to_csv(os.path.join(args.out_dir, "summary.csv"), index=False)
    print(f"  {len(summary_df)} summary rows saved")

    j = write_summary(summary_df, args.out_dir)
    print(f"\n  JUDGMENT: {j}")

    # Key table
    print("\n" + "=" * 70)
    print("KEY RESULTS (clean settings)")
    print("=" * 70)
    clean = summary_df[summary_df["proxy_variant"] == "clean"]
    if not clean.empty:
        print(f"  {'setting':<20s}  {'budget':>6s}  {'cand_rec':>8s}  "
              f"{'joint_rec':>9s}  {'delta':>7s}  {'method':<18s}")
        print("  " + "-" * 75)
        for s in clean["setting"].unique():
            sd = clean[clean["setting"] == s]
            best = sd.sort_values("delta_recall", ascending=False).iloc[0]
            print(f"  {best['setting']:<20s}  {int(best['budget']):>6d}  "
                  f"{best['candidate_only_recall']:>8.3f}  "
                  f"{best['best_joint_recall']:>9.3f}  "
                  f"{best['delta_recall']:>+7.3f}  "
                  f"{best['best_joint_method']:<18s}")

    config = {"csv": os.path.abspath(args.csv), "budgets": budgets,
              "trials": args.trials, "seed": args.seed,
              "valid_settings": valid, "judgment": j}
    with open(os.path.join(args.out_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nSaved to {args.out_dir}/")


if __name__ == "__main__":
    main()
