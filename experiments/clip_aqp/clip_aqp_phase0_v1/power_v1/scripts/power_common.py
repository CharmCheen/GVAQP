#!/usr/bin/env python3
"""Shared utilities for Phase 0.6 power/scaling simulation."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
REPAIR_DIR = PROJECT_ROOT / "test_vlm/outputs/clip_aqp_phase0_v1/repair_v1"
POWER_DIR = PROJECT_ROOT / "test_vlm/outputs/clip_aqp_phase0_v1/power_v1"

ROWS_CSV = REPAIR_DIR / "tables/block_audit_rows_v2.csv"
RESULTS_CSV = REPAIR_DIR / "tables/block_audit_no_repair_results_v2.csv"
REPAIR_REPORT = REPAIR_DIR / "reports/PHASE0_REPORT_v2.md"
ROOT_CAUSE = REPAIR_DIR / "reports/ROOT_CAUSE.md"

TARGET_EVENT_COUNTS = [50, 100, 200, 500, 1000, 2000]
NUM_TRIALS = 200
BOOTSTRAP_REPS = 80
CERT_SAMPLE_FRAC = 0.35
REFERENCE_THETA = 0.3
REFERENCE_BLOCK_SIZE = 10.0
REFERENCE_GAMMA = 0.8
REFERENCE_DELTA = 0.10
RANDOM_SEED = 20260306
EPSILON = 1e-9
MODES = ["certified_srs", "stratified_by_video", "bootstrap_diagnostic"]


def ensure_dirs() -> None:
    for name in ["scripts", "tables", "figures", "reports", "logs", "config", "data_manifest"]:
        (POWER_DIR / name).mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_progress(checkpoint: str, command: str, result: str, failure: str = "", fix: str = "", next_action: str = "") -> None:
    ensure_dirs()
    with (POWER_DIR / "logs/progress.md").open("a", encoding="utf-8") as f:
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


def certified_bound_from_values(y_vals: np.ndarray, m_vals: np.ndarray, population_n: int, delta: float) -> dict:
    n = len(y_vals)
    if n <= 0 or population_n <= 0:
        return {
            "Y_hat_O": math.nan,
            "M_hat_O": math.nan,
            "LCB_Y_O": math.nan,
            "UCB_M_O": math.nan,
            "LCB_recall_O": 0.0,
            "Y_margin": math.nan,
            "M_margin": math.nan,
        }
    z = normal_quantile(delta)
    fpc = math.sqrt(max(0.0, 1.0 - n / max(population_n, 1))) if population_n > 1 else 0.0
    y_hat = population_n * float(np.mean(y_vals))
    m_hat = population_n * float(np.mean(m_vals))
    y_se_total = population_n * (float(np.std(y_vals, ddof=1)) / math.sqrt(n) * fpc if n > 1 else 0.0)
    m_se_total = population_n * (float(np.std(m_vals, ddof=1)) / math.sqrt(n) * fpc if n > 1 else 0.0)
    lcb_y = max(0.0, y_hat - z * y_se_total)
    ucb_m = max(m_hat, m_hat + z * m_se_total)
    if ucb_m < m_hat - EPSILON or lcb_y > y_hat + EPSILON:
        raise AssertionError(f"bound invariant failed: UCB_M={ucb_m} M_hat={m_hat} LCB_Y={lcb_y} Y_hat={y_hat}")
    lcb = 0.0 if lcb_y <= 0 else max(0.0, min(1.0, 1.0 - ucb_m / lcb_y))
    return {
        "Y_hat_O": y_hat,
        "M_hat_O": m_hat,
        "LCB_Y_O": lcb_y,
        "UCB_M_O": ucb_m,
        "LCB_recall_O": lcb,
        "Y_margin": y_hat - lcb_y,
        "M_margin": ucb_m - m_hat,
    }


def stratified_bound(pop: pd.DataFrame, sample_idx: np.ndarray, delta: float, strata_col: str = "video_id") -> dict:
    sample = pop.iloc[sample_idx].copy()
    z = normal_quantile(delta)
    y_hat = 0.0
    m_hat = 0.0
    y_var_total = 0.0
    m_var_total = 0.0
    for stratum, group in pop.groupby(strata_col, sort=False):
        N_h = len(group)
        s_h = sample[sample[strata_col] == stratum]
        n_h = len(s_h)
        if n_h == 0:
            continue
        y = s_h["Y_i_O"].to_numpy(dtype=float)
        m = s_h["M_i_O"].to_numpy(dtype=float)
        y_hat += N_h * float(np.mean(y))
        m_hat += N_h * float(np.mean(m))
        fpc = max(0.0, 1.0 - n_h / max(N_h, 1))
        if n_h > 1:
            y_var_total += (N_h**2) * fpc * float(np.var(y, ddof=1)) / n_h
            m_var_total += (N_h**2) * fpc * float(np.var(m, ddof=1)) / n_h
    lcb_y = max(0.0, y_hat - z * math.sqrt(max(0.0, y_var_total)))
    ucb_m = max(m_hat, m_hat + z * math.sqrt(max(0.0, m_var_total)))
    if ucb_m < m_hat - EPSILON or lcb_y > y_hat + EPSILON:
        raise AssertionError("stratified bound invariant failed")
    lcb = 0.0 if lcb_y <= 0 else max(0.0, min(1.0, 1.0 - ucb_m / lcb_y))
    return {"Y_hat_O": y_hat, "M_hat_O": m_hat, "LCB_Y_O": lcb_y, "UCB_M_O": ucb_m, "LCB_recall_O": lcb}


def practical_bootstrap_lcb(y_vals: np.ndarray, m_vals: np.ndarray, population_n: int, rng: np.random.Generator, reps: int = BOOTSTRAP_REPS) -> float:
    if len(y_vals) == 0 or float(np.sum(y_vals)) <= 0:
        return 0.0
    recalls = []
    n = len(y_vals)
    for _ in range(reps):
        idx = rng.integers(0, n, size=n)
        y_hat = population_n * float(np.mean(y_vals[idx]))
        m_hat = population_n * float(np.mean(m_vals[idx]))
        recalls.append(0.0 if y_hat <= 0 else max(0.0, min(1.0, 1.0 - m_hat / y_hat)))
    return float(np.quantile(recalls, 0.05))


def markdown_table(df: pd.DataFrame, max_rows: int = 60) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows)
    cols = list(view.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in view.iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if isinstance(val, float):
                vals.append("" if math.isnan(val) else f"{val:.4g}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def load_repair_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_csv(ROWS_CSV), pd.read_csv(RESULTS_CSV)
