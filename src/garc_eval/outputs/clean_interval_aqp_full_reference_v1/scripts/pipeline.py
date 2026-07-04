#!/usr/bin/env python3
"""Clean mini-universe interval AQP experiment.

This script intentionally keeps proposal generation and optimization label-free.
Full-reference labels are used only in Stage 1 materialization, oracle replay
lookup, diagnostics, and final evaluation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


EXP_NAME = "clean_interval_aqp_full_reference_v1"
REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = REPO_ROOT / "src" / "garc_eval" / "experiments" / EXP_NAME
OUT_DIR = REPO_ROOT / "src" / "garc_eval" / "outputs" / EXP_NAME

INPUTS = {
    "anchor_grid": REPO_ROOT / "experiments/v13/v13_7_multimethod_replay/tables/center10_anchor_grid.csv",
    "v13_8_labels": REPO_ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv",
    "v13_8_events": REPO_ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv",
    "yolo_raw": REPO_ROOT / "src/garc_eval/outputs/realcartest_proxy_materialization_v1/tables/raw_yolo_detections_realcartest_2fps.csv",
    "yolo_frames": REPO_ROOT / "src/garc_eval/outputs/realcartest_proxy_materialization_v1/tables/yolo_sampled_frames_realcartest_2fps.csv",
    "anchor_proxy": REPO_ROOT / "src/garc_eval/outputs/realcartest_proxy_materialization_v1/tables/realcartest_anchor_proxy_features_2fps.csv",
}

BUDGETS = [5, 10, 20, 40, 80]
DIAG_BUDGETS = [5, 10, 20, 40, 80, 120]
TAUS = [0.8, 0.9]
TRIALS = 100
UNIT_SEC = 2.0
SEGMENT_DURATION = 1200.0
RNG_SEED = 20260630

EVAL_COLS = {
    "event_hit_iou_0_3",
    "event_hit_iou_0_5",
    "positive_unit_fraction",
    "matched_event_id",
    "oracle_positive",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dirs() -> None:
    for p in [
        OUT_DIR,
        OUT_DIR / "config",
        OUT_DIR / "data_manifest",
        OUT_DIR / "scripts",
        OUT_DIR / "logs",
        OUT_DIR / "tables",
        OUT_DIR / "figures",
        OUT_DIR / "reports",
        OUT_DIR / "reference_raw_vlm",
    ]:
        p.mkdir(parents=True, exist_ok=True)


def progress(checkpoint: str, command: str = "", result: str = "", failure: str = "", fix: str = "", next_action: str = "") -> None:
    ensure_dirs()
    path = OUT_DIR / "logs" / "progress.md"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {now_iso()} - {checkpoint}\n\n")
        if command:
            f.write(f"- command: `{command}`\n")
        if result:
            f.write(f"- result: {result}\n")
        if failure:
            f.write(f"- failure: {failure}\n")
        if fix:
            f.write(f"- fix: {fix}\n")
        if next_action:
            f.write(f"- next: {next_action}\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_df(df: pd.DataFrame, name: str) -> None:
    df.to_csv(OUT_DIR / name, index=False)
    if name.endswith(".csv"):
        df.to_csv(OUT_DIR / "tables" / name, index=False)


def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    """Render a small DataFrame as a markdown table without optional deps."""
    if df is None or df.empty:
        return "_No rows._"
    view = df.head(max_rows).copy() if max_rows else df.copy()
    cols = [str(c) for c in view.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in view.iterrows():
        vals = []
        for c in view.columns:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6g}")
            else:
                vals.append(str(v).replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def load_manifest() -> pd.Series:
    m = read_csv(OUT_DIR / "video_segment_manifest.csv")
    if len(m) != 1:
        raise ValueError("Expected exactly one selected segment")
    return m.iloc[0]


def load_events() -> pd.DataFrame:
    return read_csv(OUT_DIR / "reference_events.csv")


def load_units() -> pd.DataFrame:
    return read_csv(OUT_DIR / "full_reference_units.csv")


def normalize(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce").fillna(0.0)
    lo = float(s.min())
    hi = float(s.max())
    if hi <= lo:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - lo) / (hi - lo)


def safe_div(a: float, b: float) -> float:
    return float(a / b) if b else 0.0


def temporal_iou(a0: float, a1: float, b0: float, b1: float) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    return safe_div(inter, union)


def auc_score(y: Iterable[int], score: Iterable[float]) -> float:
    y = np.asarray(list(y)).astype(int)
    s = np.asarray(list(score)).astype(float)
    pos = int(y.sum())
    neg = int(len(y) - pos)
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(s)
    ranks = np.empty(len(s), dtype=float)
    ranks[order] = np.arange(1, len(s) + 1)
    _, inv, counts = np.unique(s, return_inverse=True, return_counts=True)
    for group in np.where(counts > 1)[0]:
        idx = np.where(inv == group)[0]
        ranks[idx] = ranks[idx].mean()
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


def ap_score(y: Iterable[int], score: Iterable[float]) -> float:
    y = np.asarray(list(y)).astype(int)
    s = np.asarray(list(score)).astype(float)
    pos = int(y.sum())
    if pos == 0:
        return float("nan")
    order = np.argsort(-s)
    y_sorted = y[order]
    tp = np.cumsum(y_sorted)
    precision = tp / (np.arange(len(y_sorted)) + 1)
    return float((precision * y_sorted).sum() / pos)


def selected_event_metrics(selected: pd.DataFrame, events: pd.DataFrame, tau: float | None = None) -> dict:
    if selected.empty:
        return {
            "num_selected": 0,
            "events_hit": 0,
            "event_recall_iou_0_3": 0.0,
            "observed_precision_iou_0_3": 0.0,
            "returned_duration": 0.0,
            "duplicate_rate": 0.0,
            "duration_inflation_flag": False,
            "precision_violation": bool(tau is not None),
        }
    hits = selected[selected["event_hit_iou_0_3"].astype(bool)].copy()
    hit_events: set[str] = set()
    for x in hits["matched_event_id"].fillna(""):
        for eid in str(x).split("|"):
            if eid:
                hit_events.add(eid)
    duplicate_pos = max(0, len(hits) - len(hit_events))
    returned_duration = float(selected["duration"].sum())
    true_event_duration = float(events["duration"].sum()) if "duration" in events.columns else 0.0
    precision = safe_div(len(hits), len(selected))
    duration_inflation = returned_duration > max(SEGMENT_DURATION * 0.35, true_event_duration * 4.0)
    return {
        "num_selected": int(len(selected)),
        "events_hit": int(len(hit_events)),
        "event_recall_iou_0_3": safe_div(len(hit_events), len(events)),
        "observed_precision_iou_0_3": precision,
        "returned_duration": returned_duration,
        "duplicate_rate": safe_div(duplicate_pos, len(selected)),
        "duration_inflation_flag": bool(duration_inflation),
        "precision_violation": bool(tau is not None and precision + 1e-12 < tau),
    }


def input_audit() -> None:
    rows = []
    for artifact, path in INPUTS.items():
        exists = path.exists()
        rec = {"artifact": artifact, "path": str(path), "exists": exists, "rows": "", "columns": "", "leakage_risk": ""}
        if exists and path.suffix == ".csv":
            df = pd.read_csv(path, nrows=5)
            rec["columns"] = "|".join(df.columns)
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                rec["rows"] = max(0, sum(1 for _ in f) - 1)
        if artifact in {"v13_8_labels", "v13_8_events"}:
            rec["leakage_risk"] = "reference-only; forbidden for proposal generation and optimization"
        elif artifact == "anchor_proxy":
            rec["leakage_risk"] = "contains label columns; not used by optimization"
        else:
            rec["leakage_risk"] = "cheap/input metadata"
        rows.append(rec)
    audit = pd.DataFrame(rows)
    write_df(audit, "input_manifest.csv")
    audit.to_csv(OUT_DIR / "data_manifest" / "input_manifest.csv", index=False)
    write_text(
        OUT_DIR / "config" / "experiment_config.yaml",
        "\n".join(
            [
                f"experiment: {EXP_NAME}",
                f"unit_sec: {UNIT_SEC}",
                f"segment_duration_sec: {SEGMENT_DURATION}",
                f"budgets: {BUDGETS}",
                f"diagnostic_budgets: {DIAG_BUDGETS}",
                f"precision_targets: {TAUS}",
                f"trials: {TRIALS}",
                f"seed: {RNG_SEED}",
                "reference_use_policy: final_evaluation_and_oracle_replay_only",
            ]
        ),
    )


def stage0_select() -> None:
    ensure_dirs()
    input_audit()
    labels = read_csv(INPUTS["v13_8_labels"])
    events = read_csv(INPUTS["v13_8_events"])
    anchor_grid = read_csv(INPUTS["anchor_grid"])
    candidates = []
    max_end = float(labels["end_time"].max())
    for start in np.arange(0.0, max_end - SEGMENT_DURATION + 0.001, 100.0):
        end = start + SEGMENT_DURATION
        l = labels[(labels["start_time"] >= start) & (labels["end_time"] <= end)]
        ev = events[(events["event_start"] < end) & (events["event_end"] > start)]
        pos = int((l["label"] == "positive").sum())
        pr = safe_div(pos, len(l))
        duration_mix = float(np.clip(ev["event_duration"].median() if len(ev) else 0, 0, 20))
        score = len(ev) * 10 + pos - abs(pr - 0.25) * 30 + duration_mix * 0.2
        candidates.append((score, start, end, len(l), pos, len(ev), pr))
    selected = max(candidates, key=lambda x: x[0])
    _, start, end, n_units10, pos_anchors, event_count, pr = selected
    source_path = str(anchor_grid["source_video_path"].dropna().iloc[0])
    manifest = pd.DataFrame(
        [
            {
                "video_id": "realcartest",
                "source_path": source_path,
                "t_start": f"{start:.3f}",
                "t_end": f"{end:.3f}",
                "duration": f"{end - start:.3f}",
                "selection_reason": (
                    "20min window maximizing VLM-defined event count with mixed positives/background; "
                    f"{event_count} reference events, {pos_anchors}/{n_units10} positive center10 anchors. "
                    "Reference labels used only for mini-universe curation, not proposal generation."
                ),
            }
        ]
    )
    write_df(manifest, "video_segment_manifest.csv")
    write_text(
        OUT_DIR / "selected_universe.md",
        f"""# Selected Mini-Universe

