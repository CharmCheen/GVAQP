from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import prepare_p1_independent_geometry_replication as prepare
import resume_p1_independent_geometry_replication as resume
from garc_eval.p1b_protocol_v1_2 import (
    assign_positive_units_to_events, reference_quality_decision,
    temporal_region_count, trace_proxy_metadata,
)


def test_pair_extremes_use_frozen_public_geometry_order():
    frame = pd.DataFrame(
        [
            {"number_of_temporal_regions_touched": 2, "temporal_dispersion": 0.1, "coverage_fraction": 0.2, "largest_unqueried_gap": 20.0, "query_redundancy": 0.5, "trace_instance_id": "low", "forbidden_outcome": 999},
            {"number_of_temporal_regions_touched": 5, "temporal_dispersion": 0.2, "coverage_fraction": 0.4, "largest_unqueried_gap": 10.0, "query_redundancy": 0.1, "trace_instance_id": "high", "forbidden_outcome": -999},
        ]
    )
    high, low = prepare.select_extremes(frame)
    assert high.trace_instance_id == "high"
    assert low.trace_instance_id == "low"


def test_human_event_matching_is_one_to_one_and_overlap_only():
    left = [
        {"start_time": 0.0, "end_time": 10.0},
        {"start_time": 20.0, "end_time": 30.0},
    ]
    right = [
        {"start_time": 1.0, "end_time": 9.0},
        {"start_time": 40.0, "end_time": 50.0},
    ]
    matched = resume.match_annotation_events(left, right)
    assert len(matched) == 1
    assert matched[0][2] == 0.8


def test_secondary_c1_metric_calls_authoritative_matcher():
    precision, recall, f1, mean_iou = resume.authoritative_c1_metrics(
        [(0.0, 10.0)], [(0.0, 10.0)], "DALI", "Q"
    )
    assert (precision, recall, f1) == (1.0, 1.0, 1.0)
    assert mean_iou == 1.0


def test_current_preannotation_package_is_fail_closed():
    out = ROOT / "outputs/p1_independent_geometry_replication_v1"
    state = json.loads((out / "RESEARCH_STATE.json").read_text())
    protocol = json.loads((out / "P1_PROTOCOL.json").read_text())
    assert state["phase_status"] == "WAITING_HUMAN_REFERENCE"
    assert state["p1_trace_feasibility"] == "PASS"
    assert protocol["primary_unit_of_inference"] == "video-query cluster"
    assert (out / "HUMAN_EVENT_LABELS.jsonl").stat().st_size == 0
    for prohibited in (
        "EQUAL_YIELD_PRIMARY_RESULTS.csv",
        "MATERIALIZER_INDEPENDENT_TRACE_RESULTS.csv",
        "LOVO_RESULTS.csv",
    ):
        assert not (out / prohibited).exists()


def test_anchor_primary_credits_at_most_one_event_deterministically():
    units = [{"start": 0, "end": 10}]
    events = [
        {"event_id": "E2", "start_time": 1, "end_time": 9},
        {"event_id": "E1", "start_time": 2, "end_time": 8},
    ]
    result = assign_positive_units_to_events(units, events)
    assert sum(result.values()) == 1
    assert result == {"E2": 1, "E1": 0}  # E2 has larger overlap.
    tied = [dict(events[0], event_id="E2"), dict(events[0], event_id="E1")]
    assert assign_positive_units_to_events(units, tied) == {"E2": 0, "E1": 1}


def test_overlap_any_is_separate_multi_credit_sensitivity():
    units = [{"start": 0, "end": 10}]
    events = [{"event_id":"E1","start_time":1,"end_time":6},{"event_id":"E2","start_time":4,"end_time":9}]
    assert sum(assign_positive_units_to_events(units, events).values()) == 1
    assert sum(assign_positive_units_to_events(units, events, "OVERLAP_ANY_EVENT").values()) == 2


def test_primary_region_construction_is_deterministic():
    assert temporal_region_count([4, 2, 3, 9, 9]) == 2
    assert temporal_region_count([]) == 0


