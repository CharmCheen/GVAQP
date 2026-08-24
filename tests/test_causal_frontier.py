from __future__ import annotations

import math

import pytest

from garc.causal_frontier import (
    Action,
    Candidate,
    CausalFrontierReplay,
    ConstantCostModel,
    ContractError,
    DatbSVPolicy,
    EventRelation,
    ExSampleEndToEndPolicy,
    InadmissibleAction,
    MappingOracle,
    ScriptedPolicy,
    ScanCell,
    SequentialPolicy,
    UniformStridePolicy,
    assert_replay_parity,
)


def candidate(candidate_id: str, cell_id: str, start: float, score: float = 1.0):
    return Candidate(candidate_id, cell_id, start, start + 10.0, score)


def cell(cell_id: str, start: float, *candidates: Candidate):
    return ScanCell(cell_id, start, start + 10.0, tuple(candidates))


def replay(cells, results=None, *, deadline=20.0, costs=None, reference=3):
    return CausalFrontierReplay(
        cells,
        MappingOracle(results or {}),
        costs or ConstantCostModel(1.0, 2.0),
        deadline,
        reference,
    )


def test_candidate_is_inaccessible_before_scan():
    c0 = candidate("c0", "u0", 0.0)
    engine = replay([cell("u0", 0.0, c0)])
    with pytest.raises(InadmissibleAction):
        engine.run(ScriptedPolicy([Action.verify("c0")]))


def test_every_scanned_cell_exposes_low_priority_fallback():
    c0 = candidate("c0", "u0", 0.0)
    result = replay([cell("u0", 0.0, c0)]).run(
        ScriptedPolicy([Action.scan("u0"), Action.stop()])
    )
    assert result.trace[0].exposed_candidate_ids == ("c0", "fallback:u0")


def test_verification_supports_zero_or_multiple_events():
    c0 = candidate("c0", "u0", 0.0)
    c1 = candidate("c1", "u1", 10.0)
    events = (
        EventRelation("r1", 10.0, 12.0, ("track-a",)),
        EventRelation("r2", 13.0, 15.0, ("track-b",)),
    )
    result = replay([cell("u0", 0.0, c0), cell("u1", 10.0, c1)], {"c1": events}).run(
        ScriptedPolicy(
            [
                Action.scan("u0"),
                Action.verify("c0"),
                Action.scan("u1"),
                Action.verify("c1"),
            ]
        )
    )
    assert result.trace[1].returned_relation_ids == ()
    assert result.trace[3].returned_relation_ids == ("r1", "r2")
    assert len(result.committed_events) == 2


def test_same_participants_within_gap_merge_but_other_cases_stay_separate():
    c0 = candidate("c0", "u0", 0.0)
    c1 = candidate("c1", "u1", 10.0)
    c2 = candidate("c2", "u2", 30.0)
    c3 = candidate("c3", "u3", 40.0)
    results = {
        "c0": (EventRelation("r0", 1.0, 4.0, ("a",)),),
        "c1": (EventRelation("r1", 11.0, 14.0, ("a",)),),
        "c2": (EventRelation("r2", 31.0, 34.0, ("a",)),),
        "c3": (EventRelation("r3", 41.0, 44.0, ("b",)),),
    }
    actions = []
    for index in range(4):
        actions.extend([Action.scan(f"u{index}"), Action.verify(f"c{index}")])
    result = replay(
        [
            cell("u0", 0.0, c0),
            cell("u1", 10.0, c1),
            cell("u2", 30.0, c2),
            cell("u3", 40.0, c3),
        ],
        results,
        deadline=30.0,
    ).run(ScriptedPolicy(actions))
    assert len(result.committed_events) == 3
    merged = result.committed_events[0]
    assert merged.relation_ids == ("r0", "r1")


def test_action_that_crosses_deadline_cannot_mutate_state():
    c0 = candidate("c0", "u0", 0.0)
    result = replay(
        [cell("u0", 0.0, c0)],
        deadline=0.5,
        costs=ConstantCostModel(1.0, 2.0),
    ).run(ScriptedPolicy([Action.scan("u0")]))
    assert result.elapsed_s == 0.0
    assert result.committed_events == ()
    assert result.trace[0].status == "REJECTED_DEADLINE"


def test_order_specific_scan_cost_is_charged():
    c0 = candidate("c0", "u0", 0.0)
    c1 = candidate("c1", "u1", 10.0)
    costs = ConstantCostModel(
        1.0,
        2.0,
        transition_overrides={(None, "u1"): 3.0, ("u1", "u0"): 4.0},
    )
    result = replay(
        [cell("u0", 0.0, c0), cell("u1", 10.0, c1)], costs=costs
    ).run(ScriptedPolicy([Action.scan("u1"), Action.scan("u0")]))
    assert [entry.cost_s for entry in result.trace] == [3.0, 4.0]
    assert result.elapsed_s == 7.0