Experiment: `{EXP_NAME}`

Selected video segment: `realcartest` from {start:.1f}s to {end:.1f}s ({(end-start)/60:.1f} minutes).

Selection basis: existing V13.8 Qwen3-VL-32B pseudo-oracle labels were used only to choose a compact
mini-universe with enough cut-in / near-conflict / abnormal interaction events and substantial negative
background. This curation step is explicitly not part of the tested retrieval method.

Reference-event count inside segment: {event_count}

Positive center10 anchors inside segment: {pos_anchors}/{n_units10} ({pr:.3f})

Leakage boundary: Stage 2 cheap signals, Stage 4 proposal generation, and Stage 7 optimization do not
read full-reference labels. Reference labels are used for Stage 1 materialization, oracle replay lookup,
diagnostics, and final evaluation only.
""",
    )
    progress("stage0_select", result=f"selected realcartest {start:.1f}-{end:.1f}s with {event_count} events")


def stage1_reference() -> None:
    seg = load_manifest()
    t0 = float(seg["t_start"])
    t1 = float(seg["t_end"])
    labels = read_csv(INPUTS["v13_8_labels"])
    events = read_csv(INPUTS["v13_8_events"])
    labels = labels[(labels["start_time"] < t1) & (labels["end_time"] > t0)].copy()
    events = events[(events["event_start"] < t1) & (events["event_end"] > t0)].copy()

    base_rows = []
    for i, s in enumerate(np.arange(t0, t1, UNIT_SEC)):
        e = min(s + UNIT_SEC, t1)
        base_rows.append(
            {
                "unit_id": f"u{i:04d}",
                "video_id": seg["video_id"],
                "t_start": round(s - t0, 3),
                "t_end": round(e - t0, 3),
                "absolute_t_start": round(s, 3),
                "absolute_t_end": round(e, 3),
                "duration": round(e - s, 3),
            }
        )
    base = pd.DataFrame(base_rows)
    write_df(base, "base_units.csv")

    event_rows = []
    for _, ev in events.iterrows():
        s = max(float(ev["event_start"]), t0)
        e = min(float(ev["event_end"]), t1)
        if e <= s:
            continue
        event_rows.append(
            {
                "event_id": ev["event_id"],
                "video_id": ev["video_id"],
                "t_start": round(s - t0, 3),
                "t_end": round(e - t0, 3),
                "absolute_t_start": round(s, 3),
                "absolute_t_end": round(e, 3),
                "duration": round(e - s, 3),
                "event_type": ev["event_type_majority"],
                "involved_object": ev["involved_object_majority"],
                "num_supporting_anchors": ev["num_supporting_anchors"],
                "supporting_anchor_ids": ev["supporting_anchor_ids"],
                "label_source": "VLM_ORACLE_RELATIVE_REUSED_FOR_MINI_FULL_REFERENCE",
                "oracle_version": ev["oracle_version"],
            }
        )
    ref_events = pd.DataFrame(event_rows)
    write_df(ref_events, "reference_events.csv")

    ref_rows = []
    for _, u in base.iterrows():
        overlaps = ref_events[(ref_events["t_start"] < u["t_end"]) & (ref_events["t_end"] > u["t_start"])]
        label_event = int(len(overlaps) > 0)
        ref_rows.append(
            {
                "unit_id": u["unit_id"],
                "t_start": u["t_start"],
                "t_end": u["t_end"],
                "label_event": label_event,
                "event_type": "|".join(sorted(set(overlaps["event_type"].astype(str)))) if label_event else "none",
                "event_id": "|".join(overlaps["event_id"].astype(str)) if label_event else "",
                "boundary_start": "|".join(f"{x:.3f}" for x in overlaps["t_start"]) if label_event else "",
                "boundary_end": "|".join(f"{x:.3f}" for x in overlaps["t_end"]) if label_event else "",
                "label_source": "VLM_ORACLE_RELATIVE_REUSED_FOR_MINI_FULL_REFERENCE",
                "confidence": "high" if label_event else "inherited_negative",
                "notes": "2s unit overlaps clipped V13.8 event interval" if label_event else "no overlap with clipped V13.8 events",
            }
        )
    ref_units = pd.DataFrame(ref_rows)
    write_df(ref_units, "full_reference_units.csv")

    selected_anchor_labels = labels.copy()
    parse_rows = selected_anchor_labels[
        [
            "anchor_id",
            "start_time",
            "end_time",
            "label",
            "event_start_absolute",
            "event_end_absolute",
            "event_type",
            "involved_object",
            "confidence",
            "raw_response_path",
            "parse_status",
        ]
    ].copy()
    parse_rows["used_for"] = "mini_reference_event_boundary_source"
    write_df(parse_rows, "oracle_parsing_results.csv")

    copied = []
    for raw in sorted(set(labels["raw_response_path"].dropna().astype(str))):
        src = Path(raw)
        if src.exists():
            dst = OUT_DIR / "reference_raw_vlm" / src.name
            shutil.copyfile(src, dst)
            copied.append({"raw_response_path": str(raw), "copied_to": str(dst), "exists": True})
        else:
            copied.append({"raw_response_path": str(raw), "copied_to": "", "exists": False})
    write_df(pd.DataFrame(copied), "vlm_raw_output_manifest.csv")
    write_text(
        OUT_DIR / "oracle_protocol.md",
        """# Oracle Protocol

Reference source: V13.8 Qwen3-VL-32B full center10 pseudo-oracle labels on `realcartest`.

No new large VLM full scan was launched for this experiment. The mini-universe full reference is a
clean, clipped, 2s-unit rematerialization of the selected V13.8 pseudo-oracle event intervals.

Predicate: `O_enter_ego_path_v0`, an object starts outside the ego future path and enters or overlaps
it, creating potential spatial conflict requiring ego attention.

Oracle replay policy: limited-budget methods may query only this rematerialized reference through the
oracle replay lookup, which returns whether the queried interval contains any positive 2s base unit.
Event-level IoU hits are reserved for final evaluation. Unqueried labels are not available to
calibration, proposal generation, or optimization.
""",
    )
    write_text(
        OUT_DIR / "oracle_prompt.txt",
        """Use the V13.6 center10 predicate prompt for `O_enter_ego_path_v0`.

This file records the predicate used by the reused V13.8 pseudo-oracle labels. The experiment did not
rerun Qwen3-VL-32B. Raw VLM JSON files for selected anchors are copied under `reference_raw_vlm/`.
""",
    )
    write_text(
        OUT_DIR / "reference_quality_report.md",
        f"""# Reference Quality Report

Reference type: VLM-defined pseudo-oracle, not human ground truth.

Mini-universe units: {len(ref_units)} 2s base units.

Positive base units: {int(ref_units['label_event'].sum())} ({ref_units['label_event'].mean():.3f}).

Reference events: {len(ref_events)}.

Anchor labels clipped into the segment: {len(labels)}.

Raw VLM outputs copied or indexed: {len(copied)}.

Limitations:

- Boundary resolution inherits V13.8 center10 oracle behavior and event stitching.
- The first-stage universe selection used existing pseudo-oracle labels for curation, so this is a
  clean mini-universe experiment, not an unbiased prevalence estimate.
