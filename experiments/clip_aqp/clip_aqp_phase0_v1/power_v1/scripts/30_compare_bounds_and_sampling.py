#!/usr/bin/env python3
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from power_common import POWER_DIR, append_progress, ensure_dirs


def plot_metric(summary: pd.DataFrame, metric: str, ylabel: str, path_name: str) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for mode, group in summary.groupby("mode", sort=False):
        ordered = group.sort_values("target_event_count")
        ax.plot(ordered["target_event_count"], ordered[metric], marker="o", label=mode)
    ax.set_xscale("log")
    ax.set_xlabel("Target pseudo-event count")
    ax.set_ylabel(ylabel)
    ax.set_title(ylabel + " vs pseudo-event count")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(POWER_DIR / f"figures/{path_name}", dpi=160)
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    results = pd.read_csv(POWER_DIR / "tables/power_scaling_results.csv")
    summary = (
        results.groupby(["mode", "target_event_count"], as_index=False)
        .agg(
            trials=("trial", "count"),
            actual_event_count_mean=("actual_event_count", "mean"),
            population_blocks_mean=("population_blocks", "mean"),
            cost_to_certificate_mean=("cost_to_certificate", "mean"),
            true_recall_mean=("true_recall", "mean"),
            LCB_recall_mean=("LCB_recall", "mean"),
            LCB_recall_median=("LCB_recall", "median"),
            LCB_recall_p10=("LCB_recall", lambda x: x.quantile(0.10)),
            LCB_recall_p90=("LCB_recall", lambda x: x.quantile(0.90)),
            GVR=("GVR", "mean"),
            coverage=("coverage", "mean"),
            tightness_mean=("tightness", "mean"),
            certificate_success_rate=("certificate_success", "mean"),
            fraction_vacuous=("fraction_vacuous_indicator", "mean"),
        )
        .sort_values(["mode", "target_event_count"])
    )
    summary.to_csv(POWER_DIR / "tables/power_scaling_summary.csv", index=False)

    certified = summary[summary["mode"] == "certified_srs"][["target_event_count", "LCB_recall_median", "fraction_vacuous", "tightness_mean"]].rename(
        columns={
            "LCB_recall_median": "certified_lcb_median",
            "fraction_vacuous": "certified_fraction_vacuous",
            "tightness_mean": "certified_tightness",
        }
    )
    strat = summary[summary["mode"] == "stratified_by_video"][["target_event_count", "LCB_recall_median", "fraction_vacuous", "tightness_mean"]].rename(
        columns={
            "LCB_recall_median": "stratified_lcb_median",
            "fraction_vacuous": "stratified_fraction_vacuous",
            "tightness_mean": "stratified_tightness",
        }
    )
    boot = summary[summary["mode"] == "bootstrap_diagnostic"][["target_event_count", "LCB_recall_median", "fraction_vacuous", "tightness_mean"]].rename(
        columns={
            "LCB_recall_median": "bootstrap_lcb_median",
            "fraction_vacuous": "bootstrap_fraction_vacuous",
            "tightness_mean": "bootstrap_tightness",
        }
    )
    comparison = certified.merge(strat, on="target_event_count").merge(boot, on="target_event_count")
    comparison["stratified_minus_certified_lcb"] = comparison["stratified_lcb_median"] - comparison["certified_lcb_median"]
    comparison["bootstrap_minus_certified_lcb"] = comparison["bootstrap_lcb_median"] - comparison["certified_lcb_median"]
    comparison.to_csv(POWER_DIR / "tables/mode_comparison.csv", index=False)

    plot_metric(summary, "LCB_recall_median", "Median LCB recall", "lcb_recall_vs_event_count.png")
    plot_metric(summary, "fraction_vacuous", "Fraction vacuous", "fraction_vacuous_vs_event_count.png")
    plot_metric(summary, "certificate_success_rate", "Certificate success rate", "certificate_success_vs_event_count.png")
    plot_metric(summary, "GVR", "Coverage violation rate", "gvr_vs_event_count.png")
    append_progress(
        "compare bounds and sampling",
        "python scripts/30_compare_bounds_and_sampling.py",
        f"wrote summary for {len(summary)} mode/event-count rows and figures",
        next_action="generate power report",
    )


if __name__ == "__main__":
    main()
