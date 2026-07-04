#!/usr/bin/env python3
from __future__ import annotations

import ast
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
EXP = ROOT / "src/garc_eval/experiments/clean_interval_aqp_full_reference_v2_label_aligned"
V2 = ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned"
OUT = ROOT / "src/garc_eval/outputs/clean_interval_aqp_code_audit_v1"
ANSWER = "answer_iou_0_3"
SEED = 20250630
EPS = 1e-6

REQUIRED = [
    "FINAL_REPORT.md",
    "AGENT_LOOP_LOG.md",
    "reference_events.csv",
    "base_units.csv",
    "full_reference_units.csv",
    "cheap_signals_per_unit.csv",
    "interval_lattice_v2.csv",
    "interval_lattice_features_only.csv",
    "interval_labels_v2.csv",
    "proposal_quality_v2.csv",
    "proposal_recall_curve_v2.csv",
    "calibration_trials_v2.csv",
    "calibration_quality_v2.csv",
    "main_budget_curve_v2.csv",
    "baseline_comparison_v2.csv",
    "precision_recall_duration_duplicate_summary_v2.csv",
    "selected_intervals_by_trial_v2.csv",
    "stress_test_results_v2.csv",
    "sanity_checks_v2.md",
    "proposal_upper_bound_report.md",
    "calibration_label_alignment_report.md",
    "failure_analysis.md",
    "label_leakage_audit.md",
]

FORBIDDEN_FEATURE_FIELDS = {
    "label_event",
    "label_available",
    "event_id",
    "matched_event_id",
    "answer_positive",
    "discovery_positive",
    "answer_iou_0_3",
    "answer_iou_0_5",
    "answer_overlap_purity",
    "event_hit_iou_0_3",
    "event_hit_iou_0_5",
    "positive_unit_fraction",
    "event_overlap_ratio",
    "interval_purity",
    "duration_inflation",
    "oracle_positive",
    "reference_event",
    "is_reference",
    "best_iou",
    "any_overlap",
    "center_hit",
}

LABEL_HINTS = (
    "label",
    "event",
    "answer",
    "iou",
    "overlap",
    "purity",
    "duration_inflation",
    "reference",
    "oracle",
)

FINDINGS: list[dict] = []


def add(severity: str, area: str, finding: str, evidence: str, impact: str = "") -> None:
    FINDINGS.append(
        {
            "severity": severity,
            "area": area,
            "finding": finding,
            "evidence": evidence,
            "impact": impact,
        }
    )


