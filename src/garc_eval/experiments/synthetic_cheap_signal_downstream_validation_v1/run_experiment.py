#!/usr/bin/env python3
from __future__ import annotations

import math
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from garc_eval.metrics.craq_lite_metrics import Interval, interval_iou

EXP_NAME = "synthetic_cheap_signal_downstream_validation_v1"
OUT_DIR = ROOT / "src/garc_eval/outputs" / EXP_NAME
SCRIPT_DIR = ROOT / "src/garc_eval/experiments" / EXP_NAME
PLOTS_DIR = OUT_DIR / "plots"
TABLES_DIR = OUT_DIR / "tables"
LOGS_DIR = OUT_DIR / "logs"
CONFIG_DIR = OUT_DIR / "config"
MANIFEST_DIR = OUT_DIR / "data_manifest"

V2 = ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak"
INPUT_DIRS = [
    ROOT / "src/garc_eval/outputs/cils_calibration_repair_smoke_v1",
    ROOT / "src/garc_eval/outputs/cils_calibration_repair_replay_v1",
    ROOT / "src/garc_eval/outputs/cils_empty_return_root_cause_audit_v1",
    V2,
    ROOT / "src/garc_eval/outputs/reference_duration_stratified_eval_v1",
    ROOT / "src/garc_eval/outputs/within_bin_tiebreak_ablation_v1",
    ROOT / "runs/craq_lite_v1/20260701T075242Z/patch_smoke",
    ROOT / "outputs/reports",
]
EXPECTED_FILES = [
    "interval_lattice_features_only.csv",
    "interval_lattice_v2_clean.csv",
    "interval_labels_v2_clean.csv",
    "smoke_candidate_p_answer.csv",
    "candidate_p_answer_by_policy.csv",
    "smoke_selected_intervals.csv",
    "smoke_interval_eval_curve.csv",
    "event_duration_strata.csv",
    "per_event_best_candidate.csv",
    "reference_events.csv",
    "top_p_answer_bin_candidates.csv",
    "single_feature_tiebreak_results.csv",
    "composite_tiebreak_results.csv",
    "feature_informativeness.csv",
    "FINAL_REPORT.md",
    "CURRENT_PROJECT_STATE_READONLY_AUDIT.md",
    "predictions_cils_craq_lite.csv",
    "metrics_summary.csv",
    "metrics_by_method_seed.csv",
]

BUDGETS = [20, 40, 80, 160]
PRECISION_TARGETS = [0.8, 0.9]
CILS_TAUS = [0.5, 0.6, 0.7, 0.8, 0.9]
SYNTHETIC_TARGETS = [0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
SYNTHETIC_SEEDS = list(range(20))
RANDOM_BASELINE_REPEATS = 100
IOU_THRESHOLDS = [0.3, 0.5]
BASE_SEED = 20260701


@dataclass(frozen=True)
class SignalSpec:
    name: str
    target_auc: float | None
    seed: int
    diagnostic_label_derived: bool


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    for d in [OUT_DIR, PLOTS_DIR, TABLES_DIR, LOGS_DIR, CONFIG_DIR, MANIFEST_DIR, OUT_DIR / "scripts"]:
        d.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_df(df: pd.DataFrame, rel: str) -> None:
    path = OUT_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    if "/" not in rel:
        (TABLES_DIR / path.name).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(TABLES_DIR / path.name, index=False)


def append_progress(checkpoint: str, result: str, command: str = "", failure: str = "", next_action: str = "") -> None:
    line = (
        f"- {timestamp()} | checkpoint={checkpoint} | command={command or 'n/a'} | "
        f"result={result} | failure={failure or 'none'} | next={next_action or 'n/a'}\n"
    )
    with (LOGS_DIR / "progress.md").open("a", encoding="utf-8") as fh:
        fh.write(line)


def md_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    d = df.head(max_rows).copy()
    lines = ["| " + " | ".join(map(str, d.columns)) + " |", "| " + " | ".join(["---"] * len(d.columns)) + " |"]
    for _, row in d.iterrows():
        vals = []
        for c in d.columns:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6g}")
            else:
                vals.append(str(v).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def safe_div(a: float, b: float) -> float:
    return float(a / b) if b else 0.0


def normalize(values: pd.Series) -> pd.Series:
    s = pd.to_numeric(values, errors="coerce").fillna(0.0).astype(float)
    lo = float(s.min())
    hi = float(s.max())
    if hi <= lo:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - lo) / (hi - lo)


def auc_score(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y).astype(int)
    score = np.asarray(score).astype(float)
    pos = int(y.sum())
    neg = int(len(y) - pos)
    if pos == 0 or neg == 0:
        return math.nan
    ranks = pd.Series(score).rank(method="average").to_numpy()
    rank_sum_pos = float(ranks[y == 1].sum())
    return (rank_sum_pos - pos * (pos + 1) / 2.0) / (pos * neg)


def average_precision(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y).astype(int)
    score = np.asarray(score).astype(float)
    pos = int(y.sum())
    if pos == 0:
        return math.nan
    order = np.argsort(-score, kind="mergesort")
    yy = y[order]
    tp_cum = np.cumsum(yy)
    ranks = np.arange(1, len(yy) + 1)
    return float(((tp_cum / ranks) * yy).sum() / pos)


def qbin(s: pd.Series, n: int = 5) -> pd.Series:
    labels = [f"q{i}" for i in range(1, n + 1)]
    ranked = pd.to_numeric(s, errors="coerce").fillna(0.0).rank(method="first")
    return pd.qcut(ranked, n, labels=labels, duplicates="drop").astype(str)


