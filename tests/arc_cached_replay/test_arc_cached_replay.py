from __future__ import annotations

import contextlib
import importlib.util
import inspect
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from garc_eval.arc_cached_replay import (
    ARCConfig,
    ARCSelector,
    FrozenOracle,
    OracleAccessError,
    sequential_js_clusters,
)


REPO = Path(__file__).resolve().parents[2]
FROZEN = REPO / "BSEC_AQP_Development_Gate_v1" / "outputs" / "native_arc_vs_pstr"
BENCHMARK_LIB = (
    REPO
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run"
    / "clean_baseline_benchmark_v2_strict"
    / "scripts"
    / "benchmark_lib.py"
)


def _load_benchmark_lib():
    spec = importlib.util.spec_from_file_location("arc_replay_test_benchmark_lib", BENCHMARK_LIB)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BENCH = _load_benchmark_lib()


def _simple_units(count: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "benchmark_id": "synthetic",
            "video_id": "v",
            "unit_id": range(count),
            "start_time": np.arange(count, dtype=float) * 10.0,
            "end_time": (np.arange(count, dtype=float) + 1.0) * 10.0,
        }
    )


def _meta() -> dict[str, object]:
    return {
        "benchmark_id": "synthetic",
        "run_id": "same_trace",
        "method": "ARC-CACHED-REPLAY-v1",
        "method_variant": "test",
        "seed": 0,
        "horizon_budget": 5,
    }


class _Tracker:
    def __init__(self, labels: np.ndarray):
        self.labels = labels
        self.calls: list[int] = []

    def read(self, index: int) -> int:
        index = int(index)
        if index not in self.calls:
            self.calls.append(index)
        return int(self.labels[index])


class _Posterior:
    def __init__(self, tracker: _Tracker):
        self.tracker = tracker

    def __getitem__(self, index):
        if np.isscalar(index):
            value = self.tracker.read(int(index))
            return np.asarray([1 - value, value], dtype=float)
        indices = np.asarray(index)
        values = np.asarray([self.tracker.read(int(i)) for i in indices.ravel()])
        return np.column_stack((1 - values, values)).reshape((*indices.shape, 2))


class _Binary:
    def __init__(self, tracker: _Tracker):
        self.tracker = tracker

    def __getitem__(self, index):
        if np.isscalar(index):
            return self.tracker.read(int(index))
        indices = np.asarray(index)
        return np.asarray([self.tracker.read(int(i)) for i in indices.ravel()]).reshape(indices.shape)


def test_selector_parity_with_surviving_historical_arc() -> None:
    domain = FROZEN / "frozen_inputs" / "dataset3_development"
    scores = pd.read_csv(domain / "proxy_only.csv").sort_values("unit_id").proxy_score.to_numpy()
    labels_text = pd.read_csv(domain / "oracle_labels.csv").sort_values("unit_id").oracle_label
    labels = (labels_text.str.lower() == "positive").astype(int).to_numpy()
    clusters = sequential_js_clusters(scores, 0.001)
    proxy = np.column_stack((1.0 - scores, scores))
    proxy_binary = (scores >= 0.4).astype(int)

    arc_root = REPO / "try_or_no" / "arc_source" / "arc"
    sys.path.insert(0, str(arc_root))
    try:
        import arc as historical_arc_module
    finally:
        sys.path.remove(str(arc_root))
    # NumPy 2 compatibility repair under test; the historical control loop is
    # otherwise executed directly.
    from garc_eval.arc_cached_replay.core import safe_confidence

    historical_arc_module.calculate_confidence = safe_confidence
    historical_arc = historical_arc_module.arc
    tracker = _Tracker(labels)
    np.random.seed(3)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        historical = historical_arc(
            proxy=proxy,
            oracle=_Posterior(tracker),
            proxy_score=proxy_binary.copy(),
            oracle_score=_Binary(tracker),
            B=21,
            op=">",
            constant=0,
            tau=1,
            confidence=0.9,
            IOUThreshold=0.5,
            clusters=clusters,
            startup_sampling_rate=0.002,
            tc_enabled=True,
            ps_enabled=True,
            lp_enabled=True,
        )

    oracle = FrozenOracle(dict(enumerate(labels_text.str.lower().tolist())))
    selector = ARCSelector(scores, clusters, budget=20, seed=3)
    selector.run(oracle)
    assert list(oracle.access_log) == tracker.calls
    assert selector.diagnostics()["candidate_clips"] == np.asarray(
        historical["cand_clips"], dtype=int
    ).reshape(-1, 2).tolist()


def test_oracle_access_is_causal_and_no_future_label_is_read() -> None:
    scores = np.asarray([0.9, 0.8, 0.2, 0.7, 0.1])
    selector = ARCSelector(
        scores,
        sequential_js_clusters(scores, 0.001),
        budget=3,
        seed=1,
        config=ARCConfig(confidence=2.0),
    )
    oracle = FrozenOracle({i: "positive" if i == 1 else "negative" for i in range(5)})
    assert oracle.access_log == ()
    selected = selector.select_next()
    assert selected is not None
    assert oracle.access_log == ()
    revealed = oracle.reveal(selected)
    assert oracle.access_log == (selected.unit_id,)
    selector.observe(selected, revealed)
    assert len(oracle.access_log) == 1


def test_selector_api_has_no_reference_or_oracle_labels() -> None:
    parameters = set(inspect.signature(ARCSelector.__init__).parameters)
    assert "reference" not in parameters
    assert "oracle" not in parameters
    assert "labels" not in parameters


