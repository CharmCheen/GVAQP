import json

import numpy as np

import pytest

from garc_eval.partial_scan_v2.error_redaction import PublicPolicyError, public_error_code
from garc_eval.partial_scan_v2.public_schema import PublicSchemaError, validate_action
from garc_eval.partial_scan_v2.physical_environment import PhysicalEnvironment
from garc_eval.partial_scan_v2.replay_environment import ReplayEnvironment
from garc_eval.partial_scan_v2.id_redaction import RunScopedIdMapper, new_public_run_id
from garc_eval.partial_scan_v2.public_state_builder import InternalRunState, build_public_state
from garc_eval.partial_scan_v2.public_state_builder import (
    build_choose_action_message,
    build_initialize_message,
)
from garc_eval.partial_scan_v2.isolated_policy_client import IsolatedPolicyClient


UNITS = {"u_00000000000000000000", "u_11111111111111111111"}


def response(step_id=17, unit_id="u_00000000000000000000", **extra):
    return {"step_id": step_id, "unit_id": unit_id, **extra}


def test_valid_response():
    assert validate_action(response(), UNITS, 17)["unit_id"] in UNITS


@pytest.mark.parametrize(
    "message",
    [
        {"unit_id": "u_00000000000000000000"},  # missing step_id
        response(16),  # stale step
        response(18),  # future step
        response(unit_id="u_ffffffffffffffffffff"),  # unknown unit
        response(extra_field=True),  # extra field
    ],
)
def test_invalid_response_schema(message):
    with pytest.raises(PublicSchemaError):
        validate_action(message, UNITS, 17)


def test_already_scanned_unit_id_is_not_currently_available():
    scanned = {"u_00000000000000000000"}
    with pytest.raises(PublicSchemaError):
        validate_action(response(), UNITS - scanned, 17)


def test_duplicate_response_is_rejected_as_unavailable_after_first_acceptance():
    first = validate_action(response(), UNITS, 17)
    assert first["unit_id"] == "u_00000000000000000000"
    with pytest.raises(PublicSchemaError):
        validate_action(response(), UNITS - {first["unit_id"]}, 17)


def test_malformed_json_is_protocol_error():
    with pytest.raises(json.JSONDecodeError):
        json.loads(b'{"step_id":17,"unit_id":')


def test_policy_timeout_is_frozen_public_error():
    assert public_error_code(PublicPolicyError("POLICY_TIMEOUT")) == "POLICY_TIMEOUT"


def test_internal_exception_is_redacted_to_frozen_code():
    assert public_error_code(RuntimeError("/host/private/traceback")) == "POLICY_PROTOCOL_ERROR"


def test_physical_environment_representative_execute_path_uses_only_supplied_unit():
    class Engine:
        detector = object()
        capture = object()
        def scan(self, unit):
            assert unit == {"unit_id": "unit-1"}
            return {"runtime": {"total_action_time_sec": 1.0}, "raw_candidates": []}
        def close(self):
            pass
    environment = object.__new__(PhysicalEnvironment)
    environment.engine = Engine()
    environment.raw_by_unit = {}
    result = environment.execute({"unit_id": "unit-1"})
    assert result["raw_candidate_count"] == 0
    assert environment.raw_by_unit == {"unit-1": []}


def test_replay_environment_representative_path_uses_constructed_protocol_only(monkeypatch, tmp_path):
    import garc_eval.partial_scan_v2.replay_environment as replay

    units = [{"unit_id": "unit-1", "start_sec": 0.0, "end_sec": 1.0}]
    class Candidates:
        candidate_id = np.array([], dtype=str)
        def __len__(self):
            return 0
    class Client:
        def __init__(self, **kwargs):
            self.available = None
        def choose(self, message, available):
            self.available = available
            return next(iter(available)), {
                "policy_request_serialize_sec": 0.0, "ipc_send_sec": 0.0,
                "policy_decision_sec": 0.0, "ipc_receive_sec": 0.0,
                "policy_response_validate_sec": 0.0,
            }
        def close(self, reason):
            self.reason = reason
        def summary(self):
            return {"client": "constructed"}
    monkeypatch.setattr(replay, "load_video", lambda _: {"duration_sec": 1.0})
    monkeypatch.setattr(replay, "load_units", lambda _: units)
    monkeypatch.setattr(replay, "IsolatedPolicyClient", Client)
    monkeypatch.setattr(replay, "transition", lambda current, selected: {"transition": "synthetic"})
    monkeypatch.setattr(replay, "replay_frozen_visible", lambda *_: (Candidates(), set()))
    environment = ReplayEnvironment(video_id="synthetic", policy_id="SEQUENTIAL", seed=1,
        budget_sec=6.0, public_contract_hash="0" * 64, private_stderr_log=tmp_path / "stderr")
    result = environment.run()
    assert len(result["trace"]) == 1
    assert result["trace"][0]["action_completed"] is True


def test_public_state_is_explicit_allowlist_not_internal_serialization():
    state = InternalRunState(
        internal_video_id="private-video", duration_sec=1.0,
        units=[{"unit_id": "private-unit", "start_sec": 0.0, "end_sec": 1.0}], budget_sec=1.0,
        hidden_reference_event_ids={"private-reference"},
        hidden_future_costs={"private-unit": 9.0},
        hidden_output_paths={"private-unit": "/private/path"},
    )
    public = build_public_state(state, RunScopedIdMapper(new_public_run_id()), 0)
    assert set(public) == {
        "step_id", "public_protocol_version", "scanned_unit_ids", "current_unit_id",
        "remaining_budget_sec", "past_action_costs_sec", "geometric_coverage",
        "revealed_observations",
    }
    assert "private-reference" not in json.dumps(public)
    assert "/private/path" not in json.dumps(public)


def test_policy_decision_uses_a_real_jsonl_child_process(tmp_path):
    internal = InternalRunState(
        internal_video_id="private-video", duration_sec=2.0,
        units=[
            {"unit_id": "internal-a", "start_sec": 0.0, "end_sec": 1.0},
            {"unit_id": "internal-b", "start_sec": 1.0, "end_sec": 2.0},
        ], budget_sec=10.0,
    )
    mapper = RunScopedIdMapper(new_public_run_id())
    client = IsolatedPolicyClient(
        policy_id="SEQUENTIAL", seed=1,
        initialize_message=build_initialize_message(internal, mapper, "0" * 64),
        private_stderr_log=tmp_path / "policy.stderr",
    )
    try:
        selected, timings = client.choose(
            build_choose_action_message(internal, mapper, 0)
        )
        assert selected == mapper.unit("internal-a")
        assert client.pid > 0
        assert set(timings) == {
            "policy_request_serialize_sec", "ipc_send_sec",
            "policy_decision_sec", "ipc_receive_sec",
            "policy_response_validate_sec",
        }
        assert client.summary()["application_attestation"] == {
            "policy_execution_mode": "OUT_OF_PROCESS",
            "policy_pid": client.pid,
            "policy_environment_keys": [
                "POLICY_PROTOCOL_VERSION", "POLICY_RUN_ID", "PYTHONUNBUFFERED",
            ],
            "transport": "STDIN_STDOUT_JSONL",
            "application_boundary_only": True,
            "capability_security": "NOT_YET_ESTABLISHED",
        }
    finally:
        client.close("RUN_COMPLETE")