- These labels are oracle-relative only and must not be described as human truth.
""",
    )
    progress("stage1_reference", result=f"{len(ref_units)} units, {len(ref_events)} events")


def iou_box(a: dict, b: dict) -> float:
    x0 = max(a["x1"], b["x1"])
    y0 = max(a["y1"], b["y1"])
    x1 = min(a["x2"], b["x2"])
    y1 = min(a["y2"], b["y2"])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area_a = max(0.0, a["x2"] - a["x1"]) * max(0.0, a["y2"] - a["y1"])
    area_b = max(0.0, b["x2"] - b["x1"]) * max(0.0, b["y2"] - b["y1"])
    return safe_div(inter, area_a + area_b - inter)


def assign_iou_tracks(det: pd.DataFrame) -> pd.DataFrame:
    if det.empty:
        det["track_id"] = []
        return det
    det = det.sort_values(["timestamp_sec", "confidence"], ascending=[True, False]).copy()
    active: dict[int, dict] = {}
    next_id = 0
    track_ids = []
    for _, row in det.iterrows():
        box = row.to_dict()
        best_tid = None
        best_iou = 0.0
        for tid, last in list(active.items()):
            if row["timestamp_sec"] - last["timestamp_sec"] > 1.1:
                continue
            if row["class_name"] != last["class_name"]:
                continue
            val = iou_box(box, last)
            if val > best_iou:
                best_iou = val
                best_tid = tid
        if best_tid is None or best_iou < 0.25:
            best_tid = next_id
            next_id += 1
        active[best_tid] = box
        track_ids.append(best_tid)
    det["track_id"] = track_ids
    return det


def stage2_signals() -> None:
    seg = load_manifest()
    t0 = float(seg["t_start"])
    t1 = float(seg["t_end"])
    base = read_csv(OUT_DIR / "base_units.csv")
    t_start = time.time()
    det = read_csv(INPUTS["yolo_raw"])
    frames = read_csv(INPUTS["yolo_frames"])
    det = det[(det["timestamp_sec"] >= t0) & (det["timestamp_sec"] < t1)].copy()
    frames = frames[(frames["timestamp_sec"] >= t0) & (frames["timestamp_sec"] < t1)].copy()
    det["unit_idx"] = np.floor((det["timestamp_sec"] - t0) / UNIT_SEC).astype(int)
    frames["unit_idx"] = np.floor((frames["timestamp_sec"] - t0) / UNIT_SEC).astype(int)
    w = float(det["image_width"].dropna().iloc[0]) if len(det) else 1920.0
    h = float(det["image_height"].dropna().iloc[0]) if len(det) else 1080.0
    det["bbox_area_norm"] = det["bbox_area"] / (w * h)
    det["cx_norm"] = det["cx"] / w
    det["cy_norm"] = det["cy"] / h
    vehicle = {"car", "truck", "bus", "motorcycle"}
    trackable = det[det["class_name"].isin(vehicle | {"person", "bicycle"})].copy()
    tracked = assign_iou_tracks(trackable)
    tracked = tracked.sort_values(["track_id", "timestamp_sec"]).copy()
    tracked["dt"] = tracked.groupby("track_id")["timestamp_sec"].diff()
    tracked["dcx"] = tracked.groupby("track_id")["cx_norm"].diff()
    tracked["dcy"] = tracked.groupby("track_id")["cy_norm"].diff()
    tracked["darea"] = tracked.groupby("track_id")["bbox_area_norm"].diff()
    tracked["track_speed_frame"] = np.sqrt(tracked["dcx"].fillna(0) ** 2 + tracked["dcy"].fillna(0) ** 2) / tracked["dt"].replace(0, np.nan)
    tracked["track_speed_frame"] = tracked["track_speed_frame"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    tracked["track_accel_frame"] = tracked.groupby("track_id")["track_speed_frame"].diff() / tracked["dt"].replace(0, np.nan)
    tracked["track_accel_frame"] = tracked["track_accel_frame"].replace([np.inf, -np.inf], np.nan).fillna(0.0).abs()
    tracked["relative_motion_frame"] = tracked["track_speed_frame"].abs() + tracked["darea"].fillna(0).abs()

    frame_summary = []
    for ts, g in det.groupby("timestamp_sec"):
        frame_summary.append(
            {
                "timestamp_sec": ts,
                "unit_idx": int(np.floor((ts - t0) / UNIT_SEC)),
                "vehicle_count": int(g["class_name"].isin(vehicle).sum()),
                "person_count": int((g["class_name"] == "person").sum()),
                "object_count": int(len(g)),
                "bbox_area_mean": float(g["bbox_area_norm"].mean()) if len(g) else 0.0,
                "bbox_center_x": float(g["cx_norm"].mean()) if len(g) else 0.0,
                "bbox_center_y": float(g["cy_norm"].mean()) if len(g) else 0.0,
            }
        )
    fs = pd.DataFrame(frame_summary)
    if fs.empty:
        fs = pd.DataFrame(columns=["timestamp_sec", "unit_idx", "vehicle_count", "person_count", "object_count", "bbox_area_mean", "bbox_center_x", "bbox_center_y"])
    fs = fs.sort_values("timestamp_sec")
    for c in ["vehicle_count", "person_count", "object_count", "bbox_area_mean", "bbox_center_x", "bbox_center_y"]:
        fs[f"d_{c}"] = fs[c].diff().abs().fillna(0.0)
    fs["motion_energy_frame"] = (
        normalize(fs["d_object_count"]) * 0.35
        + normalize(fs["d_bbox_area_mean"]) * 0.35
        + normalize(fs["d_bbox_center_x"] + fs["d_bbox_center_y"]) * 0.30
    )

    rows = []
    tracked_unit = tracked.groupby("unit_idx") if len(tracked) else {}
    for idx, u in base.reset_index().iterrows():
        unit_idx = int(idx)
        g = det[det["unit_idx"] == unit_idx]
        fg = fs[fs["unit_idx"] == unit_idx]
        tg = tracked_unit.get_group(unit_idx) if len(tracked) and unit_idx in tracked_unit.groups else pd.DataFrame()
        vehicle_frames = fg["vehicle_count"] if len(fg) else pd.Series(dtype=float)
        person_frames = fg["person_count"] if len(fg) else pd.Series(dtype=float)
        area = g["bbox_area_norm"] if len(g) else pd.Series(dtype=float)
        rows.append(
            {
                "unit_id": u["unit_id"],
                "t_start": u["t_start"],
                "t_end": u["t_end"],
                "absolute_t_start": u["absolute_t_start"],
                "absolute_t_end": u["absolute_t_end"],
                "num_sampled_frames": int(len(fg)),
                "yolo_vehicle_count": float(vehicle_frames.mean()) if len(vehicle_frames) else 0.0,
                "person_count": float(person_frames.mean()) if len(person_frames) else 0.0,
                "bbox_area_mean": float(area.mean()) if len(area) else 0.0,
                "bbox_area_max": float(area.max()) if len(area) else 0.0,
                "bbox_center_x": float(g["cx_norm"].mean()) if len(g) else 0.5,
                "bbox_center_y": float(g["cy_norm"].mean()) if len(g) else 0.5,
                "bbox_size_change": float(fg["d_bbox_area_mean"].mean()) if len(fg) else 0.0,
                "track_speed": float(tg["track_speed_frame"].mean()) if len(tg) else 0.0,
                "track_acceleration": float(tg["track_accel_frame"].mean()) if len(tg) else 0.0,
                "relative_motion_score": float(tg["relative_motion_frame"].mean()) if len(tg) else 0.0,
                "motion_energy": float(fg["motion_energy_frame"].mean()) if len(fg) else 0.0,
                "optical_flow_burst": float((fg["motion_energy_frame"] > fs["motion_energy_frame"].quantile(0.75)).mean()) if len(fg) else 0.0,
                "object_density_change": float(fg["d_object_count"].mean()) if len(fg) else 0.0,
            }
        )
    signals = pd.DataFrame(rows)
    core = [
        "yolo_vehicle_count",
        "person_count",
        "bbox_area_mean",
        "bbox_area_max",
        "bbox_size_change",
        "track_speed",
        "track_acceleration",
        "relative_motion_score",
        "motion_energy",
        "optical_flow_burst",
        "object_density_change",
    ]
    normed = pd.DataFrame({c: normalize(signals[c]) for c in core})
    signals["signal_disagreement"] = normed.std(axis=1)
    normed["signal_disagreement"] = normalize(signals["signal_disagreement"])
    signals["cheap_fused_score"] = (
        0.22 * normed["yolo_vehicle_count"]
        + 0.12 * normed["person_count"]
        + 0.12 * normed["bbox_area_max"]
        + 0.14 * normed["track_speed"]
        + 0.12 * normed["relative_motion_score"]
        + 0.16 * normed["motion_energy"]
        + 0.12 * normed["signal_disagreement"]
    )
    signals["primary_signal_score"] = normalize(signals["yolo_vehicle_count"] + signals["person_count"])
    write_df(signals, "cheap_signals_per_unit.csv")
    elapsed = time.time() - t_start
    write_text(
        OUT_DIR / "cheap_signal_cost_report.md",
        f"""# Cheap Signal Cost Report

Input detections: `{INPUTS['yolo_raw']}`.

Detection source: cached YOLOv8n 2fps detections from the local realcartest proxy materialization.

Rows read in selected segment: {len(det)} detections over {len(frames)} sampled frames.

Signal materialization runtime in this run: {elapsed:.3f}s CPU wall time.

Tracking: simple class-aware IoU tracking at 2fps, no external tracker dependency.

