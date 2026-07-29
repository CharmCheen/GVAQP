from garc_eval.accelerated_event_query import (
    K3UnitEventAdapter,
    model_relative_event_metrics,
)

from .v3_helpers import unit


def test_formal_metrics_use_required_32b_relative_names():
    reference = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1").materialize([
        unit(0, "relevant")
    ])
    metrics = model_relative_event_metrics(reference.events, reference)
    assert metrics["32B-relative_event_precision"] == 1.0
    assert metrics["32B-relative_event_recall"] == 1.0
    assert "32b_operational_oracle_relative_event_precision" not in metrics
