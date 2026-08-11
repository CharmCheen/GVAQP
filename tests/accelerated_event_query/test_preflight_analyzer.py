import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/analyze_accelerated_event_query_oracle_preflight_v1.py"
SPEC = importlib.util.spec_from_file_location("preflight_analyzer", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def record(label: str, confidence: str = "high", parse_status: str = "ok") -> dict:
    return {
        "parse_status": parse_status,
        "effective_label": label,
        "parsed": {"confidence": confidence},
    }


def frozen_inputs():
    prereg = {
        "clips": [
            {"candidate_id": "A", "video_id": "V1"},
            {"candidate_id": "B", "video_id": "V2"},
            {"candidate_id": "C", "video_id": "V2"},
        ]
    }
    review = {
        "reviews": [
            {"candidate_id": "A", "label": "not_relevant", "confidence": "medium", "evidence": "none"},
            {"candidate_id": "B", "label": "not_relevant", "confidence": "high", "evidence": "none"},
            {"candidate_id": "C", "label": "unknown", "confidence": "medium", "evidence": "ambiguous"},
        ]
    }
    records = {}
    for candidate_id in ("A", "B", "C"):
        records[(candidate_id, "base", 2.0, 0)] = record("relevant")
        records[(candidate_id, "base", 2.0, 1)] = record("relevant")
    return prereg, review, records


def test_two_cross_video_contradictions_are_systematic_failure():
    prereg, review, records = frozen_inputs()
    result = MODULE.classify_visual_review(prereg, review, records)
    assert result["contradiction_candidate_count"] == 2
    assert result["contradiction_videos"] == ["V1", "V2"]
    assert result["systematic_contradiction"] is True
    assert result["visual_review_status"].startswith("FAIL_SYSTEMATIC")


def test_unknown_review_and_nonconsensus_model_are_not_contradictions():
    prereg, review, records = frozen_inputs()
    records[("B", "base", 2.0, 1)] = record("relevant", confidence="medium")
    result = MODULE.classify_visual_review(prereg, review, records)
    assert result["contradiction_candidate_count"] == 1
    assert result["systematic_contradiction"] is False
    assert result["visual_review_status"].startswith("REVIEW_REQUIRED")


def test_review_ids_must_exactly_match_preregistered_clips():
    prereg, review, records = frozen_inputs()
    review["reviews"].pop()
    try:
        MODULE.classify_visual_review(prereg, review, records)
    except RuntimeError as error:
        assert "exactly match" in str(error)
    else:
        raise AssertionError("expected mismatched review IDs to fail closed")
