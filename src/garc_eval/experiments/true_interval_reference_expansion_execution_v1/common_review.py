from __future__ import annotations

import csv
import html
import math
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
EXP = "true_interval_reference_expansion_execution_v1"
OUT = ROOT / "src/garc_eval/outputs" / EXP
SCRIPT_DIR = ROOT / "src/garc_eval/experiments" / EXP
MEDIA_DIR = OUT / "review_media"

SQ = ROOT / "src/garc_eval/outputs/sq_craq_next_stage_goal_v1"
SQ_REF = SQ / "true_interval_reference_expansion_v1"
SQ_ENV = SQ / "audited_interval_envelope_mvp_v1"
REF_DUR = ROOT / "src/garc_eval/outputs/reference_duration_stratified_eval_v1"
V2 = ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak"
SMOKE = ROOT / "src/garc_eval/outputs/cils_calibration_repair_smoke_v1"
TIEBREAK = ROOT / "src/garc_eval/outputs/within_bin_tiebreak_ablation_v1"
SYN = ROOT / "src/garc_eval/outputs/synthetic_cheap_signal_downstream_validation_v1"

REQUESTED_VIDEO = ROOT / "try_or_no/videos/realcartest.mp4"
FALLBACK_VIDEO = ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"

TARGET_QUEUE_SIZE = 120


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    for p in [
        OUT,
        OUT / "config",
        OUT / "data_manifest",
        OUT / "logs",
        OUT / "reports",
        OUT / "tables",
        OUT / "figures",
        OUT / "scripts",
        MEDIA_DIR,
        MEDIA_DIR / "clips",
        MEDIA_DIR / "sheets",
        MEDIA_DIR / "centers",
    ]:
        p.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_df(df: pd.DataFrame, path: Path, mirror_table: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    if mirror_table and path.parent == OUT:
        (OUT / "tables").mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT / "tables" / path.name, index=False)


def append_progress(checkpoint: str, result: str, command: str = "", failure: str = "", next_action: str = "") -> None:
    path = OUT / "logs/progress.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("# Progress\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"- {ts()} | checkpoint={checkpoint} | command={command or 'n/a'} | result={result} | failure={failure or 'none'} | next={next_action or 'n/a'}\n")


def md_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df is None or df.empty:
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


def safe_float(x, default: float = 0.0) -> float:
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


def temporal_iou(a0: float, a1: float, b0: float, b1: float) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    return inter / union if union > 0 else 0.0


def normalize(s: pd.Series) -> pd.Series:
    v = pd.to_numeric(s, errors="coerce").fillna(0.0).astype(float)
    lo, hi = float(v.min()), float(v.max())
    if hi <= lo:
        return pd.Series(np.zeros(len(v)), index=v.index)
    return (v - lo) / (hi - lo)


def csv_info(path: Path) -> tuple[int | None, str]:
    if not path.exists() or path.suffix.lower() != ".csv":
        return None, ""
    try:
        rows = max(0, sum(1 for _ in path.open("r", encoding="utf-8", errors="replace")) - 1)
        cols = ",".join(pd.read_csv(path, nrows=0).columns.tolist())
        return rows, cols
    except Exception as exc:  # noqa: BLE001
        return None, f"READ_ERROR:{exc}"


def input_inventory() -> pd.DataFrame:
    paths = [
        SQ / "FINAL_HANDOFF.md",
        SQ_REF / "true_interval_review_queue.csv",
        SQ_ENV / "envelope_candidates.csv",
        SQ_ENV / "envelope_repair_trace.csv",
        REF_DUR / "event_duration_strata.csv",
        REF_DUR / "event_failure_types.csv",
        V2 / "reference_events.csv",
        V2 / "interval_lattice_v2_clean.csv",
        V2 / "interval_labels_v2_clean.csv",
        SMOKE / "smoke_selected_intervals.csv",
        TIEBREAK / "top_p_answer_bin_candidates.csv",
        TIEBREAK / "single_feature_tiebreak_results.csv",
        SYN / "predictions_cils_synthetic_downstream.csv",
        SYN / "predictions_synthetic_score_topk.csv",
        REQUESTED_VIDEO,
        FALLBACK_VIDEO,
    ]
    rows = []
    for p in paths:
        n, cols = csv_info(p)
        rows.append(
            {
                "path": str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
                "exists": p.exists(),
                "row_count_if_csv": n,
                "column_names_if_csv": cols,
                "role": role_for_path(p),
                "limitations": "Read-only input. Missing optional files are recorded and nearest available artifacts are used.",
            }
        )
    return pd.DataFrame(rows)


