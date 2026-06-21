#!/usr/bin/env python3
"""Shared helpers for Phase 0 diagnostics.

This directory performs read-only re-analysis of already produced Phase 0
outputs. It does not call VLMs, collect data, or modify the Phase 0 inputs.
"""

from __future__ import annotations

import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
PHASE0_DIR = PROJECT_ROOT / "test_vlm/outputs/clip_aqp_phase0_v1"
DIAG_DIR = PHASE0_DIR / "diagnostics_v1"
MANDATED_POWER_SENTENCE = (
    "Sample size insufficient for robust GVR estimation; results indicate direction only "
    "and must not be treated as sufficient evidence for GO/NO_GO."
)


def ensure_dirs() -> None:
    for name in ["scripts", "tables", "reports", "logs", "config", "data_manifest", "figures"]:
        (DIAG_DIR / name).mkdir(parents=True, exist_ok=True)


def read_phase0_csv(rel: str) -> pd.DataFrame:
    return pd.read_csv(PHASE0_DIR / rel)


def read_phase0_text(rel: str) -> str:
    return (PHASE0_DIR / rel).read_text(encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_progress(checkpoint: str, command: str, result: str, failure: str = "", fix: str = "", next_action: str = "") -> None:
    ensure_dirs()
    path = DIAG_DIR / "logs/progress.md"
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


def git_status_for(paths: list[str]) -> str:
    try:
        out = subprocess.check_output(["git", "status", "--short", "--", *paths], cwd=PROJECT_ROOT, text=True)
    except Exception as exc:
        return f"git status unavailable: {exc!r}"
    return out.strip()


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
                if math.isnan(value):
                    vals.append("")
                else:
                    vals.append(f"{value:.4g}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_manifest() -> None:
    ensure_dirs()
    rows = []
    for rel in [
        "reports/PHASE0_REPORT.md",
        "logs/run_phase0.log",
        "tables/block_audit_no_repair_results.csv",
        "tables/block_audit_repair_fresh_cert_results.csv",
        "tables/oracle_stability.csv",
        "tables/supg_stitch_results.csv",
        "tables/supg_stitch_summary.csv",
        "data_audit/phase0_units.csv",
        "data_audit/phase0_pseudo_events.csv",
    ]:
        path = PHASE0_DIR / rel
        rows.append({"input": rel, "exists": path.exists(), "bytes": path.stat().st_size if path.exists() else 0})
    pd.DataFrame(rows).to_csv(DIAG_DIR / "data_manifest/diagnostic_inputs.csv", index=False)
