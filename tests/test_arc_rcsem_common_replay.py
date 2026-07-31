from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).parents[1] / "experiments" / "arc_rcsem_common_replay.py"
SPEC = importlib.util.spec_from_file_location("arc_rcsem_common_replay", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_wilson_gate_is_conservative_for_small_apparent_perfect_set():
    assert MODULE.wilson_lower(9, 9) < 0.80
    assert MODULE.wilson_lower(20, 20) >= 0.80


def test_ranking_rejects_evaluator_label_column():
    frame = pd.DataFrame(
        {"unit_id": [0, 1], "posterior_score": [0.1, 0.9], "oracle_label": ["negative", "positive"]}
    )
    with pytest.raises(ValueError, match="leaked"):
        MODULE.label_hidden_ranking(frame)


def test_ranking_is_deterministic_and_uses_unit_id_tie_break():
    frame = pd.DataFrame(
        {"unit_id": [3, 1, 2], "posterior_score": [0.8, 0.8, 0.9], "proxy_score": [0.2, 0.3, 0.4]}
    )
    assert MODULE.label_hidden_ranking(frame) == [2, 1, 3]


def test_reveal_trace_matches_arc_schema_and_exact_budget():
    domain = MODULE.Domain(
        name="toy",
        dataset="toy",
        video_id="toy",
        units=pd.DataFrame(
            {"benchmark_id": ["b"] * 3, "video_id": ["v"] * 3, "unit_id": [0, 1, 2], "start_time": [0, 10, 20], "end_time": [10, 20, 30]}
        ),
        proxy=pd.DataFrame({"unit_id": [0, 1, 2], "proxy_score": [0.2, 0.8, 0.5]}),
        oracle=pd.DataFrame({"unit_id": [0, 1, 2], "oracle_label": ["negative", "positive", "negative"]}),
        reference=pd.DataFrame(),
        hashes={},
    )
    trace = MODULE.reveal_trace(domain, [1, 2, 0], 2)
    assert list(trace.columns) == MODULE.TRACE_COLUMNS
    assert trace.unit_id.tolist() == [1, 2]
    assert trace.oracle_label_after_query.tolist() == ["positive", "negative"]
    assert trace.oracle_accessed_only_after_selection.all()


def test_reveal_trace_forbids_duplicate_attempts():
    domain = MODULE.Domain(
        name="toy",
        dataset="toy",
        video_id="toy",
        units=pd.DataFrame({"benchmark_id": ["b"], "unit_id": [0]}),
        proxy=pd.DataFrame({"unit_id": [0], "proxy_score": [0.2]}),
        oracle=pd.DataFrame({"unit_id": [0], "oracle_label": ["negative"]}),
        reference=pd.DataFrame(),
        hashes={},
    )
    with pytest.raises(RuntimeError, match="unique"):
        MODULE.reveal_trace(domain, [0, 0], 2)
