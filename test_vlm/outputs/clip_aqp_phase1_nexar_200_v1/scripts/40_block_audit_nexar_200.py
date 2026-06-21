#!/usr/bin/env python3
"""No-repair block/event audit on Nexar-200 derived boundaries."""

from __future__ import annotations

import random

import matplotlib.pyplot as plt

from nexar_200_common import (
    OUT,
    append_progress,
    event_hit,
    finite_population_total_bounds,
    read_csv,
    stable_score,
    stitch_intervals,
    write_csv,
)


def select_candidate_clips(units: list[dict], fraction: float) -> list[dict]:
    scored = [(stable_score(unit["unit_id"], seed="nexar_200_block_candidate_hash"), unit) for unit in units]
    scored.sort(key=lambda x: x[0], reverse=True)
    k = max(1, int(round(len(scored) * fraction)))
    return stitch_intervals([unit for _, unit in scored[:k]])


def build_blocks(manifest: list[dict], events: list[dict], clips: list[dict], block_size: int, theta: float) -> list[dict]:
    event_by_video = {event["video_id"]: event for event in events}
    blocks = []
    for row in manifest:
        video_id = row["video_id"]
        event = event_by_video.get(video_id)
        duration = 30.0
        if event:
            duration = max(30.0, float(event["event_end"]) + 10.0)
        t = 0.0
        while t + block_size <= duration + 1e-9:
            end = t + block_size
            y = 0
            m = 0
            if event:
                midpoint = float(event["event_midpoint"])
                if t <= midpoint < end:
                    y = 1
                    hit = event_hit(event, clips, theta)
                    m = 0 if hit else 1
            blocks.append(
                {
                    "video_id": video_id,
                    "block_id": f"{video_id}_b{block_size}_{int(t):06d}_{int(end):06d}",
                    "start_time": t,
                    "end_time": end,
                    "block_size_seconds": block_size,
                    "Y_i": y,
                    "M_i": m,
                    "sample_split": "certification",
                    "used_for_design": False,
                    "used_for_repair": False,
                    "used_for_certificate": True,
                }
            )
            t = end
    return blocks


def true_recall(events: list[dict], clips: list[dict], theta: float) -> float:
    if not events:
        return 0.0
    hits = sum(1 for event in events if event_hit(event, clips, theta))
    return hits / len(events)


def run_audit(blocks: list[dict], events: list[dict], clips: list[dict], theta: float, gamma: float, delta: float, sample_fraction: float, trial: int) -> dict:
    rng = random.Random(20260621 + trial + int(theta * 1000) + int(gamma * 100) + int(delta * 1000) + int(sample_fraction * 10000))
    n = max(1, int(round(len(blocks) * sample_fraction)))
    sample = rng.sample(blocks, n)
    y_values = [float(row["Y_i"]) for row in sample]
    m_values = [float(row["M_i"]) for row in sample]
    lcb_y = finite_population_total_bounds(y_values, len(blocks), delta, lower=True)
    ucb_m = finite_population_total_bounds(m_values, len(blocks), delta, lower=False)
    point_y = len(blocks) * sum(y_values) / len(y_values)
    point_m = len(blocks) * sum(m_values) / len(m_values)
    if lcb_y <= 1e-12:
        lcb_recall = 0.0
        vacuous = True
    else:
        lcb_recall = max(0.0, 1.0 - ucb_m / lcb_y)
        vacuous = lcb_recall <= 1e-12
    recall = true_recall(events, clips, theta)
    return {
        "trial": trial,
        "theta": theta,
        "gamma": gamma,
        "delta": delta,
        "sample_fraction": sample_fraction,
        "sample_n": n,
        "population_blocks": len(blocks),
        "derived_event_count": len(events),
        "Y_hat": point_y,
        "M_hat": point_m,
        "LCB_Y": lcb_y,
        "UCB_M": ucb_m,
        "true_derived_recall": recall,
        "LCB_recall": lcb_recall,
        "GVR": float(lcb_recall >= gamma and recall < gamma),
        "coverage": float(lcb_recall <= recall + 1e-12),
        "tightness": recall - lcb_recall,
        "fraction_vacuous": float(vacuous),
        "certificate_success_rate": float(lcb_recall >= gamma),
        "cost_to_certificate": n,
        "candidate_selection_fraction": 0.35,
        "candidate_generator": "metadata_only_hash_top_35pct_5s_units_no_labels",
    }