def test_uniform_stride_uses_fixed_original_grid():
    cells = [cell(f"u{index}", index * 10.0) for index in range(5)]
    result = replay(cells, deadline=20.0).run(UniformStridePolicy(stride=2))
    scan_targets = [entry.target_id for entry in result.trace if entry.action == "SCAN"]
    assert scan_targets == ["u0", "u2", "u4", "u1", "u3"]


def test_datb_defers_low_score_fallback_while_exposure_remains():
    cells = [cell("u0", 0.0), cell("u1", 10.0)]
    result = replay(cells, deadline=10.0).run(DatbSVPolicy(verify_score_threshold=0.5))
    assert [entry.action for entry in result.trace[:2]] == ["SCAN", "SCAN"]
    assert [entry.target_id for entry in result.trace[:2]] == ["u0", "u1"]


def test_datb_interleaving_changes_with_verify_scan_cost_ratio():
    c0 = candidate("c0", "u0", 0.0, score=0.6)
    cells = [cell("u0", 0.0, c0), cell("u1", 10.0)]
    expensive = replay(
        cells,
        deadline=40.0,
        costs=ConstantCostModel(1.0, 30.0),
    ).run(DatbSVPolicy())
    cheap = replay(
        cells,
        deadline=40.0,
        costs=ConstantCostModel(1.0, 1.0),
    ).run(DatbSVPolicy())
    assert [entry.action for entry in expensive.trace[:2]] == ["SCAN", "SCAN"]
    assert [entry.action for entry in cheap.trace[:2]] == ["SCAN", "VERIFY"]


def test_sequential_also_defers_fallback_without_deleting_it():
    cells = [cell("u0", 0.0), cell("u1", 10.0)]
    result = replay(cells, deadline=10.0).run(SequentialPolicy())
    assert [entry.action for entry in result.trace[:2]] == ["SCAN", "SCAN"]
    assert "fallback:u0" in result.trace[0].exposed_candidate_ids


def test_exsample_adaptation_routes_each_sample_through_scan_then_verify():
    cells = [cell(f"u{index}", index * 10.0) for index in range(4)]
    result = replay(cells, deadline=20.0).run(
        ExSampleEndToEndPolicy(seed=7, chunk_count=2)
    )
    completed = [entry.action for entry in result.trace if entry.status == "COMPLETED"]
    assert completed[:4] == ["SCAN", "VERIFY", "SCAN", "VERIFY"]


def test_fixed_verify_window_is_enforced():
    bad = Candidate("bad", "u0", 0.0, 5.0, 1.0)
    with pytest.raises(ContractError):
        replay([cell("u0", 0.0, bad)])


def test_identical_action_trace_has_exact_evaluator_parity():
    c0 = candidate("c0", "u0", 0.0)
    relation = EventRelation("r0", 1.0, 4.0, ("a",))
    actions = [Action.scan("u0"), Action.verify("c0")]
    engine = replay([cell("u0", 0.0, c0)], {"c0": (relation,)}, reference=1)
    left = engine.run(ScriptedPolicy(actions, name="policy-path"))
    right = engine.run(ScriptedPolicy(actions, name="baseline-path"))
    assert_replay_parity(left, right)
    assert math.isclose(left.normalized_anytime_event_auc, 0.85)
    assert left.terminal_event_recall == 1.0


def test_oracle_event_must_lie_inside_verified_window():
    c0 = candidate("c0", "u0", 0.0)
    outside = EventRelation("r0", 9.0, 11.0, ("a",))
    engine = replay([cell("u0", 0.0, c0)], {"c0": (outside,)})
    with pytest.raises(ContractError):
        engine.run(ScriptedPolicy([Action.scan("u0"), Action.verify("c0")]))


def test_oracle_failure_is_charged_and_not_coerced_to_negative():
    c0 = candidate("c0", "u0", 0.0)
    engine = CausalFrontierReplay(
        [cell("u0", 0.0, c0)],
        MappingOracle({}, frozenset({"c0"})),
        ConstantCostModel(1.0, 2.0),
        deadline_s=10.0,
        reference_event_count=1,
    )
    result = engine.run(ScriptedPolicy([Action.scan("u0"), Action.verify("c0")]))
    assert result.elapsed_s == 3.0
    assert result.trace[1].oracle_status == "FAILURE"
    assert result.committed_events == ()
