from rc_sem.exploratory_deadline_evaluation import deadline_safe_summary


def row(completed: float, *, label: str = "negative", groups=()):
    return {"timestamp_seconds": completed - 5.0, "physical_cost_seconds": 5.0, "action_type": "VERIFY", "outcome": {"label": label}, "current_event_relation": [list(group) for group in groups]}


def test_completion_boundary_and_post_deadline_state_are_strictly_excluded() -> None:
    reference = {0: "positive"}
    base = [row(299.9, groups=()), row(300.0, groups=())]
    safe = deadline_safe_summary(base, reference, 300.0)
    late = deadline_safe_summary([*base, row(300.1, label="positive", groups=((0,),))], reference, 300.0)
    assert safe["verify_actions_completed_at_deadline"] == 2
    assert late["verify_actions_completed_at_deadline"] == 2
    assert late["event_recall_at_deadline"] == safe["event_recall_at_deadline"] == 0.0
    assert late["event_f1_at_deadline"] == safe["event_f1_at_deadline"] == 0.0
    assert late["event_recall_auc"] == safe["event_recall_auc"] == 0.0
    assert late["post_deadline_completed_actions"] == 1


def test_positive_at_exact_deadline_is_visible() -> None:
    summary = deadline_safe_summary([row(300.0, label="positive", groups=((0,),))], {0: "positive"}, 300.0)
    assert summary["event_recall_at_deadline"] == summary["event_f1_at_deadline"] == 1.0
