"""Adapter to run SUPG methods on a CSV / DataFrame with id, label, proxy_score columns.

Wraps the refe_repos/supg core classes without modifying them.
If the editable install has import issues, falls back to sys.path insertion.
"""

import sys
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Ensure supg is importable — try installed first, fallback to sys.path
try:
    from supg.datasource import DataSource, DFDataSource, load_csv_source
    from supg.sampler import ImportanceSampler
    from supg.selector import ApproxQuery, RecallSelector, ImportancePrecisionTwoStageSelector
except ImportError:
    _supg_root = str(Path(__file__).resolve().parents[2] / "refe_repos" / "supg")
    if _supg_root not in sys.path:
        sys.path.insert(0, _supg_root)
    from supg.datasource import DataSource, DFDataSource, load_csv_source
    from supg.sampler import ImportanceSampler
    from supg.selector import ApproxQuery, RecallSelector, ImportancePrecisionTwoStageSelector


def _prepare_source(csv_path: str | None = None, df: pd.DataFrame | None = None) -> tuple[DataSource, pd.DataFrame]:
    """Load data into a SUPG DFDataSource."""
    if df is None and csv_path is not None:
        df = pd.read_csv(csv_path)
    if df is None:
        raise ValueError("Must provide either csv_path or df")
    df = df.copy()
    df["label"] = df["label"].astype("float32")
    source = DFDataSource(df)
    return source, df


def run_supg_rt(
    csv_path: str | None = None,
    df: pd.DataFrame | None = None,
    budget: int = 10000,
    gamma: float = 0.9,
    delta: float = 0.05,
    seed: int | None = None,
) -> dict:
    """Run SUPG recall-target selector.

    Returns dict with: selected_ids, sampled_ids, metadata.
    """
    source, raw_df = _prepare_source(csv_path, df)
    sampler = ImportanceSampler(seed=seed if seed is not None else 0)
    query = ApproxQuery(
        qtype="rt",
        min_recall=gamma,
        delta=delta,
        budget=budget,
    )
    selector = RecallSelector(query, source, sampler, sample_mode="sqrt", verbose=False)
    selected_ids = selector.select()

    sampled_ids = None
    if hasattr(selector, "sampled") and selector.sampled is not None:
        sampled_ids = selector.sampled

    return {
        "selected_ids": selected_ids,
        "sampled_ids": sampled_ids,
        "metadata": {
            "method": "SUPG-RT",
            "qtype": "rt",
            "budget": budget,
            "gamma": gamma,
            "delta": delta,
            "seed": seed,
        },
    }


def run_supg_pt(
    csv_path: str | None = None,
    df: pd.DataFrame | None = None,
    budget: int = 10000,
    gamma: float = 0.9,
    delta: float = 0.05,
    seed: int | None = None,
) -> dict:
    """Run SUPG precision-target two-stage selector.

    Returns dict with: selected_ids, sampled_ids, metadata.
    """
    source, raw_df = _prepare_source(csv_path, df)
    sampler = ImportanceSampler(seed=seed if seed is not None else 0)
    query = ApproxQuery(
        qtype="pt",
        min_precision=gamma,
        delta=delta,
        budget=budget,
    )
    selector = ImportancePrecisionTwoStageSelector(query, source, sampler)
    selected_ids = selector.select()

    sampled_ids = None
    if hasattr(selector, "sampled") and selector.sampled is not None:
        sampled_ids = selector.sampled

    return {
        "selected_ids": selected_ids,
        "sampled_ids": sampled_ids,
        "metadata": {
            "method": "SUPG-PT",
            "qtype": "pt",
            "budget": budget,
            "gamma": gamma,
            "delta": delta,
            "seed": seed,
        },
    }