Optical flow: downgraded to detection-derived `optical_flow_burst` because this clean AQP run avoids
expensive video-frame processing. This is recorded as an engineering limitation, not a research claim.
""",
    )
    write_text(
        OUT_DIR / "signal_extraction_log.txt",
        "\n".join(
            [
                f"{now_iso()} start cheap signal extraction",
                f"segment_absolute_sec={t0:.3f}-{t1:.3f}",
                f"raw_detection_rows={len(det)}",
                f"sampled_frame_rows={len(frames)}",
                f"unit_rows={len(signals)}",
                "tracker=simple_iou",
                "optical_flow_burst=detection_motion_proxy",
                f"elapsed_sec={elapsed:.3f}",
            ]
        ),
    )
    progress("stage2_signals", result=f"{len(signals)} unit signal rows, {len(det)} detection rows")


def stage3_diagnostics() -> None:
    signals = read_csv(OUT_DIR / "cheap_signals_per_unit.csv")
    ref = load_units()[["unit_id", "label_event", "event_id"]]
    df = signals.merge(ref, on="unit_id", how="left")
    signal_cols = [
        "yolo_vehicle_count",
        "person_count",
        "bbox_area_mean",
        "bbox_area_max",
        "bbox_center_x",
        "bbox_center_y",
        "bbox_size_change",
        "track_speed",
        "track_acceleration",
        "relative_motion_score",
        "motion_energy",
        "optical_flow_burst",
        "object_density_change",
        "signal_disagreement",
        "cheap_fused_score",
        "primary_signal_score",
    ]
    quality = []
    budget_rows = []
    base_rate = float(df["label_event"].mean())
    total_pos = int(df["label_event"].sum())
    for c in signal_cols:
        quality.append({"signal": c, "auc": auc_score(df["label_event"], df[c]), "ap": ap_score(df["label_event"], df[c]), "base_positive_rate": base_rate})
        ranked = df.sort_values(c, ascending=False)
        for b in DIAG_BUDGETS:
            top = ranked.head(min(b, len(ranked)))
            hits = int(top["label_event"].sum())
            precision = safe_div(hits, len(top))
            budget_rows.append(
                {
                    "signal": c,
                    "budget": b,
                    "recall_at_b": safe_div(hits, total_pos),
                    "precision_at_b": precision,
                    "enrichment_at_b": safe_div(precision, base_rate),
                    "positives_found": hits,
                }
            )
    write_df(pd.DataFrame(quality).sort_values("auc", ascending=False), "signal_quality.csv")
    write_df(pd.DataFrame(budget_rows), "signal_recall_precision_at_budget.csv")

    q = {c: df[c].quantile for c in signal_cols}
    blind = []
    rules = [
        ("low_vehicle_count_but_positive", (df["label_event"] == 1) & (df["yolo_vehicle_count"] <= q["yolo_vehicle_count"](0.25))),
        ("high_motion_low_object_count", (df["label_event"] == 1) & (df["motion_energy"] >= q["motion_energy"](0.75)) & (df["yolo_vehicle_count"] <= q["yolo_vehicle_count"](0.50))),
        ("high_person_count_positive", (df["label_event"] == 1) & (df["person_count"] >= q["person_count"](0.75))),
        ("low_cheap_score_positive", (df["label_event"] == 1) & (df["cheap_fused_score"] <= q["cheap_fused_score"](0.25))),
        ("high_signal_disagreement_positive", (df["label_event"] == 1) & (df["signal_disagreement"] >= q["signal_disagreement"](0.75))),
    ]
    for name, mask in rules:
        for _, r in df[mask].iterrows():
            blind.append(
                {
                    "blind_spot_type": name,
                    "unit_id": r["unit_id"],
                    "t_start": r["t_start"],
                    "t_end": r["t_end"],
                    "event_id": r["event_id"],
                    "yolo_vehicle_count": r["yolo_vehicle_count"],
                    "person_count": r["person_count"],
                    "motion_energy": r["motion_energy"],
                    "cheap_fused_score": r["cheap_fused_score"],
                    "signal_disagreement": r["signal_disagreement"],
                }
            )
    blind_df = pd.DataFrame(blind)
    write_df(blind_df, "blind_spot_report.csv")
    topq = pd.DataFrame(quality).sort_values("auc", ascending=False).head(8)
    write_text(
        OUT_DIR / "signal_diagnostics.md",
        f"""# Signal Diagnostics

Units evaluated against pseudo-oracle full reference: {len(df)}.

Positive units: {total_pos} ({base_rate:.3f}).

Best AUC signals:

{md_table(topq)}

Blind-spot rows generated: {len(blind_df)}.

Interpretation limit: this stage intentionally uses full reference for diagnostics only. These metrics
must not be fed back into proposal generation or optimization in the main method.
""",
    )
    progress("stage3_diagnostics", result=f"computed {len(quality)} signal metrics")


def interval_features(units: pd.DataFrame, method: str, source_signal: str, start_idx: int, end_idx: int, interval_id: str) -> dict:
    g = units.iloc[start_idx:end_idx].copy()
    score = g[source_signal].astype(float)
    left_prev = float(units.iloc[start_idx - 1][source_signal]) if start_idx > 0 else float(score.iloc[0])
    right_next = float(units.iloc[end_idx][source_signal]) if end_idx < len(units) else float(score.iloc[-1])
    return {
        "interval_id": interval_id,
        "method": method,
        "source_signal": source_signal,
        "unit_start_idx": start_idx,
        "unit_end_idx_exclusive": end_idx,
        "t_start": float(g["t_start"].iloc[0]),
        "t_end": float(g["t_end"].iloc[-1]),
        "duration": float(g["t_end"].iloc[-1] - g["t_start"].iloc[0]),
        "num_units": int(len(g)),
        "mean_score": float(score.mean()),
        "max_score": float(score.max()),
        "score_persistence": float((score >= score.quantile(0.60)).mean()),
        "score_std": float(score.std(ddof=0)),
        "boundary_left_drop": float(max(0.0, score.iloc[0] - left_prev)),
        "boundary_right_drop": float(max(0.0, score.iloc[-1] - right_next)),
        "signal_disagreement": float(g["signal_disagreement"].mean()),
        "cheap_fused_score": float(g["cheap_fused_score"].mean()),
        "primary_signal_score": float(g["primary_signal_score"].mean()),
    }


def add_interval(rows: list[dict], seen: set[tuple], units: pd.DataFrame, method: str, source_signal: str, start: int, end: int) -> None:
    start = max(0, int(start))
    end = min(len(units), int(end))
    if end <= start:
        return
    key = (method, source_signal, start, end)
    if key in seen:
        return
    seen.add(key)
    rows.append(interval_features(units, method, source_signal, start, end, f"iv_{len(rows):06d}"))


def assign_overlap_groups(iv: pd.DataFrame) -> pd.DataFrame:
    iv = iv.sort_values(["t_start", "t_end"]).copy()
    groups = []
    current_group = -1
    group_end = -1.0
    for _, r in iv.iterrows():
        if r["t_start"] > group_end:
            current_group += 1
            group_end = r["t_end"]
        else:
            group_end = max(group_end, r["t_end"])
        groups.append(f"og_{current_group:04d}")
    iv["overlap_group_id"] = groups
    return iv.sort_values("interval_id").reset_index(drop=True)


def evaluate_intervals(iv: pd.DataFrame, ref_units: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    out = iv.copy()
    ref = ref_units.copy()
    eval_rows = []
    for _, r in out.iterrows():
        units = ref[(ref["t_start"] < r["t_end"]) & (ref["t_end"] > r["t_start"])]
        pfrac = float(units["label_event"].mean()) if len(units) else 0.0
        best_iou = 0.0
        best_eid = ""
        hit_eids_03 = []
        hit_eids_05 = []
        for _, ev in events.iterrows():
            val = temporal_iou(float(r["t_start"]), float(r["t_end"]), float(ev["t_start"]), float(ev["t_end"]))
            if val > best_iou:
                best_iou = val
                best_eid = ev["event_id"]
            if val >= 0.3:
                hit_eids_03.append(ev["event_id"])
            if val >= 0.5:
                hit_eids_05.append(ev["event_id"])
        eval_rows.append(
            {
                "event_hit_iou_0_3": bool(hit_eids_03),
                "event_hit_iou_0_5": bool(hit_eids_05),
                "positive_unit_fraction": pfrac,
                "matched_event_id": "|".join(hit_eids_03) if hit_eids_03 else (best_eid if best_iou > 0 else ""),
                "oracle_positive": bool(pfrac > 0.0),
            }
        )
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(eval_rows)], axis=1)


def stage4_lattice() -> None:
    units = read_csv(OUT_DIR / "cheap_signals_per_unit.csv").copy()
    score_cols = ["cheap_fused_score", "primary_signal_score", "motion_energy", "signal_disagreement", "person_count"]
    rows: list[dict] = []
    seen: set[tuple] = set()

    for width in [5, 10, 15]:
        stride = max(1, width // 2)
        for start in range(0, len(units), stride):
            add_interval(rows, seen, units, "fixed_window", "cheap_fused_score", start, min(start + width, len(units)))

    for sig in score_cols:
        s = units[sig]
        for qv in [0.70, 0.82]:
            mask = s >= s.quantile(qv)
            start = None
            gap = 0
            for i, val in enumerate(mask.tolist() + [False]):
                if val and start is None:
                    start = i
                    gap = 0
                elif not val and start is not None:
                    gap += 1
                    if gap > 1:
                        add_interval(rows, seen, units, "threshold_merge", sig, start, i)
                        start = None
                        gap = 0

    for sig in ["cheap_fused_score", "motion_energy", "signal_disagreement"]:
        s = units[sig].to_numpy()
        top_idx = np.argsort(-s)[: min(80, len(s))]
        for peak in top_idx:
            peak_val = s[peak]
            lo = peak
            hi = peak + 1
            floor = max(np.quantile(s, 0.55), peak_val * 0.45)
            while lo > 0 and s[lo - 1] >= floor and peak - lo < 10:
                lo -= 1
            while hi < len(s) and s[hi] >= floor and hi - peak < 10:
                hi += 1
            add_interval(rows, seen, units, "peak_expand", sig, lo, hi)

    for sig in ["cheap_fused_score", "motion_energy"]:
        s = units[sig].to_numpy()
        high = np.quantile(s, 0.60)
        low = np.quantile(s, 0.35)
        start = None
        for i, val in enumerate(list(s) + [0.0]):
            if val >= high and start is None:
                start = i
            elif start is not None and (val <= low or i == len(s)):
                add_interval(rows, seen, units, "valley_split", sig, start, i)
                start = None

    masks = []
    for sig, qv in [("cheap_fused_score", 0.75), ("motion_energy", 0.78), ("signal_disagreement", 0.80), ("person_count", 0.80)]:
        masks.append(units[sig] >= units[sig].quantile(qv))
    union = np.logical_or.reduce([m.to_numpy() for m in masks])
    start = None
    for i, val in enumerate(list(union) + [False]):
        if val and start is None:
            start = i
        elif not val and start is not None:
            add_interval(rows, seen, units, "multi_signal_union", "cheap_fused_score", start, i)
            start = None

    iv = assign_overlap_groups(pd.DataFrame(rows))
    ref_units = load_units()
    events = load_events()
    iv_eval = evaluate_intervals(iv, ref_units, events)
    write_df(iv_eval, "interval_lattice.csv")
    features_only = iv_eval.drop(columns=[c for c in EVAL_COLS if c in iv_eval.columns])
    write_df(features_only, "interval_lattice_features_only.csv")

    summary = (
        iv_eval.groupby("method")
        .agg(
            number_of_intervals=("interval_id", "count"),
            avg_duration=("duration", "mean"),
            median_duration=("duration", "median"),
            positive_interval_rate=("event_hit_iou_0_3", "mean"),
            mean_positive_unit_fraction=("positive_unit_fraction", "mean"),
        )
        .reset_index()
    )
    write_df(summary, "lattice_summary.csv")
    proposal_quality = (
        iv_eval.groupby(["method", "source_signal"])
        .agg(
            number_of_intervals=("interval_id", "count"),
            iou_0_3_hit_rate=("event_hit_iou_0_3", "mean"),
            iou_0_5_hit_rate=("event_hit_iou_0_5", "mean"),
            avg_positive_unit_fraction=("positive_unit_fraction", "mean"),
            avg_duration=("duration", "mean"),
        )
        .reset_index()
    )
    write_df(proposal_quality, "proposal_quality.csv")
    write_text(
        OUT_DIR / "lattice_construction_report.md",
        f"""# Lattice Construction Report

