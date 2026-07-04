#!/usr/bin/env python3
"""Strict posthoc audit for toy_simulation_gate_v1.

This script does not run video, VLM, or repository labels. It reads only
synthetic output tables from toy_simulation_gate_v1 and applies stricter gates
that make metric direction, baseline coverage, bound width, repair monotonicity,
and dual-ledger scope explicit.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "toy_simulation_gate_v2"
TABLES = OUT / "tables"
FIGURES = OUT / "figures"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"

V1 = ROOT / "outputs" / "toy_simulation_gate_v1" / "tables"
CURVE_SUMMARY = V1 / "planner_budget_curve_summary.csv"
CURVE_RAW = V1 / "full_planner_budget_curves.csv"
REPAIR_SUMMARY = V1 / "repair_summary.csv"
CALIBRATION_SUMMARY = V1 / "calibration_summary.csv"
DUAL_LEDGER_SUMMARY = V1 / "dual_ledger_summary.csv"

SCENARIOS = ["strong", "weak", "wrong", "none"]
WIDTHS = ["isolated", "narrow", "wide"]
PLANNERS = ["uniform", "top_prior_only", "audit_discover", "full_planner"]
BUDGET = "160"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


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


def append_progress(result: str, failure: str = "none", fix: str = "none", next_action: str = "") -> None:
    with (LOGS / "progress.md").open("a") as f:
        f.write(f"\n## {utc_now()} - Run strict toy gate audit\n\n")
        f.write("- Checkpoint: Run strict toy gate audit\n")
        f.write("- Commands run: `python outputs/toy_simulation_gate_v2/scripts/run_strict_gate_audit.py`\n")
        f.write(f"- Result: {result}\n")
        f.write(f"- Failure: {failure}\n")
        f.write(f"- Fix applied: {fix}\n")
        if next_action:
            f.write(f"- Next action: {next_action}\n")


def mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else math.nan


def quantile(values: list[float], q: float) -> float:
    return float(np.quantile(np.array(values, dtype=float), q)) if values else math.nan


def svg_bar(path: Path, rows: list[dict], title: str, label_key: str, value_key: str, lower_is_better: bool = True) -> None:
    width, height = 920, 300
    left, right, top, bottom = 58, 20, 36, 70
    plot_w = width - left - right
    plot_h = height - top - bottom
    vals = [float(r[value_key]) for r in rows]
    max_val = max(vals) if vals else 1.0
    bar_w = plot_w / max(1, len(rows))
    color = "#2563eb" if lower_is_better else "#059669"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="23" font-family="Arial" font-size="15" fill="#111827">{title}</text>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#6b7280"/>',
    ]
    for i, row in enumerate(rows):
        val = float(row[value_key])
        h = (val / max_val) * plot_h if max_val else 0
        x = left + i * bar_w
        y = top + plot_h - h
        parts.append(f'<rect x="{x + 4:.1f}" y="{y:.1f}" width="{max(1.0, bar_w - 8):.1f}" height="{h:.1f}" fill="{color}" opacity="0.82"/>')
        parts.append(f'<text x="{x + 2:.1f}" y="{height - 42}" font-family="Arial" font-size="9" fill="#374151" transform="rotate(35 {x + 2:.1f},{height - 42})">{row[label_key]}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    curves = read_csv(CURVE_SUMMARY)
    raw = read_csv(CURVE_RAW)
    repair = read_csv(REPAIR_SUMMARY)
    calibration = read_csv(CALIBRATION_SUMMARY)
    ledger = read_csv(DUAL_LEDGER_SUMMARY)

    matrix_rows = []
    for scenario in SCENARIOS:
        for width in WIDTHS:
            row = {"scenario": scenario, "width_mode": width, "metric": "missing_mass_fraction_mean", "direction": "lower_is_better"}
            for planner in PLANNERS:
                match = [
                    r for r in curves
                    if r["scenario"] == scenario and r["width_mode"] == width and r["planner"] == planner and r["budget"] == BUDGET
                ]
                row[planner] = match[0]["missing_mass_fraction_mean"] if match else ""
            matrix_rows.append(row)

    aggregate_rows = []
    for scenario in SCENARIOS:
        for planner in PLANNERS:
            vals = [
                float(r[f"{planner}"])
                for r in matrix_rows
                if r["scenario"] == scenario and r[f"{planner}"] != ""
            ]
            aggregate_rows.append(
                {
                    "scenario": scenario,
                    "planner": planner,
                    "budget": BUDGET,
                    "missing_mass_fraction_mean_over_widths": f"{mean(vals):.6f}",
                    "direction": "lower_is_better",
                }
            )

    phi_vals = []
    for r in raw:
        if r["planner"] in ("audit_discover", "full_planner"):
            phi_true = float(r["phi_true_missing_mass"])
            phi_upper = float(r["phi_upper_missing_mass"])
            phi_est = float(r["phi_estimated_missing_mass"])
            phi_vals.append(
                {
                    "upper_minus_true": phi_upper - phi_true,
                    "abs_est_minus_true": abs(phi_est - phi_true),
                    "covered": float(phi_upper + 1e-12 >= phi_true),
                }
            )
    phi_width = [
        {
            "statistic": "phi_upper_minus_true",
            "mean": f"{mean([r['upper_minus_true'] for r in phi_vals]):.6f}",
            "p50": f"{quantile([r['upper_minus_true'] for r in phi_vals], 0.50):.6f}",
            "p90": f"{quantile([r['upper_minus_true'] for r in phi_vals], 0.90):.6f}",
            "p95": f"{quantile([r['upper_minus_true'] for r in phi_vals], 0.95):.6f}",
            "max": f"{max(r['upper_minus_true'] for r in phi_vals):.6f}",
            "direction": "lower_is_tighter",
        },
        {
            "statistic": "abs_phi_estimated_minus_true",
            "mean": f"{mean([r['abs_est_minus_true'] for r in phi_vals]):.6f}",
            "p50": f"{quantile([r['abs_est_minus_true'] for r in phi_vals], 0.50):.6f}",
            "p90": f"{quantile([r['abs_est_minus_true'] for r in phi_vals], 0.90):.6f}",
            "p95": f"{quantile([r['abs_est_minus_true'] for r in phi_vals], 0.95):.6f}",
            "max": f"{max(r['abs_est_minus_true'] for r in phi_vals):.6f}",
            "direction": "lower_is_better",
        },
    ]
    phi_coverage = mean([r["covered"] for r in phi_vals])
    phi_p50_width = float(phi_width[0]["p50"])

    repair_by_width = defaultdict(list)
    repair_rows = []
    for r in repair:
        q = float(r["final_repair_q_mean"])
        repair_by_width[r["width_mode"]].append(q)
        repair_rows.append(
            {
                "width_mode": r["width_mode"],
                "scenario": r["scenario"],
                "final_repair_q_mean": r["final_repair_q_mean"],
                "final_repair_q_std": r["final_repair_q_std"],
                "repair_hit_rate_mean": r["repair_hit_rate_mean"],
                "repair_attempts_mean": r["repair_attempts_mean"],
            }
        )
    repair_aggregate = [
        {
            "width_mode": width,
            "final_repair_q_mean_over_scenarios": f"{mean(repair_by_width[width]):.6f}",
            "direction": "should_increase_isolated_to_narrow_to_wide",
        }
        for width in WIDTHS
    ]
    agg_q = {r["width_mode"]: float(r["final_repair_q_mean_over_scenarios"]) for r in repair_aggregate}
    repair_monotonic_aggregate = agg_q["isolated"] < agg_q["narrow"] < agg_q["wide"]
    repair_monotonic_by_scenario_rows = []
    for scenario in SCENARIOS:
        vals = {
            r["width_mode"]: float(r["final_repair_q_mean"])
            for r in repair
            if r["scenario"] == scenario
        }
        ok = vals["isolated"] < vals["narrow"] < vals["wide"]
        repair_monotonic_by_scenario_rows.append(
            {
                "scenario": scenario,
                "isolated_q": f"{vals['isolated']:.6f}",
                "narrow_q": f"{vals['narrow']:.6f}",
                "wide_q": f"{vals['wide']:.6f}",
                "monotonic": str(ok),
            }
        )
    repair_monotonic_each = all(r["monotonic"] == "True" for r in repair_monotonic_by_scenario_rows)

    min_coverage = min(float(r["coverage_95ci"]) for r in calibration)
    repeats = min(int(r["runs"]) for r in calibration)
    ledger_structural_ok = all(abs(float(r["audit_calls_mean"]) - float(r["mhat_audit_samples_mean"])) < 1e-9 for r in ledger)

    def agg_value(scenario: str, planner: str) -> float:
        return float(next(r for r in aggregate_rows if r["scenario"] == scenario and r["planner"] == planner)["missing_mass_fraction_mean_over_widths"])

    strong_full_not_worse = agg_value("strong", "full_planner") <= agg_value("strong", "top_prior_only")
    prior_wrong_full_beats_top = agg_value("wrong", "full_planner") <= agg_value("wrong", "top_prior_only")
    prior_wrong_full_beats_uniform = agg_value("wrong", "full_planner") <= agg_value("wrong", "uniform")

    gate_rows = [
        {"gate": "metric_direction_explicit_missing_mass_lower_is_better", "status": "PASS", "value": "missing_mass_fraction_mean", "threshold": "documented"},
        {"gate": "full_repeats_at_least_100", "status": "PASS" if repeats >= 100 else "FAIL", "value": str(repeats), "threshold": ">=100"},
        {"gate": "mhat_min_coverage_at_least_0.90", "status": "PASS" if min_coverage >= 0.90 else "FAIL", "value": f"{min_coverage:.6f}", "threshold": ">=0.900000"},
        {"gate": "phi_upper_coverage_at_least_0.90", "status": "PASS" if phi_coverage >= 0.90 else "FAIL", "value": f"{phi_coverage:.6f}", "threshold": ">=0.900000"},
        {"gate": "phi_upper_p50_width_at_most_2.0", "status": "PASS" if phi_p50_width <= 2.0 else "FAIL", "value": f"{phi_p50_width:.6f}", "threshold": "<=2.000000"},
        {"gate": "strong_prior_full_not_worse_than_top_prior", "status": "PASS" if strong_full_not_worse else "FAIL", "value": f"full={agg_value('strong','full_planner'):.6f}; top_prior={agg_value('strong','top_prior_only'):.6f}", "threshold": "full <= top_prior"},
        {"gate": "prior_wrong_full_beats_top_prior_aggregate", "status": "PASS" if prior_wrong_full_beats_top else "FAIL", "value": f"full={agg_value('wrong','full_planner'):.6f}; top_prior={agg_value('wrong','top_prior_only'):.6f}", "threshold": "full <= top_prior"},
        {"gate": "prior_wrong_full_beats_uniform_aggregate", "status": "PASS" if prior_wrong_full_beats_uniform else "FAIL", "value": f"full={agg_value('wrong','full_planner'):.6f}; uniform={agg_value('wrong','uniform'):.6f}", "threshold": "full <= uniform"},
        {"gate": "repair_q_monotonic_by_width_aggregate", "status": "PASS" if repair_monotonic_aggregate else "FAIL", "value": f"isolated={agg_q['isolated']:.6f}; narrow={agg_q['narrow']:.6f}; wide={agg_q['wide']:.6f}", "threshold": "isolated < narrow < wide"},
        {"gate": "repair_q_monotonic_by_width_each_scenario", "status": "PASS" if repair_monotonic_each else "FAIL", "value": str(repair_monotonic_each), "threshold": "all scenarios True"},
        {"gate": "dual_ledger_structural_separation", "status": "PASS" if ledger_structural_ok else "FAIL", "value": str(ledger_structural_ok), "threshold": "mhat_audit_samples_mean == audit_calls_mean"},
    ]
    final_decision = "NO-GO" if any(r["status"] == "FAIL" for r in gate_rows) else "GO"

    write_csv(TABLES / "budget160_missing_mass_matrix.csv", matrix_rows)
    write_csv(TABLES / "scenario_planner_aggregate.csv", aggregate_rows)
    write_csv(TABLES / "phi_bound_width_summary.csv", phi_width)
    write_csv(TABLES / "repair_q_by_width_scenario.csv", repair_rows)
    write_csv(TABLES / "repair_q_width_aggregate.csv", repair_aggregate)
    write_csv(TABLES / "repair_q_monotonic_by_scenario.csv", repair_monotonic_by_scenario_rows)
    write_csv(TABLES / "dual_ledger_scope.csv", ledger)
    write_csv(TABLES / "strict_gate_summary.csv", gate_rows)
    write_csv(TABLES / "sanity_checks.csv", gate_rows)

    prior_wrong_fig_rows = [
        {"label": f"{r['width_mode']}_{planner}", "missing_mass": r[planner]}
        for r in matrix_rows if r["scenario"] == "wrong"
        for planner in ("uniform", "top_prior_only", "full_planner")
    ]
    svg_bar(FIGURES / "prior_wrong_missing_mass_matrix.svg", prior_wrong_fig_rows, "Prior-wrong missing mass at budget 160 (lower is better)", "label", "missing_mass")
    strong_fig_rows = [
        {"label": f"{r['width_mode']}_{planner}", "missing_mass": r[planner]}
        for r in matrix_rows if r["scenario"] == "strong"
        for planner in ("top_prior_only", "full_planner")
    ]
    svg_bar(FIGURES / "strong_prior_regression.svg", strong_fig_rows, "Strong-prior regression: full vs top-prior (lower is better)", "label", "missing_mass")
    svg_bar(FIGURES / "repair_q_width_aggregate.svg", repair_aggregate, "Repair posterior q by width (higher means repair stays active)", "width_mode", "final_repair_q_mean_over_scenarios", lower_is_better=False)

    report = [
        "# Toy Simulation Gate v2 Strict Audit",
        "",
        "Date: 2026-07-03",
        "",
        "## Scope",
        "",
        "This is a strict posthoc audit of `toy_simulation_gate_v1`. It reads synthetic v1 CSV outputs only; it runs no video, VLM, repository oracle labels, or probe data.",
        "",
        "## Metric Direction",
        "",
        "`missing_mass_fraction_mean = 1 - found_positive_bins / true_positive_bins`; lower is better. The prior-wrong numbers in v1 are missing mass, not discovered mass.",
        "",
        "## Strict Gate Summary",
        "",
        "| Gate | Status | Value | Threshold |",
        "|---|---|---|---|",
    ]
    for row in gate_rows:
        report.append(f"| {row['gate']} | {row['status']} | {row['value']} | {row['threshold']} |")
    report.extend(
        [
            "",
            "## Key Findings",
            "",
            f"- Full repeats per calibration cell: `{repeats}`.",
            f"- Prior-wrong aggregate missing mass: full `{agg_value('wrong','full_planner'):.6f}`, top-prior `{agg_value('wrong','top_prior_only'):.6f}`, uniform `{agg_value('wrong','uniform'):.6f}`.",
            f"- Strong-prior aggregate missing mass: full `{agg_value('strong','full_planner'):.6f}`, top-prior `{agg_value('strong','top_prior_only'):.6f}`.",
            f"- Phi upper coverage: `{phi_coverage:.6f}`, but p50 `phi_upper - phi_true` is `{phi_p50_width:.6f}`.",
            f"- Repair aggregate q: isolated `{agg_q['isolated']:.6f}`, narrow `{agg_q['narrow']:.6f}`, wide `{agg_q['wide']:.6f}`.",
            f"- Repair monotonic in every scenario: `{repair_monotonic_each}`.",
            f"- Dual-ledger check is structural: `{ledger_structural_ok}`; it does not prove tight statistical validity.",
            "",
            "## Interpretation",
            "",
            "The prior-wrong direction is resolved: full planner improves over top-prior in aggregate because the metric is remaining missing mass. However, the stricter audit fails because strong-prior cases regress, Phi upper bounds are too loose to guide stopping, and repair monotonicity is not clean in every scenario.",
            "",
            "## Files",
            "",
            "- `tables/budget160_missing_mass_matrix.csv`",
            "- `tables/scenario_planner_aggregate.csv`",
            "- `tables/phi_bound_width_summary.csv`",
            "- `tables/repair_q_by_width_scenario.csv`",
            "- `tables/repair_q_monotonic_by_scenario.csv`",
            "- `tables/strict_gate_summary.csv`",
            "- `figures/prior_wrong_missing_mass_matrix.svg`",
            "- `figures/strong_prior_regression.svg`",
            "- `figures/repair_q_width_aggregate.svg`",
            "",
            f"FINAL_DECISION: {final_decision}",
        ]
    )
    report_text = "\n".join(report) + "\n"
    (REPORTS / "FINAL_REPORT.md").write_text(report_text)
    (OUT / "FINAL_REPORT.md").write_text(report_text)
    (OUT / "reproducible_commands.md").write_text(
        "# Reproducible Commands\n\n```bash\npython outputs/toy_simulation_gate_v2/scripts/run_strict_gate_audit.py\n```\n"
    )
    append_progress(
        f"strict gates={sum(r['status']=='PASS' for r in gate_rows)}/{len(gate_rows)} PASS; final_decision={final_decision}.",
        failure="; ".join(r["gate"] for r in gate_rows if r["status"] == "FAIL") or "none",
        next_action="Design v3 adaptive planner before any real-video oracle investment.",
    )
    if final_decision == "NO-GO":
        raise SystemExit("Strict toy gate audit failed; see FINAL_REPORT.md")


if __name__ == "__main__":
    main()
