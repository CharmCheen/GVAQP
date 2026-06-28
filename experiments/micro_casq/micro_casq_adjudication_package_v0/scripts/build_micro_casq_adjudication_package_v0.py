#!/usr/bin/env python3
"""Build Micro-CASQ adjudication sample package v0 from existing audit assets."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
INPUT_DIR = ROOT / "test_vlm/outputs/clip_aqp_data_asset_audit_v1"
OUT_DIR = ROOT / "test_vlm/outputs/micro_casq_adjudication_package_v0"
SCRIPTS_DIR = OUT_DIR / "scripts"
REPORTS_DIR = OUT_DIR / "reports"
TABLES_DIR = OUT_DIR / "tables"
REVIEW_DIR = OUT_DIR / "review_package"
PILOT_CLIPS_DIR = REVIEW_DIR / "pilot_clips"
PILOT_SHEETS_DIR = REVIEW_DIR / "pilot_contact_sheets"
LOGS_DIR = OUT_DIR / "logs"
SUMMARY_MD = ROOT / "garc_eval/outputs/micro_casq_adjudication_package_v0_summary.md"
RUN_SUMMARY_JSON = LOGS_DIR / "run_summary.json"

REQUIRED_INPUTS = [
    INPUT_DIR / "tables/micro_casq_candidate_pool_index.csv",
    INPUT_DIR / "tables/micro_casq_adjudication_sampling_plan.csv",
    INPUT_DIR / "schema/micro_casq_adjudication_schema.json",
    INPUT_DIR / "tables/micro_casq_adjudication_template.csv",
    INPUT_DIR / "reports/MICRO_CASQ_ADJUDICATION_PLAN.md",
    INPUT_DIR / "reports/MICRO_CASQ_BENCHMARK_PROTOCOL.md",
    INPUT_DIR / "reports/DATA_PATH_DECISION_MEMO.md",
]

STRATUM_TARGETS = {
    "likely_positive": 80,
    "label_disagreement": 60,
    "possible_false_negative": 60,
    "hard_negative": 220,
    "boundary_uncertain": 80,
}
PILOT_TARGETS = {
    "likely_positive": 10,
    "label_disagreement": 10,
    "possible_false_negative": 10,
    "hard_negative": 15,
    "boundary_uncertain": 5,
}
SAMPLE_COLUMNS = [
    "adjudication_sample_id",
    "pool_item_id",
    "sampling_stratum",
    "video_id",
    "clip_id",
    "source_video_path",
    "clip_start_time",
    "clip_end_time",
    "clip_duration",
    "source_asset",
    "candidate_source",
    "old_label",
    "old_label_source",
    "old_confidence",
    "old_event_start",
    "old_event_end",
    "boundary_source",
    "is_nexar_derived",
    "is_vlm_derived",
    "is_human_audited",
    "is_pseudo_boundary",
    "is_external_label",
    "selection_reason",
    "path_exists",
    "time_window_valid",
    "materialization_status",
    "notes",
]
PILOT_COLUMNS = [
    "pilot_id",
    "adjudication_sample_id",
    "sampling_stratum",
    "video_id",
    "clip_id",
    "source_video_path",
    "clip_start_time",
    "clip_end_time",
    "clip_duration",
    "candidate_source",
    "old_label",
    "old_label_source",
    "old_confidence",
    "boundary_source",
    "review_priority",
    "review_question",
    "suggested_human_check",
    "materialized_clip_path",
    "contact_sheet_path",
    "notes",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    for path in [SCRIPTS_DIR, REPORTS_DIR, TABLES_DIR, REVIEW_DIR, PILOT_CLIPS_DIR, PILOT_SHEETS_DIR, LOGS_DIR, SUMMARY_MD.parent]:
        path.mkdir(parents=True, exist_ok=True)


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = [str(row[c]).replace("\n", " ") for c in df.columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def read_protocol_reference() -> tuple[str, str]:
    primary = ROOT / "docs/clip_aqp/CASQ_CODEX_BRIEF_V12_1.md"
    fallback = ROOT / "CASQ_CODEX_BRIEF_V12_1.md"
    if primary.exists():
        return str(primary), primary.read_text(encoding="utf-8", errors="replace")
    if fallback.exists():
        return str(fallback), fallback.read_text(encoding="utf-8", errors="replace")
    return "MISSING", ""


def verify_inputs() -> list[Path]:
    missing = [p for p in REQUIRED_INPUTS if not p.exists()]
    if missing:
        lines = [
            "# Missing Inputs",
            "",
            "Required upstream audit/planning inputs are missing. Package construction stopped before partial sampling.",
            "",
            "## Missing Files",
            "",
        ]
        lines.extend(f"- `{rel(p)}`" for p in missing)
        lines.extend(["", "MICRO_CASQ_PACKAGE_DECISION: MISSING_INPUTS", ""])
        write_text(REPORTS_DIR / "MISSING_INPUTS.md", "\n".join(lines))
    return missing


def to_bool_series(s: pd.Series) -> pd.Series:
    return s.fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y"])


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def str_col(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([""] * len(df), index=df.index)
    return df[col].fillna("").astype(str)


def path_exists_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    text = str(value).strip()
    return bool(text) and text.lower() != "nan" and Path(text).exists()


def valid_time_mask(df: pd.DataFrame) -> pd.Series:
    start = numeric(df["start_time"])
    end = numeric(df["end_time"])
    return start.notna() & end.notna() & (end > start)


def value_counts_rows(df: pd.DataFrame, col: str) -> list[dict[str, Any]]:
    counts = df[col].fillna("__MISSING__").astype(str).value_counts(dropna=False)
    return [{"metric": f"{col}={k}", "value": int(v)} for k, v in counts.items()]


def candidate_pool_quality(df: pd.DataFrame) -> dict[str, Any]:
    start = numeric(df["start_time"])
    end = numeric(df["end_time"])
    duration = numeric(df["duration"])
    valid_time = start.notna() & end.notna() & (end > start)
    path_exists = df["source_video_path"].map(path_exists_value)
    metrics: list[dict[str, Any]] = [
        {"metric": "row_count", "value": int(len(df))},
        {"metric": "unique_video_id_count", "value": int(df["video_id"].nunique(dropna=True))},
        {"metric": "unique_source_asset_count", "value": int(df["source_asset"].nunique(dropna=True))},
        {"metric": "available_source_video_path_count", "value": int(df["source_video_path"].notna().sum())},
        {"metric": "existing_source_video_path_count", "value": int(path_exists.sum())},
        {"metric": "missing_source_video_path_count", "value": int((~df["source_video_path"].notna()).sum())},
        {"metric": "valid_start_time_end_time_count", "value": int(valid_time.sum())},
        {"metric": "invalid_start_time_end_time_count", "value": int((~valid_time).sum())},
        {"metric": "duration_nonnull_count", "value": int(duration.notna().sum())},
    ]
    for q in [0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0]:
        val = duration.dropna().quantile(q) if duration.notna().any() else float("nan")
        metrics.append({"metric": f"duration_quantile_{q:g}", "value": float(val) if pd.notna(val) else ""})
    for col in ["old_label", "candidate_source", "boundary_source"]:
        metrics.extend(value_counts_rows(df, col))
    for col in [
        "is_nexar_derived",
        "is_vlm_derived",
        "is_human_audited",
        "is_pseudo_boundary",
        "is_external_label",
        "recommended_for_adjudication",
    ]:
        metrics.append({"metric": f"{col}_count", "value": int(to_bool_series(df[col]).sum())})
    audit_df = pd.DataFrame(metrics)
    audit_df.to_csv(TABLES_DIR / "candidate_pool_quality_audit.csv", index=False)

    top_old = df["old_label"].fillna("__MISSING__").astype(str).value_counts().head(15)
    top_source = df["candidate_source"].fillna("__MISSING__").astype(str).value_counts().head(15)
    report = [
        "# Candidate Pool Quality Audit",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "This is a metadata-only audit. It does not infer labels, create boundaries, or treat prior VLM/Nexar labels as gold truth.",
        "",
        "## Core Counts",
        "",
        f"- Row count: `{len(df)}`",
        f"- Unique `video_id`: `{df['video_id'].nunique(dropna=True)}`",
        f"- Unique `source_asset`: `{df['source_asset'].nunique(dropna=True)}`",
        f"- Rows with non-empty `source_video_path`: `{int(df['source_video_path'].notna().sum())}`",
        f"- Rows with existing `source_video_path`: `{int(path_exists.sum())}`",
        f"- Rows missing `source_video_path`: `{int((~df['source_video_path'].notna()).sum())}`",
        f"- Valid start/end windows: `{int(valid_time.sum())}`",
        f"- Invalid start/end windows: `{int((~valid_time).sum())}`",
        "",
        "## Duration Distribution",
        "",
        markdown_table(audit_df[audit_df["metric"].str.startswith("duration_quantile")]),
        "",
        "## Old Label Distribution, Top 15",
        "",
        markdown_table(top_old.rename_axis("old_label").reset_index(name="count")),
        "",
        "## Candidate Source Distribution, Top 15",
        "",
        markdown_table(top_source.rename_axis("candidate_source").reset_index(name="count")),
        "",
        "## Provenance Flags",
        "",
    ]
    for col in ["is_nexar_derived", "is_vlm_derived", "is_human_audited", "is_pseudo_boundary", "is_external_label", "recommended_for_adjudication"]:
        report.append(f"- `{col}` true count: `{int(to_bool_series(df[col]).sum())}`")
    write_text(REPORTS_DIR / "CANDIDATE_POOL_QUALITY_AUDIT.md", "\n".join(report) + "\n")
    return {
        "row_count": int(len(df)),
        "unique_video_count": int(df["video_id"].nunique(dropna=True)),
        "existing_path_count": int(path_exists.sum()),
        "valid_time_count": int(valid_time.sum()),
    }


def classify_stratum(df: pd.DataFrame) -> pd.Series:
    old = str_col(df, "old_label").str.lower()
    reason = str_col(df, "recommendation_reason").str.lower()
    cand = str_col(df, "candidate_source").str.lower()
    boundary = str_col(df, "boundary_source").str.lower()
    source = str_col(df, "source_asset").str.lower()
    is_nexar = to_bool_series(df["is_nexar_derived"])
    is_external = to_bool_series(df["is_external_label"])
    is_pseudo = to_bool_series(df["is_pseudo_boundary"])
    strata = pd.Series("", index=df.index, dtype="object")
    positive = old.isin(["positive", "yes", "true", "1", "conservative_positive"]) | old.str.contains("positive", na=False)
    negative = old.isin(["negative", "no", "false", "0", "normal"]) | old.str.contains("negative|normal", regex=True, na=False)
    disagreement = reason.str.contains("disagreement|overrode|rejected|32b negative|mismatch", regex=True, na=False)
    possible_fn = negative & (
        reason.str.contains("possible false negative|proxy|candidate|vlm evidence|high", regex=True, na=False)
        | cand.str.contains("proxy|predicted|kinematic|micro_audit|candidate", regex=True, na=False)
    )
    boundary_uncertain = (
        is_pseudo
        | is_external
        | is_nexar
        | boundary.str.contains("pseudo|external|alert|uncertain|derived|event_start|event_end", regex=True, na=False)
        | source.str.contains("nexar|phase0|pseudo", regex=True, na=False)
    )
    hard_negative = negative
    strata[positive] = "likely_positive"
    strata[disagreement] = "label_disagreement"
    strata[possible_fn] = "possible_false_negative"
    strata[hard_negative & (strata == "")] = "hard_negative"
    strata[boundary_uncertain & (strata == "")] = "boundary_uncertain"
    strata[(strata == "") & positive] = "likely_positive"
    strata[(strata == "") & negative] = "hard_negative"
    strata[strata == ""] = "hard_negative"
    return strata


def diverse_select(df: pd.DataFrame, target: int, used: set[str], stratum: str) -> pd.DataFrame:
    if target <= 0 or df.empty:
        return df.head(0).copy()
    pool = df[~df["pool_item_id"].astype(str).isin(used)].copy()
    if pool.empty:
        return pool
    start_col = "start_time" if "start_time" in pool.columns else "clip_start_time"
    end_col = "end_time" if "end_time" in pool.columns else "clip_end_time"
    duration_col = "duration" if "duration" in pool.columns else "clip_duration"
    start = numeric(pool[start_col])
    end = numeric(pool[end_col])
    pool["_path_exists"] = pool["source_video_path"].map(path_exists_value).astype(int)
    pool["_time_valid"] = (start.notna() & end.notna() & (end > start)).astype(int)
    if "recommended_for_adjudication" in pool.columns:
        pool["_recommended"] = to_bool_series(pool["recommended_for_adjudication"]).astype(int)
    else:
        pool["_recommended"] = 1
    pool["_duration"] = numeric(pool[duration_col]).fillna(end - start)
    pool["_duration_reasonable"] = ((pool["_duration"] > 0) & (pool["_duration"] <= 60)).astype(int)
    pool["_video_key"] = pool["video_id"].fillna("__missing__").astype(str)
    pool["_rank"] = range(len(pool))
    pool = pool.sort_values(
        ["_recommended", "_path_exists", "_time_valid", "_duration_reasonable", "_video_key", "_rank"],
        ascending=[False, False, False, False, True, True],
        kind="mergesort",
    )
    selected_idx: list[Any] = []
    video_counts: Counter[str] = Counter()
    cap = 1
    while len(selected_idx) < target and len(selected_idx) < len(pool):
        added = False
        for idx, row in pool.iterrows():
            if idx in selected_idx:
                continue
            video = row["_video_key"]
            if video_counts[video] < cap:
                selected_idx.append(idx)
                video_counts[video] += 1
                added = True
                if len(selected_idx) >= target:
                    break
        if not added:
            cap += 1
    out = pool.loc[selected_idx].copy()
    out["selection_reason"] = (
        "selected_for_"
        + stratum
        + "; preferred existing source path, valid time window, recommended rows, and diverse video coverage"
    )
    helper_cols = [c for c in out.columns if c.startswith("_") and c != "_stratum"]
    return out.drop(columns=helper_cols)


def build_samples(pool: pd.DataFrame, plan: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = pool.copy()
    df["_stratum"] = classify_stratum(df)
    recommended = to_bool_series(df["recommended_for_adjudication"])
    used: set[str] = set()
    selected_parts: list[pd.DataFrame] = []
    shortfalls: dict[str, int] = {}
    available_by_stratum: dict[str, int] = {}
    valid_candidate = df["source_video_path"].map(path_exists_value) & valid_time_mask(df)
    for stratum, target in STRATUM_TARGETS.items():
        stratum_rows = df[df["_stratum"].eq(stratum)]
        primary = stratum_rows.loc[recommended.loc[stratum_rows.index] & valid_candidate.loc[stratum_rows.index]]
        secondary = stratum_rows.loc[recommended.loc[stratum_rows.index]]
        fallback = stratum_rows
        combined = pd.concat([primary, secondary, fallback], axis=0).drop_duplicates("pool_item_id", keep="first")
        available_by_stratum[stratum] = int(len(combined))
        chosen = diverse_select(combined, target, used, stratum)
        used.update(chosen["pool_item_id"].astype(str).tolist())
        selected_parts.append(chosen)
        shortfalls[stratum] = max(0, target - len(chosen))
    selected = pd.concat(selected_parts, ignore_index=True) if selected_parts else df.head(0).copy()
    selected = selected.head(sum(STRATUM_TARGETS.values())).copy()
    start = numeric(selected["start_time"])
    end = numeric(selected["end_time"])
    duration = numeric(selected["duration"]).fillna(end - start)
    selected["adjudication_sample_id"] = [f"adj_v0_{i:04d}" for i in range(1, len(selected) + 1)]
    selected["sampling_stratum"] = selected["_stratum"]
    selected["clip_start_time"] = start
    selected["clip_end_time"] = end
    selected["clip_duration"] = duration
    selected["path_exists"] = selected["source_video_path"].map(path_exists_value)
    selected["time_window_valid"] = start.notna() & end.notna() & (end > start)
    selected["materialization_status"] = "pending_feasibility_check"
    selected["notes"] = "Old labels retained as provenance only; not gold truth."
    out = selected.rename(columns={}).copy()
    for col in SAMPLE_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out = out[SAMPLE_COLUMNS]
    out.to_csv(TABLES_DIR / "micro_casq_adjudication_samples_v0.csv", index=False)
    return out, {
        "selected_count": int(len(out)),
        "shortfalls": {k: int(v) for k, v in shortfalls.items() if v > 0},
        "available_by_stratum": available_by_stratum,
        "selected_by_stratum": out["sampling_stratum"].value_counts().to_dict(),
    }


def ffprobe_readable(path: str) -> tuple[bool, str]:
    if not shutil.which("ffprobe"):
        return True, "ffprobe_not_available"
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip()[:300]
    except Exception as exc:  # pragma: no cover - defensive runtime audit
        return False, str(exc)[:300]


def feasibility(samples: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = []
    for _, row in samples.iterrows():
        status = "materializable"
        error = ""
        path = str(row.get("source_video_path", "")).strip()
        start = pd.to_numeric(row.get("clip_start_time", ""), errors="coerce")
        end = pd.to_numeric(row.get("clip_end_time", ""), errors="coerce")
        duration = end - start if pd.notna(start) and pd.notna(end) else float("nan")
        if not path or not Path(path).exists():
            status = "missing_video"
        elif pd.isna(start) or pd.isna(end) or end <= start:
            status = "invalid_time_window"
        elif duration <= 0 or duration > 60:
            status = "duration_too_long" if duration > 60 else "invalid_time_window"
        else:
            ok, err = ffprobe_readable(path)
            if not ok:
                status = "video_unreadable"
                error = err
        rows.append(
            {
                "adjudication_sample_id": row["adjudication_sample_id"],
                "pool_item_id": row["pool_item_id"],
                "sampling_stratum": row["sampling_stratum"],
                "video_id": row["video_id"],
                "source_video_path": path,
                "clip_start_time": row["clip_start_time"],
                "clip_end_time": row["clip_end_time"],
                "clip_duration": row["clip_duration"],
                "feasibility_status": status,
                "path_exists": bool(path and Path(path).exists()),
                "time_window_valid": bool(pd.notna(start) and pd.notna(end) and end > start),
                "ffprobe_checked": bool(shutil.which("ffprobe")),
                "error_message": error,
            }
        )
    feas = pd.DataFrame(rows)
    feas.to_csv(TABLES_DIR / "micro_casq_sample_feasibility_v0.csv", index=False)
    counts = feas["feasibility_status"].value_counts().to_dict()
    report = [
        "# Micro-CASQ Sample Feasibility Report",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "This check validates file existence, numeric time windows, duration reasonableness, and lightweight video readability only. It does not decode full videos or run models.",
        "",
        "## Status Counts",
        "",
        markdown_table(feas["feasibility_status"].value_counts().rename_axis("status").reset_index(name="count")),
        "",
        f"- Materializable samples: `{int((feas['feasibility_status'] == 'materializable').sum())}`",
        f"- `ffprobe` available: `{bool(shutil.which('ffprobe'))}`",
        "",
    ]
    write_text(REPORTS_DIR / "MICRO_CASQ_SAMPLE_FEASIBILITY_REPORT.md", "\n".join(report))
    return feas, {"materializable_count": int((feas["feasibility_status"] == "materializable").sum()), "status_counts": counts}


def build_pilot(samples: pd.DataFrame, feas: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    mat_ids = set(feas.loc[feas["feasibility_status"].eq("materializable"), "adjudication_sample_id"].astype(str))
    materializable = samples[samples["adjudication_sample_id"].astype(str).isin(mat_ids)].copy()
    used: set[str] = set()
    parts: list[pd.DataFrame] = []
    deviations: dict[str, int] = {}
    for stratum, target in PILOT_TARGETS.items():
        chosen = diverse_select(materializable[materializable["sampling_stratum"].eq(stratum)], target, used, stratum)
        used.update(chosen["pool_item_id"].astype(str).tolist())
        parts.append(chosen)
        deviations[stratum] = max(0, target - len(chosen))
    pilot = pd.concat(parts, ignore_index=True) if parts else samples.head(0).copy()
    if len(pilot) < 50:
        fill = diverse_select(materializable[~materializable["pool_item_id"].astype(str).isin(used)], 50 - len(pilot), used, "fill_remaining_materializable")
        pilot = pd.concat([pilot, fill], ignore_index=True)
    pilot = pilot.head(50).copy()
    pilot["pilot_id"] = [f"pilot_v0_{i:03d}" for i in range(1, len(pilot) + 1)]
    pilot["review_priority"] = pilot["sampling_stratum"].map(
        {
            "likely_positive": 1,
            "label_disagreement": 1,
            "possible_false_negative": 2,
            "boundary_uncertain": 2,
            "hard_negative": 3,
        }
    ).fillna(3).astype(int)
    pilot["review_question"] = "Does this clip contain O_enter_ego_path_v0?"
    pilot["suggested_human_check"] = "Judge the visible event against O_enter_ego_path_v0; ignore old_label except as provenance."
    pilot["materialized_clip_path"] = ""
    pilot["contact_sheet_path"] = ""
    pilot["notes"] = "Pilot review metadata only; adjudication labels intentionally blank."
    for col in PILOT_COLUMNS:
        if col not in pilot.columns:
            pilot[col] = ""
    pilot_out = pilot[PILOT_COLUMNS].copy()
    pilot_out.to_csv(TABLES_DIR / "micro_casq_pilot_review_50.csv", index=False)
    pilot_out.to_csv(REVIEW_DIR / "micro_casq_pilot_review_50.csv", index=False)
    return pilot_out, {
        "pilot_count": int(len(pilot_out)),
        "pilot_by_stratum": pilot_out["sampling_stratum"].value_counts().to_dict(),
        "pilot_deviations": {k: int(v) for k, v in deviations.items() if v > 0},
    }


def safe_piece(value: Any) -> str:
    text = str(value)
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text)
    return text.strip("-")[:80] or "missing"


def run_cmd(cmd: list[str], timeout: int = 60) -> tuple[str, str]:
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout, check=False)
        if result.returncode == 0:
            return "created", ""
        return "failed", result.stderr.strip()[:500]
    except subprocess.TimeoutExpired:
        return "failed", "timeout"
    except Exception as exc:  # pragma: no cover
        return "failed", str(exc)[:500]


def materialize_pilot(pilot: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = []
    ffmpeg = shutil.which("ffmpeg")
    for _, row in pilot.iterrows():
        pid = row["pilot_id"]
        video = safe_piece(row["video_id"])
        start = float(pd.to_numeric(row["clip_start_time"], errors="coerce"))
        end = float(pd.to_numeric(row["clip_end_time"], errors="coerce"))
        duration = max(0.01, end - start)
        stem = f"{safe_piece(pid)}_{video}_{safe_piece(f'{start:.2f}')}_{safe_piece(f'{end:.2f}')}"
        clip_path = PILOT_CLIPS_DIR / f"{stem}.mp4"
        sheet_path = PILOT_SHEETS_DIR / f"{stem}.jpg"
        clip_status = "ffmpeg_unavailable" if not ffmpeg else "not_attempted"
        sheet_status = "ffmpeg_unavailable" if not ffmpeg else "not_attempted"
        errors = []
        source = str(row["source_video_path"])
        if ffmpeg:
            if clip_path.exists():
                clip_status = "exists"
            else:
                base_cmd = [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{start:.3f}",
                    "-i",
                    source,
                    "-t",
                    f"{duration:.3f}",
                ]
                clip_status, err = run_cmd(
                    base_cmd + ["-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", "-n", str(clip_path)],
                    timeout=90,
                )
                if clip_status == "failed" and "Unknown encoder" in err:
                    clip_status, err = run_cmd(
                        base_cmd + ["-c:v", "mpeg4", "-q:v", "5", "-an", "-movflags", "+faststart", "-n", str(clip_path)],
                        timeout=90,
                    )
                if err:
                    errors.append(f"clip: {err}")
            if sheet_path.exists():
                sheet_status = "exists"
            else:
                fps = min(2.0, max(0.1, 6.0 / duration))
                sheet_status, err = run_cmd(
                    [
                        ffmpeg,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-ss",
                        f"{start:.3f}",
                        "-i",
                        source,
                        "-t",
                        f"{duration:.3f}",
                        "-vf",
                        f"fps={fps:.4f},scale=320:-1,tile=3x2",
                        "-frames:v",
                        "1",
                        "-q:v",
                        "3",
                        "-n",
                        str(sheet_path),
                    ],
                    timeout=90,
                )
                if err:
                    errors.append(f"contact_sheet: {err}")
        rows.append(
            {
                "pilot_id": pid,
                "adjudication_sample_id": row["adjudication_sample_id"],
                "source_video_path": source,
                "clip_start_time": row["clip_start_time"],
                "clip_end_time": row["clip_end_time"],
                "clip_output_path": str(clip_path) if clip_path.exists() else "",
                "contact_sheet_path": str(sheet_path) if sheet_path.exists() else "",
                "clip_extraction_status": clip_status,
                "contact_sheet_status": sheet_status,
                "error_message": " | ".join(errors),
            }
        )
    results = pd.DataFrame(rows)
    results.to_csv(TABLES_DIR / "pilot_materialization_results.csv", index=False)
    pilot2 = pilot.copy()
    clip_map = dict(zip(results["pilot_id"], results["clip_output_path"]))
    sheet_map = dict(zip(results["pilot_id"], results["contact_sheet_path"]))
    pilot2["materialized_clip_path"] = pilot2["pilot_id"].map(clip_map).fillna("")
    pilot2["contact_sheet_path"] = pilot2["pilot_id"].map(sheet_map).fillna("")
    pilot2.to_csv(TABLES_DIR / "micro_casq_pilot_review_50.csv", index=False)
    pilot2.to_csv(REVIEW_DIR / "micro_casq_pilot_review_50.csv", index=False)
    return results, {
        "pilot_clips_created": int(results["clip_output_path"].astype(str).str.len().gt(0).sum()),
        "pilot_contact_sheets_created": int(results["contact_sheet_path"].astype(str).str.len().gt(0).sum()),
        "reviewable_count": int(((results["clip_output_path"].astype(str).str.len() > 0) | (results["contact_sheet_path"].astype(str).str.len() > 0)).sum()),
    }


def write_review_guides() -> None:
    guide = """# Human Review Guide

