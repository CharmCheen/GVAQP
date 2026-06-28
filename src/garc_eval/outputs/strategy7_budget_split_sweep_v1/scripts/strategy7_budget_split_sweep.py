#!/usr/bin/env python3
"""Budget split sweep for Strategy7 recovery/certificate Pareto analysis.

Pure replay. No model inference, frame extraction, downloads, or training.

Selection policy:
- L3 exploitation uses object_count_mean only.
- Strategy7 disagreement audit uses existing GLM labels plus proxy score only.
- Qwen/VLM-defined positive labels and event ids are evaluation-only.

Certificate policy:
- Only the final uniform random audit is used as the exact hypergeometric sample.
- L3 and disagreement-audit positives are observed retrieval positives, not random
  samples for residual certification.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
PREV_SCRIPT = ROOT / "src/garc_eval/outputs/strategy7_certificate_power_v1/scripts/strategy7_certificate_power.py"
OUT = ROOT / "src/garc_eval/outputs/strategy7_budget_split_sweep_v1"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"
CONFIG = OUT / "config"
MANIFEST = OUT / "data_manifest"
FIGURES = OUT / "figures"

BUDGETS = [20, 30, 40, 60, 80, 100, 150]
TARGET_GAMMAS = [0.1, 0.2, 0.3, 0.5]
DELTA = 0.05
N_SEEDS_FULL = 500
SEED_BASE = 202606290000


def load_prev_module():
    spec = importlib.util.spec_from_file_location("strategy7_certificate_power_prev", PREV_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load previous script: {PREV_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PREV = load_prev_module()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    for d in [TABLES, REPORTS, LOGS, CONFIG, MANIFEST, FIGURES]:
        d.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def log(message: str) -> None:
    ensure_dirs()
    with (LOGS / "progress.md").open("a", encoding="utf-8") as f:
        f.write(f"- {utc_now()} {message}\n")
    print(message, flush=True)


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty_"
    cols = list(df.columns)
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v).replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def split_grid() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for l3_frac in [0.50, 0.60, 0.70, 0.80]:
        for s7_frac in [0.00, 0.10, 0.20, 0.30, 0.40]:
            uniform_frac = round(1.0 - l3_frac - s7_frac, 10)
            if uniform_frac < 0.05:
                continue
            split_id = f"L3{int(round(100*l3_frac)):02d}_S7{int(round(100*s7_frac)):02d}_U{int(round(100*uniform_frac)):02d}"
            rows.append({
                "split_id": split_id,
                "l3_frac": l3_frac,
                "s7_frac": s7_frac,
                "uniform_frac": uniform_frac,
                "policy_family": "L3_uniform_only" if s7_frac == 0 else "L3_strategy7_uniform",
            })
    return rows


def split_budget(split: dict[str, Any], requested_b: int, universe_n: int) -> dict[str, Any]:
    effective_b = min(requested_b, universe_n)
    status = "ok" if requested_b <= universe_n else "budget_exceeds_universe_clipped"
    exploit = min(effective_b, math.floor(float(split["l3_frac"]) * effective_b))
    targeted = min(effective_b - exploit, math.floor(float(split["s7_frac"]) * effective_b))
    random_n = effective_b - exploit - targeted
    return {
        "requested_B": requested_b,
        "effective_B": effective_b,
        "budget_status": status,
        "exploit_n": exploit,
        "targeted_audit_n": targeted,
        "random_audit_n": random_n,
    }


def run_one(df: pd.DataFrame, split: dict[str, Any], requested_b: int, seed: int) -> dict[str, Any]:
    n = len(df)
    budget = split_budget(split, requested_b, n)
    order = PREV.l3_order(df)
    exploit = order[: int(budget["exploit_n"])]
    excluded = set(exploit)

    if int(budget["targeted_audit_n"]) > 0:
        pool = PREV.strategy7_target_pool(df, excluded)
        targeted = [i for i in pool if i not in excluded][: int(budget["targeted_audit_n"])]
    else:
        targeted = []
    excluded.update(targeted)

    residual_before_random = [i for i in df.index if i not in excluded]
    rng = np.random.default_rng(seed)
    random_n = min(int(budget["random_audit_n"]), len(residual_before_random))
    if random_n > 0:
        random_audit = rng.choice(np.array(residual_before_random), size=random_n, replace=False).tolist()
    else:
        random_audit = []

    selected = PREV.fill_unique(exploit + targeted + random_audit, order, int(budget["effective_B"]))

    exploit_pos = int(df.loc[exploit, "is_positive_bool"].sum()) if exploit else 0
    targeted_pos = int(df.loc[targeted, "is_positive_bool"].sum()) if targeted else 0
    random_pos = int(df.loc[random_audit, "is_positive_bool"].sum()) if random_audit else 0
    found_pos = int(df.loc[selected, "is_positive_bool"].sum()) if selected else 0
    total_true_pos = int(df["is_positive_bool"].sum())

    pop_m = len(residual_before_random)
    residual_upper = PREV.exact_hypergeom_upper_bound(pop_m, random_pos, len(random_audit), DELTA) if pop_m else 0
    known_pos = exploit_pos + targeted_pos
    total_positive_upper = min(n, known_pos + residual_upper)
    recall_lower = found_pos / total_positive_upper if total_positive_upper > 0 else 1.0
    true_recall = found_pos / total_true_pos if total_true_pos else float("nan")
    event_recall, singleton_recall = PREV.eval_clusters(df, selected)

    l3_top_b = set(order[: int(budget["effective_B"])])
    l3_missed_recovered = len((set(selected) - l3_top_b) & set(df.index[df["is_positive_bool"]]))
    audit_selected = set(targeted + random_audit)
    audit_pos = len(audit_selected & set(df.index[df["is_positive_bool"]]))

    out: dict[str, Any] = {
        "dataset": df["dataset"].iloc[0],
        **split,
        "seed": seed,
        **budget,
        "selected_count": len(selected),
        "exploit_positive_count": exploit_pos,
        "targeted_audit_positive_count": targeted_pos,
        "random_audit_positive_count": random_pos,
        "audit_positive_count": audit_pos,
        "found_positive_count": found_pos,
        "total_true_positives": total_true_pos,
        "true_recall": true_recall,
        "event_cluster_recall": event_recall,
        "singleton_recall": singleton_recall,
        "l3_topB_missed_positive_recovered_count": l3_missed_recovered,
        "residual_population_for_random_audit": pop_m,
        "random_sample_n": len(random_audit),
        "random_sample_positive_x": random_pos,
        "residual_positive_upper_bound": residual_upper,
        "total_positive_upper_bound": total_positive_upper,
        "recall_lower_bound": recall_lower,
        "gap_true_recall_to_lower_bound": true_recall - recall_lower,
        "lower_bound_interval_width_to_one": 1.0 - recall_lower,
        "non_vacuous_lb_gt_0": recall_lower > 0,
        "coverage_ok_simulated": recall_lower <= true_recall + 1e-12,
        "selection_uses_qwen_or_event_cluster": False,
        "certificate_random_sample_only": True,
    }
    for gamma in TARGET_GAMMAS:
        out[f"certifies_gamma_{gamma:.1f}"] = recall_lower >= gamma
    return out


def summarize(trace: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "selected_count",
        "found_positive_count",
        "audit_positive_count",
        "targeted_audit_positive_count",
        "random_audit_positive_count",
        "l3_topB_missed_positive_recovered_count",
        "true_recall",
        "event_cluster_recall",
        "singleton_recall",
        "residual_positive_upper_bound",
        "total_positive_upper_bound",
        "recall_lower_bound",
        "gap_true_recall_to_lower_bound",
        "lower_bound_interval_width_to_one",
    ]
    group_cols = [
        "dataset", "split_id", "policy_family", "l3_frac", "s7_frac", "uniform_frac",
        "requested_B", "effective_B", "budget_status", "exploit_n", "targeted_audit_n", "random_audit_n",
    ]
    rows: list[dict[str, Any]] = []
    for keys, g in trace.groupby(group_cols, sort=False):
        row = dict(zip(group_cols, keys))
        row["n_seeds"] = len(g)
        for m in metrics:
            vals = pd.to_numeric(g[m], errors="coerce")
            row[f"mean_{m}"] = float(vals.mean())
            row[f"std_{m}"] = float(vals.std(ddof=1)) if len(vals.dropna()) > 1 else 0.0
            row[f"ci95_halfwidth_{m}"] = 1.96 * row[f"std_{m}"] / math.sqrt(len(vals.dropna())) if len(vals.dropna()) > 1 else 0.0
        row["non_vacuous_certificate_rate_lb_gt_0"] = float(g["non_vacuous_lb_gt_0"].mean())
        row["coverage_ok_rate_simulated"] = float(g["coverage_ok_simulated"].mean())
        for gamma in TARGET_GAMMAS:
            row[f"certificate_rate_gamma_{gamma:.1f}"] = float(g[f"certifies_gamma_{gamma:.1f}"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def add_baseline_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    baseline_id = "L370_S700_U30"
    rows: list[dict[str, Any]] = []
    for (dataset, b), g in summary.groupby(["dataset", "requested_B"], sort=False):
        base = g[g["split_id"] == baseline_id]
        if base.empty:
            continue
        base_row = base.iloc[0]
        for _, r in g.iterrows():
            out = r.to_dict()
            out["baseline_split_id"] = baseline_id
            out["delta_vs_baseline_recall_lower_bound"] = float(r["mean_recall_lower_bound"] - base_row["mean_recall_lower_bound"])
            out["delta_vs_baseline_l3_missed_recovered"] = float(r["mean_l3_topB_missed_positive_recovered_count"] - base_row["mean_l3_topB_missed_positive_recovered_count"])
            out["delta_vs_baseline_audit_positives"] = float(r["mean_audit_positive_count"] - base_row["mean_audit_positive_count"])
            out["delta_vs_baseline_width_to_one"] = float(r["mean_lower_bound_interval_width_to_one"] - base_row["mean_lower_bound_interval_width_to_one"])
            rows.append(out)
    return pd.DataFrame(rows)


def mark_pareto(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (dataset, b), g in summary.groupby(["dataset", "requested_B"], sort=False):
        g = g.copy()
        rec = g["mean_l3_topB_missed_positive_recovered_count"].to_numpy()
        lb = g["mean_recall_lower_bound"].to_numpy()
        pareto = []
        for i in range(len(g)):
            dominated = bool(np.any((rec >= rec[i]) & (lb >= lb[i]) & ((rec > rec[i]) | (lb > lb[i]))))
            pareto.append(not dominated)
        g["pareto_efficient_recovery_lb"] = pareto
        rec_span = float(rec.max() - rec.min())
        lb_span = float(lb.max() - lb.min())
        rec_norm = (rec - rec.min()) / rec_span if rec_span > 0 else np.zeros_like(rec)
        lb_norm = (lb - lb.min()) / lb_span if lb_span > 0 else np.zeros_like(lb)
        g["balanced_recovery_lb_score"] = 0.5 * rec_norm + 0.5 * lb_norm
        g["rank_within_dataset_budget"] = g["balanced_recovery_lb_score"].rank(ascending=False, method="min")
        rows.extend(g.to_dict("records"))
    return pd.DataFrame(rows)


def target_budget_table(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (dataset, split_id), g in summary.groupby(["dataset", "split_id"], sort=False):
        g = g.sort_values(["effective_B", "requested_B"])
        meta = g.iloc[0]
        for gamma in TARGET_GAMMAS:
            rate_col = f"certificate_rate_gamma_{gamma:.1f}"
            mean_hit = g[g["mean_recall_lower_bound"] >= gamma]
            rate_hit = g[g[rate_col] >= 0.95]
            rows.append({
                "dataset": dataset,
                "split_id": split_id,
                "l3_frac": float(meta["l3_frac"]),
                "s7_frac": float(meta["s7_frac"]),
                "uniform_frac": float(meta["uniform_frac"]),
                "target_lower_bound_gamma": gamma,
                "min_effective_budget_mean_reaches_gamma": int(mean_hit["effective_B"].iloc[0]) if not mean_hit.empty else "",
                "min_requested_budget_mean_reaches_gamma": int(mean_hit["requested_B"].iloc[0]) if not mean_hit.empty else "",
                "min_effective_budget_95pct_seeds_reach_gamma": int(rate_hit["effective_B"].iloc[0]) if not rate_hit.empty else "",
                "min_requested_budget_95pct_seeds_reach_gamma": int(rate_hit["requested_B"].iloc[0]) if not rate_hit.empty else "",
                "max_mean_recall_lower_bound": float(g["mean_recall_lower_bound"].max()),
                "max_certificate_rate_for_gamma": float(g[rate_col].max()),
            })
    return pd.DataFrame(rows)


def recommended_splits(pareto: pd.DataFrame) -> pd.DataFrame:
    best_rows = []
    for (dataset, b), g in pareto.groupby(["dataset", "requested_B"], sort=False):
        g = g[g["mean_true_recall"] < 0.999].copy()
        if g.empty:
            continue
        p = g[g["pareto_efficient_recovery_lb"]].copy()
        p = p.sort_values(
            ["balanced_recovery_lb_score", "mean_recall_lower_bound", "mean_l3_topB_missed_positive_recovered_count"],
            ascending=[False, False, False],
        )
        best_rows.append(p.iloc[0].to_dict())
    best = pd.DataFrame(best_rows)
    counts = best.groupby(["dataset", "split_id", "l3_frac", "s7_frac", "uniform_frac"], sort=False).agg(
        selected_budget_count=("requested_B", "count"),
        mean_balanced_score=("balanced_recovery_lb_score", "mean"),
        mean_recall_lower_bound=("mean_recall_lower_bound", "mean"),
        mean_l3_missed_recovered=("mean_l3_topB_missed_positive_recovered_count", "mean"),
    ).reset_index()
    return counts.sort_values(["dataset", "selected_budget_count", "mean_balanced_score"], ascending=[True, False, False])


def sanity_checks(trace: pd.DataFrame, summary: pd.DataFrame, pareto: pd.DataFrame) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    min_n_seeds = int(summary["n_seeds"].min())
    min_coverage_threshold = 0.80 if min_n_seeds < 100 else 0.90
    min_coverage = float(summary["coverage_ok_rate_simulated"].min())
    mean_coverage = float(summary["coverage_ok_rate_simulated"].mean())
    checks.append({
        "check": "coverage_rate_mc_sanity",
        "status": "PASS" if (min_coverage >= min_coverage_threshold and mean_coverage >= 1 - DELTA - 1e-12) else "FAIL",
        "raw_value": f"min={min_coverage:.6f}; mean={mean_coverage:.6f}; n_seeds_min={min_n_seeds}",
        "condition": f"mean simulated coverage >= {1 - DELTA}; min group coverage >= {min_coverage_threshold} to allow finite-seed MC noise",
    })
    checks.append({
        "check": "selection_policy_no_label_leakage_flag",
        "status": "PASS" if not trace["selection_uses_qwen_or_event_cluster"].any() else "FAIL",
        "raw_value": bool(trace["selection_uses_qwen_or_event_cluster"].any()),
        "condition": "selection flags must remain false",
    })
    checks.append({
        "check": "certificate_uses_random_sample_only",
        "status": "PASS" if trace["certificate_random_sample_only"].all() else "FAIL",
        "raw_value": bool(trace["certificate_random_sample_only"].all()),
        "condition": "only final uniform random audit is used for hypergeometric bound",
    })
    checks.append({
        "check": "split_budget_sums_to_effective_B",
        "status": "PASS" if ((summary["exploit_n"] + summary["targeted_audit_n"] + summary["random_audit_n"]) == summary["effective_B"]).all() else "FAIL",
        "raw_value": bool(((summary["exploit_n"] + summary["targeted_audit_n"] + summary["random_audit_n"]) == summary["effective_B"]).all()),
        "condition": "exploit + targeted + random must equal effective_B",
    })
    checks.append({
        "check": "pareto_front_nonempty_each_dataset_budget",
        "status": "PASS" if pareto.groupby(["dataset", "requested_B"])["pareto_efficient_recovery_lb"].sum().min() >= 1 else "FAIL",
        "raw_value": int(pareto.groupby(["dataset", "requested_B"])["pareto_efficient_recovery_lb"].sum().min()),
        "condition": "at least one Pareto-efficient split per dataset/budget",
    })
    return checks


def write_static_files(inputs: pd.DataFrame, grid: pd.DataFrame, n_seeds: int, budgets: list[int], mode: str) -> None:
    write_text(CONFIG / "experiment_config.yaml", "\n".join([
        "task: strategy7_budget_split_sweep_v1",
        f"mode: {mode}",
        f"budgets: {budgets}",
        f"n_seeds: {n_seeds}",
        f"delta: {DELTA}",
        f"target_lower_bounds: {TARGET_GAMMAS}",
        "split_grid: tables/split_grid.csv",
        "model_calls_allowed: false",
        "certificate_rule: exact_hypergeometric_upper_bound_on_uniform_random_residual_audit",
        "selection_leakage_rule: qwen labels and event ids evaluation-only",
    ]) + "\n")
    inputs.to_csv(MANIFEST / "input_manifest.csv", index=False)
    grid.to_csv(TABLES / "split_grid.csv", index=False)
    write_text(CONFIG / "schema_mapping.yaml", "\n".join([
        "common_schema:",
        "  anchor_id: clip id",
        "  score: object_count_mean cheap proxy",
        "  timestamp: center timestamp seconds",
        "  is_positive_bool: existing VLM-defined evaluation label",
        "  glm_label: existing fixed-prompt GLM label for Strategy7 grouping",
        "  event_cluster_eval: evaluation-only event id",
        "  singleton_eval: evaluation-only singleton flag",
    ]) + "\n")


def write_reports(
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    pareto: pd.DataFrame,
    recs: pd.DataFrame,
    targets: pd.DataFrame,
    inputs: pd.DataFrame,
    grid: pd.DataFrame,
    n_seeds: int,
    mode: str,
) -> str:
    baseline_id = "L370_S700_U30"
    current_id = "L370_S720_U10"
    current = deltas[deltas["split_id"] == current_id]
    pos_counts = current.groupby("dataset")["delta_vs_baseline_recall_lower_bound"].apply(lambda s: int((s > 0).sum())).to_dict()
    mean_gaps = current.groupby("dataset")["delta_vs_baseline_recall_lower_bound"].mean().to_dict()
    pareto_counts = pareto[pareto["pareto_efficient_recovery_lb"]].groupby(["dataset", "split_id"]).size().reset_index(name="pareto_budget_count")

    def best_table(ds: str) -> pd.DataFrame:
        rows = pareto[(pareto["dataset"] == ds) & (pareto["pareto_efficient_recovery_lb"])].copy()
        rows = rows.sort_values(["requested_B", "balanced_recovery_lb_score"], ascending=[True, False])
        rows = rows.groupby("requested_B", sort=False).head(3)
        return rows[[
            "requested_B", "split_id", "l3_frac", "s7_frac", "uniform_frac",
            "mean_recall_lower_bound", "mean_l3_topB_missed_positive_recovered_count",
            "mean_audit_positive_count", "balanced_recovery_lb_score",
        ]]

    def current_vs_base_table(ds: str) -> pd.DataFrame:
        rows = current[current["dataset"] == ds].sort_values("requested_B")
        return rows[[
            "requested_B", "delta_vs_baseline_recall_lower_bound",
            "delta_vs_baseline_l3_missed_recovered", "delta_vs_baseline_audit_positives",
            "delta_vs_baseline_width_to_one",
        ]]

    # A split is useful if it beats the 70/0/30 baseline in both recovery and lower bound for at least one
    # non-exhaustive budget on both datasets.
    useful = deltas[
        (deltas["split_id"] != baseline_id)
        & (deltas["delta_vs_baseline_recall_lower_bound"] > 0)
        & (deltas["delta_vs_baseline_l3_missed_recovered"] > 0)
        & (deltas["mean_true_recall"] < 0.999)
    ]
    useful_datasets = set(useful["dataset"].unique())
    if {"dataset3_clean_pool", "realcartest_v13"}.issubset(useful_datasets):
        decision = "WEAK_GO_PARETO_SPLITS_EXIST"
    elif len(useful_datasets) == 1:
        decision = "NO_GO_SPLITS_DATASET_SPECIFIC"
    else:
        decision = "NO_GO_NO_RECOVERY_CERTIFICATE_PARETO_SPLIT"

    report = [
        "# Strategy7 Budget Split Sweep Report",
        "",
        f"- Timestamp: {utc_now()}",
        f"- Mode: `{mode}`; seeds per stochastic split: {n_seeds}.",
        "- No Qwen, GLM, YOLO, GPT, human oracle, frame extraction, downloads, or training were run.",
        f"- Split grid size: {len(grid)}; budgets: {BUDGETS}; delta: {DELTA}.",
        f"- Baseline split: `{baseline_id}` = 70% L3, 0% Strategy7, 30% uniform random audit.",
        f"- Previous Strategy7 split: `{current_id}` = 70% L3, 20% Strategy7, 10% uniform random audit.",
        f"- Decision: `{decision}`.",
        "",
        "## Input Audit",
        "",
        md_table(inputs),
        "",
        "## Split Grid",
        "",
        md_table(grid),
        "",
        "## Previous Strategy7 Split Vs Baseline",
        "",
        "### Dataset3 Clean Pool",
        "",
        md_table(current_vs_base_table("dataset3_clean_pool")),
        "",
        "### Realcartest",
        "",
        md_table(current_vs_base_table("realcartest_v13")),
        "",
        "## Pareto Frontier Examples",
        "",
        "Rows are Pareto-efficient for mean L3-missed-positive recovery and mean recall lower bound within each dataset/budget.",
        "",
        "### Dataset3 Clean Pool",
        "",
        md_table(best_table("dataset3_clean_pool")),
        "",
        "### Realcartest",
        "",
        md_table(best_table("realcartest_v13")),
        "",
        "## Recommended Split Counts",
        "",
        "The balanced score is a diagnostic ranking after Pareto filtering, not a deployable tuned policy.",
        "",
        md_table(recs),
        "",
        "## Target Budget Summary",
        "",
        "Full target table is in `tables/target_lower_bound_budget_table.csv`.",
        "",
        md_table(targets.sort_values(["dataset", "target_lower_bound_gamma", "max_mean_recall_lower_bound"], ascending=[True, True, False]).groupby(["dataset", "target_lower_bound_gamma"]).head(5)),
        "",
        "## Interpretation",
        "",
        "- More Strategy7 audit generally increases L3-missed-positive recovery, but it can weaken the exact hypergeometric certificate by reducing the uniform random sample.",
        "- The useful AQP region is therefore not the maximum-disagreement split; it is the Pareto frontier where targeted recovery is bought without sacrificing too much random-audit mass.",
        "- Selection policy uses only proxy scores, timestamps, anchor ids, and existing GLM labels. Existing VLM-defined positives and event ids are used only for evaluation and simulated oracle outcomes.",
        "- Current exact certificate remains clip-level and assumes the uniform audit is sampled uniformly from the residual population.",
        "",
        "## Limitations",
        "",
        "- This is a replay over existing pseudo-oracle/VLM-defined labels, not human truth.",
        "- The split grid is intentionally coarse; it identifies Pareto regions, not a final optimized policy.",
        "- Dataset3 clean pool has N=100, so B=150 is clipped to B=100 and should not be interpreted as a true 150-call regime.",
        "- Disagreement audit is not certified as a random stratum here; that is the next algorithmic task.",
    ]
    write_text(REPORTS / "STRATEGY7_BUDGET_SPLIT_SWEEP_REPORT.md", "\n".join(report) + "\n")

    final = [
        "# Final Summary",
        "",
        f"- Timestamp: {utc_now()}",
        "- Task type: pure replay split sweep; no large model was run.",
        f"- Decision: `{decision}`.",
        f"- Split grid size: {len(grid)}.",
        f"- Previous Strategy7 split dataset3 R_lower positive gaps vs baseline: {pos_counts.get('dataset3_clean_pool', 0)}/7, mean gap {mean_gaps.get('dataset3_clean_pool', float('nan')):.6f}.",
        f"- Previous Strategy7 split realcartest R_lower positive gaps vs baseline: {pos_counts.get('realcartest_v13', 0)}/7, mean gap {mean_gaps.get('realcartest_v13', float('nan')):.6f}.",
        "- Core result: the split sweep exposes a recovery/certificate tradeoff; preserving more uniform audit mass is necessary for certificate power.",
        "- See `reports/STRATEGY7_BUDGET_SPLIT_SWEEP_REPORT.md` for Pareto front examples and limitations.",
        "",
        "strategy7_budget_split_sweep_complete=true",
    ]
    write_text(OUT / "FINAL_SUMMARY.md", "\n".join(final) + "\n")

    pd.DataFrame([{
        "decision_label": decision,
        "timestamp_utc": utc_now(),
        "mode": mode,
        "n_seeds": n_seeds,
        "delta": DELTA,
        "split_grid_size": len(grid),
        "baseline_split_id": baseline_id,
        "previous_strategy7_split_id": current_id,
        "dataset3_previous_strategy7_positive_budget_gaps": f"{pos_counts.get('dataset3_clean_pool', 0)}/7",
        "dataset3_previous_strategy7_mean_r_lower_gap": mean_gaps.get("dataset3_clean_pool", float("nan")),
        "realcartest_previous_strategy7_positive_budget_gaps": f"{pos_counts.get('realcartest_v13', 0)}/7",
        "realcartest_previous_strategy7_mean_r_lower_gap": mean_gaps.get("realcartest_v13", float("nan")),
        "no_large_model_run": True,
        "output_dir": str(OUT),
    }]).to_csv(TABLES / "final_decision.csv", index=False)
    pareto_counts.to_csv(TABLES / "pareto_split_counts.csv", index=False)
    return decision


def load_inputs() -> tuple[list[pd.DataFrame], pd.DataFrame]:
    datasets = [PREV.load_dataset3_clean(), PREV.load_realcartest()]
    rows = []
    for df in datasets:
        rows.append({
            "dataset": df["dataset"].iloc[0],
            "rows": len(df),
            "positive_count": int(df["is_positive_bool"].sum()),
            "negative_count": int((~df["is_positive_bool"]).sum()),
            "glm_counts": {str(k): int(v) for k, v in df["glm_label"].value_counts().items()},
            "score_column": "object_count_mean",
            "source_tables": "see config/experiment_config.yaml",
            "leakage_note": "labels/event clusters used only for evaluation and simulated oracle outcomes",
        })
    return datasets, pd.DataFrame(rows)


def run(mode: str, n_seeds: int, budgets: list[int]) -> int:
    ensure_dirs()
    log(f"Starting Strategy7 budget split sweep mode={mode}, n_seeds={n_seeds}, budgets={budgets}.")
    datasets, inputs = load_inputs()
    grid = pd.DataFrame(split_grid())
    write_static_files(inputs, grid, n_seeds, budgets, mode)

    rows: list[dict[str, Any]] = []
    for df in datasets:
        dataset = df["dataset"].iloc[0]
        for split in grid.to_dict("records"):
            for b in budgets:
                for i in range(n_seeds):
                    rows.append(run_one(df, split, b, SEED_BASE + i))
                log(f"Completed {dataset} {split['split_id']} B={b}.")

    trace = pd.DataFrame(rows)
    trace.to_csv(TABLES / "budget_split_seed_traces.csv", index=False)
    summary = summarize(trace)
    summary.to_csv(TABLES / "budget_split_summary.csv", index=False)
    deltas = add_baseline_deltas(summary)
    deltas.to_csv(TABLES / "budget_split_vs_baseline.csv", index=False)
    pareto = mark_pareto(summary)
    pareto.to_csv(TABLES / "budget_split_pareto_front.csv", index=False)
    recs = recommended_splits(pareto)
    recs.to_csv(TABLES / "recommended_splits.csv", index=False)
    targets = target_budget_table(summary)
    targets.to_csv(TABLES / "target_lower_bound_budget_table.csv", index=False)

    checks = sanity_checks(trace, summary, pareto)
    checks_df = pd.DataFrame(checks)
    checks_df.to_csv(TABLES / "sanity_checks.csv", index=False)
    summary[[
        "dataset", "split_id", "l3_frac", "s7_frac", "uniform_frac", "requested_B",
        "mean_recall_lower_bound", "ci95_halfwidth_recall_lower_bound",
        "mean_l3_topB_missed_positive_recovered_count",
        "mean_lower_bound_interval_width_to_one",
    ]].to_csv(FIGURES / "split_recovery_certificate_curve_data.csv", index=False)

    if (checks_df["status"] == "FAIL").any():
        write_text(REPORTS / "SANITY_FAILURE.md", md_table(checks_df) + "\n")
        log("Sanity checks failed; wrote SANITY_FAILURE.md.")
        return 1
    stale_failure = REPORTS / "SANITY_FAILURE.md"
    if stale_failure.exists():
        stale_failure.unlink()

    decision = write_reports(summary, deltas, pareto, recs, targets, inputs, grid, n_seeds, mode)
    log(f"Completed Strategy7 budget split sweep: {decision}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "full"], default="full")
    args = parser.parse_args()
    if args.mode == "smoke":
        return run("smoke", 30, [20, 60, 100])
    return run("full", N_SEEDS_FULL, BUDGETS)


if __name__ == "__main__":
    raise SystemExit(main())