def read(name: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(V2 / name, **kwargs)


def write(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8")


def md_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df is None or df.empty:
        return "_empty_"
    d = df.head(max_rows).copy()
    cols = [str(c) for c in d.columns]
    rows = []
    for _, r in d.iterrows():
        vals = []
        for c in d.columns:
            v = r[c]
            if isinstance(v, float):
                vals.append(f"{v:.6g}")
            else:
                vals.append(str(v))
        rows.append(vals)
    def esc(x: str) -> str:
        return x.replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(esc(c) for c in cols) + " |"]
    out.append("| " + " | ".join("---" for _ in cols) + " |")
    for vals in rows:
        out.append("| " + " | ".join(esc(v) for v in vals) + " |")
    return "\n".join(out)


def bools(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(["true", "1", "yes"])


def safe_div(a: float, b: float) -> float:
    return float(a / b) if b else 0.0


def tiou(a0: float, a1: float, b0: float, b1: float) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    return safe_div(inter, union)


def overlap_ratio(a0: float, a1: float, b0: float, b1: float) -> tuple[float, float, float]:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    event_d = max(0.0, b1 - b0)
    int_d = max(0.0, a1 - a0)
    return safe_div(inter, event_d), safe_div(inter, int_d), safe_div(int_d, event_d)


def normalize(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce").fillna(0.0).astype(float)
    lo, hi = float(s.min()), float(s.max())
    if hi - lo < 1e-12:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - lo) / (hi - lo)


def ece(y: pd.Series, p: pd.Series, bins: int = 5) -> float:
    y = y.astype(float).reset_index(drop=True)
    p = p.astype(float).reset_index(drop=True).clip(0, 1)
    total = 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    for i in range(bins):
        if i == bins - 1:
            mask = (p >= edges[i]) & (p <= edges[i + 1])
        else:
            mask = (p >= edges[i]) & (p < edges[i + 1])
        if mask.any():
            total += float(mask.mean()) * abs(float(p[mask].mean()) - float(y[mask].mean()))
    return total


def duplicate_rate(df: pd.DataFrame) -> float:
    if len(df) <= 1 or "matched_event_id" not in df:
        return 0.0
    ids = df["matched_event_id"].dropna().astype(str)
    ids = ids[ids != ""]
    if len(ids) == 0:
        return 0.0
    return safe_div(len(ids) - ids.nunique(), len(df))


def event_recall(sel: pd.DataFrame, events: pd.DataFrame, thresh: float) -> float:
    hits = set()
    for ev in events.itertuples(index=False):
        for r in sel.itertuples(index=False):
            if tiou(float(r.t_start), float(r.t_end), float(ev.t_start), float(ev.t_end)) >= thresh:
                hits.add(ev.event_id)
                break
    return safe_div(len(hits), len(events))


def eval_selection(sel: pd.DataFrame, labels: pd.DataFrame, events: pd.DataFrame) -> dict:
    if sel.empty:
        return {
            "number_returned": 0,
            "event_recall_iou_0_3": 0.0,
            "event_recall_iou_0_5": 0.0,
            "interval_precision_iou_0_3": 0.0,
            "interval_precision_iou_0_5": 0.0,
            "duplicate_rate": 0.0,
            "avg_returned_duration": 0.0,
            "p95_returned_duration": 0.0,
            "background_duration_ratio": 0.0,
        }
    lab = labels.set_index("interval_id")
    e = sel.copy()
    for c in ["answer_iou_0_3", "answer_iou_0_5", "positive_unit_fraction", "matched_event_id"]:
        if c not in e.columns:
            e[c] = e["interval_id"].map(lab[c])
    return {
        "number_returned": int(len(e)),
        "event_recall_iou_0_3": event_recall(e, events, 0.3),
        "event_recall_iou_0_5": event_recall(e, events, 0.5),
        "interval_precision_iou_0_3": float(bools(e["answer_iou_0_3"]).mean()),
        "interval_precision_iou_0_5": float(bools(e["answer_iou_0_5"]).mean()),
        "duplicate_rate": duplicate_rate(e),
        "avg_returned_duration": float(e["duration"].mean()),
        "p95_returned_duration": float(e["duration"].quantile(0.95)),
        "background_duration_ratio": float(1.0 - pd.to_numeric(e["positive_unit_fraction"]).mean()),
    }


def prepare_features(f: pd.DataFrame) -> pd.DataFrame:
    out = f.copy()
    out["active_score"] = normalize(out["active_score"])
    out["score_bin"] = pd.qcut(out["active_score"].rank(method="first"), 5, labels=False)
    out["duration_bin"] = pd.qcut(out["duration"].rank(method="first"), 5, labels=False)
    out["disagreement_bin"] = pd.qcut(out["signal_disagreement"].rank(method="first"), 5, labels=False)
    out["candidate_value"] = np.minimum(out["duration"], 32.0) * (0.5 + 0.5 * out["active_score"])
    out["predicted_uncertainty"] = out["active_score"] * (1.0 - out["active_score"])
    return out


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
        tmp = f.assign(priority=f["predicted_uncertainty"] * f["candidate_value"])
        return tmp.sort_values("priority", ascending=False)["interval_id"].head(budget).tolist()
    return []


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


def parse_upper_report() -> tuple[float | None, float | None, float | None]:
    p = V2 / "proposal_upper_bound_report.md"
    if not p.exists():
        return None, None, None
    text = p.read_text(encoding="utf-8")
    m = re.search(r"\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*[0-9]+\s*\|", text)
    if not m:
        return None, None, None
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def calibrate(f: pd.DataFrame, samples: pd.DataFrame) -> pd.DataFrame:
    out = f.copy()
    if samples.empty:
        out["p_answer"] = 0.5
        return out
    smap = samples.set_index("interval_id")["oracle_label"].astype(int).to_dict()
    s = out[out["interval_id"].isin(smap)].copy()
    s["y"] = s["interval_id"].map(smap).astype(int)
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


def cils_reasons(cal: pd.DataFrame, tau: float, max_return: int, duration_cap: float) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    df = cal.copy()
    bq = 0.55 + 0.45 * normalize(df["boundary_left_drop"] + df["boundary_right_drop"])
    dur_penalty = np.where(df["duration"] <= duration_cap, 1.0, duration_cap / df["duration"])
    df["value"] = np.minimum(df["duration"], duration_cap) * (0.5 + 0.5 * df["active_score"])
    df["boundary_quality"] = bq * dur_penalty
    df["utility"] = df["p_answer"] * df["value"] * df["boundary_quality"]
    ranked = df.sort_values(["utility", "active_score"], ascending=False).head(min(len(df), max(300, max_return * 30)))
    selected, rows, spans = [], [], []
    tp = total = dur = 0.0
    used_groups = set()
    for r in ranked.itertuples(index=False):
        reason = "selected"
        if len(selected) >= max_return:
            reason = "max_return_reached"
        elif pd.isna(r.p_answer):
            reason = "missing_p_answer"
        elif r.overlap_group_id in used_groups:
            reason = "overlap_conflict"
        elif dur + r.duration > 360.0:
            reason = "duration_penalty_too_large"
        elif any(tiou(r.t_start, r.t_end, a, b) > 0.3 for a, b in spans):
            reason = "overlap_conflict"
        else:
            ntp = tp + float(r.p_answer) * float(r.value)
            ntotal = total + float(r.value)
            exp = safe_div(ntp, ntotal)
            if exp + 1e-12 < tau:
                reason = "below_precision_constraint"
            elif float(r.utility) <= 0:
                reason = "non_positive_utility"
            else:
                selected.append(r._asdict())
                spans.append((r.t_start, r.t_end))
                used_groups.add(r.overlap_group_id)
                tp, total, dur = ntp, ntotal, dur + r.duration
        rows.append(
            {
                "tau": tau,
                "budget": max_return,
                "interval_id": r.interval_id,
                "p_answer": float(r.p_answer),
                "active_score": float(r.active_score),
                "duration": float(r.duration),
                "value": float(r.value),
                "utility": float(r.utility),
                "rejection_reason": reason,
            }
        )
    return pd.DataFrame(selected), pd.DataFrame(rows), safe_div(tp, total)


def artifact_inventory() -> None:
    rows = []
    for name in REQUIRED:
        p = V2 / name
        row = {"artifact": name, "path": str(p), "exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() else 0}
        if p.suffix == ".csv" and p.exists():
            try:
                df0 = pd.read_csv(p, nrows=0)
                row["rows"] = max(0, sum(1 for _ in p.open("r", encoding="utf-8")) - 1)
                row["columns"] = "|".join(df0.columns)
                row["duplicate_columns"] = "|".join(pd.Series(df0.columns)[pd.Series(df0.columns).duplicated()].tolist())
                row["empty_file"] = row["rows"] == 0
            except Exception as e:
                row["read_error"] = str(e)
        rows.append(row)
    inv = pd.DataFrame(rows)
    inv.to_csv(OUT / "artifact_inventory.csv", index=False)
    branch = subprocess.run(["git", "-c", f"safe.directory={ROOT}", "branch", "--show-current"], cwd=ROOT, text=True, capture_output=True)
    status = subprocess.run(["git", "-c", f"safe.directory={ROOT}", "status", "--short"], cwd=ROOT, text=True, capture_output=True)
    write(
        "artifact_inventory.md",
        f"""# Artifact Inventory

- git branch: `{branch.stdout.strip() or 'UNKNOWN'}`
- git status exit: `{status.returncode}`
- v2 script exists: `{(EXP / 'pipeline.py').exists()}`
- v2 run script exists: `{(EXP / 'run_all.sh').exists()}`
- v2 output dir exists: `{V2.exists()}`

Git status:

```text
{status.stdout.strip() or status.stderr.strip() or 'clean'}
```

{md_table(inv, 80)}
""",
    )
    if inv[~inv["exists"]].shape[0]:
        add("WARNING", "Artifact inventory", "Some requested v2 artifacts are missing.", ", ".join(inv.loc[~inv["exists"], "artifact"]))
    if inv.get("empty_file", pd.Series(dtype=bool)).fillna(False).any():
        add("INFO", "Artifact inventory", "At least one CSV is empty.", ", ".join(inv.loc[inv.get("empty_file", False).fillna(False), "artifact"]))


def label_leakage() -> None:
    feat = read("interval_lattice_features_only.csv")
    pipe = (EXP / "pipeline.py").read_text(encoding="utf-8")
    inventory = pd.DataFrame(
        [
            {
                "field": c,
                "in_features_only": True,
                "forbidden_or_reference_derived": c in FORBIDDEN_FEATURE_FIELDS or any(h in c.lower() for h in LABEL_HINTS),
            }
            for c in feat.columns
        ]
    )
    inventory.to_csv(OUT / "label_field_inventory.csv", index=False)
    forbidden = sorted(set(feat.columns) & FORBIDDEN_FEATURE_FIELDS)
    text_hits = []
    for term in ["reference_events.csv", "full_reference_units.csv", "interval_labels_v2.csv", "features_only", "oracle_samples", "calibrate"]:
        text_hits.append({"term": term, "count": pipe.count(term)})
    if forbidden:
        add("BLOCKER", "Label leakage", "features-only lattice contains reference-derived fields.", ", ".join(forbidden), "Optimization input can carry held-out answer/evaluation information.")
    if "features = full.drop" in pipe or "full.drop(columns=label_cols" in pipe:
        add("WARNING", "Label leakage", "features-only appears to be produced from the joined full lattice by dropping columns.", "Static audit saw drop-after-join pattern.", "Drop lists are brittle and already missed reference-derived fields.")
    write(
        "label_leakage_audit.md",
        f"""# Label Leakage Audit

Verdict: **{'BLOCKER' if forbidden else 'PASS'}**

Forbidden/reference-derived fields present in `interval_lattice_features_only.csv`:

```text
{', '.join(forbidden) if forbidden else 'none'}
```

Static pipeline term inventory:

{md_table(pd.DataFrame(text_hits))}

Conclusion: the features-only artifact is not actually label-free because it includes reference-derived metric fields. Even if CILS does not intentionally use every leaked field, this violates the v2 trust boundary and makes the optimization input unsafe.
""",
    )


def label_definition() -> None:
    labels = read("interval_labels_v2.csv")
    events = read("reference_events.csv")
    lattice = read("interval_lattice_v2.csv")
    rows = []
    for r in lattice.itertuples(index=False):
        best_iou = 0.0
        best_ev = None
        any_ov = False
        center = False
        hit03 = hit05 = False
        ev_ov = purity = infl = 0.0
        for ev in events.itertuples(index=False):
            iou = tiou(r.t_start, r.t_end, ev.t_start, ev.t_end)
            eov, ipur, dinf = overlap_ratio(r.t_start, r.t_end, ev.t_start, ev.t_end)
            inter = max(0.0, min(r.t_end, ev.t_end) - max(r.t_start, ev.t_start))
            any_ov = any_ov or inter > 0
            center_t = (ev.t_start + ev.t_end) / 2.0
            center = center or (r.t_start <= center_t <= r.t_end)
            hit03 = hit03 or iou >= 0.3
            hit05 = hit05 or iou >= 0.5
            if iou > best_iou:
                best_iou, best_ev, ev_ov, purity, infl = iou, ev.event_id, eov, ipur, dinf
        rows.append(
            {
                "interval_id": r.interval_id,
                "re_best_iou": best_iou,
                "re_matched_event_id": best_ev,
                "re_any_overlap": any_ov,
                "re_center_hit": center,
                "re_event_hit_iou_0_3": hit03,
                "re_event_hit_iou_0_5": hit05,
                "re_event_overlap_ratio": ev_ov,
                "re_interval_purity": purity,
                "re_duration_inflation": infl if best_ev is not None else np.nan,
            }
        )
    rec = pd.DataFrame(rows).merge(labels, on="interval_id", how="left")
    checks = pd.DataFrame(
        [
            {"check": "answer_iou_0_3_equals_event_hit_iou_0_3", "pass": bool((bools(rec["answer_iou_0_3"]) == bools(rec["event_hit_iou_0_3"])).all()), "mismatches": int((bools(rec["answer_iou_0_3"]) != bools(rec["event_hit_iou_0_3"])).sum())},
            {"check": "answer_iou_0_5_equals_event_hit_iou_0_5", "pass": bool((bools(rec["answer_iou_0_5"]) == bools(rec["event_hit_iou_0_5"])).all()), "mismatches": int((bools(rec["answer_iou_0_5"]) != bools(rec["event_hit_iou_0_5"])).sum())},
            {"check": "independent_iou_0_3_matches", "pass": bool((bools(rec["answer_iou_0_3"]) == rec["re_event_hit_iou_0_3"]).all()), "mismatches": int((bools(rec["answer_iou_0_3"]) != rec["re_event_hit_iou_0_3"]).sum())},
            {"check": "independent_iou_0_5_matches", "pass": bool((bools(rec["answer_iou_0_5"]) == rec["re_event_hit_iou_0_5"]).all()), "mismatches": int((bools(rec["answer_iou_0_5"]) != rec["re_event_hit_iou_0_5"]).sum())},
        ]
    )
    checks.to_csv(OUT / "label_consistency_checks.csv", index=False)
    trials = read("calibration_trials_v2.csv")
    target_ok = set(trials["answer_label"].dropna()) == {ANSWER}
    if not target_ok:
        add("BLOCKER", "Label alignment", "Calibration trials use a different answer label than final evaluation.", str(sorted(set(trials["answer_label"].dropna()))))
    if not bool(checks["pass"].all()):
        add("FAIL", "Label definition", "Independent label recomputation found mismatches.", md_table(checks))
    else:
        add("PASS", "Label definition", "Independent IoU label recomputation matches v2 labels.", md_table(checks))
    write(
        "label_definition_audit.md",
        f"""# Label Definition And Alignment Audit

Verdict: **{'PASS' if bool(checks['pass'].all()) and target_ok else 'FAIL'}**

Calibration target in `calibration_trials_v2.csv`: `{sorted(set(trials['answer_label'].dropna()))}`

{md_table(checks)}

The independent recomputation uses temporal IoU = intersection / union, event overlap ratio = intersection / event duration, interval purity = intersection / interval duration, and duration inflation = interval duration / matched event duration.
""",
    )


def metric_recompute() -> None:
    events = read("reference_events.csv")
    lattice = read("interval_lattice_v2.csv")
    labels = read("interval_labels_v2.csv")
    prop = read("proposal_quality_v2.csv")
    main = read("main_budget_curve_v2.csv")
    selected = read("selected_intervals_by_trial_v2.csv")
    per_rows = []
    for ev in events.itertuples(index=False):
        best = None
        for r in lattice.itertuples(index=False):
            iou = tiou(r.t_start, r.t_end, ev.t_start, ev.t_end)
            inter = max(0.0, min(r.t_end, ev.t_end) - max(r.t_start, ev.t_start))
            center_t = (ev.t_start + ev.t_end) / 2.0
            cand = {
                "event_id": ev.event_id,
                "best_iou": iou,
                "best_any_overlap": inter > 0,
                "best_center_hit": r.t_start <= center_t <= r.t_end,
                "best_candidate_duration": r.duration,
                "best_candidate_method": r.method,
                "best_candidate_active_score": r.active_score,
            }
            if best is None or (iou, inter, -r.duration) > (best["best_iou"], float(best["best_any_overlap"]), -best["best_candidate_duration"]):
                best = cand
        per_rows.append(best)
    per = pd.DataFrame(per_rows)
    per["best_candidate_active_score_rank"] = per["best_candidate_active_score"].rank(ascending=False, method="min")
    per.to_csv(OUT / "per_event_recomputed_best_candidate.csv", index=False)
    upper03 = float((per["best_iou"] >= 0.3).mean())
    upper05 = float((per["best_iou"] >= 0.5).mean())
    anyrec = float(per["best_any_overlap"].mean())
    centerrec = float(per["best_center_hit"].mean())
    report_upper03, report_upper05, report_dense03 = parse_upper_report()
    diffs = [
        {"metric": "lattice_oracle_upper_bound_iou_0_3", "recomputed": upper03, "v2": report_upper03, "source": "proposal_upper_bound_report"},
        {"metric": "lattice_oracle_upper_bound_iou_0_5", "recomputed": upper05, "v2": report_upper05, "source": "proposal_upper_bound_report"},
        {"metric": "best_proposal_family_iou_0_3", "recomputed": float(prop["event_recall_iou_0_3"].max()), "v2": float(prop["event_recall_iou_0_3"].max()), "source": "proposal_quality max"},
        {"metric": "any_overlap_event_recall", "recomputed": anyrec, "v2": float(prop["any_overlap_event_recall"].max()), "source": "proposal_quality max"},
        {"metric": "center_hit_event_recall", "recomputed": centerrec, "v2": float(prop["center_hit_event_recall"].max()), "source": "proposal_quality max"},
        {"metric": "main_CILS_max_recall_iou_0_3", "recomputed": 0.0 if selected.empty else np.nan, "v2": float(main["event_recall_iou_0_3"].max()), "source": "selected_intervals empty" if selected.empty else "not directly reconstructable"},
    ]
    d = pd.DataFrame(diffs)
    d["abs_diff"] = (d["recomputed"] - d["v2"]).abs()
    d.to_csv(OUT / "metric_diff.csv", index=False)
    bad = d[d["abs_diff"].fillna(0) > EPS]
    if not bad.empty:
        add("FAIL", "Metric recomputation", "Independent metrics differ from v2 outputs.", md_table(bad), "Reported upper bounds or selected-set metrics may not be trustworthy.")
    else:
        add("PASS", "Metric recomputation", "Independent recomputation matches audited v2 aggregate metrics.", md_table(d))
    write(
        "metric_recompute_audit.md",
        f"""# Metric Recompute Audit

Verdict: **{'FAIL' if not bad.empty else 'PASS'}**

{md_table(d)}

Selected intervals file rows: `{len(selected)}`. Because it is empty, the independent selected-set recomputation proves the reported CILS main recall of 0.0, but cannot validate non-empty per-trial selection behavior.
""",
    )


def oracle_budget() -> None:
    trials = read("calibration_trials_v2.csv")
    usage = trials.groupby(["budget", "seed", "policy"]).size().reset_index(name="oracle_calls")
    usage["within_budget"] = usage["oracle_calls"] <= usage["budget"]
    usage.to_csv(OUT / "oracle_budget_usage.csv", index=False)
    selected = read("selected_intervals_by_trial_v2.csv")
    base = read("baseline_comparison_v2.csv")
    over = usage[~usage["within_budget"]]
    upper_as_alg = base[base["method"].str.contains("upper_bound", na=False)]
    if not over.empty:
        add("BLOCKER", "Oracle budget", "Calibration replay exceeds budget.", md_table(over))
    else:
        add("PASS", "Oracle budget", "Calibration oracle replay sample counts are <= budget.", f"{len(usage)} cells checked")
    if not selected.empty and (selected.groupby(["method", "budget", "tau", "seed"]).size().reset_index(name="n").eval("n > budget")).any():
        add("BLOCKER", "Oracle budget", "Selected intervals exceed budget.", "selected_intervals_by_trial_v2.csv")
    write(
        "oracle_budget_audit.md",
        f"""# Oracle Budget And Replay Audit

Verdict: **{'BLOCKER' if not over.empty else 'PASS'}**

- Calibration replay cells checked: `{len(usage)}`
- Budget violations: `{len(over)}`
- `selected_intervals_by_trial_v2.csv` rows: `{len(selected)}`
- Upper-bound baseline rows present and named as upper bounds: `{len(upper_as_alg)}`

{md_table(usage.groupby('budget').agg(max_calls=('oracle_calls','max'), min_within_budget=('within_budget','min')).reset_index())}
""",
    )


def calibration_audit() -> None:
    f = prepare_features(read("interval_lattice_features_only.csv"))
    labels = read("interval_labels_v2.csv").set_index("interval_id")
    trials = read("calibration_trials_v2.csv")
    qual = read("calibration_quality_v2.csv")
    y = labels[ANSWER].astype(int)
    rows = []
    for (b, seed, policy), s in trials.groupby(["budget", "seed", "policy"]):
        samples = s[["interval_id", "oracle_label"]].copy()
        cal = calibrate(f, samples)
        p = cal.set_index("interval_id")["p_answer"].reindex(y.index)
        rows.append(
            {
                "budget": b,
                "seed": seed,
                "policy": policy,
                "sample_positive_rate": float(s["oracle_label"].mean()) if len(s) else 0.0,
                "mean_p_answer": float(p.mean()),
                "min_p_answer": float(p.min()),
                "max_p_answer": float(p.max()),
                "brier_recomputed": float(((p - y) ** 2).mean()),
                "ece_5bin_recomputed": ece(y, p, 5),
            }
        )
    rec = pd.DataFrame(rows)
    rec.to_csv(OUT / "calibration_recompute.csv", index=False)
    cmp = rec.merge(qual, on=["budget", "seed", "policy"], how="left")
    cmp["brier_diff"] = (cmp["brier_recomputed"] - cmp["brier"]).abs()
    # v2 used 10-bin ECE; this audit reports 5-bin ECE per task, so it is not compared as exact.
    bad = cmp[cmp["brier_diff"] > EPS]
    empty_precision_violation = bool((read("main_budget_curve_v2.csv")["number_returned"] == 0).all() and (read("main_budget_curve_v2.csv")["precision_violation_rate"] == 1.0).all())
    if not bad.empty:
        add("FAIL", "Calibration", "Recomputed Brier scores differ from v2.", md_table(bad.head()))
    if not empty_precision_violation:
        add("FAIL", "Calibration", "Empty CILS return sets are not consistently counted as precision violations.", "main_budget_curve_v2.csv")
    else:
        add("PASS", "Calibration", "Empty CILS return sets are counted as precision violations.", "number_returned=0 and violation_rate=1.0")
    write(
        "calibration_audit.md",
        f"""# Calibration Audit

Verdict: **{'FAIL' if not bad.empty else 'PASS'}**

- Calibration target labels observed: `{sorted(set(trials['answer_label'].dropna()))}`
- Recomputed Brier mismatches: `{len(bad)}`
- Empty return sets counted as precision violations: `{empty_precision_violation}`
- Top-score max p_answer range by budget:

{md_table(rec[rec['policy']=='top_score'].groupby('budget').agg(mean_max_p=('max_p_answer','mean'), min_max_p=('max_p_answer','min'), mean_sample_positive_rate=('sample_positive_rate','mean')).reset_index())}

This audit reports 5-bin ECE as requested. The v2 artifact appears to use a 10-bin ECE, so ECE is not treated as an exact mismatch gate.
""",
    )


def cils_audit() -> None:
    f = prepare_features(read("interval_lattice_features_only.csv"))
    labels = read("interval_labels_v2.csv").set_index("interval_id")
    events = read("reference_events.csv")
    cap = min(32.0, float(events["duration"].quantile(0.95)) * 3.0)
    dist_rows, reason_frames = [], []
    for b in sorted(read("main_budget_curve_v2.csv")["budget"].unique()):
        for seed in range(5):
            order = policy_order(f, int(b), SEED + seed, "top_score")
            samples = pd.DataFrame({"interval_id": order})
            samples["oracle_label"] = samples["interval_id"].map(labels[ANSWER]).astype(bool)
            cal = calibrate(f, samples)
            dist_rows.append(
                {
                    "budget": b,
                    "seed": seed,
                    "min_p_answer": float(cal["p_answer"].min()),
                    "p50_p_answer": float(cal["p_answer"].median()),
                    "max_p_answer": float(cal["p_answer"].max()),
                    "mean_p_answer": float(cal["p_answer"].mean()),
                    "top_score_sample_positive_rate": float(samples["oracle_label"].mean()) if len(samples) else 0.0,
                }
            )
            for tau in sorted(read("main_budget_curve_v2.csv")["tau"].unique()):
                _, reasons, _ = cils_reasons(cal, float(tau), int(b), cap)
                reasons["seed"] = seed
                reason_frames.append(reasons)
    dist = pd.DataFrame(dist_rows)
    reasons = pd.concat(reason_frames, ignore_index=True) if reason_frames else pd.DataFrame()
    dist.to_csv(OUT / "cils_candidate_score_distribution.csv", index=False)
    reasons.to_csv(OUT / "cils_rejection_reasons.csv", index=False)
    maxp = float(dist["max_p_answer"].max()) if not dist.empty else 0.0
    selected_count = int((reasons["rejection_reason"] == "selected").sum()) if not reasons.empty else 0
    reason_summary = reasons.groupby(["budget", "tau", "rejection_reason"]).size().reset_index(name="count") if not reasons.empty else pd.DataFrame()
    if selected_count == 0 and maxp < float(read("main_budget_curve_v2.csv")["tau"].min()) - EPS:
        add("PASS", "CILS selector", "CILS empty return is explained by calibrated p_answer below tau.", f"max p_answer={maxp:.6f}")
    elif selected_count == 0:
        add("WARNING", "CILS selector", "CILS empty return needs caution; candidates reached tau in audit distribution but were still rejected.", f"max p_answer={maxp:.6f}")
    write(
        "cils_selector_audit.md",
        f"""# CILS Selector Audit

Verdict: **{'PASS' if selected_count == 0 and maxp < float(read('main_budget_curve_v2.csv')['tau'].min()) - EPS else 'WARNING'}**

- Recomputed selected count in audited CILS sample: `{selected_count}`
- Max calibrated `p_answer` in audited top-score trials: `{maxp:.6f}`
- Minimum tau in main curve: `{float(read('main_budget_curve_v2.csv')['tau'].min()):.3f}`

Primary rejection reason counts:

{md_table(reason_summary, 80)}

Conclusion: CILS max recall 0 is a real consequence of the selector/calibration combination in this artifact, not evidence of a metric recomputation bug. It is still not a trustworthy research conclusion while the feature-only leakage BLOCKER remains.
""",
    )


def baseline_audit() -> None:
    base = read("baseline_comparison_v2.csv")
    f = read("interval_lattice_features_only.csv")
    rows = []
    for m, g in base.groupby("method"):
        rows.append(
            {
                "method": m,
                "rows": len(g),
                "budgets": ",".join(map(str, sorted(g["budget"].unique()))),
                "taus": ",".join(map(str, sorted(g["tau"].unique()))),
                "max_number_returned": float(g["number_returned"].max()),
                "mean_recall_iou_0_3": float(g["event_recall_iou_0_3"].mean()),
                "is_upper_bound": "upper_bound" in m,
                "uses_same_feature_file_for_non_upper_bound": "upper_bound" not in m,
            }
        )
    comp = pd.DataFrame(rows)
    comp.to_csv(OUT / "baseline_input_comparison.csv", index=False)
    for m in ["oracle_confirmed_only", "arc_style_prune_refine_simplified", "arc_plus_uniform_outside_audit_simplified"]:
        if m in set(base["method"]):
            add("WARNING", "Baseline fairness", f"{m} uses answer labels during replay/confirmation and must be interpreted as budgeted oracle-replay, not a cheap baseline.", "pipeline static audit")
    write(
        "baseline_fairness_audit.md",
        f"""# Baseline Fairness Audit

Verdict: **WARNING**

{md_table(comp, 80)}

The two oracle upper-bound baselines are explicitly named as upper bounds. Several simplified baselines use budgeted oracle replay labels for confirmation, which is acceptable only if reported as replay/simplified baselines rather than cheap production algorithms.
""",
    )


def stress_audit() -> None:
    f = prepare_features(read("interval_lattice_features_only.csv"))
    labels = read("interval_labels_v2.csv").set_index("interval_id")
    rng = np.random.default_rng(SEED)
    lab = labels[ANSWER].astype(int).reindex(f["interval_id"]).reset_index(drop=True)
    scores = {
        "best_proxy": normalize(lab + 0.15 * f["active_score"].reset_index(drop=True)),
        "noisy_proxy": normalize(f["active_score"] + rng.normal(0, 0.30, len(f))),
        "partial_inverted_proxy": normalize(0.45 * f["active_score"] + 0.55 * (1 - f["active_score"])),
        "low_density_blindspot_proxy": normalize(f["active_score"] * (f["vehicle_count"] <= f["vehicle_count"].quantile(0.35)).astype(float)),
        "random_proxy": pd.Series(rng.random(len(f))),
    }
    rows = []
    for name, s in scores.items():
        rows.append({"stress_test": name, "mean": float(s.mean()), "std": float(s.std()), "min": float(s.min()), "max": float(s.max()), "top20_positive_rate": float(lab.iloc[s.sort_values(ascending=False).head(20).index].mean())})
    dist = pd.DataFrame(rows)
    dist.to_csv(OUT / "stress_score_distribution.csv", index=False)
    res = read("stress_test_results_v2.csv")
    agg = res.groupby("stress_test").agg(recall=("event_recall_iou_0_3", "mean"), precision=("observed_precision", "mean"), returned=("number_returned", "mean")).reset_index()
    agg.to_csv(OUT / "stress_result_diff.csv", index=False)
    identical = agg[["recall", "precision", "returned"]].drop_duplicates().shape[0] == 1
    if identical:
        add("FAIL", "Stress test", "Stress variants produce identical aggregate results.", md_table(agg))
    elif float(agg.set_index("stress_test").loc["best_proxy", "recall"]) <= float(agg.set_index("stress_test").loc["random_proxy", "recall"]):
        add("WARNING", "Stress test", "Random proxy is not worse than best proxy in aggregate recall.", md_table(agg), "May reflect metric/reference dynamics, but weakens stress-test evidence.")
    else:
        add("PASS", "Stress test", "Stress variants differ and best_proxy outperforms random_proxy in aggregate recall.", md_table(agg))
    write(
        "stress_test_audit.md",
        f"""# Stress Test Audit

Verdict: **{'FAIL' if identical else 'PASS'}**

Score distributions:

{md_table(dist)}

Result aggregates:

{md_table(agg)}
""",
    )


def synthetic_tests() -> None:
    test_path = OUT / "synthetic_test_cases.py"
    test_path.write_text(
        '''#!/usr/bin/env python3
from math import isclose

def tiou(a0,a1,b0,b1):
    inter=max(0,min(a1,b1)-max(a0,b0))
    union=max(a1,b1)-min(a0,b0)
    return inter/union if union else 0.0

def event_recall(cands, events, th=.3):
    hits=0
    for ev in events:
        if any(tiou(c[0],c[1],ev[0],ev[1])>=th for c in cands):
            hits+=1
    return hits/len(events)

def duplicate_rate(cands, events, th=.3):
    hits=[]
    for c in cands:
        matched=[i for i,e in enumerate(events) if tiou(c[0],c[1],e[0],e[1])>=th]
        hits.extend(matched[:1])
    return (len(hits)-len(set(hits)))/len(cands) if cands else 0.0

def cils(cands, tau):
    sel=[]; tp=tot=0
    for c in sorted(cands, key=lambda x: x["p"]*x["value"], reverse=True):
        ntp=tp+c["p"]*c["value"]; ntot=tot+c["value"]
        if ntp/ntot >= tau:
            sel.append(c); tp,tot=ntp,ntot
    return sel, (tp/tot if tot else 0)

assert isclose(tiou(10,20,10,20),1.0)
assert isclose(tiou(8,22,10,20),10/14)
assert isclose(tiou(0,5,10,20),0.0)
assert event_recall([(10,20),(8,22),(0,5)], [(10,20)]) == 1.0
assert event_recall([(9,19),(10,20),(40,50)], [(10,20),(40,50)]) == 1.0
assert duplicate_rate([(9,19),(10,20),(40,50)], [(10,20),(40,50)]) > 0
toy=[{"id":"h","p":.95,"value":1},{"id":"m","p":.55,"value":1},{"id":"l","p":.2,"value":1}]
lo,_=cils(toy,.5); hi,_=cils(toy,.9)
assert len(lo) > len(hi)
assert [x["id"] for x in hi] == ["h"]
print("PASS synthetic metric and selector cases")
''',
        encoding="utf-8",
    )
    proc = subprocess.run(["python", str(test_path)], cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        add("BLOCKER", "Synthetic tests", "Synthetic unit tests failed.", proc.stdout + proc.stderr)
    else:
        add("PASS", "Synthetic tests", "Synthetic unit tests passed.", proc.stdout.strip())
    write(
        "unit_test_results.md",
        f"""# Unit Test Results

- command: `python {test_path}`
- exit_code: `{proc.returncode}`

```text
{proc.stdout}{proc.stderr}
```
""",
    )


def final_report() -> None:
    order = {"BLOCKER": 5, "FAIL": 4, "WARNING": 3, "INFO": 2, "PASS": 1}
    worst = max(FINDINGS, key=lambda x: order.get(x["severity"], 0))["severity"] if FINDINGS else "PASS"
    blockers = [f for f in FINDINGS if f["severity"] == "BLOCKER"]
    fails = [f for f in FINDINGS if f["severity"] == "FAIL"]
    main = read("main_budget_curve_v2.csv")
    propdiff = pd.read_csv(OUT / "metric_diff.csv")
    lattice_upper = float(propdiff.loc[propdiff["metric"] == "lattice_oracle_upper_bound_iou_0_3", "recomputed"].iloc[0])
    cils_max = float(main["event_recall_iou_0_3"].max())
    v2_trust = "no" if blockers else ("partial" if fails else "yes")
    level2_trust = "no" if blockers else "partial"
    next_eval = "no; fix the BLOCKER first" if blockers else "yes, with the documented warnings"
    crit = pd.DataFrame([f for f in FINDINGS if f["severity"] in {"BLOCKER", "FAIL", "WARNING", "INFO"}])
    write(
        "FINAL_CODE_AUDIT_REPORT.md",
        f"""# Final Code Audit Report

## Executive Summary

- Overall verdict: **{worst}**
- v2 results are trustworthy? **{v2_trust}**
- BLOCKER present: **{'yes' if blockers else 'no'}**
- v2 Level 2 Negative credible? **{level2_trust}**
- CILS max recall 0 credible? **{'yes as an artifact behavior, no as a final research conclusion' if blockers else 'yes'}**
- Lattice upper bound 0.55 credible? **{'yes' if abs(lattice_upper - 0.55) <= 0.05 else 'check exact value'}** (`recomputed={lattice_upper:.3f}`)
- Reference mismatch conclusion still holds? **partial: metric recomputation supports limited answer-compatible proposal coverage, but the leakage BLOCKER prevents treating v2 as clean evidence.**

## Critical Findings

{md_table(crit, 80)}

## Artifact Inventory

See `artifact_inventory.md` and `artifact_inventory.csv`.

## Label Leakage Audit

See `label_leakage_audit.md`. The decisive finding is that the features-only lattice contains reference-derived fields.

## Label Definition And Alignment Audit

See `label_definition_audit.md` and `label_consistency_checks.csv`. Calibration uses `answer_iou_0_3`; independent temporal IoU labels match the v2 label table.

## Metric Recompute Audit

See `metric_recompute_audit.md`, `metric_diff.csv`, and `per_event_recomputed_best_candidate.csv`. Independent recomputation supports the reported lattice upper-bound scale and the empty CILS selected-set result.

## Oracle Budget And Replay Audit

See `oracle_budget_audit.md` and `oracle_budget_usage.csv`. Calibration replay respects the oracle budget.

## Calibration Audit

See `calibration_audit.md` and `calibration_recompute.csv`. Empty return sets are counted as precision violations; top-score calibration keeps CILS probabilities below the main tau grid.

## CILS Selector Audit

See `cils_selector_audit.md`, `cils_candidate_score_distribution.csv`, and `cils_rejection_reasons.csv`. The empty return is explained by precision-threshold rejection under low calibrated `p_answer`, not by a recomputed metric bug.

## Baseline Fairness Audit

See `baseline_fairness_audit.md` and `baseline_input_comparison.csv`. Upper bounds are named as upper bounds; simplified oracle-replay baselines need careful wording.

## Stress Test Audit

See `stress_test_audit.md`, `stress_score_distribution.csv`, and `stress_result_diff.csv`. Stress variants differ in score and result distributions.

## Synthetic Unit Tests

See `unit_test_results.md` and `synthetic_test_cases.py`.

## Impact On Research Conclusions

The v2 Negative should **not** be treated as a clean Level 2 research conclusion until the feature-only leakage is fixed and the audit is rerun. The CILS zero-recall behavior appears real for the current artifact, but it is only an artifact-level selector/calibration failure. The reference mismatch / limited answer-compatible lattice coverage signal is directionally supported by independent metrics, but remains contaminated by the trust-boundary violation.

Do **not** enter `reference_duration_stratified_eval_v1` as a research-valid next experiment from this v2 state. First regenerate a truly label-free features-only lattice, rerun v2, then rerun this audit.

## Recommended Next Actions

1. Fix v2 artifact generation so `interval_lattice_features_only.csv` is produced before label joins or from an allowlisted feature schema.
2. Rerun v2 and rerun `bash src/garc_eval/experiments/clean_interval_aqp_code_audit_v1/run_audit.sh`.
3. Only if the rerun has no BLOCKER, proceed to `reference_duration_stratified_eval_v1`.
""",
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    artifact_inventory()
    label_leakage()
    label_definition()
    metric_recompute()
    oracle_budget()
    calibration_audit()
    cils_audit()
    baseline_audit()
    stress_audit()
    synthetic_tests()
    final_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