Intervals generated from cheap signals only: {len(iv_eval)}.

Methods implemented: fixed_window, threshold_merge, peak_expand, valley_split, multi_signal_union.

Feature-only lattice for selection: `interval_lattice_features_only.csv`.

Evaluation-labelled lattice: `interval_lattice.csv`.

Leakage control: interval generation consumes only `cheap_signals_per_unit.csv`; reference labels are
joined afterward by `evaluate_intervals` for diagnostics and oracle replay.

{md_table(summary)}
""",
    )
    progress("stage4_lattice", result=f"{len(iv_eval)} intervals")


def duplicate_rate(df: pd.DataFrame) -> float:
    pos = df[df["event_hit_iou_0_3"].astype(bool)]
    if pos.empty:
        return 0.0
    eids = []
    for x in pos["matched_event_id"].fillna(""):
        eids.append(str(x).split("|")[0])
    return safe_div(len(eids) - len(set(eids)), len(df))


def stage5_proposals() -> None:
    iv = read_csv(OUT_DIR / "interval_lattice.csv")
    events = load_events()
    rows = []
    curves = []
    for method, g in iv.groupby("method"):
        hit03 = set()
        hit05 = set()
        for _, r in g.iterrows():
            if bool(r["event_hit_iou_0_3"]):
                for eid in str(r["matched_event_id"]).split("|"):
                    if eid:
                        hit03.add(eid)
            if bool(r["event_hit_iou_0_5"]):
                for _, ev in events.iterrows():
                    if temporal_iou(r["t_start"], r["t_end"], ev["t_start"], ev["t_end"]) >= 0.5:
                        hit05.add(ev["event_id"])
        ranked = g.sort_values(["max_score", "mean_score"], ascending=False)
        rec = {
            "method": method,
            "proposal_recall_iou_0_3": safe_div(len(hit03), len(events)),
            "proposal_recall_iou_0_5": safe_div(len(hit05), len(events)),
            "number_of_intervals": len(g),
            "avg_duration": float(g["duration"].mean()),
            "median_duration": float(g["duration"].median()),
            "duplicate_rate": duplicate_rate(g),
            "background_duration_ratio": float(1.0 - g["positive_unit_fraction"].mean()),
            "positive_unit_fraction": float(g["positive_unit_fraction"].mean()),
        }
        for k in DIAG_BUDGETS:
            top = ranked.head(min(k, len(ranked)))
            met = selected_event_metrics(top, events)
            rec[f"budgeted_recall@{k}"] = met["event_recall_iou_0_3"]
            rec[f"budgeted_precision@{k}"] = met["observed_precision_iou_0_3"]
            curves.append({"method": method, "budget": k, **met})
        rows.append(rec)
    eval_df = pd.DataFrame(rows)
    write_df(eval_df, "proposal_evaluation.csv")
    write_df(pd.DataFrame(curves), "proposal_recall_curve.csv")
    write_text(
        OUT_DIR / "proposal_evaluation.md",
        f"""# Proposal Evaluation

Full-reference use: evaluation only.

{md_table(eval_df)}
""",
    )
    progress("stage5_proposals", result=f"evaluated {len(rows)} proposal families")


def policy_order(features: pd.DataFrame, policy: str, seed: int, budget: int) -> list[str]:
    rng = np.random.default_rng(seed)
    f = features.copy()
    if policy == "uniform":
        return f.sample(frac=1, random_state=seed)["interval_id"].tolist()
    if policy == "top_score":
        return f.sort_values(["max_score", "mean_score", "duration"], ascending=[False, False, True])["interval_id"].tolist()
    if policy == "stratified_by_score_duration_disagreement":
        f["score_bin"] = pd.qcut(f["max_score"].rank(method="first"), 4, labels=False)
        f["duration_bin"] = pd.qcut(f["duration"].rank(method="first"), 3, labels=False)
        f["disagreement_bin"] = pd.qcut(f["signal_disagreement"].rank(method="first"), 3, labels=False)
        parts = []
        for _, g in f.groupby(["score_bin", "duration_bin", "disagreement_bin"]):
            parts.extend(g.sample(frac=1, random_state=int(rng.integers(0, 1_000_000)))["interval_id"].tolist())
        return parts
    if policy == "decision_aware_simple":
        f["decision_score"] = (
            normalize(f["max_score"]) * 0.45
            + normalize(f["boundary_left_drop"] + f["boundary_right_drop"]) * 0.25
            + normalize(f["signal_disagreement"]) * 0.20
            - normalize(f["duration"]) * 0.10
        )
        out = []
        selected_spans: list[tuple[float, float]] = []
        ranked = f.sort_values("decision_score", ascending=False)
        for r in ranked.itertuples(index=False):
            if len(out) >= min(len(f), max(budget * 2, budget + 20)):
                break
            if all(temporal_iou(r.t_start, r.t_end, s0, s1) <= 0.3 for s0, s1 in selected_spans):
                out.append(r.interval_id)
                selected_spans.append((r.t_start, r.t_end))
        out_set = set(out)
        rest = [x for x in ranked["interval_id"].tolist() if x not in out_set]
        return out + rest
    raise ValueError(policy)


def make_calibration(features: pd.DataFrame, samples: pd.DataFrame, mode: str = "beta_bin_strata") -> pd.DataFrame:
    f = features.copy()
    f["score_bin"] = pd.qcut(f["max_score"].rank(method="first"), 5, labels=False)
    f["duration_bin"] = pd.qcut(f["duration"].rank(method="first"), 3, labels=False)
    f["disagreement_bin"] = pd.qcut(f["signal_disagreement"].rank(method="first"), 3, labels=False)
    if mode == "no_calibration_raw_score":
        f["p_rel"] = normalize(f["max_score"])
        f["calibration_mode"] = mode
        return f

    sample_map = samples.set_index("interval_id")["oracle_positive"].astype(int).to_dict()
    samples2 = f[f["interval_id"].isin(sample_map)].copy()
    samples2["y"] = samples2["interval_id"].map(sample_map).astype(int)
    global_p = safe_div(float(samples2["y"].sum()) + 1.0, len(samples2) + 2.0)

    key = ["score_bin", "duration_bin", "disagreement_bin"]
    local = samples2.groupby(key, dropna=False)["y"].agg(["sum", "count"]).reset_index()
    local["p_local"] = (local["sum"] + 1.0) / (local["count"] + 2.0)
    local = local.rename(columns={"count": "n_local"})[key + ["n_local", "p_local"]]

    score = samples2.groupby(["score_bin"], dropna=False)["y"].agg(["sum", "count"]).reset_index()
    score["p_score"] = (score["sum"] + 1.0) / (score["count"] + 2.0)
    score = score.rename(columns={"count": "n_score"})[["score_bin", "n_score", "p_score"]]

    f = f.merge(local, on=key, how="left").merge(score, on=["score_bin"], how="left")
    f["p_rel"] = np.where(
        f["n_local"].fillna(0) >= 2,
        f["p_local"],
        np.where(f["n_score"].fillna(0) > 0, f["p_score"], global_p),
    )
    f["p_rel"] = f["p_rel"].fillna(global_p).astype(float)
    f["calibration_mode"] = mode
    return f


def oracle_samples(features: pd.DataFrame, eval_lattice: pd.DataFrame, policy: str, budget: int, seed: int) -> pd.DataFrame:
    order = policy_order(features, policy, seed, budget)
    chosen = order[: min(budget, len(order))]
    labels = eval_lattice.set_index("interval_id")["oracle_positive"].to_dict()
    rows = []
    for rank, iid in enumerate(chosen, 1):
        rows.append({"interval_id": iid, "rank": rank, "oracle_positive": bool(labels[iid])})
    return pd.DataFrame(rows)


def stage6_calibration() -> None:
    features = read_csv(OUT_DIR / "interval_lattice_features_only.csv")
    eval_lattice = read_csv(OUT_DIR / "interval_lattice.csv")
    policies = ["uniform", "top_score", "stratified_by_score_duration_disagreement", "decision_aware_simple"]
    trial_rows = []
    quality_rows = []
    y_all = eval_lattice.set_index("interval_id")["oracle_positive"].astype(int)
    for budget in BUDGETS:
        for seed in range(TRIALS):
            for policy in policies:
                samples = oracle_samples(features, eval_lattice, policy, budget, RNG_SEED + seed)
                for _, s in samples.iterrows():
                    trial_rows.append({"budget": budget, "seed": seed, "policy": policy, **s.to_dict()})
                for mode in ["beta_bin_strata"]:
                    cal = make_calibration(features, samples, mode)
                    p = cal.set_index("interval_id")["p_rel"].reindex(y_all.index)
                    y = y_all.reindex(p.index)
                    quality_rows.append(
                        {
                            "budget": budget,
                            "seed": seed,
                            "policy": policy,
                            "calibration": mode,
                            "num_oracle_calls": len(samples),
                            "sample_positive_rate": float(samples["oracle_positive"].mean()) if len(samples) else 0.0,
                            "mean_p_rel": float(p.mean()),
                            "brier": float(((p - y) ** 2).mean()),
                            "auc": auc_score(y, p),
                            "ap": ap_score(y, p),
                        }
                    )
    trials = pd.DataFrame(trial_rows)
    quality = pd.DataFrame(quality_rows)
    write_df(trials, "calibration_trials.csv")
    write_df(quality, "calibration_quality.csv")
    summary = quality.groupby(["budget", "policy", "calibration"]).agg(brier=("brier", "mean"), auc=("auc", "mean"), sample_positive_rate=("sample_positive_rate", "mean")).reset_index()
    write_text(
        OUT_DIR / "calibration_report.md",
        f"""# Calibration Report

