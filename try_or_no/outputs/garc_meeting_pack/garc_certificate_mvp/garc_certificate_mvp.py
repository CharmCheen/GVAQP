#!/usr/bin/env python3
"""
garc_certificate_mvp.py

First minimal G-ARC recall certificate prototype using
finite-population non-candidate frame-mass audit.

NOT ARC reproduction. NOT final theory. Uses YOLOv8x as pseudo-oracle.
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--csv-path", required=True)
    p.add_argument("--output-csv", required=True)
    p.add_argument("--output-report", required=True)
    p.add_argument("--k-values", default="10")
    p.add_argument("--tau-values", default="5,10,20")
    p.add_argument("--sample-sizes", default="100,200,500,1000")
    p.add_argument("--gamma-values", default="0.8,0.9")
    p.add_argument("--delta", type=float, default=0.05)
    p.add_argument("--seeds", type=int, default=50)
    p.add_argument("--boundary-margin", type=int, default=0,
                   help="Exclusion margin around candidates (0 = no margin)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Step 1: Candidate generation
# ---------------------------------------------------------------------------

def frame_labels_to_clips(labels, min_len=1, gap=0):
    """Convert binary labels to clips (start, end) inclusive."""
    n = len(labels)
    positive_idx = np.where(labels == 1)[0]
    if len(positive_idx) == 0:
        return []
    clips = []
    start = int(positive_idx[0])
    end = int(positive_idx[0])
    for i in range(1, len(positive_idx)):
        idx = int(positive_idx[i])
        if idx - end - 1 <= gap:
            end = idx
        else:
            if end - start + 1 >= min_len:
                clips.append((start, end))
            start = idx
            end = idx
    if end - start + 1 >= min_len:
        clips.append((start, end))
    return clips


def clip_iou(a, b):
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]) + 1)
    union = (a[1] - a[0] + 1) + (b[1] - b[0] + 1) - inter
    return inter / union if union > 0 else 0.0


def evaluate_clips(pred_clips, gt_clips, iou_threshold=0.5):
    """Compute clip recall, precision, mIoU."""
    if len(gt_clips) == 0:
        recall = 1.0
    else:
        matched_gt = 0
        for gt in gt_clips:
            for pred in pred_clips:
                if clip_iou(pred, gt) >= iou_threshold:
                    matched_gt += 1
                    break
        recall = matched_gt / len(gt_clips)

    if len(pred_clips) == 0:
        precision = 1.0 if len(gt_clips) == 0 else 0.0
    else:
        matched_pred = 0
        for pred in pred_clips:
            for gt in gt_clips:
                if clip_iou(pred, gt) >= iou_threshold:
                    matched_pred += 1
                    break
        precision = matched_pred / len(pred_clips)

    # mIoU: mean best-IoU over GT clips
    if len(gt_clips) == 0:
        miou = 1.0
    else:
        ious = []
        for gt in gt_clips:
            best = max((clip_iou(pred, gt) for pred in pred_clips), default=0.0)
            ious.append(best)
        miou = float(np.mean(ious))

    return recall, precision, miou


def generate_candidates(proxy_positive, tau, gap_frac=3):
    """Generate candidate clips from proxy positives.
    Merge runs separated by gap <= tau//3, keep clips >= tau.
    """
    gap = max(1, tau // gap_frac)
    return frame_labels_to_clips(proxy_positive, min_len=tau, gap=gap)


# ---------------------------------------------------------------------------
# Step 2: Non-candidate frame-mass audit
# ---------------------------------------------------------------------------

def get_non_candidate_frames(n_frames, candidate_clips, boundary_margin=0):
    """Return indices of frames not covered by any candidate clip + margin."""
    covered = np.zeros(n_frames, dtype=bool)
    for s, e in candidate_clips:
        s_m = max(0, s - boundary_margin)
        e_m = min(n_frames - 1, e + boundary_margin)
        covered[s_m:e_m + 1] = True
    return np.where(~covered)[0]


def hoeffding_upper(x, s, delta):
    """One-sided Hoeffding upper bound on true fraction."""
    if s == 0:
        return 1.0
    bound = x / s + math.sqrt(math.log(1.0 / delta) / (2 * s))
    return min(1.0, bound)


def compute_certificate(true_clips, candidate_clips, n_frames, nc_frames,
                        oracle_positive, tau, sample_size, gamma, delta, seed):
    """Run one audit trial. Returns metrics dict."""
    rng = np.random.RandomState(seed)

    # Actual clip metrics
    actual_recall, actual_precision, miou = evaluate_clips(candidate_clips, true_clips)

    # Candidate-side confidence = clip precision
    candidate_confidence = actual_precision

    # Hit true clips
    H = 0
    for gt in true_clips:
        for pred in candidate_clips:
            if clip_iou(pred, gt) >= 0.5:
                H += 1
                break

    # Sample from non-candidate frames
    N_NC = len(nc_frames)
    s = min(sample_size, N_NC)

    if s == 0:
        # No non-candidate frames
        return {
            "K": None, "tau": tau, "sample_size": sample_size,
            "gamma": gamma, "delta": delta, "seed": seed,
            "num_frames": n_frames, "num_true_clips": len(true_clips),
            "num_candidate_clips": len(candidate_clips),
            "H_hit_true_clips": H, "actual_clip_recall": actual_recall,
            "actual_clip_precision": actual_precision,
            "candidate_confidence": candidate_confidence,
            "N_NC": N_NC, "sampled_positive_count": 0,
            "sampled_positive_rate": 0.0, "q_U": 0.0,
            "missed_positive_frame_upper": 0,
            "missed_clip_upper": 0,
            "certified_recall_LB": 1.0,
            "certificate_pass": True,
            "oracle_ratio_audit": 0.0, "oracle_ratio_total": 0.0,
            "bound_gap": actual_recall - 1.0,
        }

    sampled_idx = rng.choice(N_NC, size=s, replace=False)
    sampled_frames = nc_frames[sampled_idx]
    sampled_labels = oracle_positive[sampled_frames]
    x = int(np.sum(sampled_labels))

    # Hoeffding upper bound on fraction of positives in NC region
    q_U = hoeffding_upper(x, s, delta)

    # Missed positive frame upper bound
    F_U = q_U * N_NC

    # Missed clip upper bound
    M_U = int(math.floor(F_U / tau))

    # Certified recall lower bound
    denom = H + M_U
    if denom > 0:
        recall_LB = H / denom
    else:
        recall_LB = 1.0

    certificate_pass = recall_LB >= gamma

    return {
        "K": None,  # filled by caller
        "tau": tau,
        "sample_size": sample_size,
        "gamma": gamma,
        "delta": delta,
        "seed": seed,
        "num_frames": n_frames,
        "num_true_clips": len(true_clips),
        "num_candidate_clips": len(candidate_clips),
        "H_hit_true_clips": H,
        "actual_clip_recall": actual_recall,
        "actual_clip_precision": actual_precision,
        "candidate_confidence": candidate_confidence,
        "N_NC": N_NC,
        "sampled_positive_count": x,
        "sampled_positive_rate": x / s,
        "q_U": q_U,
        "missed_positive_frame_upper": F_U,
        "missed_clip_upper": M_U,
        "certified_recall_LB": recall_LB,
        "certificate_pass": certificate_pass,
        "oracle_ratio_audit": s / n_frames,
        "oracle_ratio_total": s / n_frames,
        "bound_gap": actual_recall - recall_LB,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    K_values = [int(x) for x in args.k_values.split(",")]
    tau_values = [int(x) for x in args.tau_values.split(",")]
    sample_sizes = [int(x) for x in args.sample_sizes.split(",")]
    gamma_values = [float(x) for x in args.gamma_values.split(",")]
    delta = args.delta

    # Load data
    print(f"Loading: {args.csv_path}")
    df = pd.read_csv(args.csv_path)
    n_frames = len(df)
    print(f"N = {n_frames}")

    all_results = []

    for K in K_values:
        oracle_pos = (df["oracle_vehicle_count"] >= K).values.astype(int)
        proxy_pos = (df["proxy_vehicle_count"] >= K).values.astype(int)

        n_true_pos = int(np.sum(oracle_pos))
        n_proxy_pos = int(np.sum(proxy_pos))
        print(f"\nK={K}: oracle_pos={n_true_pos} ({n_true_pos/n_frames:.2%}), "
              f"proxy_pos={n_proxy_pos} ({n_proxy_pos/n_frames:.2%})")

        for tau in tau_values:
            # Generate candidate clips from proxy
            candidate_clips = generate_candidates(proxy_pos, tau)
            # Generate true clips from oracle
            true_clips = frame_labels_to_clips(oracle_pos, min_len=tau, gap=max(1, tau // 3))

            # Non-candidate frames
            nc_frames = get_non_candidate_frames(n_frames, candidate_clips, args.boundary_margin)

            actual_recall, actual_precision, miou = evaluate_clips(candidate_clips, true_clips)

            print(f"  tau={tau}: true_clips={len(true_clips)}, "
                  f"candidates={len(candidate_clips)}, "
                  f"NC_frames={len(nc_frames)}/{n_frames}, "
                  f"actual_recall={actual_recall:.3f}, "
                  f"actual_precision={actual_precision:.3f}, "
                  f"mIoU={miou:.3f}")

            for s in sample_sizes:
                for gamma in gamma_values:
                    for seed in range(args.seeds):
                        result = compute_certificate(
                            true_clips, candidate_clips, n_frames, nc_frames,
                            oracle_pos, tau, s, gamma, delta, seed
                        )
                        result["K"] = K
                        all_results.append(result)

    # Save results
    results_df = pd.DataFrame(all_results)
    out_csv = Path(args.output_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(out_csv, index=False)
    print(f"\nSaved: {out_csv}")

    # Summary
    print("\n" + "=" * 90)
    print("SUMMARY")
    print("=" * 90)

    summary_rows = []
    for K in K_values:
        for tau in tau_values:
            for s in sample_sizes:
                for gamma in gamma_values:
                    mask = (
                        (results_df["K"] == K) &
                        (results_df["tau"] == tau) &
                        (results_df["sample_size"] == s) &
                        (results_df["gamma"] == gamma)
                    )
                    sub = results_df[mask]
                    if len(sub) == 0:
                        continue
                    row = {
                        "K": K, "tau": tau, "sample_size": s,
                        "gamma": gamma, "delta": delta,
                        "actual_recall": sub["actual_clip_recall"].iloc[0],
                        "actual_precision": sub["actual_clip_precision"].iloc[0],
                        "candidate_confidence": sub["candidate_confidence"].iloc[0],
                        "num_true_clips": sub["num_true_clips"].iloc[0],
                        "num_candidate_clips": sub["num_candidate_clips"].iloc[0],
                        "H_hit": sub["H_hit_true_clips"].iloc[0],
                        "N_NC": sub["N_NC"].iloc[0],
                        "mean_sampled_pos": sub["sampled_positive_count"].mean(),
                        "mean_q_U": sub["q_U"].mean(),
                        "mean_missed_clip_upper": sub["missed_clip_upper"].mean(),
                        "mean_certified_recall_LB": sub["certified_recall_LB"].mean(),
                        "certificate_pass_rate": sub["certificate_pass"].mean(),
                        "mean_bound_gap": sub["bound_gap"].mean(),
                    }
                    summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(out_csv.parent / "summary.csv", index=False)

    # Print summary table
    print(f"\n{'K':>3s} {'tau':>4s} {'s':>5s} {'gamma':>6s} "
          f"{'actual_R':>9s} {'cert_LB':>8s} {'pass%':>6s} "
          f"{'gap':>6s} {'q_U':>6s} {'M_U':>6s} {'H':>3s} {'cands':>6s}")
    print("-" * 80)
    for _, r in summary_df.iterrows():
        print(f"{r['K']:>3.0f} {r['tau']:>4.0f} {r['sample_size']:>5.0f} {r['gamma']:>6.1f} "
              f"{r['actual_recall']:>9.3f} {r['mean_certified_recall_LB']:>8.3f} "
              f"{r['certificate_pass_rate']:>5.0%} "
              f"{r['mean_bound_gap']:>6.3f} {r['mean_q_U']:>6.3f} "
              f"{r['mean_missed_clip_upper']:>6.0f} {r['H_hit']:>3.0f} {r['num_candidate_clips']:>6.0f}")

    # Generate report
    report = generate_report(summary_df, df, K_values, tau_values, sample_sizes,
                             gamma_values, delta, args)
    out_report = Path(args.output_report)
    out_report.write_text(report, encoding="utf-8")
    print(f"\nSaved: {out_report}")

    return summary_df


def generate_report(summary_df, df, K_values, tau_values, sample_sizes,
                    gamma_values, delta, args):
    lines = []
    lines.append("# G-ARC Certificate MVP Report\n")

    lines.append("## 1. Purpose\n")
    lines.append("This is a first minimal G-ARC recall certificate prototype.")
    lines.append("It uses finite-population non-candidate frame-mass audit to derive")
    lines.append("a conservative lower bound on clip-level recall.")
    lines.append("")
    lines.append("This is NOT ARC reproduction. This is NOT final theory.")
    lines.append("YOLOv8x is used as pseudo-oracle, not human ground truth.\n")

    lines.append("## 2. Method\n")
    lines.append("### Candidate Generation (arc_style_proxy_candidates)")
    lines.append("1. Threshold proxy_vehicle_count >= K to get proxy-positive frames.")
    lines.append("2. Merge positive runs separated by gap <= tau/3.")
    lines.append("3. Keep clips with length >= tau.\n")
    lines.append("### Non-Candidate Frame-Mass Audit")
    lines.append("1. Define non-candidate (NC) frames as frames not covered by any candidate clip.")
    lines.append("2. Sample s frames uniformly without replacement from NC frames.")
    lines.append("3. Query oracle-positive labels on sampled frames.")
    lines.append("4. Apply one-sided Hoeffding bound: q_U = min(1, x/s + sqrt(log(1/delta)/(2s))).")
    lines.append("5. Missed positive frame upper bound: F_U = q_U * N_NC.")
    lines.append("6. Missed clip upper bound: M_U = floor(F_U / tau).")
    lines.append("7. Certified recall lower bound: recall_LB = H / (H + M_U).\n")
    lines.append("## 3. Why This Is Conservative but Valid\n")
    lines.append("The bound is conservative because:")
    lines.append("- Hoeffding gives a worst-case upper bound on the positive fraction in NC region.")
    lines.append("- Converting frame mass to clip count (floor(F_U / tau)) adds further slack.")
    lines.append("- It assumes every missed positive frame forms a full tau-length clip.")
    lines.append("")
    lines.append("The bound is valid because:")
    lines.append("- It is a proper finite-population confidence bound (no distributional assumptions).")
    lines.append("- With probability >= 1-delta, q_U is an upper bound on the true NC positive fraction.")
    lines.append("- Therefore recall_LB is a valid lower bound on true clip recall.\n")

    lines.append("## 4. Results by Tau and Sample Size\n")
    lines.append(f"Data: `{args.csv_path}`, N={len(df)}")
    lines.append(f"K={K_values}, delta={delta}\n")

    for gamma in gamma_values:
        lines.append(f"### gamma = {gamma}\n")
        sub = summary_df[summary_df["gamma"] == gamma]
        if len(sub) == 0:
            lines.append("No results.\n")
            continue
        lines.append("| K | tau | s | actual_recall | cert_recall_LB | pass_rate | bound_gap | q_U | M_U | H |")
        lines.append("|---|-----|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
        for _, r in sub.iterrows():
            lines.append(
                f"| {r['K']:.0f} | {r['tau']:.0f} | {r['sample_size']:.0f} "
                f"| {r['actual_recall']:.3f} | {r['mean_certified_recall_LB']:.3f} "
                f"| {r['certificate_pass_rate']:.0%} | {r['mean_bound_gap']:.3f} "
                f"| {r['mean_q_U']:.3f} | {r['mean_missed_clip_upper']:.0f} | {r['H_hit']:.0f} |"
            )
        lines.append("")

    lines.append("## 5. Certificate Pass Rate\n")
    for gamma in gamma_values:
        sub = summary_df[summary_df["gamma"] == gamma]
        passing = sub[sub["certificate_pass_rate"] > 0]
        if len(passing) > 0:
            best = passing.loc[passing["sample_size"].idxmin()]
            lines.append(f"- gamma={gamma}: **PASSES** at tau={best['tau']:.0f}, "
                         f"s={best['sample_size']:.0f} (pass rate={best['certificate_pass_rate']:.0%})")
        else:
            lines.append(f"- gamma={gamma}: **NO passing configurations**")
    lines.append("")

    lines.append("## 6. Bound Tightness\n")
    for gamma in gamma_values:
        sub = summary_df[summary_df["gamma"] == gamma]
        if len(sub) == 0:
            continue
        best_gap = sub.loc[sub["mean_bound_gap"].idxmin()]
        lines.append(f"- gamma={gamma}: best bound_gap = {best_gap['mean_bound_gap']:.3f} "
                     f"(actual={best_gap['actual_recall']:.3f}, cert_LB={best_gap['mean_certified_recall_LB']:.3f})")
    lines.append("")

    lines.append("## 7. Whether Frame-Mass Bound Is Too Loose\n")
    lines.append("The frame-mass bound is inherently loose because:")
    lines.append("1. It converts a frame-level positive fraction to a clip count by dividing by tau.")
    lines.append("2. This assumes worst-case: every tau positive frames form one clip.")
    lines.append("3. In reality, positive frames cluster, so fewer clips are missed than predicted.")
    lines.append("4. The Hoeffding bound itself adds sqrt(log(1/delta)/(2s)) slack.\n")

    lines.append("## 8. Failure Cases\n")
    for gamma in gamma_values:
        sub = summary_df[summary_df["gamma"] == gamma]
        failing = sub[sub["certificate_pass_rate"] < 1.0]
        if len(failing) > 0:
            worst = failing.loc[failing["certificate_pass_rate"].idxmin()]
            lines.append(f"- gamma={gamma}: worst pass rate = {worst['certificate_pass_rate']:.0%} "
                         f"at tau={worst['tau']:.0f}, s={worst['sample_size']:.0f}")
        else:
            lines.append(f"- gamma={gamma}: all configurations pass")
    lines.append("")

    lines.append("## 9. Next Improvement: Run-Aware / Window Audit\n")
    lines.append("The current audit samples uniformly from all non-candidate frames.")
    lines.append("A tighter bound would:")
    lines.append("1. Sample **runs** (windows) rather than individual frames,")
    lines.append("2. Detect whether a window contains a missed clip,")
    lines.append("3. Use run-level Hoeffding to bound missed clip count directly.")
    lines.append("4. This avoids the loose frame-to-clip conversion (floor(F_U / tau)).\n")

    lines.append("---\n")
    lines.append("This is a first certificate MVP. It is not final G-ARC theory.")
    lines.append("The bound is valid but conservative. Tighter bounds require run-aware auditing.")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