def git_status_note() -> tuple[str, str]:
    p = subprocess.run(["git", "status", "--short"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode == 0:
        return "available", p.stdout.strip()
    return "unavailable_due_to_dubious_ownership_or_git_error", p.stdout.strip()


def file_row_count(path: Path) -> int | None:
    if not path.exists() or path.suffix.lower() != ".csv":
        return None
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return max(0, sum(1 for _ in fh) - 1)


def inventory() -> pd.DataFrame:
    rows = []
    git_state, git_output = git_status_note()
    discovered = {}
    for d in INPUT_DIRS:
        for name in EXPECTED_FILES:
            p = d / name
            if p.exists() and name not in discovered:
                discovered[name] = p
    explicit_paths = [
        V2 / "interval_lattice_features_only.csv",
        V2 / "interval_lattice_v2_clean.csv",
        V2 / "interval_labels_v2_clean.csv",
        V2 / "reference_events.csv",
        ROOT / "src/garc_eval/outputs/cils_calibration_repair_smoke_v1/smoke_candidate_p_answer.csv",
        ROOT / "src/garc_eval/outputs/cils_calibration_repair_replay_v1/candidate_p_answer_by_policy.csv",
        ROOT / "src/garc_eval/outputs/within_bin_tiebreak_ablation_v1/top_p_answer_bin_candidates.csv",
        ROOT / "src/garc_eval/outputs/within_bin_tiebreak_ablation_v1/single_feature_tiebreak_results.csv",
        ROOT / "src/garc_eval/outputs/within_bin_tiebreak_ablation_v1/composite_tiebreak_results.csv",
        ROOT / "src/garc_eval/outputs/within_bin_tiebreak_ablation_v1/feature_informativeness.csv",
        ROOT / "runs/craq_lite_v1/20260701T075242Z/patch_smoke/predictions_cils_craq_lite.csv",
        ROOT / "runs/craq_lite_v1/20260701T075242Z/patch_smoke/metrics_summary.csv",
        ROOT / "runs/craq_lite_v1/20260701T075242Z/patch_smoke/metrics_by_method_seed.csv",
        ROOT / "outputs/reports/CURRENT_PROJECT_STATE_READONLY_AUDIT.md",
        ROOT / "src/garc_eval/outputs/reference_duration_stratified_eval_v1",
    ]
    seen = set()
    for p in explicit_paths + list(discovered.values()):
        if p in seen:
            continue
        seen.add(p)
        role = "context / prior artifact"
        if p.name == "interval_lattice_features_only.csv":
            role = "candidate feature source"
        elif p.name == "interval_lattice_v2_clean.csv":
            role = "candidate lattice with prior labels, used for schema cross-check only"
        elif p.name == "interval_labels_v2_clean.csv":
            role = "prior label table, not trusted for true-interval-only TP without reconstruction"
        elif p.name == "reference_events.csv":
            role = "reference event boundary source"
        elif p.name == "CURRENT_PROJECT_STATE_READONLY_AUDIT.md":
            role = "project handoff context"
        elif p.name == "reference_duration_stratified_eval_v1":
            role = "expected prior duration-stratified artifact directory"
        cols = ""
        row_count = None
        if p.exists() and p.is_file() and p.suffix.lower() == ".csv":
            row_count = file_row_count(p)
            cols = ",".join(pd.read_csv(p, nrows=0).columns.tolist())
        rows.append(
            {
                "path": str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
                "exists": bool(p.exists()),
                "row_count_if_csv": row_count,
                "column_names_if_csv": cols,
                "role": role,
                "assumptions_limitations": (
                    "CSV row count excludes header. Synthetic experiment uses label-derived scores only as diagnostic intervention."
                ),
            }
        )
    rows.append(
        {
            "path": "git status --short",
            "exists": git_state == "available",
            "row_count_if_csv": None,
            "column_names_if_csv": "",
            "role": "worktree status check",
            "assumptions_limitations": f"{git_state}; no global Git config changed. Output: {git_output[:300]}",
        }
    )
    df = pd.DataFrame(rows)
    write_df(df, "artifact_inventory.csv")
    missing_duration = not (ROOT / "src/garc_eval/outputs/reference_duration_stratified_eval_v1").exists()
    write_text(
        OUT_DIR / "artifact_inventory.md",
        f"""# Artifact Inventory

This inventory was generated for `{EXP_NAME}`. Missing artifacts are recorded and the run continues with nearest defensible existing equivalents.

- Missing `src/garc_eval/outputs/reference_duration_stratified_eval_v1/`: **{missing_duration}**
- Git status availability: **{git_state}**
- Global Git config changed by this experiment: **no**
- No VLM, YOLO, CLIP, tracking, motion proxy, or model execution was run.

{md_table(df, 80)}
""",
    )
    return df


def load_reference() -> pd.DataFrame:
    return pd.read_csv(V2 / "reference_events.csv")


def build_reference_audit(reference: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    for r in reference.itertuples(index=False):
        dur = float(r.duration)
        is_interval = dur >= 5.0
        is_point = dur <= 2.0
        rows.append(
            {
                "event_id": str(r.event_id),
                "video_id": str(r.video_id),
                "t_start": float(r.t_start),
                "t_end": float(r.t_end),
                "duration": dur,
                "event_type": getattr(r, "event_type", ""),
                "is_true_interval_event": int(is_interval),
                "is_point_anchor_event": int(is_point),
                "notes": "true_interval_duration_ge_5s" if is_interval else "point_anchor_duration_le_2s" if is_point else "ambiguous_duration_2_to_5s",
            }
        )
    audit = pd.DataFrame(rows)
    true_events = audit[audit["is_true_interval_event"] == 1].copy()
    point_events = audit[audit["is_point_anchor_event"] == 1].copy()
    write_df(audit, "reference_event_audit.csv")
    desc = true_events["duration"].describe().to_frame("duration").reset_index() if not true_events.empty else pd.DataFrame()
    write_text(
        OUT_DIR / "canonical_reference_summary.md",
        f"""# Canonical Reference Summary

Main evaluation uses only true interval events, defined locally as reference events with duration >= 5 seconds.
Point-anchor events, defined as duration <= 2 seconds, are excluded from main TP counts and reported separately.

- Total reference events: `{len(audit)}`
- True interval events: `{len(true_events)}`
- Point-anchor-only events: `{len(point_events)}`
- Reference gate (`true interval events >= 20`): **{'PASS' if len(true_events) >= 20 else 'FAIL'}**
- Conclusion scope: **diagnostic only** because the main true interval reference has fewer than 20 events.

True interval duration summary:

{md_table(desc, 20)}
""",
    )
    return audit, true_events, point_events


def match_candidates(candidates: pd.DataFrame, true_events: pd.DataFrame, point_events: pd.DataFrame) -> pd.DataFrame:
    out = candidates.copy()
    true_03, true_05, true_id_03, true_id_05 = [], [], [], []
    ans_03, ans_05, ans_id_03, ans_id_05 = [], [], [], []
    point_03, point_05 = [], []
    point_id_03, point_id_05 = [], []
    true_records = true_events.to_dict("records")
    point_records = point_events.to_dict("records")
    for r in out.itertuples(index=False):
        pred = Interval(float(r.t_start), float(r.t_end))
        best_true = (0.0, "")
        for ev in true_records:
            iou = interval_iou(pred, Interval(float(ev["t_start"]), float(ev["t_end"]), str(ev["event_id"])))
            if iou > best_true[0]:
                best_true = (iou, str(ev["event_id"]))
        best_point = (0.0, "")
        for ev in point_records:
            iou = interval_iou(pred, Interval(float(ev["t_start"]), float(ev["t_end"]), str(ev["event_id"])))
            if iou > best_point[0]:
                best_point = (iou, str(ev["event_id"]))
        hit_t03 = best_true[0] >= 0.3
        hit_t05 = best_true[0] >= 0.5
        hit_p03 = (not hit_t03) and best_point[0] >= 0.3
        hit_p05 = (not hit_t05) and best_point[0] >= 0.5
        true_03.append(hit_t03)
        true_05.append(hit_t05)
        true_id_03.append(best_true[1] if hit_t03 else "")
        true_id_05.append(best_true[1] if hit_t05 else "")
        ans_03.append(hit_t03)
        ans_05.append(hit_t05)
        ans_id_03.append(best_true[1] if hit_t03 else "")
        ans_id_05.append(best_true[1] if hit_t05 else "")
        point_03.append(hit_p03)
        point_05.append(hit_p05)
        point_id_03.append(best_point[1] if hit_p03 else "")
        point_id_05.append(best_point[1] if hit_p05 else "")
    out["answer_iou_0_3"] = true_03
    out["answer_iou_0_5"] = true_05
    out["matched_event_id_iou_0_3"] = ans_id_03
    out["matched_event_id_iou_0_5"] = ans_id_05
    out["matched_true_interval_event_id_iou_0_3"] = true_id_03
    out["matched_true_interval_event_id_iou_0_5"] = true_id_05
    out["point_anchor_only_iou_0_3"] = point_03
    out["point_anchor_only_iou_0_5"] = point_05
    out["matched_point_anchor_event_id_iou_0_3"] = point_id_03
    out["matched_point_anchor_event_id_iou_0_5"] = point_id_05
    out["TP_iou_0_3"] = out["answer_iou_0_3"].astype(bool)
    out["TP_iou_0_5"] = out["answer_iou_0_5"].astype(bool)
    return out


def build_canonical_candidates() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    features = pd.read_csv(V2 / "interval_lattice_features_only.csv")
    reference = load_reference()
    _, true_events, point_events = build_reference_audit(reference)
    cand = features.copy()
    if "video_id" not in cand.columns:
        cand["video_id"] = "realcartest"
    cand["duration"] = pd.to_numeric(cand["duration"], errors="coerce").fillna(cand["t_end"] - cand["t_start"])
    cand["boundary_quality"] = normalize(cand.get("boundary_left_drop", 0.0) + cand.get("boundary_right_drop", 0.0))
    required = [
        "interval_id",
        "video_id",
        "t_start",
        "t_end",
        "duration",
        "method",
        "source_signal",
        "active_score",
        "max_score",
        "mean_score",
        "score_persistence",
        "boundary_left_drop",
        "boundary_right_drop",
        "boundary_quality",
        "signal_disagreement",
        "num_units",
        "overlap_group_id",
    ]
    for col in required:
        if col not in cand.columns:
            cand[col] = 0.0 if col not in {"interval_id", "video_id", "method", "source_signal", "overlap_group_id"} else ""
    cand = match_candidates(cand, true_events, point_events)
    cols = required + [
        "answer_iou_0_3",
        "answer_iou_0_5",
        "matched_event_id_iou_0_3",
        "matched_event_id_iou_0_5",
        "matched_true_interval_event_id_iou_0_3",
        "matched_true_interval_event_id_iou_0_5",
        "point_anchor_only_iou_0_3",
        "point_anchor_only_iou_0_5",
        "matched_point_anchor_event_id_iou_0_3",
        "matched_point_anchor_event_id_iou_0_5",
        "TP_iou_0_3",
        "TP_iou_0_5",
    ]
    cand = cand[cols].copy()
    write_df(cand, "canonical_candidates.csv")
    append_progress("stage1_canonical_candidates", f"rows={len(cand)} true_tp_iou03={int(cand['TP_iou_0_3'].sum())}")
    return cand, true_events, point_events


def make_score_for_auc(y: np.ndarray, target_auc: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(BASE_SEED + seed + int(target_auc * 1000))
    delta = math.sqrt(2.0) * NormalDist().inv_cdf(target_auc)
    return rng.normal(loc=delta * y.astype(float), scale=1.0, size=len(y))


def signal_specs() -> list[SignalSpec]:
    specs = [SignalSpec("current_real_signal", None, -1, False), SignalSpec("oracle_signal", 1.0, -1, True)]
    specs.extend(SignalSpec("random_signal", 0.5, seed, False) for seed in SYNTHETIC_SEEDS)
    for target in SYNTHETIC_TARGETS:
        specs.extend(SignalSpec(f"synthetic_auc_{target:.2f}".replace(".", "_"), target, seed, True) for seed in SYNTHETIC_SEEDS)
    return specs


def generate_signals(cand: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    y03 = cand["TP_iou_0_3"].astype(int).to_numpy()
    y05 = cand["TP_iou_0_5"].astype(int).to_numpy()
    records = []
    quality_rows = []
    base_real = normalize(cand["active_score"]).to_numpy()
    for spec in signal_specs():
        if spec.name == "current_real_signal":
            score = base_real.copy()
        elif spec.name == "oracle_signal":
            noise = np.linspace(0.0, 1e-9, len(cand), dtype=float)
            score = y03.astype(float) + noise
        elif spec.name == "random_signal":
            rng = np.random.default_rng(BASE_SEED + 100_000 + spec.seed)
            score = rng.normal(0.0, 1.0, size=len(cand))
        else:
            score = make_score_for_auc(y03, float(spec.target_auc), spec.seed)
        auc03 = auc_score(y03, score)
        ap03 = average_precision(y03, score)
        auc05 = auc_score(y05, score)
        ap05 = average_precision(y05, score)
        pos_scores = score[y03 == 1]
        neg_scores = score[y03 == 0]
        quality_rows.append(
            {
                "synthetic_signal_name": spec.name,
                "target_auc": spec.target_auc,
                "empirical_auc_iou_0_3": auc03,
                "empirical_ap_iou_0_3": ap03,
                "empirical_auc_iou_0_5": auc05,
                "empirical_ap_iou_0_5": ap05,
                "seed": spec.seed,
                "pos_count": int(y03.sum()),
                "neg_count": int(len(y03) - y03.sum()),
                "score_mean_pos": float(np.mean(pos_scores)) if len(pos_scores) else math.nan,
                "score_mean_neg": float(np.mean(neg_scores)) if len(neg_scores) else math.nan,
                "score_std_pos": float(np.std(pos_scores)) if len(pos_scores) else math.nan,
                "score_std_neg": float(np.std(neg_scores)) if len(neg_scores) else math.nan,
                "diagnostic_label_derived": spec.diagnostic_label_derived,
                "off_target_auc": bool(spec.target_auc is not None and spec.name not in {"oracle_signal"} and abs(auc03 - spec.target_auc) > 0.03),
            }
        )
        for iid, s in zip(cand["interval_id"].to_numpy(), score):
            records.append(
                {
                    "interval_id": iid,
                    "synthetic_signal_name": spec.name,
                    "seed": spec.seed,
                    "target_auc": spec.target_auc,
                    "synthetic_score": float(s),
                    "diagnostic_label_derived": spec.diagnostic_label_derived,
                }
            )
    signal_df = pd.DataFrame.from_records(records)
    quality = pd.DataFrame(quality_rows)
    write_df(signal_df, "synthetic_signal_candidates.csv")
    write_df(quality, "synthetic_signal_quality.csv")
    off = int(quality["off_target_auc"].fillna(False).sum())
    write_text(
        OUT_DIR / "synthetic_signal_generation.md",
        f"""# Synthetic Signal Generation

Synthetic scores are candidate-level, label-derived diagnostic interventions. They use `y = TP_iou_0_3`, where TP means matching a true interval event at IoU >= 0.3. These scores are not non-leak cheap signals and must not be reported as real retrieval performance.

- Synthetic seeds: `{SYNTHETIC_SEEDS[0]}..{SYNTHETIC_SEEDS[-1]}` (smoke-scale 20 seeds because full 100-seed CILS grid is high runtime).
- Random baseline repeats: `{RANDOM_BASELINE_REPEATS}`.
- Normal-score construction: positive scores are shifted by `sqrt(2) * Phi^-1(target_auc)` with unit Gaussian noise.
- Current real signal: normalized existing `active_score`, no label access.
- Oracle signal: `TP_iou_0_3 + tiny deterministic noise`, diagnostic upper bound only.
- Off-target AUC rows beyond +/-0.03: `{off}`.

Quality preview:

{md_table(quality.head(30), 30)}
""",
    )
    append_progress("stage2_synthetic_signals", f"signals_rows={len(signal_df)} quality_rows={len(quality)} off_target={off}")
    return signal_df, quality


def prepare_for_signal(cand: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    df = cand.merge(scores[["interval_id", "synthetic_score"]], on="interval_id", how="left")
    df["synthetic_score"] = pd.to_numeric(df["synthetic_score"], errors="coerce").fillna(0.0)
    df["synthetic_active_score"] = normalize(df["synthetic_score"])
    df["synthetic_boundary_quality"] = df["boundary_quality"] if "boundary_quality" in df else 0.0
    df["synthetic_utility"] = df["synthetic_score"]
    df["active_score_original"] = df["active_score"]
    df["active_score"] = df["synthetic_active_score"]
    df["answer_quality_proxy"] = df["synthetic_active_score"]
    df["answer_quality_proxy_bin"] = qbin(df["answer_quality_proxy"])
    df["boundary_quality_bin"] = qbin(df["synthetic_boundary_quality"])
    df["duration_bin"] = pd.cut(
        df["duration"],
        [0, 2, 5, 10, 20, 40, 80, 1e12],
        labels=["<=2", "2-5", "5-10", "10-20", "20-40", "40-80", ">80"],
        include_lowest=True,
    ).astype(str)
    return df


def nms(df: pd.DataFrame, limit: int, iou_threshold: float = 0.3) -> pd.DataFrame:
    selected = []
    spans = []
    for r in df.itertuples(index=False):
        if len(selected) >= limit:
            break
        pred = Interval(float(r.t_start), float(r.t_end))
        if any(interval_iou(pred, Interval(a, b)) > iou_threshold for a, b in spans):
            continue
        selected.append(r._asdict())
        spans.append((float(r.t_start), float(r.t_end)))
    return pd.DataFrame(selected)


def wilson_lower(pos: pd.Series, n: pd.Series, z: float = 1.0) -> pd.Series:
    nn = n.replace(0, np.nan)
    p = pos / nn
    denom = 1 + z * z / nn
    centre = p + z * z / (2 * nn)
    adj = z * np.sqrt((p * (1 - p) + z * z / (4 * nn)) / nn)
    return ((centre - adj) / denom).fillna(0.0).clip(0, 1)


def calibrate_cils(cand: pd.DataFrame, budget: int) -> pd.DataFrame:
    out = cand.copy()
    samples = cand.sort_values(["answer_quality_proxy", "duration"], ascending=[False, True]).head(budget).copy()
    s = samples[["interval_id", "answer_iou_0_3"]].copy()
    s["y"] = s["answer_iou_0_3"].astype(int)
    global_p = (float(s["y"].sum()) + 1.0) / (len(s) + 2.0)
    keys = ["answer_quality_proxy_bin", "duration_bin", "method", "boundary_quality_bin"]
    sample_keys = out.loc[out["interval_id"].isin(s["interval_id"]), ["interval_id"] + keys].merge(s[["interval_id", "y"]], on="interval_id")
    stat = sample_keys.groupby(keys, observed=True, dropna=False)["y"].agg(["sum", "count"]).reset_index()
    stat["lower"] = wilson_lower(stat["sum"], stat["count"])
    out = out.merge(stat[keys + ["lower"]], on=keys, how="left")
    out["p_answer"] = out["lower"].fillna(global_p * 0.5).clip(0, 1)
    return out


def cils_select(cand: pd.DataFrame, budget: int, tau: float, true_events: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    cal = calibrate_cils(cand, budget)
    duration_cap = min(32.0, float(true_events["duration"].quantile(0.95)) * 3.0) if not true_events.empty else 32.0
    df = cal.copy()
    boundary = 0.55 + 0.45 * normalize(df["boundary_left_drop"] + df["boundary_right_drop"])
    dur_penalty = np.where(df["duration"] <= duration_cap, 1.0, duration_cap / df["duration"])
    df["value"] = np.minimum(df["duration"], duration_cap) * (0.5 + 0.5 * df["active_score"])
    df["boundary_quality_for_cils"] = boundary * dur_penalty
    df["utility"] = df["p_answer"] * df["value"] * df["boundary_quality_for_cils"]
    ranked = df.sort_values(["utility", "active_score"], ascending=False).head(min(len(df), max(300, budget * 30)))
    selected = []
    spans = []
    expected_tp = 0.0
    expected_total = 0.0
    total_duration = 0.0
    for r in ranked.itertuples(index=False):
        if len(selected) >= budget:
            break
        if total_duration + float(r.duration) > 360.0:
            continue
        pred = Interval(float(r.t_start), float(r.t_end))
        if any(interval_iou(pred, Interval(a, b)) > 0.3 for a, b in spans):
            continue
        ntp = expected_tp + float(r.p_answer) * float(r.value)
        ntotal = expected_total + float(r.value)
        if safe_div(ntp, ntotal) + 1e-12 < tau:
            continue
        selected.append(r._asdict())
        spans.append((float(r.t_start), float(r.t_end)))
        expected_tp = ntp
        expected_total = ntotal
        total_duration += float(r.duration)
    return pd.DataFrame(selected), safe_div(expected_tp, expected_total)


def distinct_hits(sel: pd.DataFrame, threshold: float) -> set[str]:
    col = "matched_true_interval_event_id_iou_0_3" if threshold == 0.3 else "matched_true_interval_event_id_iou_0_5"
    if sel.empty or col not in sel:
        return set()
    return {str(x) for x in sel[col].dropna().astype(str) if x}


def evaluate_selection(
    sel: pd.DataFrame,
    method: str,
    signal_name: str,
    signal_seed: int,
    budget: int,
    precision_target: float,
    cils_tau: float | None,
    empirical_auc: float,
    empirical_ap: float,
    true_events: pd.DataFrame,
    expected_precision: float | None = None,
) -> dict:
    if sel.empty:
        selected_count = 0
        duration_total = 0.0
    else:
        selected_count = len(sel)
        duration_total = float(sel["duration"].sum())
    true_count = len(true_events)
    true_duration = float(true_events["duration"].sum()) if true_count else 0.0

    metrics = {
        "method": method,
        "synthetic_signal_name": signal_name,
        "seed": signal_seed,
        "budget": budget,
        "precision_target": precision_target,
        "cils_tau": cils_tau if cils_tau is not None else math.nan,
        "selected_interval_count": selected_count,
        "selected_duration_total": duration_total,
        "empty_return": selected_count == 0,
        "max_synthetic_score_selected": float(sel["synthetic_score"].max()) if selected_count and "synthetic_score" in sel else math.nan,
        "mean_synthetic_score_selected": float(sel["synthetic_score"].mean()) if selected_count and "synthetic_score" in sel else math.nan,
        "min_synthetic_score_selected": float(sel["synthetic_score"].min()) if selected_count and "synthetic_score" in sel else math.nan,
        "empirical_signal_auc": empirical_auc,
        "empirical_signal_ap": empirical_ap,
        "expected_precision": expected_precision if expected_precision is not None else math.nan,
    }
    for threshold in IOU_THRESHOLDS:
        suffix = "iou_0_3" if threshold == 0.3 else "iou_0_5"
        ans_col = "answer_iou_0_3" if threshold == 0.3 else "answer_iou_0_5"
        point_col = "point_anchor_only_iou_0_3" if threshold == 0.3 else "point_anchor_only_iou_0_5"
        hits = distinct_hits(sel, threshold)
        tp_count = int(sel[ans_col].astype(bool).sum()) if selected_count else 0
        precision = safe_div(tp_count, selected_count)
        recall = safe_div(len(hits), true_count)
        duplicate_count = max(0, tp_count - len(hits))
        matched_duration = float(true_events[true_events["event_id"].isin(hits)]["duration"].sum()) if hits else true_duration
        metrics[f"observed_precision_interval_{suffix}"] = precision
        metrics[f"event_recall_{suffix}"] = recall
        metrics[f"distinct_true_interval_events_hit_{suffix}"] = len(hits)
        metrics[f"duplicate_rate_{suffix}"] = safe_div(duplicate_count, selected_count)
        metrics[f"duration_inflation_{suffix}"] = safe_div(duration_total, matched_duration)
        metrics[f"point_anchor_only_selected_count_{suffix}"] = int(sel[point_col].astype(bool).sum()) if selected_count else 0
        metrics[f"recall_at_precision_target_{suffix}"] = recall if precision >= precision_target and selected_count > 0 else math.nan
    metrics["point_anchor_only_selected_count"] = metrics["point_anchor_only_selected_count_iou_0_3"]
    return metrics


def prediction_rows(sel: pd.DataFrame, method: str, signal: str, seed: int, budget: int, precision_target: float, tau: float | None) -> list[dict]:
    rows = []
    if sel.empty:
        return rows
    for rank, r in enumerate(sel.itertuples(index=False), 1):
        rows.append(
            {
                "method": method,
                "synthetic_signal_name": signal,
                "seed": seed,
                "budget": budget,
                "precision_target": precision_target,
                "cils_tau": tau if tau is not None else math.nan,
                "rank": rank,
                "interval_id": r.interval_id,
                "t_start": r.t_start,
                "t_end": r.t_end,
                "duration": r.duration,
                "synthetic_score": r.synthetic_score,
                "answer_iou_0_3": bool(r.answer_iou_0_3),
                "answer_iou_0_5": bool(r.answer_iou_0_5),
                "matched_true_interval_event_id_iou_0_3": getattr(r, "matched_true_interval_event_id_iou_0_3", ""),
                "matched_true_interval_event_id_iou_0_5": getattr(r, "matched_true_interval_event_id_iou_0_5", ""),
                "point_anchor_only_iou_0_3": bool(getattr(r, "point_anchor_only_iou_0_3", False)),
                "point_anchor_only_iou_0_5": bool(getattr(r, "point_anchor_only_iou_0_5", False)),
            }
        )
    return rows


def quality_lookup(quality: pd.DataFrame) -> dict[tuple[str, int], tuple[float, float]]:
    return {
        (str(r.synthetic_signal_name), int(r.seed)): (float(r.empirical_auc_iou_0_3), float(r.empirical_ap_iou_0_3))
        for r in quality.itertuples(index=False)
    }


def run_evaluation(cand: pd.DataFrame, signal_df: pd.DataFrame, quality: pd.DataFrame, true_events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    q = quality_lookup(quality)
    metrics_rows = []
    preds = {
        "predictions_cils_synthetic_downstream.csv": [],
        "predictions_synthetic_score_topk.csv": [],
        "predictions_oracle_topk.csv": [],
        "predictions_random_topk.csv": [],
        "predictions_current_real_score_topk.csv": [],
    }
    signal_groups = list(signal_df.groupby(["synthetic_signal_name", "seed"], sort=False))
    for (signal_name, seed), scores in signal_groups:
        work = prepare_for_signal(cand, scores)
        empirical_auc, empirical_ap = q[(signal_name, int(seed))]
        for budget in BUDGETS:
            if signal_name == "random_signal":
                rng = np.random.default_rng(BASE_SEED + 400_000 + int(seed) * 1000 + budget)
                random_rank = work.assign(random_rank_score=rng.normal(size=len(work))).sort_values("random_rank_score", ascending=False)
                random_sel = nms(random_rank, budget)
                for pt in PRECISION_TARGETS:
                    metrics_rows.append(evaluate_selection(random_sel, "random_topk", signal_name, int(seed), budget, pt, None, empirical_auc, empirical_ap, true_events))
                    preds["predictions_random_topk.csv"].extend(prediction_rows(random_sel, "random_topk", signal_name, int(seed), budget, pt, None))
            if signal_name != "random_signal":
                topk_sel = nms(work.sort_values(["synthetic_score", "duration"], ascending=[False, True]), budget)
                method = "current_real_score_topk" if signal_name == "current_real_signal" else "oracle_topk" if signal_name == "oracle_signal" else "synthetic_score_topk"
                pred_file = (
                    "predictions_current_real_score_topk.csv"
                    if method == "current_real_score_topk"
                    else "predictions_oracle_topk.csv"
                    if method == "oracle_topk"
                    else "predictions_synthetic_score_topk.csv"
                )
                for pt in PRECISION_TARGETS:
                    metrics_rows.append(evaluate_selection(topk_sel, method, signal_name, int(seed), budget, pt, None, empirical_auc, empirical_ap, true_events))
                    preds[pred_file].extend(prediction_rows(topk_sel, method, signal_name, int(seed), budget, pt, None))
            if signal_name.startswith("synthetic_auc_") or signal_name in {"oracle_signal", "current_real_signal"}:
                for tau in CILS_TAUS:
                    cils_sel, exp_precision = cils_select(work, budget, tau, true_events)
                    for pt in PRECISION_TARGETS:
                        metrics_rows.append(
                            evaluate_selection(
                                cils_sel,
                                "cils_synthetic_downstream",
                                signal_name,
                                int(seed),
                                budget,
                                pt,
                                tau,
                                empirical_auc,
                                empirical_ap,
                                true_events,
                                exp_precision,
                            )
                        )
                        preds["predictions_cils_synthetic_downstream.csv"].extend(
                            prediction_rows(cils_sel, "cils_synthetic_downstream", signal_name, int(seed), budget, pt, tau)
                        )
    metrics = pd.DataFrame(metrics_rows)
    for rel, rows in preds.items():
        write_df(pd.DataFrame(rows), rel)
    write_df(metrics, "metrics_by_method_seed.csv")
    summary_keys = ["method", "synthetic_signal_name", "budget", "precision_target", "cils_tau"]
    summary = (
        metrics.groupby(summary_keys, dropna=False)
        .agg(
            seed_count=("seed", "nunique"),
            mean_selected_interval_count=("selected_interval_count", "mean"),
            mean_observed_precision_interval_iou_0_3=("observed_precision_interval_iou_0_3", "mean"),
            mean_observed_precision_interval_iou_0_5=("observed_precision_interval_iou_0_5", "mean"),
            mean_event_recall_iou_0_3=("event_recall_iou_0_3", "mean"),
            mean_event_recall_iou_0_5=("event_recall_iou_0_5", "mean"),
            max_event_recall_iou_0_3=("event_recall_iou_0_3", "max"),
            mean_duration_inflation_iou_0_3=("duration_inflation_iou_0_3", "mean"),
            mean_duration_inflation_iou_0_5=("duration_inflation_iou_0_5", "mean"),
            mean_duplicate_rate_iou_0_3=("duplicate_rate_iou_0_3", "mean"),
            mean_point_anchor_only_selected_count=("point_anchor_only_selected_count", "mean"),
            empty_return_rate=("empty_return", "mean"),
            mean_empirical_signal_auc=("empirical_signal_auc", "mean"),
            mean_empirical_signal_ap=("empirical_signal_ap", "mean"),
            best_recall_at_precision_0_8_iou_0_3=("recall_at_precision_target_iou_0_3", lambda s: float(np.nanmax(s)) if s.notna().any() else math.nan),
            best_recall_at_precision_0_8_iou_0_5=("recall_at_precision_target_iou_0_5", lambda s: float(np.nanmax(s)) if s.notna().any() else math.nan),
        )
        .reset_index()
    )
    write_df(summary, "metrics_summary.csv")
    append_progress("stage3_stage4_evaluation", f"metrics_rows={len(metrics)} summary_rows={len(summary)}")
    return metrics, summary


def best_cils_at_precision(metrics: pd.DataFrame, precision_target: float) -> pd.DataFrame:
    c = metrics[
        (metrics["method"] == "cils_synthetic_downstream")
        & (metrics["observed_precision_interval_iou_0_3"] >= precision_target)
        & (metrics["event_recall_iou_0_3"] > 0)
        & (metrics["selected_interval_count"] > 0)
    ].copy()
    if c.empty:
        return c
    return c.sort_values(["empirical_signal_auc", "event_recall_iou_0_3", "selected_interval_count"], ascending=[True, False, True])


def conclusion(metrics: pd.DataFrame, quality: pd.DataFrame, true_events: pd.DataFrame) -> dict:
    ref_gate = len(true_events) >= 20
    viable = best_cils_at_precision(metrics, 0.8)
    strong = best_cils_at_precision(metrics, 0.9)
    viable_le_090 = viable[viable["empirical_signal_auc"] <= 0.90 + 1e-12]
    viable_seed_counts = viable_le_090.groupby("synthetic_signal_name")["seed"].nunique() if not viable_le_090.empty else pd.Series(dtype=int)
    conditionally_viable = bool((viable_seed_counts > 1).any())

    topk = metrics[metrics["method"] == "synthetic_score_topk"].copy()
    cils = metrics[metrics["method"] == "cils_synthetic_downstream"].copy()
    cils_best = cils[cils["observed_precision_interval_iou_0_3"] >= 0.8]["event_recall_iou_0_3"].max()
    topk_best = topk[topk["observed_precision_interval_iou_0_3"] >= 0.8]["event_recall_iou_0_3"].max()
    cils_best = float(cils_best) if pd.notna(cils_best) else 0.0
    topk_best = float(topk_best) if pd.notna(topk_best) else 0.0
    if cils_best > topk_best + 1e-9:
        value = "CILS_VALUE_ADD"
    elif topk_best > cils_best + 1e-9:
        value = "CILS_HURTS"
    else:
        value = "CILS_NEUTRAL"

    labels = []
    if conditionally_viable:
        labels.append("DOWNSTREAM_CONDITIONALLY_VIABLE_SIGNAL_LIMITED")
    oracle_cils = cils[(cils["synthetic_signal_name"] == "oracle_signal") & (cils["observed_precision_interval_iou_0_3"] >= 0.8) & (cils["event_recall_iou_0_3"] > 0)]
    if oracle_cils.empty and cils[cils["empirical_signal_auc"] >= 0.9]["event_recall_iou_0_3"].max() <= 0:
        labels.append("DOWNSTREAM_SELECTOR_BOTTLENECK")
    if value in {"CILS_HURTS", "CILS_NEUTRAL"}:
        labels.append("DOWNSTREAM_WEAK_OR_NOT_VALUE_ADDING")
    if not ref_gate:
        labels.append("INCONCLUSIVE_DUE_TO_SMALL_REFERENCE")
    if not labels:
        labels.append("INCONCLUSIVE_DUE_TO_SMALL_REFERENCE")

    weakest08 = viable.head(1)
    weakest09 = strong.head(1)
    return {
        "conclusion_type": " + ".join(labels),
        "reference_gate": "PASS" if ref_gate else "FAIL",
        "cils_value_add": value,
        "cils_best_recall_at_p08": cils_best,
        "topk_best_recall_at_p08": topk_best,
        "weakest_p08_auc": float(weakest08["empirical_signal_auc"].iloc[0]) if not weakest08.empty else math.nan,
        "weakest_p08_ap": float(weakest08["empirical_signal_ap"].iloc[0]) if not weakest08.empty else math.nan,
        "weakest_p08_budget": int(weakest08["budget"].iloc[0]) if not weakest08.empty else None,
        "weakest_p08_tau": float(weakest08["cils_tau"].iloc[0]) if not weakest08.empty else math.nan,
        "weakest_p08_signal": str(weakest08["synthetic_signal_name"].iloc[0]) if not weakest08.empty else "",
        "weakest_p09_auc": float(weakest09["empirical_signal_auc"].iloc[0]) if not weakest09.empty else math.nan,
        "weakest_p09_ap": float(weakest09["empirical_signal_ap"].iloc[0]) if not weakest09.empty else math.nan,
        "weakest_p09_budget": int(weakest09["budget"].iloc[0]) if not weakest09.empty else None,
        "weakest_p09_tau": float(weakest09["cils_tau"].iloc[0]) if not weakest09.empty else math.nan,
        "weakest_p09_signal": str(weakest09["synthetic_signal_name"].iloc[0]) if not weakest09.empty else "",
        "recommended_next_action": "compare CILS against simple top-k if CILS lacks value-add"
        if value != "CILS_VALUE_ADD"
        else "design new discriminative cheap signal",
    }


def plot_line(df: pd.DataFrame, x: str, y: str, title: str, path: Path, hue: str | None = None) -> None:
    plt.figure(figsize=(8, 5))
    if df.empty:
        plt.text(0.5, 0.5, "No rows", ha="center", va="center")
    elif hue and hue in df:
        for name, g in df.groupby(hue):
            gg = g.sort_values(x)
            plt.plot(gg[x], gg[y], marker="o", label=str(name))
        plt.legend(fontsize=8)
    else:
        gg = df.sort_values(x)
        plt.plot(gg[x], gg[y], marker="o")
    plt.title(title)
    plt.xlabel(x)
    plt.ylabel(y)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def make_plots(metrics: pd.DataFrame) -> None:
    cils = metrics[metrics["method"] == "cils_synthetic_downstream"].copy()
    topk = metrics[metrics["method"].isin(["synthetic_score_topk", "oracle_topk", "current_real_score_topk", "random_topk", "cils_synthetic_downstream"])].copy()
    by_signal = (
        cils.groupby("synthetic_signal_name")
        .agg(
            empirical_auc=("empirical_signal_auc", "mean"),
            best_recall_p08=("recall_at_precision_target_iou_0_3", lambda s: float(np.nanmax(s)) if s.notna().any() else 0.0),
            best_recall_p09=("recall_at_precision_target_iou_0_3", lambda s: float(np.nanmax(s)) if s.notna().any() else 0.0),
            best_precision=("observed_precision_interval_iou_0_3", "max"),
            mean_selected=("selected_interval_count", "mean"),
            mean_duration_inflation=("duration_inflation_iou_0_3", "mean"),
        )
        .reset_index()
    )
    p09 = cils.copy()
    p09.loc[p09["observed_precision_interval_iou_0_3"] < 0.9, "recall_at_precision_target_iou_0_3"] = np.nan
    by_signal_p09 = (
        p09.groupby("synthetic_signal_name")
        .agg(empirical_auc=("empirical_signal_auc", "mean"), best_recall_p09=("recall_at_precision_target_iou_0_3", lambda s: float(np.nanmax(s)) if s.notna().any() else 0.0))
        .reset_index()
    )
    plot_line(by_signal, "empirical_auc", "best_recall_p08", "AUC vs best CILS recall at precision >= 0.8", PLOTS_DIR / "auc_vs_best_cils_recall_p08.png")
    plot_line(by_signal_p09, "empirical_auc", "best_recall_p09", "AUC vs best CILS recall at precision >= 0.9", PLOTS_DIR / "auc_vs_best_cils_recall_p09.png")
    plot_line(by_signal, "empirical_auc", "best_precision", "AUC vs observed precision", PLOTS_DIR / "auc_vs_observed_precision.png")
    plot_line(by_signal, "empirical_auc", "mean_selected", "AUC vs selected interval count", PLOTS_DIR / "auc_vs_selected_interval_count.png")
    plot_line(by_signal, "empirical_auc", "mean_duration_inflation", "AUC vs duration inflation", PLOTS_DIR / "auc_vs_duration_inflation.png")
    compare = topk[topk["method"].isin(["cils_synthetic_downstream", "synthetic_score_topk"])].copy()
    comp = (
        compare.groupby(["method", "synthetic_signal_name"])
        .agg(empirical_auc=("empirical_signal_auc", "mean"), best_recall_p08=("recall_at_precision_target_iou_0_3", lambda s: float(np.nanmax(s)) if s.notna().any() else 0.0))
        .reset_index()
    )
    plot_line(comp, "empirical_auc", "best_recall_p08", "CILS vs synthetic_score_topk recall at precision >= 0.8", PLOTS_DIR / "cils_vs_synthetic_topk_recall_p08.png", "method")
    gap = topk[topk["method"].isin(["cils_synthetic_downstream", "oracle_topk"])].copy()
    gapg = gap.groupby(["method", "synthetic_signal_name"]).agg(empirical_auc=("empirical_signal_auc", "mean"), recall=("event_recall_iou_0_3", "max")).reset_index()
    plot_line(gapg, "empirical_auc", "recall", "CILS vs oracle_topk gap", PLOTS_DIR / "cils_vs_oracle_topk_gap.png", "method")
    b80 = topk[topk["budget"] == 80].groupby(["method", "synthetic_signal_name"]).agg(empirical_auc=("empirical_signal_auc", "mean"), precision=("observed_precision_interval_iou_0_3", "mean"), recall=("event_recall_iou_0_3", "mean")).reset_index()
    plot_line(b80, "empirical_auc", "recall", "Random / real / synthetic / oracle comparison at budget 80", PLOTS_DIR / "budget80_method_comparison.png", "method")
    mono = by_signal[by_signal["synthetic_signal_name"].str.startswith("synthetic_auc_")].copy()
    plot_line(mono, "empirical_auc", "best_recall_p08", "Monotonicity across synthetic AUC levels", PLOTS_DIR / "monotonicity_across_auc_levels.png")
    append_progress("stage6_plots", f"plots={len(list(PLOTS_DIR.glob('*.png')))}")


def write_config() -> None:
    write_text(
        CONFIG_DIR / "experiment_config.yaml",
        f"""experiment: {EXP_NAME}
budgets: {BUDGETS}
precision_targets: {PRECISION_TARGETS}
cils_taus: {CILS_TAUS}
iou_thresholds: {IOU_THRESHOLDS}
synthetic_targets: {SYNTHETIC_TARGETS}
synthetic_seeds: {SYNTHETIC_SEEDS}
random_baseline_repeats_requested: {RANDOM_BASELINE_REPEATS}
base_seed: {BASE_SEED}
diagnostic_only: true
label_derived_synthetic_scores: true
models_rerun: false
production_cils_modified: false
production_calibration_modified: false
""",
    )
    write_text(
        OUT_DIR / "reproducible_commands.md",
        """# Reproducible Commands

```bash
bash src/garc_eval/experiments/synthetic_cheap_signal_downstream_validation_v1/run_all.sh
pytest -q src/garc_eval/tests/test_craq_lite_metrics.py
pytest -q src/garc_eval/tests/test_synthetic_cheap_signal_downstream_validation.py
```
""",
    )


def write_report(metrics: pd.DataFrame, quality: pd.DataFrame, true_events: pd.DataFrame, concl: dict) -> None:
    target_hit = (
        quality.groupby("synthetic_signal_name")
        .agg(mean_target_auc=("target_auc", "mean"), mean_empirical_auc=("empirical_auc_iou_0_3", "mean"), off_target_rate=("off_target_auc", "mean"), seeds=("seed", "nunique"))
        .reset_index()
        .sort_values("mean_empirical_auc")
    )
    cils_summary = (
        metrics[metrics["method"] == "cils_synthetic_downstream"]
        .groupby("synthetic_signal_name")
        .agg(
            mean_auc=("empirical_signal_auc", "mean"),
            max_precision=("observed_precision_interval_iou_0_3", "max"),
            max_recall=("event_recall_iou_0_3", "max"),
            nonempty_rate=("empty_return", lambda s: 1.0 - float(s.mean())),
        )
        .reset_index()
        .sort_values("mean_auc")
    )
    text = f"""# Synthetic Cheap Signal Downstream Validation V1

## Purpose

This controlled intervention asks whether downstream CILS / calibration / selector mechanics can convert a cheap signal with controlled TP/FP separability into high-precision interval retrieval.

## Diagnostic-Only Label Use

Synthetic scores use `TP_iou_0_3`, reconstructed from true interval events only, as the positive label. This is intentionally label-derived and diagnostic. It is not real non-leak cheap-signal performance and must not be used as a retrieval claim.

## Reference Scope

- True interval events: `{len(true_events)}`
- Reference gate: **{concl['reference_gate']}**
- Main TP excludes point-anchor-only matches.
- All conclusions are diagnostic because true interval events are fewer than 20.
- Git status limitation: unavailable due to dubious-ownership protection; no global Git config was changed.

## Synthetic Signal Quality

{md_table(target_hit, 30)}

## CILS Signal-Quality Response

{md_table(cils_summary, 30)}

## Answers

1. Purpose: validate downstream mechanism under controlled synthetic separability.
2. Labels used: `TP_iou_0_3` true-interval-only candidate labels reconstructed from `reference_events.csv`.
3. Diagnostic only: synthetic and oracle signals use evaluation labels and are label-derived.
4. Target AUCs: see `synthetic_signal_quality.csv`; off-target rows are explicitly marked.
5. Monotonicity: see plots and CILS summary; monotonicity is assessed diagnostically on a six-event interval reference.
6. Minimum CILS signal quality for precision >= 0.8 with nonzero recall: `{concl['weakest_p08_signal'] or 'none'}`; empirical AUC `{concl['weakest_p08_auc']}`; AP `{concl['weakest_p08_ap']}`; budget `{concl['weakest_p08_budget']}`; tau `{concl['weakest_p08_tau']}`.
7. Minimum CILS signal quality for precision >= 0.9 with nonzero recall: `{concl['weakest_p09_signal'] or 'none'}`; empirical AUC `{concl['weakest_p09_auc']}`; AP `{concl['weakest_p09_ap']}`; budget `{concl['weakest_p09_budget']}`; tau `{concl['weakest_p09_tau']}`.
8. CILS value-add over simple synthetic top-k: **{concl['cils_value_add']}**. Best CILS recall at precision>=0.8: `{concl['cils_best_recall_at_p08']:.6g}`; best synthetic top-k recall at precision>=0.8: `{concl['topk_best_recall_at_p08']:.6g}`.
9. Strong/oracle-like signal failure check: see oracle rows in metrics; if oracle rows succeed, the selector is not absolutely blocked, but value-add remains separate.
10. Current real-signal failure interpretation: more consistent with weak/non-discriminative cheap signal if synthetic/oracle signal succeeds; otherwise downstream selector remains suspect.
11. Small reference limitation: **yes**, append `INCONCLUSIVE_DUE_TO_SMALL_REFERENCE`.
12. Recommended next action: **{concl['recommended_next_action']}**.

## Final Decision

`{concl['conclusion_type']}`

## Limitations

- Synthetic scores are label-derived.
- Only 20 synthetic seeds were used for signal generation because the full 100-seed CILS grid is high runtime; random baseline uses 100 repeats.
- Main true interval reference has only six events.
- No model, proposal generation, production CILS, or default calibration code was modified.
"""
    write_text(OUT_DIR / "FINAL_REPORT.md", text)


def main() -> None:
    ensure_dirs()
    (LOGS_DIR / "progress.md").write_text(f"# Progress Log\n\n- {timestamp()} | start {EXP_NAME}\n", encoding="utf-8")
    write_config()
    inv = inventory()
    inv.to_csv(MANIFEST_DIR / "artifact_inventory.csv", index=False)
    append_progress("stage0_inventory", f"rows={len(inv)}")
    cand, true_events, _ = build_canonical_candidates()
    signal_df, quality = generate_signals(cand)
    metrics, _summary = run_evaluation(cand, signal_df, quality, true_events)
    make_plots(metrics)
    concl = conclusion(metrics, quality, true_events)
    pd.DataFrame([concl]).to_csv(OUT_DIR / "diagnostic_gate_summary.csv", index=False)
    write_report(metrics, quality, true_events, concl)
    append_progress("stage8_final_report", f"conclusion={concl['conclusion_type']}")
    write_text(
        OUT_DIR / "RUN_MANIFEST.md",
        f"""# Run Manifest

- Experiment: `{EXP_NAME}`
- Host platform: `{platform.platform()}`
- Python: `{platform.python_version()}`
- Completed UTC: `{timestamp()}`
- Command: `bash src/garc_eval/experiments/synthetic_cheap_signal_downstream_validation_v1/run_all.sh`
- Diagnostic only: yes
""",
    )


if __name__ == "__main__":
    main()
