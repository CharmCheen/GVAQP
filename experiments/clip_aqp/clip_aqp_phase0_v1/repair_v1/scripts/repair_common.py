#!/usr/bin/env python3
"""Shared code for Phase 0 repair_v1.

This is an isolated repair pass over existing Phase 0 outputs. It does not
collect new data, train models, or call VLMs.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
PHASE0_DIR = PROJECT_ROOT / "test_vlm/outputs/clip_aqp_phase0_v1"
REPAIR_DIR = PHASE0_DIR / "repair_v1"
EPSILON = 1e-9

GAMMAS = [0.8, 0.9]
DELTAS = [0.05, 0.10]
THETAS = [0.3, 0.5]
BLOCK_SIZES = [10.0, 15.0, 30.0]
NUM_TRIALS = 100
RANDOM_SEED = 20260221
CERT_SAMPLE_FRAC = 0.35
RETURNED_CLIP_BUDGET_FRAC = 0.20
PADDING_WIDTH_SECONDS = 5.0
MANDATED_POWER_SENTENCE = (
    "Sample size insufficient for robust GVR estimation; results indicate direction only "
    "and must not be treated as sufficient evidence for GO/NO_GO."
)


def ensure_dirs() -> None:
    for name in ["scripts", "tables", "reports", "logs", "config", "data_manifest", "figures"]:
        (REPAIR_DIR / name).mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_progress(checkpoint: str, command: str, result: str, failure: str = "", fix: str = "", next_action: str = "") -> None:
    ensure_dirs()
    path = REPAIR_DIR / "logs/progress.md"
    with path.open("a", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    f"## {now()}",
                    f"- checkpoint: {checkpoint}",
                    f"- commands run: `{command}`",
                    f"- result: {result}",
                    f"- failure if any: {failure or 'none'}",
                    f"- fix applied: {fix or 'none'}",
                    f"- next action: {next_action or 'none'}",
                    "",
                ]
            )
        )


def normal_quantile(delta: float) -> float:
    if delta <= 0.05:
        return 1.96
    if delta <= 0.10:
        return 1.645
    return 1.282


def load_units() -> pd.DataFrame:
    return pd.read_csv(PHASE0_DIR / "data_audit/phase0_units.csv")


def load_events() -> pd.DataFrame:
    return pd.read_csv(PHASE0_DIR / "data_audit/phase0_pseudo_events.csv")


def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def interval_iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union


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


def fixed_returned_clips(units: pd.DataFrame, budget_frac: float = RETURNED_CLIP_BUDGET_FRAC) -> pd.DataFrame:
    n = max(1, int(math.ceil(len(units) * budget_frac)))
    selected = units.sort_values(["proxy_score", "video_id", "start_time", "unit_id"], ascending=[False, True, True, True]).head(n)
    return stitch_units(selected, merge_gap=0.0)


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
    return hits / len(events), hits, len(events)


def partition_blocks(units: pd.DataFrame, events: pd.DataFrame, returned: pd.DataFrame, block_size: float, theta: float) -> pd.DataFrame:
    rows = []
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
            for event in owned:
                ev_start = safe_float(event["event_start"])
                ev_end = safe_float(event["event_end"])
                candidates = returned[returned["video_id"].astype(str) == str(video_id)]
                hit = any(interval_iou(ev_start, ev_end, safe_float(c["start_time"]), safe_float(c["end_time"])) >= theta for _, c in candidates.iterrows())
                missed += int(not hit)
            rows.append(
                {
                    "block_id": f"block_{block_id:05d}",
                    "video_id": video_id,
                    "start_time": start,
                    "end_time": end,
                    "Y_i_O": y,
                    "M_i_O": missed,
                    "padding_width_used": PADDING_WIDTH_SECONDS,
                    "score_source": "proxy_score",
                }
            )
            block_id += 1
            start = end
    return pd.DataFrame(rows)


def sample_blocks(blocks: pd.DataFrame, rng: np.random.Generator, frac: float) -> pd.DataFrame:
    n = max(1, int(math.ceil(len(blocks) * frac)))
    n = min(n, len(blocks))
    idx = rng.choice(blocks.index.to_numpy(), size=n, replace=False)
    out = blocks.loc[idx].copy().sort_values(["video_id", "start_time", "block_id"]).reset_index(drop=True)
    out["inclusion_probability"] = n / len(blocks)
    return out


def add_certification_provenance(sample: pd.DataFrame, trial: int, gamma: float, delta: float, theta: float, block_size: float, population_blocks: int) -> pd.DataFrame:
    out = sample.copy()
    out["trial"] = trial
    out["gamma"] = gamma
    out["delta"] = delta
    out["theta"] = theta
    out["block_size_seconds"] = block_size
    out["population_blocks"] = population_blocks
    out["sample_split"] = "certification"
    out["used_for_design"] = False
    out["used_for_repair"] = False
    out["used_for_certificate"] = True
    return out


def assert_certification_samples(sample: pd.DataFrame) -> None:
    required = {"sample_split", "used_for_design", "used_for_repair", "inclusion_probability"}
    missing = sorted(required - set(sample.columns))
    if missing:
        raise AssertionError(f"certificate sample missing columns: {missing}")
    bad = (
        (sample["sample_split"].astype(str) != "certification")
        | sample["used_for_design"].astype(bool)
        | sample["used_for_repair"].astype(bool)
    )
    if bool(bad.any()):
        raise AssertionError("final certificate contains non-certification/design/repair samples")


def write_bound_violation(context: dict) -> None:
    lines = ["# Bound Invariant Violation", "", "The repaired certificate code halted because a bound invariant failed.", ""]
    for key, value in context.items():
        lines.append(f"- {key}: `{value}`")
    (REPAIR_DIR / "reports/BOUND_INVARIANT_VIOLATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def certificate_from_sample(sample: pd.DataFrame, population_n: int, delta: float, context: dict | None = None) -> dict:
    assert_certification_samples(sample)
    n = len(sample)
    if n == 0 or population_n <= 0:
        return {
            "Y_hat_O": math.nan,
            "M_hat_O": math.nan,
            "UCB_M_O": math.nan,
            "LCB_Y_O": math.nan,
            "LCB_recall_O": 0.0,
            "certificate_status": "NO_CERTIFICATE",
        }
    z = normal_quantile(delta)
    y_vals = pd.to_numeric(sample["Y_i_O"], errors="coerce").fillna(0.0).astype(float)
    m_vals = pd.to_numeric(sample["M_i_O"], errors="coerce").fillna(0.0).astype(float)
    fpc = math.sqrt(max(0.0, 1.0 - n / max(population_n, 1))) if population_n > 1 else 0.0
    y_hat = population_n * float(y_vals.mean())
    m_hat = population_n * float(m_vals.mean())
    y_se_total = population_n * (float(y_vals.std(ddof=1)) / math.sqrt(n) * fpc if n > 1 else 0.0)
    m_se_total = population_n * (float(m_vals.std(ddof=1)) / math.sqrt(n) * fpc if n > 1 else 0.0)
    lcb_y = max(0.0, y_hat - z * y_se_total)
    ucb_m = max(m_hat, m_hat + z * m_se_total)
    violation = None
    if ucb_m < m_hat - EPSILON:
        violation = "UCB_M_O < M_hat_O - epsilon"
    if lcb_y > y_hat + EPSILON:
        violation = "LCB_Y_O > Y_hat_O + epsilon"
    if violation:
        payload = {
            "violation": violation,
            "epsilon": EPSILON,
            "population_n": population_n,
            "sample_n": n,
            "delta": delta,
            "Y_hat_O": y_hat,
            "M_hat_O": m_hat,
            "UCB_M_O": ucb_m,
            "LCB_Y_O": lcb_y,
        }
        if context:
            payload.update(context)
        write_bound_violation(payload)
        raise AssertionError(violation)
    if lcb_y <= 0:
        lcb_recall = 0.0
        status = "NO_CERTIFICATE"
    else:
        lcb_recall = max(0.0, min(1.0, 1.0 - ucb_m / lcb_y))
        status = "CERTIFICATE_COMPUTED"
    return {
        "Y_hat_O": y_hat,
        "M_hat_O": m_hat,
        "UCB_M_O": ucb_m,
        "LCB_Y_O": lcb_y,
        "LCB_recall_O": lcb_recall,
        "certificate_status": status,
        "Y_margin": y_hat - lcb_y,
        "M_margin": ucb_m - m_hat,
        "epsilon": EPSILON,
    }


def markdown_table(df: pd.DataFrame, max_rows: int = 40) -> str:
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
                vals.append("" if math.isnan(value) else f"{value:.4g}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)
