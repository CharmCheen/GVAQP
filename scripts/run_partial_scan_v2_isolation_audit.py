#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from garc_eval.partial_scan_v2.artifacts import (  # noqa: E402
    atomic_json,
    atomic_text,
    build_parent_v1_manifest,
    canonical_hash,
    code_version,
    compile_launcher,
    create_v2_directories,
    freeze_v2_immutable,
    recursive_manifest,
    sha256_file,
    utc_now,
    verify_parent_v1_manifest,
    verify_v2_immutable,
)
from garc_eval.partial_scan_v2.config import (  # noqa: E402
    POLICY_IDS,
    V2_AUDITS,
    V2_BENCH,
    V2_DERIVED,
    V2_IMMUTABLE,
    V2_ISOLATION,
    V2_OUTPUT,
)
from garc_eval.partial_scan_v2.hidden_evaluator import (  # noqa: E402
    load_units,
    load_video,
)
from garc_eval.partial_scan_v2.id_redaction import (  # noqa: E402
    RunScopedIdMapper,
    new_public_run_id,
)
from garc_eval.partial_scan_v2.isolated_policy_client import (  # noqa: E402
    IsolatedPolicyClient,
    run_controlled_exception_test,
    run_sentinel_probe_worker,
)
from garc_eval.partial_scan_v2.protocol import (  # noqa: E402
    POLICY_PROTOCOL_VERSION,
    SANITIZED_ENVIRONMENT_KEYS,
)
from garc_eval.partial_scan_v2.public_schema import (  # noqa: E402
    OPAQUE_CANDIDATE_RE,
    OPAQUE_UNIT_RE,
    PUBLIC_JSON_SCHEMA,
    PublicSchemaError,
    assert_public_payload_clean,
    validate_action,
    validate_choose_action,
)
from garc_eval.partial_scan_v2.public_state_builder import (  # noqa: E402
    InternalRunState,
    build_choose_action_message,
    build_initialize_message,
    build_public_state,
)
from garc_eval.partial_scan_v2.rootfs import (  # noqa: E402
    build_policy_rootfs,
    host_isolation_configuration_audit,
    policy_bundle_hash,
)


PACKAGE = ROOT / "src/garc_eval/partial_scan_v2"
CONTRACT_DOC = ROOT / "docs/PARTIAL_SCAN_BENCHMARK_PILOT_V2_CONTRACT.md"


