#!/usr/bin/env python3
"""ERAEA gate tests (CPU-only, no inference)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/eraea_cpu_novelty_gate"))
sys.path.insert(0, str(ROOT / "scripts/mab_cpu_gate"))
GATE = ROOT / "outputs/eraea_cpu_novelty_gate_v1"


@pytest.fixture(scope="module")
def matrix():
    p = GATE / "BASELINE_MATRIX.csv"
    if not p.exists():
        pytest.skip("BASELINE_MATRIX.csv not built")
    return pd.read_csv(p)


def test_matrix_covers_required_policies(matrix):
    required = {"uniform", "stratified", "top_proxy", "temporal_coverage",
                "new_component", "mmr", "facility", "exsample", "seiden_ucb",
                "relation_greedy", "relation_ts", "yield_ts", "oracle1", "oracle2"}
    assert required <= set(matrix["policy"])


def test_matrix_full_budgets_per_cluster(matrix):
    counts = matrix.groupby(["video_id", "policy"])["budget"].nunique()
    assert (counts == 6).all()


def test_mmr_matches_top_proxy_when_scores_dominate(matrix):
    """Frozen MMR formula must not systematically beat top_proxy beyond the
    P2-established 'essentially tied' relation."""
    mmr = matrix[matrix["policy"] == "mmr"].groupby("video_id")["eventf1_auc"].mean()
    top = matrix[matrix["policy"] == "top_proxy"].groupby("video_id")["eventf1_auc"].mean()
    assert (mmr - top).abs().max() < 0.005


def test_equal_yield_pairs_constraints():
    p = GATE / "EQUAL_YIELD_PAIRS.parquet"
    if not p.exists():
        pytest.skip("EQUAL_YIELD_PAIRS.parquet not built")
    pairs = pd.read_parquet(p)
    assert ((pairs["yield_i"] - pairs["yield_j"]).abs() <= 1).all()
    cov_max = pairs[["coverage_i", "coverage_j"]].max(axis=1)
    rel = ((pairs["coverage_i"] - pairs["coverage_j"]).abs() /
           cov_max.replace(0, float("nan")))
    rel = rel.fillna(0.0)  # both zero coverage -> relative diff = 0
    assert (rel <= 0.05 + 1e-9).all()


def test_reward_terms_identical_property():
    d = pd.read_csv(GATE / "MATERIALIZER_DECOUPLING.csv")
    e3 = d[d["reward"].notna()]
    piv = e3.pivot_table(index=["video_id", "budget"], columns="reward", values="eventf1_auc")
    for pair in (("R1", "R2"), ("R2", "R3"), ("R3", "R4")):
        assert (piv[pair[0]] == piv[pair[1]]).all(), f"{pair} should be identical"


def test_deviation_audit_exists():
    p = GATE / "DEVIATION_AUDIT.parquet"
    if not p.exists():
        pytest.skip("DEVIATION_AUDIT.parquet not built")
    dev = pd.read_parquet(p)
    assert set(dev["class"]).issubset({"BENEFICIAL", "HARMFUL", "INDIFFERENT"})