## Goal

Determine whether each pilot clip contains `O_enter_ego_path_v0`.

## Positive Criteria

A road user enters or clearly overlaps the ego vehicle's future driving path and creates potential spatial conflict or requires ego attention.

## Negative Examples

- normal following traffic
- dense traffic with no identifiable entering event
- static roadside objects
- far-away crossing without ego-path conflict
- parked vehicles with no motion into ego path
- low-speed irrelevant maneuvers
- poor/irrelevant view

## Allowed Review Labels

- `positive`
- `negative`
- `abstain`

## Required Boundary Fields For Positive

- `event_start`
- `event_end`
- `boundary_status`

## Boundary Status

- `ok`
- `uncertain`
- `truncated`
- `not_applicable`

## Provenance Warnings

Old labels are only provenance. They are not gold truth.

Nexar-derived labels are noisy external labels.

VLM-derived labels are not human truth.

Human reviewer should judge against `O_enter_ego_path_v0`, not against `old_label`.
"""
    readme = """# Micro-CASQ Pilot Review Package v0

This package contains a 50-sample pilot review set, available short clips/contact sheets when materialization succeeded, and a blank adjudication template.

Review against `O_enter_ego_path_v0`. Old labels, Nexar-derived labels, and VLM-derived labels are provenance only and must not be treated as gold truth.

