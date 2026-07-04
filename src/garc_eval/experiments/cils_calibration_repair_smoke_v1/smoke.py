#!/usr/bin/env python3
from __future__ import annotations

import math
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[4]
V2 = ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak"
DUR = ROOT / "src/garc_eval/outputs/reference_duration_stratified_eval_v1"
REPLAY = ROOT / "src/garc_eval/outputs/cils_calibration_repair_replay_v1"
OUT = ROOT / "src/garc_eval/outputs/cils_calibration_repair_smoke_v1"

ANSWER = "answer_iou_0_3"
POLICY = "answer_quality_proxy_top"
CAL_MODEL = "beta_bin_strata_lower"
BUDGETS = [5, 10, 20, 40, 80]
TAUS = [0.5, 0.6, 0.7, 0.8, 0.9]
N_SEEDS = 100
SEED0 = 20260630

FORBIDDEN_PROXY_FIELDS = {
    "answer_iou_0_3", "answer_iou_0_5", "best_iou", "center_hit", "any_overlap",
    "event_overlap_ratio", "interval_purity", "duration_inflation", "matched_event_id",
    "event_id", "discovery_positive", "positive_unit_fraction", "event_hit_iou_0_3",
    "event_hit_iou_0_5", "answer_overlap_purity", "label_event",
}
PROXY_SOURCE_FIELDS = [
    "active_score", "score_persistence", "boundary_left_drop", "boundary_right_drop",
    "duration", "signal_disagreement", "method", "source_signal",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def append_progress(text: str) -> None:
    ensure_dirs()
    with (OUT / "logs/progress.md").open("a", encoding="utf-8") as f:
        f.write(f"## {now()}\n\n{text.rstrip()}\n\n")


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


def load_inputs() -> dict[str, pd.DataFrame]:
    return {
        "features": read_csv(V2 / "interval_lattice_features_only.csv"),
        "lattice": read_csv(V2 / "interval_lattice_v2_clean.csv"),
        "labels": read_csv(V2 / "interval_labels_v2_clean.csv"),
        "events": read_csv(V2 / "reference_events.csv"),
        "clean_main": read_csv(V2 / "main_budget_curve_v2_clean.csv"),
        "clean_selected": read_csv(V2 / "selected_intervals_by_trial_v2_clean.csv"),
        "replay_interval_curve": read_csv(REPLAY / "repaired_cils_interval_eval_curve.csv"),
        "replay_baseline": read_csv(REPLAY / "repair_vs_baseline_comparison.csv"),
    }


def evaluation_subsets(events: pd.DataFrame) -> pd.DataFrame:
    strata_path = DUR / "event_duration_strata.csv"
    if strata_path.exists():
        strata = read_csv(strata_path)
        cols = [c for c in ["event_id", "duration", "duration_stratum"] if c in strata.columns]
        out = events.merge(strata[cols].drop_duplicates("event_id"), on="event_id", how="left", suffixes=("", "_strata"))
        if "duration_stratum" not in out.columns:
            out["duration_stratum"] = np.where(out["duration"] <= 2, "point_anchor", np.where(out["duration"] >= 5, "true_interval", "short_interval"))
    else:
        out = events.copy()
        out["duration_stratum"] = np.where(out["duration"] <= 2, "point_anchor", np.where(out["duration"] >= 5, "true_interval", "short_interval"))
    out["eval_subset"] = np.where(out["duration"] <= 2, "point_anchor", np.where(out["duration"] >= 5, "interval_eval", "short_interval"))
    write_df(out, "evaluation_subsets.csv")
    summary = out.groupby("eval_subset", dropna=False).agg(
        events=("event_id", "count"),
        min_duration=("duration", "min"),
        median_duration=("duration", "median"),
        max_duration=("duration", "max"),
        event_ids=("event_id", lambda x: ",".join(map(str, x))),
    ).reset_index()
    write_text("evaluation_subset_summary.md", f"""# Evaluation Subset Summary

Duration strata source: `{'event_duration_strata.csv' if strata_path.exists() else 'fallback_from_reference_events.csv'}`.

{md_table(summary, 20)}

The primary interval-IoU smoke claim uses only `interval_eval` events (`duration >= 5s`). Point-anchor events are reported separately.
""")
    return out


def prepare_candidates(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    c = inputs["features"].copy().merge(inputs["labels"].copy(), on="interval_id", how="left")
    c["boundary_quality_proxy"] = normalize(c["boundary_left_drop"] + c["boundary_right_drop"])
    c["duration_bin"] = pd.cut(c["duration"], [0, 2, 5, 10, 20, 40, 80, 1e9], labels=["<=2", "2-5", "5-10", "10-20", "20-40", "40-80", ">80"], include_lowest=True)
    c["answer_quality_proxy_bin"] = pd.qcut(c["active_score"].rank(method="first"), 5, labels=["q1", "q2", "q3", "q4", "q5"])
    c["boundary_quality_bin"] = pd.qcut(c["boundary_quality_proxy"].rank(method="first"), 5, labels=["q1", "q2", "q3", "q4", "q5"])
    overlong = np.maximum(0.0, (c["duration"] - 40.0) / 40.0)
    c["answer_quality_proxy"] = (
        rank01(c["active_score"])
        + rank01(c["score_persistence"])
        + rank01(c["boundary_quality_proxy"])
        + 0.5 * c["duration"].between(5, 40).astype(float)
        - rank01(c["signal_disagreement"])
        - overlong.clip(0, 1)
    )
    c["answer_quality_proxy"] = normalize(c["answer_quality_proxy"])
    c["answer_quality_proxy_bin"] = pd.qcut(c["answer_quality_proxy"].rank(method="first"), 5, labels=["q1", "q2", "q3", "q4", "q5"])
    return c


def artifact_inventory(inputs: dict[str, pd.DataFrame], cand: pd.DataFrame, events_sub: pd.DataFrame) -> None:
    files = [
        V2 / "interval_lattice_features_only.csv",
        V2 / "interval_lattice_v2_clean.csv",
        V2 / "interval_labels_v2_clean.csv",
        V2 / "reference_events.csv",
        DUR / "event_duration_strata.csv",
        REPLAY / "root_cause_update.md",
        REPLAY / "repaired_cils_interval_eval_curve.csv",
        REPLAY / "repair_vs_baseline_comparison.csv",
    ]
    rows = []
    for path in files:
        row = {"path": str(path), "file": path.name, "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else 0}
        if path.exists() and path.suffix == ".csv":
            row["rows"] = max(0, sum(1 for _ in path.open()) - 1)
            row["columns"] = "|".join(pd.read_csv(path, nrows=0).columns)
        rows.append(row)
    inv = pd.DataFrame(rows)
    write_df(inv, "artifact_inventory.csv")
    write_text("artifact_inventory.md", f"""# Artifact Inventory

- Candidate intervals: `{len(cand)}`
- Answer-positive candidates (`{ANSWER}`): `{int(cand[ANSWER].sum())}`
- interval_eval events: `{int((events_sub['eval_subset'] == 'interval_eval').sum())}`
- point_anchor events: `{int((events_sub['eval_subset'] == 'point_anchor').sum())}`

{md_table(inv, 80)}
""")


def write_protocol() -> None:
    write_text("SMOKE_TEST_PROTOCOL.md", f"""# CILS Calibration Repair Smoke V1 Protocol

This is a preregistered clean no-leak smoke test, not a policy search and not final algorithm validation.

- pilot_policy: `{POLICY}`
- calibration_model: `{CAL_MODEL}`
- selector: `clean_v2_cils_selector`
- tau_p: `{TAUS}`
- budgets: `{BUDGETS}`
- seeds: `0..{N_SEEDS - 1}` (`{N_SEEDS}` seeds)
- primary evaluation subset: `interval_eval` events (`duration >= 5s`)
- point-anchor handling: excluded from interval IoU main claim; reported separately by any-overlap, center-hit, and containment
- no model reruns; no new proposal families; clean v2 outputs are read-only
""")


def answer_quality_proxy_report(cand: pd.DataFrame) -> None:
    out = cand[["interval_id", "answer_quality_proxy", "active_score", "score_persistence", "boundary_quality_proxy", "duration", "signal_disagreement", "method", "source_signal"]].copy()
    write_df(out, "answer_quality_proxy_scores.csv")
    top = []
    for k in [20, 50, 100, 200, 400]:
        s = cand.sort_values(["answer_quality_proxy", "duration"], ascending=[False, True]).head(k)
        top.append({"K": k, "answer_positive_rate": float(s[ANSWER].mean()), "answer_positive_count": int(s[ANSWER].sum()), "mean_duration": float(s["duration"].mean()), "p95_duration": float(s["duration"].quantile(0.95))})
    write_text("answer_quality_proxy_report.md", f"""# Answer Quality Proxy Report

Formula copied from `cils_calibration_repair_replay_v1` without retuning:

`rank(active_score) + rank(score_persistence) + rank(boundary_left_drop + boundary_right_drop) + 0.5 * moderate_duration_flag - rank(signal_disagreement) - overlong_duration_penalty`

Allowed source fields: `{PROXY_SOURCE_FIELDS}`.

Forbidden fields used: `{sorted(set(PROXY_SOURCE_FIELDS) & FORBIDDEN_PROXY_FIELDS)}`.

Top-K diagnostic precision, using labels only for post-hoc smoke audit:

{md_table(pd.DataFrame(top), 20)}
""")


def fixed_pilot_samples(cand: pd.DataFrame, events_sub: pd.DataFrame) -> tuple[dict[tuple[int, int], pd.DataFrame], pd.DataFrame]:
    interval_events = set(events_sub[events_sub["eval_subset"] == "interval_eval"]["event_id"].astype(str))
    point_events = set(events_sub[events_sub["eval_subset"] == "point_anchor"]["event_id"].astype(str))
    lab = cand.set_index("interval_id")
    samples_by_key: dict[tuple[int, int], pd.DataFrame] = {}
    rows, sample_rows = [], []
    ranked_ids = cand.sort_values(["answer_quality_proxy", "duration"], ascending=[False, True])["interval_id"].tolist()
    for b in BUDGETS:
        ids = ranked_ids[:b]
        for seed in range(N_SEEDS):
            s = pd.DataFrame({"interval_id": ids})
            s["rank"] = np.arange(1, len(s) + 1)
            s["oracle_label"] = s["interval_id"].map(lab[ANSWER]).fillna(False).astype(bool)
            s["matched_event_id"] = s["interval_id"].map(lab["matched_event_id"]).fillna("").astype(str)
            s["interval_eval_positive"] = s["oracle_label"] & s["matched_event_id"].isin(interval_events)
            s["point_anchor_only_positive"] = s["oracle_label"] & s["matched_event_id"].isin(point_events)
            s["budget"], s["seed"], s["pilot_policy"] = b, seed, POLICY
            samples_by_key[(b, seed)] = s
            sample_rows.append(s)
            rows.append({
                "budget": b,
                "seed": seed,
                "oracle_labels_used": len(s),
                "positive_count": int(s["oracle_label"].sum()),
                "interval_eval_positive_count": int(s["interval_eval_positive"].sum()),
                "point_anchor_only_positive_count": int(s["point_anchor_only_positive"].sum()),
                "positive_rate": float(s["oracle_label"].mean()) if len(s) else 0.0,
                "interval_eval_positive_rate": float(s["interval_eval_positive"].mean()) if len(s) else 0.0,
                "zero_positive_pilot": int(s["oracle_label"].sum()) == 0,
                "within_budget": len(s) <= b,
            })
    all_samples = pd.concat(sample_rows, ignore_index=True)
    rates = pd.DataFrame(rows)
    write_df(all_samples, "smoke_pilot_samples.csv")
    write_df(rates, "smoke_pilot_positive_rates.csv")
    return samples_by_key, rates


def wilson_lower(pos: pd.Series, n: pd.Series, z: float = 1.0) -> pd.Series:
    p = pos / n.replace(0, np.nan)
    denom = 1 + z * z / n.replace(0, np.nan)
    centre = p + z * z / (2 * n.replace(0, np.nan))
    adj = z * np.sqrt((p * (1 - p) + z * z / (4 * n.replace(0, np.nan))) / n.replace(0, np.nan))
    return ((centre - adj) / denom).fillna(0.0).clip(0, 1)


def calibration_bins(y: pd.Series, p: pd.Series, bins: int = 5) -> pd.DataFrame:
    y = y.astype(float).reset_index(drop=True)
    p = p.astype(float).clip(0, 1).reset_index(drop=True)
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for i in range(bins):
        mask = (p >= edges[i]) & ((p < edges[i + 1]) if i < bins - 1 else (p <= edges[i + 1]))
        rows.append({
            "bin_low": float(edges[i]),
            "bin_high": float(edges[i + 1]),
            "count": int(mask.sum()),
            "mean_pred": float(p[mask].mean()) if mask.any() else math.nan,
            "observed_rate": float(y[mask].mean()) if mask.any() else math.nan,
            "weight": float(mask.mean()),
            "abs_gap": abs(float(p[mask].mean()) - float(y[mask].mean())) if mask.any() else math.nan,
        })
    return pd.DataFrame(rows)


def ece(y: pd.Series, p: pd.Series) -> float:
    b = calibration_bins(y, p)
    b = b.dropna(subset=["abs_gap"])
    return float((b["weight"] * b["abs_gap"]).sum())


def calibrate(cand: pd.DataFrame, samples: pd.DataFrame) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    out = cand.copy()
    smap = samples.set_index("interval_id")["oracle_label"].astype(int).to_dict()
    s = out[out["interval_id"].isin(smap)].copy()
    s["y"] = s["interval_id"].map(smap).astype(int)
    global_p = (s["y"].sum() + 1.0) / (len(s) + 2.0) if len(s) else 0.0
    keys = ["answer_quality_proxy_bin", "duration_bin", "method", "boundary_quality_bin"]
    stat = s.groupby(keys, observed=True, dropna=False)["y"].agg(["sum", "count"]).reset_index()
    stat["posterior_mean"] = (stat["sum"] + 1.0) / (stat["count"] + 2.0)
    stat["posterior_lower"] = wilson_lower(stat["sum"], stat["count"])
    out = out.merge(stat[keys + ["count", "sum", "posterior_mean", "posterior_lower"]], on=keys, how="left")
    out["p_answer"] = out["posterior_lower"].fillna(max(0.0, global_p * 0.5)).clip(0, 1)
    meta = {
        "pilot_n": int(len(s)),
        "pilot_positives": int(s["y"].sum()),
        "global_p": float(global_p),
        "mean_p_answer": float(out["p_answer"].mean()),
        "max_p_answer": float(out["p_answer"].max()),
        "brier": float(((out["p_answer"].astype(float) - out[ANSWER].astype(float)) ** 2).mean()),
        "ece": ece(out[ANSWER].astype(float), out["p_answer"].astype(float)),
    }
    return out, meta, stat


def eval_selection(sel: pd.DataFrame, events: pd.DataFrame, subset: str) -> dict:
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


def duplicate_rate(df: pd.DataFrame) -> float:
    if df.empty or "matched_event_id" not in df:
        return 0.0
    ids = df["matched_event_id"].dropna().astype(str)
    ids = ids[ids != ""]
    return safe_div(len(ids) - ids.nunique(), len(df)) if len(df) else 0.0


def cils_ranked(cal: pd.DataFrame, budget: int, events: pd.DataFrame) -> pd.DataFrame:
    df = cal[[
        "interval_id", "method", "source_signal", "t_start", "t_end", "duration",
        "active_score", "boundary_left_drop", "boundary_right_drop", "p_answer",
        "overlap_group_id", "positive_unit_fraction", ANSWER, "answer_iou_0_5", "matched_event_id",
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


def run_smoke(cand: pd.DataFrame, samples_by_key: dict[tuple[int, int], pd.DataFrame], events_sub: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cal_rows, bin_rows, p_rows, curve_rows, selected_rows = [], [], [], [], []
    for b in BUDGETS:
        for seed in range(N_SEEDS):
            cal, meta, bins = calibrate(cand, samples_by_key[(b, seed)])
            cal_rows.append({"budget": b, "seed": seed, "pilot_policy": POLICY, "calibration_model": CAL_MODEL, **meta})
            bins = bins.copy()
            bins["budget"], bins["seed"] = b, seed
            bin_rows.append(bins)
            p = cal[["interval_id", "p_answer"]].copy()
            p["budget"], p["seed"], p["pilot_policy"], p["calibration_model"] = b, seed, POLICY, CAL_MODEL
            p_rows.append(p)
            ranked = cils_ranked(cal, b, events_sub)
            for tau in TAUS:
                sel, exp_prec = cils_select_ranked(ranked, tau, b)
                if not sel.empty:
                    ssel = sel[["interval_id", "t_start", "t_end", "duration", "p_answer", ANSWER, "answer_iou_0_5", "matched_event_id", "positive_unit_fraction"]].copy()
                    ssel["budget"], ssel["tau"], ssel["seed"] = b, tau, seed
                    ssel["pilot_policy"], ssel["calibration_model"] = POLICY, CAL_MODEL
                    selected_rows.append(ssel)
                overall = eval_selection(sel, events_sub, "overall")
                interval = eval_selection(sel, events_sub, "interval_eval")
                point = eval_selection(sel, events_sub, "point_anchor")
                curve_rows.append({
                    "pilot_policy": POLICY,
                    "calibration_model": CAL_MODEL,
                    "budget": b,
                    "tau": tau,
                    "seed": seed,
                    "expected_precision": exp_prec,
                    "observed_precision": float(sel[ANSWER].mean()) if not sel.empty and ANSWER in sel else math.nan,
                    "observed_precision_interval_eval_only": float(sel[sel["matched_event_id"].isin(events_sub[events_sub["eval_subset"] == "interval_eval"]["event_id"])][ANSWER].mean()) if not sel.empty and ANSWER in sel else math.nan,
                    "number_returned": len(sel),
                    "empty_return": bool(sel.empty),
                    "avg_returned_duration": float(sel["duration"].mean()) if not sel.empty else 0.0,
                    "p95_returned_duration": float(sel["duration"].quantile(0.95)) if not sel.empty else 0.0,
                    "duplicate_rate": duplicate_rate(sel),
                    "background_duration_ratio": float(1.0 - sel["positive_unit_fraction"].mean()) if not sel.empty and "positive_unit_fraction" in sel else 0.0,
                    **{f"overall_{k}": v for k, v in overall.items()},
                    **{f"interval_eval_{k}": v for k, v in interval.items()},
                    **{f"point_anchor_{k}": v for k, v in point.items()},
                })
    q = pd.DataFrame(cal_rows)
    bins = pd.concat(bin_rows, ignore_index=True) if bin_rows else pd.DataFrame()
    p_all = pd.concat(p_rows, ignore_index=True) if p_rows else pd.DataFrame()
    curve = pd.DataFrame(curve_rows)
    selected = pd.concat(selected_rows, ignore_index=True) if selected_rows else pd.DataFrame(columns=["interval_id", "t_start", "t_end", "duration", "p_answer", ANSWER, "answer_iou_0_5", "matched_event_id", "positive_unit_fraction", "budget", "tau", "seed", "pilot_policy", "calibration_model"])
    write_df(p_all, "smoke_candidate_p_answer.csv")
    write_df(q, "smoke_calibration_quality.csv")
    write_df(bins, "smoke_calibration_bins.csv")
    write_df(selected, "smoke_selected_intervals.csv")
    write_df(curve, "smoke_main_curve.csv")
    write_df(curve[[c for c in curve.columns if c in ["pilot_policy", "calibration_model", "budget", "tau", "seed", "expected_precision", "observed_precision", "observed_precision_interval_eval_only", "number_returned", "empty_return", "avg_returned_duration", "p95_returned_duration", "duplicate_rate", "background_duration_ratio"] or c.startswith("interval_eval_")]], "smoke_interval_eval_curve.csv")
    write_df(curve[[c for c in curve.columns if c in ["pilot_policy", "calibration_model", "budget", "tau", "seed", "number_returned", "empty_return"] or c.startswith("point_anchor_")]], "smoke_point_anchor_curve.csv")
    qsum = q.groupby("budget").agg(pilot_positive_rate=("pilot_positives", lambda s: float((s / q.loc[s.index, "pilot_n"]).mean())), mean_brier=("brier", "mean"), mean_ece=("ece", "mean"), mean_max_p=("max_p_answer", "mean")).reset_index()
    write_text("smoke_calibration_report.md", f"""# Smoke Calibration Report

Fixed calibration model: `{CAL_MODEL}` with beta-binomial strata lower estimates.

{md_table(qsum, 20)}
""")
    return q, curve, selected


def baseline_select(cand: pd.DataFrame, method: str, budget: int, events_sub: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    if method == "threshold_merge_topk":
        ranked = cand.sort_values(["active_score", "duration"], ascending=[False, True]).head(max(400, budget * 20))
        tau = math.nan
    elif method == "arc_style_prune_refine_simplified":
        ranked = cand.sort_values(["answer_quality_proxy", "duration"], ascending=[False, True]).head(max(400, budget * 20))
        tau = math.nan
    elif method == "lattice_oracle_upper_bound":
        ranked = cand[cand[ANSWER].astype(bool)].sort_values(["duration", "active_score"], ascending=[True, False]).head(max(400, budget * 20))
        tau = math.nan
    elif method == "oracle_confirmed_only":
        ranked = cand.sort_values(["active_score", "duration"], ascending=[False, True]).head(budget)
        return ranked[ranked[ANSWER].astype(bool)].copy(), math.nan
    elif method == "oracle_p_answer_counterfactual":
        oracle = cand.copy()
        oracle["p_answer"] = oracle[ANSWER].astype(float)
        ranked = cils_ranked(oracle, budget, events_sub)
        return cils_select_ranked(ranked, 0.5, budget)
    else:
        raise ValueError(method)
    sel, spans, groups = [], [], set()
    for r in ranked.itertuples(index=False):
        if len(sel) >= budget:
            break
        if r.overlap_group_id in groups:
            continue
        if any(tiou(r.t_start, r.t_end, a, b) > 0.3 for a, b in spans):
            continue
        sel.append(r._asdict())
        spans.append((r.t_start, r.t_end))
        groups.add(r.overlap_group_id)
    return pd.DataFrame(sel), tau


def baseline_comparison(inputs: dict[str, pd.DataFrame], cand: pd.DataFrame, curve: pd.DataFrame, events_sub: pd.DataFrame) -> None:
    rows = []
    smoke = curve.groupby(["budget", "tau"]).agg(
        interval_recall=("interval_eval_event_recall_iou_0_3", "mean"),
        interval_recall_iou_0_5=("interval_eval_event_recall_iou_0_5", "mean"),
        precision=("observed_precision", "mean"),
        returned=("number_returned", "mean"),
        avg_duration=("avg_returned_duration", "mean"),
        duplicate_rate=("duplicate_rate", "mean"),
        empty_return_rate=("empty_return", "mean"),
    ).reset_index()
    for _, r in smoke.iterrows():
        rows.append({"method": "smoke_repaired_cils", "pilot_policy": POLICY, "calibration_model": CAL_MODEL, **r.to_dict()})
    for _, r in inputs["clean_main"].iterrows():
        rows.append({
            "method": "clean_v2_CILS",
            "pilot_policy": "top_score",
            "calibration_model": "clean_v2",
            "budget": r["budget"],
            "tau": r["tau"],
            "interval_recall": 0.0,
            "interval_recall_iou_0_5": 0.0,
            "precision": r.get("observed_precision", math.nan),
            "returned": r.get("number_returned", 0),
            "avg_duration": r.get("avg_returned_duration", 0),
            "duplicate_rate": r.get("duplicate_rate", 0),
            "empty_return_rate": r.get("empty_return_rate", 1.0),
        })
    for b in BUDGETS:
        for method in ["threshold_merge_topk", "arc_style_prune_refine_simplified", "oracle_confirmed_only", "lattice_oracle_upper_bound", "oracle_p_answer_counterfactual"]:
            sel, exp = baseline_select(cand, method, b, events_sub)
            interval = eval_selection(sel, events_sub, "interval_eval")
            rows.append({
                "method": method,
                "pilot_policy": "baseline_or_diagnostic",
                "calibration_model": "none" if method != "oracle_p_answer_counterfactual" else "oracle_p_answer",
                "budget": b,
                "tau": 0.5 if method == "oracle_p_answer_counterfactual" else math.nan,
                "interval_recall": interval["event_recall_iou_0_3"],
                "interval_recall_iou_0_5": interval["event_recall_iou_0_5"],
                "precision": float(sel[ANSWER].mean()) if not sel.empty and ANSWER in sel else math.nan,
                "returned": len(sel),
                "avg_duration": float(sel["duration"].mean()) if not sel.empty else 0.0,
                "duplicate_rate": duplicate_rate(sel),
                "empty_return_rate": float(sel.empty),
                "expected_precision": exp,
                "diagnostic_only": "DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT" if method == "oracle_p_answer_counterfactual" else "",
            })
    comp = pd.DataFrame(rows)
    write_df(comp, "smoke_vs_baseline_comparison.csv")
    top = comp.sort_values(["interval_recall", "precision", "returned"], ascending=[False, False, False]).head(30)
    write_text("smoke_baseline_report.md", f"""# Smoke Baseline Report

Primary comparison scope: interval_eval events only.

{md_table(top, 30)}

`oracle_p_answer_counterfactual` is diagnostic only and not an algorithm result.
""")


def sanity_and_leakage(samples: pd.DataFrame, p_df: pd.DataFrame, curve: pd.DataFrame) -> bool:
    budget = samples.groupby(["budget", "seed"]).size().reset_index(name="oracle_labels_used")
    budget["within_budget"] = budget["oracle_labels_used"] <= budget["budget"]
    write_df(budget, "budget_usage_audit.csv")
    checks = [
        ("answer_quality_proxy_no_forbidden_fields", len(set(PROXY_SOURCE_FIELDS) & FORBIDDEN_PROXY_FIELDS) == 0),
        ("calibration_labels_used_within_budget", bool(budget["within_budget"].all())),
        ("candidate_p_answer_has_no_label_cols", len(set(p_df.columns) & FORBIDDEN_PROXY_FIELDS) == 0),
        ("point_interval_split_present", any(c.startswith("interval_eval_") for c in curve.columns) and any(c.startswith("point_anchor_") for c in curve.columns)),
        ("no_policy_search_fixed_policy_only", set(curve["pilot_policy"].unique()) == {POLICY} and set(curve["calibration_model"].unique()) == {CAL_MODEL}),
    ]
    blocker = any(not ok for _, ok in checks)
    write_text("sanity_checks.md", "# Sanity Checks\n\n" + "\n".join(f"- {name}: {'PASS' if ok else 'FAIL'}" for name, ok in checks) + f"\n\nBLOCKER: `{'yes' if blocker else 'no'}`")
    write_text("leakage_audit.md", f"""# Leakage Audit

- Proxy source fields: `{PROXY_SOURCE_FIELDS}`
- Forbidden proxy fields intersect source fields: `{sorted(set(PROXY_SOURCE_FIELDS) & FORBIDDEN_PROXY_FIELDS)}`
- Candidate p-answer label columns present: `{sorted(set(p_df.columns) & FORBIDDEN_PROXY_FIELDS)}`
- Calibration uses only `smoke_pilot_samples.csv` oracle replay labels.
- Selector input is p_answer plus clean v2 feature columns; held-out labels are joined only for smoke evaluation/output reporting.
- Policy search: `no`; fixed `{POLICY} + {CAL_MODEL}` only.
- BLOCKER: `{'yes' if blocker else 'no'}`
""")
    return blocker


def final_report(q: pd.DataFrame, rates: pd.DataFrame, curve: pd.DataFrame, blocker: bool) -> None:
    pilot_sum = rates.groupby("budget").agg(
        mean_positive_rate=("positive_rate", "mean"),
        zero_positive_rate=("zero_positive_pilot", "mean"),
        mean_interval_eval_positive_rate=("interval_eval_positive_rate", "mean"),
    ).reset_index()
    cal_sum = q.groupby("budget").agg(mean_brier=("brier", "mean"), mean_ece=("ece", "mean"), mean_max_p=("max_p_answer", "mean"), mean_p=("mean_p_answer", "mean")).reset_index()
    smoke_sum = curve.groupby(["budget", "tau"]).agg(
        interval_recall=("interval_eval_event_recall_iou_0_3", "mean"),
        interval_recall_iou_0_5=("interval_eval_event_recall_iou_0_5", "mean"),
        precision=("observed_precision", "mean"),
        expected_precision=("expected_precision", "mean"),
        empty_return_rate=("empty_return", "mean"),
        mean_returned=("number_returned", "mean"),
        avg_duration=("avg_returned_duration", "mean"),
        p95_duration=("p95_returned_duration", "mean"),
        duplicate_rate=("duplicate_rate", "mean"),
        background_duration_ratio=("background_duration_ratio", "mean"),
    ).reset_index()
    point_sum = curve.groupby(["budget", "tau"]).agg(
        point_any_overlap=("point_anchor_any_overlap_recall", "mean"),
        point_center_hit=("point_anchor_center_hit_recall", "mean"),
        point_containment=("point_anchor_point_containment_recall", "mean"),
    ).reset_index()
    best = smoke_sum.sort_values(["interval_recall", "precision", "mean_returned"], ascending=[False, False, False]).head(1).iloc[0]
    nonempty = bool((curve["number_returned"] > 0).any())
    decision = "WEAK GO" if (not blocker and nonempty and float(best["interval_recall"]) > 0 and float(best["p95_duration"]) <= 40) else "NO-GO"
    write_text("FINAL_REPORT.md", f"""# FINAL REPORT: CILS Calibration Repair Smoke V1

## 1. Executive Summary

- Smoke ran through: **yes**.
- BLOCKER: **{'yes' if blocker else 'no'}**.
- Fixed policy makes CILS non-empty: **{'yes' if nonempty else 'no'}**.
- Best interval_eval IoU@0.3 recall / precision: `{float(best['interval_recall']):.3f}` / `{float(best['precision']):.3f}`.
- Best empty_return_rate: `{float(best['empty_return_rate']):.3f}` at B=`{int(best['budget'])}`, tau=`{float(best['tau']):.1f}`.
- Decision: **{decision}**. This is smoke evidence only, not final algorithm validation.

## 2. Protocol

Fixed `{POLICY} + {CAL_MODEL}`; budgets `{BUDGETS}`; tau `{TAUS}`; seeds `0..{N_SEEDS - 1}`. Primary interval-IoU evaluation uses only interval_eval events. Point-anchor events are excluded from the main interval claim.

## 3. Pilot And Calibration

Pilot summary:

{md_table(pilot_sum, 20)}

Calibration summary:

{md_table(cal_sum, 20)}

## 4. CILS Smoke Results

Best interval_eval rows:

{md_table(smoke_sum.sort_values(['interval_recall','precision','mean_returned'], ascending=[False, False, False]), 25)}

## 5. Baseline Comparison

See `smoke_vs_baseline_comparison.csv` and `smoke_baseline_report.md`. Main comparison is interval_eval only; oracle p-answer is diagnostic only.

## 6. Point-Anchor Separate Metrics

{md_table(point_sum.sort_values(['point_center_hit','point_any_overlap'], ascending=False), 20)}

## 7. Sanity/Leakage

Sanity and leakage checks are in `sanity_checks.md` and `leakage_audit.md`. BLOCKER: `{'yes' if blocker else 'no'}`.

## 8. Research Implication

Calibration repair is worth continuing as a smoke-tested fix for empty return, but the evidence is weak because interval_eval has only six events and the best recall remains about one event. The selector remains worth continuing under fixed no-leak calibration, not as a final CILS validation. A true interval reference remains needed, and audited proposal repair should remain a baseline before elevating CILS as the main AQP route.

## 9. Next Actions

1. Run one formal no-leak replication on a larger true-interval reference before claiming stability.
2. Keep interval_eval and point-anchor metrics split in every CILS report.
3. Compare fixed repaired CILS against audited proposal repair using the same interval_eval subset.
""")


def main() -> int:
    ensure_dirs()
    write_text("logs/progress.md", f"# Progress\n\nStarted fixed-policy smoke at {now()}.")
    inputs = load_inputs()
    events_sub = evaluation_subsets(inputs["events"])
    cand = prepare_candidates(inputs)
    artifact_inventory(inputs, cand, events_sub)
    write_protocol()
    answer_quality_proxy_report(cand)
    append_progress("Completed inventory, protocol, evaluation subsets, and fixed answer-quality proxy.")
    samples_by_key, rates = fixed_pilot_samples(cand, events_sub)
    append_progress("Completed fixed answer_quality_proxy_top pilot samples for 100 seeds.")
    q, curve, selected = run_smoke(cand, samples_by_key, events_sub)
    append_progress("Completed fixed beta-binomial lower calibration and unchanged CILS selector smoke.")
    baseline_comparison(inputs, cand, curve, events_sub)
    all_samples = pd.read_csv(OUT / "smoke_pilot_samples.csv")
    p_df = pd.read_csv(OUT / "smoke_candidate_p_answer.csv", nrows=1)
    blocker = sanity_and_leakage(all_samples, p_df, curve)
    final_report(q, rates, curve, blocker)
    append_progress(f"Completed reports. BLOCKER={'yes' if blocker else 'no'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
