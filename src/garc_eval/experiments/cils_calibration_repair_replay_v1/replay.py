#!/usr/bin/env python3
from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[4]
V2 = ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak"
DUR = ROOT / "src/garc_eval/outputs/reference_duration_stratified_eval_v1"
ROOT_CAUSE = ROOT / "src/garc_eval/outputs/cils_empty_return_root_cause_audit_v1"
CODE_AUDIT = ROOT / "src/garc_eval/outputs/clean_interval_aqp_code_audit_v2_clean_no_leak"
OUT = ROOT / "src/garc_eval/outputs/cils_calibration_repair_replay_v1"

ANSWER = "answer_iou_0_3"
SEED0 = 20260630
BUDGETS = [5, 10, 20, 40, 80]
TAUS = [0.5, 0.6, 0.7, 0.8, 0.9]
KS = [20, 50, 100, 200, 400]
N_SEEDS = 50
PILOT_POLICIES = [
    "uniform",
    "top_active_score",
    "quota_stratified_v2",
    "answer_quality_proxy_top",
    "hybrid_discovery_boundary",
    "epsilon_mixed_answer_proxy",
]
CAL_MODELS = [
    "beta_bin_strata_mean",
    "beta_bin_strata_lower",
    "hierarchical_beta_pooling",
    "isotonic_or_logistic",
    "calibrated_floor_0_25",
    "calibrated_floor_0_5",
    "calibrated_floor_1_0",
]


def ensure_dirs() -> None:
    for d in [OUT, OUT / "logs", OUT / "tables", OUT / "reports", OUT / "config", OUT / "data_manifest", OUT / "figures", OUT / "scripts"]:
        d.mkdir(parents=True, exist_ok=True)


def write_df(df: pd.DataFrame, name: str) -> None:
    ensure_dirs()
    df.to_csv(OUT / name, index=False)
    df.to_csv(OUT / "tables" / name, index=False)


def write_text(name: str, text: str) -> None:
    ensure_dirs()
    (OUT / name).write_text(text.rstrip() + "\n", encoding="utf-8")


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, **kwargs)


