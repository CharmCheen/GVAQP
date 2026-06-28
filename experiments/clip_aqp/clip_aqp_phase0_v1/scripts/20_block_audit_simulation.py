#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from phase0_common import (
    BLOCK_SIZES,
    CERT_SAMPLE_FRAC,
    DELTAS,
    DIAG_SAMPLE_FRAC,
    GAMMAS,
    NUM_TRIALS,
    OUT_DIR,
    RANDOM_SEED,
    RETURNED_CLIP_BUDGET_FRAC,
    THETAS,
    append_progress,
    build_pseudo_events,
    conservative_certificate,
    ensure_dirs,
    event_recall,
    fixed_returned_clips,
    load_units,
    partition_blocks,
    sample_blocks,
)


def add_provenance(df: pd.DataFrame, split: str, design: bool, repair: bool) -> pd.DataFrame:
    out = df.copy()
    out["sample_split"] = split
    out["used_for_design"] = bool(design)
    out["used_for_repair"] = bool(repair)
    out["used_for_certificate"] = split == "certification" and not design and not repair
    return out


def summarize_trial(sample: pd.DataFrame, blocks: pd.DataFrame, true_recall: float, gamma: float, delta: float, theta: float, block_size: float, trial: int, mode: str, costs: dict) -> dict:
    cert = conservative_certificate(sample, len(blocks), delta)
    total_events = int(blocks["Y_i_O"].sum())
    total_missed = int(blocks["M_i_O"].sum())
    lcb = float(cert["LCB_recall_O"])
    return {
        "mode": mode,
        "trial": trial,
        "gamma": gamma,
        "delta": delta,
        "theta": theta,
        "block_size_seconds": block_size,
        "population_blocks": len(blocks),
        "sampled_blocks": len(sample),
        "sample_split": "certification",
        "used_for_design": False,
        "used_for_repair": False,
        "used_for_certificate": True,
        "padding_width_used": float(sample["padding_width_used"].max()) if len(sample) else math.nan,
        "score_source": ";".join(sorted(sample["score_source"].dropna().astype(str).unique())) if len(sample) else "proxy_score",
        "Y_sample_sum_O": int(sample["Y_i_O"].sum()) if len(sample) else 0,
        "M_sample_sum_O": int(sample["M_i_O"].sum()) if len(sample) else 0,
        "total_events_O": total_events,
        "total_missed_O": total_missed,
        "true_oracle_recall": true_recall,
        "UCB_M_O": cert["UCB_M_O"],
        "LCB_Y_O": cert["LCB_Y_O"],
        "LCB_recall_O": lcb,
        "coverage": lcb <= true_recall,
        "GVR": lcb > true_recall,
        "tightness": true_recall - lcb,
        "certificate_success": lcb >= gamma,
        "certificate_status": cert["certificate_status"] if lcb >= gamma else "NO_CERTIFICATE",
        "cost_to_certificate": costs.get("certification_cost", len(sample)),
        "diagnostic_cost": costs.get("diagnostic_cost", 0),
        "repair_cost": costs.get("repair_cost", 0),
        "certification_cost": costs.get("certification_cost", len(sample)),
        "total_cost": costs.get("total_cost", costs.get("certification_cost", len(sample))),
        "event_boundary_type": "pseudo_from_adjacent_oracle_positive_units",
        "oracle_relative": True,
    }


def no_repair_trials() -> pd.DataFrame:
    units = load_units()
    events = build_pseudo_events(units)
    rng = np.random.default_rng(RANDOM_SEED + 20)
    rows = []
    returned = fixed_returned_clips(units, RETURNED_CLIP_BUDGET_FRAC)
    for theta in THETAS:
        true_recall, _, _ = event_recall(events, returned, theta)
        for block_size in BLOCK_SIZES:
            blocks = partition_blocks(units, events, returned, block_size, theta)
            for gamma in GAMMAS:
                for delta in DELTAS:
                    for trial in range(NUM_TRIALS):
                        sample = add_provenance(sample_blocks(blocks, rng, CERT_SAMPLE_FRAC), "certification", False, False)
                        rows.append(
                            summarize_trial(
                                sample,
                                blocks,
                                true_recall,
                                gamma,
                                delta,
                                theta,
                                block_size,
                                trial,
                                "no_repair",
                                {"certification_cost": len(sample), "total_cost": len(sample)},
                            )
                        )
    return pd.DataFrame(rows)


