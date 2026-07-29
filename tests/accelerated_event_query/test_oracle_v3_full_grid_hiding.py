import os
from dataclasses import replace
from pathlib import Path

import pytest

from garc_eval.accelerated_event_query.oracle_v3_full_grid_hiding import (
    EvaluatorCapability,
    EvaluatorOnlyLabelStore,
    RuntimeVerifyHistory,
    RuntimeOSIsolationPolicy,
    VerifyCompletionAuthority,
    assert_runtime_path_isolation,
    assert_runtime_os_isolation,
    secure_evaluator_directory,
)

from .v3_helpers import unit


def test_evaluator_store_has_no_controller_lookup():
    capability = EvaluatorCapability("a" * 64)
    store = EvaluatorOnlyLabelStore([unit(0, "relevant")], capability)
    assert store.evaluator_rows(capability)[0].outcome == "relevant"
    with pytest.raises(PermissionError, match="evaluator-only"):
        store.controller_view(["V0_u0000"])
    with pytest.raises(PermissionError):
        store.evaluator_rows(EvaluatorCapability("b" * 64))


def test_runtime_accepts_only_signed_past_verify_results():
    authority = VerifyCompletionAuthority(b"x" * 32)
    history = RuntimeVerifyHistory(authority.public_verification_key())
    result = authority.issue(
        unit_id="U0", action_id="VERIFY:0", completed_at_seconds=3.0,
        authoritative_label="relevant", payload_sha256="p" * 64,
    )
    history.accept(result, current_time_seconds=3.0)
    assert history.public_rows()[0]["unit_id"] == "U0"
    with pytest.raises(PermissionError, match="unauthenticated"):
        history.accept(replace(result, authoritative_label="not_relevant"), current_time_seconds=4.0)
    future = authority.issue(
        unit_id="U1", action_id="VERIFY:1", completed_at_seconds=9.0,
        authoritative_label="unknown", payload_sha256="q" * 64,
    )
    with pytest.raises(PermissionError, match="future"):
        history.accept(future, current_time_seconds=8.0)


def test_hidden_label_permutation_cannot_change_public_state():
    authority = VerifyCompletionAuthority(b"z" * 32)
    result = authority.issue(
        unit_id="U0", action_id="VERIFY:0", completed_at_seconds=1.0,
        authoritative_label="not_relevant", payload_sha256="r" * 64,
    )
    left = RuntimeVerifyHistory(authority.public_verification_key())
    right = RuntimeVerifyHistory(authority.public_verification_key())
    left.accept(result, current_time_seconds=2.0)
    right.accept(result, current_time_seconds=2.0)
    # Exhaustive hidden stores differ, but neither object enters controller state.
    cap_a = EvaluatorCapability("1" * 64)
    cap_b = EvaluatorCapability("2" * 64)
    EvaluatorOnlyLabelStore([unit(1, "relevant")], cap_a)
    EvaluatorOnlyLabelStore([unit(1, "unknown")], cap_b)
    observations = {"scan_candidates": ["C0"], "elapsed": 2.0}
    assert left.public_state_hash(observations) == right.public_state_hash(observations)


def test_runtime_and_evaluator_paths_must_not_overlap(tmp_path):
    evaluator = tmp_path / "evaluator"
    runtime = tmp_path / "runtime"
    assert_runtime_path_isolation(
        runtime_import_roots=[runtime], evaluator_output_root=evaluator
    )
    with pytest.raises(RuntimeError, match="overlaps"):
        assert_runtime_path_isolation(
            runtime_import_roots=[tmp_path], evaluator_output_root=evaluator
        )


def test_different_uid_runtime_cannot_open_guessed_evaluator_path(tmp_path):
    if os.geteuid() != 0 or not hasattr(os, "fork"):
        pytest.skip("real UID-isolation test requires root and fork")
    os.chmod(tmp_path, 0o755)
    evaluator = tmp_path / "evaluator_only"
    sentinel = evaluator / "unit_labels.parquet"
    policy = RuntimeOSIsolationPolicy(evaluator_uid=0, runtime_uid=65534)
    secure_evaluator_directory(evaluator, policy)
    sentinel.write_bytes(b"hidden-label-sentinel")
    os.chmod(sentinel, 0o600)
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(read_fd)
            os.setgroups([])
            os.setgid(65534)
            os.setuid(65534)
            assert_runtime_os_isolation(
                evaluator_output_root=evaluator,
                guessed_evaluator_file=sentinel,
                policy=policy,
            )
            os.write(write_fd, b"PASS")
        except BaseException as exc:
            os.write(write_fd, f"FAIL:{type(exc).__name__}:{exc}".encode())
        finally:
            os.close(write_fd)
            os._exit(0)
    os.close(write_fd)
    result = os.read(read_fd, 4096).decode()
    os.close(read_fd)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0
    assert result == "PASS"