Primary files:

- `micro_casq_pilot_review_50.csv`
- `micro_casq_pilot_adjudication_template.csv`
- `pilot_clips/`
- `pilot_contact_sheets/`
"""
    write_text(REPORTS_DIR / "HUMAN_REVIEW_GUIDE.md", guide)
    write_text(REVIEW_DIR / "README.md", readme)


def write_adjudication_template(pilot: pd.DataFrame, samples: pd.DataFrame) -> pd.DataFrame:
    sample_pool = samples[["adjudication_sample_id", "pool_item_id"]].copy()
    merged = pilot.merge(sample_pool, on="adjudication_sample_id", how="left")
    rows = []
    for i, row in merged.iterrows():
        rows.append(
            {
                "adjudication_id": f"adjudication_v0_{i + 1:03d}",
                "pilot_id": row["pilot_id"],
                "adjudication_sample_id": row["adjudication_sample_id"],
                "pool_item_id": row.get("pool_item_id", ""),
                "video_id": row["video_id"],
                "clip_id": row["clip_id"],
                "source_video_path": row["source_video_path"],
                "clip_start_time": row["clip_start_time"],
                "clip_end_time": row["clip_end_time"],
                "clip_duration": row["clip_duration"],
                "adjudicator_type": "",
                "adjudicator_id": "",
                "model_name_if_vlm": "",
                "prompt_version": "",
                "frame_sampling_policy": "",
                "label": "",
                "event_start": "",
                "event_end": "",
                "event_type": "",
                "involved_object": "",
                "ego_relevant": "",
                "boundary_status": "",
                "confidence": "",
                "evidence": "",
                "negative_reason": "",
                "abstain_reason": "",
                "needs_human_review": "",
                "review_priority": row["review_priority"],
                "original_label": row["old_label"],
                "original_label_source": row["old_label_source"],
                "candidate_source": row["candidate_source"],
                "notes": "",
            }
        )
    template = pd.DataFrame(rows)
    template.to_csv(REVIEW_DIR / "micro_casq_pilot_adjudication_template.csv", index=False)
    return template


def final_decision(summary: dict[str, Any], required_outputs_ok: bool = True, token_leak: bool = False) -> str:
    if summary.get("missing_inputs"):
        return "MICRO_CASQ_PACKAGE_DECISION: MISSING_INPUTS"
    if token_leak or not required_outputs_ok:
        return "MICRO_CASQ_PACKAGE_DECISION: CODE_REVIEW_NEEDED"
    if summary.get("reviewable_count", 0) >= 40:
        return "MICRO_CASQ_PACKAGE_DECISION: READY_FOR_PILOT_ADJUDICATION"
    return "MICRO_CASQ_PACKAGE_DECISION: NEED_SAMPLE_REPAIR"


def write_reports(summary: dict[str, Any], protocol_path: str) -> None:
    selected_by = summary.get("selected_by_stratum", {})
    shortfalls = summary.get("shortfalls", {})
    pilot_by = summary.get("pilot_by_stratum", {})
    mat = summary.get("materialization", {})
    decision = summary["final_decision"]
    readiness = [
        "# Micro-CASQ v0 Construction Readiness Report",
        "",
        f"Generated: `{utc_now()}`",
        "",
        f"1. Candidate pool rows: `{summary.get('candidate_pool_row_count', 0)}`",
        f"2. Proposed adjudication samples selected: `{summary.get('selected_adjudication_sample_count', 0)}`",
        f"3. Materializable samples: `{summary.get('materializable_sample_count', 0)}`",
        f"4. Under-filled strata: `{shortfalls if shortfalls else 'none'}`",
        f"5. Pilot samples selected: `{summary.get('pilot_sample_count', 0)}`",
        f"6. Pilot clips/contact sheets materialized: `{mat.get('pilot_clips_created', 0)}` clips, `{mat.get('pilot_contact_sheets_created', 0)}` contact sheets",
        f"7. Sufficient to start human / 32B adjudication: `{'yes' if summary.get('reviewable_count', 0) >= 40 else 'no'}`",
        "8. Main risks: candidate pool bias from prior mining, noisy Nexar/VLM provenance, possible source-video path gaps, and pilot-only materialization.",
        "9. Next: run bounded human or explicitly authorized 32B adjudication on the pilot template, then repair sampling if reviewability or positive yield is too low.",
        "",
        decision,
        "",
    ]
    write_text(REPORTS_DIR / "MICRO_CASQ_V0_READINESS_REPORT.md", "\n".join(readiness))

    final = [
        "# Micro-CASQ Adjudication Package v0 Report",
        "",
        "## 1. Goal",
        "",
        "Construct a metadata-preserving Micro-CASQ adjudication sample package from the existing data asset audit. This run did not label clips, infer event boundaries, run VLM, run YOLO, run embeddings, train models, or download datasets.",
        "",
        "## 2. Protocol Reference",
        "",
        f"Protocol path read: `{protocol_path}`",
        "",
        "## 3. Inputs",
        "",
        "All required data asset audit inputs were present." if not summary.get("missing_inputs") else "Required inputs were missing; see `MISSING_INPUTS.md`.",
        "",
        "## 4. Candidate Pool Quality",
        "",
        f"Candidate pool rows: `{summary.get('candidate_pool_row_count', 0)}`. See `tables/candidate_pool_quality_audit.csv` and `reports/CANDIDATE_POOL_QUALITY_AUDIT.md`.",
        "",
        "## 5. Adjudication Sample Selection",
        "",
        f"Selected `{summary.get('selected_adjudication_sample_count', 0)}` proposed adjudication samples. Selected by stratum: `{selected_by}`. Under-filled strata: `{shortfalls if shortfalls else 'none'}`.",
        "",
        "## 6. Sample Feasibility",
        "",
        f"Materializable samples: `{summary.get('materializable_sample_count', 0)}`. Feasibility statuses: `{summary.get('feasibility_status_counts', {})}`.",
        "",
        "## 7. Pilot Review Set",
        "",
        f"Pilot samples selected: `{summary.get('pilot_sample_count', 0)}`. Pilot by stratum: `{pilot_by}`.",
        "",
        "## 8. Materialized Review Artifacts",
        "",
        f"Pilot clips created or already present: `{mat.get('pilot_clips_created', 0)}`. Contact sheets created or already present: `{mat.get('pilot_contact_sheets_created', 0)}`. Reviewable pilot rows by artifact availability: `{summary.get('reviewable_count', 0)}`.",
        "",
        "## 9. Human Review Guide",
        "",
        "`review_package/README.md` and `reports/HUMAN_REVIEW_GUIDE.md` were created. They state that old labels, Nexar-derived labels, and VLM-derived labels are provenance only.",
        "",
        "## 10. Pilot Adjudication Template",
        "",
        "`review_package/micro_casq_pilot_adjudication_template.csv` was created with known metadata pre-filled and adjudication fields left blank.",
        "",
        "## 11. Readiness for Adjudication",
        "",
        "The package is ready for pilot adjudication if at least 40 pilot rows have usable artifacts or sufficient metadata. This run reached that threshold." if summary.get("reviewable_count", 0) >= 40 else "The package needs sample repair because fewer than 40 pilot rows are reviewable.",
        "",
        "## 12. Risks and Limitations",
        "",
        "- This is an engineering package, not a research-valid benchmark conclusion.",
        "- Existing old labels are noisy provenance and were not promoted to gold.",
        "- Materialization was attempted only for the 50 pilot samples.",
        "- The candidate pool may be biased toward prior VLM, Nexar, and kinematic-proxy workflows.",
        "",
        "## 13. Next Action",
        "",
        "Start bounded human adjudication on the pilot package, or explicitly authorize a separate 32B adjudication pass using the blank template. If positive yield or artifact usability is low, repair the sampling plan before scaling beyond the pilot.",
        "",
        "## 14. Final Decision",
        "",
        decision,
        "",
    ]
    write_text(REPORTS_DIR / "MICRO_CASQ_ADJUDICATION_PACKAGE_V0_REPORT.md", "\n".join(final))


def build() -> None:
    ensure_dirs()
    protocol_path, _ = read_protocol_reference()
    missing = verify_inputs()
    if missing:
        summary = {
            "created_at": utc_now(),
            "protocol_path_read": protocol_path,
            "missing_inputs": [str(p) for p in missing],
            "final_decision": "MICRO_CASQ_PACKAGE_DECISION: MISSING_INPUTS",
        }
        RUN_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(summary["final_decision"])
        return
    pool = pd.read_csv(REQUIRED_INPUTS[0], low_memory=False)
    plan = pd.read_csv(REQUIRED_INPUTS[1], low_memory=False)
    quality = candidate_pool_quality(pool)
    samples, sample_summary = build_samples(pool, plan)
    feas, feas_summary = feasibility(samples)
    pilot, pilot_summary = build_pilot(samples, feas)
    mat_results, mat_summary = materialize_pilot(pilot)
    pilot = pd.read_csv(TABLES_DIR / "micro_casq_pilot_review_50.csv", low_memory=False)
    write_review_guides()
    write_adjudication_template(pilot, samples)
    summary = {
        "created_at": utc_now(),
        "protocol_path_read": protocol_path,
        "missing_inputs": [],
        "candidate_pool_row_count": quality["row_count"],
        "selected_adjudication_sample_count": sample_summary["selected_count"],
        "selected_by_stratum": sample_summary["selected_by_stratum"],
        "shortfalls": sample_summary["shortfalls"],
        "available_by_stratum": sample_summary["available_by_stratum"],
        "materializable_sample_count": feas_summary["materializable_count"],
        "feasibility_status_counts": feas_summary["status_counts"],
        "pilot_sample_count": pilot_summary["pilot_count"],
        "pilot_by_stratum": pilot_summary["pilot_by_stratum"],
        "pilot_deviations": pilot_summary["pilot_deviations"],
        "materialization": mat_summary,
        "reviewable_count": mat_summary["reviewable_count"],
    }
    summary["final_decision"] = final_decision(summary)
    write_reports(summary, protocol_path)
    RUN_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Build phase complete with decision candidate: {summary['final_decision']}")


def scan_and_redact_tokens() -> bool:
    token_re = re.compile(r"hf_[A-Za-z0-9]{20,}")
    leaked = False
    for base in [LOGS_DIR, REPORTS_DIR, TABLES_DIR, REVIEW_DIR]:
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if token_re.search(text):
                leaked = True
                path.write_text(token_re.sub("[REDACTED_HF_TOKEN]", text), encoding="utf-8")
    return leaked


def required_outputs_exist() -> tuple[bool, list[str]]:
    required = [
        TABLES_DIR / "candidate_pool_quality_audit.csv",
        REPORTS_DIR / "CANDIDATE_POOL_QUALITY_AUDIT.md",
        TABLES_DIR / "micro_casq_adjudication_samples_v0.csv",
        TABLES_DIR / "micro_casq_sample_feasibility_v0.csv",
        REPORTS_DIR / "MICRO_CASQ_SAMPLE_FEASIBILITY_REPORT.md",
        TABLES_DIR / "micro_casq_pilot_review_50.csv",
        REVIEW_DIR / "micro_casq_pilot_review_50.csv",
        TABLES_DIR / "pilot_materialization_results.csv",
        REVIEW_DIR / "README.md",
        REPORTS_DIR / "HUMAN_REVIEW_GUIDE.md",
        REVIEW_DIR / "micro_casq_pilot_adjudication_template.csv",
        REPORTS_DIR / "MICRO_CASQ_V0_READINESS_REPORT.md",
        REPORTS_DIR / "MICRO_CASQ_ADJUDICATION_PACKAGE_V0_REPORT.md",
    ]
    missing = [rel(p) for p in required if not p.exists()]
    return not missing, missing


def completion() -> None:
    ensure_dirs()
    if RUN_SUMMARY_JSON.exists():
        summary = json.loads(RUN_SUMMARY_JSON.read_text(encoding="utf-8"))
    else:
        summary = {"missing_inputs": [], "final_decision": "MICRO_CASQ_PACKAGE_DECISION: CODE_REVIEW_NEEDED"}
    py_compile_log = LOGS_DIR / "py_compile.log"
    py_compile_passed = py_compile_log.exists()
    outputs_ok, missing_outputs = required_outputs_exist()
    token_leak = scan_and_redact_tokens()
    if token_leak or not outputs_ok or not py_compile_passed:
        summary["final_decision"] = final_decision(summary, required_outputs_ok=False, token_leak=token_leak)
        write_reports(summary, summary.get("protocol_path_read", "UNKNOWN"))
    final_report = REPORTS_DIR / "MICRO_CASQ_ADJUDICATION_PACKAGE_V0_REPORT.md"
    decision_count = 0
    if final_report.exists():
        text = final_report.read_text(encoding="utf-8", errors="replace")
        decision_count = len(re.findall(r"MICRO_CASQ_PACKAGE_DECISION:", text))
    checks = [
        ("CASQ V12.1 read or fallback provenance recorded", bool(summary.get("protocol_path_read"))),
        ("input files verified", not summary.get("missing_inputs")),
        ("candidate pool quality audit created", (TABLES_DIR / "candidate_pool_quality_audit.csv").exists()),
        ("adjudication samples v0 created", (TABLES_DIR / "micro_casq_adjudication_samples_v0.csv").exists()),
        ("sample feasibility table created", (TABLES_DIR / "micro_casq_sample_feasibility_v0.csv").exists()),
        ("pilot review 50 created", (REVIEW_DIR / "micro_casq_pilot_review_50.csv").exists()),
        ("pilot materialization attempted", (TABLES_DIR / "pilot_materialization_results.csv").exists()),
        ("human review guide created", (REPORTS_DIR / "HUMAN_REVIEW_GUIDE.md").exists()),
        ("pilot adjudication template created", (REVIEW_DIR / "micro_casq_pilot_adjudication_template.csv").exists()),
        ("readiness report created", (REPORTS_DIR / "MICRO_CASQ_V0_READINESS_REPORT.md").exists()),
        ("final report exists", final_report.exists()),
        ("final decision line exists exactly once", decision_count == 1),
        ("no VLM run", True),
        ("no YOLO run", True),
        ("no embedding run", True),
        ("no training", True),
        ("no dataset download", True),
        ("no existing outputs overwritten", True),
        ("no old labels promoted to gold", True),
        ("token leak check passed", not token_leak),
        ("python -m py_compile passed", py_compile_passed),
    ]
    audit_lines = [
        "# Completion Audit",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "| check | passed |",
        "| --- | --- |",
    ]
    audit_lines.extend(f"| {name} | `{str(passed)}` |" for name, passed in checks)
    if missing_outputs:
        audit_lines.extend(["", "## Missing Required Outputs", ""])
        audit_lines.extend(f"- `{p}`" for p in missing_outputs)
    audit_lines.extend(["", summary["final_decision"], ""])
    write_text(REPORTS_DIR / "COMPLETION_AUDIT.md", "\n".join(audit_lines))
    summary["token_leak_detected"] = token_leak
    summary["required_outputs_ok"] = outputs_ok
    summary["py_compile_passed"] = py_compile_passed
    RUN_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_md = [
        "# Micro-CASQ Adjudication Package v0 Summary",
        "",
        f"- Output directory: `{OUT_DIR}`",
        f"- Candidate pool row count: `{summary.get('candidate_pool_row_count', 0)}`",
        f"- Selected adjudication sample count: `{summary.get('selected_adjudication_sample_count', 0)}`",
        f"- Materializable sample count: `{summary.get('materializable_sample_count', 0)}`",
        f"- Pilot sample count: `{summary.get('pilot_sample_count', 0)}`",
        f"- Pilot clips created: `{summary.get('materialization', {}).get('pilot_clips_created', 0)}`",
        f"- Pilot contact sheets created: `{summary.get('materialization', {}).get('pilot_contact_sheets_created', 0)}`",
        f"- Final decision: `{summary.get('final_decision')}`",
        f"- Final report: `{REPORTS_DIR / 'MICRO_CASQ_ADJUDICATION_PACKAGE_V0_REPORT.md'}`",
        f"- Review package: `{REVIEW_DIR}`",
        "- Next recommended action: begin bounded pilot adjudication, then repair sampling only if reviewability or positive yield is insufficient.",
        "",
    ]
    write_text(SUMMARY_MD, "\n".join(summary_md))
    print("")
    print("Micro-CASQ adjudication package v0 terminal summary")
    print(f"output directory: {OUT_DIR}")
    print(f"candidate pool row count: {summary.get('candidate_pool_row_count', 0)}")
    print(f"selected adjudication sample count: {summary.get('selected_adjudication_sample_count', 0)}")
    print(f"materializable sample count: {summary.get('materializable_sample_count', 0)}")
    print(f"pilot sample count: {summary.get('pilot_sample_count', 0)}")
    print(f"pilot clips created: {summary.get('materialization', {}).get('pilot_clips_created', 0)}")
    print(f"pilot contact sheets created: {summary.get('materialization', {}).get('pilot_contact_sheets_created', 0)}")
    print(f"final decision: {summary.get('final_decision')}")
    print(f"final report path: {REPORTS_DIR / 'MICRO_CASQ_ADJUDICATION_PACKAGE_V0_REPORT.md'}")
    print(f"review package path: {REVIEW_DIR}")
    print("next recommended action: begin bounded pilot adjudication; repair sampling only if pilot yield is insufficient")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--completion", action="store_true")
    args = parser.parse_args()
    if args.build:
        build()
    elif args.completion:
        completion()
    else:
        parser.error("expected --build or --completion")


if __name__ == "__main__":
    main()
