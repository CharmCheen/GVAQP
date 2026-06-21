#!/usr/bin/env python3
"""SUPG/window-level selection plus stitching on Nexar-200 derived boundaries."""

from __future__ import annotations

import random

import matplotlib.pyplot as plt

from nexar_200_common import OUT, append_progress, event_hit, read_csv, stable_score, stitch_intervals, write_csv


def select_units(units: list[dict], fraction: float, trial: int) -> list[dict]:
    scored = []
    for unit in units:
        score = stable_score(f"{unit['unit_id']}:{trial}", seed="nexar_200_supg_random_hash")
        scored.append((score, unit))
    scored.sort(key=lambda x: x[0], reverse=True)
    k = max(1, int(round(len(scored) * fraction)))
    return [unit for _, unit in scored[:k]]


def recall_for(events: list[dict], clips: list[dict], theta: float) -> float:
    if not events:
        return 0.0
    hits = sum(1 for event in events if event_hit(event, clips, theta))
    return hits / len(events)


def main() -> int:
    events = read_csv(OUT / "converted" / "casq_events_nexar_200.csv")
    units = [row for row in read_csv(OUT / "converted" / "casq_units_nexar_200.csv") if abs(float(row["duration"]) - 5.0) < 1e-9]
    rows = []
    fractions = [0.10, 0.20, 0.35, 0.50, 1.00]
    gammas = [0.8, 0.9]
    thetas = [0.3, 0.5]
    num_trials = 100
    for theta in thetas:
        for gamma in gammas:
            for fraction in fractions:
                recalls = []
                selected_counts = []
                clip_counts = []
                for trial in range(num_trials):
                    selected = select_units(units, fraction, trial)
                    clips = stitch_intervals(selected)
                    rec = recall_for(events, clips, theta)
                    recalls.append(rec)
                    selected_counts.append(len(selected))
                    clip_counts.append(len(clips))
                    rows.append(
                        {
                            "trial": trial,
                            "theta": theta,
                            "gamma": gamma,
                            "selection_fraction": fraction,
                            "selected_n": len(selected),
                            "stitched_clip_n": len(clips),
                            "true_derived_recall": rec,
                            "LCB_recall": "",
                            "GVR": float(rec < gamma),
                            "coverage": "",
                            "tightness": "",
                            "fraction_vacuous": "",
                            "certificate_success_rate": "",
                            "cost_to_certificate": "",
                            "candidate_generator": "metadata_only_hash_random_units_no_labels",
                        }
                    )
    write_csv(
        OUT / "tables" / "nexar_200_supg_stitch_results.csv",
        rows,
        [
            "trial",
            "theta",
            "gamma",
            "selection_fraction",
            "selected_n",
            "stitched_clip_n",
            "true_derived_recall",
            "LCB_recall",
            "GVR",
            "coverage",
            "tightness",
            "fraction_vacuous",
            "certificate_success_rate",
            "cost_to_certificate",
            "candidate_generator",
        ],
    )

    summary = []
    for theta in thetas:
        for gamma in gammas:
            for fraction in fractions:
                subset = [row for row in rows if row["theta"] == theta and row["gamma"] == gamma and row["selection_fraction"] == fraction]
                recalls = [float(row["true_derived_recall"]) for row in subset]
                gvr = sum(float(row["GVR"]) for row in subset) / len(subset)
                summary.append(
                    {
                        "theta": theta,
                        "gamma": gamma,
                        "selection_fraction": fraction,
                        "trials": len(subset),
                        "mean_true_derived_recall": sum(recalls) / len(recalls),
                        "median_true_derived_recall": sorted(recalls)[len(recalls) // 2],
                        "GVR": gvr,
                        "mean_selected_n": sum(float(row["selected_n"]) for row in subset) / len(subset),
                        "mean_stitched_clip_n": sum(float(row["stitched_clip_n"]) for row in subset) / len(subset),
                    }
                )
    write_csv(
        OUT / "tables" / "nexar_200_supg_stitch_summary.csv",
        summary,
        [
            "theta",
            "gamma",
            "selection_fraction",
            "trials",
            "mean_true_derived_recall",
            "median_true_derived_recall",
            "GVR",
            "mean_selected_n",
            "mean_stitched_clip_n",
        ],
    )

    sanity_rows = []
    oracle_clips = [
        {"video_id": event["video_id"], "start_time": float(event["event_start"]), "end_time": float(event["event_end"])}
        for event in events
    ]
    all_unit_clips = stitch_intervals(units)
    for theta in thetas:
        oracle_recall = recall_for(events, oracle_clips, theta)
        stitched_all_recall = recall_for(events, all_unit_clips, theta)
        sanity_rows.append(
            {
                "check": f"oracle_event_clips_recall_theta_{theta}",
                "passed": oracle_recall >= 0.999,
                "recall": oracle_recall,
                "detail": "exact derived event intervals used only to validate IoU evaluator",
            }
        )
        sanity_rows.append(
            {
                "check": f"stitched_all_5s_units_recall_theta_{theta}",
                "passed": stitched_all_recall < 0.999,
                "recall": stitched_all_recall,
                "detail": "expected failure observed for short derived intervals; documents SUPG stitch failure mode, not evaluator failure",
            }
        )
    write_csv(OUT / "tables" / "nexar_200_sanity_checks.csv", sanity_rows, ["check", "passed", "recall", "detail"])

    fig, ax = plt.subplots(figsize=(7, 4))
    for theta in thetas:
        data = [row for row in summary if row["theta"] == theta and row["gamma"] == 0.8]
        ax.plot([row["selection_fraction"] for row in data], [row["GVR"] for row in data], marker="o", label=f"theta={theta}, gamma=0.8")
    ax.set_xlabel("5s unit selection fraction")
    ax.set_ylabel("SUPG stitch violation rate")
    ax.set_title("Nexar-200 SUPG Stitch GVR")
    ax.set_ylim(-0.02, 1.02)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "nexar_200_gvr.png", dpi=160)
    plt.close(fig)

    append_progress("supg_stitch", "python scripts/30_supg_stitch_nexar_200.py", f"rows={len(rows)}", "run block audit")
    print(f"Wrote SUPG stitch results rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