def contract(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["contract_hash"] = canonical_hash(result)
    return result


def frozen_code_paths() -> list[Path]:
    package = sorted(
        path
        for path in PACKAGE.iterdir()
        if path.is_file() and path.suffix in {".py", ".c"}
    )
    scripts = [
        ROOT / "scripts/run_partial_scan_v2_isolation_audit.py",
        ROOT / "scripts/run_partial_scan_v2_replay_pilot.py",
        ROOT / "scripts/run_partial_scan_v2_physical_pilot.py",
        ROOT / "scripts/run_partial_scan_v2_adversarial_final_check.py",
    ]
    return package + scripts + [CONTRACT_DOC]


def verify_code_freeze() -> dict[str, Any]:
    frozen = json.loads(
        (V2_IMMUTABLE / "v2_contracts/code_version.json").read_text()
    )
    mismatch = []
    for relative, expected in frozen["files"].items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            mismatch.append(relative)
    return {
        "status": "PASS" if not mismatch else "FAIL",
        "file_count": len(frozen["files"]),
        "mismatch_count": len(mismatch),
        "mismatches": mismatch,
    }


def prepare() -> None:
    if V2_BENCH.exists() or V2_OUTPUT.exists():
        raise RuntimeError("v2 paths already exist; do not overwrite a benchmark version")
    missing = [path for path in frozen_code_paths() if not path.is_file()]
    if missing:
        raise RuntimeError(f"v2 source set incomplete: {missing}")
    create_v2_directories()
    parent = build_parent_v1_manifest()
    atomic_json(V2_IMMUTABLE / "parent_v1_manifest.json", parent)
    contracts = {
        "inheritance_contract.json": contract(
            {
                "benchmark": "PARTIAL_SCAN_BENCHMARK_PILOT_V2",
                "parent_benchmark": "PARTIAL_SCAN_BENCHMARK_PILOT_V1",
                "parent_asset_manifest_hash": parent[
                    "parent_asset_manifest_hash"
                ],
                "v1_terminal_status": (
                    "BLOCKED_POLICY_INFORMATION_ISOLATION"
                ),
                "repair_scope": "OUT_OF_PROCESS_POLICY_ISOLATION_ONLY",
            }
        ),
        "policy_isolation_contract.json": contract(
            {
                "execution_mode": "OUT_OF_PROCESS",
                "backend": "TMPFS_CHROOT_DEDICATED_UID_SECCOMP",
                "benchmark_mount_count": 0,
                "root_filesystem": "READ_ONLY_TO_POLICY",
                "private_tmp": "PURGED_TMPFS_BACKED_DIRECTORY",
                "capability_count": 0,
                "no_new_privileges": True,
                "network_mode": "SECCOMP_DENY",
                "process_creation": "SECCOMP_DENY",
                "proc_mount": "NONE",
                "pid_namespace": (
                    "HOST_SHARED_WITHOUT_PROC_MOUNT_HOST_LIMITATION"
                ),
                "environment_keys": list(SANITIZED_ENVIRONMENT_KEYS),
                "inherited_fds": [0, 1, 2],
                "unexpected_sentinel_access_limit": 0,
                "validation_mode": (
                    "HOST_CONFIGURATION_PLUS_FOUR_FIXED_SYNTHETIC_SENTINELS"
                ),
            }
        ),
        "public_protocol_contract.json": contract(
            {
                "protocol_version": POLICY_PROTOCOL_VERSION,
                "transport": "STDIN_STDOUT_JSONL",
                "message_types": [
                    "initialize",
                    "initialized",
                    "choose_action",
                    "action",
                    "terminate",
                ],
                "public_state_serialization": "EXPLICIT_ALLOWLIST_ONLY",
                "internal_object_serialization": "PROHIBITED",
                "action_response_fields": ["unit_id"],
                "max_message_bytes": 2 * 1024 * 1024,
                "public_error_mode": "GENERIC_CODE_ONLY",
            }
        ),
        "identifier_contract.json": contract(
            {
                "run_id": "RANDOM_128_BIT",
                "video_id": "OPAQUE_RUN_SCOPED_HMAC",
                "unit_id": "OPAQUE_RUN_SCOPED_HMAC",
                "candidate_id": "OPAQUE_RUN_SCOPED_HMAC",
                "mapping_location": "EVALUATOR_MEMORY_ONLY",
                "reference_id_derivability": "PROHIBITED",
            }
        ),
        "sentinel_contract.json": contract(
            {
                "sentinel_type": "SYNTHETIC_RANDOM_TOKEN_ONLY",
                "policy_paths": {
                    "reference": "/hidden-test/reference_sentinel.json",
                    "future_cost": "/hidden-test/future_cost_sentinel.json",
                    "unscanned_output": (
                        "/hidden-test/unscanned_output_sentinel.json"
                    ),
                    "candidate_map": (
                        "/hidden-test/candidate_map_sentinel.json"
                    ),
                },
                "path_input": "PROHIBITED",
                "enumeration": "PROHIBITED",
                "shell": "PROHIBITED",
                "normalized_results": [
                    "NOT_PRESENT",
                    "ACCESS_DENIED",
                    "UNEXPECTEDLY_ACCESSIBLE",
                ],
            }
        ),
        "wallclock_contract.json": contract(
            {
                "cache_protocol": "CONTROLLED_WARM",
                "physical_budget_sec": 60.0,
                "run_count": 32,
                "latin_square": "2_VIDEOS_X_4_BLOCKS_X_4_POLICIES",
                "scan_cost": (
                    "seek+decode+model+tracker+candidate+scan_overhead"
                ),
                "e2e_cost": (
                    "public_state+policy+ipc+validation+scan+visible_replay"
                ),
                "started_action_completion": "MANDATORY",
                "method_ranking": "PROHIBITED",
            }
        ),
    }
    for name, payload in contracts.items():
        atomic_json(V2_IMMUTABLE / "v2_contracts" / name, payload)
    atomic_json(
        V2_IMMUTABLE / "v2_contracts/public_protocol_schema.json",
        PUBLIC_JSON_SCHEMA,
    )
    version = code_version(frozen_code_paths())
    atomic_json(V2_IMMUTABLE / "v2_contracts/code_version.json", version)
    for name in [
        "policy_worker.py",
        "sentinel_probe_worker.py",
        "synthetic_error_worker.py",
        "sandbox_launcher.c",
    ]:
        shutil.copy2(PACKAGE / name, V2_IMMUTABLE / "policy_bundle" / name)
    compile_launcher(
        PACKAGE / "sandbox_launcher.c",
        V2_IMMUTABLE / "policy_bundle/sandbox_launcher",
    )
    prefreeze = {
        "benchmark": "PARTIAL_SCAN_BENCHMARK_PILOT_V2",
        "created_at_utc": utc_now(),
        "parent_asset_manifest_hash": parent["parent_asset_manifest_hash"],
        "contract_hashes": {
            name: payload["contract_hash"]
            for name, payload in contracts.items()
        },
        "public_schema_sha256": sha256_file(
            V2_IMMUTABLE / "v2_contracts/public_protocol_schema.json"
        ),
        "policy_bundle_hash": policy_bundle_hash(),
        "code_version_hash": canonical_hash(version["files"]),
        "formal_execution_started": False,
    }
    prefreeze["freeze_hash"] = canonical_hash(prefreeze)
    atomic_json(V2_IMMUTABLE / "preexecution_freeze.json", prefreeze)
    immutable = freeze_v2_immutable()
    rootfs = build_policy_rootfs(force=True)
    parent_audit = verify_parent_v1_manifest()
    atomic_json(V2_AUDITS / "parent_asset_hash_audit.json", parent_audit)
    print(
        json.dumps(
            {
                "PREPARE_V2": "PASS",
                "parent_asset_manifest_hash": parent[
                    "parent_asset_manifest_hash"
                ],
                "v2_immutable_root_hash": immutable[
                    "immutable_root_hash"
                ],
                "v2_immutable_asset_count": immutable["asset_count"],
                "policy_bundle_hash": rootfs["policy_bundle_hash"],
                "isolation_backend": rootfs["rootfs_backend"],
            },
            indent=2,
        )
    )


def sample_state() -> tuple[InternalRunState, RunScopedIdMapper, dict, dict]:
    video = load_video("PSP_V0_SHORT")
    units = load_units("PSP_V0_SHORT")
    internal = InternalRunState(
        internal_video_id="PSP_V0_SHORT",
        duration_sec=float(video["duration_sec"]),
        units=units,
        budget_sec=60.0,
        visible_internal_candidate_ids=[
            "cand_internal_alpha",
            "cand_internal_beta",
        ],
        hidden_reference_event_ids={"PSP_V0_SHORT_ref_0001"},
        hidden_future_costs={str(units[0]["unit_id"]): 9.99},
        hidden_output_paths={
            str(units[0]["unit_id"]): "/synthetic-private/output"
        },
    )
    mapper = RunScopedIdMapper(new_public_run_id())
    contract_hash = json.loads(
        (
            V2_IMMUTABLE
            / "v2_contracts/public_protocol_contract.json"
        ).read_text()
    )["contract_hash"]
    initialize = build_initialize_message(internal, mapper, contract_hash)
    choose = build_choose_action_message(internal, mapper, 0)
    return internal, mapper, initialize, choose


def _schema_rejected(callback: Callable[[], Any]) -> bool:
    try:
        callback()
    except PublicSchemaError:
        return True
    return False


def isolation_audit() -> None:
    immutable = verify_v2_immutable()
    parent = verify_parent_v1_manifest()
    code = verify_code_freeze()
    if not all(
        item["status"] == "PASS" for item in [immutable, parent, code]
    ):
        raise RuntimeError("frozen input verification failed")
    build_policy_rootfs(force=True)
    host_configuration = host_isolation_configuration_audit()
    atomic_json(
        V2_AUDITS / "host_isolation_configuration_audit.json",
        host_configuration,
    )
    internal, mapper, initialize, choose = sample_state()

    public_before = build_public_state(internal, mapper, 0)
    changed = copy.deepcopy(internal)
    changed.hidden_reference_event_ids = {"different_synthetic_reference"}
    changed.hidden_future_costs = {"different": 12345.0}
    changed.hidden_output_paths = {
        "different": "/synthetic-private/different"
    }
    public_after = build_public_state(changed, mapper, 0)
    hidden_mutation_invariant = canonical_hash(public_before) == canonical_hash(
        public_after
    )
    builder_source = (
        ROOT / "src/garc_eval/partial_scan_v2/public_state_builder.py"
    ).read_text()
    public_builder_tail = builder_source.split(
        "def build_public_state", 1
    )[1]
    explicit_builder = (
        "dataclasses.asdict" not in builder_source
        and "asdict(" not in builder_source
        and "hidden_reference_event_ids" not in public_builder_tail
        and "hidden_future_costs" not in public_builder_tail
        and "hidden_output_paths" not in public_builder_tail
    )
    assert_public_payload_clean(initialize)
    assert_public_payload_clean(choose)
    known_public_unit = initialize["units"][0]["unit_id"]
    known_public_units = {
        str(unit["unit_id"]) for unit in initialize["units"]
    }
    schema_negative_results = {
        "action_extra_field": _schema_rejected(
            lambda: validate_action(
                {"unit_id": known_public_unit, "step_id": 0},
                {known_public_unit},
            )
        ),
        "action_unknown_id": _schema_rejected(
            lambda: validate_action(
                {"unit_id": "u_" + "f" * 20},
                {known_public_unit},
            )
        ),
        "state_hidden_field": _schema_rejected(
            lambda: validate_choose_action(
                {
                    **choose,
                    "state": {
                        **choose["state"],
                        "reference_events": [],
                    },
                },
                known_public_units,
            )
        ),
    }
    schema_status = (
        hidden_mutation_invariant
        and explicit_builder
        and all(schema_negative_results.values())
    )
    schema_audit = {
        "status": "PASS" if schema_status else "FAIL",
        "public_state_serialization": "EXPLICIT_ALLOWLIST_ONLY",
        "internal_object_serialization": "PROHIBITED",
        "policy_action_response_field_set": ["unit_id"],
        "initialize_field_set": sorted(initialize),
        "state_field_set": sorted(choose["state"]),
        "hidden_state_mutation_changes_public_hash": (
            not hidden_mutation_invariant
        ),
        "builder_source_excludes_internal_serialization": explicit_builder,
        "schema_negative_results": schema_negative_results,
        "initialize_message_bytes": len(
            json.dumps(initialize, separators=(",", ":")).encode()
        ),
    }
    atomic_json(V2_AUDITS / "public_state_schema_audit.json", schema_audit)

    internal_candidate_ids = list(internal.visible_internal_candidate_ids)
    public_candidate_ids = mapper.candidate_ids(internal_candidate_ids)
    other_mapper = RunScopedIdMapper(new_public_run_id())
    other_candidates = other_mapper.candidate_ids(internal_candidate_ids)
    unit_public_ids = [
        mapper.unit(str(unit["unit_id"])) for unit in internal.units
    ]
    opacity = {
        "PUBLIC_ID_FORMAT": (
            all(
                OPAQUE_CANDIDATE_RE.fullmatch(value)
                for value in public_candidate_ids
            )
            and all(OPAQUE_UNIT_RE.fullmatch(value) for value in unit_public_ids)
        ),
        "REFERENCE_ID_NOT_EMBEDDED": all(
            all(token not in value.lower() for token in ["ref", "event"])
            for value in public_candidate_ids + unit_public_ids
        ),
        "HOST_PATH_NOT_EMBEDDED": all(
            "/" not in value for value in public_candidate_ids + unit_public_ids
        ),
        "CROSS_RUN_ID_ROTATION": set(public_candidate_ids).isdisjoint(
            other_candidates
        ),
        "candidate_unique": len(public_candidate_ids)
        == len(set(public_candidate_ids)),
        "unit_unique": len(unit_public_ids) == len(set(unit_public_ids)),
    }
    id_audit = {
        "status": "PASS" if all(opacity.values()) else "FAIL",
        "checks": opacity,
        "public_candidate_id_count": len(public_candidate_ids),
        "public_unit_id_count": len(unit_public_ids),
        "mapping_persistence": "EVALUATOR_MEMORY_ONLY",
        "reverse_inference_test": "PROHIBITED_NOT_PERFORMED",
    }
    atomic_json(V2_AUDITS / "public_id_opacity_audit.json", id_audit)

    compatibility = {}
    launch_rows = []
    public_transcript_hashes = {}
    for index, policy_id in enumerate(POLICY_IDS):
        _, _, local_initialize, local_choose = sample_state()
        client = IsolatedPolicyClient(
            policy_id=policy_id,
            seed=20260724 + index,
            initialize_message=local_initialize,
            private_stderr_log=(
                V2_OUTPUT
                / "private_policy_logs"
                / f"isolation_{policy_id}.log"
            ),
        )
        try:
            selected, _ = client.choose(local_choose)
            compatibility[policy_id] = selected in {
                unit["unit_id"] for unit in local_initialize["units"]
            }
            launch_rows.append(client.security)
        finally:
            client.close("RUN_COMPLETE")
        public_transcript_hashes[policy_id] = (
            client.sandbox.transcript_hash()
        )

    sentinel_directory = (
        V2_ISOLATION
        / "private_sentinels"
        / ("sentinel_" + secrets.token_hex(8))
    )
    sentinel_directory.mkdir(parents=True)
    sentinel_names = {
        "reference_sentinel": "reference_sentinel.json",
        "future_cost_sentinel": "future_cost_sentinel.json",
        "unscanned_output_sentinel": "unscanned_output_sentinel.json",
        "candidate_map_sentinel": "candidate_map_sentinel.json",
    }
    sentinel_records = {}
    for kind, filename in sentinel_names.items():
        token = secrets.token_hex(32)
        path = sentinel_directory / filename
        atomic_json(
            path,
            {"kind": kind, "synthetic": True, "token": token},
        )
        sentinel_records[kind] = {
            "private_evaluator_path": str(path),
            "sha256": sha256_file(path),
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        }
    sentinel_report, sentinel_launch = run_sentinel_probe_worker(
        run_id=new_public_run_id(),
        private_stderr_log=(
            V2_OUTPUT / "private_policy_logs/sentinel_probe.log"
        ),
    )
    launch_rows.append(sentinel_launch)
    inaccessible = {"NOT_PRESENT", "ACCESS_DENIED"}
    sentinel_pass = {
        name: sentinel_report[name] in inaccessible
        for name in sentinel_names
    }
    unexpected_access_count = sum(
        value == "UNEXPECTEDLY_ACCESSIBLE"
        for value in sentinel_report.values()
    )
    sentinel_status = (
        all(sentinel_pass.values()) and unexpected_access_count == 0
    )
    sentinel_audit = {
        "status": "PASS" if sentinel_status else "FAIL",
        "probe_contract": "FOUR_FIXED_PATHS_NO_INPUT",
        "probe_accepts_arbitrary_path": False,
        "probe_performs_enumeration": False,
        "probe_uses_shell": False,
        "policy_fixed_paths": {
            "reference_sentinel": "/hidden-test/reference_sentinel.json",
            "future_cost_sentinel": (
                "/hidden-test/future_cost_sentinel.json"
            ),
            "unscanned_output_sentinel": (
                "/hidden-test/unscanned_output_sentinel.json"
            ),
            "candidate_map_sentinel": (
                "/hidden-test/candidate_map_sentinel.json"
            ),
        },
        "evaluator_private_sentinel_records": sentinel_records,
        "policy_probe_results": sentinel_report,
        "REFERENCE_SENTINEL_INACCESSIBILITY": (
            "PASS" if sentinel_pass["reference_sentinel"] else "FAIL"
        ),
        "FUTURE_COST_SENTINEL_INACCESSIBILITY": (
            "PASS" if sentinel_pass["future_cost_sentinel"] else "FAIL"
        ),
        "UNSCANNED_SENTINEL_INACCESSIBILITY": (
            "PASS"
            if sentinel_pass["unscanned_output_sentinel"]
            else "FAIL"
        ),
        "CANDIDATE_MAP_SENTINEL_INACCESSIBILITY": (
            "PASS" if sentinel_pass["candidate_map_sentinel"] else "FAIL"
        ),
        "NEGATIVE_CAPABILITY_TESTS_TOTAL": 4,
        "NEGATIVE_CAPABILITY_TESTS_PASSED": sum(
            sentinel_pass.values()
        ),
        "UNEXPECTED_HIDDEN_ASSET_ACCESS_COUNT": (
            unexpected_access_count
        ),
    }
    atomic_json(
        V2_AUDITS / "synthetic_sentinel_inaccessibility_audit.json",
        sentinel_audit,
    )

    controlled_error = run_controlled_exception_test(
        initialize_message=initialize,
        choose_message=choose,
        private_stderr_log=(
            V2_OUTPUT / "private_policy_logs/controlled_exception.log"
        ),
    )
    redaction_audit = {
        "status": controlled_error["status"],
        "controlled_exception_result": controlled_error,
        "PUBLIC_ERROR_PATH_REDACTION": (
            "PASS"
            if controlled_error["public_error_path_redacted"]
            else "FAIL"
        ),
        "PUBLIC_ERROR_REFERENCE_REDACTION": (
            "PASS"
            if controlled_error["public_error_reference_redacted"]
            else "FAIL"
        ),
        "PRIVATE_TRACEBACK_PRESERVED": (
            "PASS"
            if controlled_error["private_traceback_preserved"]
            else "FAIL"
        ),
    }
    atomic_json(
        V2_AUDITS / "path_exception_redaction_audit.json",
        redaction_audit,
    )

    launch_configuration_pass = all(
        row["policy_execution_mode"] == "OUT_OF_PROCESS"
        and row["policy_benchmark_mount_count"] == 0
        and row["policy_network_mode"] == "SECCOMP_DENY"
        and row["policy_capability_count"] == 0
        and row["policy_rootfs_read_only"]
        and row["policy_private_tmp"]
        and row["policy_inherited_fd_count"] == 3
        and row["policy_inherited_non_ipc_fd_count"] == 0
        and row["policy_working_directory"] == "/policy"
        and row["policy_host_pid_visibility"] == "NONE_NO_PROC_MOUNT"
        for row in launch_rows
    )
    status = all(
        [
            immutable["status"] == "PASS",
            parent["status"] == "PASS",
            code["status"] == "PASS",
            host_configuration["status"] == "PASS",
            schema_audit["status"] == "PASS",
            id_audit["status"] == "PASS",
            redaction_audit["status"] == "PASS",
            sentinel_audit["status"] == "PASS",
            all(compatibility.values()),
            launch_configuration_pass,
        ]
    )
    payload = {
        "status": "PASS" if status else "FAIL",
        "POLICY_EXECUTION_MODE": "OUT_OF_PROCESS",
        "POLICY_BENCHMARK_MOUNT_COUNT": host_configuration[
            "POLICY_BENCHMARK_MOUNT_COUNT"
        ],
        "POLICY_NETWORK_MODE": host_configuration["POLICY_NETWORK_MODE"],
        "POLICY_CAPABILITY_COUNT": host_configuration[
            "POLICY_CAPABILITY_COUNT"
        ],
        "POLICY_ENVIRONMENT_KEYS": host_configuration[
            "POLICY_ENVIRONMENT_KEYS"
        ],
        "POLICY_INHERITED_FD_COUNT": host_configuration[
            "POLICY_INHERITED_FD_COUNT"
        ],
        "POLICY_INHERITED_NON_IPC_FD_COUNT": host_configuration[
            "POLICY_INHERITED_NON_IPC_FD_COUNT"
        ],
        "POLICY_ROOTFS_READ_ONLY": host_configuration[
            "POLICY_ROOTFS_READ_ONLY"
        ],
        "POLICY_PRIVATE_TMP": host_configuration["POLICY_PRIVATE_TMP"],
        "POLICY_WORKING_DIRECTORY": host_configuration[
            "POLICY_WORKING_DIRECTORY"
        ],
        "POLICY_HOST_PID_VISIBILITY": host_configuration[
            "POLICY_HOST_PID_VISIBILITY"
        ],
        "PUBLIC_STATE_SCHEMA": schema_audit["status"],
        "PUBLIC_ID_OPACITY": id_audit["status"],
        "PUBLIC_ERROR_REDACTION": redaction_audit["status"],
        "REFERENCE_SENTINEL_INACCESSIBILITY": sentinel_audit[
            "REFERENCE_SENTINEL_INACCESSIBILITY"
        ],
        "FUTURE_COST_SENTINEL_INACCESSIBILITY": sentinel_audit[
            "FUTURE_COST_SENTINEL_INACCESSIBILITY"
        ],
        "UNSCANNED_SENTINEL_INACCESSIBILITY": sentinel_audit[
            "UNSCANNED_SENTINEL_INACCESSIBILITY"
        ],
        "CANDIDATE_MAP_SENTINEL_INACCESSIBILITY": sentinel_audit[
            "CANDIDATE_MAP_SENTINEL_INACCESSIBILITY"
        ],
        "NEGATIVE_CAPABILITY_TESTS_TOTAL": 4,
        "NEGATIVE_CAPABILITY_TESTS_PASSED": sentinel_audit[
            "NEGATIVE_CAPABILITY_TESTS_PASSED"
        ],
        "UNEXPECTED_HIDDEN_ASSET_ACCESS_COUNT": unexpected_access_count,
        "POLICY_INFORMATION_ISOLATION": "PASS" if status else "FAIL",
        "policy_interface_compatibility": compatibility,
        "launch_configuration_sample_count": len(launch_rows),
        "public_transcript_hashes": public_transcript_hashes,
        "validation_mode": (
            "HOST_CONFIGURATION_PLUS_FIXED_SYNTHETIC_SENTINELS"
        ),
        "prohibited_general_probe_used": False,
        "acceptance_rule": "ANY_UNEXPECTED_SENTINEL_ACCESS_FAILS",
    }
    atomic_json(V2_AUDITS / "policy_isolation_audit.json", payload)
    atomic_text(
        V2_OUTPUT / "reports/POLICY_ISOLATION_REPORT.md",
        "# V2 Policy Isolation Report\n\n"
        f"Policy isolation: `{payload['status']}`.\n\n"
        f"- Benchmark mounts: {payload['POLICY_BENCHMARK_MOUNT_COUNT']}\n"
        f"- Network mode: `{payload['POLICY_NETWORK_MODE']}`\n"
        f"- Capability count: {payload['POLICY_CAPABILITY_COUNT']}\n"
        f"- Inherited FDs: {payload['POLICY_INHERITED_FD_COUNT']} "
        f"(non-IPC: {payload['POLICY_INHERITED_NON_IPC_FD_COUNT']})\n"
        f"- Synthetic sentinel tests: "
        f"{payload['NEGATIVE_CAPABILITY_TESTS_PASSED']}/"
        f"{payload['NEGATIVE_CAPABILITY_TESTS_TOTAL']}\n"
        f"- Unexpected hidden-asset access: "
        f"{payload['UNEXPECTED_HIDDEN_ASSET_ACCESS_COUNT']}\n\n"
        "Validation used only host-side configuration evidence and four "
        "fixed synthetic sentinel paths. No general host probing was used.\n",
    )
    if not status:
        raise RuntimeError("v2 policy isolation audit failed")
    print(
        json.dumps(
            {
                "POLICY_INFORMATION_ISOLATION": "PASS",
                "negative_capability_tests": 4,
                "negative_capability_tests_passed": 4,
                "unexpected_hidden_asset_access_count": 0,
                "launch_configuration_samples": len(launch_rows),
            },
            indent=2,
        )
    )


def load_audit(name: str) -> dict[str, Any]:
    path = V2_AUDITS / name
    return json.loads(path.read_text()) if path.is_file() else {"status": "MISSING"}


def finalize() -> None:
    if (V2_BENCH / "evidence_manifest.json").exists():
        raise RuntimeError("v2 evidence is already frozen")
    immutable = verify_v2_immutable()
    parent = verify_parent_v1_manifest()
    code = verify_code_freeze()
    audits = {
        "isolation": load_audit("policy_isolation_audit.json"),
        "schema": load_audit("public_state_schema_audit.json"),
        "id": load_audit("public_id_opacity_audit.json"),
        "redaction": load_audit("path_exception_redaction_audit.json"),
        "sentinel": load_audit(
            "synthetic_sentinel_inaccessibility_audit.json"
        ),
        "replay": load_audit("replay_trace_audit.json"),
        "physical": load_audit("physical_trace_audit.json"),
        "deadline": load_audit("deadline_enforcement_audit.json"),
        "cache": load_audit("cache_protocol_audit.json"),
        "cost": load_audit("path_cost_support_audit.json"),
        "agreement": load_audit("replay_physical_agreement.json"),
        "final_review": load_audit("independent_final_review.json"),
    }
    hard = {
        "PARENT_ASSET_HASH_VALIDITY": parent["status"] == "PASS",
        "V2_IMMUTABLE_VALIDITY": immutable["status"] == "PASS",
        "CODE_VERSION_VALIDITY": code["status"] == "PASS",
        "PUBLIC_STATE_SCHEMA": audits["schema"]["status"] == "PASS",
        "PUBLIC_ID_OPACITY": audits["id"]["status"] == "PASS",
        "PUBLIC_ERROR_REDACTION": audits["redaction"]["status"] == "PASS",
        "SYNTHETIC_SENTINELS": (
            audits["sentinel"]["status"] == "PASS"
            and audits["sentinel"].get(
                "UNEXPECTED_HIDDEN_ASSET_ACCESS_COUNT", -1
            )
            == 0
        ),
        "POLICY_INFORMATION_ISOLATION": (
            audits["isolation"]["status"] == "PASS"
            and audits["isolation"].get(
                "UNEXPECTED_HIDDEN_ASSET_ACCESS_COUNT", -1
            )
            == 0
        ),
        "REPLAY_ISOLATED_POLICY_PATH": audits["replay"]["status"] == "PASS",
        "ACTION_TRACE_COMPLETENESS": audits["physical"]["status"] == "PASS",
        "PHYSICAL_DEADLINE_ENFORCEMENT": (
            audits["deadline"]["status"] == "PASS"
        ),
        "CONTROLLED_WARM_PATH_COST_SUPPORT": (
            audits["cache"]["status"] == "PASS"
            and audits["cost"]["status"] == "PASS"
        ),
        "REPLAY_PHYSICAL_DIRECTIONAL_AGREEMENT": (
            audits["agreement"]["status"] == "PASS"
        ),
        "INDEPENDENT_FINAL_REVIEW": (
            audits["final_review"]["status"] == "PASS"
        ),
    }
    passed = all(hard.values())
    overall = "PARTIALLY_SUPPORTED" if passed else "BLOCKED"
    next_stage = (
        "WRITE_SCOPED_PARTIAL_SCAN_METHOD_EXPERIMENT_CONTRACT"
        if passed
        else "ISOLATION_REDESIGN"
    )
    isolation_passed = hard["POLICY_INFORMATION_ISOLATION"]
    isolation = audits["isolation"]
    fields = [
        "PARENT_BENCHMARK = PARTIAL_SCAN_BENCHMARK_PILOT_V1",
        "PARENT_BENCHMARK_STATUS = BLOCKED_POLICY_INFORMATION_ISOLATION",
        "REPAIR_SCOPE = OUT_OF_PROCESS_POLICY_ISOLATION_ONLY",
        "",
        f"PARENT_ASSET_HASH_VALIDITY = {'PASS' if hard['PARENT_ASSET_HASH_VALIDITY'] else 'FAIL'}",
        "POLICY_EXECUTION_MODE = OUT_OF_PROCESS",
        f"POLICY_BENCHMARK_MOUNT_COUNT = {isolation.get('POLICY_BENCHMARK_MOUNT_COUNT', 'MISSING')}",
        f"POLICY_NETWORK_MODE = {isolation.get('POLICY_NETWORK_MODE', 'MISSING')}",
        f"POLICY_CAPABILITY_COUNT = {isolation.get('POLICY_CAPABILITY_COUNT', 'MISSING')}",
        f"POLICY_ROOTFS_READ_ONLY = {isolation.get('POLICY_ROOTFS_READ_ONLY', 'MISSING')}",
        f"POLICY_INHERITED_FD_COUNT = {isolation.get('POLICY_INHERITED_FD_COUNT', 'MISSING')}",
        f"POLICY_HOST_PID_VISIBILITY = {isolation.get('POLICY_HOST_PID_VISIBILITY', 'MISSING')}",
        "",
        f"PUBLIC_STATE_SCHEMA = {'PASS' if hard['PUBLIC_STATE_SCHEMA'] else 'FAIL'}",
        f"PUBLIC_ID_OPACITY = {'PASS' if hard['PUBLIC_ID_OPACITY'] else 'FAIL'}",
        f"PUBLIC_ERROR_REDACTION = {'PASS' if hard['PUBLIC_ERROR_REDACTION'] else 'FAIL'}",
        f"REFERENCE_SENTINEL_INACCESSIBILITY = {isolation.get('REFERENCE_SENTINEL_INACCESSIBILITY', 'MISSING')}",
        f"UNSCANNED_SENTINEL_INACCESSIBILITY = {isolation.get('UNSCANNED_SENTINEL_INACCESSIBILITY', 'MISSING')}",
        f"FUTURE_COST_SENTINEL_INACCESSIBILITY = {isolation.get('FUTURE_COST_SENTINEL_INACCESSIBILITY', 'MISSING')}",
        f"CANDIDATE_MAP_SENTINEL_INACCESSIBILITY = {isolation.get('CANDIDATE_MAP_SENTINEL_INACCESSIBILITY', 'MISSING')}",
        f"NEGATIVE_CAPABILITY_TESTS_TOTAL = {isolation.get('NEGATIVE_CAPABILITY_TESTS_TOTAL', 'MISSING')}",
        f"NEGATIVE_CAPABILITY_TESTS_PASSED = {isolation.get('NEGATIVE_CAPABILITY_TESTS_PASSED', 'MISSING')}",
        f"UNEXPECTED_HIDDEN_ASSET_ACCESS_COUNT = {isolation.get('UNEXPECTED_HIDDEN_ASSET_ACCESS_COUNT', 'MISSING')}",
        f"POLICY_INFORMATION_ISOLATION = {'PASS' if isolation_passed else 'FAIL'}",
        "",
        f"ACTION_TRACE_COMPLETENESS = {'PASS' if hard['ACTION_TRACE_COMPLETENESS'] else 'FAIL'}",
        f"PHYSICAL_DEADLINE_ENFORCEMENT = {'PASS' if hard['PHYSICAL_DEADLINE_ENFORCEMENT'] else 'FAIL'}",
        f"CONTROLLED_WARM_PATH_COST_SUPPORT = {'PASS' if hard['CONTROLLED_WARM_PATH_COST_SUPPORT'] else 'FAIL'}",
        f"REPLAY_PHYSICAL_DIRECTIONAL_AGREEMENT = {'PASS' if hard['REPLAY_PHYSICAL_DIRECTIONAL_AGREEMENT'] else 'FAIL'}",
        "",
        "REFERENCE_COMPLETENESS_STATUS = PARTIAL_OR_UNVERIFIED",
        f"OVERALL_PARTIAL_SCAN_BENCHMARK = {overall}",
        "VALID_EVENT_CLAIM = DISTINCT_EVENT_EXPOSURE_RELATIVE_TO_FROZEN_PSEUDO_REFERENCE",
        "VALID_WALLCLOCK_CLAIM = CONTROLLED_WARM_TEST_ENVIRONMENT_ONLY",
        "PILOT_METHOD_SELECTION = PROHIBITED",
        f"NEXT_ALLOWED_STAGE = {next_stage}",
    ]
    decision = (
        "# PARTIAL_SCAN_BENCHMARK_PILOT_V2 Final Decision\n\n"
        "V2 repairs only the policy execution boundary and inherits "
        "hash-identified V1 evaluator evidence. It does not rank methods.\n\n"
        "## Terminal fields\n\n```text\n"
        + "\n".join(fields)
        + "\n```\n\n"
        "Isolation validation used host-side configuration audit and four "
        "fixed synthetic sentinels only. No general host probing was used.\n"
    )
    atomic_text(V2_AUDITS / "FINAL_PILOT_DECISION.md", decision)
    atomic_text(V2_OUTPUT / "reports/FINAL_PILOT_DECISION.md", decision)
    evidence_path = V2_BENCH / "evidence_manifest.json"
    assets = recursive_manifest(V2_BENCH, excluded=[evidence_path])
    evidence = {
        "benchmark": "PARTIAL_SCAN_BENCHMARK_PILOT_V2",
        "frozen_at_utc": utc_now(),
        "asset_count": len(assets),
        "assets": assets,
        "evidence_root_hash": canonical_hash(assets),
        "scope_excludes_self": True,
        "overall": overall,
    }
    atomic_json(evidence_path, evidence)
    for path in sorted(V2_DERIVED.rglob("*"), reverse=True):
        path.chmod(0o444 if path.is_file() else 0o555)
    V2_DERIVED.chmod(0o555)
    evidence_path.chmod(0o444)
    V2_BENCH.chmod(0o555)
    print(
        json.dumps(
            {
                "FINALIZE_V2": "PASS",
                "overall": overall,
                "hard_gate_pass_count": sum(hard.values()),
                "hard_gate_count": len(hard),
                "next_allowed_stage": next_stage,
                "evidence_root_hash": evidence["evidence_root_hash"],
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "audit", "finalize"])
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "audit":
        isolation_audit()
    else:
        finalize()


if __name__ == "__main__":
    main()
