#!/usr/bin/env python3
from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from phase0_common import (
    DELTAS,
    GAMMAS,
    NUM_TRIALS,
    OUT_DIR,
    RANDOM_SEED,
    THETAS,
    append_progress,
    build_pseudo_events,
    ensure_dirs,
    event_recall,
    load_units,
    stitch_units,
)


def choose_threshold_from_sample(sample: pd.DataFrame, gamma: float) -> float:
    positives = sample[sample["oracle_label"].astype(bool)]
    if positives.empty:
        return float(sample["proxy_score"].quantile(0.90))
    ordered = positives.sort_values("proxy_score", ascending=False)
    need = max(1, int(math.ceil(gamma * len(ordered))))
    return float(ordered.iloc[need - 1]["proxy_score"])


def main() -> None:
    ensure_dirs()
    units = load_units()
    events = build_pseudo_events(units)
    rng = np.random.default_rng(RANDOM_SEED)
    rows = []
    sample_n = min(len(units), max(30, int(math.ceil(len(units) * 0.20))))
    all_score_source = ";".join(sorted(units["score_source"].astype(str).unique()))
    for gamma in GAMMAS:
        for delta in DELTAS:
            for theta in THETAS:
                for trial in range(NUM_TRIALS):
                    sample_idx = rng.choice(units.index.to_numpy(), size=sample_n, replace=False)
                    sample = units.loc[sample_idx].copy()
                    threshold = choose_threshold_from_sample(sample, gamma)
                    selected = units[units["proxy_score"] >= threshold].copy()
                    returned = stitch_units(selected, merge_gap=0.0)
                    window_recall = 0.0
                    positives = units["oracle_label"].astype(bool)
                    if positives.sum() > 0:
                        window_recall = float((selected["oracle_label"].astype(bool).sum()) / positives.sum())
                    clip_recall, hit_events, total_events = event_recall(events, returned, theta)
                    rows.append(
                        {
                            "trial": trial,
                            "gamma": gamma,
                            "delta": delta,
                            "theta": theta,
                            "sample_n": sample_n,
                            "threshold": threshold,
                            "selected_units": len(selected),
                            "selected_fraction": len(selected) / len(units),
                            "returned_clips": len(returned),
                            "window_recall": window_recall,
                            "clip_event_recall": clip_recall,
                            "hit_events": hit_events,
                            "total_events": total_events,
                            "guarantee_violation": clip_recall < gamma,
                            "score_source": all_score_source,
                            "event_boundary_type": "pseudo_from_adjacent_oracle_positive_units",
                            "oracle_relative": True,
                        }
                    )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "tables/supg_stitch_results.csv", index=False)

    summary = (
        out.groupby(["gamma", "delta", "theta", "score_source"], as_index=False)
        .agg(
            trials=("trial", "count"),
            GVR=("guarantee_violation", "mean"),
            mean_window_recall=("window_recall", "mean"),
            mean_clip_event_recall=("clip_event_recall", "mean"),
            mean_selected_fraction=("selected_fraction", "mean"),
            total_events=("total_events", "max"),
        )
        .sort_values(["gamma", "delta", "theta"])
    )
    summary.to_csv(OUT_DIR / "tables/supg_stitch_summary.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = []
    values = []
    colors = []
    for _, row in summary.iterrows():
        labels.append(f"g={row['gamma']},d={row['delta']},t={row['theta']}")
        values.append(row["GVR"])
        colors.append("#b23a48" if row["GVR"] > row["delta"] else "#2f6f4e")
    ax.bar(range(len(values)), values, color=colors)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Guarantee violation rate")
    ax.set_title("SUPG/window selection stitched to pseudo-events")
    for idx, row in summary.reset_index(drop=True).iterrows():
        ax.axhline(row["delta"], color="#666666", linewidth=0.5, alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figures/supg_stitch_gvr.png", dpi=160)
    plt.close(fig)
    append_progress(
        "SUPG/window stitch",
        "python scripts/10_supg_stitch_simulation.py",
        f"wrote {len(out)} trials; max GVR={summary['GVR'].max():.3f}",
        next_action="run no-repair block audit",
    )


if __name__ == "__main__":
    main()
