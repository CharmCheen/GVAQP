from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from garc_eval.metrics.craq_lite_metrics import Interval, interval_iou

EXP = "sq_craq_next_stage_goal_v1"
OUT = ROOT / "src/garc_eval/outputs" / EXP
SCRIPT_DIR = ROOT / "src/garc_eval/experiments" / EXP
SYN = ROOT / "src/garc_eval/outputs/synthetic_cheap_signal_downstream_validation_v1"
SMOKE = ROOT / "src/garc_eval/outputs/cils_calibration_repair_smoke_v1"
TIEBREAK = ROOT / "src/garc_eval/outputs/within_bin_tiebreak_ablation_v1"
ROOT_CAUSE = ROOT / "src/garc_eval/outputs/cils_empty_return_root_cause_audit_v1"
V2 = ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak"
MISSING_DURATION_DIR = ROOT / "src/garc_eval/outputs/reference_duration_stratified_eval_v1"
SEEDS = list(range(20))
VALUE_BUDGETS = [20, 40, 80, 160]
ENVELOPE_BUDGETS = [20, 50, 100, 200, 400]


@dataclass(frozen=True)
class EvalResult:
    selected_interval_count: int
    selected_duration_total: float
    observed_precision_interval_iou_0_3: float
    observed_precision_interval_iou_0_5: float
    interval_eval_event_recall_iou_0_3: float
    interval_eval_event_recall_iou_0_5: float
    duplicate_rate_iou_0_3: float
    duplicate_rate_iou_0_5: float
    avg_duration: float
    p95_duration: float
    background_duration_ratio_iou_0_3: float
    point_anchor_only_selected_count_iou_0_3: int
    empty_return: bool
    distinct_interval_events_hit_iou_0_3: int
    distinct_interval_events_hit_iou_0_5: int


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_df(df: pd.DataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    df.to_csv(path, index=False)


def md_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df is None or df.empty:
        return "_No rows._"
    d = df.head(max_rows).copy()
    lines = ["| " + " | ".join(map(str, d.columns)) + " |", "| " + " | ".join(["---"] * len(d.columns)) + " |"]
    for _, row in d.iterrows():
        vals = []
        for col in d.columns:
            val = row[col]
            if isinstance(val, float):
                vals.append(f"{val:.6g}")
            else:
                vals.append(str(val).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def safe_div(a: float, b: float) -> float:
    return float(a / b) if b else 0.0


def normalize(s: pd.Series) -> pd.Series:
    v = pd.to_numeric(s, errors="coerce").fillna(0.0).astype(float)
    lo, hi = float(v.min()), float(v.max())
    if hi <= lo:
        return pd.Series(np.zeros(len(v)), index=v.index)
    return (v - lo) / (hi - lo)


def file_info(paths: list[Path], roles: dict[str, str] | None = None) -> pd.DataFrame:
    rows = []
    roles = roles or {}
    for p in paths:
        cols = ""
        n = None
        exists = p.exists()
        if exists and p.is_file() and p.suffix.lower() == ".csv":
            try:
                n = max(0, sum(1 for _ in p.open("r", encoding="utf-8", errors="replace")) - 1)
                cols = ",".join(pd.read_csv(p, nrows=0).columns.tolist())
            except Exception as exc:  # noqa: BLE001
                cols = f"READ_ERROR:{exc}"
        rows.append(
            {
                "path": str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
                "exists": exists,
                "row_count_if_csv": n,
                "column_names_if_csv": cols,
                "role": roles.get(p.name, "context/input artifact"),
                "assumptions_limitations": "DIAGNOSTIC_ONLY; missing artifacts are recorded and nearest defensible equivalents are used.",
            }
        )
    return pd.DataFrame(rows)


def reference_events() -> pd.DataFrame:
    return pd.read_csv(V2 / "reference_events.csv")


def event_subsets() -> pd.DataFrame:
    ref = reference_events().copy()
    ref["duration"] = pd.to_numeric(ref["duration"], errors="coerce").fillna(ref["t_end"] - ref["t_start"])
    ref["event_subset"] = np.where(ref["duration"] <= 2.0, "point_anchor", np.where(ref["duration"] >= 5.0, "interval_eval", "ambiguous"))
    ref["keep_for_interval_eval"] = ref["event_subset"].eq("interval_eval")
    return ref


def canonical_candidates() -> pd.DataFrame:
    path = SYN / "canonical_candidates.csv"
    if path.exists():
        return pd.read_csv(path)
    lat = pd.read_csv(V2 / "interval_lattice_features_only.csv")
    if "video_id" not in lat:
        lat["video_id"] = "realcartest"
    return reconstruct_labels(lat)


def reconstruct_labels(cand: pd.DataFrame) -> pd.DataFrame:
    out = cand.copy()
    ev = event_subsets()
    interval_events = ev[ev["event_subset"].eq("interval_eval")]
    point_events = ev[ev["event_subset"].eq("point_anchor")]
    rows = []
    for r in out.itertuples(index=False):
        pred = Interval(float(r.t_start), float(r.t_end))
        best_i03 = ("", 0.0)
        best_p = ("", 0.0)
        for e in interval_events.itertuples(index=False):
            iou = interval_iou(pred, Interval(float(e.t_start), float(e.t_end), str(e.event_id)))
            if iou > best_i03[1]:
                best_i03 = (str(e.event_id), iou)
        for e in point_events.itertuples(index=False):
            iou = interval_iou(pred, Interval(float(e.t_start), float(e.t_end), str(e.event_id)))
            if iou > best_p[1]:
                best_p = (str(e.event_id), iou)
        rows.append((best_i03[0], best_i03[1], best_p[0], best_p[1]))
    m = pd.DataFrame(rows, columns=["best_interval_event_id", "best_interval_iou", "best_point_event_id", "best_point_iou"])
    out = pd.concat([out.reset_index(drop=True), m], axis=1)
    out["answer_iou_0_3"] = out["best_interval_iou"] >= 0.3
    out["answer_iou_0_5"] = out["best_interval_iou"] >= 0.5
    out["matched_true_interval_event_id_iou_0_3"] = np.where(out["answer_iou_0_3"], out["best_interval_event_id"], "")
    out["matched_true_interval_event_id_iou_0_5"] = np.where(out["answer_iou_0_5"], out["best_interval_event_id"], "")
    out["point_anchor_only_iou_0_3"] = (~out["answer_iou_0_3"]) & (out["best_point_iou"] >= 0.3)
    out["point_anchor_only_iou_0_5"] = (~out["answer_iou_0_5"]) & (out["best_point_iou"] >= 0.5)
    return out


def nms(df: pd.DataFrame, limit: int, iou_threshold: float = 0.3) -> pd.DataFrame:
    selected, spans = [], []
    for r in df.itertuples(index=False):
        if len(selected) >= limit:
            break
        pred = Interval(float(r.t_start), float(r.t_end))
        if any(interval_iou(pred, Interval(a, b)) > iou_threshold for a, b in spans):
            continue
        selected.append(r._asdict())
        spans.append((float(r.t_start), float(r.t_end)))
    return pd.DataFrame(selected)


def selected_hits(sel: pd.DataFrame, threshold: float) -> set[str]:
    col = "matched_true_interval_event_id_iou_0_3" if threshold == 0.3 else "matched_true_interval_event_id_iou_0_5"
    if sel.empty or col not in sel:
        return set()
    return {str(x) for x in sel[col].dropna().astype(str) if str(x)}


def evaluate_selection(sel: pd.DataFrame, interval_event_count: int | None = None) -> EvalResult:
    events = event_subsets()
    interval_events = events[events["event_subset"].eq("interval_eval")]
    if interval_event_count is None:
        interval_event_count = len(interval_events)
    if sel is None or sel.empty:
        return EvalResult(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, True, 0, 0)
    s = sel.copy()
    for col in ["answer_iou_0_3", "answer_iou_0_5", "point_anchor_only_iou_0_3"]:
        if col not in s:
            s[col] = False
    count = len(s)
    duration = float(s["duration"].sum())
    hits03 = selected_hits(s, 0.3)
    hits05 = selected_hits(s, 0.5)
    tp03 = int(s["answer_iou_0_3"].astype(bool).sum())
    tp05 = int(s["answer_iou_0_5"].astype(bool).sum())
    bg_duration = float(s.loc[~s["answer_iou_0_3"].astype(bool), "duration"].sum())
    return EvalResult(
        selected_interval_count=count,
        selected_duration_total=duration,
        observed_precision_interval_iou_0_3=safe_div(tp03, count),
        observed_precision_interval_iou_0_5=safe_div(tp05, count),
        interval_eval_event_recall_iou_0_3=safe_div(len(hits03), interval_event_count),
        interval_eval_event_recall_iou_0_5=safe_div(len(hits05), interval_event_count),
        duplicate_rate_iou_0_3=safe_div(max(0, tp03 - len(hits03)), count),
        duplicate_rate_iou_0_5=safe_div(max(0, tp05 - len(hits05)), count),
        avg_duration=float(s["duration"].mean()),
        p95_duration=float(s["duration"].quantile(0.95)),
        background_duration_ratio_iou_0_3=safe_div(bg_duration, duration),
        point_anchor_only_selected_count_iou_0_3=int(s["point_anchor_only_iou_0_3"].astype(bool).sum()),
        empty_return=False,
        distinct_interval_events_hit_iou_0_3=len(hits03),
        distinct_interval_events_hit_iou_0_5=len(hits05),
    )


def eval_dict(sel: pd.DataFrame) -> dict:
    return evaluate_selection(sel).__dict__


def load_signal_scores(names: set[str]) -> pd.DataFrame:
    path = SYN / "synthetic_signal_candidates.csv"
    if not path.exists():
        return pd.DataFrame()
    chunks = []
    for chunk in pd.read_csv(path, chunksize=250_000):
        keep = chunk[chunk["synthetic_signal_name"].isin(names)]
        if not keep.empty:
            chunks.append(keep)
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()


def condition_name(name: str) -> str:
    return "real_repaired_score" if name == "current_real_signal" else name


def add_score(cand: pd.DataFrame, scores: pd.DataFrame, signal_name: str, seed: int) -> pd.DataFrame:
    work = cand.copy()
    if signal_name == "current_real_signal":
        work["score"] = pd.to_numeric(work["active_score"], errors="coerce").fillna(0.0)
    else:
        ss = scores[(scores["synthetic_signal_name"].eq(signal_name)) & (scores["seed"].eq(seed))]
        work = work.merge(ss[["interval_id", "synthetic_score"]], on="interval_id", how="left")
        work["score"] = pd.to_numeric(work["synthetic_score"], errors="coerce").fillna(0.0)
    work["score_norm"] = normalize(work["score"])
    work["duration_norm"] = normalize(work["duration"])
    work["duration_penalized_score"] = work["score_norm"] - 0.20 * work["duration_norm"]
    return work


def coverage_mask(cand: pd.DataFrame, envelope: pd.DataFrame, threshold: float = 0.3) -> pd.Series:
    spans = [(float(r.t_start), float(r.t_end)) for r in envelope.itertuples(index=False)] if envelope is not None and not envelope.empty else []
    if not spans:
        return pd.Series(np.zeros(len(cand), dtype=bool), index=cand.index)
    starts = pd.to_numeric(cand["t_start"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    ends = pd.to_numeric(cand["t_end"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    span_starts = np.asarray([s[0] for s in spans], dtype=float)
    span_ends = np.asarray([s[1] for s in spans], dtype=float)
    out = np.zeros(len(cand), dtype=bool)
    chunk = 2048
    for lo in range(0, len(cand), chunk):
        hi = min(len(cand), lo + chunk)
        s = starts[lo:hi, None]
        e = ends[lo:hi, None]
        inter = np.maximum(0.0, np.minimum(e, span_ends[None, :]) - np.maximum(s, span_starts[None, :]))
        union = np.maximum(e, span_ends[None, :]) - np.minimum(s, span_starts[None, :])
        iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
        out[lo:hi] = (iou > threshold).any(axis=1)
    return pd.Series(out, index=cand.index)


def envelope_recall(envelope: pd.DataFrame) -> dict:
    return eval_dict(envelope)


def duration_strata_from_reference() -> pd.DataFrame:
    ev = event_subsets().copy()
    ev["duration_stratum"] = ev["event_subset"]
    return ev[["event_id", "video_id", "t_start", "t_end", "duration", "duration_stratum", "keep_for_interval_eval"]]


def script_stub(path: Path, title: str, body: str) -> None:
    write_text(
        path,
        f"""#!/usr/bin/env python3
\"\"\"{title}

Dry-run scaffold generated by `{EXP}`. This script does not run models unless
future users explicitly replace dry-run behavior.
\"\"\"

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description={title!r})
    parser.add_argument("--input", type=Path, default=None, help="Input manifest or feature table.")
    parser.add_argument("--output", type=Path, default=None, help="Output path or directory.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Default: print planned actions only.")
    args = parser.parse_args()
    print("DRY_RUN_ONLY")
    print({body!r})
    print(f"input={{args.input}} output={{args.output}}")


if __name__ == "__main__":
    main()
""",
    )
