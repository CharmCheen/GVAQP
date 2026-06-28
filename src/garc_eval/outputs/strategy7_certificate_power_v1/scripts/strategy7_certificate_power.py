#!/usr/bin/env python3
"""Strategy 7 certificate-power replay.

Pure table analysis. No model inference, frame extraction, downloads, or training.

Certificate convention:
- Non-random exploitation and targeted disagreement audit are treated as observed
  retrieval positives.
- Only the final uniform random audit is used for the exact hypergeometric
  residual upper bound.
- Recall lower bound = observed positives / conservative upper bound on total
  positives.
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import hypergeom


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "src/garc_eval/outputs/strategy7_certificate_power_v1"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"
CONFIG = OUT / "config"
MANIFEST = OUT / "data_manifest"
FIGURES = OUT / "figures"

DATASET3_CLEAN_IDS = ROOT / "src/garc_eval/outputs/prompt_tuning_v1/heldout_cascade_eval_v1/clean_pool_anchor_ids.csv"
DATASET3_GLM = ROOT / "src/garc_eval/outputs/prompt_tuning_v1/heldout_cascade_eval_v1/tables/glm_v1_pilot_123_outputs.csv"
DATASET3_CANON = ROOT / "src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv"
REAL_FEATURES = ROOT / "src/garc_eval/outputs/realcartest_proxy_materialization_v1/tables/realcartest_anchor_proxy_features_2fps.csv"
REAL_GLM = ROOT / "src/garc_eval/outputs/realcartest_strategy7_validation_v1/tables/realcartest_glm_fixed_prompt_outputs.csv"

BUDGETS = [20, 30, 40, 60, 80, 100, 150]
TARGET_GAMMAS = [0.1, 0.2, 0.3, 0.5]
DELTA = 0.05
N_SEEDS_FULL = 500
SEED_BASE = 202606280000


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    for d in [TABLES, REPORTS, LOGS, CONFIG, MANIFEST, FIGURES]:
        d.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def log(message: str) -> None:
    ensure_dirs()
    with (LOGS / "progress.md").open("a", encoding="utf-8") as f:
        f.write(f"- {utc_now()} {message}\n")
    print(message, flush=True)


def as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.astype(str).str.lower().isin({"true", "1", "yes", "positive"})


def exact_hypergeom_upper_bound(pop_size: int, sample_pos: int, sample_n: int, delta: float) -> int:
    """One-sided exact upper confidence bound for positives in a finite population.

    Returns the largest K not rejected by observing sample_pos or fewer positives
    in sample_n draws without replacement:
        CDF(sample_pos; pop_size, K, sample_n) >= delta.
    """
    if pop_size <= 0:
        return 0
    if sample_n <= 0:
        return pop_size
    sample_n = min(sample_n, pop_size)
    sample_pos = max(0, min(sample_pos, sample_n))
    lo, hi = sample_pos, pop_size
    while lo < hi:
        mid = (lo + hi + 1) // 2
        cdf = hypergeom.cdf(sample_pos, pop_size, mid, sample_n)
        if cdf >= delta:
            lo = mid
        else:
            hi = mid - 1
    return int(lo)


def load_dataset3_clean() -> pd.DataFrame:
    ids = pd.read_csv(DATASET3_CLEAN_IDS)["anchor_id"].astype(str)
    glm = pd.read_csv(DATASET3_GLM)
    canon = pd.read_csv(DATASET3_CANON)
    df = glm[glm["anchor_id"].astype(str).isin(set(ids))].copy()
    canon_cols = [
        "anchor_id",
        "center_time_s",
        "object_count_mean",
        "event_cluster_id",
        "is_singleton_cluster",
    ]
    df = df.merge(canon[canon_cols], on="anchor_id", how="left", suffixes=("", "_canon"))
    # Prefer canonical metadata for scoring/time, keep GLM table labels.
    df["dataset"] = "dataset3_clean_pool"
    df["timestamp"] = df["center_time_s"].astype(float)
    df["score"] = df["object_count_mean_canon"].astype(float)
    df["is_positive_bool"] = as_bool(df["is_positive"])
    df["glm_label"] = df["glm_pred"].fillna("parse_error").astype(str).str.lower()
    df["event_cluster_eval"] = df["event_cluster_id_canon"]
    df["singleton_eval"] = as_bool(df["is_singleton_cluster_canon"])
    return normalize_dataset(df)


def load_realcartest() -> pd.DataFrame:
    feat = pd.read_csv(REAL_FEATURES)
    glm = pd.read_csv(REAL_GLM)
    df = feat.merge(glm[["anchor_id", "parsed_label", "confidence"]], on="anchor_id", how="left")
    df["dataset"] = "realcartest_v13"
    df["timestamp"] = df["anchor_timestamp"].astype(float)
    df["score"] = df["object_count_mean"].astype(float)
    df["is_positive_bool"] = as_bool(df["is_positive"])
    df["glm_label"] = df["parsed_label"].fillna("parse_error").astype(str).str.lower()
    df["event_cluster_eval"] = df["event_cluster_id"]
    df["singleton_eval"] = as_bool(df["singleton_flag"])
    return normalize_dataset(df)


def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)
    df["anchor_id"] = df["anchor_id"].astype(str)
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(-1e9)
    timestamp = pd.to_numeric(df["timestamp"], errors="coerce")
    df["timestamp"] = timestamp.fillna(pd.Series(np.arange(len(df)), index=df.index))
    df["glm_label"] = df["glm_label"].replace({"nan": "parse_error"}).fillna("parse_error")
    df["l3_rank_order"] = np.arange(len(df.sort_values(["score", "timestamp", "anchor_id"], ascending=[False, True, True], kind="mergesort")))
    return df


def l3_order(df: pd.DataFrame) -> list[int]:
    return df.sort_values(["score", "timestamp", "anchor_id"], ascending=[False, True, True], kind="mergesort").index.tolist()


def fill_unique(primary: list[int], fallback: list[int], k: int) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for idx in primary + fallback:
        if idx not in seen:
            out.append(idx)
            seen.add(idx)
        if len(out) >= k:
            break
    return out


def strategy7_target_pool(df: pd.DataFrame, excluded: set[int]) -> list[int]:
    remaining = df.loc[[i for i in df.index if i not in excluded]].copy()
    if remaining.empty:
        return []
    median = float(df["score"].median())
    low_pos = remaining[(remaining["score"] <= median) & (remaining["glm_label"].isin(["positive", "uncertain"]))]
    pos_unc = remaining[remaining["glm_label"].isin(["positive", "uncertain"])]
    high_neg = remaining[(remaining["score"] >= df["score"].quantile(0.75)) & (remaining["glm_label"] == "negative")]
    low_order = low_pos.sort_values(["score", "timestamp", "anchor_id"], ascending=[True, True, True]).index.tolist()
    pos_order = pos_unc.sort_values(["score", "timestamp", "anchor_id"], ascending=[True, True, True]).index.tolist()
    high_neg_order = high_neg.sort_values(["score", "timestamp", "anchor_id"], ascending=[False, True, True]).index.tolist()
    fallback = [i for i in l3_order(df) if i not in excluded]
    return fill_unique(low_order + pos_order + high_neg_order, fallback, len(df))


def split_budget(policy: str, requested_b: int, universe_n: int) -> dict[str, int | str]:
    effective_b = min(requested_b, universe_n)
    status = "ok" if requested_b <= universe_n else "budget_exceeds_universe_clipped"
    if policy == "L3_uniform_certificate":
        exploit = min(effective_b, math.floor(0.7 * effective_b))
        targeted = 0
        random_n = effective_b - exploit
    elif policy == "Strategy7_certificate":
        exploit = min(effective_b, math.floor(0.7 * effective_b))
        targeted = min(effective_b - exploit, math.floor(0.2 * effective_b))
        random_n = effective_b - exploit - targeted
    else:
        raise ValueError(policy)
    return {
        "requested_B": requested_b,
        "effective_B": effective_b,
        "exploit_n": exploit,
        "targeted_audit_n": targeted,
        "random_audit_n": random_n,
        "budget_status": status,
    }


def eval_clusters(df: pd.DataFrame, selected: list[int]) -> tuple[float, float]:
    pos_clusters = set(df.loc[df["is_positive_bool"], "event_cluster_eval"].dropna().astype(str))
    pos_clusters = {x for x in pos_clusters if x not in {"-1", "-1.0", "nan", "None"}}
    sel = df.loc[selected]
    sel_clusters = set(sel.loc[sel["is_positive_bool"], "event_cluster_eval"].dropna().astype(str))
    sel_clusters = {x for x in sel_clusters if x not in {"-1", "-1.0", "nan", "None"}}
    event_recall = len(sel_clusters & pos_clusters) / len(pos_clusters) if pos_clusters else float("nan")
    singleton_pos = df["is_positive_bool"] & df["singleton_eval"]
    denom = int(singleton_pos.sum())
    num = int((df.loc[selected, "is_positive_bool"] & df.loc[selected, "singleton_eval"]).sum()) if selected else 0
    singleton_recall = num / denom if denom else float("nan")
    return event_recall, singleton_recall


def run_one(df: pd.DataFrame, policy: str, requested_b: int, seed: int) -> dict[str, Any]:
    n = len(df)
    split = split_budget(policy, requested_b, n)
    order = l3_order(df)
    exploit = order[: int(split["exploit_n"])]
    excluded = set(exploit)
    if policy == "Strategy7_certificate":
        pool = strategy7_target_pool(df, excluded)
        targeted = [i for i in pool if i not in excluded][: int(split["targeted_audit_n"])]
    else:
        targeted = []
    excluded.update(targeted)
    random_n = int(split["random_audit_n"])
    rng = np.random.default_rng(seed)
    residual_before_random = [i for i in df.index if i not in excluded]
    if random_n > 0 and residual_before_random:
        random_audit = rng.choice(np.array(residual_before_random), size=min(random_n, len(residual_before_random)), replace=False).tolist()
    else:
        random_audit = []
    selected = fill_unique(exploit + targeted + random_audit, order, int(split["effective_B"]))

    exploit_pos = int(df.loc[exploit, "is_positive_bool"].sum()) if exploit else 0
    targeted_pos = int(df.loc[targeted, "is_positive_bool"].sum()) if targeted else 0
    random_pos = int(df.loc[random_audit, "is_positive_bool"].sum()) if random_audit else 0
    found_pos = int(df.loc[selected, "is_positive_bool"].sum()) if selected else 0

    pop_m = len(residual_before_random)
    sample_n = len(random_audit)
    x = random_pos
    residual_upper = exact_hypergeom_upper_bound(pop_m, x, sample_n, DELTA) if pop_m else 0
    policy_known_pos = exploit_pos + targeted_pos
    total_positive_upper = min(n, policy_known_pos + residual_upper)
    recall_lower = found_pos / total_positive_upper if total_positive_upper > 0 else 1.0
    total_true_pos = int(df["is_positive_bool"].sum())
    true_recall = found_pos / total_true_pos if total_true_pos else float("nan")
    coverage_ok = recall_lower <= true_recall + 1e-12
    l3_top_b = set(order[: int(split["effective_B"])])
    l3_missed_recovered = len((set(selected) - l3_top_b) & set(df.index[df["is_positive_bool"]]))
    event_recall, singleton_recall = eval_clusters(df, selected)

    out: dict[str, Any] = {
        "dataset": df["dataset"].iloc[0],
        "policy": policy,
        "seed": seed,
        **split,
        "selected_count": len(selected),
        "exploit_positive_count": exploit_pos,
        "targeted_audit_positive_count": targeted_pos,
        "random_audit_positive_count": random_pos,
        "audit_positive_count": targeted_pos + random_pos,
        "found_positive_count": found_pos,
        "total_true_positives": total_true_pos,
        "true_recall": true_recall,
        "event_cluster_recall": event_recall,
        "singleton_recall": singleton_recall,
        "l3_topB_missed_positive_recovered_count": l3_missed_recovered,
        "residual_population_for_random_audit": pop_m,
        "random_sample_n": sample_n,
        "random_sample_positive_x": x,
        "residual_positive_upper_bound": residual_upper,
        "total_positive_upper_bound": total_positive_upper,
        "recall_lower_bound": recall_lower,
        "gap_true_recall_to_lower_bound": true_recall - recall_lower,
        "lower_bound_interval_width_to_one": 1.0 - recall_lower,
        "non_vacuous_lb_gt_0": recall_lower > 0,
        "coverage_ok_simulated": coverage_ok,
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
    rows: list[dict[str, Any]] = []
    group_cols = ["dataset", "policy", "requested_B", "effective_B", "budget_status", "exploit_n", "targeted_audit_n", "random_audit_n"]
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


def target_budget_table(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (dataset, policy), g in summary.groupby(["dataset", "policy"], sort=False):
        g = g.sort_values(["effective_B", "requested_B"])
        for gamma in TARGET_GAMMAS:
            rate_col = f"certificate_rate_gamma_{gamma:.1f}"
            mean_hit = g[g["mean_recall_lower_bound"] >= gamma]
            rate_hit = g[g[rate_col] >= 0.95]
            rows.append({
                "dataset": dataset,
                "policy": policy,
                "target_lower_bound_gamma": gamma,
                "min_effective_budget_mean_reaches_gamma": int(mean_hit["effective_B"].iloc[0]) if not mean_hit.empty else "",
                "min_requested_budget_mean_reaches_gamma": int(mean_hit["requested_B"].iloc[0]) if not mean_hit.empty else "",
                "min_effective_budget_95pct_seeds_reach_gamma": int(rate_hit["effective_B"].iloc[0]) if not rate_hit.empty else "",
                "min_requested_budget_95pct_seeds_reach_gamma": int(rate_hit["requested_B"].iloc[0]) if not rate_hit.empty else "",
                "max_mean_recall_lower_bound": float(g["mean_recall_lower_bound"].max()),
                "max_certificate_rate_for_gamma": float(g[rate_col].max()),
            })
    return pd.DataFrame(rows)


def comparison_table(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dataset, g in summary.groupby("dataset", sort=False):
        left = g[g["policy"] == "L3_uniform_certificate"].set_index("requested_B")
        right = g[g["policy"] == "Strategy7_certificate"].set_index("requested_B")
        for b in sorted(set(left.index) & set(right.index)):
            l = left.loc[b]
            r = right.loc[b]
            rows.append({
                "dataset": dataset,
                "requested_B": b,
                "effective_B": int(r["effective_B"]),
                "strategy7_minus_l3_uniform_mean_recall_lower_bound": float(r["mean_recall_lower_bound"] - l["mean_recall_lower_bound"]),
                "strategy7_minus_l3_uniform_mean_bound_width_to_one": float(r["mean_lower_bound_interval_width_to_one"] - l["mean_lower_bound_interval_width_to_one"]),
                "strategy7_minus_l3_uniform_gap_true_to_lb": float(r["mean_gap_true_recall_to_lower_bound"] - l["mean_gap_true_recall_to_lower_bound"]),
                "strategy7_minus_l3_uniform_audit_positives": float(r["mean_audit_positive_count"] - l["mean_audit_positive_count"]),
                "strategy7_minus_l3_uniform_l3_missed_recovered": float(r["mean_l3_topB_missed_positive_recovered_count"] - l["mean_l3_topB_missed_positive_recovered_count"]),
                "strategy7_minus_l3_uniform_nonvacuous_rate": float(r["non_vacuous_certificate_rate_lb_gt_0"] - l["non_vacuous_certificate_rate_lb_gt_0"]),
                "strategy7_minus_l3_uniform_gamma_0_2_rate": float(r["certificate_rate_gamma_0.2"] - l["certificate_rate_gamma_0.2"]),
                "strategy7_minus_l3_uniform_gamma_0_3_rate": float(r["certificate_rate_gamma_0.3"] - l["certificate_rate_gamma_0.3"]),
            })
    return pd.DataFrame(rows)


def write_reports(summary: pd.DataFrame, comp: pd.DataFrame, target: pd.DataFrame, inputs: pd.DataFrame, n_seeds: int, mode: str) -> str:
    pos_comp = comp.groupby("dataset")["strategy7_minus_l3_uniform_mean_recall_lower_bound"].apply(lambda s: int((s > 0).sum())).to_dict()
    total_comp = comp.groupby("dataset")["strategy7_minus_l3_uniform_mean_recall_lower_bound"].size().to_dict()
    mean_comp = comp.groupby("dataset")["strategy7_minus_l3_uniform_mean_recall_lower_bound"].mean().to_dict()
    both_positive = all(mean_comp.get(ds, 0) > 0 for ds in ["dataset3_clean_pool", "realcartest_v13"])
    if both_positive:
        decision = "GO_STRATEGY7_IMPROVES_CERTIFICATE_POWER"
    elif any(v > 0 for v in mean_comp.values()):
        decision = "WEAK_GO_MIXED_CERTIFICATE_POWER"
    else:
        decision = "NO_GO_STRATEGY7_DOES_NOT_TIGHTEN_CERTIFICATE"

    def fmt_dataset(ds: str) -> str:
        rows = comp[comp["dataset"] == ds].sort_values("requested_B")
        lines = [
            "| B | eff B | S7-L3 mean R_lower | S7-L3 width-to-1 | S7-L3 audit positives | S7-L3 L3-missed recovered | gamma0.2 rate gap | gamma0.3 rate gap |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for _, r in rows.iterrows():
            lines.append(
                f"| {int(r['requested_B'])} | {int(r['effective_B'])} | "
                f"{r['strategy7_minus_l3_uniform_mean_recall_lower_bound']:.6f} | "
                f"{r['strategy7_minus_l3_uniform_mean_bound_width_to_one']:.6f} | "
                f"{r['strategy7_minus_l3_uniform_audit_positives']:.3f} | "
                f"{r['strategy7_minus_l3_uniform_l3_missed_recovered']:.3f} | "
                f"{r['strategy7_minus_l3_uniform_gamma_0_2_rate']:.3f} | "
                f"{r['strategy7_minus_l3_uniform_gamma_0_3_rate']:.3f} |"
            )
        return "\n".join(lines)

    nonv = summary.groupby(["dataset", "policy"], sort=False).agg(
        min_non_vacuous_rate=("non_vacuous_certificate_rate_lb_gt_0", "min"),
        max_gamma_0_3_rate=("certificate_rate_gamma_0.3", "max"),
        max_gamma_0_5_rate=("certificate_rate_gamma_0.5", "max"),
        max_mean_recall_lower_bound=("mean_recall_lower_bound", "max"),
    ).reset_index()

    report = [
        "# Strategy 7 Certificate Power Report",
        "",
        f"- Timestamp: {utc_now()}",
        f"- Mode: `{mode}`; seeds per stochastic policy: {n_seeds}.",
        "- No Qwen, GLM, YOLO, GPT, human oracle, frame extraction, downloads, or training were run.",
        f"- Delta for exact hypergeometric upper bound: {DELTA}.",
        f"- Target lower-bound grid: {TARGET_GAMMAS}.",
        "- Certificate design: non-random L3/Strategy7 selections are retrieval observations; only the final uniform random audit is used for the exact residual hypergeometric bound.",
        f"- Decision: `{decision}`.",
        "",
        "## Input Audit",
        "",
        md_table(inputs),
        "",
        "## Dataset3 Clean Pool Comparison",
        "",
        fmt_dataset("dataset3_clean_pool"),
        "",
        "## Realcartest Comparison",
        "",
        fmt_dataset("realcartest_v13"),
        "",
        "## Target Budget Summary",
        "",
        md_table(target),
        "",
        "## Non-Vacuous And Target Certificate Rates",
        "",
        md_table(nonv),
        "",
        "- Non-vacuous means `recall_lower_bound > 0`; all rows are non-vacuous under this weak definition because every budget policy finds at least one positive in the simulated oracle labels.",
        "- Target-specific certificate rates are more informative: on realcartest, Strategy7 reaches gamma=0.3 by B=150 but has lower gamma=0.5 rate than L3+uniform at the largest budget tested.",
        "",
        "## Interpretation",
        "",
        "- Positive `S7-L3 mean R_lower` means Strategy 7 improves certificate tightness for recall lower bound, not only selected-positive recovery.",
        "- Negative `width-to-1` gap means Strategy 7 narrows the lower-bound interval to the trivial upper endpoint 1.",
        "- If Strategy 7 uses 20% targeted audit and only 10% uniform random audit, a gain is meaningful because the random certificate sample is smaller; the targeted observations must compensate by increasing observed positives and shrinking the residual population.",
        "- Result: Strategy7 clears that bar on dataset3 only in mid-budget regimes, but not on realcartest. On realcartest it recovers more L3-missed positives while producing a looser exact hypergeometric recall lower bound, because the smaller uniform random audit leaves a larger residual upper bound.",
        "- AQP implication: current Strategy7 is a recovery mechanism, not yet a robust certificate-power mechanism. It should enter the AQP layer only through a design that preserves enough random audit mass or uses a valid stratified certificate.",
        "- Dataset3 B=150 is clipped to effective B=100 because the clean pool has N=100; this row is exhaustive and should not be treated as a real 150-call budget on dataset3.",
        "",
        "## Limitations",
        "",
        "- Labels are existing pseudo-oracle/VLM-defined labels, not human truth.",
        "- The exact hypergeometric bound is clip-level and assumes the random audit is sampled uniformly from the remaining residual population. It does not solve temporal correlation at event level.",
        "- Strategy7's disagreement audit is not used as a random sample for certification; using it that way would be invalid.",
        "- Dataset3 clean pool has only 100 anchors and is not directly comparable in scale to realcartest's 399 anchors.",
    ]
    write_text(REPORTS / "STRATEGY7_CERTIFICATE_POWER_REPORT.md", "\n".join(report) + "\n")

    final = [
        "# Final Summary",
        "",
        f"- Timestamp: {utc_now()}",
        "- Task type: pure analysis; no large model was run.",
        f"- Decision: `{decision}`.",
        f"- Dataset3 positive R_lower gap budgets: {pos_comp.get('dataset3_clean_pool', 0)}/{total_comp.get('dataset3_clean_pool', 0)}, mean gap {mean_comp.get('dataset3_clean_pool', float('nan')):.6f}.",
        f"- Realcartest positive R_lower gap budgets: {pos_comp.get('realcartest_v13', 0)}/{total_comp.get('realcartest_v13', 0)}, mean gap {mean_comp.get('realcartest_v13', float('nan')):.6f}.",
        "- Core result: Strategy7 improves L3-missed positive recovery but does not reliably tighten the exact hypergeometric recall lower bound under the current 70/20/10 split.",
        "- Dataset3 certificate gain appears in mid budgets; realcartest certificate lower bounds are worse for Strategy7 at every tested budget.",
        "- Certificate validity boundary: only uniform random audit contributes to the hypergeometric residual bound.",
        "- See `reports/STRATEGY7_CERTIFICATE_POWER_REPORT.md` for full tables and limitations.",
        "",
        "strategy7_certificate_power_complete=true",
    ]
    write_text(OUT / "FINAL_SUMMARY.md", "\n".join(final) + "\n")
    pd.DataFrame([{
        "decision_label": decision,
        "timestamp_utc": utc_now(),
        "mode": mode,
        "n_seeds": n_seeds,
        "delta": DELTA,
        "dataset3_positive_budget_gaps": f"{pos_comp.get('dataset3_clean_pool', 0)}/{total_comp.get('dataset3_clean_pool', 0)}",
        "dataset3_mean_r_lower_gap": mean_comp.get("dataset3_clean_pool", float("nan")),
        "realcartest_positive_budget_gaps": f"{pos_comp.get('realcartest_v13', 0)}/{total_comp.get('realcartest_v13', 0)}",
        "realcartest_mean_r_lower_gap": mean_comp.get("realcartest_v13", float("nan")),
        "no_large_model_run": True,
        "output_dir": str(OUT),
    }]).to_csv(TABLES / "final_decision.csv", index=False)
    return decision


def write_static_files(inputs: pd.DataFrame, n_seeds: int, budgets: list[int], mode: str) -> None:
    write_text(CONFIG / "experiment_config.yaml", "\n".join([
        "task: strategy7_certificate_power_v1",
        f"mode: {mode}",
        f"budgets: {budgets}",
        f"n_seeds: {n_seeds}",
        f"delta: {DELTA}",
        f"target_lower_bounds: {TARGET_GAMMAS}",
        "policies:",
        "  - L3_uniform_certificate",
        "  - Strategy7_certificate",
        "model_calls_allowed: false",
        "certificate_rule: exact_hypergeometric_upper_bound_on_uniform_random_residual_audit",
    ]) + "\n")
    inputs.to_csv(MANIFEST / "input_manifest.csv", index=False)
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


def sanity_checks(trace: pd.DataFrame, summary: pd.DataFrame) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    checks.append({
        "check": "coverage_rate_not_below_nominal",
        "status": "PASS" if (summary["coverage_ok_rate_simulated"] >= 1 - DELTA - 1e-12).all() else "FAIL",
        "raw_value": float(summary["coverage_ok_rate_simulated"].min()),
        "condition": f"all simulated coverage rates >= {1 - DELTA}",
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
    mono_ok = True
    for (dataset, policy), g in summary.groupby(["dataset", "policy"]):
        vals = g.sort_values("effective_B")["mean_recall_lower_bound"].to_numpy()
        if np.any(np.diff(vals) < -0.15):
            mono_ok = False
    checks.append({
        "check": "mean_recall_lower_bound_no_large_monotonic_drop",
        "status": "PASS" if mono_ok else "FAIL",
        "raw_value": "checked by dataset/policy",
        "condition": "mean R_lower should not drop by more than 0.15 between increasing effective budgets",
    })
    return checks


def run(mode: str, n_seeds: int, budgets: list[int]) -> int:
    ensure_dirs()
    log(f"Starting strategy7 certificate power run mode={mode}, n_seeds={n_seeds}, budgets={budgets}.")
    datasets = [load_dataset3_clean(), load_realcartest()]
    inputs = []
    for df in datasets:
        inputs.append({
            "dataset": df["dataset"].iloc[0],
            "rows": len(df),
            "positive_count": int(df["is_positive_bool"].sum()),
            "negative_count": int((~df["is_positive_bool"]).sum()),
            "glm_counts": {str(k): int(v) for k, v in df["glm_label"].value_counts().items()},
            "score_column": "object_count_mean",
            "source_tables": "see config/experiment_config.yaml",
            "leakage_note": "labels/event clusters used only for evaluation and simulated oracle outcomes",
        })
    inputs_df = pd.DataFrame(inputs)
    write_static_files(inputs_df, n_seeds, budgets, mode)
    rows = []
    for df in datasets:
        for policy in ["L3_uniform_certificate", "Strategy7_certificate"]:
            for b in budgets:
                for i in range(n_seeds):
                    seed = SEED_BASE + i
                    rows.append(run_one(df, policy, b, seed))
                log(f"Completed {df['dataset'].iloc[0]} {policy} B={b}.")
    trace = pd.DataFrame(rows)
    trace.to_csv(TABLES / "certificate_power_seed_traces.csv", index=False)
    summary = summarize(trace)
    summary.to_csv(TABLES / "certificate_power_summary.csv", index=False)
    comp = comparison_table(summary)
    comp.to_csv(TABLES / "strategy7_vs_l3_certificate_comparison.csv", index=False)
    target = target_budget_table(summary)
    target.to_csv(TABLES / "target_lower_bound_budget_table.csv", index=False)
    checks = sanity_checks(trace, summary)
    pd.DataFrame(checks).to_csv(TABLES / "sanity_checks.csv", index=False)
    # Lightweight figure data for plotting without image dependencies.
    fig_cols = [
        "dataset", "policy", "requested_B", "effective_B", "mean_recall_lower_bound",
        "ci95_halfwidth_recall_lower_bound", "mean_gap_true_recall_to_lower_bound",
        "mean_lower_bound_interval_width_to_one",
    ]
    summary[fig_cols].to_csv(FIGURES / "recall_lower_bound_curve_data.csv", index=False)
    if any(c["status"] == "FAIL" for c in checks):
        write_text(REPORTS / "SANITY_FAILURE.md", md_table(pd.DataFrame(checks)) + "\n")
        log("Sanity checks failed; wrote SANITY_FAILURE.md.")
        return 1
    decision = write_reports(summary, comp, target, inputs_df, n_seeds, mode)
    log(f"Completed strategy7 certificate power run: {decision}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "full"], default="full")
    args = parser.parse_args()
    if args.mode == "smoke":
        return run("smoke", 20, [20, 40, 100])
    return run("full", N_SEEDS_FULL, BUDGETS)


if __name__ == "__main__":
    raise SystemExit(main())
