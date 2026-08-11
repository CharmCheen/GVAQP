import pytest

from garc_eval.accelerated_event_query import oracle_v3_analyzer as analyzer
from garc_eval.accelerated_event_query.oracle_v3_manifest import canonical_hash
from garc_eval.accelerated_event_query.oracle_v3_runner import _validate_existing_record


def test_raw_validator_recomputes_model_input_identity_before_trusting_claim():
    payload = {"execution_shard": "DALI"}
    frame_set = {"frames": [{"ordinal": 0}]}
    raw = '{"label":"relevant","confidence":"high","evidence":"x"}'
    record = {
        "identity": payload,
        "input_identity_sha256": canonical_hash(payload),
        "model_input_identity_sha256": "forged",
        "frames": frame_set["frames"],
        "raw": raw,
    }
    record["record_sha256"] = canonical_hash(record)
    with pytest.raises(RuntimeError, match="model-input identity mismatch"):
        _validate_existing_record(record, payload, frame_set)


def test_attempt_accounting_joins_accepted_record_hash(monkeypatch):
    call = {
        "artifact_name": "call.json",
        "execution_shard": "DALI",
        "candidate_id": "u0",
        "sampling_fps": 2.0,
        "call_spec_sha256": "call-spec",
    }
    common = {
        "attempt_id": "attempt-0",
        "execution_session_id": "session-0",
        "artifact": "call.json",
        "call_spec_sha256": "call-spec",
        "input_identity_sha256": canonical_hash({}),
    }
    rows = [
        {**common, "event": "PREPARED", "processed_input_sha256": "processed"},
        {**common, "event": "INFERENCE_STARTED", "processed_input_sha256": "processed"},
        {**common, "event": "INFERENCE_COMPLETED", "generated_token_ids_sha256": "tokens"},
        {**common, "event": "ACCEPTED", "generated_token_ids_sha256": "tokens",
         "record_sha256": "wrong-record", "recovered_after_crash": False},
    ]
    monkeypatch.setattr(analyzer, "identity_payload", lambda *_: {})
    monkeypatch.setattr(analyzer, "_read_attempts", lambda shard: rows if shard == "DALI" else [])
    records = {"call.json": {
        "attempt_id": "attempt-0",
        "execution_session_id": "session-0",
        "processed_input_sha256": "processed",
        "generated_token_ids_sha256": "tokens",
        "record_sha256": "record",
    }}
    _, errors = analyzer._attempt_accounting(
        {}, {("u0", 2.0): {}}, {"calls": [call]}, records
    )
    assert "attempt_record_mismatch:call.json" in errors


def test_processed_or_session_mismatch_routes_to_input_binding_revision():
    decision = analyzer._decision_status(
        complete=True,
        authenticated_input_mismatch=False,
        input_binding_pass=False,
        parse_pass=True,
        label_reproducibility_pass=True,
        class_support_pass=True,
        eventization_pass=True,
    )
    assert decision == "REVISE_V3_INPUT_BINDING"


@pytest.mark.parametrize("error", [
    "attempt_raw_session_mismatch:call.json",
    "attempt_processed_input_mismatch:call.json:PREPARED",
    "attempt_generated_tokens_mismatch:call.json:ACCEPTED",
    "attempt_record_mismatch:call.json",
])
def test_authenticated_ledger_raw_join_mismatch_overrides_incomplete(error):
    mismatch = analyzer._authenticated_input_mismatch([], [error], 11, 11)
    decision = analyzer._decision_status(
        complete=False,
        authenticated_input_mismatch=mismatch,
        input_binding_pass=False,
        parse_pass=False,
        label_reproducibility_pass=False,
        class_support_pass=False,
        eventization_pass=False,
    )
    assert decision == "REVISE_V3_INPUT_BINDING"


def test_missing_or_unauthenticated_attempt_is_insufficient_not_binding_revision():
    errors = ["incomplete_attempt:call.json:{}"]
    mismatch = analyzer._authenticated_input_mismatch([], errors, 10, 11)
    decision = analyzer._decision_status(
        complete=False,
        authenticated_input_mismatch=mismatch,
        input_binding_pass=False,
        parse_pass=False,
        label_reproducibility_pass=False,
        class_support_pass=False,
        eventization_pass=False,
    )
    assert decision == "INSUFFICIENT_EVIDENCE"


def test_same_process_and_cross_replica_session_relations_are_hard_gates():
    prereg = {"determinism_groups": [
        {"group_id": "same", "kind": "same_process", "artifact_names": ["a", "b"]},
        {"group_id": "cross", "kind": "cross_replica", "artifact_names": ["a", "c"]},
    ]}
    template = {
        "model_input_identity_sha256": "model-input",
        "processed_input_sha256": "processed",
        "effective_label": "relevant",
        "raw_response_sha256": "raw",
    }
    records = {
        "a": {**template, "execution_session_id": "session-left"},
        "b": {**template, "execution_session_id": "session-left"},
        "c": {**template, "execution_session_id": "session-right"},
    }
    assert analyzer._determinism(prereg, records)["input_binding_hard_pass"] is True
    records["b"] = {**records["b"], "execution_session_id": "split-process"}
    assert analyzer._determinism(prereg, records)["input_binding_hard_pass"] is False
