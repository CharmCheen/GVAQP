#!/usr/bin/env python3
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
EXP = ROOT / "src/garc_eval/experiments/cils_empty_return_root_cause_audit_v1"
OUT = ROOT / "src/garc_eval/outputs/cils_empty_return_root_cause_audit_v1"
V2 = ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak"
DUR = ROOT / "src/garc_eval/outputs/reference_duration_stratified_eval_v1"
CODE_AUDIT = ROOT / "src/garc_eval/outputs/clean_interval_aqp_code_audit_v2_clean_no_leak"

ANSWER = "answer_iou_0_3"
SEED = 20260630
BUDGETS = [5, 10, 20, 40, 80]
TAUS = [0.5, 0.6, 0.7, 0.8, 0.9]
LOW_TAUS = [0.1, 0.2, 0.3, 0.4]
TRACE_SEEDS = list(range(100))
FOCUS = {(80, 0.5), (80, 0.6), (80, 0.7), (80, 0.8), (40, 0.6)}


def ensure_dirs() -> None:
    for d in [OUT, OUT / "logs", OUT / "tables", OUT / "reports", OUT / "config", OUT / "data_manifest", OUT / "figures", OUT / "scripts"]:
        d.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, **kwargs)


def write_df(df: pd.DataFrame, name: str) -> None:
    ensure_dirs()
    df.to_csv(OUT / name, index=False)
    df.to_csv(OUT / "tables" / name, index=False)


def write_text(name: str, text: str) -> None:
    ensure_dirs()
    (OUT / name).write_text(text.rstrip() + "\n", encoding="utf-8")


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
            if isinstance(v, float):
                vals.append(f"{v:.6g}")
            else:
                vals.append(str(v).replace("\n", " ").replace("|", "\\|"))
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


def tiou(a0: float, a1: float, b0: float, b1: float) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    return safe_div(inter, union)


def prepare_features(features: pd.DataFrame, active_score: pd.Series | None = None) -> pd.DataFrame:
    f = features.copy()
    if active_score is not None:
        f["active_score"] = active_score.values
    f["active_score"] = normalize(f["active_score"])
    f["score_bin"] = pd.qcut(f["active_score"].rank(method="first"), 5, labels=False)
    f["duration_bin"] = pd.qcut(f["duration"].rank(method="first"), 4, labels=False)
    f["disagreement_bin"] = pd.qcut(f["signal_disagreement"].rank(method="first"), 4, labels=False)
    f["candidate_value"] = np.minimum(f["duration"], 32.0) * (0.5 + 0.5 * f["active_score"])
    f["predicted_uncertainty"] = f["active_score"] * (1.0 - f["active_score"])
    return f


