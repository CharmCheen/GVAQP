#!/usr/bin/env python3
"""Evaluator-backed VERA headroom and failure-region simulation.

All event-reference access is confined to this offline ceiling analysis. The
physical plan is uniform and does not consume these rows.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = next(
    p for p in Path(__file__).resolve().parents
    if (p / "Audited_Event_Hypothesis_AQP_Design_Pack_v1").is_dir()
)
OUT = ROOT / "AQP_Algorithm_Invention_Sprint_v1/simulation"
STRICT = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
SEEDS = 500
DENSE_UNITS = 347
RECALL_TARGET = 0.80
F1_TARGET = 0.80
COST_TARGET = 0.70
UNIT_RUNTIME = 15.410652

CORE_LENGTHS = [10, 20, 30, 50, 80, 110]
MARGINS = [0, 5, 10]
SENSITIVITIES = [0.70, 0.80, 0.85, 0.90, 0.95, 1.00]
LOCALIZATION = [0.80, 0.90, 0.95, 1.00]
FALSE_EVENTS_PER_WINDOW = [0.00, 0.02, 0.05, 0.10]
COST_SCALES = [1.0, 2.0, 3.0, 4.0, 6.0]
PLACEMENTS = ["independent", "boundary_correlated", "event_cluster_correlated", "adversarial_count"]


def beta_binomial_tp(rng: np.random.Generator, m: int, p: float, rho: float, size: int) -> np.ndarray:
    if p <= 0:
        return np.zeros(size, dtype=int)
    if p >= 1:
        return np.full(size, m, dtype=int)
    if rho <= 0:
        return rng.binomial(m, p, size=size)
    concentration = 1.0 / rho - 1.0
    per_run_p = rng.beta(p * concentration, (1 - p) * concentration, size=size)
    return rng.binomial(m, per_run_p)


def sample_counts(m: int, p: float, fp_rate: float, windows: int, placement: str, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    if placement == "independent":
        tp = beta_binomial_tp(rng, m, p, 0.0, SEEDS)
    elif placement == "boundary_correlated":
        tp = beta_binomial_tp(rng, m, p, 0.10, SEEDS)
    elif placement == "event_cluster_correlated":
        tp = beta_binomial_tp(rng, m, p, 0.30, SEEDS)
    elif placement == "adversarial_count":
        tp = np.full(SEEDS, max(0, m - math.ceil((1 - p) * m)), dtype=int)
    else:
        raise ValueError(placement)
    fp = rng.poisson(fp_rate * windows, size=SEEDS)
    return tp, fp


def summarize_cell(
    dataset: str,
    event_count: int,
    duration: float,
    core: int,
    margin: int,
    sensitivity: float,
    localization: float,
    fp_rate: float,
    cost_scale: float,
    placement: str,
    containment: float,
) -> dict[str, object]:
    windows = math.ceil(duration / core)
    p = sensitivity * localization
    seed = int(
        810_000_000
        + event_count * 100_000
        + core * 1_000
        + margin * 100
        + round(sensitivity * 10) * 11
        + round(localization * 10) * 17
        + round(fp_rate * 100) * 19
        + round(cost_scale * 10) * 23
        + PLACEMENTS.index(placement) * 29
    )
    tp, fp = sample_counts(event_count, p, fp_rate, windows, placement, seed)
    recall = tp / event_count
    precision = np.divide(tp, tp + fp, out=np.ones(SEEDS, dtype=float), where=(tp + fp) > 0)
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros(SEEDS), where=(precision + recall) > 0)
    unit_equiv = windows * cost_scale
    ratio = unit_equiv / DENSE_UNITS
    return {
        "dataset": dataset,
        "event_count": event_count,
        "video_duration_seconds": duration,
        "core_length_seconds": core,
        "margin_seconds": margin,
        "input_window_seconds_nominal": core + 2 * margin,
        "windows": windows,
        "sensitivity": sensitivity,
        "localization_success": localization,
        "effective_event_success": p,
        "false_events_per_window": fp_rate,
        "placement": placement,
        "cost_scale_vs_10s_unit": cost_scale,
        "seeds": SEEDS,
        "full_reference_containment_rate": containment,
        "logical_calls": windows,
        "unit_equivalent_cost": unit_equiv,
        "dense_cost_ratio": ratio,
        "predicted_gpu_seconds": unit_equiv * UNIT_RUNTIME,
        "event_precision_mean": float(precision.mean()),
        "event_recall_mean": float(recall.mean()),
        "event_recall_p05": float(np.quantile(recall, 0.05)),
        "event_f1_mean": float(f1.mean()),
        "event_f1_p05": float(np.quantile(f1, 0.05)),
        "failure_probability_recall": float(np.mean(recall < RECALL_TARGET)),
        "failure_probability_f1": float(np.mean(f1 < F1_TARGET)),
        "quality_pass_mean": bool(recall.mean() >= RECALL_TARGET and f1.mean() >= F1_TARGET),
        "quality_pass_p05": bool(np.quantile(recall, 0.05) >= RECALL_TARGET and np.quantile(f1, 0.05) >= F1_TARGET),
        "cost_pass": bool(ratio < COST_TARGET),
        "joint_pass_mean": bool(recall.mean() >= RECALL_TARGET and f1.mean() >= F1_TARGET and ratio < COST_TARGET),
        "joint_pass_p05": bool(np.quantile(recall, 0.05) >= RECALL_TARGET and np.quantile(f1, 0.05) >= F1_TARGET and ratio < COST_TARGET),
        "evaluator_backed_ceiling": True,
    }


def containment_rate(events: pd.DataFrame, duration: float, core: int, margin: int) -> float:
    contained = []
    for row in events.itertuples():
        owner = int(row.canonical_anchor_time // core)
        c0 = owner * core
        c1 = min(duration, c0 + core)
        w0 = max(0.0, c0 - margin)
        w1 = min(duration, c1 + margin)
        contained.append(row.start_time >= w0 and row.end_time <= w1)
    return float(np.mean(contained))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    units = pd.read_csv(STRICT / "frozen_inputs/units.csv")
    events = pd.read_csv(STRICT / "frozen_inputs/event_reference.csv")
    duration = float(units.end_time.max())
    scenarios = [("strict_reference", len(events), duration)] + [
        (f"synthetic_prevalence_{rate:.2f}", max(1, round(DENSE_UNITS * rate)), duration)
        for rate in [0.02, 0.05, 0.10, 0.20]
    ]
    rows: list[dict[str, object]] = []
    for dataset, m, video_duration in scenarios:
        placements = PLACEMENTS if dataset == "strict_reference" else ["independent"]
        for core in CORE_LENGTHS:
            for margin in MARGINS:
                contain = containment_rate(events, duration, core, margin) if dataset == "strict_reference" else 1.0
                for sensitivity in SENSITIVITIES:
                    for localization in LOCALIZATION:
                        for fp_rate in FALSE_EVENTS_PER_WINDOW:
                            for cost_scale in COST_SCALES:
                                for placement in placements:
                                    rows.append(summarize_cell(dataset, m, video_duration, core, margin, sensitivity, localization, fp_rate, cost_scale, placement, contain))
    grid = pd.DataFrame(rows)
    grid.to_csv(OUT / "HEADROOM_GRID.csv", index=False)
    grid[~grid.joint_pass_mean].to_csv(OUT / "FAILURE_REGION.csv", index=False)

    strict = grid[grid.dataset == "strict_reference"]
    group = [
        "core_length_seconds", "margin_seconds", "sensitivity",
        "localization_success", "false_events_per_window",
        "cost_scale_vs_10s_unit",
    ]
    robust_rows = []
    for keys, cell in strict.groupby(group):
        robust_rows.append(dict(zip(group, keys)) | {
            "placements": int(cell.placement.nunique()),
            "robust_mean_pass": bool(cell.joint_pass_mean.all()),
            "robust_p05_pass": bool(cell.joint_pass_p05.all()),
            "worst_recall_mean": float(cell.event_recall_mean.min()),
            "worst_recall_p05": float(cell.event_recall_p05.min()),
            "worst_f1_mean": float(cell.event_f1_mean.min()),
            "worst_f1_p05": float(cell.event_f1_p05.min()),
            "dense_cost_ratio": float(cell.dense_cost_ratio.max()),
        })
    robust = pd.DataFrame(robust_rows)
    robust.to_csv(OUT / "ROBUST_HEADROOM_REGION.csv", index=False)

    fallback_group = [
        "dataset", "event_count", "sensitivity", "localization_success",
        "false_events_per_window", "placement", "cost_scale_vs_10s_unit",
    ]
    selected = []
    for keys, cell in grid.groupby(fallback_group):
        feasible = cell[cell.joint_pass_mean]
        if feasible.empty:
            selected.append(dict(zip(fallback_group, keys)) | {
                "selected_plan": "DENSE_FALLBACK", "core_length_seconds": 10,
                "margin_seconds": 0, "dense_cost_ratio": 1.0,
                "event_recall_mean": 1.0, "event_f1_mean": 0.962963 if keys[0] == "strict_reference" else 1.0,
            })
        else:
            best = feasible.sort_values(["dense_cost_ratio", "event_f1_mean", "core_length_seconds", "margin_seconds"], ascending=[True, False, True, True]).iloc[0]
            selected.append(dict(zip(fallback_group, keys)) | {
                "selected_plan": "VERA", "core_length_seconds": int(best.core_length_seconds),
                "margin_seconds": int(best.margin_seconds), "dense_cost_ratio": float(best.dense_cost_ratio),
                "event_recall_mean": float(best.event_recall_mean), "event_f1_mean": float(best.event_f1_mean),
            })
    fallback = pd.DataFrame(selected)
    fallback.to_csv(OUT / "DENSE_FALLBACK_ANALYSIS.csv", index=False)

    # Predeclared realistic falsification cell for the physical-plan shape.
    realistic = robust[
        (robust.core_length_seconds == 50)
        & (robust.margin_seconds == 5)
        & (robust.sensitivity == 0.95)
        & (robust.localization_success == 0.95)
        & (robust.false_events_per_window == 0.05)
        & (robust.cost_scale_vs_10s_unit == 3.0)
    ]
    physical_justified = bool(len(realistic) == 1 and realistic.iloc[0].robust_mean_pass)
    summary = {
        "pre_execution_decision": "PHYSICAL_PILOT_JUSTIFIED" if physical_justified else "PHYSICAL_PILOT_NOT_JUSTIFIED",
        "grid_rows": len(grid),
        "seeds_per_cell": SEEDS,
        "robust_mean_passing_cells": int(robust.robust_mean_pass.sum()),
        "robust_p05_passing_cells": int(robust.robust_p05_pass.sum()),
        "realistic_registered_cell_pass": physical_justified,
        "physical_plan": {"core_seconds": 50, "margin_seconds": 5, "windows": math.ceil(duration / 50)},
        "physical_vlm_calls_so_far": 0,
    }
    (OUT / "PRE_EXECUTION_DECISION.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
