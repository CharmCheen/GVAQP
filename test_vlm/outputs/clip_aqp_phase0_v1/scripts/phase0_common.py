#!/usr/bin/env python3
"""Shared utilities for CASQ/G-ClipAQP Phase 0.

All outputs are oracle-relative to existing VLM-defined labels unless a caller
explicitly supplies human-adjudicated gold labels. This module never runs VLMs,
trains models, or downloads data.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT_DIR = PROJECT_ROOT / "test_vlm/outputs/clip_aqp_phase0_v1"
TIMELINE_CSV = PROJECT_ROOT / "test_vlm/focused_validation_outputs/04_temporal_concentration/positive_timeline.csv"
PREFERRED_EVENTS_CSV = PROJECT_ROOT / "test_vlm/focused_validation_outputs/03_event_conversion/oracle_events_gap3.csv"
STABILITY_FILES = [
    PROJECT_ROOT / "test_vlm/outputs/compare_8b_raw_vs_masked.csv",
    PROJECT_ROOT / "test_vlm/outputs/compare_32b_raw_vs_masked.csv",
]

GAMMAS = [0.8, 0.9]
DELTAS = [0.05, 0.10]
THETAS = [0.3, 0.5]
BLOCK_SIZES = [10.0, 15.0, 30.0]
NUM_TRIALS = 100
RANDOM_SEED = 20260221
PSEUDO_EVENT_GAP_SECONDS = 3.0
CERT_SAMPLE_FRAC = 0.35
DIAG_SAMPLE_FRAC = 0.25
RETURNED_CLIP_BUDGET_FRAC = 0.20
PADDING_WIDTH_SECONDS = 5.0


def ensure_dirs() -> None:
    for name in ["config", "data_audit", "scripts", "tables", "figures", "reports", "logs", "data_manifest"]:
        (OUT_DIR / name).mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_progress(checkpoint: str, commands: str, result: str, failure: str = "", fix: str = "", next_action: str = "") -> None:
    ensure_dirs()
    path = OUT_DIR / "logs/progress.md"
    with path.open("a", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    f"## {now()}",
                    f"- checkpoint: {checkpoint}",
                    f"- commands run: `{commands}`",
                    f"- result: {result}",
                    f"- failure if any: {failure or 'none'}",
                    f"- fix applied: {fix or 'none'}",
                    f"- next action: {next_action or 'none'}",
                    "",
                ]
            )
        )


def as_bool_label(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "positive", "y"}


def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def normal_quantile(delta: float) -> float:
    if delta <= 0.05:
        return 1.96
    if delta <= 0.10:
        return 1.645
    return 1.282


def interval_iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union


def normalize_score(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)
    lo = float(values.min())
    hi = float(values.max())
    if hi <= lo:
        return pd.Series(np.zeros(len(values)), index=series.index)
    return (values - lo) / (hi - lo)


def load_units() -> pd.DataFrame:
    if (OUT_DIR / "data_audit/phase0_units.csv").exists():
        return pd.read_csv(OUT_DIR / "data_audit/phase0_units.csv")
    if not TIMELINE_CSV.exists():
        raise SystemExit(f"missing required timeline input: {TIMELINE_CSV}")
    rows = pd.read_csv(TIMELINE_CSV)
    required = {"clip_id", "segment_id", "start_time", "end_time", "oracle_positive", "score_count"}
    missing = sorted(required - set(rows.columns))
    if missing:
        raise SystemExit(f"timeline input missing required columns: {missing}")
    rows = rows.copy()
    rows["unit_id"] = rows["clip_id"].astype(str)
    rows["video_id"] = rows["segment_id"].astype(str)
    rows["duration"] = pd.to_numeric(rows["end_time"], errors="coerce") - pd.to_numeric(rows["start_time"], errors="coerce")
    rows["proxy_score"] = pd.to_numeric(rows["score_count"], errors="coerce").fillna(0.0)
    rows["proxy_score"] = normalize_score(rows["proxy_score"])
    rows["proxy_source"] = "score_count"
    rows["score_source"] = "proxy_score"
    rows["oracle_label"] = rows["oracle_positive"].map(as_bool_label)
    rows["oracle_source"] = "conservative_vlm_pseudo_oracle"
    rows["human_label"] = pd.NA
    rows["source_path"] = rows.get("clip_path", pd.Series([pd.NA] * len(rows))).astype("string")
    rows["has_event_boundary"] = False
    rows["event_id"] = pd.NA
    rows["event_start"] = pd.NA
    rows["event_end"] = pd.NA
    rows["event_boundary_source"] = "none_in_unit_table"
    rows = rows.sort_values(["video_id", "start_time", "end_time", "unit_id"]).reset_index(drop=True)
    return rows


def build_pseudo_events(units: pd.DataFrame, gap_seconds: float = PSEUDO_EVENT_GAP_SECONDS) -> pd.DataFrame:
    positives = units[units["oracle_label"].map(as_bool_label)].sort_values(["video_id", "start_time", "end_time", "unit_id"])
    events = []
    current = None
    idx = 0
    for _, row in positives.iterrows():
        video_id = str(row["video_id"])
        start = safe_float(row["start_time"])
        end = safe_float(row["end_time"])
        if current is None or current["video_id"] != video_id or start - float(current["event_end"]) > gap_seconds:
            if current is not None:
                events.append(current)
            current = {
                "event_id": f"pseudo_event_{idx:04d}",
                "video_id": video_id,
                "event_start": start,
                "event_end": end,
                "positive_unit_ids": [str(row["unit_id"])],
            }
            idx += 1
        else:
            current["event_end"] = max(float(current["event_end"]), end)
            current["positive_unit_ids"].append(str(row["unit_id"]))
    if current is not None:
        events.append(current)
    for event in events:
        event["duration"] = float(event["event_end"]) - float(event["event_start"])
        event["num_positive_units"] = len(event["positive_unit_ids"])
        event["positive_unit_ids"] = ";".join(event["positive_unit_ids"])
        event["event_boundary_type"] = "pseudo_from_adjacent_oracle_positive_units"
        event["has_event_boundary"] = False
    return pd.DataFrame(events)


def attach_pseudo_events(units: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    rows = units.copy()
    lookup = {}
    for _, event in events.iterrows():
        for unit_id in str(event["positive_unit_ids"]).split(";"):
            lookup[unit_id] = event
    for idx, row in rows.iterrows():
        event = lookup.get(str(row["unit_id"]))
        if event is not None:
            rows.at[idx, "event_id"] = event["event_id"]
            rows.at[idx, "event_start"] = event["event_start"]
            rows.at[idx, "event_end"] = event["event_end"]
            rows.at[idx, "event_boundary_source"] = "pseudo_from_adjacent_oracle_positive_units"
            rows.at[idx, "has_event_boundary"] = False
    return rows


def stitch_units(selected: pd.DataFrame, merge_gap: float = 0.0) -> pd.DataFrame:
    selected = selected.sort_values(["video_id", "start_time", "end_time", "unit_id"])
    clips = []
    current = None
    for _, row in selected.iterrows():
        video_id = str(row["video_id"])
        start = safe_float(row["start_time"])
        end = safe_float(row["end_time"])
        if current is None or current["video_id"] != video_id or start - current["end_time"] > merge_gap:
            if current is not None:
                clips.append(current)
            current = {
                "returned_clip_id": f"returned_{len(clips):05d}",
                "video_id": video_id,
                "start_time": start,
                "end_time": end,
                "unit_ids": [str(row["unit_id"])],
            }
        else:
            current["end_time"] = max(float(current["end_time"]), end)
            current["unit_ids"].append(str(row["unit_id"]))
    if current is not None:
        clips.append(current)
    for clip in clips:
        clip["unit_ids"] = ";".join(clip["unit_ids"])
    return pd.DataFrame(clips)


def event_recall(events: pd.DataFrame, returned: pd.DataFrame, theta: float) -> tuple[float, int, int]:
    if events.empty:
        return 0.0, 0, 0
    hits = 0
    for _, event in events.iterrows():
        video_id = str(event["video_id"])
        ev_start = safe_float(event["event_start"])
        ev_end = safe_float(event["event_end"])
        candidates = returned[returned["video_id"].astype(str) == video_id]
        hit = any(interval_iou(ev_start, ev_end, safe_float(r["start_time"]), safe_float(r["end_time"])) >= theta for _, r in candidates.iterrows())
        hits += int(hit)
    total = len(events)
    return hits / total if total else 0.0, hits, total


def fixed_returned_clips(units: pd.DataFrame, budget_frac: float = RETURNED_CLIP_BUDGET_FRAC) -> pd.DataFrame:
    n = max(1, int(math.ceil(len(units) * budget_frac)))
    selected = units.sort_values(["proxy_score", "video_id", "start_time", "unit_id"], ascending=[False, True, True, True]).head(n)
    return stitch_units(selected, merge_gap=0.0)


def partition_blocks(units: pd.DataFrame, events: pd.DataFrame, returned: pd.DataFrame, block_size: float, theta: float) -> pd.DataFrame:
    block_rows = []
    block_id = 0
    for video_id, group in units.groupby("video_id", sort=True):
        min_start = math.floor(float(group["start_time"].min()) / block_size) * block_size
        max_end = math.ceil(float(group["end_time"].max()) / block_size) * block_size
        start = min_start
        while start < max_end:
            end = start + block_size
            owned = []
            for _, event in events[events["video_id"].astype(str) == str(video_id)].iterrows():
                midpoint = (safe_float(event["event_start"]) + safe_float(event["event_end"])) / 2.0
                if start <= midpoint < end:
                    owned.append(event)
            y = len(owned)
            missed = 0
            truncated = 0
            for event in owned:
                ev_start = safe_float(event["event_start"])
                ev_end = safe_float(event["event_end"])
                if ev_start < start - PADDING_WIDTH_SECONDS or ev_end > end + PADDING_WIDTH_SECONDS:
                    truncated += 1
                hit = False
                for _, clip in returned[returned["video_id"].astype(str) == str(video_id)].iterrows():
                    if interval_iou(ev_start, ev_end, safe_float(clip["start_time"]), safe_float(clip["end_time"])) >= theta:
                        hit = True
                        break
                missed += int(not hit)
            block_rows.append(
                {
                    "block_id": f"block_{block_id:05d}",
                    "video_id": video_id,
                    "block_start": start,
                    "block_end": end,
                    "Y_i_O": y,
                    "M_i_O": missed,
                    "padding_width_used": PADDING_WIDTH_SECONDS,
                    "truncated_event_count": truncated,
                    "score_source": "proxy_score",
                }
            )
            block_id += 1
            start = end
    return pd.DataFrame(block_rows)


def sample_blocks(blocks: pd.DataFrame, rng: np.random.Generator, frac: float, exclude_ids: set[str] | None = None) -> pd.DataFrame:
    exclude_ids = exclude_ids or set()
    candidates = blocks[~blocks["block_id"].isin(exclude_ids)].copy()
    if candidates.empty:
        return candidates
    n = max(1, int(math.ceil(len(candidates) * frac)))
    n = min(n, len(candidates))
    idx = rng.choice(candidates.index.to_numpy(), size=n, replace=False)
    return candidates.loc[idx].copy().sort_values(["video_id", "block_start", "block_id"]).reset_index(drop=True)


def assert_certification_samples(df: pd.DataFrame) -> None:
    required = {"sample_split", "used_for_design", "used_for_repair"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise AssertionError(f"certificate sample table missing provenance columns: {missing}")
    bad_split = df["sample_split"].astype(str) != "certification"
    bad_design = df["used_for_design"].astype(bool)
    bad_repair = df["used_for_repair"].astype(bool)
    if bool((bad_split | bad_design | bad_repair).any()):
        raise AssertionError("statistical validity violation: final certificate contains non-certification/design/repair samples")


def conservative_certificate(sample: pd.DataFrame, population_n: int, delta: float) -> dict:
    assert_certification_samples(sample)
    if sample.empty or population_n <= 0:
        return {
            "UCB_M_O": math.nan,
            "LCB_Y_O": math.nan,
            "LCB_recall_O": 0.0,
            "certificate_status": "NO_CERTIFICATE",
        }
    n = len(sample)
    z = normal_quantile(delta)
    y_vals = pd.to_numeric(sample["Y_i_O"], errors="coerce").fillna(0.0).astype(float)
    m_vals = pd.to_numeric(sample["M_i_O"], errors="coerce").fillna(0.0).astype(float)
    fpc = math.sqrt(max(0.0, 1.0 - n / max(population_n, 1))) if population_n > 1 else 0.0
    y_se = y_vals.std(ddof=1) / math.sqrt(n) * fpc if n > 1 else 0.0
    m_se = m_vals.std(ddof=1) / math.sqrt(n) * fpc if n > 1 else 0.0
    lcb_y = max(0.0, population_n * (float(y_vals.mean()) - z * y_se))
    ucb_m = min(lcb_y if lcb_y > 0 else float("inf"), population_n * (float(m_vals.mean()) + z * m_se))
    if lcb_y <= 0:
        lcb_recall = 0.0
        status = "NO_CERTIFICATE"
    else:
        lcb_recall = max(0.0, min(1.0, 1.0 - ucb_m / lcb_y))
        status = "CERTIFICATE_COMPUTED"
    return {
        "UCB_M_O": ucb_m,
        "LCB_Y_O": lcb_y,
        "LCB_recall_O": lcb_recall,
        "certificate_status": status,
    }


def markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows)
    cols = list(view.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in view.iterrows():
        vals = []
        for col in cols:
            value = row[col]
            if isinstance(value, float):
                vals.append(f"{value:.4g}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)
