"""Run SUPG experiments on real frame-level data.

Reads a source CSV (id, label, proxy_score) and runs the same
U-NOCI / U-CI / SUPG pipeline as run_supg_synthetic.py.

Usage:
    python -m garc_eval.experiments.run_supg_real_frames --source-csv path/to/supg_source.csv --budget 10000 --gamma 0.9 --trials 100 --outdir path/to/output
"""

import argparse
import json
import pathlib

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from garc_eval.baselines.u_noci import u_noci_rt, u_noci_pt
from garc_eval.baselines.u_ci import u_ci_rt
from garc_eval.adapters.supg_adapter import run_supg_rt, run_supg_pt
from garc_eval.metrics.selection_metrics import evaluate_selection
from garc_eval.metrics.guarantee import summarize_trials

_SOURCE_CSV_REQUIRED = {"id", "label", "proxy_score"}


def _validate_source_csv(df: pd.DataFrame) -> None:
    """Validate source CSV schema before running experiments."""
    missing = _SOURCE_CSV_REQUIRED - set(df.columns)
    if missing:
        raise ValueError(
            f"source CSV missing required columns {missing}. "
            f"Got {list(df.columns)}. Expected: {sorted(_SOURCE_CSV_REQUIRED)}"
        )
    if df["id"].duplicated().any():
        dupes = df[df["id"].duplicated()]["id"].head(5).tolist()
        raise ValueError(f"source CSV has duplicate ids: {dupes}")
    if df["proxy_score"].isna().any():
        n = int(df["proxy_score"].isna().sum())
        raise ValueError(f"source CSV has {n} rows with NaN proxy_score")
    if not set(df["label"].dropna().unique()).issubset({0, 1, 0.0, 1.0}):
        raise ValueError(
            f"source CSV 'label' must be binary (0/1), "
            f"got unique values: {df['label'].dropna().unique()[:10]}"
        )


def run_method(
    method_name: str,
    df: pd.DataFrame,
    budget: int,
    gamma: float,
    delta: float,
    seed: int,
) -> dict:
    """Run a single method for a single seed."""
    try:
        labels = df["label"].values
        total_ids = df["id"].values

        if method_name == "U-NOCI-RT":
            result = u_noci_rt(df, budget, gamma, seed)
            qtype = "rt"
        elif method_name == "U-NOCI-PT":
            result = u_noci_pt(df, budget, gamma, seed)
            qtype = "pt"
        elif method_name == "U-CI-RT":
            result = u_ci_rt(df, budget, gamma, delta, seed)
            qtype = "rt"
        elif method_name == "SUPG-RT":
            result = run_supg_rt(df=df, budget=budget, gamma=gamma, delta=delta, seed=seed)
            qtype = "rt"
        elif method_name == "SUPG-PT":
            result = run_supg_pt(df=df, budget=budget, gamma=gamma, delta=delta, seed=seed)
            qtype = "pt"
        else:
            raise ValueError(f"Unknown method: {method_name}")

        selected_ids = result["selected_ids"]
        sampled_ids = result.get("sampled_ids")
        sampled_n = len(sampled_ids) if sampled_ids is not None else None
        metrics = evaluate_selection(labels, selected_ids, total_ids)
        return {
            "method": method_name,
            "qtype": qtype,
            "seed": seed,
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "selected_n": metrics["selected_n"],
            "sampled_n": sampled_n,
            "true_positive_n": metrics["true_positive_n"],
            "total_positive_n": metrics["total_positive_n"],
            "error": None,
        }
    except Exception as e:
        return {
            "method": method_name,
            "qtype": "rt" if "RT" in method_name else "pt",
            "seed": seed,
            "precision": None,
            "recall": None,
            "selected_n": None,
            "sampled_n": None,
            "true_positive_n": None,
            "total_positive_n": None,
            "error": f"{type(e).__name__}: {e}",
        }


def make_boxplot(results_df, metric_col, methods, target_line, title, ylabel, outpath):
    fig, ax = plt.subplots(figsize=(10, 6))
    data_for_plot, labels_for_plot = [], []
    for m in methods:
        vals = results_df[results_df["method"] == m][metric_col].dropna().values
        if len(vals) > 0:
            data_for_plot.append(vals)
            labels_for_plot.append(m)
    if not data_for_plot:
        plt.close(fig)
        return
    try:
        ax.boxplot(data_for_plot, tick_labels=labels_for_plot, patch_artist=True)
    except TypeError:
        ax.boxplot(data_for_plot, labels=labels_for_plot, patch_artist=True)
    ax.axhline(y=target_line, color="red", linestyle="--", linewidth=1.5, label=f"target = {target_line}")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.legend()
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    pathlib.Path(outpath).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=150)
    plt.close(fig)
    print(f"Saved plot: {outpath}")


