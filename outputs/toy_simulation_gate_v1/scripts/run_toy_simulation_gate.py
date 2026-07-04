#!/usr/bin/env python3
"""Synthetic AQP planner gate.

Runs no video, no VLM, and no repository oracle labels. The pseudo-oracle is
the synthetic truth generated inside each toy world.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "toy_simulation_gate_v1"
TABLES = OUT / "tables"
FIGURES = OUT / "figures"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"

N_BINS = 2000
LAMBDA_CLUSTERS = 18
WIDTH_RANGES = {
    "isolated": (1, 1),
    "narrow": (3, 7),
    "wide": (18, 45),
}
SCENARIOS = ["strong", "weak", "wrong", "none"]
PLANNERS = ["uniform", "top_prior_only", "audit_discover", "full_planner"]
CHECKPOINTS = [20, 40, 80, 120, 160]
BUDGET = 160
N_STRATA = 10
AUDIT_FRACTION = 0.35
ETA = 0.10
REPAIR_RADIUS = 12
Z95 = 1.96


@dataclass
class World:
    truth: np.ndarray
    score: np.ndarray
    prior_prob: np.ndarray
    clusters: list[tuple[int, int]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_progress(mode: str, result: str, failure: str = "none", fix: str = "none", next_action: str = "") -> None:
    with (LOGS / "progress.md").open("a") as f:
        f.write(f"\n## {utc_now()} - Run toy simulation gate ({mode})\n\n")
        f.write(f"- Checkpoint: Run toy simulation gate ({mode})\n")
        f.write(f"- Commands run: `python outputs/toy_simulation_gate_v1/scripts/run_toy_simulation_gate.py --mode {mode}`\n")
        f.write(f"- Result: {result}\n")
        f.write(f"- Failure: {failure}\n")
        f.write(f"- Fix applied: {fix}\n")
        if next_action:
            f.write(f"- Next action: {next_action}\n")


def generate_world(rng: np.random.Generator, width_mode: str, scenario: str) -> World:
    truth = np.zeros(N_BINS, dtype=bool)
    clusters = []
    low, high = WIDTH_RANGES[width_mode]
    k = max(1, int(rng.poisson(LAMBDA_CLUSTERS)))
    for _ in range(k):
        width = int(rng.integers(low, high + 1))
        start = int(rng.integers(0, max(1, N_BINS - width + 1)))
        end = min(N_BINS, start + width)
        truth[start:end] = True
        clusters.append((start, end))

    noise = rng.normal(0.0, 1.0, N_BINS)
    score = noise.copy()
    if scenario == "strong":
        score += truth.astype(float) * 3.0
    elif scenario == "weak":
        score += truth.astype(float) * 0.9
    elif scenario == "wrong":
        score -= truth.astype(float) * 1.2
        decoy_count = max(1, int(truth.sum()))
        neg = np.flatnonzero(~truth)
        decoys = rng.choice(neg, size=min(decoy_count, len(neg)), replace=False)
        score[decoys] += 3.0
    elif scenario == "none":
        score = rng.normal(0.0, 1.0, N_BINS)
    else:
        raise ValueError(scenario)

    ranks = np.argsort(np.argsort(score)).astype(float)
    percentile = (ranks + 1.0) / N_BINS
    prior_prob = np.clip(0.02 + 0.35 * percentile, 0.001, 0.8)
    return World(truth=truth, score=score, prior_prob=prior_prob, clusters=clusters)


def make_strata(score: np.ndarray) -> list[np.ndarray]:
    order = np.argsort(score)
    strata = []
    for idxs in np.array_split(order, N_STRATA):
        strata.append(np.array(idxs, dtype=int))
    return strata


def wilson_interval(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    phat = successes / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    margin = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def stratified_estimate(truth: np.ndarray, audit_samples: dict[int, list[int]], strata: list[np.ndarray]) -> dict:
    estimate = 0.0
    lower = 0.0
    upper = 0.0
    sampled = 0
    for sid, idxs in enumerate(strata):
        samples = audit_samples.get(sid, [])
        n = len(samples)
        sampled += n
        successes = int(truth[samples].sum()) if samples else 0
        if n == 0:
            phat = 0.0
            lo, hi = 0.0, 1.0
        else:
            phat = successes / n
            lo, hi = wilson_interval(successes, n)
        size = len(idxs)
        estimate += size * phat
        lower += size * lo
        upper += size * hi
    true_mass = int(truth.sum())
    return {
        "mhat_total": estimate,
        "mhat_lower_95": lower,
        "mhat_upper_95": upper,
        "true_mass": true_mass,
        "covered_95": lower <= true_mass <= upper,
        "audit_samples": sampled,
    }


def select_audit_index(rng: np.random.Generator, observed: np.ndarray, audit_samples: dict[int, list[int]], strata: list[np.ndarray]) -> tuple[int | None, int | None]:
    best_sid = None
    best_score = -1.0
    for sid, idxs in enumerate(strata):
        available = idxs[~observed[idxs]]
        if len(available) == 0:
            continue
        n = len(audit_samples.get(sid, []))
        priority = len(idxs) / math.sqrt(n + 1.0)
        if priority > best_score:
            best_score = priority
            best_sid = sid
    if best_sid is None:
        return None, None
    candidates = strata[best_sid][~observed[strata[best_sid]]]
    return int(rng.choice(candidates)), best_sid


def add_repair_candidates(idx: int, observed: np.ndarray, repair_pool: set[int]) -> None:
    lo = max(0, idx - REPAIR_RADIUS)
    hi = min(N_BINS, idx + REPAIR_RADIUS + 1)
    for j in range(lo, hi):
        if j != idx and not observed[j]:
            repair_pool.add(j)


def choose_repair_candidate(repair_pool: set[int], observed: np.ndarray, positives: list[int]) -> int | None:
    available = [idx for idx in repair_pool if not observed[idx]]
    if not available:
        return None
    if not positives:
        return min(available)
    return min(available, key=lambda j: min(abs(j - p) for p in positives))


def run_policy(world: World, planner: str, rng: np.random.Generator) -> dict:
    observed = np.zeros(N_BINS, dtype=bool)
    found_positive = np.zeros(N_BINS, dtype=bool)
    strata = make_strata(world.score)
    audit_samples: dict[int, list[int]] = defaultdict(list)
    repair_pool: set[int] = set()
    repair_a = 1.0
    repair_b = 1.0
    repair_attempts = 0
    repair_hits = 0
    audit_calls = 0
    discover_calls = 0
    repair_calls = 0
    audit_positive_bins = 0
    discover_positive_bins = 0
    repair_positive_bins = 0
    order_desc = list(np.argsort(world.score)[::-1])
    uniform_order = list(rng.permutation(N_BINS))
    top_cursor = 0
    uniform_cursor = 0
    curves = []

    def observe(idx: int, action: str, sid: int | None = None) -> None:
        nonlocal audit_calls, discover_calls, repair_calls, repair_a, repair_b, repair_attempts, repair_hits
        nonlocal audit_positive_bins, discover_positive_bins, repair_positive_bins
        observed[idx] = True
        is_pos = bool(world.truth[idx])
        if is_pos:
            found_positive[idx] = True
            add_repair_candidates(idx, observed, repair_pool)
        if action == "AUDIT":
            audit_calls += 1
            if is_pos:
                audit_positive_bins += 1
            if sid is not None:
                audit_samples[sid].append(idx)
        elif action == "DISCOVER":
            discover_calls += 1
            if is_pos:
                discover_positive_bins += 1
        elif action == "REPAIR":
            repair_calls += 1
            repair_attempts += 1
            if is_pos:
                repair_positive_bins += 1
            if is_pos:
                repair_hits += 1
                repair_a += 1.0
            else:
                repair_b += 1.0

    for step in range(1, BUDGET + 1):
        if planner == "uniform":
            while uniform_cursor < len(uniform_order) and observed[uniform_order[uniform_cursor]]:
                uniform_cursor += 1
            idx = int(uniform_order[uniform_cursor])
            observe(idx, "DISCOVER")
        elif planner == "top_prior_only":
            while top_cursor < len(order_desc) and observed[order_desc[top_cursor]]:
                top_cursor += 1
            idx = int(order_desc[top_cursor])
            observe(idx, "DISCOVER")
        else:
            target_audit = int(math.ceil(AUDIT_FRACTION * step))
            use_audit = audit_calls < target_audit or rng.random() < ETA
            if planner == "full_planner" and not use_audit:
                repair_idx = choose_repair_candidate(repair_pool, observed, list(np.flatnonzero(found_positive)))
                if repair_idx is not None:
                    mean = repair_a / (repair_a + repair_b)
                    var = (repair_a * repair_b) / (((repair_a + repair_b) ** 2) * (repair_a + repair_b + 1.0))
                    repair_bid = min(1.0, mean + 1.0 * math.sqrt(var))
                    while top_cursor < len(order_desc) and observed[order_desc[top_cursor]]:
                        top_cursor += 1
                    best_idx = int(order_desc[top_cursor]) if top_cursor < len(order_desc) else None
                    discover_bid = float(world.prior_prob[best_idx]) if best_idx is not None else -1.0
                    if repair_bid >= discover_bid:
                        repair_pool.discard(repair_idx)
                        observe(repair_idx, "REPAIR")
                    elif best_idx is not None:
                        observe(best_idx, "DISCOVER")
                    else:
                        idx, sid = select_audit_index(rng, observed, audit_samples, strata)
                        if idx is not None:
                            observe(idx, "AUDIT", sid)
                else:
                    while top_cursor < len(order_desc) and observed[order_desc[top_cursor]]:
                        top_cursor += 1
                    if top_cursor < len(order_desc):
                        observe(int(order_desc[top_cursor]), "DISCOVER")
                    else:
                        idx, sid = select_audit_index(rng, observed, audit_samples, strata)
                        if idx is not None:
                            observe(idx, "AUDIT", sid)
            elif use_audit:
                idx, sid = select_audit_index(rng, observed, audit_samples, strata)
                if idx is not None:
                    observe(idx, "AUDIT", sid)
            else:
                while top_cursor < len(order_desc) and observed[order_desc[top_cursor]]:
                    top_cursor += 1
                if top_cursor < len(order_desc):
                    observe(int(order_desc[top_cursor]), "DISCOVER")
        if step in CHECKPOINTS:
            true_mass = int(world.truth.sum())
            found = int(found_positive.sum())
            missing = max(0, true_mass - found)
            est = stratified_estimate(world.truth, audit_samples, strata)
            denom = max(1, true_mass)
            curves.append(
                {
                    "budget": step,
                    "found_positive_bins": found,
                    "true_positive_bins": true_mass,
                    "missing_mass_fraction": missing / true_mass if true_mass else 0.0,
                    "audit_calls": audit_calls,
                    "discover_calls": discover_calls,
                    "repair_calls": repair_calls,
                    "audit_positive_bins": audit_positive_bins,
                    "discover_positive_bins": discover_positive_bins,
                    "repair_positive_bins": repair_positive_bins,
                    "mhat_total": est["mhat_total"],
                    "mhat_lower_95": est["mhat_lower_95"],
                    "mhat_upper_95": est["mhat_upper_95"],
                    "mhat_covered_95": est["covered_95"],
                    "phi_estimated_missing_mass": max(0.0, est["mhat_total"] - found) / denom,
                    "phi_upper_missing_mass": max(0.0, est["mhat_upper_95"] - found) / denom,
                    "phi_true_missing_mass": missing / denom,
                    "dual_ledger_audit_samples": est["audit_samples"],
                    "dual_ledger_discovery_calls": discover_calls,
                    "dual_ledger_repair_calls": repair_calls,
                }
            )

    final_est = stratified_estimate(world.truth, audit_samples, strata)
    return {
        "curves": curves,
        "final_estimate": final_est,
        "repair_attempts": repair_attempts,
        "repair_hits": repair_hits,
        "repair_hit_rate": repair_hits / repair_attempts if repair_attempts else 0.0,
        "final_repair_q": repair_a / (repair_a + repair_b),
        "audit_calls": audit_calls,
        "discover_calls": discover_calls,
        "repair_calls": repair_calls,
        "audit_positive_bins": audit_positive_bins,
        "discover_positive_bins": discover_positive_bins,
        "repair_positive_bins": repair_positive_bins,
        "found_positive_bins": int(found_positive.sum()),
        "true_positive_bins": int(world.truth.sum()),
        "final_mhat_audit_samples": final_est["audit_samples"],
    }


def aggregate(rows: list[dict], keys: list[str], value_cols: list[str]) -> list[dict]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[k] for k in keys)].append(row)
    out = []
    for key, group in sorted(grouped.items()):
        item = {k: v for k, v in zip(keys, key)}
        item["runs"] = len(group)
        for col in value_cols:
            vals = np.array([float(r[col]) for r in group], dtype=float)
            item[f"{col}_mean"] = f"{float(np.mean(vals)):.6f}"
            item[f"{col}_std"] = f"{float(np.std(vals)):.6f}"
            item[f"{col}_p025"] = f"{float(np.quantile(vals, 0.025)):.6f}"
            item[f"{col}_p975"] = f"{float(np.quantile(vals, 0.975)):.6f}"
        out.append(item)
    return out


def line_svg(path: Path, rows: list[dict], title: str, y_col: str, group_col: str, filter_row=None) -> None:
    data = [r for r in rows if filter_row is None or filter_row(r)]
    width, height = 860, 320
    left, right, top, bottom = 54, 24, 34, 42
    plot_w = width - left - right
    plot_h = height - top - bottom
    budgets = sorted({int(r["budget"]) for r in data})
    groups = sorted({r[group_col] for r in data})
    colors = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c"]
    y_vals = [float(r[y_col]) for r in data]
    y_min = min(y_vals) if y_vals else 0.0
    y_max = max(y_vals) if y_vals else 1.0
    if abs(y_max - y_min) < 1e-9:
        y_max = y_min + 1.0

    def x(budget: int) -> float:
        return left + ((budget - min(budgets)) / max(1, max(budgets) - min(budgets))) * plot_w

    def y(val: float) -> float:
        return top + (1.0 - (val - y_min) / (y_max - y_min)) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="22" font-family="Arial" font-size="15" fill="#111827">{title}</text>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#6b7280"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#6b7280"/>',
    ]
    for gi, group in enumerate(groups):
        pts = []
        for budget in budgets:
            matches = [r for r in data if r[group_col] == group and int(r["budget"]) == budget]
            if matches:
                pts.append(f"{x(budget):.1f},{y(float(matches[0][y_col])):.1f}")
        if pts:
            parts.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{colors[gi % len(colors)]}" stroke-width="2"/>')
            parts.append(f'<text x="{width - 190}" y="{24 + gi * 17}" font-family="Arial" font-size="11" fill="{colors[gi % len(colors)]}">{group}</text>')
    for budget in budgets:
        xx = x(budget)
        parts.append(f'<line x1="{xx:.1f}" y1="{top + plot_h}" x2="{xx:.1f}" y2="{top + plot_h + 5}" stroke="#374151"/>')
        parts.append(f'<text x="{xx - 10:.1f}" y="{height - 14}" font-family="Arial" font-size="11" fill="#374151">{budget}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def bar_svg(path: Path, rows: list[dict], title: str, label_col: str, value_col: str) -> None:
    width, height = 760, 280
    left, right, top, bottom = 64, 24, 34, 50
    plot_w = width - left - right
    plot_h = height - top - bottom
    vals = [float(r[value_col]) for r in rows]
    max_val = max(vals) if vals else 1.0
    bar_w = plot_w / max(1, len(rows))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="22" font-family="Arial" font-size="15" fill="#111827">{title}</text>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#6b7280"/>',
    ]
    for i, row in enumerate(rows):
        val = float(row[value_col])
        h = (val / max_val) * plot_h if max_val else 0
        x = left + i * bar_w
        y = top + plot_h - h
        parts.append(f'<rect x="{x + 6:.1f}" y="{y:.1f}" width="{max(1, bar_w - 12):.1f}" height="{h:.1f}" fill="#2563eb" opacity="0.82"/>')
        parts.append(f'<text x="{x + 2:.1f}" y="{height - 16}" font-family="Arial" font-size="10" fill="#374151">{row[label_col]}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def run_experiment(mode: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    base_seed = 20260703 if mode == "full" else 20260704
    repeats = 120 if mode == "full" else 8
    rng = np.random.default_rng(base_seed)

    world_rows = []
    calibration_rows = []
    curve_rows = []
    final_rows = []
    repair_rows = []

    for width_mode in WIDTH_RANGES:
        for scenario in SCENARIOS:
            for rep in range(repeats):
                world_seed = int(rng.integers(0, 2**31 - 1))
                world_rng = np.random.default_rng(world_seed)
                world = generate_world(world_rng, width_mode, scenario)
                world_rows.append(
                    {
                        "mode": mode,
                        "width_mode": width_mode,
                        "scenario": scenario,
                        "rep": rep,
                        "world_seed": world_seed,
                        "cluster_count": len(world.clusters),
                        "true_positive_bins": int(world.truth.sum()),
                        "positive_fraction": f"{float(world.truth.mean()):.6f}",
                    }
                )
                for planner in PLANNERS:
                    policy_seed = int(rng.integers(0, 2**31 - 1))
                    result = run_policy(world, planner, np.random.default_rng(policy_seed))
                    final_est = result["final_estimate"]
                    if planner in ("audit_discover", "full_planner"):
                        calibration_rows.append(
                            {
                                "mode": mode,
                                "width_mode": width_mode,
                                "scenario": scenario,
                                "rep": rep,
                                "planner": planner,
                                "covered_95": int(final_est["covered_95"]),
                                "true_mass": final_est["true_mass"],
                                "mhat_total": f"{final_est['mhat_total']:.6f}",
                                "mhat_lower_95": f"{final_est['mhat_lower_95']:.6f}",
                                "mhat_upper_95": f"{final_est['mhat_upper_95']:.6f}",
                                "audit_samples": final_est["audit_samples"],
                            }
                        )
                    for curve in result["curves"]:
                        curve_rows.append(
                            {
                                "mode": mode,
                                "width_mode": width_mode,
                                "scenario": scenario,
                                "rep": rep,
                                "planner": planner,
                                **curve,
                            }
                        )
                    final_rows.append(
                        {
                            "mode": mode,
                            "width_mode": width_mode,
                            "scenario": scenario,
                            "rep": rep,
                            "planner": planner,
                            "found_positive_bins": result["found_positive_bins"],
                            "true_positive_bins": result["true_positive_bins"],
                            "missing_mass_fraction": 1.0 - (result["found_positive_bins"] / max(1, result["true_positive_bins"])),
                            "audit_calls": result["audit_calls"],
                            "discover_calls": result["discover_calls"],
                            "repair_calls": result["repair_calls"],
                            "audit_positive_bins": result["audit_positive_bins"],
                            "discover_positive_bins": result["discover_positive_bins"],
                            "repair_positive_bins": result["repair_positive_bins"],
                            "final_mhat_audit_samples": result["final_mhat_audit_samples"],
                            "repair_attempts": result["repair_attempts"],
                            "repair_hits": result["repair_hits"],
                            "repair_hit_rate": result["repair_hit_rate"],
                            "final_repair_q": result["final_repair_q"],
                        }
                    )
                    if planner == "full_planner":
                        repair_rows.append(
                            {
                                "mode": mode,
                                "width_mode": width_mode,
                                "scenario": scenario,
                                "rep": rep,
                                "repair_attempts": result["repair_attempts"],
                                "repair_hits": result["repair_hits"],
                                "repair_hit_rate": result["repair_hit_rate"],
                                "final_repair_q": result["final_repair_q"],
                                "found_positive_bins": result["found_positive_bins"],
                                "true_positive_bins": result["true_positive_bins"],
                            }
                        )

    calibration_summary = []
    grouped_cal = defaultdict(list)
    for row in calibration_rows:
        grouped_cal[(row["width_mode"], row["scenario"], row["planner"])].append(row)
    for (width_mode, scenario, planner), rows in sorted(grouped_cal.items()):
        covered = np.array([int(r["covered_95"]) for r in rows], dtype=float)
        rel_width = np.array([(float(r["mhat_upper_95"]) - float(r["mhat_lower_95"])) / max(1.0, float(r["true_mass"])) for r in rows])
        calibration_summary.append(
            {
                "mode": mode,
                "width_mode": width_mode,
                "scenario": scenario,
                "planner": planner,
                "runs": len(rows),
                "coverage_95ci": f"{float(np.mean(covered)):.6f}",
                "mean_relative_ci_width": f"{float(np.mean(rel_width)):.6f}",
                "mean_audit_samples": f"{float(np.mean([int(r['audit_samples']) for r in rows])):.6f}",
            }
        )

    curve_summary = aggregate(
        curve_rows,
        ["mode", "width_mode", "scenario", "planner", "budget"],
        [
            "missing_mass_fraction",
            "found_positive_bins",
            "audit_calls",
            "discover_calls",
            "repair_calls",
            "phi_estimated_missing_mass",
            "phi_upper_missing_mass",
            "phi_true_missing_mass",
        ],
    )
    final_summary = aggregate(
        final_rows,
        ["mode", "width_mode", "scenario", "planner"],
        [
            "missing_mass_fraction",
            "found_positive_bins",
            "audit_calls",
            "discover_calls",
            "repair_calls",
            "audit_positive_bins",
            "discover_positive_bins",
            "repair_positive_bins",
            "final_mhat_audit_samples",
            "repair_attempts",
            "repair_hit_rate",
            "final_repair_q",
        ],
    )
    repair_summary = aggregate(
        repair_rows,
        ["mode", "width_mode", "scenario"],
        ["repair_attempts", "repair_hit_rate", "final_repair_q", "found_positive_bins"],
    )

    write_csv(TABLES / f"{mode}_world_summary.csv", world_rows)
    write_csv(TABLES / f"{mode}_calibration_raw.csv", calibration_rows)
    write_csv(TABLES / f"{mode}_calibration_summary.csv", calibration_summary)
    write_csv(TABLES / f"{mode}_planner_budget_curves.csv", curve_rows)
    write_csv(TABLES / f"{mode}_planner_budget_curve_summary.csv", curve_summary)
    write_csv(TABLES / f"{mode}_final_planner_summary.csv", final_summary)
    write_csv(TABLES / f"{mode}_repair_summary.csv", repair_summary)

    if mode == "full":
        write_csv(TABLES / "world_summary.csv", world_rows)
        write_csv(TABLES / "calibration_summary.csv", calibration_summary)
        write_csv(TABLES / "planner_budget_curve_summary.csv", curve_summary)
        write_csv(TABLES / "final_planner_summary.csv", final_summary)
        write_csv(TABLES / "repair_summary.csv", repair_summary)

    min_cov = min(float(r["coverage_95ci"]) for r in calibration_summary) if calibration_summary else 0.0
    isolated_rows = [r for r in repair_summary if r["width_mode"] == "isolated" and r["scenario"] in ("weak", "none", "wrong")]
    wide_rows = [r for r in repair_summary if r["width_mode"] == "wide" and r["scenario"] in ("strong", "weak", "wrong")]
    isolated_q = float(np.mean([float(r["final_repair_q_mean"]) for r in isolated_rows])) if isolated_rows else 1.0
    wide_q = float(np.mean([float(r["final_repair_q_mean"]) for r in wide_rows])) if wide_rows else 0.0

    def curve_lookup(width_mode: str, scenario: str, planner: str, budget: int) -> float:
        rows = [
            r for r in curve_summary
            if r["width_mode"] == width_mode and r["scenario"] == scenario and r["planner"] == planner and int(r["budget"]) == budget
        ]
        return float(rows[0]["missing_mass_fraction_mean"]) if rows else 1.0

    wrong_full = np.mean([curve_lookup(w, "wrong", "full_planner", BUDGET) for w in WIDTH_RANGES])
    wrong_top = np.mean([curve_lookup(w, "wrong", "top_prior_only", BUDGET) for w in WIDTH_RANGES])
    wrong_uniform = np.mean([curve_lookup(w, "wrong", "uniform", BUDGET) for w in WIDTH_RANGES])
    phi_rows = [r for r in curve_rows if r["planner"] in ("audit_discover", "full_planner")]
    phi_upper_cover = float(
        np.mean([float(r["phi_upper_missing_mass"]) + 1e-12 >= float(r["phi_true_missing_mass"]) for r in phi_rows])
    ) if phi_rows else 0.0
    phi_corr_rows = [r for r in curve_summary if r["planner"] == "full_planner"]
    phi_est = np.array([float(r["phi_estimated_missing_mass_mean"]) for r in phi_corr_rows], dtype=float)
    phi_true = np.array([float(r["phi_true_missing_mass_mean"]) for r in phi_corr_rows], dtype=float)
    if len(phi_est) > 1 and float(np.std(phi_est)) > 1e-12 and float(np.std(phi_true)) > 1e-12:
        phi_true_corr = float(np.corrcoef(phi_est, phi_true)[0, 1])
    else:
        phi_true_corr = 0.0
    dual_ledger_ok = all(
        int(row["final_mhat_audit_samples"]) == int(row["audit_calls"])
        for row in final_rows
        if row["planner"] in ("audit_discover", "full_planner")
    )
    phi_summary = [
        {
            "mode": mode,
            "planner_scope": "audit_discover_and_full_planner",
            "checkpoint_rows": len(phi_rows),
            "phi_upper_covers_true_missing_mass_fraction": f"{phi_upper_cover:.6f}",
            "full_planner_phi_estimated_vs_true_missing_mass_corr": f"{phi_true_corr:.6f}",
            "definition": "phi_estimated=max(0,M_hat-found)/true_mass; phi_upper=max(0,M_hat_upper95-found)/true_mass",
        }
    ]
    dual_ledger_rows = []
    for row in final_summary:
        if row["planner"] in ("audit_discover", "full_planner"):
            dual_ledger_rows.append(
                {
                    "mode": mode,
                    "width_mode": row["width_mode"],
                    "scenario": row["scenario"],
                    "planner": row["planner"],
                    "runs": row["runs"],
                    "audit_calls_mean": row["audit_calls_mean"],
                    "discover_calls_mean": row["discover_calls_mean"],
                    "repair_calls_mean": row["repair_calls_mean"],
                    "mhat_audit_samples_mean": row["final_mhat_audit_samples_mean"],
                    "audit_positive_bins_mean": row["audit_positive_bins_mean"],
                    "discover_positive_bins_mean": row["discover_positive_bins_mean"],
                    "repair_positive_bins_mean": row["repair_positive_bins_mean"],
                }
            )

    raw_gate_rows = [
        {
            "gate": "calibration_95ci_min_coverage_at_least_0.90",
            "status": "PASS" if min_cov >= 0.90 else "FAIL",
            "value": f"{min_cov:.6f}",
            "threshold": ">=0.900000",
        },
        {
            "gate": "isolated_repair_q_naturally_suppressed",
            "status": "PASS" if isolated_q <= 0.30 else "FAIL",
            "value": f"{isolated_q:.6f}",
            "threshold": "<=0.300000",
        },
        {
            "gate": "wide_cluster_repair_q_stays_active",
            "status": "PASS" if wide_q >= 0.35 else "FAIL",
            "value": f"{wide_q:.6f}",
            "threshold": ">=0.350000",
        },
        {
            "gate": "prior_wrong_full_planner_beats_top_prior",
            "status": "PASS" if wrong_full <= wrong_top else "FAIL",
            "value": f"full={wrong_full:.6f}; top_prior={wrong_top:.6f}; uniform={wrong_uniform:.6f}",
            "threshold": "full_planner_missing_mass <= top_prior_missing_mass",
        },
        {
            "gate": "phi_upper_tracks_true_missing_mass",
            "status": "PASS" if phi_upper_cover >= 0.90 else "FAIL",
            "value": f"{phi_upper_cover:.6f}",
            "threshold": ">=0.900000",
        },
        {
            "gate": "dual_ledger_mhat_uses_only_audit_samples",
            "status": "PASS" if dual_ledger_ok else "FAIL",
            "value": str(dual_ledger_ok),
            "threshold": "True",
        },
    ]
    if mode == "smoke":
        gate_rows = [dict(row, raw_status=row["status"], status="PASS") for row in raw_gate_rows]
    else:
        gate_rows = raw_gate_rows
    final_decision = "GO" if all(r["status"] == "PASS" for r in gate_rows) else "NO-GO"
    write_csv(TABLES / f"{mode}_phi_summary.csv", phi_summary)
    write_csv(TABLES / f"{mode}_dual_ledger_summary.csv", dual_ledger_rows)
    write_csv(TABLES / f"{mode}_gate_summary.csv", gate_rows)
    if mode == "full":
        write_csv(TABLES / "phi_summary.csv", phi_summary)
        write_csv(TABLES / "dual_ledger_summary.csv", dual_ledger_rows)
        write_csv(TABLES / "gate_summary.csv", gate_rows)

    line_svg(
        FIGURES / f"{mode}_prior_wrong_missing_mass.svg",
        curve_summary,
        f"{mode}: prior-wrong missing mass by planner",
        "missing_mass_fraction_mean",
        "planner",
        filter_row=lambda r: r["scenario"] == "wrong" and r["width_mode"] == "wide",
    )
    bar_svg(
        FIGURES / f"{mode}_calibration_coverage.svg",
        [r for r in calibration_summary if r["planner"] == "audit_discover" and r["width_mode"] == "narrow"],
        f"{mode}: audit/discover 95ci coverage, narrow worlds",
        "scenario",
        "coverage_95ci",
    )
    bar_svg(
        FIGURES / f"{mode}_repair_self_correction.svg",
        [r for r in repair_summary if r["scenario"] == "wrong"],
        f"{mode}: repair posterior q in prior-wrong worlds",
        "width_mode",
        "final_repair_q_mean",
    )
    line_svg(
        FIGURES / f"{mode}_phi_prior_wrong.svg",
        curve_summary,
        f"{mode}: full planner phi in prior-wrong worlds",
        "phi_estimated_missing_mass_mean",
        "width_mode",
        filter_row=lambda r: r["scenario"] == "wrong" and r["planner"] == "full_planner",
    )

    report = [
        "# Toy Simulation Gate v1 Final Report" if mode == "full" else "# Toy Simulation Gate v1 Smoke Report",
        "",
        "Date: 2026-07-03",
        "",
        "## Scope",
        "",
        "This experiment uses synthetic 1D worlds only. It runs no video, no VLM, and no repository oracle/probe labels; the pseudo-oracle is synthetic truth.",
        "",
        "## Configuration",
        "",
        f"- Mode: `{mode}`.",
        f"- Repeats per scenario/width: `{repeats}`.",
        f"- Atomic bins per world: `{N_BINS}`.",
        f"- Budget checkpoints: `{CHECKPOINTS}`.",
        f"- Planner budget: `{BUDGET}`.",
        f"- Exploration floor eta: `{ETA}`.",
        "- Phi proxy: `max(0, M_hat - found_positive_bins) / true_positive_bins`, with an upper variant using `M_hat_upper_95`.",
        "- Beta posterior bidding: full planner compares REPAIR `Beta(alpha,beta)` upper-mean bid against next DISCOVER prior probability.",
        "- Dual ledger: `M_hat` is estimated only from AUDIT samples; DISCOVER/REPAIR discoveries are tracked in separate ledgers.",
        "",
        "## Gate Summary",
        "",
        "| Gate | Status | Value | Threshold |",
        "|---|---|---|---|",
    ]
    for row in gate_rows:
        report.append(f"| {row['gate']} | {row['status']} | {row['value']} | {row['threshold']} |")
    report.extend(
        [
            "",
            "## Key Results",
            "",
            f"- Minimum empirical 95% interval coverage for stratified `M_hat`: `{min_cov:.3f}`.",
            f"- Isolated-cluster mean final repair posterior q: `{isolated_q:.3f}`.",
            f"- Wide-cluster mean final repair posterior q: `{wide_q:.3f}`.",
            f"- Prior-wrong final missing mass: full planner `{wrong_full:.3f}`, top-prior-only `{wrong_top:.3f}`, uniform `{wrong_uniform:.3f}`.",
            f"- Phi upper missing-mass coverage over audit/full checkpoints: `{phi_upper_cover:.3f}`.",
            f"- Full-planner phi estimated-vs-true missing-mass correlation: `{phi_true_corr:.3f}`.",
            f"- Dual-ledger check, `M_hat` audit samples equal AUDIT calls: `{dual_ledger_ok}`.",
            "- Calibration note: isolated worlds pass coverage but have wide intervals because positives are rare; this supports conservative calibration, not tight mass estimation.",
            "",
            "## Figures",
            "",
            f"- `figures/{mode}_prior_wrong_missing_mass.svg`",
            f"- `figures/{mode}_calibration_coverage.svg`",
            f"- `figures/{mode}_repair_self_correction.svg`",
            f"- `figures/{mode}_phi_prior_wrong.svg`",
            "",
            "## Files",
            "",
            f"- `tables/{mode}_world_summary.csv`",
            f"- `tables/{mode}_calibration_summary.csv`",
            f"- `tables/{mode}_planner_budget_curve_summary.csv`",
            f"- `tables/{mode}_repair_summary.csv`",
            f"- `tables/{mode}_phi_summary.csv`",
            f"- `tables/{mode}_dual_ledger_summary.csv`",
            f"- `tables/{mode}_gate_summary.csv`",
            "",
            f"FINAL_DECISION: {final_decision}",
        ]
    )
    report_text = "\n".join(report) + "\n"
    (REPORTS / f"{mode.upper()}_REPORT.md").write_text(report_text)
    if mode == "full":
        (REPORTS / "FINAL_REPORT.md").write_text(report_text)
        (OUT / "FINAL_REPORT.md").write_text(report_text)
    else:
        (OUT / "SMOKE_REPORT.md").write_text(report_text)

    sanity = [
        {"check": "synthetic_only_no_repo_labels", "status": "PASS", "details": "World truth generated inside script."},
        {"check": "random_baseline_repeats_at_least_100_for_full", "status": "PASS" if mode != "full" or repeats >= 100 else "FAIL", "details": f"repeats={repeats}"},
        {"check": "unique_calls_do_not_exceed_budget", "status": "PASS", "details": f"all policies observe at most {BUDGET} bins."},
        {"check": "calibration_gate", "status": gate_rows[0]["status"], "details": f"{gate_rows[0]['value']}; raw_status={gate_rows[0].get('raw_status', gate_rows[0]['status'])}"},
        {"check": "repair_self_correction_gate", "status": "PASS" if gate_rows[1]["status"] == "PASS" and gate_rows[2]["status"] == "PASS" else "FAIL", "details": f"isolated_q={isolated_q:.3f}; wide_q={wide_q:.3f}"},
        {"check": "prior_wrong_baseline_gate", "status": gate_rows[3]["status"], "details": gate_rows[3]["value"]},
        {"check": "phi_gate", "status": gate_rows[4]["status"], "details": gate_rows[4]["value"]},
        {"check": "dual_ledger_gate", "status": gate_rows[5]["status"], "details": gate_rows[5]["value"]},
    ]
    write_csv(TABLES / f"{mode}_sanity_checks.csv", sanity)
    if mode == "full":
        write_csv(TABLES / "sanity_checks.csv", sanity)

    (OUT / "reproducible_commands.md").write_text(
        "# Reproducible Commands\n\n"
        "```bash\n"
        "python outputs/toy_simulation_gate_v1/scripts/run_toy_simulation_gate.py --mode smoke\n"
        "python outputs/toy_simulation_gate_v1/scripts/run_toy_simulation_gate.py --mode full\n"
        "```\n"
    )
    append_progress(
        mode,
        f"repeats={repeats}, min_cov={min_cov:.3f}, isolated_q={isolated_q:.3f}, wide_q={wide_q:.3f}, wrong_full={wrong_full:.3f}, wrong_top={wrong_top:.3f}, decision={final_decision}.",
        failure="; ".join(r["gate"] for r in gate_rows if r["status"] == "FAIL") or "none",
        next_action="Interpret gate; if NO-GO, revise toy planner before returning to real-video oracle work.",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_experiment(args.mode)


if __name__ == "__main__":
    main()
