from garc_eval.mf_psvr.candidate_identity import (
    CandidateIdentity,
    bind_track_witness,
)


def test_candidate_identity_keeps_unit_suffix_for_frozen_policy_compatibility():
    identity = CandidateIdentity("V0", "Q1", unit_id=17, track_id=4)
    assert identity.candidate_id == "V0_Q1_track_000004_unit_000017"
    assert int(identity.candidate_id.split("_")[-1]) == 17


def test_two_track_counterfactual_cannot_mutate_bound_witness():
    bindings: dict[int, int] = {}
    first = bind_track_witness(bindings, unit_id=9, proposed_track_id=101)
    # A later global-percentile update makes track 202 the current argmax.
    # Candidate identity must stay attached to the original causal evidence.
    later = bind_track_witness(bindings, unit_id=9, proposed_track_id=202)
    assert first == 101
    assert later == 101
    assert CandidateIdentity("V1", "Q2", 9, later) == CandidateIdentity(
        "V1", "Q2", 9, first
    )

