import pytest

from rc_sem import Action, TwoPhaseCommitGuard, anytime_auc, validate_runtime_payload


def test_two_phase_commit_accepts_only_predeadline_integrity_pass():
    guard = TwoPhaseCommitGuard()
    guard.stage(
        action_id="a0",
        action=Action.SCAN,
        admitted_at_sec=1.0,
        cost_upper_sec=2.0,
        deadline_sec=4.0,
    )
    result = guard.commit(action_id="a0", completed_at_sec=3.0, integrity_passed=True)
    assert result.committed
    assert not result.post_deadline_commit


def test_late_completion_is_preserved_but_never_committed():
    guard = TwoPhaseCommitGuard()
    guard.stage(
        action_id="a0",
        action=Action.VERIFY,
        admitted_at_sec=1.0,
        cost_upper_sec=2.0,
        deadline_sec=4.0,
    )
    result = guard.commit(action_id="a0", completed_at_sec=4.1, integrity_passed=True)
    assert not result.committed
    assert result.reason == "completed_after_deadline"
    assert not result.post_deadline_commit


def test_duplicate_action_attempt_fails_closed():
    guard = TwoPhaseCommitGuard()
    kwargs = dict(
        action_id="a0",
        action=Action.SCAN,
        admitted_at_sec=0.0,
        cost_upper_sec=1.0,
        deadline_sec=2.0,
    )
    guard.stage(**kwargs)
    with pytest.raises(ValueError, match="duplicate action attempt"):
        guard.stage(**kwargs)


def test_runtime_payload_rejects_evaluator_label_leakage():
    with pytest.raises(ValueError, match="leaked"):
        validate_runtime_payload({"coverage_fraction": 0.5, "full_grid_labels": [1, 0]})


def test_runtime_payload_rejects_nested_evaluator_label_leakage():
    with pytest.raises(ValueError, match="reference_events"):
        validate_runtime_payload({"state": {"cache": [{"reference_events": ["e0"]}]}})


def test_anytime_auc_rewards_earlier_materialization():
    early = anytime_auc([(2.0, 1.0)], deadline_sec=10.0)
    late = anytime_auc([(8.0, 1.0)], deadline_sec=10.0)
    assert early == 0.8
    assert late == 0.2
    assert early > late