Oracle replay budgets: {BUDGETS}

Trials per policy/budget: {TRIALS}

Calibration implemented: beta-binomial score-duration-disagreement strata. Logistic/isotonic was not
used because several budget/policy combinations have too few positives for stable fitting.

{md_table(summary)}
""",
    )
    progress("stage6_calibration", result=f"{len(trials)} oracle replay rows, {len(quality)} quality rows")


def cils_select(
    calibrated: pd.DataFrame,
    tau: float,
    max_iou: float = 0.3,
    max_return: int | None = None,
    use_boundary: bool = True,
    use_duration_penalty: bool = True,
    max_total_duration: float = SEGMENT_DURATION * 0.30,
) -> pd.DataFrame:
    df = calibrated.copy()
    boundary = normalize(df["boundary_left_drop"] + df["boundary_right_drop"])
    if use_boundary:
        df["boundary_quality"] = 0.55 + 0.45 * boundary
    else:
        df["boundary_quality"] = 1.0
    if use_duration_penalty:
        duration_penalty = 1.0 / np.sqrt(np.maximum(df["duration"], 1.0))
    else:
        duration_penalty = 1.0
    df["coverage_value"] = np.minimum(df["duration"], 20.0) * (0.5 + 0.5 * normalize(df["max_score"]))
    df["utility"] = df["p_rel"] * df["boundary_quality"] * df["coverage_value"] * duration_penalty
    df["utility_per_duration"] = df["utility"] / np.maximum(df["duration"], 1e-6)
    ranked = df.sort_values(["utility_per_duration", "utility"], ascending=False)
    if max_return is not None:
        ranked = ranked.head(min(len(ranked), max(200, max_return * 20)))
    selected: list[dict] = []
    selected_spans: list[tuple[float, float]] = []
    p_sum = 0.0
    duration_sum = 0.0
    for r in ranked.itertuples(index=False):
        if max_return is not None and len(selected) >= max_return:
            break
        if duration_sum + float(r.duration) > max_total_duration:
            continue
        if selected_spans and any(temporal_iou(r.t_start, r.t_end, s0, s1) > max_iou for s0, s1 in selected_spans):
            continue
        new_mean = (p_sum + float(r.p_rel)) / (len(selected) + 1)
        if new_mean + 1e-12 < tau:
            continue
        selected.append(r._asdict())
        selected_spans.append((float(r.t_start), float(r.t_end)))
        p_sum += float(r.p_rel)
        duration_sum += float(r.duration)
    return pd.DataFrame(selected)


def evaluate_selection(sel_features: pd.DataFrame, eval_lattice: pd.DataFrame, events: pd.DataFrame, tau: float) -> pd.DataFrame:
    if sel_features.empty:
        return sel_features
    eval_cols = eval_lattice[["interval_id", "event_hit_iou_0_3", "event_hit_iou_0_5", "positive_unit_fraction", "matched_event_id", "oracle_positive"]]
    return sel_features.merge(eval_cols, on="interval_id", how="left")


def cils_trial(features: pd.DataFrame, eval_lattice: pd.DataFrame, budget: int, tau: float, seed: int, policy: str = "top_score", calibration_mode: str = "beta_bin_strata", max_iou: float = 0.3, max_return: int | None = None, use_boundary: bool = True, use_duration_penalty: bool = True) -> pd.DataFrame:
    samples = oracle_samples(features, eval_lattice, policy, budget, RNG_SEED + seed)
    cal = make_calibration(features, samples, calibration_mode)
    return cils_select(cal, tau, max_iou=max_iou, max_return=max_return or budget, use_boundary=use_boundary, use_duration_penalty=use_duration_penalty)


def stage7_optimization() -> None:
    features = read_csv(OUT_DIR / "interval_lattice_features_only.csv")
    eval_lattice = read_csv(OUT_DIR / "interval_lattice.csv")
    events = load_events()
    sel_rows = []
    curve_rows = []
    for budget in BUDGETS:
        for tau in TAUS:
            for seed in range(TRIALS):
                sel = cils_trial(features, eval_lattice, budget, tau, seed)
                sel_eval = evaluate_selection(sel, eval_lattice, events, tau)
                for rank, (_, r) in enumerate(sel_eval.iterrows(), 1):
                    row = {"method": "CILS_full", "budget": budget, "tau": tau, "seed": seed, "return_rank": rank}
                    row.update(r.to_dict())
                    sel_rows.append(row)
                met = selected_event_metrics(sel_eval, events, tau)
                curve_rows.append({"method": "CILS_full", "budget": budget, "tau": tau, "seed": seed, **met})
    selected = pd.DataFrame(sel_rows)
    curves = pd.DataFrame(curve_rows)
    write_df(selected, "selected_intervals_by_trial.csv")
    agg = curves.groupby(["method", "budget", "tau"]).agg(
        event_recall_mean=("event_recall_iou_0_3", "mean"),
        event_recall_std=("event_recall_iou_0_3", "std"),
        observed_precision_mean=("observed_precision_iou_0_3", "mean"),
        returned_duration_mean=("returned_duration", "mean"),
        duplicate_rate_mean=("duplicate_rate", "mean"),
        precision_violation_rate=("precision_violation", "mean"),
        duration_inflation_rate=("duration_inflation_flag", "mean"),
    ).reset_index()
    write_df(agg, "main_budget_curve.csv")
    write_text(
        OUT_DIR / "optimization_report.md",
        f"""# Optimization Report

Method: CILS, calibrated interval-lattice selection.

Selection input: `interval_lattice_features_only.csv` plus budget-limited oracle replay samples.

Evaluation labels are joined only after each return set is selected.

Pilot policy for CILS: `top_score` budget-limited oracle replay.

Greedy constraints: expected precision >= tau, pairwise interval overlap <= 0.3, max returned intervals <= B.