def repair_trials() -> pd.DataFrame:
    b1_path = OUT_DIR / "tables/block_audit_no_repair_results.csv"
    if not b1_path.exists():
        raise SystemExit("repair_fresh_cert requires no-repair results first")
    b1 = pd.read_csv(b1_path)
    viable = bool((b1["coverage"].mean() >= 0.90) and (b1["LCB_recall_O"].fillna(0).mean() > 0.05))
    if not viable:
        skipped = pd.DataFrame(
            [
                {
                    "mode": "repair_fresh_cert",
                    "trial": -1,
                    "stage_status": "SKIPPED_B1_NOT_CONSERVATIVE_NONVACUOUS",
                    "sample_split": "certification",
                    "used_for_design": False,
                    "used_for_repair": False,
                    "used_for_certificate": False,
                    "padding_width_used": math.nan,
                    "score_source": "proxy_score",
                    "diagnostic_cost": 0,
                    "repair_cost": 0,
                    "certification_cost": 0,
                    "total_cost": 0,
                }
            ]
        )
        return skipped
    units = load_units()
    events = build_pseudo_events(units)
    rng = np.random.default_rng(RANDOM_SEED + 30)
    rows = []
    base_returned = fixed_returned_clips(units, RETURNED_CLIP_BUDGET_FRAC)
    for theta in THETAS:
        for block_size in BLOCK_SIZES:
            base_blocks = partition_blocks(units, events, base_returned, block_size, theta)
            for gamma in GAMMAS:
                for delta in DELTAS:
                    for trial in range(NUM_TRIALS):
                        diag = add_provenance(sample_blocks(base_blocks, rng, DIAG_SAMPLE_FRAC), "diagnostic", True, False)
                        missed_diag = set(diag.loc[diag["M_i_O"] > 0, "block_id"].astype(str))
                        repair_units = []
                        for _, block in base_blocks[base_blocks["block_id"].isin(missed_diag)].iterrows():
                            inside = units[
                                (units["video_id"].astype(str) == str(block["video_id"]))
                                & (units["start_time"] >= float(block["block_start"]))
                                & (units["start_time"] < float(block["block_end"]))
                            ]
                            repair_units.append(inside)
                        if repair_units:
                            repaired_selected = pd.concat(repair_units, ignore_index=True)
                            repaired = pd.concat(
                                [
                                    base_returned.rename(columns={"returned_clip_id": "unit_id"})[["video_id", "start_time", "end_time"]],
                                    repaired_selected[["video_id", "start_time", "end_time"]],
                                ],
                                ignore_index=True,
                            ).drop_duplicates()
                            repaired["returned_clip_id"] = [f"repair_returned_{i:05d}" for i in range(len(repaired))]
                        else:
                            repaired = base_returned.copy()
                        final_blocks = partition_blocks(units, events, repaired, block_size, theta)
                        cert = add_provenance(sample_blocks(final_blocks, rng, CERT_SAMPLE_FRAC, exclude_ids=missed_diag), "certification", False, False)
                        true_recall, _, _ = event_recall(events, repaired, theta)
                        rows.append(
                            summarize_trial(
                                cert,
                                final_blocks,
                                true_recall,
                                gamma,
                                delta,
                                theta,
                                block_size,
                                trial,
                                "repair_fresh_cert",
                                {
                                    "diagnostic_cost": len(diag),
                                    "repair_cost": int(sum(len(x) for x in repair_units)) if repair_units else 0,
                                    "certification_cost": len(cert),
                                    "total_cost": len(diag) + (int(sum(len(x) for x in repair_units)) if repair_units else 0) + len(cert),
                                },
                            )
                        )
    return pd.DataFrame(rows)


def write_figures(no_repair: pd.DataFrame) -> None:
    if no_repair.empty:
        return
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.scatter(no_repair["true_oracle_recall"], no_repair["LCB_recall_O"], s=12, alpha=0.35, color="#315c72")
    lim = [0, 1]
    ax.plot(lim, lim, color="#444444", linewidth=1)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("Full pseudo-oracle recall")
    ax.set_ylabel("LCB_recall^O")
    ax.set_title("No-repair block audit LCB vs recall")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figures/block_audit_lcb_vs_true_recall.png", dpi=160)
    plt.close(fig)

    summary = no_repair.groupby(["block_size_seconds", "gamma", "delta"], as_index=False).agg(GVR=("GVR", "mean"))
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for block_size, group in summary.groupby("block_size_seconds"):
        labels = [f"g={r.gamma},d={r.delta}" for r in group.itertuples()]
        ax.plot(labels, group["GVR"], marker="o", label=f"{block_size:g}s")
    ax.set_ylabel("Coverage violation rate")
    ax.set_title("No-repair block audit GVR by block size")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figures/block_audit_gvr_by_budget.png", dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["no_repair", "repair_fresh_cert"], required=True)
    args = parser.parse_args()
    ensure_dirs()
    if args.mode == "no_repair":
        out = no_repair_trials()
        out.to_csv(OUT_DIR / "tables/block_audit_no_repair_results.csv", index=False)
        write_figures(out)
        append_progress(
            "block audit no-repair",
            "python scripts/20_block_audit_simulation.py --mode no_repair",
            f"wrote {len(out)} rows; coverage={out['coverage'].mean():.3f}",
            next_action="decide repair fresh-cert stage",
        )
    else:
        out = repair_trials()
        out.to_csv(OUT_DIR / "tables/block_audit_repair_fresh_cert_results.csv", index=False)
        append_progress(
            "block audit repair fresh-cert",
            "python scripts/20_block_audit_simulation.py --mode repair_fresh_cert",
            f"wrote {len(out)} rows",
            next_action="run oracle stability audit",
        )


if __name__ == "__main__":
    main()
