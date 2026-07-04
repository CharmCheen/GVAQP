import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from garc_eval.metrics.craq_lite_metrics import (
    Interval,
    duplicate_rate,
    duration_inflation,
    event_recall,
    interval_iou,
)


def test_interval_iou_exact_partial_disjoint():
    assert interval_iou(Interval(0, 10), Interval(0, 10)) == 1.0
    assert interval_iou(Interval(0, 10), Interval(20, 30)) == 0.0
    assert interval_iou(Interval(0, 10), Interval(5, 15)) == 5 / 15


def test_event_recall_counts_each_event_once():
    preds = [Interval(0, 10), Interval(100, 110)]
    events = [Interval(0, 10, "e1"), Interval(50, 60, "e2")]
    assert event_recall(preds, events, 0.3) == 0.5


def test_duplicate_rate_extra_hits_over_returned_predictions():
    preds = [Interval(0, 10), Interval(1, 11), Interval(50, 60)]
    events = [Interval(0, 10, "e1"), Interval(50, 60, "e2")]
    assert duplicate_rate(preds, events, 0.3) == 1 / 3


def test_duration_inflation_uses_matched_event_duration():
    preds = [Interval(0, 20), Interval(50, 60)]
    events = [Interval(0, 10, "e1"), Interval(50, 60, "e2")]
    assert duration_inflation(preds, events, 0.3) == 30 / 20

