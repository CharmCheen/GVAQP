from pathlib import Path

from garc_eval.safety_reference_pilot.protocol import (
    render_stage_a,
    render_stage_b,
    source_timestamp,
    stage_b_payload,
)


ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "benchmarks/safety_critical_driving_event_reference_pilot_v1/prompts"


def proposal():
    return {
        "proposal_id": "P7",
        "start_frame_index": 10,
        "peak_frame_index": 12,
        "end_frame_index": 15,
        "event_family_hint": "crossing_conflict",
        "observable_transition": "pedestrian crosses",
        "confidence": "high",
    }


def test_stage_a_renders_exact_visible_frame_range():
    template = (PROMPTS / "stage_a_discovery_v1.txt").read_text()
    rendered = render_stage_a(template, 60)
    assert "F000 through F059" in rendered
    assert "__LAST_FRAME_INDEX__" not in rendered


def test_stage_b_projection_hides_stage_a_semantics():
    visible = stage_b_payload(proposal())
    assert set(visible) == {
        "proposal_id", "start_frame_index", "peak_frame_index", "end_frame_index"
    }
    template = (PROMPTS / "stage_b_adjudication_v1.txt").read_text()
    rendered = render_stage_b(template, proposal())
    assert "P7" in rendered
    assert "F010" in rendered and "F012" in rendered and "F015" in rendered
    assert "crossing_conflict" not in rendered.split("Independently adjudicate", 1)[0]
    assert "pedestrian crosses" not in rendered


def test_source_timestamp_uses_decoded_mapping_not_fps_arithmetic():
    assert source_timestamp(2, [100.0, 100.52, 101.03]) == 101.03
