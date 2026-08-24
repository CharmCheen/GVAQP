from __future__ import annotations

from dataclasses import fields

import pytest

from garc.endogenous_contract import (
    Action,
    Candidate,
    ConstantCosts,
    DirectVerifyUniformPolicy,
    EndogenousExecutor,
    InadmissibleAction,
    LocalRelation,
    MappingGenerator,
    MappingVerifier,
    PublicState,
    Region,
    ScanThenProxyGreedyPolicy,
    ScriptedPolicy,
    VerificationResult,
    assert_exact_parity,
)


def region(name: str = "r0", start: float = 0.0) -> Region:
    return Region(name, start, start + 10.0)


def candidate(name: str, parent: str = "r0", start: float = 0.0, score: float = 0.5) -> Candidate:
    return Candidate(name, parent, start, start + 2.0, score)


def executor(generator=None, verifier=None, regions=None, deadline=20.0, reference=1):
    return EndogenousExecutor(
        regions or [region()],
        generator or MappingGenerator({}),
        verifier or MappingVerifier(),
        ConstantCosts(1.0, 2.0, 3.0),
        deadline,
        reference,
    )


def test_scan_can_return_zero_without_hidden_fallback():
    result = executor().run("q", ScriptedPolicy([Action.scan("r0")]))
    assert result.trace[0].exposed_candidate_ids == ()
    assert result.trace[0].action == "SCAN"


def test_scan_can_return_one_or_many_candidates():
    c0, c1 = candidate("c0"), candidate("c1", start=2.0)
    one = executor(MappingGenerator({("q", "r0"): (c0,)})).run("q", ScriptedPolicy([Action.scan("r0")]))
    many = executor(MappingGenerator({("q", "r0"): (c0, c1)})).run("q", ScriptedPolicy([Action.scan("r0")]))
    assert one.trace[0].exposed_candidate_ids == ("c0",)
    assert many.trace[0].exposed_candidate_ids == ("c0", "c1")


def test_candidate_verify_is_illegal_before_exposure():
    with pytest.raises(InadmissibleAction):
        executor().run("q", ScriptedPolicy([Action.verify("c0")]))


def test_direct_verify_is_distinct_and_needs_no_scan():
    relation = LocalRelation("e0", 1.0, 3.0, ("local-track",))
    verifier = MappingVerifier(direct_results={("q", "r0"): VerificationResult((relation,))})
    result = executor(verifier=verifier).run("q", DirectVerifyUniformPolicy())
    assert [entry.action for entry in result.trace] == ["DIRECT_VERIFY"]
    assert result.trace[0].exposed_candidate_ids == ()
    assert result.terminal_event_recall == 1.0


def test_query_is_public_and_conditions_candidate_generation():
    c0, c1 = candidate("cat"), candidate("car")
    generator = MappingGenerator({("q-cat", "r0"): (c0,), ("q-car", "r0"): (c1,)})
    left = executor(generator).run("q-cat", ScriptedPolicy([Action.scan("r0")]))
    right = executor(generator).run("q-car", ScriptedPolicy([Action.scan("r0")]))
    assert left.query_id == "q-cat"
    assert left.trace[0].exposed_candidate_ids == ("cat",)
    assert right.trace[0].exposed_candidate_ids == ("car",)


def test_public_state_has_no_reference_or_truth_field():
    names = {item.name for item in fields(PublicState)}
    assert not any(token in name for name in names for token in ("reference", "truth", "label", "oracle"))


def test_local_relations_materialize_by_observed_participants_only():
    c0 = candidate("c0")
    c1 = candidate("c1", start=3.0)
    relations = VerificationResult((LocalRelation("l0", 1.0, 2.0, ("p",)),))
    relations2 = VerificationResult((LocalRelation("l1", 4.0, 5.0, ("p",)),))
    engine = executor(
        MappingGenerator({("q", "r0"): (c0, c1)}),
        MappingVerifier(candidate_results={("q", "c0"): relations, ("q", "c1"): relations2}),
    )
    result = engine.run("q", ScriptedPolicy([Action.scan("r0"), Action.verify("c0"), Action.verify("c1")]))
    assert len(result.committed_events) == 1
    assert result.committed_events[0].relation_ids == ("l0", "l1")


def test_deadline_crossing_action_has_no_state_mutation():
    result = executor(deadline=0.5).run("q", ScriptedPolicy([Action.scan("r0")]))
    assert result.elapsed_s == 0.0
    assert result.trace[0].status == "REJECTED_DEADLINE"
    assert result.trace[0].exposed_candidate_ids == ()


def test_identical_trace_has_exact_common_evaluator_parity():
    c0 = candidate("c0")
    relation = LocalRelation("l0", 0.5, 1.5, ("p",))
    engine = executor(
        MappingGenerator({("q", "r0"): (c0,)}),
        MappingVerifier(candidate_results={("q", "c0"): VerificationResult((relation,))}),
    )
    actions = [Action.scan("r0"), Action.verify("c0")]
    left = engine.run("q", ScriptedPolicy(actions, "policy"))
    right = engine.run("q", ScriptedPolicy(actions, "baseline"))
    assert_exact_parity(left, right)


def test_proxy_greedy_uses_only_exposed_proxy_scores():
    low, high = candidate("low", score=0.1), candidate("high", start=3.0, score=0.9)
    result = executor(MappingGenerator({("q", "r0"): (low, high)}), deadline=10.0).run("q", ScanThenProxyGreedyPolicy())
    actions = [(entry.action, entry.target_id) for entry in result.trace]
    assert actions[:2] == [("SCAN", "r0"), ("VERIFY", "high")]


def test_verification_outcome_can_change_future_public_state():
    c0 = candidate("c0")
    positive = LocalRelation("l0", 0.5, 1.5, ("p",))
    generator = MappingGenerator({("q", "r0"): (c0,)})
    pos = executor(generator, MappingVerifier(candidate_results={("q", "c0"): VerificationResult((positive,))})).run("q", ScanThenProxyGreedyPolicy())
    neg = executor(generator, MappingVerifier()).run("q", ScanThenProxyGreedyPolicy())
    assert len(pos.committed_events) == 1
    assert len(neg.committed_events) == 0