def test_proxy_blind_metadata_deduplicates_across_proxy():
    base={"video_id":"DALI","generator_family":"UniformTemporal","queried_unit_ids":"[\"DALI_u0000\"]"}
    a=trace_proxy_metadata(base|{"proxy_id":"YOLO"}); b=trace_proxy_metadata(base|{"proxy_id":"FLOW"})
    assert a["trace_content_hash"] == b["trace_content_hash"]
    assert a["proxy_origin"] == b["proxy_origin"] == "SHARED_CONTROL"


def test_reference_quality_hard_failures_and_eligibility():
    good={"event_existence_agreement":True,"annotator_a_event_count":2,"annotator_b_event_count":2,"matched_events_iou_gt_0":2}
    assert reference_quality_decision([good.copy() for _ in range(6)])[0] == "ADJUDICATION_ELIGIBLE"
    bad=[good|{"event_existence_agreement":False} for _ in range(3)]+[good.copy() for _ in range(3)]
    assert reference_quality_decision(bad)[0] == "INSUFFICIENT"
    unmatched=[good|{"matched_events_iou_gt_0":0} for _ in range(6)]
    assert reference_quality_decision(unmatched)[0] == "INSUFFICIENT"


def test_generalization_labels_and_privacy_are_frozen():
    protocol=json.loads((ROOT/"outputs/p1_independent_geometry_replication_v1/P1_PROTOCOL.json").read_text())
    assert protocol["inference"]["generalization_primary"] == "Leave-One-Video-Out"
    assert protocol["inference"]["generalization_secondary"] == "Leave-One-VideoQuery-Out"
    assert protocol["inference"]["lovq_cannot_rescue_negative_lovo"] is True
    server=(ROOT/"scripts/serve_p1_independent_geometry_reference.py").read_text()
    assert "BaseHTTPRequestHandler" in server and "SimpleHTTPRequestHandler" not in server
    assert 'self.path == "/api/cases"' in server and 'self.path != "/api/save"' in server


def test_check_and_incomplete_state_cannot_start_agreement_or_outcomes(monkeypatch):
    called=[]
    monkeypatch.setattr(resume,"readiness",lambda:{"raw_records":0})
    monkeypatch.setattr(resume,"verify_protocol_freeze",lambda:None)
    monkeypatch.setattr(resume,"validate_independent_annotations",lambda:called.append("agreement"))
    monkeypatch.setattr(resume,"run_analysis",lambda *_:called.append("analysis"))
    monkeypatch.setattr(sys,"argv",["resume","--check"])
    resume.main()
    assert called == []


def test_protocol_hash_mismatch_stops_execution(tmp_path, monkeypatch):
    cases=tmp_path/"cases.json"; raw=tmp_path/"labels.jsonl"; protocol=tmp_path/"protocol.json"
    cases.write_text(json.dumps([{"case_id":"c","video_id":"v","query_id":"q","duration_sec":10}]))
    protocol.write_text(json.dumps({"protocol_hash":"expected"}))
    raw.write_text(json.dumps({"case_id":"c","annotator_id":"ANNOTATOR_A","protocol_hash":"wrong"})+"\n")
    monkeypatch.setattr(resume,"CASES",cases); monkeypatch.setattr(resume,"RAW",raw); monkeypatch.setattr(resume,"HUMAN_PROTOCOL",protocol)
    import pytest
    with pytest.raises(RuntimeError,match="protocol hash mismatch"):
        resume.latest_annotations()


def test_incomplete_annotator_cannot_trigger_agreement(monkeypatch):
    monkeypatch.setattr(resume,"latest_annotations",lambda:({"c":{}},{("ANNOTATOR_A","c"):{"events":[]}},["ANNOTATOR_A"]))
    import pytest
    with pytest.raises(RuntimeError,match="must each complete"):
        resume.validate_independent_annotations()


def test_agreement_does_not_adjudicate_automatically(tmp_path, monkeypatch):
    monkeypatch.setattr(resume,"ADJUDICATED",tmp_path/"absent.csv")
    import pytest
    with pytest.raises(RuntimeError,match="ADJUDICATED_EVENTS"):
        resume.freeze_adjudicated_reference({}, {"human_reference_quality":"ADJUDICATION_ELIGIBLE"})


def test_outcome_analysis_requires_reference_freeze():
    source=(ROOT/"scripts/resume_p1_independent_geometry_replication.py").read_text()
    main=source.split("def main() -> None:",1)[1]
    assert main.index("freeze_adjudicated_reference") < main.index("run_analysis(reference, freeze)")
