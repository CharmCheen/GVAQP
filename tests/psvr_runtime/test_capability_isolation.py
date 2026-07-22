from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from garc_eval.psvr_runtime import (
    EvidenceLedger,
    RuntimeConfig,
    adversarial_sandbox_probe,
    start_oracle_service,
    start_selector_service,
)


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/oracle/oracle_presence_observations.csv"
REFERENCE = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/event_reference.csv"


def test_accessor_surface_and_exact_visibility():
    handle = start_oracle_service(CACHE)
    try:
        accessor = handle.runtime_accessor()
        assert dir(accessor) == ["queried_ids", "query", "query_count"]
        assert accessor.query_count() == 0
        for forbidden in ("table", "all_labels", "items", "dump", "reference", "cache_path", "__dict__"):
            with pytest.raises(AttributeError):
                getattr(accessor, forbidden)
        with pytest.raises(TypeError):
            iter(accessor)
        ledger = EvidenceLedger()
        zero = ledger.selector_view([{"unit_id": 0}], [])
        assert zero.visible_label_count() == 0
        for uid in (0, 50, 57):
            ledger.append_query_result(accessor.query(uid))
        view = ledger.selector_view([{"unit_id": x} for x in range(3)], [{"unit_id": 0, "proxy_score": 0.2}])
        assert view.visible_label_count() == 3
        assert accessor.query_count() == 3
        assert accessor.queried_ids() == (0, 50, 57)
        assert len(ledger.materializer_trace_rows()) == 3
    finally:
        handle.close()


def test_runtime_config_and_import_graph_have_no_reference_paths():
    config = RuntimeConfig("bench", "video", "query", "proxy")
    assert all("path" not in name for name in config.__dataclass_fields__)
    runtime = importlib.import_module("garc_eval.psvr_runtime")
    assert "psvr_evaluation" not in Path(runtime.__file__).read_text()
    for module in ("garc_eval.psvr_runtime.capabilities", "garc_eval.psvr_runtime.views"):
        assert "psvr_evaluation" not in Path(importlib.import_module(module).__file__).read_text()


def test_actual_selector_sandbox_blocks_import_and_direct_path_open():
    result = adversarial_sandbox_probe(
        [{"unit_id": 0}], [{"unit_id": 0, "proxy_score": 0.2}], [], (CACHE, REFERENCE)
    )
    assert result["status"] == "ok"
    assert result["worker_uid"] == 65534
    assert result["worker_root"] == "/"
    assert result["evaluator_import"].startswith("BLOCKED:")
    assert all(value.startswith("BLOCKED:") for value in result["direct_path_access"].values())
    assert result["oracle_accessor_present"] is False
    assert result["visible_labels"] == 0
    assert result["memory_enumeration_attack"]["sensitive_stack_names"] == []
    assert result["memory_enumeration_attack"]["sensitive_gc_objects"] == []


def test_persistent_selector_sees_only_legal_view_and_is_deterministic():
    public = [{
        "benchmark_id": "b", "video_id": "v", "video_sha256": "h", "unit_id": unit_id,
        "start_frame": unit_id * 10, "end_frame": unit_id * 10 + 9,
        "start_time": float(unit_id), "end_time": float(unit_id + 1), "duration_seconds": 1.0,
        "split_role": "development", "eligible_for_query": True, "anchor_id": f"a{unit_id}",
    } for unit_id in (0, 1)]
    proxy = [{"unit_id": 0, "proxy_score": 0.9}, {"unit_id": 1, "proxy_score": 0.8}]
    service = start_selector_service()
    try:
        assert service.initialization == {"worker_uid": 65534, "worker_root": "/"}
        first = service.select(public, proxy, [], {"mode": "ranked_proxy", "rank_offset": 0})
        repeat = service.select(public, proxy, [], {"mode": "ranked_proxy", "rank_offset": 0})
        assert first == repeat
        assert first["candidate_unit_id"] == 0 and first["visible_label_count"] == 0
        after = service.select(
            public, proxy, [{"unit_id": 0, "parsed_label": "positive"}],
            {"mode": "ranked_proxy", "rank_offset": 0},
        )
        assert after["candidate_unit_id"] == 1 and after["visible_label_count"] == 1
        with pytest.raises(ValueError, match="invalid queried-oracle columns"):
            service.select(
                public, proxy, [{"unit_id": 0, "parsed_label": "positive", "reference_event_id": "leak"}],
                {"mode": "ranked_proxy", "rank_offset": 0},
            )
    finally:
        service.close()
