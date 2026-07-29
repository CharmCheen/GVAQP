import json
from pathlib import Path

import pytest

from garc_eval.accelerated_event_query.oracle_v3_parser import parse_oracle_v3_response


ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "outputs/accelerated_event_query_v1/operational_oracle/preflight_v2/raw"


def load(relative: str) -> dict:
    return json.loads((V2 / relative).read_text(encoding="utf-8"))


def project_v2_diagnostics(record: dict) -> str:
    parsed = record["parsed"]
    return json.dumps({
        "label": parsed["label"],
        "confidence": parsed["confidence"],
        "evidence": parsed["evidence"],
    })


def test_dali_u0548_v2_free_time_coordinates_are_structurally_impossible_in_v3():
    record = load("DALI/DALI_u0548_fps4_sensitivity.json")
    assert record["parse_status"] == "invalid_relevant_boundary"
    assert record["parsed"]["event_start_sec"] == 17.0
    assert parse_oracle_v3_response(record["raw"]).parse_status == "schema_mismatch"
    projected = parse_oracle_v3_response(project_v2_diagnostics(record))
    assert projected.parse_status == "ok"
    assert set(projected.parsed) == {"label", "confidence", "evidence"}


@pytest.mark.parametrize("left_path,right_path", [
    ("DALI/DALI_u0555_fps2_r0.json", "DALI/DALI_u0555_fps2_r1.json"),
    ("HANGZHOU/HANGZHOU_u0234_fps2_r0.json", "HANGZHOU/HANGZHOU_u0234_fps2_r1.json"),
    ("WUHAN/WUHAN_u0217_fps2_r0.json", "WUHAN/WUHAN_u0217_fps2_r1.json"),
    ("WUHAN/WUHAN_u0171_fps2_r0.json", "WUHAN/WUHAN_u0171_fps2_r1.json"),
])
def test_v2_regression_inputs_preserve_repeat_label_under_v3_projection(left_path, right_path):
    left, right = load(left_path), load(right_path)
    a = parse_oracle_v3_response(project_v2_diagnostics(left))
    b = parse_oracle_v3_response(project_v2_diagnostics(right))
    assert a.parse_status == b.parse_status == "ok"
    assert a.authoritative_label == b.authoritative_label
