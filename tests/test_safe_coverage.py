from itertools import combinations

from frozen_reference import source_largest_gap
from garc.scan import CoverageState, PublicUnit, SafeCoveragePolicy
from garc.scan.policy import EVALUATION_BASELINES, SafeCoverageConfig


def make_state(count, scanned=()):
    units = tuple(PublicUnit(f"u{i}", i * 10.0, (i + 1) * 10.0) for i in range(count))
    return CoverageState(units, tuple(f"u{i}" for i in scanned))


def test_default_is_anytime_largest_gap():
    policy = SafeCoveragePolicy()
    assert policy.policy_id == "ANYTIME_LARGEST_GAP"
    assert policy.choose_next_unit(make_state(9)) == "u4"


def test_action_parity_exhaustive_public_states():
    policy = SafeCoveragePolicy()
    comparisons = 0
    for count in range(1, 10):
        for size in range(count):
            for scanned in combinations(range(count), size):
                expected = source_largest_gap(count, scanned)
                assert policy.choose_next_unit(make_state(count, scanned)) == f"u{expected}"
                comparisons += 1
    assert comparisons == sum(2**n - 1 for n in range(1, 10))


def test_evaluation_baselines_are_explicit_and_complete():
    state = make_state(9)
    for name in EVALUATION_BASELINES:
        policy = SafeCoveragePolicy(SafeCoverageConfig(name))
        first = policy.choose_next_unit(state)
        second = policy.choose_next_unit(make_state(9, (int(first[1:]),)))
        assert first != second


def test_video_id_or_rejected_policy_cannot_select_a_winner():
    for invalid in ("YOLO_GUIDED", "RANDOM", "PSP_V0_SHORT"):
        try:
            SafeCoverageConfig(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("rejected or per-video policy accepted")
