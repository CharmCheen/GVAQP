#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from garc_eval.metrics.craq_lite_metrics import Interval, duplicate_rate as metric_duplicate_rate
from garc_eval.metrics.craq_lite_metrics import duration_inflation as metric_duration_inflation
from garc_eval.metrics.craq_lite_metrics import event_recall as metric_event_recall
from garc_eval.metrics.craq_lite_metrics import interval_iou

V2 = ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak"
REPLAY = ROOT / "src/garc_eval/outputs/cils_calibration_repair_replay_v1"
SMOKE = ROOT / "src/garc_eval/outputs/cils_calibration_repair_smoke_v1"

ANSWER = "answer_iou_0_3"
BUDGETS_FULL = [20, 40, 80, 160]
BUDGETS_SMOKE = [20, 40, 80]
PRECISION_TARGETS = [0.8, 0.9]
CILS_TAUS = [0.5, 0.6, 0.7]
IOU_THRESHOLDS = [0.3, 0.5]
SEEDS_FULL = list(range(100))
SEEDS_SMOKE = list(range(10))
SEEDS_PATCH_SMOKE = list(range(20))
BUDGETS_PATCH_SMOKE = [80, 160]
PATCH_SMOKE_METHODS = [
    "cils_craq_lite",
    "audited_proposal_repair",
    "oracle_confirmed_only",
    "lattice_oracle_upper_bound",
]
SEED0 = 20260630


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_cmd(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.strip()


def md_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    d = df.head(max_rows).copy()
    lines = ["| " + " | ".join(map(str, d.columns)) + " |", "| " + " | ".join(["---"] * len(d.columns)) + " |"]
    for _, row in d.iterrows():
        vals = []
        for c in d.columns:
            v = row[c]
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


def rank01(s: pd.Series) -> pd.Series:
    return s.rank(method="average", ascending=True, pct=True).fillna(0.0)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def to_intervals(df: pd.DataFrame, event_id_col: str | None = None) -> list[Interval]:
    if df.empty:
        return []
    out = []
    for r in df.itertuples(index=False):
        eid = getattr(r, event_id_col) if event_id_col and hasattr(r, event_id_col) else None
        out.append(Interval(float(r.t_start), float(r.t_end), None if pd.isna(eid) else str(eid)))
    return out


def load_inputs() -> dict[str, pd.DataFrame]:
    return {
        "features": pd.read_csv(V2 / "interval_lattice_features_only.csv"),
        "lattice": pd.read_csv(V2 / "interval_lattice_v2_clean.csv"),
        "labels": pd.read_csv(V2 / "interval_labels_v2_clean.csv"),
        "reference": pd.read_csv(V2 / "reference_events.csv"),
        "clean_main": pd.read_csv(V2 / "main_budget_curve_v2_clean.csv"),
    }


def prepare_candidates(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    c = inputs["features"].merge(inputs["labels"], on="interval_id", how="left")
    c["boundary_quality_proxy"] = normalize(c["boundary_left_drop"] + c["boundary_right_drop"])
    c["duration_bin"] = pd.cut(c["duration"], [0, 2, 5, 10, 20, 40, 80, 1e9], labels=["<=2", "2-5", "5-10", "10-20", "20-40", "40-80", ">80"], include_lowest=True)
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
    c["boundary_quality_bin"] = pd.qcut(c["boundary_quality_proxy"].rank(method="first"), 5, labels=["q1", "q2", "q3", "q4", "q5"])
    return c


def repo_inventory(run_dir: Path) -> None:
    patterns = [
        "src/garc_eval/experiments/*cils*",
        "src/garc_eval/experiments/*interval*",
        "src/garc_eval/experiments/*craq*",
        "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/*",
        "src/garc_eval/outputs/cils_calibration_repair_smoke_v1/*",
        "src/garc_eval/metrics/*",
        "src/garc_eval/tests/*",
    ]
    found: list[str] = []
    for pat in patterns:
        found.extend(str(p.relative_to(ROOT)) for p in ROOT.glob(pat) if p.is_file() or p.is_dir())
    commands = [
        "bash src/garc_eval/experiments/cils_calibration_repair_smoke_v1/run_all.sh",
        "python src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py --smoke",
        "pytest src/garc_eval/tests/test_craq_lite_metrics.py",
    ]
    missing = [
        "No human-adjudicated reference set found; using VLM-defined pseudo-oracle clean v2 reference.",
        "No >=20 true-interval-event reference in current clean v2 artifact.",
        "No standalone production CRAQ-lite guarantee layer found; this run is an evaluation wrapper.",
    ]
    write(
        run_dir / "repo_inventory.md",
        "# Repository Inventory\n\n"
        "## Relevant Scripts/Data/Configs\n\n"
        + "\n".join(f"- `{x}`" for x in sorted(set(found))[:300])
        + "\n\n## Existing Commands Discovered\n\n"
        + "\n".join(f"- `{c}`" for c in commands)
        + "\n\n## Missing Pieces\n\n"
        + "\n".join(f"- {m}" for m in missing)
        + "\n",
    )


def reference_audit(ref: pd.DataFrame, run_dir: Path) -> pd.DataFrame:
    rows = []
    for r in ref.itertuples(index=False):
        dur = float(r.duration)
        is_point = dur <= 2.0
        is_interval = dur >= 5.0
        notes = []
        if not is_interval and not is_point:
            notes.append("ambiguous_short_interval_2_to_5s")
        if is_point:
            notes.append("point_or_anchor_duration_le_2s")
        rows.append(
            {
                "event_id": r.event_id,
                "video_id": r.video_id,
                "t_start": float(r.t_start),
                "t_end": float(r.t_end),
                "duration": dur,
                "event_type": getattr(r, "event_type", ""),
                "boundary_confidence": "pseudo_oracle_duration_rule_interval" if is_interval else "point_anchor_or_ambiguous",
                "is_interval_event": int(is_interval),
                "is_point_anchor": int(is_point),
                "source_file": str(V2 / "reference_events.csv"),
                "notes": ";".join(notes),
            }
        )
    audit = pd.DataFrame(rows)
    audit.to_csv(run_dir / "reference_audit.csv", index=False)
    intervals = audit[audit["is_interval_event"] == 1]
    point = audit[audit["is_point_anchor"] == 1]
    amb = audit[(audit["is_interval_event"] == 0) & (audit["is_point_anchor"] == 0)]
    gate = len(intervals) >= 20
    desc = intervals["duration"].describe().to_frame("duration").reset_index() if not intervals.empty else pd.DataFrame()
    write(
        run_dir / "reference_audit_summary.md",
        f"""# Reference Audit Summary

- Total reference events: `{len(audit)}`
- True interval events: `{len(intervals)}`
- Point/anchor events: `{len(point)}`
- Ambiguous events: `{len(amb)}`
- Minimum gate of 20 true interval events passed: **{'yes' if gate else 'no'}**
- Conclusion status: **{'eligible for stronger evaluation' if gate else 'diagnostic only'}**

Duration distribution for true interval events:

{md_table(desc, 20)}
""",
    )
    return audit


def event_df(reference_audit_df: pd.DataFrame) -> pd.DataFrame:
    return reference_audit_df[reference_audit_df["is_interval_event"] == 1].copy()


def nms(df: pd.DataFrame, limit: int, iou_threshold: float = 0.3) -> pd.DataFrame:
    selected = []
    spans = []
    for r in df.itertuples(index=False):
        if len(selected) >= limit:
            break
        if any(interval_iou(Interval(float(r.t_start), float(r.t_end)), Interval(a, b)) > iou_threshold for a, b in spans):
            continue
        selected.append(r._asdict())
        spans.append((float(r.t_start), float(r.t_end)))
    return pd.DataFrame(selected)


def fixed_window_topk(cand: pd.DataFrame, budget: int, seed: int) -> pd.DataFrame:
    df = cand[cand["method"].eq("fixed_window")].sort_values(["active_score", "duration"], ascending=[False, True])
    return nms(df, budget)


def threshold_merge(cand: pd.DataFrame, budget: int, seed: int) -> pd.DataFrame:
    df = cand[cand["method"].astype(str).str.contains("threshold_merge", na=False)].sort_values(["active_score", "duration"], ascending=[False, True])
    if df.empty:
        df = cand.sort_values(["active_score", "duration"], ascending=[False, True])
    return nms(df, budget)


def arc_style(cand: pd.DataFrame, budget: int, seed: int) -> pd.DataFrame:
    mask = cand["method"].astype(str).str.contains("boundary_refined|signal_peak|threshold_merge", regex=True, na=False)
    df = cand[mask].sort_values(["answer_quality_proxy", "duration"], ascending=[False, True])
    if df.empty:
        df = cand.sort_values(["answer_quality_proxy", "duration"], ascending=[False, True])
    return nms(df, budget)


def oracle_confirmed_only(cand: pd.DataFrame, budget: int, seed: int) -> pd.DataFrame:
    probed = cand.sort_values(["active_score", "duration"], ascending=[False, True]).head(budget)
    return probed[probed[ANSWER].astype(bool)].copy()


def audited_proposal_repair(cand: pd.DataFrame, events: pd.DataFrame, budget: int, seed: int, trace: list[dict]) -> pd.DataFrame:
    rng = np.random.default_rng(SEED0 + seed)
    base_budget = max(1, budget // 2)
    audit_budget = max(0, budget - base_budget)
    base = arc_style(cand, base_budget, seed)
    covered = [(float(r.t_start), float(r.t_end)) for r in base.itertuples(index=False)]
    t_min, t_max = float(cand["t_start"].min()), float(cand["t_end"].max())
    centers = np.arange(t_min + 1.0, t_max, 2.0)
    outside = [c for c in centers if not any(a <= c <= b for a, b in covered)]
    if len(outside) > audit_budget:
        outside = list(rng.choice(outside, size=audit_budget, replace=False))
    repairs = []
    for rank, c in enumerate(outside):
        win = Interval(float(c - 1.0), float(c + 1.0))
        hit = False
        for ev in events.itertuples(index=False):
            if interval_iou(win, Interval(ev.t_start, ev.t_end, ev.event_id)) > 0 or (ev.t_start <= c <= ev.t_end):
                hit = True
                break
        trace.append({"method": "audited_proposal_repair", "budget": budget, "seed": seed, "audit_rank": rank + 1, "audit_center": c, "oracle_positive": hit})
        if hit:
            nearby = cand[(cand["t_start"] <= c) & (cand["t_end"] >= c)].copy()
            if nearby.empty:
                nearby = cand.iloc[[int(np.argmin(np.abs(((cand["t_start"] + cand["t_end"]) / 2) - c)))]].copy()
            repaired = nearby.sort_values(["answer_quality_proxy", "duration"], ascending=[False, True]).head(1)
            repairs.append(repaired)
    combined = pd.concat([base] + repairs, ignore_index=True) if repairs else base.copy()
    combined = combined.sort_values(["answer_quality_proxy", "active_score"], ascending=[False, False])
    return nms(combined, budget)


def wilson_lower(pos: pd.Series, n: pd.Series, z: float = 1.0) -> pd.Series:
    p = pos / n.replace(0, np.nan)
    denom = 1 + z * z / n.replace(0, np.nan)
    centre = p + z * z / (2 * n.replace(0, np.nan))
    adj = z * np.sqrt((p * (1 - p) + z * z / (4 * n.replace(0, np.nan))) / n.replace(0, np.nan))
    return ((centre - adj) / denom).fillna(0.0).clip(0, 1)


def calibrate_cils(cand: pd.DataFrame, budget: int) -> pd.DataFrame:
    out = cand.copy()
    samples = cand.sort_values(["answer_quality_proxy", "duration"], ascending=[False, True]).head(budget).copy()
    smap = samples.set_index("interval_id")[ANSWER].astype(int).to_dict()
    s = out[out["interval_id"].isin(smap)].copy()
    s["y"] = s["interval_id"].map(smap).astype(int)
    global_p = (s["y"].sum() + 1.0) / (len(s) + 2.0)
    keys = ["answer_quality_proxy_bin", "duration_bin", "method", "boundary_quality_bin"]
    stat = s.groupby(keys, observed=True, dropna=False)["y"].agg(["sum", "count"]).reset_index()
    stat["lower"] = wilson_lower(stat["sum"], stat["count"])
    out = out.merge(stat[keys + ["lower"]], on=keys, how="left")
    out["p_answer"] = out["lower"].fillna(global_p * 0.5).clip(0, 1)
    return out


def cils_select(cand: pd.DataFrame, budget: int, tau: float, interval_events: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    cal = calibrate_cils(cand, budget)
    duration_cap = min(32.0, float(interval_events["duration"].quantile(0.95)) * 3.0) if not interval_events.empty else 32.0
    df = cal.copy()
    bq = 0.55 + 0.45 * normalize(df["boundary_left_drop"] + df["boundary_right_drop"])
    dur_penalty = np.where(df["duration"] <= duration_cap, 1.0, duration_cap / df["duration"])
    df["value"] = np.minimum(df["duration"], duration_cap) * (0.5 + 0.5 * df["active_score"])
    df["boundary_quality"] = bq * dur_penalty
    df["utility"] = df["p_answer"] * df["value"] * df["boundary_quality"]
    ranked = df.sort_values(["utility", "active_score"], ascending=False).head(min(len(df), max(300, budget * 30)))
    selected, spans = [], []
    tp = total = dur = 0.0
    for r in ranked.itertuples(index=False):
        if len(selected) >= budget:
            break
        if dur + r.duration > 360.0:
            continue
        if any(interval_iou(Interval(r.t_start, r.t_end), Interval(a, b)) > 0.3 for a, b in spans):
            continue
        ntp = tp + float(r.p_answer) * float(r.value)
        ntotal = total + float(r.value)
        if safe_div(ntp, ntotal) + 1e-12 < tau:
            continue
        selected.append(r._asdict())
        spans.append((float(r.t_start), float(r.t_end)))
        tp, total, dur = ntp, ntotal, dur + float(r.duration)
    return pd.DataFrame(selected), safe_div(tp, total)


def lattice_oracle_for_events(cand: pd.DataFrame, events: pd.DataFrame, budget: int, iou_threshold: float) -> pd.DataFrame:
    """Event-wise lattice upper bound for the interval-eval subset.

    This is diagnostic only: it uses the reference events to ask whether the
    existing lattice contains at least one candidate per event at the requested
    IoU threshold. It should not be confused with an algorithmic selector.
    """

    chosen = []
    used = set()
    for ev in events.itertuples(index=False):
        best_row = None
        best_iou = -1.0
        for row in cand.itertuples(index=False):
            if row.interval_id in used:
                continue
            iou = interval_iou(Interval(row.t_start, row.t_end), Interval(ev.t_start, ev.t_end, ev.event_id))
            if iou > best_iou:
                best_iou = iou
                best_row = row
        if best_row is not None and best_iou >= iou_threshold:
            d = best_row._asdict()
            d["oracle_matched_event_id"] = ev.event_id
            d["oracle_event_iou"] = best_iou
            chosen.append(d)
            used.add(best_row.interval_id)
        if len(chosen) >= budget:
            break
    return pd.DataFrame(chosen)


def eval_predictions(sel: pd.DataFrame, events: pd.DataFrame, iou_threshold: float, expected_precision: float | None = None) -> dict:
    preds = to_intervals(sel)
    evs = to_intervals(events, "event_id")
    precision = float(sel[ANSWER].mean()) if not sel.empty and ANSWER in sel else math.nan
    returned_duration = float(sel["duration"].sum()) if not sel.empty and "duration" in sel else 0.0
    true_duration = float(events["duration"].sum()) if not events.empty else 0.0
    return {
        "event_recall": metric_event_recall(preds, evs, iou_threshold),
        "precision": precision,
        "expected_precision": expected_precision if expected_precision is not None else math.nan,
        "returned_interval_count": len(sel),
        "returned_duration_total": returned_duration,
        "true_event_duration_total": true_duration,
        "duration_inflation": metric_duration_inflation(preds, evs, iou_threshold),
        "duplicate_rate": metric_duplicate_rate(preds, evs, iou_threshold),
    }


def run_grid(cand: pd.DataFrame, events: pd.DataFrame, run_dir: Path, smoke: bool, patch_smoke: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if patch_smoke:
        budgets = BUDGETS_PATCH_SMOKE
        seeds = SEEDS_PATCH_SMOKE
        cils_taus = CILS_TAUS
        methods = list(PATCH_SMOKE_METHODS)
    else:
        budgets = BUDGETS_SMOKE if smoke else BUDGETS_FULL
        seeds = SEEDS_SMOKE if smoke else SEEDS_FULL
        cils_taus = CILS_TAUS
        methods = [
            "fixed_window_topk",
            "threshold_merge",
            "arc_style_prune_refine",
            "oracle_confirmed_only",
            "audited_proposal_repair",
            "cils_craq_lite",
            "lattice_oracle_upper_bound",
        ]
    prediction_rows = {m: [] for m in methods}
    prediction_cols = [
        "method", "budget", "precision_target", "cils_tau", "seed", "rank", "interval_id",
        "t_start", "t_end", "duration", "answer_iou_0_3", "answer_iou_0_5",
        "matched_event_id",
    ]
    metric_rows = []
    oracle_trace = []
    non_cils_methods = [m for m in methods if m != "cils_craq_lite" and m != "lattice_oracle_upper_bound"]
    run_cils = "cils_craq_lite" in methods
    run_lattice = "lattice_oracle_upper_bound" in methods
    for budget in budgets:
        for seed in seeds:
            non_cils_selections: dict[str, tuple[pd.DataFrame, float | None]] = {}
            for method in non_cils_methods:
                if method == "fixed_window_topk":
                    non_cils_selections[method] = (fixed_window_topk(cand, budget, seed), None)
                elif method == "threshold_merge":
                    non_cils_selections[method] = (threshold_merge(cand, budget, seed), None)
                elif method == "arc_style_prune_refine":
                    non_cils_selections[method] = (arc_style(cand, budget, seed), None)
                elif method == "oracle_confirmed_only":
                    non_cils_selections[method] = (oracle_confirmed_only(cand, budget, seed), None)
                elif method == "audited_proposal_repair":
                    non_cils_selections[method] = (audited_proposal_repair(cand, events, budget, seed, oracle_trace), None)
            for method, (sel, exp_prec) in non_cils_selections.items():
                sel = sel.copy()
                if not sel.empty:
                    for rank, row in enumerate(sel.itertuples(index=False), start=1):
                        for precision_target in PRECISION_TARGETS:
                            prediction_rows[method].append(
                                {
                                    "method": method,
                                    "budget": budget,
                                    "precision_target": precision_target,
                                    "cils_tau": math.nan,
                                    "seed": seed,
                                    "rank": rank,
                                    "interval_id": getattr(row, "interval_id", ""),
                                    "t_start": getattr(row, "t_start", math.nan),
                                    "t_end": getattr(row, "t_end", math.nan),
                                    "duration": getattr(row, "duration", math.nan),
                                    "answer_iou_0_3": getattr(row, ANSWER, math.nan),
                                    "answer_iou_0_5": getattr(row, "answer_iou_0_5", math.nan),
                                    "matched_event_id": getattr(row, "matched_event_id", ""),
                                }
                            )
                for precision_target in PRECISION_TARGETS:
                    for th in IOU_THRESHOLDS:
                        m = eval_predictions(sel, events, th, exp_prec)
                        metric_rows.append(
                            {
                                "method": method,
                                "budget": budget,
                                "precision_target": precision_target,
                                "cils_tau": math.nan,
                                "iou_threshold": th,
                                "seed": seed,
                                **m,
                                "conclusion_scope": "diagnostic_only" if len(events) < 20 else "eligible",
                            }
                        )
            if run_cils:
                for cils_tau in cils_taus:
                    sel, exp_prec = cils_select(cand, budget, cils_tau, events)
                    sel = sel.copy()
                    if not sel.empty:
                        for rank, row in enumerate(sel.itertuples(index=False), start=1):
                            for precision_target in PRECISION_TARGETS:
                                prediction_rows["cils_craq_lite"].append(
                                    {
                                        "method": "cils_craq_lite",
                                        "budget": budget,
                                        "precision_target": precision_target,
                                        "cils_tau": cils_tau,
                                        "seed": seed,
                                        "rank": rank,
                                        "interval_id": getattr(row, "interval_id", ""),
                                        "t_start": getattr(row, "t_start", math.nan),
                                        "t_end": getattr(row, "t_end", math.nan),
                                        "duration": getattr(row, "duration", math.nan),
                                        "answer_iou_0_3": getattr(row, ANSWER, math.nan),
                                        "answer_iou_0_5": getattr(row, "answer_iou_0_5", math.nan),
                                        "matched_event_id": getattr(row, "matched_event_id", ""),
                                    }
                                )
                    for precision_target in PRECISION_TARGETS:
                        for th in IOU_THRESHOLDS:
                            m = eval_predictions(sel, events, th, exp_prec)
                            metric_rows.append(
                                {
                                    "method": "cils_craq_lite",
                                    "budget": budget,
                                    "precision_target": precision_target,
                                    "cils_tau": cils_tau,
                                    "iou_threshold": th,
                                    "seed": seed,
                                    **m,
                                    "conclusion_scope": "diagnostic_only" if len(events) < 20 else "eligible",
                                }
                            )
            if run_lattice:
                for th in IOU_THRESHOLDS:
                    sel = lattice_oracle_for_events(cand, events, budget, th)
                    if not sel.empty:
                        for rank, row in enumerate(sel.itertuples(index=False), start=1):
                            for precision_target in PRECISION_TARGETS:
                                prediction_rows["lattice_oracle_upper_bound"].append(
                                    {
                                        "method": "lattice_oracle_upper_bound",
                                        "budget": budget,
                                        "precision_target": precision_target,
                                        "cils_tau": math.nan,
                                        "seed": seed,
                                        "rank": rank,
                                        "interval_id": getattr(row, "interval_id", ""),
                                        "t_start": getattr(row, "t_start", math.nan),
                                        "t_end": getattr(row, "t_end", math.nan),
                                        "duration": getattr(row, "duration", math.nan),
                                        "answer_iou_0_3": getattr(row, ANSWER, math.nan),
                                        "answer_iou_0_5": getattr(row, "answer_iou_0_5", math.nan),
                                        "matched_event_id": getattr(row, "matched_event_id", ""),
                                    }
                                )
                    for precision_target in PRECISION_TARGETS:
                        m = eval_predictions(sel, events, th, None)
                        metric_rows.append(
                            {
                                "method": "lattice_oracle_upper_bound",
                                "budget": budget,
                                "precision_target": precision_target,
                                "cils_tau": math.nan,
                                "iou_threshold": th,
                                "seed": seed,
                                **m,
                                "conclusion_scope": "diagnostic_only" if len(events) < 20 else "eligible",
                            }
                        )
    for method, rows in prediction_rows.items():
        pd.DataFrame(rows, columns=prediction_cols).to_csv(run_dir / f"predictions_{method}.csv", index=False)
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(run_dir / "metrics_by_method_seed.csv", index=False)
    summary = metrics.groupby(["method", "budget", "precision_target", "cils_tau", "iou_threshold"], dropna=False).agg(
        mean_event_recall=("event_recall", "mean"),
        std_event_recall=("event_recall", "std"),
        mean_precision=("precision", "mean"),
        mean_expected_precision=("expected_precision", "mean"),
        mean_returned_interval_count=("returned_interval_count", "mean"),
        mean_duration_inflation=("duration_inflation", "mean"),
        mean_duplicate_rate=("duplicate_rate", "mean"),
    ).reset_index()
    summary.to_csv(run_dir / "metrics_summary.csv", index=False)
    prop_rows = []
    for method in methods:
        for th in IOU_THRESHOLDS:
            best = summary[(summary["method"] == method) & (summary["iou_threshold"] == th)]["mean_event_recall"].max()
            prop_rows.append({"method": method, "iou_threshold": th, "proposal_or_return_recall": float(best) if pd.notna(best) else 0.0})
    proposal = pd.DataFrame(prop_rows)
    proposal_wide = proposal.pivot(index="method", columns="iou_threshold", values="proposal_or_return_recall").reset_index()
    proposal_wide = proposal_wide.rename(columns={0.3: "proposal_recall_iou_0_3", 0.5: "proposal_recall_iou_0_5"})
    proposal = proposal.merge(proposal_wide, on="method", how="left")
    proposal.to_csv(run_dir / "proposal_recall.csv", index=False)
    trace = pd.DataFrame(oracle_trace)
    trace.to_csv(run_dir / "oracle_budget_trace.csv", index=False)
    return metrics, summary, proposal, trace


def write_config(run_dir: Path, smoke: bool, commit: str, patch_smoke: bool = False) -> None:
    if patch_smoke:
        mode = "patch_smoke"
        methods = list(PATCH_SMOKE_METHODS)
        budgets = BUDGETS_PATCH_SMOKE
        seeds = SEEDS_PATCH_SMOKE
    elif smoke:
        mode = "smoke_scale"
        methods = ["fixed_window_topk", "threshold_merge", "arc_style_prune_refine", "oracle_confirmed_only", "audited_proposal_repair", "cils_craq_lite", "lattice_oracle_upper_bound"]
        budgets = BUDGETS_SMOKE
        seeds = SEEDS_SMOKE
    else:
        mode = "full_grid"
        methods = ["fixed_window_topk", "threshold_merge", "arc_style_prune_refine", "oracle_confirmed_only", "audited_proposal_repair", "cils_craq_lite", "lattice_oracle_upper_bound"]
        budgets = BUDGETS_FULL
        seeds = SEEDS_FULL
    cfg = {
        "experiment": "craq_lite_v1",
        "timestamp": run_dir.name,
        "commit": commit,
        "mode": mode,
        "methods": methods,
        "oracle_budgets": budgets,
        "precision_targets": PRECISION_TARGETS,
        "cils_taus": CILS_TAUS,
        "iou_thresholds": IOU_THRESHOLDS,
        "seeds": seeds,
        "fixed_cils_policy": {"pilot": "answer_quality_proxy_top", "calibration": "beta_bin_strata_lower", "selector": "clean_v2_no_leak_cils_selector"},
        "inputs": {"clean_v2": str(V2), "repair_smoke": str(SMOKE), "repair_replay": str(REPLAY)},
    }
    (run_dir / "config_used.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def make_plots(run_dir: Path, summary: pd.DataFrame, proposal: pd.DataFrame) -> None:
    plot_dir = run_dir / "plots"
    plot_dir.mkdir(exist_ok=True)
    for target in [0.8, 0.9]:
        fig, ax = plt.subplots(figsize=(7, 4))
        data = summary[(summary["precision_target"] == target) & (summary["iou_threshold"] == 0.3)]
        for method, g in data.groupby("method"):
            eligible = g[g["mean_precision"].fillna(0) >= target]
            ax.plot(eligible["budget"], eligible["mean_event_recall"], marker="o", label=method)
        ax.set_title(f"Budget vs event recall, observed precision >= {target}")
        ax.set_xlabel("oracle budget")
        ax.set_ylabel("event recall IoU@0.3")
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(plot_dir / f"budget_vs_recall_precision_{str(target).replace('.', '_')}.png", dpi=160)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    data = summary[(summary["iou_threshold"] == 0.3) & (summary["precision_target"] == 0.8)]
    for method, g in data.groupby("method"):
        ax.plot(g["budget"], g["mean_duration_inflation"], marker="o", label=method)
    ax.set_title("Budget vs returned duration inflation")
    ax.set_xlabel("oracle budget")
    ax.set_ylabel("duration inflation")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(plot_dir / "budget_vs_duration_inflation.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    p03 = proposal[proposal["iou_threshold"] == 0.3].sort_values("proposal_or_return_recall", ascending=False)
    ax.barh(p03["method"], p03["proposal_or_return_recall"])
    ax.set_title("Proposal/return recall by method IoU@0.3")
    fig.tight_layout()
    fig.savefig(plot_dir / "proposal_recall_by_method.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    data = summary[(summary["iou_threshold"] == 0.3) & (summary["precision_target"] == 0.8)]
    ub = data[data["method"] == "lattice_oracle_upper_bound"][["budget", "mean_event_recall"]].rename(columns={"mean_event_recall": "upper"})
    for method, g in data[data["method"] != "lattice_oracle_upper_bound"].groupby("method"):
        m = g.merge(ub, on="budget", how="left")
        ax.plot(m["budget"], m["mean_event_recall"], marker="o", label=method)
    ax.plot(ub["budget"], ub["upper"], marker="x", color="black", label="lattice_oracle_upper_bound")
    ax.set_title("Lattice oracle upper bound vs actual recall")
    ax.set_xlabel("oracle budget")
    ax.set_ylabel("event recall IoU@0.3")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(plot_dir / "upper_bound_vs_actual_recall.png", dpi=160)
    plt.close(fig)


def report(run_dir: Path, commit: str, command: str, ref_audit: pd.DataFrame, summary: pd.DataFrame, proposal: pd.DataFrame, metrics: pd.DataFrame, smoke: bool, patch_smoke: bool = False) -> None:
    n_interval = int(ref_audit["is_interval_event"].sum())
    reference_gate = n_interval >= 20
    ub = summary[(summary["method"] == "lattice_oracle_upper_bound") & (summary["iou_threshold"] == 0.3)]["mean_event_recall"].max()
    proposal_gate = bool(pd.notna(ub) and ub >= 0.5)
    cils_all = summary[(summary["method"] == "cils_craq_lite") & (summary["iou_threshold"] == 0.3)] if "cils_craq_lite" in set(summary["method"]) else pd.DataFrame()
    cils_p08 = cils_all[cils_all["mean_precision"].fillna(0) >= 0.8] if not cils_all.empty else cils_all
    cils_p09 = cils_all[cils_all["mean_precision"].fillna(0) >= 0.9] if not cils_all.empty else cils_all
    best_cils = float(cils_p08["mean_event_recall"].max()) if not cils_p08.empty else 0.0
    best_cils_p09 = float(cils_p09["mean_event_recall"].max()) if not cils_p09.empty else 0.0
    repair_all = summary[(summary["method"] == "audited_proposal_repair") & (summary["iou_threshold"] == 0.3)] if "audited_proposal_repair" in set(summary["method"]) else pd.DataFrame()
    repair = repair_all[repair_all["mean_precision"].fillna(0) >= 0.8] if not repair_all.empty else repair_all
    best_repair = float(repair["mean_event_recall"].max()) if not repair.empty else 0.0
    best_repair_any_prec = float(repair_all["mean_event_recall"].max()) if not repair_all.empty else 0.0
    cils_infl = float(cils_p08.sort_values("mean_event_recall", ascending=False)["mean_duration_inflation"].head(1).mean()) if not cils_p08.empty else math.nan
    repair_infl = float(repair.sort_values("mean_event_recall", ascending=False)["mean_duration_inflation"].head(1).mean()) if not repair.empty else math.nan
    selector_gate_passed = bool((best_cils >= best_repair + 0.10 or (best_repair > 0 and best_cils >= 1.3 * best_repair)) and (pd.isna(repair_infl) or cils_infl <= repair_infl * 1.25))
    top = summary.sort_values(["mean_event_recall", "mean_precision"], ascending=[False, False]).head(25)
    plots = sorted(str(p.relative_to(run_dir)) for p in (run_dir / "plots").glob("*.png")) if (run_dir / "plots").exists() else []
    mode_label = "patch-smoke" if patch_smoke else ("smoke-scale" if smoke else "full-grid")
    rerun_flag = "--patch-smoke " if patch_smoke else ("--smoke " if smoke else "")
    # CILS tau summary for patch_smoke
    cils_tau_summary = ""
    if patch_smoke and not cils_all.empty:
        tau_grp = cils_all.groupby(["cils_tau"]).agg(
            mean_returned_interval_count=("mean_returned_interval_count", "mean"),
            mean_event_recall=("mean_event_recall", "mean"),
            mean_precision=("mean_precision", "mean"),
        ).reset_index()
        # empty-return rate from per-seed metrics
        cils_metrics = metrics[(metrics["method"] == "cils_craq_lite") & (metrics["iou_threshold"] == 0.3)] if not metrics.empty else pd.DataFrame()
        if not cils_metrics.empty:
            empty_rate = cils_metrics.groupby("cils_tau").apply(lambda g: float((g["returned_interval_count"] == 0).mean()), include_groups=False).reset_index()
            empty_rate.columns = ["cils_tau", "empty_return_rate"]
            tau_grp = tau_grp.merge(empty_rate, on="cils_tau", how="left")
        cils_tau_summary = "\n\n### CILS by tau (IoU@0.3)\n\n" + md_table(tau_grp, 20)
    # patch-smoke specific Q&A
    patch_qa = ""
    if patch_smoke:
        cils_taus_used = sorted(cils_all["cils_tau"].dropna().unique().tolist()) if not cils_all.empty else []
        n_cils_preds = 0
        pred_file = run_dir / "predictions_cils_craq_lite.csv"
        if pred_file.exists():
            import csv as _csv
            with open(pred_file) as fh:
                n_cils_preds = sum(1 for _ in _csv.reader(fh)) - 1
        max_cils_returned = float(cils_all["mean_returned_interval_count"].max()) if not cils_all.empty else 0.0
        tau05_nonempty = bool(not cils_all.empty and float(cils_all[cils_all["cils_tau"] == 0.5]["mean_returned_interval_count"].max()) > 0) if 0.5 in cils_taus_used else False
        tau06_nonempty = bool(not cils_all.empty and float(cils_all[cils_all["cils_tau"] == 0.6]["mean_returned_interval_count"].max()) > 0) if 0.6 in cils_taus_used else False
        patch_qa = f"""

## Patch-Smoke Diagnostic Q&A

- Was precision_target fully decoupled from cils_tau? **YES**. `cils_select` receives `tau` from the `cils_taus` axis; `precision_target` is only a reporting/filter label.
- What cils_tau values actually ran? `{cils_taus_used}`
- Was the single overlap_group_id issue fixed? **YES**. NMS and `cils_select` no longer skip by `overlap_group_id`; selection uses IoU > 0.3 only.
- Can CILS now return more than one interval when candidates permit it? **{'YES' if max_cils_returned > 1.0 else 'NO'}** (max mean returned count = `{max_cils_returned:.2f}`).
- Does CILS at tau=0.5/0.6 reproduce non-empty behavior? **{'YES' if tau05_nonempty or tau06_nonempty else 'NO'}** (tau=0.5 nonempty: {tau05_nonempty}, tau=0.6 nonempty: {tau06_nonempty}).
- Does any CILS setting achieve observed precision >= 0.8 with nonzero recall? **{'YES' if best_cils > 0 else 'NO'}** (best recall = `{best_cils:.3f}`).
- Does any CILS setting achieve observed precision >= 0.9 with nonzero recall? **{'YES' if best_cils_p09 > 0 else 'NO'}** (best recall = `{best_cils_p09:.3f}`).
- Does audited_proposal_repair still return zero recall after the group-id/NMS fix? **{'YES (still zero at precision>=0.8)' if best_repair == 0 else 'NO'}** (best repair recall @ precision>=0.8 = `{best_repair:.3f}`; repair recall ignoring precision = `{best_repair_any_prec:.3f}`).
- Is the selector gate still failed, passed, or inconclusive? **{'PASS' if selector_gate_passed else ('INCONCLUSIVE (reference gate failed, diagnostic only)' if not reference_gate else 'FAIL')}**.

### Prediction counts

- `predictions_cils_craq_lite.csv` rows: `{n_cils_preds}`
"""
    write(
        run_dir / "REPORT.md",
        f"""# CRAQ-lite / CILS Inner Selector Evaluation V1

## Run Metadata

- Git commit: `{commit}`
- Main command: `{command}`
- Test command: `pytest -q src/garc_eval/tests/test_craq_lite_metrics.py`
- Syntax check command: `python -m py_compile src/garc_eval/metrics/craq_lite_metrics.py src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py`
- Environment: Python `{platform.python_version()}`, platform `{platform.platform()}`
- Run directory: `{run_dir}`
- Grid mode: `{mode_label}`
- Exact rerun command: `python src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py {rerun_flag}--run-dir {run_dir}`

## Repository Structure

See `repo_inventory.md`.

## Reference Audit

See `reference_audit.csv` and `reference_audit_summary.md`.

- True interval events: `{n_interval}`
- Reference gate passed: **{'yes' if reference_gate else 'no'}**
- Conclusion status: **{'diagnostic only' if not reference_gate else 'eligible for stronger claims'}**

## Method Descriptions

- `fixed_window_topk`: clean v2 fixed-window candidates ranked by cheap active score with temporal NMS.
- `threshold_merge`: clean v2 threshold-merge candidates ranked by cheap active score with temporal NMS.
- `arc_style_prune_refine`: closest clean v2 ARC-style proxy using signal-peak, threshold-merge, and boundary-refined proposals ranked by fixed answer-quality proxy.
- `oracle_confirmed_only`: top active-score candidates directly filtered by existing oracle replay labels; conservative lower-bound baseline.
- `audited_proposal_repair`: starts from ARC-style candidates, audits candidate-external 2s locations with fixed seed, repairs positives by local nearest clean lattice intervals, and counts audit calls in `oracle_budget_trace.csv`.
- `cils_craq_lite`: CRAQ-lite outer wrapper using clean v2 lattice and fixed CILS inner selector (`answer_quality_proxy_top + beta_bin_strata_lower`). Selector tau is set by `cils_taus`, NOT by `precision_target`.
- `lattice_oracle_upper_bound`: diagnostic oracle over the clean v2 candidate lattice.

## Metric Definitions

Metrics are implemented in `src/garc_eval/metrics/craq_lite_metrics.py` and tested in `src/garc_eval/tests/test_craq_lite_metrics.py`. Event recall hits a true interval event once if any returned interval reaches the IoU threshold. Precision uses existing clean v2 `answer_iou_0_3` interval labels. Duplicate rate is extra hit predictions per returned prediction. Duration inflation is returned duration divided by matched true-event duration, falling back to total true-event duration when no event is matched.

## Experiment Grid Actually Run

- Budgets: `{BUDGETS_PATCH_SMOKE if patch_smoke else (BUDGETS_SMOKE if smoke else BUDGETS_FULL)}`
- Precision targets (reporting only): `{PRECISION_TARGETS}`
- CILS taus (selector threshold): `{CILS_TAUS}`
- IoU thresholds: `{IOU_THRESHOLDS}`
- Seeds: `{SEEDS_PATCH_SMOKE if patch_smoke else (SEEDS_SMOKE if smoke else SEEDS_FULL)}`

## Results

{md_table(top, 25)}
{cils_tau_summary}
{patch_qa}
## Plots

{chr(10).join(f'- `{p}`' for p in plots)}

## Gate Outcomes

- Gate 1 reference gate: **{'PASS' if reference_gate else 'FAIL'}**. `{n_interval}` true interval events; conclusions are diagnostic only when this is below 20.
- Gate 2 proposal gate: **{'PASS' if proposal_gate else 'FAIL'}**. Lattice oracle upper bound IoU@0.3 max = `{float(ub) if pd.notna(ub) else 0.0:.3f}`.
- Gate 3 selector gate: **{'PASS' if selector_gate_passed else 'FAIL'}**. Best CILS recall at precision >= 0.8 = `{best_cils:.3f}`; best audited repair recall at precision >= 0.8 = `{best_repair:.3f}`.

## Preferred Interpretation

Current result **{'supports' if selector_gate_passed and reference_gate else 'does not support'}** the claim:

> "CILS as a CRAQ-lite inner selector improves event recall under a precision constraint, compared with audited proposal repair, without materially increasing returned duration."

Evidence:
- Best CILS recall: `{best_cils:.3f}`.
- Best audited proposal repair recall: `{best_repair:.3f}`.
- Reference size: `{n_interval}` true interval events, so this run is **{'not diagnostic-only' if reference_gate else 'diagnostic only'}**.

Bottleneck diagnosis:
- Reference size is the dominant validity bottleneck when true interval events < 20.
- Candidate coverage is not the primary bottleneck if lattice upper bound remains high.
- Selector/calibration still has weak recall at high precision targets in this small reference.

## Limitations

- Uses VLM-defined pseudo-oracle labels, not human truth.
- Audited proposal repair is a fixed diagnostic wrapper over existing labels, not a tuned production algorithm.
- No strong event-level guarantee is claimed.

## Next Recommended Action

Build or acquire a larger true-interval reference (>=20 interval events) and rerun this exact wrapper before making any CILS-vs-repair claim.
""",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--smoke", action="store_true", help="Run smoke-scale grid: budgets 20/40/80 and seeds 0..9.")
    ap.add_argument("--patch-smoke", action="store_true", help="Run patch-smoke diagnostic grid: budgets 80/160, taus 0.5/0.6/0.7, seeds 0..19, methods cils/repair/oracle/lattice only.")
    args = ap.parse_args()
    run_dir = args.run_dir or (ROOT / "runs/craq_lite_v1" / timestamp())
    run_dir.mkdir(parents=True, exist_ok=True)
    if not args.patch_smoke:
        (run_dir / "plots").mkdir(exist_ok=True)
    code, commit = run_cmd(["git", "rev-parse", "HEAD"])
    if code != 0:
        commit = f"UNKNOWN ({commit})"
    flags = ""
    if args.patch_smoke:
        flags = "--patch-smoke "
    elif args.smoke:
        flags = "--smoke "
    command = "python src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py " + flags + f"--run-dir {run_dir}"
    if not args.patch_smoke:
        repo_inventory(run_dir)
    inputs = load_inputs()
    cand = prepare_candidates(inputs)
    ref_audit = reference_audit(inputs["reference"], run_dir)
    events = event_df(ref_audit)
    write_config(run_dir, args.smoke, commit, args.patch_smoke)
    metrics, summary, proposal, trace = run_grid(cand, events, run_dir, args.smoke, args.patch_smoke)
    if not args.patch_smoke:
        make_plots(run_dir, summary, proposal)
    report(run_dir, commit, command, ref_audit, summary, proposal, metrics, args.smoke, args.patch_smoke)
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
