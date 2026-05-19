"""Run proxy score rule ablations for count_at_least frame predicates."""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

import pandas as pd

from garc_eval.datasets.build_frame_table import build_frame_table


def _diagnose(source_csv: pathlib.Path) -> dict:
    df = pd.read_csv(source_csv)
    return {
        "n": int(len(df)),
        "label_mean": float(df["label"].mean()),
        "label_counts": df["label"].value_counts(dropna=False).to_dict(),
        "proxy_score_min": float(df["proxy_score"].min()),
        "proxy_score_max": float(df["proxy_score"].max()),
        "proxy_unique_count": int(df["proxy_score"].nunique()),
        "proxy_saturated_count": int((df["proxy_score"] == 1.0).sum()),
    }


def _run_supg(source_csv: pathlib.Path, outdir: pathlib.Path, budget: int, gamma: float, delta: float, trials: int) -> None:
    cmd = [
        sys.executable,
        "-m",
        "garc_eval.experiments.run_supg_real_frames",
        "--source-csv",
        str(source_csv),
        "--budget",
        str(budget),
        "--gamma",
        str(gamma),
        "--delta",
        str(delta),
        "--trials",
        str(trials),
        "--outdir",
        str(outdir),
    ]
    subprocess.run(cmd, check=True)


def _summary_value(summary: pd.DataFrame, method: str, column: str):
    rows = summary[summary["method"] == method]
    if rows.empty or column not in rows.columns:
        return None
    value = rows.iloc[0][column]
    return None if pd.isna(value) else value


def run_ablation(args: argparse.Namespace) -> pd.DataFrame:
    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []

    for rule in args.rules:
        rule_dir = outdir / rule
        rule_dir.mkdir(parents=True, exist_ok=True)
        frames_path = rule_dir / "frames.parquet"
        source_csv = rule_dir / "supg_source.csv"

        build_frame_table(
            frame_metadata_path=args.frame_metadata,
            proxy_scores_path=args.proxy_scores,
            oracle_scores_path=args.oracle_scores,
            oracle_threshold=0.5,
            predicate="count_at_least",
            count_threshold=args.selected_k,
            proxy_score_rule=rule,
            output_frames_path=str(frames_path),
            output_source_csv=str(source_csv),
        )
        diag = _diagnose(source_csv)
        (rule_dir / "diagnostics.json").write_text(pd.Series(diag).to_json(indent=2), encoding="utf-8")

        supg_out = rule_dir / "supg_results"
        _run_supg(source_csv, supg_out, args.budget, args.gamma, args.delta, args.trials)
        summary = pd.read_csv(supg_out / "summary.csv")

        rt_selected = _summary_value(summary, "SUPG-RT", "mean_selected_n")
        row = {
            "rule": rule,
            "n": diag["n"],
            "label_mean": diag["label_mean"],
            "proxy_unique_count": diag["proxy_unique_count"],
            "proxy_saturated_count": diag["proxy_saturated_count"],
            "rt_supg_failure_rate": _summary_value(summary, "SUPG-RT", "failure_rate"),
            "rt_supg_mean_precision": _summary_value(summary, "SUPG-RT", "mean_precision"),
            "rt_supg_mean_recall": _summary_value(summary, "SUPG-RT", "mean_recall"),
            "rt_supg_mean_selected_n": rt_selected,
            "rt_supg_vacuous": bool(rt_selected is not None and rt_selected >= 0.95 * diag["n"]),
            "pt_supg_error_count": _summary_value(summary, "SUPG-PT", "error_count"),
            "pt_supg_mean_precision": _summary_value(summary, "SUPG-PT", "mean_precision"),
            "pt_supg_mean_recall": _summary_value(summary, "SUPG-PT", "mean_recall"),
            "u_noci_rt_failure_rate": _summary_value(summary, "U-NOCI-RT", "failure_rate"),
            "u_noci_rt_mean_precision": _summary_value(summary, "U-NOCI-RT", "mean_precision"),
        }
        rows.append(row)

    result = pd.DataFrame(rows)
    result.to_csv(outdir / "proxy_score_ablation_summary.csv", index=False)
    print(result.to_string(index=False))
    print(f"Saved {outdir / 'proxy_score_ablation_summary.csv'}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run proxy score ablations for count_at_least predicates")
    parser.add_argument("--frame-metadata", required=True)
    parser.add_argument("--proxy-scores", required=True)
    parser.add_argument("--oracle-scores", required=True)
    parser.add_argument("--selected-k", type=int, required=True)
    parser.add_argument("--rules", nargs="+", required=True)
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--gamma", type=float, required=True)
    parser.add_argument("--delta", type=float, required=True)
    parser.add_argument("--trials", type=int, required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    run_ablation(args)


if __name__ == "__main__":
    main()