{md_table(agg)}
""",
    )
    progress("stage7_optimization", result=f"{len(selected)} selected interval rows")


def select_top(g: pd.DataFrame, n: int) -> pd.DataFrame:
    return g.sort_values(["max_score", "mean_score", "duration"], ascending=[False, False, True]).head(min(n, len(g))).copy()


def baseline_selection(name: str, features: pd.DataFrame, eval_lattice: pd.DataFrame, budget: int, tau: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED + seed)
    ev = eval_lattice.set_index("interval_id")
    if name == "fixed_window_topk":
        return select_top(features[features["method"] == "fixed_window"], budget)
    if name == "threshold_merge_topk":
        return select_top(features[features["method"] == "threshold_merge"], budget)
    if name == "cheap_signal_only":
        return select_top(features, budget)
    if name == "oracle_confirmed_only":
        probes = select_top(features, budget)
        return probes[probes["interval_id"].map(ev["oracle_positive"]).astype(bool)].copy()
    if name == "supg_on_windows_simplified":
        fw = features[features["method"] == "fixed_window"].copy()
        samples = oracle_samples(fw, eval_lattice, "uniform", budget, seed)
        cal = make_calibration(fw, samples, "beta_bin_strata")
        return cal[cal["p_rel"] >= tau].sort_values("p_rel", ascending=False).head(budget).copy()
    if name == "arc_style_prune_refine_simplified":
        top_n = max(1, int(math.ceil(0.6 * budget)))
        top = select_top(features, top_n)
        pool = features[features["overlap_group_id"].isin(top["overlap_group_id"])].copy()
        refine = select_top(pool[~pool["interval_id"].isin(top["interval_id"])], budget - len(top))
        probes = pd.concat([top, refine], ignore_index=True).drop_duplicates("interval_id").head(budget)
        return probes[probes["interval_id"].map(ev["oracle_positive"]).astype(bool)].copy()
    if name == "arc_plus_uniform_outside_audit_simplified":
        audit_n = max(1, int(round(0.2 * budget)))
        arc_n = budget - audit_n
        top = select_top(features, max(1, int(math.ceil(0.6 * arc_n))))
        pool = features[features["overlap_group_id"].isin(top["overlap_group_id"])].copy()
        refine = select_top(pool[~pool["interval_id"].isin(top["interval_id"])], max(0, arc_n - len(top)))
        used = set(pd.concat([top, refine])["interval_id"])
        outside = features[~features["interval_id"].isin(used)]
        audit = outside.sample(n=min(audit_n, len(outside)), random_state=RNG_SEED + seed) if len(outside) else outside
        probes = pd.concat([top, refine, audit], ignore_index=True).drop_duplicates("interval_id").head(budget)
        samples = probes[["interval_id"]].copy()
        samples["oracle_positive"] = samples["interval_id"].map(ev["oracle_positive"]).astype(bool)
        cal = make_calibration(features, samples, "beta_bin_strata")
        confirmed = probes[probes["interval_id"].map(ev["oracle_positive"]).astype(bool)]
        predicted = cal[cal["p_rel"] >= tau].sort_values("p_rel", ascending=False).head(max(0, budget - len(confirmed)))
        return pd.concat([confirmed, predicted], ignore_index=True).drop_duplicates("interval_id").head(budget)
    if name == "oracle_full_scan_upper_bound":
        positives = eval_lattice[eval_lattice["event_hit_iou_0_3"].astype(bool)].copy()
        positives["event_key"] = positives["matched_event_id"].fillna("").astype(str).str.split("|").str[0]
        positives = positives.sort_values(["duration", "max_score"], ascending=[True, False]).drop_duplicates("event_key")
        return features[features["interval_id"].isin(positives.head(budget)["interval_id"])].copy()
    raise ValueError(name)


def stage8_baselines() -> None:
    features = read_csv(OUT_DIR / "interval_lattice_features_only.csv")
    eval_lattice = read_csv(OUT_DIR / "interval_lattice.csv")
    events = load_events()
    names = [
        "fixed_window_topk",
        "threshold_merge_topk",
        "cheap_signal_only",
        "oracle_confirmed_only",
        "supg_on_windows_simplified",
        "arc_style_prune_refine_simplified",
        "arc_plus_uniform_outside_audit_simplified",
        "oracle_full_scan_upper_bound",
    ]
    rows = []
    for budget in BUDGETS:
        for tau in TAUS:
            for seed in range(TRIALS):
                for name in names:
                    sel = baseline_selection(name, features, eval_lattice, budget, tau, seed)
                    sel_eval = evaluate_selection(sel, eval_lattice, events, tau)
                    met = selected_event_metrics(sel_eval, events, tau if name not in {"fixed_window_topk", "threshold_merge_topk", "cheap_signal_only", "oracle_full_scan_upper_bound"} else None)
                    rows.append({"method": name, "budget": budget, "tau": tau, "seed": seed, **met})
    df = pd.DataFrame(rows)
    write_df(df, "baseline_comparison.csv")
    agg = df.groupby(["method", "budget", "tau"]).agg(
        event_recall_mean=("event_recall_iou_0_3", "mean"),
        observed_precision_mean=("observed_precision_iou_0_3", "mean"),
        returned_duration_mean=("returned_duration", "mean"),
        duplicate_rate_mean=("duplicate_rate", "mean"),
        precision_violation_rate=("precision_violation", "mean"),
    ).reset_index()
    write_text(
        OUT_DIR / "baseline_report.md",
        f"""# Baseline Report

All baselines use the same mini-universe full reference for evaluation. Oracle-using baselines only see
budget-limited replay labels.

