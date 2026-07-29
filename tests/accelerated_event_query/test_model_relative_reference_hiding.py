from garc_eval.accelerated_event_query import ModelRelativeLabelStore

from .v3_helpers import unit


def test_controller_can_only_receive_explicitly_queried_labels():
    store = ModelRelativeLabelStore([unit(0, "relevant"), unit(1, "not_relevant")])
    view = store.controller_view(["V0_u0001"])
    assert view == ({
        "unit_id": "V0_u0001",
        "query_id": "Q_DRIVER_RESPONSE_V1",
        "start_time": 10.0,
        "end_time": 20.0,
        "label": "not_relevant",
    },)
    assert "V0_u0000" not in repr(view)