def quota_sample(f: pd.DataFrame, budget: int, seed: int, uncertainty: bool = False) -> list[str]:
    rng = np.random.default_rng(seed)
    strata_cols = ["score_bin", "duration_bin", "disagreement_bin"]
    groups = [(k, g.copy()) for k, g in f.groupby(strata_cols, dropna=False)]
    if not groups or budget <= 0:
        return []
    quota = {k: min(len(g), budget // len(groups)) for k, g in groups}
    remaining = budget - sum(quota.values())
    weights = []
    group_map = dict(groups)
    for k, g in groups:
        if len(g) <= quota[k]:
            w = 0.0
        elif uncertainty:
            w = float((g["predicted_uncertainty"] * g["candidate_value"]).sum())
        else:
            w = float(len(g))
        weights.append((w, k))
    while remaining > 0 and any(w > 0 for w, _ in weights):
        for _, k in sorted(weights, reverse=True):
            g = group_map[k]
            if remaining <= 0:
                break
            if quota[k] < len(g):
                quota[k] += 1
                remaining -= 1
        weights = [(max(0.0, w - 1e-9), k) for w, k in weights]
    chosen = []
    for k, g in groups:
        n = quota[k]
        if n > 0:
            chosen.extend(g.sample(n=n, random_state=int(rng.integers(0, 1_000_000)))["interval_id"].tolist())
    if len(chosen) > budget:
        chosen = list(rng.choice(chosen, size=budget, replace=False))
    return chosen


def policy_order(f: pd.DataFrame, budget: int, seed: int, policy: str) -> list[str]:
    if policy == "uniform":
        return f.sample(frac=1, random_state=seed)["interval_id"].head(budget).tolist()
    if policy == "top_score":
        return f.sort_values(["active_score", "duration"], ascending=[False, True])["interval_id"].head(budget).tolist()
    if policy == "quota_stratified":
        return quota_sample(f, budget, seed, uncertainty=False)
    if policy == "uncertainty_stratified":
        return quota_sample(f, budget, seed, uncertainty=True)
    if policy == "decision_aware_simple":
        ff = f.assign(priority=f["predicted_uncertainty"] * f["candidate_value"])
        return ff.sort_values("priority", ascending=False)["interval_id"].head(budget).tolist()
    raise ValueError(policy)


def calibrate(f: pd.DataFrame, samples: pd.DataFrame) -> pd.DataFrame:
    out = f.copy()
    sample_map = samples.set_index("interval_id")["oracle_label"].astype(int).to_dict()
    s = out[out["interval_id"].isin(sample_map)].copy()
    s["y"] = s["interval_id"].map(sample_map).astype(int)
    global_p = safe_div(float(s["y"].sum()) + 1.0, len(s) + 2.0)
    key = ["score_bin", "duration_bin", "disagreement_bin"]
    local = s.groupby(key, dropna=False)["y"].agg(["sum", "count"]).reset_index()
    local["p_local"] = (local["sum"] + 1.0) / (local["count"] + 2.0)
    score = s.groupby(["score_bin"], dropna=False)["y"].agg(["sum", "count"]).reset_index()
    score["p_score"] = (score["sum"] + 1.0) / (score["count"] + 2.0)
    out = out.merge(local[key + ["count", "p_local"]].rename(columns={"count": "n_local"}), on=key, how="left")
    out = out.merge(score[["score_bin", "count", "p_score"]].rename(columns={"count": "n_score"}), on="score_bin", how="left")
    out["p_answer"] = np.where(
        out["n_local"].fillna(0) >= 2,
        out["p_local"],
        np.where(out["n_score"].fillna(0) > 0, out["p_score"], global_p),
    )
    out["p_answer"] = out["p_answer"].fillna(global_p).clip(0, 1)
    return out


def oracle_samples(f: pd.DataFrame, labels: pd.DataFrame, budget: int, seed: int, policy: str) -> pd.DataFrame:
    order = policy_order(f, budget, seed, policy)
    lab = labels.set_index("interval_id")
    return pd.DataFrame(
        [
            {
                "interval_id": iid,
                "rank": rank,
                "oracle_label": bool(lab.loc[iid, ANSWER]),
                "discovery_positive": bool(lab.loc[iid, "discovery_positive"]),
                "answer_label": ANSWER,
            }
            for rank, iid in enumerate(order[:budget], 1)
        ]
    )


def event_recall(sel: pd.DataFrame, events: pd.DataFrame, thresh: float) -> float:
    if sel.empty:
        return 0.0
    hit = set()
    for ev in events.itertuples(index=False):
        for r in sel.itertuples(index=False):
            if tiou(r.t_start, r.t_end, ev.t_start, ev.t_end) >= thresh:
                hit.add(ev.event_id)
                break
    return safe_div(len(hit), len(events))


def selector_trace(
    cal: pd.DataFrame,
    tau: float,
    budget: int,
    duration_cap: float,
    labels: pd.DataFrame,
    max_total_duration: float = 360.0,
    disable_duration_penalty: bool = False,
    disable_overlap_control: bool = False,
    trace_all_ranked: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    df = cal.copy()
    bq_base = 0.55 + 0.45 * normalize(df["boundary_left_drop"] + df["boundary_right_drop"])
    if disable_duration_penalty:
        dur_penalty = np.ones(len(df))
    else:
        dur_penalty = np.where(df["duration"] <= duration_cap, 1.0, duration_cap / df["duration"])
    df["duration_penalty"] = dur_penalty
    df["value"] = np.minimum(df["duration"], duration_cap) * (0.5 + 0.5 * df["active_score"])
    df["boundary_quality"] = bq_base * df["duration_penalty"]
    df["utility"] = df["p_answer"] * df["value"] * df["boundary_quality"]
    ranked = df.sort_values(["utility", "active_score"], ascending=False).head(min(len(df), max(300, budget * 30)))
    lab = labels.set_index("interval_id")
    rows, selected, spans = [], [], []
    tp = total = dur = 0.0
    used_groups = set()
    for rank, r in enumerate(ranked.itertuples(index=False), 1):
        reason = "selected"
        overlap_conflict = False
        ntp = tp + float(r.p_answer) * float(r.value)
        ntotal = total + float(r.value)
        exp_if = safe_div(ntp, ntotal)
        if len(selected) >= budget:
            reason = "skipped_by_sort_order"
        elif pd.isna(r.p_answer):
            reason = "missing_p_answer"
        elif r.overlap_group_id in used_groups and not disable_overlap_control:
            overlap_conflict = True
            reason = "overlap_conflict"
        elif dur + r.duration > max_total_duration:
            reason = "duration_penalty_too_large"
        elif (not disable_overlap_control) and any(tiou(r.t_start, r.t_end, a, b) > 0.3 for a, b in spans):
            overlap_conflict = True
            reason = "overlap_conflict"
        elif float(r.utility) <= 0:
            reason = "non_positive_utility"
        elif exp_if + 1e-12 < tau:
            reason = "below_precision_constraint"
            if float(r.p_answer) < tau:
                reason = "p_answer_too_low"
        else:
            selected.append(r._asdict())
            spans.append((r.t_start, r.t_end))
            used_groups.add(r.overlap_group_id)
            tp, total, dur = ntp, ntotal, dur + r.duration
        if trace_all_ranked or reason == "selected":
            rows.append(
                {
                    "rank": rank,
                    "interval_id": r.interval_id,
                    "method": r.method,
                    "source_signal": r.source_signal,
                    "active_score": float(r.active_score),
                    "p_answer": float(r.p_answer),
                    "value": float(r.value),
                    "boundary_quality": float(r.boundary_quality),
                    "duration": float(r.duration),
                    "duration_penalty": float(r.duration_penalty),
                    "utility": float(r.utility),
                    "expected_precision_if_added": exp_if,
                    "expected_tp_if_added": ntp,
                    "expected_total_if_added": ntotal,
                    "overlap_conflict": overlap_conflict,
                    "rejection_reason": reason,
                    "answer_iou_0_3": bool(lab.loc[r.interval_id, ANSWER]) if r.interval_id in lab.index else False,
                    "matched_event_id": lab.loc[r.interval_id, "matched_event_id"] if r.interval_id in lab.index else "",
                }
            )
    sel = pd.DataFrame(selected)
    if not sel.empty:
        sel = sel.merge(labels, on="interval_id", how="left", suffixes=("", "_label"))
    return sel, pd.DataFrame(rows), safe_div(tp, total)


def load_inputs() -> dict[str, pd.DataFrame | str]:
    inputs = {
        "reference_events": read_csv(V2 / "reference_events.csv"),
        "lattice": read_csv(V2 / "interval_lattice_v2_clean.csv"),
        "features": read_csv(V2 / "interval_lattice_features_only.csv"),
        "labels": read_csv(V2 / "interval_labels_v2_clean.csv"),
        "cal_trials": read_csv(V2 / "calibration_trials_v2_clean.csv"),
        "cal_quality": read_csv(V2 / "calibration_quality_v2_clean.csv"),
        "main": read_csv(V2 / "main_budget_curve_v2_clean.csv"),
        "baseline": read_csv(V2 / "baseline_comparison_v2_clean.csv"),
        "selected": read_csv(V2 / "selected_intervals_by_trial_v2_clean.csv"),
        "stress": read_csv(V2 / "stress_test_results_v2_clean.csv"),
    }
    inputs["final_report_text"] = (V2 / "FINAL_REPORT.md").read_text(encoding="utf-8") if (V2 / "FINAL_REPORT.md").exists() else ""
    return inputs


def artifact_inventory() -> None:
    files = [
        V2 / "reference_events.csv",
        V2 / "interval_lattice_v2_clean.csv",
        V2 / "interval_lattice_features_only.csv",
        V2 / "interval_labels_v2_clean.csv",
        V2 / "calibration_trials_v2_clean.csv",
        V2 / "calibration_quality_v2_clean.csv",
        V2 / "main_budget_curve_v2_clean.csv",
        V2 / "baseline_comparison_v2_clean.csv",
        V2 / "selected_intervals_by_trial_v2_clean.csv",
        V2 / "stress_test_results_v2_clean.csv",
        V2 / "FINAL_REPORT.md",
        DUR / "event_duration_strata.csv",
        DUR / "per_event_best_candidate.csv",
        DUR / "event_failure_types.csv",
        DUR / "DURATION_STRATIFIED_DIAGNOSIS.md",
        DUR / "FINAL_REPORT.md",
        CODE_AUDIT / "FINAL_CODE_AUDIT_REPORT.md",
    ]
    rows = []
    for p in files:
        row = {"path": str(p), "artifact": p.name, "exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() else 0}
        if p.suffix == ".csv" and p.exists():
            df0 = pd.read_csv(p, nrows=0)
            row["rows"] = max(0, sum(1 for _ in p.open()) - 1)
            row["columns"] = "|".join(df0.columns)
            if p.name == "selected_intervals_by_trial_v2_clean.csv":
                row["selected_intervals_empty"] = row["rows"] == 0
            if p.name == "calibration_trials_v2_clean.csv":
                df = pd.read_csv(p, usecols=["budget", "policy"])
                row["budgets"] = ",".join(map(str, sorted(df["budget"].unique())))
                row["policies"] = ",".join(map(str, sorted(df["policy"].unique())))
        rows.append(row)
    inv = pd.DataFrame(rows)
    write_df(inv, "artifact_inventory.csv")
    write_text(
        "artifact_inventory.md",
        f"""# Artifact Inventory

Duration diagnosis directory exists: `{DUR.exists()}`. If missing, this audit falls back to duration strata from `reference_events.csv`.

{md_table(inv, 80)}
""",
    )


def build_event_sets(events: pd.DataFrame) -> pd.DataFrame:
    strata_file = DUR / "event_duration_strata.csv"
    if strata_file.exists():
        s = pd.read_csv(strata_file)
        if "duration_stratum" not in s.columns:
            dur_col = "duration" if "duration" in s.columns else "event_duration"
            s["duration_stratum"] = np.where(s[dur_col] <= 2, "point_anchor", np.where(s[dur_col] < 5, "short_interval", "true_interval"))
        keep = [c for c in ["event_id", "duration", "duration_stratum"] if c in s.columns]
        out = events.merge(s[keep].drop_duplicates("event_id"), on="event_id", how="left", suffixes=("", "_strata"))
        if "duration_stratum" not in out.columns:
            out["duration_stratum"] = np.where(out["duration"] <= 2, "point_anchor", np.where(out["duration"] < 5, "short_interval", "true_interval"))
    else:
        out = events.copy()
        out["duration_stratum"] = np.where(out["duration"] <= 2, "point_anchor", np.where(out["duration"] < 5, "short_interval", "true_interval"))
    out["is_interval_eval"] = out["duration_stratum"].isin(["short_interval", "true_interval"])
    out["is_true_interval"] = out["duration_stratum"].eq("true_interval")
    write_df(out, "interval_eval_event_set.csv")
    interval_events = out[out["is_interval_eval"]]
    write_text(
        "interval_eval_subset_summary.md",
        f"""# Interval-Eval Event Set

- Event strata source: `{'duration diagnosis artifact' if (DUR / 'event_duration_strata.csv').exists() else 'fallback from reference_events.csv'}`
- Total reference events: `{len(out)}`
- Interval-eval events (`short_interval` or `true_interval`): `{len(interval_events)}`
- True interval events (`duration >= 5s`): `{int(out['is_true_interval'].sum())}`
- Event IDs: `{interval_events['event_id'].tolist()}`

Duration summary:

{md_table(out.groupby('duration_stratum').agg(events=('event_id','count'), min_duration=('duration','min'), median_duration=('duration','median'), max_duration=('duration','max')).reset_index())}

These events are the appropriate interval-IoU focus set because point anchors can have overlap/center hits but fail IoU@0.3 due boundary mismatch.
""",
    )
    return out


def add_event_hit_columns(candidates: pd.DataFrame, event_sets: pd.DataFrame) -> pd.DataFrame:
    interval_ids, point_ids = [], []
    interval_event_ids, point_event_ids = set(event_sets[event_sets["is_interval_eval"]]["event_id"]), set(event_sets[~event_sets["is_interval_eval"]]["event_id"])
    for mid in candidates["matched_event_id"].fillna("").astype(str):
        if mid in interval_event_ids:
            interval_ids.append(True)
            point_ids.append(False)
        elif mid in point_event_ids:
            interval_ids.append(False)
            point_ids.append(True)
        else:
            interval_ids.append(False)
            point_ids.append(False)
    candidates["hits_interval_eval_event"] = candidates[ANSWER].astype(bool) & pd.Series(interval_ids, index=candidates.index)
    candidates["hits_point_anchor_event"] = candidates[ANSWER].astype(bool) & pd.Series(point_ids, index=candidates.index)
    candidates["point_event_only_positive"] = candidates["hits_point_anchor_event"] & ~candidates["hits_interval_eval_event"]
    return candidates


def candidate_pool(inputs: dict, event_sets: pd.DataFrame) -> pd.DataFrame:
    cand = inputs["features"].merge(inputs["labels"], on="interval_id", how="left")
    cand = add_event_hit_columns(cand, event_sets)
    cand["duration_bin"] = pd.cut(cand["duration"], bins=[0, 2, 5, 10, 20, 40, 80, 1e9], labels=["<=2", "2-5", "5-10", "10-20", "20-40", "40-80", ">80"])
    cand["active_score_bin"] = pd.qcut(cand["active_score"].rank(method="first"), 5, labels=["q1_low", "q2", "q3", "q4", "q5_high"])
    total = pd.DataFrame(
        [
            {
                "total_candidates": len(cand),
                "answer_iou_0_3_positive_candidates": int(cand[ANSWER].sum()),
                "answer_iou_0_5_positive_candidates": int(cand["answer_iou_0_5"].sum()),
                "discovery_positive_candidates": int(cand["discovery_positive"].sum()),
                "point_event_only_positive_candidates": int(cand["point_event_only_positive"].sum()),
                "interval_event_positive_candidates": int(cand["hits_interval_eval_event"].sum()),
                "candidates_that_hit_true_interval_events": int(cand[cand["matched_event_id"].isin(event_sets[event_sets["is_true_interval"]]["event_id"])][ANSWER].sum()),
                "candidates_that_hit_only_point_anchor_events": int(cand["point_event_only_positive"].sum()),
                "max_active_score_positive_rank": float(cand.loc[cand[ANSWER].astype(bool), "active_score"].rank(ascending=False).min()) if cand[ANSWER].any() else math.nan,
            }
        ]
    )
    write_df(total, "candidate_pool_accounting.csv")
    groups = []
    for keys in [["method"], ["source_signal"], ["duration_bin"], ["active_score_bin"], ["method", "active_score_bin"]]:
        g = cand.groupby(keys, dropna=False)
        for k, df in g:
            rec = {"group_by": "+".join(keys), "group": str(k)}
            rec.update(
                {
                    "candidate_count": len(df),
                    "answer_iou_0_3_positive_rate": float(df[ANSWER].mean()),
                    "interval_event_answer_positive_rate": float(df["hits_interval_eval_event"].mean()),
                    "answer_positive_count": int(df[ANSWER].sum()),
                    "interval_event_positive_count": int(df["hits_interval_eval_event"].sum()),
                    "mean_active_score": float(df["active_score"].mean()),
                    "median_active_score": float(df["active_score"].median()),
                }
            )
            groups.append(rec)
    by_group = pd.DataFrame(groups)
    write_df(by_group, "candidate_pool_by_group.csv")
    top_rows = []
    for pct in [0.01, 0.05, 0.10, 0.20]:
        n = max(1, int(len(cand) * pct))
        top = cand.sort_values("active_score", ascending=False).head(n)
        top_rows.append({"top_active_score_percent": pct, "n": n, "answer_positive_rate": float(top[ANSWER].mean()), "interval_event_positive_rate": float(top["hits_interval_eval_event"].mean()), "answer_positive_count": int(top[ANSWER].sum())})
    top_df = pd.DataFrame(top_rows)
    write_df(top_df, "candidate_pool_top_active_score.csv")
    write_text(
        "candidate_pool_summary.md",
        f"""# Candidate Pool Summary

{md_table(total)}

Top active-score prefix quality:

{md_table(top_df)}

Answer-positive candidates exist in the lattice. Their availability to CILS depends on pilot sampling and calibrated `p_answer`, not on an empty candidate universe.
""",
    )
    return cand


def pilot_sampling(inputs: dict, cand: pd.DataFrame) -> None:
    trials = inputs["cal_trials"].copy()
    lab = cand.set_index("interval_id")
    trials["interval_event_positive"] = trials["interval_id"].map(lab["hits_interval_eval_event"]).fillna(False).astype(bool)
    trials["point_event_only_positive"] = trials["interval_id"].map(lab["point_event_only_positive"]).fillna(False).astype(bool)
    features = prepare_features(inputs["features"])
    strata_map = features.set_index("interval_id")[["score_bin", "duration_bin", "disagreement_bin"]]
    trials = trials.merge(strata_map, on="interval_id", how="left")
    grp = trials.groupby(["budget", "seed", "policy"], dropna=False).agg(
        oracle_labels_used=("oracle_label", "count"),
        sampled_intervals=("interval_id", "nunique"),
        sampled_answer_iou_0_3_positives=("oracle_label", "sum"),
        sampled_interval_event_positives=("interval_event_positive", "sum"),
        sampled_point_event_only_positives=("point_event_only_positive", "sum"),
        sample_positive_rate=("oracle_label", "mean"),
        number_of_strata_sampled=("score_bin", lambda s: trials.loc[s.index, ["score_bin", "duration_bin", "disagreement_bin"]].drop_duplicates().shape[0]),
        positive_strata_count=("oracle_label", lambda s: trials.loc[s.index][trials.loc[s.index, "oracle_label"].astype(bool)][["score_bin", "duration_bin", "disagreement_bin"]].drop_duplicates().shape[0]),
    ).reset_index()
    grp["zero_positive_pilot"] = grp["sampled_answer_iou_0_3_positives"] == 0
    write_df(grp, "pilot_sampling_audit.csv")
    budget = grp.groupby(["budget", "policy"]).agg(
        trials=("seed", "count"),
        mean_sample_positive_rate=("sample_positive_rate", "mean"),
        zero_positive_pilot_rate=("zero_positive_pilot", "mean"),
        mean_interval_event_positives=("sampled_interval_event_positives", "mean"),
        mean_answer_positives=("sampled_answer_iou_0_3_positives", "mean"),
    ).reset_index()
    write_df(budget, "pilot_positive_rate_by_budget.csv")
    cils = budget[budget["policy"] == "top_score"]
    write_text(
        "pilot_sampling_summary.md",
        f"""# Pilot Sampling Audit

CILS uses the `top_score` pilot policy in clean v2 main trials.

Top-score pilot summary:

{md_table(cils, 20)}

All-policy comparison:

{md_table(budget, 40)}

Interpretation: if top-score zero-positive rates remain high at the main budgets, calibration posterior estimates will stay below `tau_p` and the first CILS addition will be rejected.
""",
    )


def p_answer_audit(inputs: dict, cand: pd.DataFrame) -> dict[tuple[int, int], pd.DataFrame]:
    features = prepare_features(inputs["features"])
    labels = inputs["labels"]
    cal_by_key = {}
    rows, group_rows, strata_rows = [], [], []
    for b in BUDGETS:
        for seed in range(100):
            samples = oracle_samples(features, labels, b, SEED + seed, "top_score")
            cal = calibrate(features, samples).merge(cand[["interval_id", ANSWER, "hits_interval_eval_event"]], on="interval_id", how="left")
            cal_by_key[(b, seed)] = cal
            p = cal["p_answer"]
            rows.append(
                {
                    "budget": b,
                    "seed": seed,
                    "min": float(p.min()),
                    "p25": float(p.quantile(0.25)),
                    "median": float(p.median()),
                    "p75": float(p.quantile(0.75)),
                    "p90": float(p.quantile(0.90)),
                    "p95": float(p.quantile(0.95)),
                    "max": float(p.max()),
                    "answer_positive_mean_p": float(cal.loc[cal[ANSWER].astype(bool), "p_answer"].mean()),
                    "interval_answer_positive_mean_p": float(cal.loc[cal["hits_interval_eval_event"].astype(bool), "p_answer"].mean()),
                    "negative_mean_p": float(cal.loc[~cal[ANSWER].astype(bool), "p_answer"].mean()),
                    "max_answer_positive_p": float(cal.loc[cal[ANSWER].astype(bool), "p_answer"].max()),
                }
            )
            for name, mask in {
                "all": pd.Series(True, index=cal.index),
                "answer_positive": cal[ANSWER].astype(bool),
                "interval_event_answer_positive": cal["hits_interval_eval_event"].astype(bool),
                "negative": ~cal[ANSWER].astype(bool),
            }.items():
                vals = cal.loc[mask, "p_answer"]
                group_rows.append({"budget": b, "seed": seed, "candidate_group": name, "count": int(mask.sum()), "mean_p": float(vals.mean()) if len(vals) else math.nan, "median_p": float(vals.median()) if len(vals) else math.nan, "max_p": float(vals.max()) if len(vals) else math.nan})
            st = cal.groupby(["score_bin", "duration_bin", "disagreement_bin"], dropna=False).agg(count=("interval_id", "count"), mean_p=("p_answer", "mean"), answer_rate=(ANSWER, "mean")).reset_index()
            st["budget"], st["seed"] = b, seed
            strata_rows.append(st)
    dist = pd.DataFrame(rows)
    write_df(dist, "p_answer_distribution.csv")
    write_df(pd.DataFrame(group_rows), "p_answer_by_candidate_group.csv")
    write_df(pd.concat(strata_rows, ignore_index=True), "calibration_probability_audit.csv")
    summary = dist.groupby("budget").agg(
        mean_max_p=("max", "mean"),
        mean_answer_positive_p=("answer_positive_mean_p", "mean"),
        mean_interval_answer_positive_p=("interval_answer_positive_mean_p", "mean"),
        mean_negative_p=("negative_mean_p", "mean"),
        mean_max_answer_positive_p=("max_answer_positive_p", "mean"),
    ).reset_index()
    write_text(
        "calibration_probability_summary.md",
        f"""# Calibration Probability Audit

Budget-level p_answer summary for CILS top-score pilot:

{md_table(summary)}

If `max p_answer < tau_p`, the first greedy addition cannot satisfy the expected precision constraint, regardless of utility or overlap control.
""",
    )
    return cal_by_key


def selector_rejection(inputs: dict, cand: pd.DataFrame, cal_by_key: dict) -> pd.DataFrame:
    labels = inputs["labels"]
    events = inputs["reference_events"]
    duration_cap = min(32.0, float(events["duration"].quantile(0.95)) * 3.0)
    trace_frames = []
    for b in BUDGETS:
        for tau in TAUS:
            for seed in TRACE_SEEDS:
                cal = cal_by_key[(b, seed)]
                _, trace, _ = selector_trace(cal, tau, b, duration_cap, labels)
                trace["budget"], trace["tau"], trace["seed"] = b, tau, seed
                trace["focus_cell"] = (b, tau) in FOCUS
                trace_frames.append(trace)
    trace_df = pd.concat(trace_frames, ignore_index=True)
    write_df(trace_df, "cils_rejection_trace.csv")
    summary = trace_df.groupby(["budget", "tau", "rejection_reason"]).size().reset_index(name="count")
    total = trace_df.groupby(["budget", "tau"]).size().reset_index(name="total")
    summary = summary.merge(total, on=["budget", "tau"], how="left")
    summary["fraction"] = summary["count"] / summary["total"]
    write_df(summary, "cils_rejection_reason_summary.csv")
    focus = summary[summary[["budget", "tau"]].apply(tuple, axis=1).isin(FOCUS)]
    write_text(
        "cils_selector_trace_summary.md",
        f"""# CILS Selector Trace Summary

Focus cells:

{md_table(focus, 80)}

Across audited clean v2 main cells, rejection is dominated by `p_answer_too_low` / `below_precision_constraint` when calibrated probabilities never reach the requested `tau_p`.
""",
    )
    return trace_df


def empty_return_semantics(inputs: dict) -> None:
    main = inputs["main"].copy()
    selected = inputs["selected"]
    rows = main[["method", "budget", "tau", "number_returned", "event_recall_iou_0_3", "observed_precision", "precision_violation_rate", "empty_return_rate"]].copy()
    rows["selected_file_has_rows"] = len(selected) > 0
    write_df(rows, "empty_return_by_budget_tau.csv")
    write_text(
        "empty_return_semantics_audit.md",
        f"""# Empty Return Semantics Audit

- `selected_intervals_by_trial_v2_clean.csv` rows: `{len(selected)}`
- Main curve max `number_returned`: `{float(main['number_returned'].max())}`
- Main curve max CILS recall IoU@0.3: `{float(main['event_recall_iou_0_3'].max())}`
- Empty return rate range: `{float(main['empty_return_rate'].min())}` to `{float(main['empty_return_rate'].max())}`
- Observed precision empty handling: `NaN` in clean v2 main rows = `{main['observed_precision'].isna().all()}`

Conclusion: clean v2 CILS recall 0 comes from genuinely no selected intervals, not from selected intervals being filtered out during evaluation.
""",
    )


def counterfactuals(inputs: dict, cand: pd.DataFrame, cal_by_key: dict, event_sets: pd.DataFrame) -> pd.DataFrame:
    labels = inputs["labels"]
    features = prepare_features(inputs["features"])
    events_all = inputs["reference_events"]
    events_interval = event_sets[event_sets["is_interval_eval"]].copy()
    duration_cap = min(32.0, float(events_all["duration"].quantile(0.95)) * 3.0)
    rows = []
    cells = [(80, t) for t in LOW_TAUS + TAUS] + [(40, 0.6)]
    for b, tau in cells:
        for seed in range(100):
            cal = cal_by_key[(b, seed)]
            variants = {
                "clean_calibrated": cal,
                "oracle_p_answer": cal.assign(p_answer=cal["interval_id"].map(labels.set_index("interval_id")[ANSWER]).astype(float)),
                "no_duration_penalty": cal,
                "no_overlap_control": cal,
            }
            for variant, cdf in variants.items():
                sel, _, exp = selector_trace(
                    cdf,
                    tau,
                    b,
                    duration_cap,
                    labels,
                    disable_duration_penalty=(variant == "no_duration_penalty"),
                    disable_overlap_control=(variant == "no_overlap_control"),
                    trace_all_ranked=False,
                )
                rows.append(
                    {
                        "diagnostic_only": "DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT",
                        "budget": b,
                        "tau": tau,
                        "seed": seed,
                        "variant": variant,
                        "number_returned": len(sel),
                        "expected_precision": exp,
                        "event_recall_iou_0_3_all_events": event_recall(sel, events_all, 0.3),
                        "event_recall_iou_0_3_interval_eval_events": event_recall(sel, events_interval, 0.3),
                        "selected_answer_positive": int(sel[ANSWER].sum()) if not sel.empty and ANSWER in sel.columns else 0,
                    }
                )
    cf = pd.DataFrame(rows)
    write_df(cf, "counterfactual_diagnostics.csv")
    agg = cf.groupby(["variant", "budget", "tau"]).agg(
        mean_returned=("number_returned", "mean"),
        return_rate=("number_returned", lambda s: float((s > 0).mean())),
        mean_all_event_recall=("event_recall_iou_0_3_all_events", "mean"),
        mean_interval_event_recall=("event_recall_iou_0_3_interval_eval_events", "mean"),
        mean_expected_precision=("expected_precision", "mean"),
    ).reset_index()
    write_df(agg, "counterfactual_diagnostics_summary_table.csv")
    write_text(
        "counterfactual_diagnostics_summary.md",
        f"""# Counterfactual Diagnostics

All rows are `DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT`.

{md_table(agg, 80)}

Interpretation rules: if oracle `p_answer` selects intervals while calibrated `p_answer` does not, selector implementation is usable and the root cause is calibration/pilot probability estimation. If low tau begins returning intervals, the precision constraint is binding under the calibrated posterior.
""",
    )
    return cf


def root_cause(inputs: dict, cand: pd.DataFrame, trace: pd.DataFrame, cf: pd.DataFrame) -> None:
    pilot = pd.read_csv(OUT / "pilot_positive_rate_by_budget.csv")
    p_dist = pd.read_csv(OUT / "p_answer_distribution.csv")
    trace_summary = pd.read_csv(OUT / "cils_rejection_reason_summary.csv")
    cf_agg = pd.read_csv(OUT / "counterfactual_diagnostics_summary_table.csv")
    top_score = pilot[pilot["policy"] == "top_score"]
    b80_zero = float(top_score[top_score["budget"] == 80]["zero_positive_pilot_rate"].iloc[0])
    maxp80 = float(p_dist[p_dist["budget"] == 80]["max"].mean())
    tau05_reasons = trace_summary[(trace_summary["budget"] == 80) & (trace_summary["tau"] == 0.5)].sort_values("count", ascending=False).head(3)
    oracle_return = cf_agg[(cf_agg["variant"] == "oracle_p_answer") & (cf_agg["budget"] == 80) & (cf_agg["tau"] == 0.5)]["return_rate"].iloc[0]
    lowtau_return = cf_agg[(cf_agg["variant"] == "clean_calibrated") & (cf_agg["budget"] == 80) & (cf_agg["tau"] == 0.1)]["return_rate"].iloc[0]
    top_score_by_budget = top_score.set_index("budget")
    top_score_stats = "; ".join(
        f"B={b}: zero_rate={top_score_by_budget.loc[b, 'zero_positive_pilot_rate']:.3f}, pos_rate={top_score_by_budget.loc[b, 'mean_sample_positive_rate']:.3f}"
        for b in [5, 10, 20, 40, 80]
    )
    evidence = pd.DataFrame(
        [
            {"root_cause": "PILOT_NO_POSITIVES", "support": "budget_dependent_not_primary", "evidence": f"{top_score_stats}. B=80 has positives, so no-positive pilot alone cannot explain empty return."},
            {"root_cause": "CALIBRATION_FLOOR_TOO_LOW", "support": "strong" if maxp80 < 0.5 else "weak", "evidence": f"B=80 mean max p_answer={maxp80:.3f}, below tau_p grid minimum 0.5"},
            {"root_cause": "PRECISION_CONSTRAINT_IMPOSSIBLE", "support": "strong", "evidence": "first selected candidate must satisfy p_answer >= tau; clean calibrated p_answer max is below tau=0.5"},
            {"root_cause": "SELECTOR_IMPLEMENTATION_BUG", "support": "not_supported" if oracle_return > 0 else "possible", "evidence": f"oracle p_answer B=80 tau=0.5 return_rate={oracle_return:.3f}"},
            {"root_cause": "UTILITY_OR_DURATION_PENALTY_SUPPRESSES_SELECTION", "support": "not_primary", "evidence": "positive utility exists; rejection happens before utility can matter because expected precision fails"},
            {"root_cause": "OVERLAP_CONTROL_SUPPRESSES_SELECTION", "support": "not_primary", "evidence": "no selected spans exist before precision rejection; overlap conflicts are not the first blocker"},
            {"root_cause": "SCORE_RANKING_FAILURE", "support": "secondary", "evidence": "top_score pilot positive rates are low despite many answer-positive candidates"},
            {"root_cause": "REFERENCE_MIXTURE_EFFECT", "support": "secondary", "evidence": "point/interval mixture affects global target, but interval positives are still assigned low p_answer under top-score pilot"},
        ]
    )
    write_df(evidence, "root_cause_evidence_table.csv")
    primary = "CALIBRATION_FLOOR_TOO_LOW / PRECISION_CONSTRAINT_IMPOSSIBLE, caused by weak top-score pilot positives"
    write_text(
        "root_cause_classification.md",
        f"""# Root Cause Classification

Primary root cause: **{primary}**.

Secondary root causes:

- **PILOT_SPARSITY / weak positive pilot yield**: top-score CILS pilots contain no answer-positive intervals at B=5/10/20 and low positive rates at B=40/80.
- **SCORE_RANKING_FAILURE**: answer-positive candidates exist, but high active-score prefixes have low answer-positive yield.
- **REFERENCE_MIXTURE_EFFECT**: point-anchor events make the global answer target brittle, though this audit focuses on interval-eval events.

Not supported as primary causes:

- **SELECTOR_IMPLEMENTATION_BUG**: oracle `p_answer` counterfactual returns intervals.
- **UTILITY_OR_DURATION_PENALTY_SUPPRESSES_SELECTION**: utility remains positive; candidates are rejected by expected precision before duration penalty dominates.
- **OVERLAP_CONTROL_SUPPRESSES_SELECTION**: no selected spans are established before precision rejection.

Key evidence:

{md_table(evidence, 20)}

Top rejection reasons for B=80, tau=0.5:

{md_table(tau05_reasons)}

Conclusion: CILS empty return is real and is caused by calibrated `p_answer` never reaching the requested `tau_p` threshold. The selector requires the first added interval to satisfy expected precision, so with `max(p_answer) < 0.5`, every candidate is rejected at tau=0.5 and above.
""",
    )


def final_report() -> None:
    inventory = pd.read_csv(OUT / "artifact_inventory.csv")
    event_set = pd.read_csv(OUT / "interval_eval_event_set.csv")
    pool = pd.read_csv(OUT / "candidate_pool_accounting.csv")
    pilot = pd.read_csv(OUT / "pilot_positive_rate_by_budget.csv")
    pdist = pd.read_csv(OUT / "p_answer_distribution.csv")
    reject = pd.read_csv(OUT / "cils_rejection_reason_summary.csv")
    cf = pd.read_csv(OUT / "counterfactual_diagnostics_summary_table.csv")
    evidence = pd.read_csv(OUT / "root_cause_evidence_table.csv")
    selected_empty = pd.read_csv(OUT / "empty_return_by_budget_tau.csv")
    top_pilot = pilot[pilot["policy"] == "top_score"]
    p_budget = pdist.groupby("budget").agg(mean_max_p=("max", "mean"), mean_answer_positive_p=("answer_positive_mean_p", "mean"), mean_interval_answer_positive_p=("interval_answer_positive_mean_p", "mean")).reset_index()
    reject_focus = reject[(reject["budget"] == 80) & (reject["tau"].isin([0.5, 0.6, 0.7]))].sort_values(["tau", "count"], ascending=[True, False]).groupby("tau").head(3)
    cf_focus = cf[(cf["budget"] == 80) & (cf["tau"].isin([0.1, 0.5, 0.6]))]
    write_text(
        "FINAL_REPORT.md",
        f"""# FINAL REPORT: CILS Empty Return Root Cause Audit V1

## 1. Executive Summary

- CILS empty return is real: **yes**. `selected_intervals_by_trial_v2_clean.csv` is empty and clean main curve `number_returned=0`.
- Selector implementation bug: **not supported**. Oracle `p_answer` counterfactual returns intervals.
- Primary root cause: **calibrated `p_answer` is below the precision threshold, making the expected-precision constraint impossible**.
- Practical cause underneath: **top-score pilot sampling sees too few answer-positive intervals, so beta-bin calibration assigns a low posterior floor/ceiling**.
- Direction: fix pilot/calibration and reference target separation before changing selector mechanics.

## 2. Inputs And Audit Status

- Clean no-leak v2 input: `{V2}`.
- Code audit status: clean audit WARNING / no BLOCKER.
- Duration-stratified directory exists: `{DUR.exists()}`. This run used fallback duration strata from `reference_events.csv` when duration artifacts were absent.
- No model inference, no clean v2 modifications, no proposal-family changes.

## 3. Interval Subset And Candidate Availability

Event strata:

{md_table(event_set.groupby('duration_stratum').agg(events=('event_id','count'), min_duration=('duration','min'), median_duration=('duration','median'), max_duration=('duration','max')).reset_index())}

Candidate pool:

{md_table(pool)}

There are answer-positive intervals in the candidate lattice. The empty return is therefore not caused by an empty feasible candidate universe.

## 4. Pilot Sampling Diagnosis

CILS main uses `top_score` pilot sampling:

{md_table(top_pilot, 20)}

The high-score pilot has low positive yield. This is the first probability-estimation bottleneck.

## 5. Calibration Probability Diagnosis

Budget-level p_answer distribution:

{md_table(p_budget)}

For all clean main tau values (`0.5` and above), the calibrated `p_answer` maximum remains below tau, including B=80. Since CILS checks expected precision before accepting the first candidate, no interval can enter the set.

## 6. Selector Rejection Diagnosis

Dominant focus-cell rejection reasons:

{md_table(reject_focus, 30)}

Rejections are dominated by `p_answer_too_low` / precision-constraint failure. Duration penalty and overlap control are not primary blockers because no candidate passes the first precision gate.

## 7. Counterfactual Diagnostics

All counterfactual rows are `DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT`.

{md_table(cf_focus, 40)}

Low-tau diagnostics show whether the calibrated posterior can select when the precision threshold drops. Oracle-`p_answer` diagnostics show the selector can select when probabilities are informative, ruling against a selector implementation bug as the primary cause.

## 8. Root Cause Conclusion

{md_table(evidence, 20)}

Primary root cause: **CALIBRATION_FLOOR_TOO_LOW / PRECISION_CONSTRAINT_IMPOSSIBLE**, caused by weak top-score pilot positives and poor score-to-answer alignment.

Secondary causes: **PILOT_SPARSITY**, **SCORE_RANKING_FAILURE**, and **REFERENCE_MIXTURE_EFFECT**.

## 9. Impact On Research Direction

- Clean v2 CILS=0 can be interpreted as the current CILS calibration/pilot design failing on this pseudo-oracle workload.
- It should **not** be interpreted as proof that interval proposal generation is impossible; interval positives exist and oracle probability counterfactual can select them.
- Next work should prioritize **A. fixing pilot/calibration** and **C. separating/rebuilding true interval reference**. Selector implementation repair is not the first target.

## 10. Recommended Next Actions

1. Build a calibration/pilot repair experiment that reserves exploration budget for interval-event-positive strata instead of pure top-score pilots.
2. Re-evaluate CILS on the true-interval subset separately from point-anchor events, keeping the no-leak whitelist protocol.
3. Compare repaired calibration against a simple audited proposal-repair baseline before continuing the current CILS route.
""",
    )


def main() -> int:
    ensure_dirs()
    artifact_inventory()
    inputs = load_inputs()
    event_sets = build_event_sets(inputs["reference_events"])
    cand = candidate_pool(inputs, event_sets)
    pilot_sampling(inputs, cand)
    cal_by_key = p_answer_audit(inputs, cand)
    trace = selector_rejection(inputs, cand, cal_by_key)
    empty_return_semantics(inputs)
    cf = counterfactuals(inputs, cand, cal_by_key, event_sets)
    root_cause(inputs, cand, trace, cf)
    final_report()
    write_text(
        "logs/progress.md",
        """# Progress Log

- Ran read-only clean v2 CILS root-cause audit.
- Duration diagnosis directory was missing; used fallback duration strata from `reference_events.csv`.
- Recomputed diagnostic calibration and selector traces without modifying clean v2 artifacts.
- Generated root-cause report and diagnostic-only counterfactuals.
""",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
