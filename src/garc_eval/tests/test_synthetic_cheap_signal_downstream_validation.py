import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from garc_eval.experiments.synthetic_cheap_signal_downstream_validation_v1.run_experiment import (
    CILS_TAUS,
    PRECISION_TARGETS,
    auc_score,
    cils_select,
    evaluate_selection,
    make_score_for_auc,
    nms,
    prepare_for_signal,
)


def _toy_candidates():
    return pd.DataFrame(
        [
            {
                "interval_id": f"iv_{i}",
                "video_id": "v",
                "t_start": float(i * 20),
                "t_end": float(i * 20 + 10),
                "duration": 10.0,
                "method": "fixed_window",
                "source_signal": "toy",
                "active_score": 0.1,
                "max_score": 0.1,
                "mean_score": 0.1,
                "score_persistence": 0.1,
                "boundary_left_drop": 0.5,
                "boundary_right_drop": 0.5,
                "boundary_quality": 1.0,
                "signal_disagreement": 0.0,
                "num_units": 5,
                "overlap_group_id": "one_group",
                "answer_iou_0_3": i < 5,
                "answer_iou_0_5": i < 5,
                "matched_true_interval_event_id_iou_0_3": "e1" if i < 2 else "e2" if i < 5 else "",
                "matched_true_interval_event_id_iou_0_5": "e1" if i < 2 else "e2" if i < 5 else "",
                "point_anchor_only_iou_0_3": i == 8,
                "point_anchor_only_iou_0_5": i == 8,
            }
            for i in range(10)
        ]
    )


def test_high_auc_synthetic_scores_rank_tp_above_fp():
    y = np.array([1] * 100 + [0] * 100)
    score = make_score_for_auc(y, 0.95, 0)
    assert score[y == 1].mean() > score[y == 0].mean()
    assert auc_score(y, score) > 0.90


def test_random_signal_near_random_auc():
    rng = np.random.default_rng(123)
    y = np.array([1] * 200 + [0] * 200)
    score = rng.normal(size=len(y))
    assert 0.40 <= auc_score(y, score) <= 0.60


def test_oracle_signal_near_perfect_auc():
    y = np.array([1, 0, 1, 0, 0, 1])
    score = y + np.linspace(0, 1e-9, len(y))
    assert auc_score(y, score) == 1.0


def test_precision_target_not_passed_as_cils_tau():
    for precision_target in PRECISION_TARGETS:
        assert precision_target not in [0.5, 0.6, 0.7]
    assert 0.8 in CILS_TAUS and 0.9 in CILS_TAUS


def test_point_anchor_only_does_not_count_as_main_tp():
    cand = _toy_candidates().iloc[[8]].copy()
    events = pd.DataFrame([{"event_id": "e1", "t_start": 0.0, "t_end": 10.0, "duration": 10.0}])
    row = evaluate_selection(cand, "toy", "toy_signal", 0, 1, 0.8, None, 0.5, 0.1, events)
    assert row["observed_precision_interval_iou_0_3"] == 0.0
    assert row["point_anchor_only_selected_count"] == 1


def test_topk_and_cils_share_evaluation_function():
    cand = _toy_candidates()
    scores = pd.DataFrame({"interval_id": cand["interval_id"], "synthetic_score": [10 - i for i in range(len(cand))]})
    work = prepare_for_signal(cand, scores)
    topk = nms(work.sort_values("synthetic_score", ascending=False), 5)
    events = pd.DataFrame(
        [
            {"event_id": "e1", "t_start": 0.0, "t_end": 30.0, "duration": 30.0},
            {"event_id": "e2", "t_start": 40.0, "t_end": 90.0, "duration": 50.0},
        ]
    )
    cils, _ = cils_select(work, 5, 0.5, events)
    topk_row = evaluate_selection(topk, "topk", "toy", 0, 5, 0.8, None, 1.0, 1.0, events)
    cils_row = evaluate_selection(cils, "cils", "toy", 0, 5, 0.8, 0.5, 1.0, 1.0, events)
    assert "event_recall_iou_0_3" in topk_row
    assert "event_recall_iou_0_3" in cils_row


def test_fixed_scores_are_reproducible():
    y = np.array([1] * 10 + [0] * 10)
    a = make_score_for_auc(y, 0.8, 7)
    b = make_score_for_auc(y, 0.8, 7)
    assert np.array_equal(a, b)
