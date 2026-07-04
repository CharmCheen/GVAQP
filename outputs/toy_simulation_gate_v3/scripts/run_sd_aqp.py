#!/usr/bin/env python3
"""Run SD-AQP synthetic search.

No video, no VLM, no repository oracle/probe labels. Synthetic truth is used as
the pseudo-oracle inside generated toy worlds.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "toy_simulation_gate_v3"
TABLES = OUT / "tables"
FIGURES = OUT / "figures"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"

SCENARIOS = ["strong", "weak", "wrong", "none"]
WIDTHS = ["isolated", "narrow", "wide"]
PLANNERS = ["uniform", "top_prior_only", "v1_full_planner", "sd_aqp"]
CHECKPOINTS = [20, 40, 80, 120, 160]
BUDGET = 160
TRUST_PROBE_CALLS = 40
TRUST_HIT_RATE_THRESHOLD = 0.05
POST_SWITCH_AUDIT_FRACTION = 0.25
ETA = 0.08


def load_v1():
    path = ROOT / "outputs" / "toy_simulation_gate_v1" / "scripts" / "run_toy_simulation_gate.py"
    spec = importlib.util.spec_from_file_location("toy_v1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V1 = load_v1()


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


def append_progress(mode: str, result: str, failure: str = "none", next_action: str = "") -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "progress.md").open("a") as f:
        f.write(f"\n## {utc_now()} - Run SD-AQP ({mode})\n\n")
        f.write(f"- Checkpoint: Run SD-AQP ({mode})\n")
        f.write(f"- Commands run: `python outputs/toy_simulation_gate_v3/scripts/run_sd_aqp.py --mode {mode}`\n")
        f.write(f"- Result: {result}\n")
        f.write(f"- Failure: {failure}\n")
        f.write("- Fix applied: none\n")
        if next_action:
            f.write(f"- Next action: {next_action}\n")


def select_audit_index(rng, observed, audit_samples, strata, prefer_top: bool = False):
    best_sid = None
    best_score = -1.0
    for sid, idxs in enumerate(strata):
        available = idxs[~observed[idxs]]
        if len(available) == 0:
            continue
        n = len(audit_samples.get(sid, []))
        priority = len(idxs) / math.sqrt(n + 1.0)
        if prefer_top:
            priority *= 1.0 + sid / max(1, len(strata) - 1)
        if priority > best_score:
            best_score = priority
            best_sid = sid
    if best_sid is None:
        return None, None
    candidates = strata[best_sid][~observed[strata[best_sid]]]
    return int(rng.choice(candidates)), best_sid


def run_sd_aqp_policy(world, rng):
    n_bins = V1.N_BINS
    observed = np.zeros(n_bins, dtype=bool)
    found_positive = np.zeros(n_bins, dtype=bool)
    strata = V1.make_strata(world.score)
    audit_samples = defaultdict(list)
    repair_pool = set()
    repair_a = 1.0
    repair_b = 1.0
    audit_calls = discover_calls = repair_calls = 0
    audit_positive = discover_positive = repair_positive = 0
    repair_attempts = repair_hits = 0
    top_order = list(np.argsort(world.score)[::-1])
    top_cursor = 0
    mode = "probe"
    curves = []

    def next_top():
        nonlocal top_cursor
        while top_cursor < len(top_order) and observed[top_order[top_cursor]]:
            top_cursor += 1
        return int(top_order[top_cursor]) if top_cursor < len(top_order) else None

    def observe(idx, action, sid=None):
        nonlocal audit_calls, discover_calls, repair_calls, audit_positive, discover_positive, repair_positive
        nonlocal repair_attempts, repair_hits, repair_a, repair_b
        observed[idx] = True
        is_pos = bool(world.truth[idx])
        if is_pos:
            found_positive[idx] = True
            V1.add_repair_candidates(idx, observed, repair_pool)
        if action == "AUDIT":
            audit_calls += 1
            if sid is not None:
                audit_samples[sid].append(idx)
            if is_pos:
                audit_positive += 1
        elif action == "DISCOVER":
            discover_calls += 1
            if is_pos:
                discover_positive += 1
        elif action == "REPAIR":
            repair_calls += 1
            repair_attempts += 1
            if is_pos:
                repair_positive += 1
                repair_hits += 1
                repair_a += 1.0
            else:
                repair_b += 1.0

    for step in range(1, BUDGET + 1):
        if step <= TRUST_PROBE_CALLS:
            idx = next_top()
            if idx is not None:
                observe(idx, "DISCOVER")
        else:
            if mode == "probe":
                hit_rate = discover_positive / max(1, discover_calls)
                mode = "trust_prior" if hit_rate >= TRUST_HIT_RATE_THRESHOLD else "override_prior"
            if mode == "trust_prior":
                idx = next_top()
                if idx is not None:
                    observe(idx, "DISCOVER")
            else:
                target_audit = TRUST_PROBE_CALLS * 0 + int(math.ceil(POST_SWITCH_AUDIT_FRACTION * (step - TRUST_PROBE_CALLS)))
                use_audit = audit_calls < target_audit or rng.random() < ETA
                if use_audit:
                    idx, sid = select_audit_index(rng, observed, audit_samples, strata, prefer_top=False)
                    if idx is not None:
                        observe(idx, "AUDIT", sid)
                else:
                    repair_idx = V1.choose_repair_candidate(repair_pool, observed, list(np.flatnonzero(found_positive)))
                    if repair_idx is not None:
                        mean = repair_a / (repair_a + repair_b)
                        var = (repair_a * repair_b) / (((repair_a + repair_b) ** 2) * (repair_a + repair_b + 1.0))
                        repair_bid = min(1.0, mean + math.sqrt(var))
                        top_idx = next_top()
                        discover_bid = float(world.prior_prob[top_idx]) if top_idx is not None else -1.0
                        if repair_bid >= discover_bid:
                            repair_pool.discard(repair_idx)
                            observe(repair_idx, "REPAIR")
                        elif top_idx is not None:
                            observe(top_idx, "DISCOVER")
                    else:
                        idx = next_top()
                        if idx is not None:
                            observe(idx, "DISCOVER")
        if step in CHECKPOINTS:
            true_mass = int(world.truth.sum())
            found = int(found_positive.sum())
            est = V1.stratified_estimate(world.truth, audit_samples, strata)
            denom = max(1, true_mass)
            curves.append(
                {
                    "budget": step,
                    "found_positive_bins": found,
                    "true_positive_bins": true_mass,
                    "missing_mass_fraction": max(0, true_mass - found) / denom,
                    "audit_calls": audit_calls,
                    "discover_calls": discover_calls,
                    "repair_calls": repair_calls,
                    "audit_positive_bins": audit_positive,
                    "discover_positive_bins": discover_positive,
                    "repair_positive_bins": repair_positive,
                    "mhat_total": est["mhat_total"],
                    "mhat_upper_95": est["mhat_upper_95"],
                    "mhat_covered_95": est["covered_95"],
                    "phi_estimated_missing_mass": max(0.0, est["mhat_total"] - found) / denom,
                    "phi_upper_missing_mass": max(0.0, est["mhat_upper_95"] - found) / denom,
                    "phi_true_missing_mass": max(0, true_mass - found) / denom,
                    "mode": mode,
                }
            )
    final_est = V1.stratified_estimate(world.truth, audit_samples, strata)
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
        "audit_positive_bins": audit_positive,
        "discover_positive_bins": discover_positive,
        "repair_positive_bins": repair_positive,
        "found_positive_bins": int(found_positive.sum()),
        "true_positive_bins": int(world.truth.sum()),
        "final_mode": mode,
    }


def aggregate(rows, keys, value_cols):
    grouped = defaultdict(list)
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
        return_rows = out
        return_rows.append(item)
    return out


def svg_bar(path, rows, title, label_key, value_key):
    width, height = 900, 300
    left, right, top, bottom = 58, 20, 34, 72
    plot_w = width - left - right
    plot_h = height - top - bottom
    vals = [float(r[value_key]) for r in rows]
    max_val = max(vals) if vals else 1.0
    bar_w = plot_w / max(1, len(rows))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="22" font-family="Arial" font-size="15" fill="#111827">{title}</text>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#6b7280"/>',
    ]
    for i, row in enumerate(rows):
        val = float(row[value_key])
        h = (val / max_val) * plot_h if max_val else 0.0
        x = left + i * bar_w
        y = top + plot_h - h
        parts.append(f'<rect x="{x+4:.1f}" y="{y:.1f}" width="{max(1, bar_w-8):.1f}" height="{h:.1f}" fill="#2563eb" opacity="0.82"/>')
        parts.append(f'<text x="{x+2:.1f}" y="{height-43}" font-family="Arial" font-size="9" fill="#374151" transform="rotate(35 {x+2:.1f},{height-43})">{row[label_key]}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def run(mode: str):
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    repeats = 120 if mode == "full" else 8
    rng = np.random.default_rng(20260713 if mode == "full" else 20260714)
    world_rows = []
    curve_rows = []
    final_rows = []
    repair_rows = []

    for width in WIDTHS:
        for scenario in SCENARIOS:
            for rep in range(repeats):
                world_seed = int(rng.integers(0, 2**31 - 1))
                world = V1.generate_world(np.random.default_rng(world_seed), width, scenario)
                world_rows.append({"mode": mode, "width_mode": width, "scenario": scenario, "rep": rep, "world_seed": world_seed, "true_positive_bins": int(world.truth.sum())})
                for planner in PLANNERS:
                    policy_seed = int(rng.integers(0, 2**31 - 1))
                    prng = np.random.default_rng(policy_seed)
                    if planner == "sd_aqp":
                        result = run_sd_aqp_policy(world, prng)
                    elif planner == "v1_full_planner":
                        result = V1.run_policy(world, "full_planner", prng)
                    else:
                        result = V1.run_policy(world, planner, prng)
                    for curve in result["curves"]:
                        row = {"mode": mode, "width_mode": width, "scenario": scenario, "rep": rep, "planner": planner, **curve}
                        curve_rows.append(row)
                    final_rows.append(
                        {
                            "mode": mode,
                            "width_mode": width,
                            "scenario": scenario,
                            "rep": rep,
                            "planner": planner,
                            "found_positive_bins": result["found_positive_bins"],
                            "true_positive_bins": result["true_positive_bins"],
                            "missing_mass_fraction": 1.0 - result["found_positive_bins"] / max(1, result["true_positive_bins"]),
                            "audit_calls": result["audit_calls"],
                            "discover_calls": result["discover_calls"],
                            "repair_calls": result["repair_calls"],
                            "repair_attempts": result["repair_attempts"],
                            "repair_hit_rate": result["repair_hit_rate"],
                            "final_repair_q": result["final_repair_q"],
                            "final_mode_trust_prior": 1 if result.get("final_mode") == "trust_prior" else 0,
                            "final_mode_override_prior": 1 if result.get("final_mode") == "override_prior" else 0,
                        }
                    )
                    if planner == "sd_aqp":
                        repair_rows.append(
                            {
                                "mode": mode,
                                "width_mode": width,
                                "scenario": scenario,
                                "rep": rep,
                                "repair_attempts": result["repair_attempts"],
                                "repair_hit_rate": result["repair_hit_rate"],
                                "final_repair_q": result["final_repair_q"],
                            }
                        )

    curve_summary = aggregate(
        curve_rows,
        ["mode", "width_mode", "scenario", "planner", "budget"],
        ["missing_mass_fraction", "found_positive_bins", "audit_calls", "discover_calls", "repair_calls", "phi_upper_missing_mass", "phi_true_missing_mass"],
    )
    final_summary = aggregate(
        final_rows,
        ["mode", "width_mode", "scenario", "planner"],
        ["missing_mass_fraction", "found_positive_bins", "audit_calls", "discover_calls", "repair_calls", "repair_attempts", "repair_hit_rate", "final_repair_q", "final_mode_trust_prior", "final_mode_override_prior"],
    )
    repair_summary = aggregate(repair_rows, ["mode", "width_mode", "scenario"], ["repair_attempts", "repair_hit_rate", "final_repair_q"])

    write_csv(TABLES / f"{mode}_world_summary.csv", world_rows)
    write_csv(TABLES / f"{mode}_planner_budget_curves.csv", curve_rows)
    write_csv(TABLES / f"{mode}_planner_budget_curve_summary.csv", curve_summary)
    write_csv(TABLES / f"{mode}_final_planner_summary.csv", final_summary)
    write_csv(TABLES / f"{mode}_repair_summary.csv", repair_summary)

    if mode == "full":
        write_csv(TABLES / "world_summary.csv", world_rows)
        write_csv(TABLES / "planner_budget_curves.csv", curve_rows)
        write_csv(TABLES / "planner_budget_curve_summary.csv", curve_summary)
        write_csv(TABLES / "final_planner_summary.csv", final_summary)
        write_csv(TABLES / "repair_summary.csv", repair_summary)

    def lookup(scenario, width, planner):
        rows = [r for r in curve_summary if r["scenario"] == scenario and r["width_mode"] == width and r["planner"] == planner and int(r["budget"]) == BUDGET]
        return float(rows[0]["missing_mass_fraction_mean"]) if rows else math.nan

    matrix = []
    for scenario in SCENARIOS:
        for width in WIDTHS:
            row = {"scenario": scenario, "width_mode": width, "metric": "missing_mass_fraction_mean", "direction": "lower_is_better"}
            for planner in PLANNERS:
                row[planner] = f"{lookup(scenario, width, planner):.6f}"
            matrix.append(row)
    write_csv(TABLES / f"{mode}_budget160_missing_mass_matrix.csv", matrix)
    if mode == "full":
        write_csv(TABLES / "budget160_missing_mass_matrix.csv", matrix)

    def agg(scenario, planner):
        return float(np.mean([lookup(scenario, width, planner) for width in WIDTHS]))

    repair_by_width = defaultdict(list)
    for r in repair_summary:
        repair_by_width[r["width_mode"]].append(float(r["final_repair_q_mean"]))
    repair_agg = {w: float(np.mean(repair_by_width[w])) if repair_by_width[w] else math.nan for w in WIDTHS}

    strong_ok = agg("strong", "sd_aqp") <= agg("strong", "top_prior_only") + 0.02
    wrong_top_ok = agg("wrong", "sd_aqp") <= agg("wrong", "top_prior_only")
    wrong_uniform_ok = agg("wrong", "sd_aqp") <= agg("wrong", "uniform")
    repair_agg_ok = repair_agg["isolated"] < repair_agg["narrow"] < repair_agg["wide"]
    gate_rows = [
        {"gate": "full_repeats_at_least_100", "status": "PASS" if mode != "full" or repeats >= 100 else "FAIL", "value": str(repeats), "threshold": ">=100"},
        {"gate": "strong_prior_sd_aqp_not_worse_than_top_prior_plus_0.02", "status": "PASS" if strong_ok else "FAIL", "value": f"sd_aqp={agg('strong','sd_aqp'):.6f}; top_prior={agg('strong','top_prior_only'):.6f}", "threshold": "sd_aqp <= top_prior + 0.02"},
        {"gate": "prior_wrong_sd_aqp_beats_top_prior", "status": "PASS" if wrong_top_ok else "FAIL", "value": f"sd_aqp={agg('wrong','sd_aqp'):.6f}; top_prior={agg('wrong','top_prior_only'):.6f}", "threshold": "sd_aqp <= top_prior"},
        {"gate": "prior_wrong_sd_aqp_beats_uniform", "status": "PASS" if wrong_uniform_ok else "FAIL", "value": f"sd_aqp={agg('wrong','sd_aqp'):.6f}; uniform={agg('wrong','uniform'):.6f}", "threshold": "sd_aqp <= uniform"},
        {"gate": "repair_q_monotonic_by_width_aggregate", "status": "PASS" if repair_agg_ok else "FAIL", "value": f"isolated={repair_agg['isolated']:.6f}; narrow={repair_agg['narrow']:.6f}; wide={repair_agg['wide']:.6f}", "threshold": "isolated < narrow < wide"},
    ]
    decision = "GO" if all(r["status"] == "PASS" for r in gate_rows) else "NO-GO"
    write_csv(TABLES / f"{mode}_gate_summary.csv", gate_rows)
    if mode == "full":
        write_csv(TABLES / "gate_summary.csv", gate_rows)
        write_csv(TABLES / "sanity_checks.csv", gate_rows)

    fig_rows = []
    for row in matrix:
        if row["scenario"] in ("strong", "wrong"):
            for planner in ("uniform", "top_prior_only", "v1_full_planner", "sd_aqp"):
                fig_rows.append({"label": f"{row['scenario']}_{row['width_mode']}_{planner}", "missing": row[planner]})
    svg_bar(FIGURES / f"{mode}_strong_wrong_missing_mass.svg", fig_rows, f"{mode}: strong/wrong missing mass at B=160", "label", "missing")

    report = [
        "# SD-AQP Synthetic Search v3",
        "",
        "Date: 2026-07-03",
        "",
        "## Scope",
        "",
        "Synthetic-only algorithm search. No video, VLM, repository oracle labels, or probe data.",
        "",
        "## Algorithm",
        "",
        "SD-AQP first probes the high-prior ranking through DISCOVER calls. If early hit rate is high, it trusts the prior and continues top-prior selection. If low, it switches to AUDIT plus Beta-gated REPAIR. `M_hat` remains audit-ledger only.",
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
            "## Scenario Aggregates",
            "",
            f"- Strong prior missing mass: SD-AQP `{agg('strong','sd_aqp'):.3f}`, top-prior `{agg('strong','top_prior_only'):.3f}`, v1 full `{agg('strong','v1_full_planner'):.3f}`.",
            f"- Prior-wrong missing mass: SD-AQP `{agg('wrong','sd_aqp'):.3f}`, top-prior `{agg('wrong','top_prior_only'):.3f}`, uniform `{agg('wrong','uniform'):.3f}`, v1 full `{agg('wrong','v1_full_planner'):.3f}`.",
            f"- Repair q aggregate: isolated `{repair_agg['isolated']:.3f}`, narrow `{repair_agg['narrow']:.3f}`, wide `{repair_agg['wide']:.3f}`.",
            "",
            "## Files",
            "",
            f"- `tables/{mode}_budget160_missing_mass_matrix.csv`",
            f"- `tables/{mode}_planner_budget_curve_summary.csv`",
            f"- `tables/{mode}_final_planner_summary.csv`",
            f"- `tables/{mode}_gate_summary.csv`",
            f"- `figures/{mode}_strong_wrong_missing_mass.svg`",
            "",
            f"FINAL_DECISION: {decision}",
        ]
    )
    report_text = "\n".join(report) + "\n"
    (REPORTS / f"{mode.upper()}_REPORT.md").write_text(report_text)
    if mode == "full":
        (REPORTS / "FINAL_REPORT.md").write_text(report_text)
        (OUT / "FINAL_REPORT.md").write_text(report_text)
    else:
        (OUT / "SMOKE_REPORT.md").write_text(report_text)
    (OUT / "reproducible_commands.md").write_text(
        "# Reproducible Commands\n\n```bash\npython outputs/toy_simulation_gate_v3/scripts/run_sd_aqp.py --mode smoke\npython outputs/toy_simulation_gate_v3/scripts/run_sd_aqp.py --mode full\n```\n"
    )
    append_progress(mode, f"decision={decision}; strong_sd={agg('strong','sd_aqp'):.3f}; wrong_sd={agg('wrong','sd_aqp'):.3f}.", failure="; ".join(r["gate"] for r in gate_rows if r["status"] == "FAIL") or "none", next_action="If NO-GO, inspect matrix and revise policy.")
    if mode == "full" and decision == "NO-GO":
        raise SystemExit("SD-AQP v3 strict gates failed")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args().mode)