def test_empty_candidates_are_finite_and_do_not_query() -> None:
    scores = np.asarray([0.1, 0.2, 0.3])
    selector = ARCSelector(scores, sequential_js_clusters(scores, 0.001), budget=3, seed=0)
    oracle = FrozenOracle({0: "negative", 1: "negative", 2: "negative"})
    assert selector.run(oracle) == []
    diagnostics = selector.diagnostics()
    assert diagnostics["candidate_clips"] == []
    assert diagnostics["candidate_clip_confidences"] == []
    assert diagnostics["tau_confidence"] == 0.0
    assert np.isfinite(diagnostics["tau_confidence"])
    assert oracle.access_log == ()


def test_duplicate_logical_queries_are_forbidden_and_selector_deduplicates() -> None:
    scores = np.asarray([0.9, 0.8, 0.7, 0.2, 0.1])
    clusters = sequential_js_clusters(scores, 0.001)
    oracle = FrozenOracle({i: "unknown" for i in range(len(scores))})
    selector = ARCSelector(scores, clusters, budget=3, seed=1, config=ARCConfig(confidence=2.0))
    first = selector.select_next()
    assert first is not None
    selector.observe(first, oracle.reveal(first))
    with pytest.raises(OracleAccessError, match="duplicate"):
        oracle.reveal(first)
    selector.run(oracle)
    selected = [int(row["unit_id"]) for row in selector.trace]
    assert len(selected) == len(set(selected))


@pytest.mark.parametrize("outcome", ["unknown", "parse_failure", "timeout", "ambiguous", "abstain", "unusable"])
def test_indeterminate_outcomes_are_not_negative_or_propagated(outcome: str) -> None:
    scores = np.asarray([0.9, 0.9, 0.9, 0.2])
    clusters = np.asarray([0, 0, 0, 1])
    selector = ARCSelector(scores, clusters, budget=1, seed=1)
    selection = selector.select_next()
    assert selection is not None
    selector.observe(selection, outcome)
    assert np.all(selector.explicit_labels == -1)
    assert not selector.sampled.any()
    assert selector.propagation_log == []

    trace = pd.DataFrame(selector.trace)
    predictions = BENCH.materialize_from_trace(
        trace, _simple_units(4), _meta(), "k3_bridge_safe", {"g_max": 1, "d_core_max": 40, "d_seg_max": 60}
    )
    assert predictions.empty


def test_propagated_positives_never_enter_comparable_event_relation() -> None:
    scores = np.asarray([0.9, 0.9, 0.9, 0.2])
    clusters = np.asarray([0, 0, 0, 1])
    selector = ARCSelector(scores, clusters, budget=1, seed=1, config=ARCConfig(confidence=2.0))
    selection = selector.select_next()
    assert selection is not None
    selector.observe(selection, "positive")
    diagnostics = selector.diagnostics()
    assert diagnostics["propagated_positive_unit_ids"]

    predictions = BENCH.materialize_from_trace(
        pd.DataFrame(selector.trace),
        _simple_units(4),
        _meta(),
        "k3_bridge_safe",
        {"g_max": 1, "d_core_max": 40, "d_seg_max": 60},
    )
    assert predictions.num_positive_anchors.sum() == 1
    assert predictions.anchor_unit_ids.tolist() == [str(selection.unit_id)]


def test_replay_is_deterministic() -> None:
    scores = np.asarray([0.91, 0.62, 0.13, 0.77, 0.42, 0.11, 0.83, 0.22])
    clusters = sequential_js_clusters(scores, 0.001)
    labels = {i: "positive" if i in {1, 3, 6} else "negative" for i in range(len(scores))}
    traces = []
    diagnostics = []
    for _ in range(2):
        selector = ARCSelector(scores, clusters, budget=5, seed=17, config=ARCConfig(confidence=2.0))
        selector.run(FrozenOracle(labels))
        traces.append(selector.trace)
        diagnostics.append(selector.diagnostics())
    assert traces[0] == traces[1]
    assert diagnostics[0] == diagnostics[1]


def test_identical_oracle_trace_has_identical_k3_output() -> None:
    trace = pd.DataFrame(
        {
            "call_idx": [0, 1, 2],
            "unit_id": [1, 2, 4],
            "oracle_label_after_query": ["positive", "positive", "negative"],
        }
    )
    args = (trace, _simple_units(6), _meta(), "k3_bridge_safe", {"g_max": 1, "d_core_max": 40, "d_seg_max": 60})
    left = BENCH.materialize_from_trace(*args)
    right = BENCH.materialize_from_trace(*args)
    pd.testing.assert_frame_equal(left, right)


def test_frozen_evaluator_and_unit_reference_alignment() -> None:
    for domain in ["dataset3_development", "realcartest_0_1570", "realcartest_2000_3200"]:
        root = FROZEN / "frozen_inputs" / domain
        units = pd.read_csv(root / "units.csv")
        references = pd.read_csv(root / "reference_events.csv")
        assert units.unit_id.astype(int).tolist() == list(range(len(units)))
        durations = (units.end_time - units.start_time).to_numpy(float)
        assert np.all(durations > 0.0)
        assert np.all(durations <= 10.0 + 1e-9)
        if domain == "dataset3_development":
            assert np.count_nonzero(~np.isclose(durations, 10.0)) == 1
            assert durations[-1] == pytest.approx(5.0)
        else:
            assert np.allclose(durations, 10.0)
        valid = set(units.unit_id.astype(int))
        for raw_ids in references.source_unit_ids:
            assert set(BENCH.read_ids(raw_ids)) <= valid
        empty = pd.DataFrame(columns=BENCH.EVENT_SEGMENT_COLUMNS)
        _, metrics = BENCH.evaluate_events(empty, references, _meta(), "frozen-evaluator")
        metric_map = dict(zip(metrics.metric_name, metrics.metric_value))
        assert metric_map["event_precision"] == 0.0
        assert metric_map["event_recall"] == 0.0
        assert metric_map["event_f1"] == 0.0
