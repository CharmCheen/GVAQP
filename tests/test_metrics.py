from frozen_reference import source_cumulative_utility
from garc.evaluation.metrics import cumulative_utility, utility_at_deadline


def test_cumulative_utility_parity_and_deadline():
    trace = [
        {"completed": True, "new_distinct_utility": 1, "elapsed_sec": 2},
        {"completed": False, "new_distinct_utility": 9, "elapsed_sec": 3},
        {"completed": True, "new_distinct_utility": 2, "elapsed_sec": 11},
    ]
    assert cumulative_utility(trace) == source_cumulative_utility(trace) == [1, 1, 3]
    assert utility_at_deadline(trace, 10) == 1
