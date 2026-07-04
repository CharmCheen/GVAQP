"""Regression tests for the CRAQ-lite patch (precision_target vs tau decoupling
and overlap_group_id / NMS single-group fix).

These tests guard against two bugs found in the
runs/craq_lite_v1/20260701T075242Z audit:

1. precision_target was passed as the CILS selector tau.
2. nms() and cils_select() skipped candidates by overlap_group_id, which is
   a single group for the clean v2 lattice, capping every selection to 1
   interval regardless of budget.
"""

import math
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from garc_eval.metrics.craq_lite_metrics import Interval, interval_iou
from garc_eval.experiments.craq_lite_v1.run_craq_lite import (
    CILS_TAUS,
    PRECISION_TARGETS,
    cils_select,
    nms,
)


def _make_cand(rows):
    cols = [
        "interval_id", "method", "t_start", "t_end", "duration",
        "active_score", "answer_quality_proxy", "overlap_group_id",
        "boundary_left_drop", "boundary_right_drop", "signal_disagreement",
        "score_persistence", "answer_iou_0_3", "answer_iou_0_5",
    ]
    df = pd.DataFrame(rows, columns=cols)
    df["answer_quality_proxy_bin"] = "q3"
    df["boundary_quality_bin"] = "q3"
    df["duration_bin"] = "5-10"
    return df


def test_precision_targets_disjoint_from_cils_taus():
    """precision_targets must not appear in cils_taus (they are reporting only)."""
    for pt in PRECISION_TARGETS:
        assert pt not in CILS_TAUS, (
            f"precision_target {pt} must not be used as a CILS tau; "
            f"CILS_TAUS={CILS_TAUS}"
        )


def test_cils_select_uses_tau_not_precision_target():
    """cils_select signature must have a tau parameter distinct from any
    precision_target reporting value. We verify by calling with tau=0.5
    (in CILS_TAUS) and tau=0.9 (a precision_target) and checking the calls
    do not raise and treat tau as the selector threshold."""
    rows = [
        {
            "interval_id": f"iv_{i}",
            "method": "fixed_window",
            "t_start": float(i * 100),
            "t_end": float(i * 100 + 10),
            "duration": 10.0,
            "active_score": 0.5,
            "answer_quality_proxy": 1.0 - i * 0.001,
            "overlap_group_id": "og2_00000",
            "boundary_left_drop": 0.1,
            "boundary_right_drop": 0.1,
            "signal_disagreement": 0.0,
            "score_persistence": 0.5,
            "answer_iou_0_3": True,
            "answer_iou_0_5": True,
        }
        for i in range(20)
    ]
    cand = _make_cand(rows)
    events = pd.DataFrame(
        [{"event_id": "e1", "t_start": 0.0, "t_end": 10.0, "duration": 10.0}]
    )
    sel05, exp05 = cils_select(cand, 10, 0.5, events)
    sel09, exp09 = cils_select(cand, 10, 0.9, events)
    # tau=0.5 should be more permissive than tau=0.9
    assert len(sel05) >= len(sel09)
    # With all-True labels and permissive tau, we should get > 0 at tau=0.5
    assert len(sel05) > 0, "tau=0.5 must produce non-empty selection when labels are all positive"


def test_nms_returns_multiple_non_overlapping():
    """NMS must be able to return more than one interval when intervals do
    not overlap, even if they all share the same overlap_group_id."""
    rows = [
        {
            "interval_id": f"iv_{i}",
            "method": "fixed_window",
            "t_start": float(i * 100),
            "t_end": float(i * 100 + 10),
            "duration": 10.0,
            "active_score": 1.0 - i * 0.01,
            "answer_quality_proxy": 1.0 - i * 0.01,
            "overlap_group_id": "og2_00000",  # all same group — the bug scenario
            "boundary_left_drop": 0.1,
            "boundary_right_drop": 0.1,
            "signal_disagreement": 0.0,
            "score_persistence": 0.5,
            "answer_iou_0_3": True,
            "answer_iou_0_5": True,
        }
        for i in range(10)
    ]
    cand = _make_cand(rows)
    result = nms(cand, limit=10, iou_threshold=0.3)
    assert len(result) > 1, (
        f"NMS must return >1 non-overlapping interval even with a single "
        f"overlap_group_id; got {len(result)}"
    )


def test_nms_drops_overlapping():
    """NMS must still drop highly overlapping intervals."""
    rows = [
        {
            "interval_id": f"iv_{i}",
            "method": "fixed_window",
            "t_start": float(i),
            "t_end": float(i + 10),
            "duration": 10.0,
            "active_score": 1.0 - i * 0.01,
            "answer_quality_proxy": 1.0 - i * 0.01,
            "overlap_group_id": "og2_00000",
            "boundary_left_drop": 0.1,
            "boundary_right_drop": 0.1,
            "signal_disagreement": 0.0,
            "score_persistence": 0.5,
            "answer_iou_0_3": True,
            "answer_iou_0_5": True,
        }
        for i in range(10)
    ]
    cand = _make_cand(rows)
    result = nms(cand, limit=10, iou_threshold=0.3)
    # intervals 0..9 each overlap heavily with neighbors; at most ~1-2 survive
    assert len(result) <= 2, (
        f"NMS must drop overlapping intervals; got {len(result)} from 10 "
        f"heavily overlapping candidates"
    )


def test_cils_select_no_group_id_skip():
    """cils_select must not skip candidates by overlap_group_id. With all
    non-overlapping intervals sharing one group id, it must return > 1."""
    rows = []
    for i in range(20):
        rows.append({
            "interval_id": f"iv_{i}",
            "method": "fixed_window",
            "t_start": float(i * 100),
            "t_end": float(i * 100 + 10),
            "duration": 10.0,
            "active_score": 0.5,
            "answer_quality_proxy": 1.0 - i * 0.001,
            "overlap_group_id": "og2_00000",
            "boundary_left_drop": 0.5,
            "boundary_right_drop": 0.5,
            "signal_disagreement": 0.0,
            "score_persistence": 0.5,
            "answer_iou_0_3": True,
            "answer_iou_0_5": True,
        })
    cand = _make_cand(rows)
    events = pd.DataFrame(
        [{"event_id": "e1", "t_start": 0.0, "t_end": 10.0, "duration": 10.0}]
    )
    sel, exp = cils_select(cand, 10, 0.5, events)
    assert len(sel) > 1, (
        f"cils_select must return >1 non-overlapping interval even with a "
        f"single overlap_group_id; got {len(sel)}"
    )