def role_for_path(path: Path) -> str:
    name = path.name
    if name == "realcartest.mp4":
        return "requested full video path"
    if name == "long_video_dataset3.mp4":
        return "fallback corresponding full video candidate"
    if name == "true_interval_review_queue.csv":
        return "prior generated review queue source"
    if name == "event_duration_strata.csv":
        return "optional duration strata source"
    if name == "top_p_answer_bin_candidates.csv":
        return "top-bin high-score / false-positive source"
    if name == "smoke_selected_intervals.csv":
        return "selected interval source"
    if name == "envelope_candidates.csv":
        return "audited-envelope candidate source"
    if name == "reference_events.csv":
        return "current VLM-defined reference event source"
    if name == "interval_lattice_v2_clean.csv":
        return "dense interval lattice candidate source"
    return "context/input artifact"


def reference_events() -> pd.DataFrame:
    ref = pd.read_csv(V2 / "reference_events.csv").copy()
    ref["duration"] = pd.to_numeric(ref["duration"], errors="coerce").fillna(ref["t_end"] - ref["t_start"])
    ref["duration_stratum"] = np.where(ref["duration"] <= 2.0, "point_anchor", np.where(ref["duration"] >= 5.0, "true_interval", "ambiguous"))
    ref["keep_for_interval_eval_existing"] = ref["duration_stratum"].eq("true_interval")
    return ref


def absolute_offset_seconds() -> float:
    ref = reference_events()
    if "absolute_t_start" in ref.columns:
        diffs = pd.to_numeric(ref["absolute_t_start"], errors="coerce") - pd.to_numeric(ref["t_start"], errors="coerce")
        diffs = diffs.dropna()
        if not diffs.empty:
            return float(diffs.median())
    return 0.0


def video_source() -> tuple[Path | None, str, float]:
    if REQUESTED_VIDEO.exists():
        return REQUESTED_VIDEO, "requested_realcartest_path", 0.0
    if FALLBACK_VIDEO.exists():
        return FALLBACK_VIDEO, "fallback_long_video_dataset3_with_reference_absolute_offset", absolute_offset_seconds()
    return None, "missing", 0.0


def ffprobe_duration(path: Path | None) -> float | None:
    if path is None or not path.exists():
        return None
    try:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return float(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None
    except Exception:
        return None


def minimal_xlsx(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    """Write a small XLSX workbook using only the standard library."""

    def col_name(idx: int) -> str:
        name = ""
        idx += 1
        while idx:
            idx, rem = divmod(idx - 1, 26)
            name = chr(65 + rem) + name
        return name

    sheet_items = list(sheets.items())
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
""" + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheet_items) + 1)) + "\n</Types>")
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        z.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
""" + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheet_items) + 1)) + "\n</Relationships>")
        z.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>
""" + "".join(f'<sheet name="{html.escape(name[:31])}" sheetId="{i}" r:id="rId{i}"/>' for i, (name, _) in enumerate(sheet_items, 1)) + "\n</sheets></workbook>")
        for si, (_, df) in enumerate(sheet_items, 1):
            rows_xml = []
            d = df.fillna("").astype(str)
            values = [list(d.columns)] + d.values.tolist()
            for ri, row in enumerate(values, 1):
                cells = []
                for ci, value in enumerate(row):
                    ref = f"{col_name(ci)}{ri}"
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{html.escape(str(value))}</t></is></c>')
                rows_xml.append(f'<row r="{ri}">' + "".join(cells) + "</row>")
            z.writestr(f"xl/worksheets/sheet{si}.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
""" + "\n".join(rows_xml) + "\n</sheetData></worksheet>")


def legal_values_report() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"field": "human_event_type", "allowed_values": "cut_in;near_conflict;abnormal_vehicle_interaction;pedestrian_crossing;cyclist_crossing;blocked;overtaking;being_overtaken;other;negative;ambiguous"},
            {"field": "human_is_true_interval", "allowed_values": "yes;no;review"},
            {"field": "human_is_point_anchor", "allowed_values": "yes;no;review"},
            {"field": "human_is_negative", "allowed_values": "yes;no;review"},
            {"field": "boundary_confidence", "allowed_values": "high;medium;low;review"},
            {"field": "keep_for_interval_eval", "allowed_values": "yes;no;review"},
        ]
    )