def main():
    parser = argparse.ArgumentParser(description="Run SUPG on real frame-level data")
    parser.add_argument("--source-csv", required=True, help="Path to supg_source.csv (id,label,proxy_score)")
    parser.add_argument("--budget", type=int, default=10000)
    parser.add_argument("--gamma", type=float, default=0.9)
    parser.add_argument("--delta", type=float, default=0.05)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--outdir", type=str, required=True)
    args = parser.parse_args()

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    config = vars(args)
    with open(outdir / "config.json", "w") as f:
        json.dump(config, f, indent=2)
    print(f"Config: {config}")

    # Load data
    df = pd.read_csv(args.source_csv)
    _validate_source_csv(df)
    df["label"] = df["label"].astype("float32")
    print(f"Loaded {len(df)} rows from {args.source_csv}")
    print(f"  label rate: {df['label'].mean():.4f}")
    print(f"  proxy_score range: [{df['proxy_score'].min():.4f}, {df['proxy_score'].max():.4f}]")

    # Methods
    rt_methods = ["U-NOCI-RT", "U-CI-RT", "SUPG-RT"]
    pt_methods = ["U-NOCI-PT", "SUPG-PT"]
    all_methods = rt_methods + pt_methods

    # Run trials
    all_results = []
    for method_name in all_methods:
        print(f"\n=== Running {method_name} ({args.trials} seeds) ===")
        for seed in range(args.trials):
            row = run_method(method_name, df, args.budget, args.gamma, args.delta, seed)
            all_results.append(row)
            if row["error"]:
                print(f"  seed={seed}: ERROR — {row['error']}")
            elif (seed + 1) % max(1, args.trials // 5) == 0 or seed == 0:
                print(f"  seed={seed}: prec={row['precision']:.4f}  recall={row['recall']:.4f}  n={row['selected_n']}")

    results_df = pd.DataFrame(all_results)
    results_df.to_csv(outdir / "per_trial_results.csv", index=False)
    print(f"\nSaved per_trial_results.csv")

    # Summary
    summary_rows = []
    for method_name in all_methods:
        method_df = results_df[results_df["method"] == method_name]
        valid_df = method_df[method_df["error"].isna()]
        qtype = "rt" if "RT" in method_name else "pt"

        if len(valid_df) == 0:
            summary_rows.append({
                "method": method_name, "qtype": qtype, "trials": len(method_df),
                "gamma": args.gamma, "delta": args.delta, "budget": args.budget,
                "failure_rate": None, "mean_precision": None, "median_precision": None,
                "mean_recall": None, "median_recall": None,
                "mean_selected_n": None, "median_selected_n": None,
                "mean_sampled_n": None, "error_count": len(method_df),
            })
            continue

        s = summarize_trials(valid_df, qtype, args.gamma)
        s["method"] = method_name
        s["qtype"] = qtype
        s["trials"] = len(method_df)
        s["gamma"] = args.gamma
        s["delta"] = args.delta
        s["budget"] = args.budget
        s["median_selected_n"] = float(valid_df["selected_n"].median())
        s["mean_sampled_n"] = float(valid_df["sampled_n"].mean()) if valid_df["sampled_n"].notna().any() else None
        s["error_count"] = int(method_df["error"].notna().sum())
        summary_rows.append(s)

    col_order = ["method", "qtype", "trials", "gamma", "delta", "budget",
                 "failure_rate", "mean_precision", "median_precision",
                 "mean_recall", "median_recall",
                 "mean_selected_n", "median_selected_n", "mean_sampled_n", "error_count"]
    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df[[c for c in col_order if c in summary_df.columns]]
    summary_df.to_csv(outdir / "summary.csv", index=False)
    print(f"Saved summary.csv")
    print("\n" + summary_df.to_string(index=False))

    # Summary markdown
    md_lines = ["# Real Frames Experiment Summary\n"]
    md_lines.append(f"- source: {args.source_csv}")
    md_lines.append(f"- budget: {args.budget}, gamma: {args.gamma}, delta: {args.delta}")
    md_lines.append(f"- trials: {args.trials}\n")
    cols = summary_df.columns.tolist()
    md_lines.append("| " + " | ".join(cols) + " |")
    md_lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, row in summary_df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            if pd.isna(v):
                vals.append("-")
            elif isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        md_lines.append("| " + " | ".join(vals) + " |")
    md_lines.append(f"\nGenerated: {pd.Timestamp.now().isoformat()}")
    (outdir / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Saved summary.md")

    # Plots
    make_boxplot(
        results_df, "recall", rt_methods, args.gamma,
        f"Recall Distribution (RT, budget={args.budget}, gamma={args.gamma})",
        "Recall", str(outdir / "boxplot_rt_recall.png"),
    )
    make_boxplot(
        results_df, "precision", pt_methods, args.gamma,
        f"Precision Distribution (PT, budget={args.budget}, gamma={args.gamma})",
        "Precision", str(outdir / "boxplot_pt_precision.png"),
    )

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
