#!/usr/bin/env python3
"""
build_arc_input_from_counts.py

Convert moving-camera per-frame CSV (proxy/oracle vehicle counts) into
ARC-compatible input files:
  - proxy CDF CSV  (columns: predicates, <constant>)
  - cluster CSV    (columns: label)
  - ground-truth clips CSV

Does NOT modify arc_source. Outputs to data_moving_arc/<dataset_name>/.

Usage:
    python scripts/build_arc_input_from_counts.py \
        --input outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv \
        --dataset realcar_5k \
        --K 14 \
        --tau 30 60 120 \
        --cdf-window 30
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert per-frame proxy/oracle counts to ARC input files."
    )
    parser.add_argument("--input", required=True,
                        help="Path to per-frame CSV with proxy_vehicle_count and oracle_vehicle_count")
    parser.add_argument("--dataset", required=True,
                        help="Dataset name (used as subdirectory under data_moving_arc/)")
    parser.add_argument("--K", type=int, required=True,
                        help="Threshold K: oracle_positive = (oracle_vehicle_count >= K)")
    parser.add_argument("--tau", type=int, nargs="+", default=[30, 60, 120],
                        help="Tau values for ground-truth clips (default: 30 60 120)")
    parser.add_argument("--cdf-window", type=int, default=30,
                        help="Sliding window size for proxy CDF estimation (default: 30)")
    parser.add_argument("--output-dir", default="data_moving_arc",
                        help="Root output directory (default: data_moving_arc)")
    parser.add_argument("--cluster-mode", default="temporal",
                        choices=["single", "temporal", "uniform"],
                        help="Cluster assignment mode (default: temporal)")
    parser.add_argument("--cluster-size", type=int, default=50,
                        help="Frames per cluster in temporal mode (default: 50)")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def load_and_validate(input_path: str) -> pd.DataFrame:
    """Load per-frame CSV and validate required columns."""
    df = pd.read_csv(input_path)
    required = ["proxy_vehicle_count", "oracle_vehicle_count"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"[ERROR] Missing required columns: {missing}")
        print(f"  Available columns: {list(df.columns)}")
        sys.exit(1)
    print(f"[INFO] Loaded {len(df)} frames from {input_path}")
    return df


def compute_oracle_predicate(df: pd.DataFrame, K: int) -> np.ndarray:
    """Return raw oracle_vehicle_count (NOT binary).

    ARC's generate_oracle_proxy applies (x > K) to the predicates column
    to derive oracle labels. We must pass raw counts, not pre-binarized labels.
    """
    raw = df["oracle_vehicle_count"].values.astype(float)
    oracle_positive = (raw >= K).astype(int)
    pos_rate = oracle_positive.mean()
    print(f"[INFO] K={K}: oracle positive rate = {pos_rate:.4f} "
          f"({oracle_positive.sum()}/{len(oracle_positive)})")
    if pos_rate < 0.001:
        print("[WARNING] Positive rate < 0.1%. ARC may have very few clips to find.")
    if pos_rate > 0.5:
        print("[WARNING] Positive rate > 50%. Consider a higher K.")
    return raw


def compute_proxy_cdf(df: pd.DataFrame, K: int, window: int) -> np.ndarray:
    """Compute proxy CDF = P(proxy_vehicle_count <= K) via sliding window.

    ARC's generate_oracle_proxy reads the CDF column as p_0 = P(proxy <= K),
    then builds proxy = [p_0, 1-p_0] and proxy_score = argmax(proxy).
    So proxy_score = 1 (positive) when p_0 < 0.5, i.e., when the proxy
    thinks the frame is likely above threshold.

    We compute:
      proxy_positive[i] = 1 if proxy_vehicle_count[i] >= K else 0
      P(proxy > K)[i] = sliding_window_mean(proxy_positive, window)
      CDF[i] = P(proxy <= K) = 1 - P(proxy > K)
    """
    proxy_pos = (df["proxy_vehicle_count"].values >= K).astype(int).astype(float)
    n = len(proxy_pos)
    half = window // 2

    # Cumulative sum trick for sliding window mean of proxy_positive
    cumsum = np.concatenate([[0], np.cumsum(proxy_pos)])
    p_pos = np.zeros(n)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        p_pos[i] = (cumsum[hi] - cumsum[lo]) / (hi - lo)

    # CDF = P(proxy <= K) = 1 - P(proxy > K)
    cdf = 1.0 - p_pos

    # Clamp to avoid 0/1 extremes (which would make proxy one-hot degenerate)
    eps = 0.001
    cdf = np.clip(cdf, eps, 1 - eps)

    proxy_positive_rate = (1 - cdf).mean()
    print(f"[INFO] Proxy CDF (window={window}): "
          f"mean={cdf.mean():.4f}, std={cdf.std():.4f}, "
          f"min={cdf.min():.4f}, max={cdf.max():.4f}")
    print(f"[INFO] Proxy positive rate (from CDF): {proxy_positive_rate:.4f}")
    return cdf


def generate_clusters(n: int, mode: str, cluster_size: int) -> np.ndarray:
    """Generate cluster labels for n frames.

    Modes:
      - 'single': all frames in one cluster (label=0)
      - 'temporal': consecutive blocks of cluster_size frames
      - 'uniform': each frame is its own cluster
    """
    if mode == "single":
        clusters = np.zeros(n, dtype=int)
        print(f"[INFO] Clusters: single cluster (all {n} frames)")
    elif mode == "temporal":
        clusters = np.arange(n) // cluster_size
        n_clusters = clusters[-1] + 1
        print(f"[INFO] Clusters: temporal (size={cluster_size}, "
              f"{n_clusters} clusters for {n} frames)")
    elif mode == "uniform":
        clusters = np.arange(n)
        print(f"[INFO] Clusters: uniform ({n} unique clusters)")
    else:
        raise ValueError(f"Unknown cluster mode: {mode}")
    return clusters


def find_ground_truth_clips(oracle_raw: np.ndarray, K: int, tau: int) -> np.ndarray:
    """Find clips: maximal runs of oracle_vehicle_count >= K with length >= tau.

    Returns (n_clips, 2) array of [start, end] inclusive indices.
    """
    oracle_binary = (oracle_raw >= K).astype(int)
    n = len(oracle_binary)
    clips = []
    start = None
    for i in range(n):
        if oracle_binary[i] == 1:
            if start is None:
                start = i
        else:
            if start is not None:
                length = i - start
                if length >= tau:
                    clips.append([start, i - 1])
                start = None
    # Handle clip at end
    if start is not None:
        length = n - start
        if length >= tau:
            clips.append([start, n - 1])

    clips_arr = np.array(clips) if clips else np.empty((0, 2), dtype=int)
    print(f"[INFO] Ground-truth clips (tau={tau}): {len(clips_arr)} clips found")
    return clips_arr


def write_cdf_csv(output_path: str, oracle_pred: np.ndarray,
                  proxy_cdf: np.ndarray, constant: int):
    """Write ARC-compatible CDF CSV.

    Format (matching generate_oracle_proxy in tools.py):
      - 'predicates' column: oracle predicate values (0 or 1)
      - '<constant>' column: proxy CDF probability values
    """
    df = pd.DataFrame({
        "predicates": oracle_pred,
        str(constant): proxy_cdf,
    })
    df.to_csv(output_path, index=False)
    print(f"[INFO] CDF CSV written: {output_path} ({len(df)} rows)")


def write_cluster_csv(output_path: str, clusters: np.ndarray):
    """Write ARC-compatible cluster CSV.

    Format (matching generate_cluster in tools.py):
      - 'label' column: integer cluster labels
    """
    df = pd.DataFrame({"label": clusters})
    df.to_csv(output_path, index=False)
    print(f"[INFO] Cluster CSV written: {output_path} ({len(df)} rows)")


def write_gt_clips_csv(output_path: str, clips: np.ndarray, tau: int):
    """Write ground-truth clips CSV for reference."""
    if len(clips) == 0:
        df = pd.DataFrame(columns=["clip_id", "start", "end", "length", "tau"])
    else:
        df = pd.DataFrame({
            "clip_id": np.arange(len(clips)),
            "start": clips[:, 0],
            "end": clips[:, 1],
            "length": clips[:, 1] - clips[:, 0] + 1,
            "tau": tau,
        })
    df.to_csv(output_path, index=False)
    print(f"[INFO] GT clips CSV written: {output_path} ({len(df)} clips)")


def write_metadata(output_path: str, args, df: pd.DataFrame,
                   oracle_raw: np.ndarray, proxy_cdf: np.ndarray,
                   clusters: np.ndarray):
    """Write a metadata JSON for reproducibility."""
    import json
    oracle_positive = (oracle_raw >= args.K).astype(int)
    meta = {
        "input_csv": str(Path(args.input).resolve()),
        "dataset": args.dataset,
        "K": args.K,
        "tau_values": args.tau,
        "cdf_window": args.cdf_window,
        "cluster_mode": args.cluster_mode,
        "cluster_size": args.cluster_size,
        "n_frames": len(df),
        "oracle_positive_count": int(oracle_positive.sum()),
        "oracle_positive_rate": float(oracle_positive.mean()),
        "proxy_cdf_mean": float(proxy_cdf.mean()),
        "proxy_cdf_std": float(proxy_cdf.std()),
        "n_clusters": int(len(np.unique(clusters))),
    }
    with open(output_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[INFO] Metadata written: {output_path}")


def main():
    args = parse_args()

    # Resolve paths
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        sys.exit(1)

    output_root = Path(args.output_dir) / args.dataset
    output_root.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Output directory: {output_root}")

    # Load data
    df = load_and_validate(str(input_path))
    n = len(df)

    # ARC uses strict '>' operator, so to get (vehicle_count >= K) we need
    # ARC constant = K - 1, giving (vehicle_count > K-1) = (vehicle_count >= K).
    arc_constant = args.K - 1

    # Compute oracle raw counts (ARC will apply x > constant to get labels)
    oracle_raw = compute_oracle_predicate(df, args.K)

    # Compute proxy CDF = P(proxy_vehicle_count <= K-1) = 1 - P(proxy_vehicle_count >= K)
    proxy_cdf = compute_proxy_cdf(df, args.K, args.cdf_window)

    # Generate clusters
    clusters = generate_clusters(n, args.cluster_mode, args.cluster_size)

    # Write CDF CSV (the main ARC input)
    # Column named by arc_constant (K-1) so ARC's generate_oracle_proxy works
    cdf_path = output_root / f"{args.dataset}_K{args.K}.csv"
    write_cdf_csv(str(cdf_path), oracle_raw, proxy_cdf, arc_constant)

    # Write cluster CSV
    cluster_threshold = "0.001"  # default from ARC config
    cluster_dir = output_root / "cluster"
    cluster_dir.mkdir(exist_ok=True)
    cluster_path = cluster_dir / f"{args.dataset}-{cluster_threshold}.csv"
    write_cluster_csv(str(cluster_path), clusters)

    # Write ground-truth clips for each tau
    gt_dir = output_root / "ground_truth"
    gt_dir.mkdir(exist_ok=True)
    for tau in args.tau:
        clips = find_ground_truth_clips(oracle_raw, args.K, tau)
        gt_path = gt_dir / f"gt_clips_tau{tau}.csv"
        write_gt_clips_csv(str(gt_path), clips, tau)

    # Write metadata
    meta_path = output_root / "metadata.json"
    write_metadata(str(meta_path), args, df, oracle_raw, proxy_cdf, clusters)

    # Summary
    oracle_positive = (oracle_raw >= args.K).astype(int)
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Dataset: {args.dataset}")
    print(f"  Frames: {n}")
    print(f"  K (user threshold): {args.K}  →  ARC constant: {arc_constant}")
    print(f"  Oracle positive rate (count >= {args.K}): {oracle_positive.mean():.4f}")
    print(f"  Proxy CDF mean: {proxy_cdf.mean():.4f} (= P(proxy <= {arc_constant}))")
    print(f"  Clusters: {len(np.unique(clusters))}")
    print(f"  Output: {output_root}")
    print()
    print("Generated files:")
    for p in sorted(output_root.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(output_root)}")

    # ARC compatibility check
    print("\n" + "=" * 60)
    print("ARC COMPATIBILITY CHECK")
    print("=" * 60)
    print(f"  CDF CSV: {cdf_path}")
    print(f"    - 'predicates' column: {('predicates' in pd.read_csv(str(cdf_path)).columns)}")
    print(f"    - '{arc_constant}' column: {(str(arc_constant) in pd.read_csv(str(cdf_path)).columns)}")
    print(f"  Cluster CSV: {cluster_path}")
    print(f"    - 'label' column: {('label' in pd.read_csv(str(cluster_path)).columns)}")
    print()
    print("To load in ARC:")
    print(f"  oracle, proxy, oracle_score, proxy_score = generate_oracle_proxy(")
    print(f"      '{cdf_path}', '>', {arc_constant})")
    print(f"  clusters = generate_cluster('{cluster_path}')")
    print()
    print("NOTE: ARC uses strict '>' operator. To get (vehicle_count >= K),")
    print(f"  we store constant = K-1 = {arc_constant}. ARC computes (count > {arc_constant}) = (count >= {args.K}).")
    print()
    print("NOTE: ARC's generate_oracle_proxy reads from arc_source/data/CDF/ by default.")
    print("You may need to either:")
    print(f"  1. Copy {cdf_path} to arc_source/data/CDF/{args.dataset}.csv")
    print(f"  2. Or modify DATA_DIRS['cdf'] in experiment_config.py to point to {output_root}")


if __name__ == "__main__":
    main()
