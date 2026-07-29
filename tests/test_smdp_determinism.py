from garc_eval.scan_confirm_controller.action import Action
from garc_eval.scan_confirm_controller.runner import SCORE_PREFIX_CACHE, TraceReplayEnvironment
from garc_eval.scan_confirm_controller.smdp_oracle import evaluator_state_hash


def test_same_trace_and_cache_produce_identical_state():
    SCORE_PREFIX_CACHE.clear()
    first = TraceReplayEnvironment("V0_Q1", 60.0)
    first.step(Action.SCAN)
    first_hash = evaluator_state_hash(first)
    second = TraceReplayEnvironment("V0_Q1", 60.0)
    second.step(Action.SCAN)
    assert evaluator_state_hash(second) == first_hash


def test_hash_changes_with_frontier_capacity_and_static_task_assets():
    first = TraceReplayEnvironment("V1_Q1", 60.0)
    second = TraceReplayEnvironment("V1_Q1", 60.0)
    second.frontier.capacity = first.frontier.capacity + 1
    assert evaluator_state_hash(second) != evaluator_state_hash(first)
    other_query = TraceReplayEnvironment("V1_Q2", 60.0)
    assert evaluator_state_hash(other_query) != evaluator_state_hash(first)
