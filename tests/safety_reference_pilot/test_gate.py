from garc_eval.safety_reference_pilot.gate import evaluate_gate


def test_gate_passes_only_with_complete_metrics_and_no_failures():
    thresholds = {
        "human_event_recall_min": 0.9,
        "hard_negative_false_positive_rate_max": 0.1,
    }
    result = evaluate_gate(
        thresholds,
        {"human_event_recall_min": 0.92, "hard_negative_false_positive_rate_max": 0.08},
        {"all_positive_events_have_high_confidence": False},
    )
    assert result["status"] == "PASS"


def test_gate_blocks_missing_metric_or_automatic_failure():
    thresholds = {"human_event_recall_min": 0.9}
    assert evaluate_gate(thresholds, {}, {})["status"] == "BLOCK"
    assert evaluate_gate(
        thresholds,
        {"human_event_recall_min": 0.95},
        {"all_positive_events_have_high_confidence": True},
    )["status"] == "BLOCK"

