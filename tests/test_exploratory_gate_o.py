from rc_sem.exploratory_gate_o import event_f1, event_groups, event_recall, right_continuous_auc, temporal_bisection_order


def test_exploratory_bisection_is_deterministic_and_complete() -> None:
    assert temporal_bisection_order(35)[:6] == (17, 8, 26, 3, 12, 21)
    assert set(temporal_bisection_order(43)) == set(range(43))


def test_event_metrics_are_one_to_one_and_right_continuous() -> None:
    reference = event_groups([1, 2, 8])
    predicted = event_groups([1, 2])
    assert event_recall(predicted, reference) == 0.5
    assert event_f1(predicted, reference) == 2 / 3
    assert right_continuous_auc([(2.0, 0.5)], 10.0) == 0.4