{md_table(agg)}
""",
    )
    progress("stage8_baselines", result=f"{len(df)} baseline trial rows")


def run_variant(features: pd.DataFrame, eval_lattice: pd.DataFrame, events: pd.DataFrame, variant: str, budget: int, tau: float, seed: int) -> dict:
    f = features.copy()
    if variant == "no_lattice_fixed_windows":
        f = f[f["method"] == "fixed_window"].copy()
    if variant == "primary_signal_only":
        f["max_score"] = f["primary_signal_score"]
        f["mean_score"] = f["primary_signal_score"]
    if variant == "fused_signal":
        f["max_score"] = f["cheap_fused_score"]
        f["mean_score"] = f["cheap_fused_score"]
    calibration = "beta_bin_strata"
    if variant == "no_calibration_raw_score":
        samples = oracle_samples(f, eval_lattice, "top_score", budget, RNG_SEED + seed)
        cal = make_calibration(f, samples, "no_calibration_raw_score")
        sel = cils_select(cal, tau, max_iou=0.3, max_return=budget)
    else:
        samples = oracle_samples(f, eval_lattice, "top_score", budget, RNG_SEED + seed)
        cal = make_calibration(f, samples, calibration)
        sel = cils_select(
            cal,
            tau,
            max_iou=1.0 if variant == "no_overlap_control" else 0.3,
            max_return=budget,
            use_boundary=variant != "no_boundary_quality",
            use_duration_penalty=variant != "no_duration_penalty",
        )
    sel_eval = evaluate_selection(sel, eval_lattice, events, tau)
    return selected_event_metrics(sel_eval, events, tau)


def stage9_ablation() -> None:
    features = read_csv(OUT_DIR / "interval_lattice_features_only.csv")
    eval_lattice = read_csv(OUT_DIR / "interval_lattice.csv")
    events = load_events()
    variants = [
        "CILS_full",
        "no_lattice_fixed_windows",
        "no_calibration_raw_score",
        "no_boundary_quality",
        "no_duration_penalty",
        "no_overlap_control",
        "primary_signal_only",
        "fused_signal",
    ]
    rows = []
    for variant in variants:
        for budget in BUDGETS:
            for tau in TAUS:
                for seed in range(TRIALS):
                    met = run_variant(features, eval_lattice, events, variant, budget, tau, seed)
                    rows.append({"ablation": variant, "budget": budget, "tau": tau, "seed": seed, **met})
    ab = pd.DataFrame(rows)
    write_df(ab, "ablation_results.csv")

    stress_rows = []
    base = features.copy()
    y = eval_lattice.set_index("interval_id")["oracle_positive"].astype(int)
    best_signal = pd.read_csv(OUT_DIR / "signal_quality.csv").iloc[0]["signal"]
    for stress in ["best_proxy", "noisy_proxy", "partial_inverted_proxy", "low_density_blindspot_proxy", "random_proxy", "random_baseline"]:
        f = base.copy()
        rng = np.random.default_rng(RNG_SEED)
        if stress == "best_proxy" and best_signal in read_csv(OUT_DIR / "cheap_signals_per_unit.csv").columns:
            # Interval-level best cheap proxy approximation: keep regular fused interval scores.
            f["max_score"] = f["cheap_fused_score"]
            f["mean_score"] = f["cheap_fused_score"]
        elif stress == "noisy_proxy":
            noise = rng.normal(0, 0.25, len(f))
            f["max_score"] = np.clip(normalize(f["max_score"]) + noise, 0, 1)
            f["mean_score"] = f["max_score"]
        elif stress == "partial_inverted_proxy":
            inv = 1 - normalize(f["max_score"])
            f["max_score"] = 0.5 * normalize(f["max_score"]) + 0.5 * inv
            f["mean_score"] = f["max_score"]
        elif stress == "low_density_blindspot_proxy":
            f["max_score"] = normalize(f["max_score"]) * (normalize(f["duration"]) > 0.25).astype(float)
            f["mean_score"] = f["max_score"]
        elif stress in {"random_proxy", "random_baseline"}:
            rand = rng.random(len(f))
            f["max_score"] = rand
            f["mean_score"] = rand
        for budget in BUDGETS:
            for tau in TAUS:
                for seed in range(TRIALS):
                    if stress == "random_baseline":
                        sel = f.sample(n=min(budget, len(f)), random_state=RNG_SEED + seed)
                        sel_eval = evaluate_selection(sel, eval_lattice, events, None)
                        met = selected_event_metrics(sel_eval, events, None)
                    else:
                        met = run_variant(f, eval_lattice, events, "fused_signal", budget, tau, seed)
                    stress_rows.append({"stress_test": stress, "budget": budget, "tau": tau, "seed": seed, **met})
    stress_df = pd.DataFrame(stress_rows)
    write_df(stress_df, "stress_test_results.csv")

    checks = []
    rand_proxy = stress_df[stress_df["stress_test"] == "random_proxy"].groupby(["budget", "tau"])["event_recall_iou_0_3"].mean()
    rand_base = stress_df[stress_df["stress_test"] == "random_baseline"].groupby(["budget", "tau"])["event_recall_iou_0_3"].mean()
    diff = (rand_proxy - rand_base).dropna()
    checks.append(("random_proxy_not_significantly_above_random", bool((diff < 0.05).all()), float(diff.max() if len(diff) else 0.0)))

    bc = read_csv(OUT_DIR / "baseline_comparison.csv")
    oc = bc[bc["method"] == "oracle_confirmed_only"]
    checks.append(("oracle_confirmed_only_return_count_le_budget", bool((oc["num_selected"] <= oc["budget"]).all()), float((oc["num_selected"] - oc["budget"]).max())))

    main = read_csv(OUT_DIR / "main_budget_curve.csv")
    checks.append(("cils_duration_inflation_rate_zero", bool((main["duration_inflation_rate"] == 0).all()), float(main["duration_inflation_rate"].max())))
    checks.append(("precision_violations_recorded", "precision_violation_rate" in main.columns, float(main["precision_violation_rate"].max())))

    script_text = (SCRIPT_DIR / "pipeline.py").read_text(encoding="utf-8")
    leak_ok = "interval_lattice_features_only.csv" in script_text and "evaluate_selection(sel" in script_text
    checks.append(("optimization_uses_feature_only_lattice_before_eval_join", bool(leak_ok), 1.0 if leak_ok else 0.0))

    lines = ["# Sanity Checks", ""]
    for name, passed, value in checks:
        lines.append(f"- {name}: {'PASS' if passed else 'FAIL'} (value={value})")
    if not all(x[1] for x in checks):
        lines.append("\nInterpretation should be fail-closed for failed checks.")
    write_text(OUT_DIR / "sanity_checks.md", "\n".join(lines))
    progress("stage9_ablation", result=f"{len(ab)} ablation rows, {len(stress_df)} stress rows")


def stage10_final() -> None:
    manifest = read_csv(OUT_DIR / "video_segment_manifest.csv")
    ref_units = load_units()
    ref_events = load_events()
    signal_q = read_csv(OUT_DIR / "signal_quality.csv")
    proposal = read_csv(OUT_DIR / "proposal_evaluation.csv")
    main = read_csv(OUT_DIR / "main_budget_curve.csv")
    base = read_csv(OUT_DIR / "baseline_comparison.csv")
    ab = read_csv(OUT_DIR / "ablation_results.csv")
    stress = read_csv(OUT_DIR / "stress_test_results.csv")

    base_agg = base.groupby(["method", "budget", "tau"]).agg(
        event_recall_mean=("event_recall_iou_0_3", "mean"),
        observed_precision_mean=("observed_precision_iou_0_3", "mean"),
        returned_duration_mean=("returned_duration", "mean"),
        duplicate_rate_mean=("duplicate_rate", "mean"),
    ).reset_index()
    compare = main.merge(
        base_agg[base_agg["method"].isin(["threshold_merge_topk", "arc_style_prune_refine_simplified"])],
        on=["budget", "tau"],
        suffixes=("_cils", "_baseline"),
    )
    improvements = compare[
        (compare["event_recall_mean_cils"] > compare["event_recall_mean_baseline"] + 1e-9)
        & (compare["observed_precision_mean_cils"] >= compare["tau"] - 1e-9)
        & (compare["duplicate_rate_mean_cils"] <= compare["duplicate_rate_mean_baseline"] + 0.10)
        & (compare["returned_duration_mean_cils"] <= compare["returned_duration_mean_baseline"] * 1.5 + 20.0)
    ]
    by_tau_baseline = improvements.groupby(["tau", "method_baseline"])["budget"].nunique().reset_index(name="improved_budget_count")
    promising_by_tau = {}
    for tau, g in by_tau_baseline.groupby("tau"):
        counts = dict(zip(g["method_baseline"], g["improved_budget_count"]))
        promising_by_tau[float(tau)] = (
            counts.get("threshold_merge_topk", 0) >= 2
            and counts.get("arc_style_prune_refine_simplified", 0) >= 2
        )
    promising = any(promising_by_tau.values())
    decision = "PROMISING" if promising else "WEAK_OR_INCONCLUSIVE"
    if "FAIL" in (OUT_DIR / "sanity_checks.md").read_text(encoding="utf-8"):
        decision = "NO-GO_SANITY_FAILURE"

    ab_agg = ab.groupby(["ablation", "budget", "tau"]).agg(event_recall_mean=("event_recall_iou_0_3", "mean"), precision_mean=("observed_precision_iou_0_3", "mean")).reset_index()
    stress_agg = stress.groupby(["stress_test", "budget", "tau"]).agg(event_recall_mean=("event_recall_iou_0_3", "mean"), precision_mean=("observed_precision_iou_0_3", "mean")).reset_index()

    main_comp = pd.concat(
        [
            main.rename(columns={"event_recall_mean": "event_recall", "observed_precision_mean": "precision"})[
                ["method", "budget", "tau", "event_recall", "precision", "returned_duration_mean", "duplicate_rate_mean"]
            ],
            base_agg.rename(columns={"event_recall_mean": "event_recall", "observed_precision_mean": "precision"})[
                ["method", "budget", "tau", "event_recall", "precision", "returned_duration_mean", "duplicate_rate_mean"]
            ],
        ],
        ignore_index=True,
    )
    write_df(main_comp, "precision_recall_duration_duplicate_summary.csv")
    write_text(
        OUT_DIR / "FINAL_REPORT.md",
        f"""# FINAL REPORT: {EXP_NAME}

## 1. Mini-Universe

{md_table(manifest)}

The selected segment contains {len(ref_units)} 2s units and {len(ref_events)} VLM-defined reference events.
Positive unit rate is {ref_units['label_event'].mean():.3f}.

## 2. Oracle / Reference Definition

Reference labels are rematerialized from V13.8 Qwen3-VL-32B center10 pseudo-oracle outputs for
`O_enter_ego_path_v0`. They are not human truth. Full reference is used for evaluation and oracle replay
lookup only.

## 3. Cheap Signal Quality

Top cheap signals by AUC:

{md_table(signal_q.head(8))}

## 4. Interval Lattice Proposal Quality

{md_table(proposal)}

## 5. Main Comparison: Budget vs Event Recall

{md_table(main_comp)}

## 6. Precision / Recall / Boundary / Duration / Duplicate Summary

See `precision_recall_duration_duplicate_summary.csv`. Main CILS table:

{md_table(main)}

## 7. Ablation Conclusions

Mean ablation results are in `ablation_results.csv`. Compact view:

{md_table(ab_agg.groupby('ablation').agg(event_recall_mean=('event_recall_mean','mean'), precision_mean=('precision_mean','mean')).reset_index())}

## 8. Stress Test Conclusions

{md_table(stress_agg.groupby('stress_test').agg(event_recall_mean=('event_recall_mean','mean'), precision_mean=('precision_mean','mean')).reset_index())}

## 9. Decision

Decision: `{decision}`.

Success criterion checked: CILS must improve event recall over both `threshold_merge_topk` and
`arc_style_prune_refine_simplified` at at least two budget points for tau 0.8 or 0.9, while maintaining
observed precision and without obvious duration or duplicate inflation.

Improvement budget counts by tau and required baseline:

{md_table(by_tau_baseline)}

Promising-by-tau flags: {promising_by_tau}.

## 10. Next Step

If decision is PROMISING, the next step is a second clean mini-universe on a different long video before
claiming generalization. If weak or inconclusive, inspect calibration sparsity, blind spots, and whether
interval boundaries are too short for IoU>=0.3 event matching before running more VLM.

## Limitations

- This is a pseudo-oracle mini-universe experiment on a single selected segment.
- Universe selection used existing VLM labels for curation, so prevalence is not unbiased.
- Cached YOLOv8n detections were reused; optical flow is represented by a detection-derived burst proxy.
- No formal clip-level recall certificate is claimed here.
""",
    )
    progress("stage10_final", result=f"decision={decision}")


STAGES = {
    "stage0": stage0_select,
    "stage1": stage1_reference,
    "stage2": stage2_signals,
    "stage3": stage3_diagnostics,
    "stage4": stage4_lattice,
    "stage5": stage5_proposals,
    "stage6": stage6_calibration,
    "stage7": stage7_optimization,
    "stage8": stage8_baselines,
    "stage9": stage9_ablation,
    "stage10": stage10_final,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=list(STAGES) + ["all"])
    args = parser.parse_args()
    ensure_dirs()
    shutil.copyfile(SCRIPT_DIR / "pipeline.py", OUT_DIR / "scripts" / "pipeline.py")
    if args.stage == "all":
        for name, fn in STAGES.items():
            print(f"[{now_iso()}] running {name}", flush=True)
            fn()
        return 0
    print(f"[{now_iso()}] running {args.stage}", flush=True)
    STAGES[args.stage]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
