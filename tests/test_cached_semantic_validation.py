from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


SCRIPT = Path(__file__).parents[1] / "experiments" / "cached_semantic_validation.py"
SPEC = importlib.util.spec_from_file_location("cached_semantic_validation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_wilson_gate_rejects_apparent_but_unsupported_precision():
    threshold = MODULE.choose_risk_threshold(
        [0.99, 0.98, 0.97, 0.96, 0.95, 0.94, 0.93, 0.92, 0.91, 0.90],
        [1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
        precision_floor=0.80,
        minimum_admissions=10,
    )
    assert threshold is None


def test_risk_threshold_maximizes_safe_training_coverage():
    threshold = MODULE.choose_risk_threshold(
        [0.99] * 20 + [0.50] * 20,
        [1] * 20 + [0] * 20,
        precision_floor=0.80,
        minimum_admissions=10,
    )
    assert threshold is not None
    assert threshold.admitted_count == 20
    assert threshold.empirical_precision == 1.0
    assert threshold.wilson_lower_95 >= 0.80


def test_one_to_one_matching_penalizes_duplicate_event_hypotheses():
    adjacency = {
        "candidate_a": ("reference_0",),
        "candidate_b": ("reference_0",),
        "candidate_c": ("reference_1",),
    }
    metrics = MODULE.publication_metrics(
        ["candidate_a", "candidate_b", "candidate_c"],
        adjacency,
        reference_count=2,
    )
    assert metrics["matched_reference_events"] == 2
    assert metrics["false_or_duplicate_events"] == 1
    assert metrics["event_precision"] == 2 / 3
    assert metrics["event_recall"] == 1.0


def test_probable_publication_increases_anytime_auc_when_it_is_true():
    adjacency = {"probable": ("reference_0",), "verify": ("reference_1",)}
    baseline = MODULE.verified_prefix_metrics(
        ["probable", "verify"],
        adjacency,
        probable_candidates=(),
        reference_count=2,
        budget=2,
    )
    speculative = MODULE.verified_prefix_metrics(
        ["probable", "verify"],
        adjacency,
        probable_candidates=("probable",),
        reference_count=2,
        budget=2,
    )
    assert speculative["event_recall"] == baseline["event_recall"]
    assert speculative["anytime_event_recall_auc"] > baseline["anytime_event_recall_auc"]