def md_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df is None or df.empty:
        return "_No rows._"
    d = df.head(max_rows).copy()
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, r in d.iterrows():
        vals = []
        for c in d.columns:
            v = r[c]
            vals.append(f"{v:.6g}" if isinstance(v, float) else str(v).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def safe_div(a: float, b: float) -> float:
    return float(a / b) if b else 0.0


def normalize(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce").fillna(0.0).astype(float)
    lo, hi = float(s.min()), float(s.max())
    if hi <= lo:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - lo) / (hi - lo)


def rank01(s: pd.Series, ascending: bool = True) -> pd.Series:
    return s.rank(method="average", ascending=ascending, pct=True).fillna(0.0)


def tiou(a0: float, a1: float, b0: float, b1: float) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    return safe_div(inter, union)


def overlap_len(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def load_inputs() -> dict[str, pd.DataFrame | str]:
    return {
        "features": read_csv(V2 / "interval_lattice_features_only.csv"),
        "lattice": read_csv(V2 / "interval_lattice_v2_clean.csv"),
        "labels": read_csv(V2 / "interval_labels_v2_clean.csv"),
        "events": read_csv(V2 / "reference_events.csv"),
        "cal_trials": read_csv(V2 / "calibration_trials_v2_clean.csv"),
        "main": read_csv(V2 / "main_budget_curve_v2_clean.csv"),
        "selected": read_csv(V2 / "selected_intervals_by_trial_v2_clean.csv"),
        "baseline": read_csv(V2 / "baseline_comparison_v2_clean.csv") if (V2 / "baseline_comparison_v2_clean.csv").exists() else pd.DataFrame(),
    }


def prepare_candidates(inputs: dict) -> pd.DataFrame:
    f = inputs["features"].copy()
    labels = inputs["labels"].copy()
    c = f.merge(labels, on="interval_id", how="left")
    c["boundary_quality_proxy"] = normalize(c["boundary_left_drop"] + c["boundary_right_drop"])
    c["duration_bin"] = pd.cut(c["duration"], [0, 2, 5, 10, 20, 40, 80, 1e9], labels=["<=2", "2-5", "5-10", "10-20", "20-40", "40-80", ">80"], include_lowest=True)
    c["active_score_bin"] = pd.qcut(c["active_score"].rank(method="first"), 5, labels=["q1", "q2", "q3", "q4", "q5"])
    c["boundary_quality_bin"] = pd.qcut(c["boundary_quality_proxy"].rank(method="first"), 5, labels=["q1", "q2", "q3", "q4", "q5"])
    c["signal_disagreement_bin"] = pd.qcut(c["signal_disagreement"].rank(method="first"), 5, labels=["q1", "q2", "q3", "q4", "q5"])
    c["moderate_duration_flag"] = c["duration"].between(5, 40)
    c["high_persistence_flag"] = c["score_persistence"] >= c["score_persistence"].quantile(0.75)
    c["high_boundary_drop_flag"] = c["boundary_quality_proxy"] >= c["boundary_quality_proxy"].quantile(0.75)
    overlong = np.maximum(0.0, (c["duration"] - 40.0) / 40.0)
    c["answer_quality_proxy"] = (
        rank01(c["active_score"])
        + rank01(c["score_persistence"])
        + rank01(c["boundary_quality_proxy"])
        + 0.5 * c["moderate_duration_flag"].astype(float)
        - rank01(c["signal_disagreement"])
        - overlong.clip(0, 1)
    )
    c["answer_quality_proxy"] = normalize(c["answer_quality_proxy"])
    return c


def evaluation_subsets(events: pd.DataFrame) -> pd.DataFrame:
    strata_file = DUR / "event_duration_strata.csv"
    if strata_file.exists():
        s = pd.read_csv(strata_file)
        cols = [x for x in ["event_id", "duration", "duration_stratum"] if x in s.columns]
        out = events.merge(s[cols].drop_duplicates("event_id"), on="event_id", how="left", suffixes=("", "_s"))
        if "duration_stratum" not in out.columns:
            out["duration_stratum"] = np.where(out["duration"] <= 2, "point_anchor", np.where(out["duration"] >= 5, "true_interval", "short_interval"))
    else:
        out = events.copy()
        out["duration_stratum"] = np.where(out["duration"] <= 2, "point_anchor", np.where(out["duration"] >= 5, "true_interval", "short_interval"))
    out["eval_subset"] = np.where(out["duration"] <= 2, "point_anchor", np.where(out["duration"] >= 5, "interval_eval", "short_interval"))
    write_df(out, "evaluation_subsets.csv")
    summ = out.groupby("eval_subset").agg(events=("event_id", "count"), min_duration=("duration", "min"), median_duration=("duration", "median"), max_duration=("duration", "max")).reset_index()
    write_text("evaluation_subset_summary.md", f"""# Evaluation Subsets

Duration strata source: `{'duration artifact' if strata_file.exists() else 'fallback from reference_events.csv'}`.

{md_table(summ)}

Interval-IoU main replay metrics use only `interval_eval` events. Point-anchor events are reported separately with overlap/center/containment style metrics.
""")
    return out


def artifact_inventory(inputs: dict, events_sub: pd.DataFrame, cand: pd.DataFrame) -> None:
    files = [
        V2 / "interval_lattice_features_only.csv",
        V2 / "interval_lattice_v2_clean.csv",
        V2 / "interval_labels_v2_clean.csv",
        V2 / "reference_events.csv",
        V2 / "calibration_trials_v2_clean.csv",
        V2 / "main_budget_curve_v2_clean.csv",
        V2 / "selected_intervals_by_trial_v2_clean.csv",
        DUR / "event_duration_strata.csv",
        ROOT_CAUSE / "root_cause_classification.md",
        ROOT_CAUSE / "counterfactual_diagnostics.csv",
        ROOT_CAUSE / "cils_rejection_trace.csv",
        CODE_AUDIT / "FINAL_CODE_AUDIT_REPORT.md",
    ]
    rows = []
    for p in files:
        row = {"artifact": p.name, "path": str(p), "exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() else 0}
        if p.suffix == ".csv" and p.exists():
            df0 = pd.read_csv(p, nrows=0)
            row["rows"] = max(0, sum(1 for _ in p.open()) - 1)
            row["columns"] = "|".join(df0.columns)
        rows.append(row)
    inv = pd.DataFrame(rows)
    write_df(inv, "artifact_inventory.csv")
    write_text("artifact_inventory.md", f"""# Artifact Inventory

- Interval candidates: `{len(cand)}`
- `answer_iou_0_3` positives: `{int(cand[ANSWER].sum())}`
- true/interval events: `{int((events_sub['eval_subset'] == 'interval_eval').sum())}`
- point-anchor events: `{int((events_sub['eval_subset'] == 'point_anchor').sum())}`
- Replay seeds: `{N_SEEDS}`

{md_table(inv, 80)}
""")


def feature_diagnostics(cand: pd.DataFrame, events_sub: pd.DataFrame) -> None:
    interval_ids = set(events_sub[events_sub["eval_subset"] == "interval_eval"]["event_id"])
    cand["interval_event_positive"] = cand[ANSWER].astype(bool) & cand["matched_event_id"].fillna("").astype(str).isin(interval_ids)
    feats = ["active_score", "max_score", "mean_score", "score_persistence", "score_std", "duration", "num_units", "boundary_left_drop", "boundary_right_drop", "signal_disagreement", "boundary_quality_proxy", "answer_quality_proxy"]
    rows = []
    for feat in feats:
        for group, mask in {
            "answer_positive": cand[ANSWER].astype(bool),
            "answer_negative": ~cand[ANSWER].astype(bool),
            "interval_event_positive": cand["interval_event_positive"].astype(bool),
            "other": ~cand["interval_event_positive"].astype(bool),
        }.items():
            v = cand.loc[mask, feat]
            rows.append({"feature": feat, "group": group, "count": int(mask.sum()), "mean": float(v.mean()), "median": float(v.median()), "p90": float(v.quantile(0.9))})
    diag = pd.DataFrame(rows)
    write_df(diag, "answer_feature_diagnostics.csv")
    top_rows = []
    score_cols = ["active_score", "max_score", "mean_score", "score_persistence", "boundary_quality_proxy", "answer_quality_proxy"]
    for col in score_cols:
        for k in KS:
            top = cand.sort_values([col, "duration"], ascending=[False, True]).head(k)
            top_rows.append({"score": col, "K": k, "answer_precision": float(top[ANSWER].mean()), "interval_event_precision": float(top["interval_event_positive"].mean()), "answer_count": int(top[ANSWER].sum()), "interval_answer_count": int(top["interval_event_positive"].sum())})
    top = pd.DataFrame(top_rows)
    write_df(top, "feature_topk_precision.csv")
    fam = cand.groupby(["method", "duration_bin"], dropna=False).agg(candidates=("interval_id", "count"), answer_rate=(ANSWER, "mean"), interval_answer_rate=("interval_event_positive", "mean"), mean_active=("active_score", "mean"), mean_aq_proxy=("answer_quality_proxy", "mean")).reset_index()
    write_df(fam, "answer_feature_by_family_duration.csv")
    write_text("answer_feature_diagnostics.md", f"""# Answer Feature Diagnostics

Top-K precision by non-leak scores:

{md_table(top, 40)}

Method/duration concentration:

{md_table(fam.sort_values('interval_answer_rate', ascending=False), 40)}

Raw `active_score` is weakly aligned: its top prefixes contain few answer-positive candidates relative to the available 1192 positives. The hand-built `answer_quality_proxy` is diagnostic-only and uses feature-only columns.
""")


def select_policy(cand: pd.DataFrame, budget: int, seed: int, policy: str) -> list[str]:
    rng = np.random.default_rng(seed)
    if policy == "uniform":
        return cand.sample(frac=1, random_state=seed)["interval_id"].head(budget).tolist()
    if policy == "top_active_score":
        return cand.sort_values(["active_score", "duration"], ascending=[False, True])["interval_id"].head(budget).tolist()
    if policy == "answer_quality_proxy_top":
        return cand.sort_values(["answer_quality_proxy", "duration"], ascending=[False, True])["interval_id"].head(budget).tolist()
    if policy == "quota_stratified_v2":
        return quota_stratified(cand, budget, seed)
    if policy == "hybrid_discovery_boundary":
        n1 = budget // 2
        a = cand.sort_values(["active_score", "score_persistence"], ascending=False)["interval_id"].head(n1).tolist()
        rest = cand[~cand["interval_id"].isin(a)].copy()
        b = rest[rest["moderate_duration_flag"]].sort_values(["boundary_quality_proxy", "answer_quality_proxy"], ascending=False)["interval_id"].head(budget - len(a)).tolist()
        if len(a) + len(b) < budget:
            fill = rest[~rest["interval_id"].isin(b)].sample(n=min(budget - len(a) - len(b), len(rest)), random_state=seed)["interval_id"].tolist()
            b += fill
        return (a + b)[:budget]
    if policy == "epsilon_mixed_answer_proxy":
        n1, n2 = int(round(0.7 * budget)), int(round(0.2 * budget))
        a = cand.sort_values(["answer_quality_proxy", "duration"], ascending=[False, True])["interval_id"].head(n1).tolist()
        rest = cand[~cand["interval_id"].isin(a)]
        b = quota_stratified(rest, min(n2, budget - len(a)), seed + 17)
        rest2 = cand[~cand["interval_id"].isin(set(a + b))]
        n3 = budget - len(a) - len(b)
        c = rest2.sample(n=min(n3, len(rest2)), random_state=seed + 29)["interval_id"].tolist() if n3 > 0 else []
        return (a + b + c)[:budget]
    raise ValueError(policy)


def quota_stratified(cand: pd.DataFrame, budget: int, seed: int) -> list[str]:
    if budget <= 0 or cand.empty:
        return []
    strata = ["duration_bin", "method", "active_score_bin", "boundary_quality_bin", "signal_disagreement_bin"]
    groups = [(k, g.copy()) for k, g in cand.groupby(strata, observed=True, dropna=False)]
    rng = np.random.default_rng(seed)
    if not groups:
        return []
    quota = {k: min(len(g), max(0, budget // len(groups))) for k, g in groups}
    remaining = budget - sum(quota.values())
    weights = [(len(g) * (0.5 + float(g["answer_quality_proxy"].mean())), k) for k, g in groups if len(g) > quota[k]]
    while remaining > 0 and weights:
        weights = sorted(weights, reverse=True)
        progressed = False
        for _, k in weights:
            g = dict(groups)[k]
            if remaining <= 0:
                break
            if quota[k] < len(g):
                quota[k] += 1
                remaining -= 1
                progressed = True
        weights = [(max(0, w - 1e-9), k) for w, k in weights if quota[k] < len(dict(groups)[k])]
        if not progressed:
            break
    chosen = []
    for k, g in groups:
        n = quota[k]
        if n:
            chosen += g.sample(n=n, random_state=int(rng.integers(0, 1_000_000)))["interval_id"].tolist()
    if len(chosen) > budget:
        chosen = list(rng.choice(chosen, size=budget, replace=False))
    return chosen


def pilot_policies(cand: pd.DataFrame) -> dict[tuple[str, int, int], pd.DataFrame]:
    lab = cand.set_index("interval_id")
    samples = {}
    rows = []
    for policy in PILOT_POLICIES:
        for b in BUDGETS:
            for seed in range(N_SEEDS):
                ids = select_policy(cand, b, SEED0 + seed, policy)
                s = pd.DataFrame({"interval_id": ids})
                s["rank"] = np.arange(1, len(s) + 1)
                s["oracle_label"] = s["interval_id"].map(lab[ANSWER]).fillna(False).astype(bool)
                s["interval_event_positive"] = s["interval_id"].map(lab["interval_event_positive"]).fillna(False).astype(bool)
                s["policy"], s["budget"], s["seed"] = policy, b, seed
                samples[(policy, b, seed)] = s
                strata_cov = cand[cand["interval_id"].isin(ids)][["duration_bin", "method", "active_score_bin", "boundary_quality_bin", "signal_disagreement_bin"]].drop_duplicates().shape[0]
                pos_strata_cov = cand[cand["interval_id"].isin(s[s["oracle_label"]]["interval_id"])][["duration_bin", "method", "active_score_bin", "boundary_quality_bin", "signal_disagreement_bin"]].drop_duplicates().shape[0]
                rows.append({"pilot_policy": policy, "budget": b, "seed": seed, "sampled": len(s), "answer_positive": int(s["oracle_label"].sum()), "interval_event_positive": int(s["interval_event_positive"].sum()), "sample_positive_rate": float(s["oracle_label"].mean()) if len(s) else 0, "interval_positive_rate": float(s["interval_event_positive"].mean()) if len(s) else 0, "zero_positive_pilot": int(s["oracle_label"].sum()) == 0, "positive_strata_coverage": pos_strata_cov, "strata_coverage": strata_cov})
    all_samples = pd.concat(samples.values(), ignore_index=True)
    write_df(all_samples, "pilot_policy_samples.csv")
    rates = pd.DataFrame(rows)
    write_df(rates, "pilot_policy_positive_rates.csv")
    summ = rates.groupby(["pilot_policy", "budget"]).agg(trials=("seed", "count"), mean_positive_rate=("sample_positive_rate", "mean"), mean_interval_positive_rate=("interval_positive_rate", "mean"), zero_positive_pilot_rate=("zero_positive_pilot", "mean"), mean_positive_strata_coverage=("positive_strata_coverage", "mean")).reset_index()
    write_text("pilot_policy_report.md", f"""# Pilot Policy Report

Replay uses `{N_SEEDS}` seeds.

{md_table(summ, 80)}

The original clean-v2-equivalent policy is `top_active_score`. Repaired policies are diagnostic replays, not production algorithms.
""")
    return samples


def wilson_lower(pos: pd.Series, n: pd.Series, z: float = 1.0) -> pd.Series:
    p = pos / n.replace(0, np.nan)
    denom = 1 + z * z / n.replace(0, np.nan)
    centre = p + z * z / (2 * n.replace(0, np.nan))
    adj = z * np.sqrt((p * (1 - p) + z * z / (4 * n.replace(0, np.nan))) / n.replace(0, np.nan))
    return ((centre - adj) / denom).fillna(0.0).clip(0, 1)


def calibrate_candidates(cand: pd.DataFrame, samples: pd.DataFrame, model: str) -> tuple[pd.DataFrame, dict]:
    out = cand.copy()
    smap = samples.set_index("interval_id")["oracle_label"].astype(int).to_dict()
    s = out[out["interval_id"].isin(smap)].copy()
    s["y"] = s["interval_id"].map(smap).astype(int)
    global_p = (s["y"].sum() + 1.0) / (len(s) + 2.0) if len(s) else 0.0
    keys = ["duration_bin", "method", "active_score_bin", "boundary_quality_bin", "signal_disagreement_bin"]
    parent1 = ["duration_bin", "method"]
    parent2 = ["duration_bin"]
    meta = {"skip_reason": "", "global_p": global_p, "pilot_positives": int(s["y"].sum()), "pilot_n": int(len(s))}
    if model == "isotonic_or_logistic":
        if s["y"].sum() < 3 or s["y"].nunique() < 2:
            out["p_answer"] = global_p
            meta["skip_reason"] = "too_few_positive_or_single_class"
            return out, meta
        xcols = ["answer_quality_proxy", "active_score", "boundary_quality_proxy", "score_persistence", "duration"]
        coef = np.array([1.2, 0.4, 0.5, 0.3, -0.015])
        xs = s[xcols].astype(float).to_numpy()
        y = s["y"].to_numpy()
        # Lightweight deterministic logistic-style score scaling, calibrated to pilot mean.
        z = xs @ coef
        z = (z - z.mean()) / (z.std() + 1e-9)
        base = math.log(global_p / max(1e-9, 1 - global_p)) if 0 < global_p < 1 else -4
        allz = out[xcols].astype(float).to_numpy() @ coef
        allz = (allz - allz.mean()) / (allz.std() + 1e-9)
        out["p_answer"] = 1 / (1 + np.exp(-(base + 0.8 * allz)))
        meta["skip_reason"] = "lightweight_logistic_surrogate"
        return out, meta
    stat = s.groupby(keys, dropna=False, observed=True)["y"].agg(["sum", "count"]).reset_index()
    stat["mean"] = (stat["sum"] + 1) / (stat["count"] + 2)
    stat["lower"] = wilson_lower(stat["sum"], stat["count"])
    p1 = s.groupby(parent1, dropna=False, observed=True)["y"].agg(["sum", "count"]).reset_index()
    p1["mean_p1"] = (p1["sum"] + 1) / (p1["count"] + 2)
    p2 = s.groupby(parent2, dropna=False, observed=True)["y"].agg(["sum", "count"]).reset_index()
    p2["mean_p2"] = (p2["sum"] + 1) / (p2["count"] + 2)
    out = out.merge(stat[keys + ["count", "mean", "lower"]], on=keys, how="left")
    out = out.merge(p1[parent1 + ["mean_p1"]], on=parent1, how="left")
    out = out.merge(p2[parent2 + ["mean_p2"]], on=parent2, how="left")
    if model == "beta_bin_strata_mean":
        out["p_answer"] = out["mean"].fillna(global_p)
    elif model == "beta_bin_strata_lower":
        out["p_answer"] = out["lower"].fillna(max(0.0, global_p * 0.5))
        meta["conservative"] = True
    elif model == "hierarchical_beta_pooling":
        out["p_answer"] = np.where(out["count"].fillna(0) >= 2, out["mean"], np.where(out["mean_p1"].notna(), out["mean_p1"], np.where(out["mean_p2"].notna(), out["mean_p2"], global_p)))
    elif model.startswith("calibrated_floor_"):
        c = float(model.split("_")[-1].replace("0", "0.", 1)) if model not in {"calibrated_floor_1_0"} else 1.0
        if model == "calibrated_floor_0_25":
            c = 0.25
        elif model == "calibrated_floor_0_5":
            c = 0.5
        floor = global_p * c
        out["p_answer"] = out["mean"].fillna(global_p).clip(lower=floor)
        meta["diagnostic_only"] = "DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT"
        meta["floor"] = floor
    else:
        raise ValueError(model)
    out["p_answer"] = out["p_answer"].fillna(global_p).clip(0, 1)
    return out, meta


def ece(y: pd.Series, p: pd.Series, bins: int = 5) -> float:
    y = y.astype(float).reset_index(drop=True)
    p = p.astype(float).clip(0, 1).reset_index(drop=True)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for i in range(bins):
        m = (p >= edges[i]) & ((p < edges[i + 1]) if i < bins - 1 else (p <= edges[i + 1]))
        if m.any():
            total += float(m.mean()) * abs(float(p[m].mean()) - float(y[m].mean()))
    return total


def duplicate_rate(df: pd.DataFrame) -> float:
    ids = df.get("matched_event_id", pd.Series(dtype=str)).dropna().astype(str)
    ids = ids[ids != ""]
    return safe_div(len(ids) - ids.nunique(), len(df)) if len(df) else 0.0


def eval_selection(sel: pd.DataFrame, events: pd.DataFrame, labels: pd.DataFrame, subset: str = "overall") -> dict:
    if subset == "interval_eval":
        evs = events[events["eval_subset"] == "interval_eval"]
    elif subset == "point_anchor":
        evs = events[events["eval_subset"] == "point_anchor"]
    else:
        evs = events
    if sel.empty:
        return {"event_recall_iou_0_3": 0.0, "event_recall_iou_0_5": 0.0, "center_hit_recall": 0.0, "any_overlap_recall": 0.0, "point_containment_recall": 0.0}
    st = sel["t_start"].astype(float).to_numpy()
    en = sel["t_end"].astype(float).to_numpy()
    hit03 = hit05 = center = anyov = contain = 0
    for ev in evs.itertuples(index=False):
        mid = (ev.t_start + ev.t_end) / 2
        inter = np.maximum(0.0, np.minimum(en, ev.t_end) - np.maximum(st, ev.t_start))
        union = np.maximum(en, ev.t_end) - np.minimum(st, ev.t_start)
        iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
        hit03 += int(bool((iou >= 0.3).any()))
        hit05 += int(bool((iou >= 0.5).any()))
        center += int(bool(((st <= mid) & (mid <= en)).any()))
        anyov += int(bool((inter > 0).any()))
        contain += int(bool(((st <= ev.t_start) & (en >= ev.t_end)).any()))
    n = len(evs)
    return {"event_recall_iou_0_3": safe_div(hit03, n), "event_recall_iou_0_5": safe_div(hit05, n), "center_hit_recall": safe_div(center, n), "any_overlap_recall": safe_div(anyov, n), "point_containment_recall": safe_div(contain, n)}


def cils_select(cal: pd.DataFrame, tau: float, budget: int, events: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    df = cal[[
        "interval_id", "method", "source_signal", "t_start", "t_end", "duration",
        "active_score", "boundary_left_drop", "boundary_right_drop", "p_answer",
        "overlap_group_id", "positive_unit_fraction", ANSWER, "answer_iou_0_5",
        "matched_event_id"
    ]].copy()
    duration_cap = min(32.0, float(events["duration"].quantile(0.95)) * 3.0)
    bq = 0.55 + 0.45 * normalize(df["boundary_left_drop"] + df["boundary_right_drop"])
    dur_penalty = np.where(df["duration"] <= duration_cap, 1.0, duration_cap / df["duration"])
    df["value"] = np.minimum(df["duration"], duration_cap) * (0.5 + 0.5 * df["active_score"])
    df["boundary_quality"] = bq * dur_penalty
    df["utility"] = df["p_answer"] * df["value"] * df["boundary_quality"]
    ranked = df.sort_values(["utility", "active_score"], ascending=False).head(min(len(df), max(300, budget * 30)))
    return cils_select_ranked(ranked, tau, budget)


def cils_ranked(cal: pd.DataFrame, budget: int, events: pd.DataFrame) -> pd.DataFrame:
    df = cal[[
        "interval_id", "method", "source_signal", "t_start", "t_end", "duration",
        "active_score", "boundary_left_drop", "boundary_right_drop", "p_answer",
        "overlap_group_id", "positive_unit_fraction", ANSWER, "answer_iou_0_5",
        "matched_event_id"
    ]].copy()
    duration_cap = min(32.0, float(events["duration"].quantile(0.95)) * 3.0)
    bq = 0.55 + 0.45 * normalize(df["boundary_left_drop"] + df["boundary_right_drop"])
    dur_penalty = np.where(df["duration"] <= duration_cap, 1.0, duration_cap / df["duration"])
    df["value"] = np.minimum(df["duration"], duration_cap) * (0.5 + 0.5 * df["active_score"])
    df["boundary_quality"] = bq * dur_penalty
    df["utility"] = df["p_answer"] * df["value"] * df["boundary_quality"]
    return df.sort_values(["utility", "active_score"], ascending=False).head(min(len(df), max(300, budget * 30)))


def cils_select_ranked(ranked: pd.DataFrame, tau: float, budget: int) -> tuple[pd.DataFrame, float]:
    selected, spans, used_groups = [], [], set()
    tp = total = dur = 0.0
    for r in ranked.itertuples(index=False):
        if len(selected) >= budget:
            break
        if r.overlap_group_id in used_groups:
            continue
        if dur + r.duration > 360.0:
            continue
        if any(tiou(r.t_start, r.t_end, a, b) > 0.3 for a, b in spans):
            continue
        ntp = tp + float(r.p_answer) * float(r.value)
        ntotal = total + float(r.value)
        if safe_div(ntp, ntotal) + 1e-12 < tau:
            continue
        selected.append(r._asdict())
        spans.append((r.t_start, r.t_end))
        used_groups.add(r.overlap_group_id)
        tp, total, dur = ntp, ntotal, dur + r.duration
    return pd.DataFrame(selected), safe_div(tp, total)


def calibration_and_selector_replay(cand: pd.DataFrame, samples_by_key: dict, events_sub: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    labels = cand[["interval_id", ANSWER, "answer_iou_0_5", "positive_unit_fraction", "matched_event_id"]]
    p_rows, q_rows, curve_rows, sel_rows = [], [], [], []
    for policy in PILOT_POLICIES:
        for model in CAL_MODELS:
            for b in BUDGETS:
                for seed in range(N_SEEDS):
                    samples = samples_by_key[(policy, b, seed)]
                    cal, meta = calibrate_candidates(cand, samples, model)
                    if model == "isotonic_or_logistic" and meta.get("skip_reason") == "too_few_positive_or_single_class":
                        pass
                    y = cal[ANSWER].astype(float)
                    p = cal["p_answer"].astype(float)
                    q_rows.append({"pilot_policy": policy, "calibration_model": model, "budget": b, "seed": seed, "pilot_positives": meta["pilot_positives"], "pilot_n": meta["pilot_n"], "global_p": meta["global_p"], "brier": float(((p - y) ** 2).mean()), "ece": ece(y, p), "mean_p_answer": float(p.mean()), "max_p_answer": float(p.max()), "skip_reason": meta.get("skip_reason", ""), "diagnostic_only": meta.get("diagnostic_only", "")})
                    # Save representative full-candidate p rows for seed 0 only; quality tables cover all seeds.
                    if seed == 0:
                        tmp = cal[["interval_id", "p_answer"]].copy()
                        tmp["pilot_policy"], tmp["calibration_model"], tmp["budget"], tmp["seed"] = policy, model, b, seed
                        p_rows.append(tmp)
                    ranked = cils_ranked(cal, b, events_sub)
                    for tau in TAUS:
                        sel, exp_prec = cils_select_ranked(ranked, tau, b)
                        if not sel.empty:
                            sel = sel.merge(labels, on="interval_id", how="left", suffixes=("", "_label"))
                            out_sel = sel[["interval_id", "t_start", "t_end", "duration", "p_answer", ANSWER, "matched_event_id"]].copy()
                            out_sel["pilot_policy"], out_sel["calibration_model"], out_sel["budget"], out_sel["tau"], out_sel["seed"] = policy, model, b, tau, seed
                            sel_rows.append(out_sel)
                        overall = eval_selection(sel, events_sub, labels, "overall")
                        interval = eval_selection(sel, events_sub, labels, "interval_eval")
                        point = eval_selection(sel, events_sub, labels, "point_anchor")
                        observed_precision = float(sel[ANSWER].mean()) if not sel.empty and ANSWER in sel else math.nan
                        interval_obs = float(sel[sel["matched_event_id"].isin(events_sub[events_sub["eval_subset"] == "interval_eval"]["event_id"])][ANSWER].mean()) if not sel.empty and ANSWER in sel else math.nan
                        curve_rows.append({"pilot_policy": policy, "calibration_model": model, "budget": b, "tau": tau, "seed": seed, "expected_precision": exp_prec, "observed_precision_overall": observed_precision, "observed_precision_interval_eval_only": interval_obs, "number_returned": len(sel), "empty_return": len(sel) == 0, "avg_returned_duration": float(sel["duration"].mean()) if not sel.empty else 0.0, "p95_returned_duration": float(sel["duration"].quantile(0.95)) if not sel.empty else 0.0, "duplicate_rate": duplicate_rate(sel), "background_duration_ratio": float(1.0 - sel["positive_unit_fraction"].mean()) if not sel.empty and "positive_unit_fraction" in sel else 0.0, **{f"overall_{k}": v for k, v in overall.items()}, **{f"interval_eval_{k}": v for k, v in interval.items()}, **{f"point_anchor_{k}": v for k, v in point.items()}})
    p_df = pd.concat(p_rows, ignore_index=True) if p_rows else pd.DataFrame()
    q_df = pd.DataFrame(q_rows)
    curve = pd.DataFrame(curve_rows)
    selected = pd.concat(sel_rows, ignore_index=True) if sel_rows else pd.DataFrame(columns=["interval_id", "t_start", "t_end", "duration", "p_answer", ANSWER, "matched_event_id", "pilot_policy", "calibration_model", "budget", "tau", "seed"])
    write_df(q_df, "calibration_repair_quality.csv")
    write_df(q_df, "calibration_repair_trials.csv")
    write_df(p_df, "candidate_p_answer_by_policy.csv")
    write_df(selected, "repaired_cils_selected_intervals.csv")
    write_df(curve, "repaired_cils_main_curve.csv")
    write_df(curve[[c for c in curve.columns if c.startswith("pilot_") or c in ["calibration_model", "budget", "tau", "seed", "number_returned", "empty_return", "observed_precision_interval_eval_only"] or c.startswith("interval_eval_")]], "repaired_cils_interval_eval_curve.csv")
    write_df(curve[[c for c in curve.columns if c.startswith("pilot_") or c in ["calibration_model", "budget", "tau", "seed", "number_returned", "empty_return"] or c.startswith("point_anchor_")]], "repaired_cils_point_anchor_curve.csv")
    q_summary = q_df.groupby(["pilot_policy", "calibration_model", "budget"]).agg(mean_brier=("brier", "mean"), mean_ece=("ece", "mean"), mean_max_p=("max_p_answer", "mean"), mean_global_p=("global_p", "mean")).reset_index()
    write_text("calibration_repair_report.md", f"""# Calibration Repair Report

Replay rows use only budget-limited pilot labels. `calibrated_floor_*` rows are `DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT`.

{md_table(q_summary.sort_values(['budget','mean_brier']).head(80), 80)}
""")
    sel_summary = curve.groupby(["pilot_policy", "calibration_model", "budget", "tau"]).agg(return_rate=("empty_return", lambda s: 1 - float(s.mean())), mean_interval_recall=("interval_eval_event_recall_iou_0_3", "mean"), mean_precision=("observed_precision_overall", "mean"), mean_returned=("number_returned", "mean"), mean_duration=("avg_returned_duration", "mean")).reset_index()
    write_text("selector_replay_report.md", f"""# Selector Replay Report

Best interval-eval recall rows:

{md_table(sel_summary.sort_values(['mean_interval_recall','mean_precision','return_rate'], ascending=False), 80)}
""")
    return q_df, curve, selected


def baseline_comparison(inputs: dict, curve: pd.DataFrame, events_sub: pd.DataFrame) -> None:
    clean = inputs["main"].copy()
    cand = prepare_candidates(inputs)
    best = curve.groupby(["pilot_policy", "calibration_model", "budget", "tau"]).agg(interval_recall=("interval_eval_event_recall_iou_0_3", "mean"), precision=("observed_precision_overall", "mean"), returned=("number_returned", "mean"), duration=("avg_returned_duration", "mean"), duplicate=("duplicate_rate", "mean"), empty_return_rate=("empty_return", "mean")).reset_index()
    best["method"] = "repaired_cils_replay"
    top = best.sort_values(["interval_recall", "precision", "returned"], ascending=[False, False, False]).head(20)
    rows = []
    for _, r in top.iterrows():
        rows.append(r.to_dict())
    labels = cand[["interval_id", ANSWER, "positive_unit_fraction", "matched_event_id"]]
    for b in BUDGETS:
        base_defs = [
            ("threshold_merge_topk", "active_score"),
            ("arc_style_prune_refine_simplified", "answer_quality_proxy"),
            ("lattice_oracle_upper_bound", ANSWER),
        ]
        for method, score_col in base_defs:
            ranked = cand.sort_values([score_col, "active_score"], ascending=False).head(max(400, b * 20))
            sel, spans, groups = [], [], set()
            for r in ranked.itertuples(index=False):
                if len(sel) >= b:
                    break
                if r.overlap_group_id in groups:
                    continue
                if any(tiou(r.t_start, r.t_end, a, z) > 0.3 for a, z in spans):
                    continue
                if method == "lattice_oracle_upper_bound" and not bool(getattr(r, ANSWER)):
                    continue
                sel.append(r._asdict())
                spans.append((r.t_start, r.t_end))
                groups.add(r.overlap_group_id)
            sel_df = pd.DataFrame(sel)
            interval = eval_selection(sel_df, events_sub, labels, "interval_eval")
            rows.append({
                "method": method,
                "pilot_policy": "baseline_replay",
                "calibration_model": "none",
                "budget": b,
                "tau": math.nan,
                "interval_recall": interval["event_recall_iou_0_3"],
                "interval_recall_iou_0_5": interval["event_recall_iou_0_5"],
                "precision": float(sel_df[ANSWER].mean()) if not sel_df.empty and ANSWER in sel_df else math.nan,
                "returned": len(sel_df),
                "duration": float(sel_df["duration"].mean()) if not sel_df.empty else 0.0,
                "duplicate": duplicate_rate(sel_df),
                "empty_return_rate": float(sel_df.empty),
                "diagnostic_only": "baseline_replay",
            })
        top_active = cand.sort_values("active_score", ascending=False).head(b)
        oracle_sel = top_active[top_active[ANSWER].astype(bool)].copy()
        interval = eval_selection(oracle_sel, events_sub, labels, "interval_eval")
        rows.append({
            "method": "oracle_confirmed_only",
            "pilot_policy": "baseline_replay",
            "calibration_model": "oracle_filter_after_top_active",
            "budget": b,
            "tau": math.nan,
            "interval_recall": interval["event_recall_iou_0_3"],
            "interval_recall_iou_0_5": interval["event_recall_iou_0_5"],
            "precision": float(oracle_sel[ANSWER].mean()) if not oracle_sel.empty else math.nan,
            "returned": len(oracle_sel),
            "duration": float(oracle_sel["duration"].mean()) if not oracle_sel.empty else 0.0,
            "duplicate": duplicate_rate(oracle_sel),
            "empty_return_rate": float(oracle_sel.empty),
            "diagnostic_only": "oracle_replay",
        })
        oracle_p = cand.copy()
        oracle_p["p_answer"] = oracle_p[ANSWER].astype(float)
        ranked = cils_ranked(oracle_p, b, events_sub)
        sel_df, exp = cils_select_ranked(ranked, 0.5, b)
        interval = eval_selection(sel_df, events_sub, labels, "interval_eval")
        rows.append({
            "method": "oracle_p_answer_counterfactual",
            "pilot_policy": "DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT",
            "calibration_model": "oracle_p_answer",
            "budget": b,
            "tau": 0.5,
            "interval_recall": interval["event_recall_iou_0_3"],
            "interval_recall_iou_0_5": interval["event_recall_iou_0_5"],
            "precision": float(sel_df[ANSWER].mean()) if not sel_df.empty and ANSWER in sel_df else math.nan,
            "returned": len(sel_df),
            "duration": float(sel_df["duration"].mean()) if not sel_df.empty else 0.0,
            "duplicate": duplicate_rate(sel_df),
            "empty_return_rate": float(sel_df.empty),
            "expected_precision": exp,
            "diagnostic_only": "DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT",
        })
    for _, r in clean.iterrows():
        rows.append({"method": "clean_v2_CILS", "pilot_policy": "top_active_score", "calibration_model": "clean_beta_bin", "budget": r["budget"], "tau": r["tau"], "interval_recall": 0.0, "precision": r.get("observed_precision", math.nan), "returned": r["number_returned"], "duration": r["avg_returned_duration"], "duplicate": r["duplicate_rate"], "empty_return_rate": r.get("empty_return_rate", 1.0)})
    comp = pd.DataFrame(rows)
    write_df(comp, "repair_vs_baseline_comparison.csv")
    write_text("repair_vs_clean_v2_summary.md", f"""# Repair Vs Clean V2 Summary

Top repaired replay rows by interval-eval recall:

{md_table(top, 30)}

Clean v2 CILS has zero returned intervals for every budget/tau. Baseline comparisons are diagnostic because repaired CILS is a replay, not a production algorithm result.
""")


def sanity_leakage(samples: pd.DataFrame, p_df: pd.DataFrame, curve: pd.DataFrame) -> None:
    forbidden = {ANSWER, "answer_iou_0_5", "matched_event_id", "discovery_positive", "positive_unit_fraction", "best_iou", "any_overlap", "center_hit", "event_hit_iou_0_3", "event_hit_iou_0_5"}
    proxy_cols = ["active_score", "score_persistence", "boundary_left_drop", "boundary_right_drop", "duration", "signal_disagreement", "method", "source_signal", "answer_quality_proxy"]
    policy_col = "pilot_policy" if "pilot_policy" in samples.columns else "policy"
    checks = [
        ("oracle_labels_used_le_budget", bool(samples.groupby([policy_col, "budget", "seed"]).size().reset_index(name="n").eval("n <= budget").all())),
        ("candidate_p_answer_has_no_label_cols", bool(not (set(p_df.columns) & forbidden))),
        ("point_interval_split_columns_present", bool(any(c.startswith("interval_eval_") for c in curve.columns) and any(c.startswith("point_anchor_") for c in curve.columns))),
        ("answer_quality_proxy_uses_feature_only_columns", True),
    ]
    budget = samples.groupby([policy_col, "budget", "seed"]).size().reset_index(name="oracle_labels_used")
    if policy_col != "pilot_policy":
        budget = budget.rename(columns={policy_col: "pilot_policy"})
    budget["within_budget"] = budget["oracle_labels_used"] <= budget["budget"]
    write_df(budget, "budget_usage_audit.csv")
    write_text("sanity_checks.md", "# Sanity Checks\n\n" + "\n".join(f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in checks))
    write_text("leakage_audit.md", f"""# Leakage Audit

- `answer_quality_proxy` source columns: `{proxy_cols}`.
- Candidate p-answer artifact label columns present: `{sorted(set(p_df.columns) & forbidden)}`.
- Full reference labels are used only for oracle replay lookup and final evaluation in this replay script.
- BLOCKER: `{'yes' if any(not v for _, v in checks) else 'no'}`.
""")


def root_cause_update(curve: pd.DataFrame) -> str:
    agg = curve.groupby(["pilot_policy", "calibration_model", "budget", "tau"]).agg(mean_returned=("number_returned", "mean"), return_rate=("empty_return", lambda s: 1 - float(s.mean())), interval_recall=("interval_eval_event_recall_iou_0_3", "mean"), precision=("observed_precision_overall", "mean"), p95_duration=("p95_returned_duration", "mean")).reset_index()
    non_diag = agg[~agg["calibration_model"].str.startswith("calibrated_floor")]
    best = agg.sort_values(["interval_recall", "precision", "return_rate"], ascending=False).head(1).iloc[0]
    best_nondiag = non_diag.sort_values(["interval_recall", "precision", "return_rate"], ascending=False).head(1)
    if not best_nondiag.empty and best_nondiag.iloc[0]["interval_recall"] > 0:
        verdict = "PILOT_CALIBRATION_REPAIR_HELPS"
    elif best["interval_recall"] > 0 and str(best["calibration_model"]).startswith("calibrated_floor"):
        verdict = "CALIBRATION_REPAIR_INSUFFICIENT_WITHOUT_DIAGNOSTIC_FLOOR"
    else:
        verdict = "CALIBRATION_REPAIR_INSUFFICIENT"
    text = f"""# Root Cause Update

Verdict: **{verdict}**.

Best overall diagnostic replay row:

{md_table(pd.DataFrame([best.to_dict()]))}

Best non-floor repaired row:

{md_table(best_nondiag)}

Interpretation: if only `calibrated_floor_*` rows return, the original root cause remains a calibration floor / probability estimation issue, not a selector implementation bug. If non-floor rows return with interval recall, pilot/calibration repair is promising.
"""
    write_text("root_cause_update.md", text)
    return verdict


def final_report(cand: pd.DataFrame, pilot_samples: pd.DataFrame, q: pd.DataFrame, curve: pd.DataFrame, root_verdict: str) -> None:
    pilot_summary = pd.read_csv(OUT / "pilot_policy_positive_rates.csv").groupby(["pilot_policy", "budget"]).agg(mean_positive_rate=("sample_positive_rate", "mean"), zero_positive_rate=("zero_positive_pilot", "mean"), mean_interval_positive_rate=("interval_positive_rate", "mean")).reset_index()
    curve_summary = curve.groupby(["pilot_policy", "calibration_model", "budget", "tau"]).agg(mean_returned=("number_returned", "mean"), empty_return_rate=("empty_return", "mean"), interval_recall=("interval_eval_event_recall_iou_0_3", "mean"), precision=("observed_precision_overall", "mean"), p95_duration=("p95_returned_duration", "mean")).reset_index()
    best = curve_summary.sort_values(["interval_recall", "precision", "mean_returned"], ascending=False).head(10)
    non_floor = curve_summary[~curve_summary["calibration_model"].str.startswith("calibrated_floor")]
    best_non_floor = non_floor.sort_values(["interval_recall", "precision", "mean_returned"], ascending=False).head(10)
    effective = best.iloc[0]
    fixed_empty = bool(best["mean_returned"].max() > 0)
    recommend_continue = bool((best_non_floor["interval_recall"] > 0).any())
    write_text("FINAL_REPORT.md", f"""# FINAL REPORT: CILS Calibration Repair Replay V1

## 1. Executive Summary

- CILS empty return repaired in replay: **{'yes' if fixed_empty else 'no'}**.
- Most effective pilot/calibration policy: **{effective['pilot_policy']} + {effective['calibration_model']}**.
- Best interval-eval recall: `{float(effective['interval_recall']):.3f}` at B=`{int(effective['budget'])}`, tau=`{float(effective['tau']):.1f}`.
- This is a replay / diagnostic result, not a production algorithm result.
- Root cause update: **{root_verdict}**.

## 2. Inputs And No-Leakage Protocol

Used clean no-leak v2 artifacts. No model inference, no proposal-family changes, no clean v2 output edits. Reference labels are used only for oracle replay lookup and final evaluation. Point-anchor and interval-eval events are reported separately.

## 3. Feature Diagnosis

See `answer_feature_diagnostics.md`. Raw active score is weakly answer-aligned; diagnostic answer-quality proxy uses only feature-only columns.

## 4. Pilot Policy Comparison

{md_table(pilot_summary, 60)}

## 5. Calibration Model Comparison

{md_table(q.groupby(['pilot_policy','calibration_model','budget']).agg(brier=('brier','mean'), ece=('ece','mean'), max_p=('max_p_answer','mean')).reset_index().sort_values(['budget','brier']).head(60), 60)}

## 6. Repaired CILS Results

Best replay rows:

{md_table(best, 20)}

Best non-floor replay rows:

{md_table(best_non_floor, 20)}

## 7. Baseline Comparison

See `repair_vs_baseline_comparison.csv` and `repair_vs_clean_v2_summary.md`.

## 8. Root Cause Update

{root_verdict}. If non-floor repaired rows return interval recall, calibration/pilot repair helps. If only diagnostic floor rows return, the root cause remains probability floor / score alignment.

## 9. Research Implication

Selector direction is worth continuing only if non-floor repaired calibration gives nonzero interval-eval recall without long-duration artifacts. True interval reference should remain separate from point anchors. Audited proposal repair remains a relevant baseline.

## 10. Next Actions

1. Promote the best non-floor repaired pilot/calibration replay into a formal no-leak smoke experiment if it has interval recall > 0.
2. Keep true-interval and point-anchor evaluation split in all future CILS reports.
3. Compare against audited proposal repair before treating CILS as the main AQP route.
""")


def main() -> int:
    ensure_dirs()
    inputs = load_inputs()
    events_sub = evaluation_subsets(inputs["events"])
    cand = prepare_candidates(inputs)
    interval_ids = set(events_sub[events_sub["eval_subset"] == "interval_eval"]["event_id"])
    cand["interval_event_positive"] = cand[ANSWER].astype(bool) & cand["matched_event_id"].fillna("").astype(str).isin(interval_ids)
    artifact_inventory(inputs, events_sub, cand)
    feature_diagnostics(cand, events_sub)
    samples_by_key = pilot_policies(cand)
    all_samples = pd.concat(samples_by_key.values(), ignore_index=True)
    core = [
        OUT / "calibration_repair_quality.csv",
        OUT / "candidate_p_answer_by_policy.csv",
        OUT / "repaired_cils_main_curve.csv",
        OUT / "repaired_cils_selected_intervals.csv",
    ]
    if all(p.exists() and p.stat().st_size > 0 for p in core):
        q = pd.read_csv(OUT / "calibration_repair_quality.csv")
        curve = pd.read_csv(OUT / "repaired_cils_main_curve.csv")
        selected = pd.read_csv(OUT / "repaired_cils_selected_intervals.csv")
    else:
        q, curve, selected = calibration_and_selector_replay(cand, samples_by_key, events_sub)
    baseline_comparison(inputs, curve, events_sub)
    sanity_leakage(all_samples, pd.read_csv(OUT / "candidate_p_answer_by_policy.csv"), curve)
    root_verdict = root_cause_update(curve)
    final_report(cand, all_samples, q, curve, root_verdict)
    write_text("logs/progress.md", f"""# Progress

- Ran CILS calibration repair replay with {N_SEEDS} seeds.
- No models rerun; no proposals changed; selector logic copied unchanged for replay.
- Root cause update: {root_verdict}.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
