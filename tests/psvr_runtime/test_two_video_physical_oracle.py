from garc_eval.psvr_runtime.two_video_physical_oracle import project_generic_label


def test_frozen_query_projection_is_type_specific_and_fail_closed():
    vehicle = {"label": "positive", "involved_object": "vehicle"}
    cyclist = {"label": "positive", "involved_object": "cyclist"}
    pedestrian = {"label": "positive", "involved_object": "pedestrian"}
    other = {"label": "positive", "involved_object": "other"}
    q1 = {"vehicle", "cyclist"}
    q2 = {"pedestrian", "cyclist"}

    assert project_generic_label(vehicle, q1) == "positive"
    assert project_generic_label(vehicle, q2) == "negative"
    assert project_generic_label(cyclist, q1) == "positive"
    assert project_generic_label(cyclist, q2) == "positive"
    assert project_generic_label(pedestrian, q1) == "negative"
    assert project_generic_label(pedestrian, q2) == "positive"
    assert project_generic_label(other, q1) == "negative"
    assert project_generic_label(other, q2) == "negative"


def test_projection_preserves_abstain_and_never_promotes_negative():
    allowed = {"vehicle", "cyclist"}
    assert (
        project_generic_label(
            {"label": "abstain", "involved_object": "vehicle"}, allowed
        )
        == "abstain"
    )
    assert (
        project_generic_label(
            {"label": "negative", "involved_object": "vehicle"}, allowed
        )
        == "negative"
    )