def main() -> int:
    manifest = read_csv(OUT / "manifests" / "nexar_200_manifest.csv")
    events = read_csv(OUT / "converted" / "casq_events_nexar_200.csv")
    units_5s = [row for row in read_csv(OUT / "converted" / "casq_units_nexar_200.csv") if abs(float(row["duration"]) - 5.0) < 1e-9]
    clips = select_candidate_clips(units_5s, 0.35)
    rows = []
    block_sizes = [10, 15]
    thetas = [0.3, 0.5]
    gammas = [0.8, 0.9]
    deltas = [0.05, 0.10]
    sample_fractions = [0.10, 0.20, 0.35, 0.50]
    num_trials = 100
    for block_size in block_sizes:
        for theta in thetas:
            blocks = build_blocks(manifest, events, clips, block_size, theta)
            for gamma in gammas:
                for delta in deltas:
                    for sample_fraction in sample_fractions:
                        for trial in range(num_trials):
                            row = run_audit(blocks, events, clips, theta, gamma, delta, sample_fraction, trial)
                            row["block_size_seconds"] = block_size
                            rows.append(row)
    fields = [
        "trial",
        "theta",
        "gamma",
        "delta",
        "block_size_seconds",
        "sample_fraction",
        "sample_n",
        "population_blocks",
        "derived_event_count",
        "Y_hat",
        "M_hat",
        "LCB_Y",
        "UCB_M",
        "true_derived_recall",
        "LCB_recall",
        "GVR",
        "coverage",
        "tightness",
        "fraction_vacuous",
        "certificate_success_rate",
        "cost_to_certificate",
        "candidate_selection_fraction",
        "candidate_generator",
    ]
    write_csv(OUT / "tables" / "nexar_200_block_audit_results.csv", rows, fields)

    summary = []
    for block_size in block_sizes:
        for theta in thetas:
            for gamma in gammas:
                for delta in deltas:
                    for sample_fraction in sample_fractions:
                        subset = [
                            row
                            for row in rows
                            if row["block_size_seconds"] == block_size
                            and row["theta"] == theta
                            and row["gamma"] == gamma
                            and row["delta"] == delta
                            and row["sample_fraction"] == sample_fraction
                        ]
                        lcb = [float(row["LCB_recall"]) for row in subset]
                        summary.append(
                            {
                                "theta": theta,
                                "gamma": gamma,
                                "delta": delta,
                                "block_size_seconds": block_size,
                                "sample_fraction": sample_fraction,
                                "trials": len(subset),
                                "true_derived_recall": subset[0]["true_derived_recall"],
                                "LCB_recall_mean": sum(lcb) / len(lcb),
                                "LCB_recall_median": sorted(lcb)[len(lcb) // 2],
                                "LCB_recall_p10": sorted(lcb)[int(0.10 * (len(lcb) - 1))],
                                "LCB_recall_p90": sorted(lcb)[int(0.90 * (len(lcb) - 1))],
                                "GVR": sum(float(row["GVR"]) for row in subset) / len(subset),
                                "coverage": sum(float(row["coverage"]) for row in subset) / len(subset),
                                "tightness": sum(float(row["tightness"]) for row in subset) / len(subset),
                                "fraction_vacuous": sum(float(row["fraction_vacuous"]) for row in subset) / len(subset),
                                "certificate_success_rate": sum(float(row["certificate_success_rate"]) for row in subset) / len(subset),
                                "cost_to_certificate": sum(float(row["cost_to_certificate"]) for row in subset) / len(subset),
                            }
                        )
    write_csv(
        OUT / "tables" / "nexar_200_block_audit_summary.csv",
        summary,
        [
            "theta",
            "gamma",
            "delta",
            "block_size_seconds",
            "sample_fraction",
            "trials",
            "true_derived_recall",
            "LCB_recall_mean",
            "LCB_recall_median",
            "LCB_recall_p10",
            "LCB_recall_p90",
            "GVR",
            "coverage",
            "tightness",
            "fraction_vacuous",
            "certificate_success_rate",
            "cost_to_certificate",
        ],
    )

    fig, ax = plt.subplots(figsize=(7, 4))
    plot_rows = [row for row in summary if row["theta"] == 0.3 and row["gamma"] == 0.8 and row["delta"] == 0.1 and row["block_size_seconds"] == 10]
    ax.plot([row["sample_fraction"] for row in plot_rows], [row["LCB_recall_median"] for row in plot_rows], marker="o", label="median LCB")
    ax.axhline(float(plot_rows[0]["true_derived_recall"]), color="black", linestyle="--", label="true derived recall")
    ax.set_xlabel("certification sample fraction")
    ax.set_ylabel("recall")
    ax.set_title("Nexar-200 LCB vs True Derived Recall")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "nexar_200_lcb_vs_true_recall.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot([row["sample_fraction"] for row in plot_rows], [row["fraction_vacuous"] for row in plot_rows], marker="o")
    ax.set_xlabel("certification sample fraction")
    ax.set_ylabel("fraction vacuous")
    ax.set_title("Nexar-200 Fraction Vacuous")
    ax.set_ylim(-0.02, 1.02)
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "nexar_200_fraction_vacuous.png", dpi=160)
    plt.close(fig)

    append_progress("block_audit", "python scripts/40_block_audit_nexar_200.py", f"rows={len(rows)}", "generate report")
    print(f"Wrote block audit rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

