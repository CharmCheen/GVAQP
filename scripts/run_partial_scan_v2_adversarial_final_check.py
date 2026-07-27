#!/usr/bin/env python3
"""Independent final review using configuration and fixed sentinels only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import secrets
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from garc_eval.partial_scan_v2.artifacts import (  # noqa: E402
    atomic_json,
    atomic_text,
    sha256_file,
    verify_parent_v1_manifest,
    verify_v2_immutable,
)
from garc_eval.partial_scan_v2.config import (  # noqa: E402
    V2_AUDITS,
    V2_IMMUTABLE,
    V2_ISOLATION,
    V2_OUTPUT,
    V2_PHYSICAL,
    V2_REPLAY,
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
    run_controlled_exception_test,
    run_sentinel_probe_worker,
)
from garc_eval.partial_scan_v2.public_schema import (  # noqa: E402
    OPAQUE_CANDIDATE_RE,
    OPAQUE_UNIT_RE,
)
from garc_eval.partial_scan_v2.public_state_builder import (  # noqa: E402
    InternalRunState,
    build_choose_action_message,
    build_initialize_message,
)
from garc_eval.partial_scan_v2.rootfs import (  # noqa: E402
    build_policy_rootfs,
    host_isolation_configuration_audit,
)


def synthetic_messages():
    video = load_video("PSP_V1_LONG")
    units = load_units("PSP_V1_LONG")
    internal = InternalRunState(
        internal_video_id="PSP_V1_LONG",
        duration_sec=float(video["duration_sec"]),
        units=units,
        budget_sec=60.0,
        visible_internal_candidate_ids=[
            "synthetic_internal_candidate_1",
            "synthetic_internal_candidate_2",
            "synthetic_internal_candidate_3",
        ],
        hidden_reference_event_ids={"synthetic_reference_marker"},
        hidden_future_costs={str(units[-1]["unit_id"]): 999.0},
        hidden_output_paths={
            str(units[-1]["unit_id"]): "/synthetic-private/runtime"
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
    candidates = mapper.candidate_ids(
        internal.visible_internal_candidate_ids
    )
    return internal, mapper, initialize, choose, candidates


def create_private_sentinels() -> dict:
    directory = (
        V2_ISOLATION
        / "private_sentinels_final_review"
        / ("sentinel_" + secrets.token_hex(8))
    )
    directory.mkdir(parents=True)
    records = {}
    for kind in [
        "reference_sentinel",
        "future_cost_sentinel",
        "unscanned_output_sentinel",
        "candidate_map_sentinel",
    ]:
        token = secrets.token_hex(32)
        path = directory / f"{kind}.json"
        atomic_json(
            path,
            {"kind": kind, "synthetic": True, "token": token},
        )
        records[kind] = {
            "private_evaluator_path": str(path),
            "sha256": sha256_file(path),
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        }
    return records


def main() -> None:
    immutable = verify_v2_immutable()
    parent = verify_parent_v1_manifest()
    build_policy_rootfs(force=True)
    host_configuration = host_isolation_configuration_audit()
    prior = json.loads(
        (V2_AUDITS / "policy_isolation_audit.json").read_text()
    )
    _, _, initialize, choose, candidates = synthetic_messages()
    sentinel_records = create_private_sentinels()
    sentinel_results, launch_configuration = run_sentinel_probe_worker(
        run_id=new_public_run_id(),
        private_stderr_log=(
            V2_OUTPUT
            / "private_policy_logs"
            / "final_review_sentinel_probe.log"
        ),
    )
    inaccessible = {"NOT_PRESENT", "ACCESS_DENIED"}
    sentinel_pass_count = sum(
        value in inaccessible for value in sentinel_results.values()
    )
    unexpected_access_count = sum(
        value == "UNEXPECTEDLY_ACCESSIBLE"
        for value in sentinel_results.values()
    )
    controlled_error = run_controlled_exception_test(
        initialize_message=initialize,
        choose_message=choose,
        private_stderr_log=(
            V2_OUTPUT
            / "private_policy_logs"
            / "final_review_controlled_exception.log"
        ),
    )

    physical_summaries = [
        json.loads(path.read_text())
        for path in sorted(V2_PHYSICAL.glob("*/run_summary.json"))
    ]
    replay_summaries = [
        json.loads(path.read_text())
        for path in sorted(V2_REPLAY.glob("*/run_summary.json"))
    ]
    all_summaries = physical_summaries + replay_summaries
    recorded_configuration_pass = (
        len(physical_summaries) == 32
        and len(replay_summaries) == 8
        and all(
            summary["security_attestation"][
                "policy_execution_mode"
            ]
            == "OUT_OF_PROCESS"
            and summary["security_attestation"][
                "policy_benchmark_mount_count"
            ]
            == 0
            and summary["security_attestation"][
                "policy_network_mode"
            ]
            == "SECCOMP_DENY"
            and summary["security_attestation"][
                "policy_capability_count"
            ]
            == 0
            and summary["security_attestation"][
                "policy_inherited_non_ipc_fd_count"
            ]
            == 0
            for summary in all_summaries
        )
    )
    other_mapper = RunScopedIdMapper(new_public_run_id())
    other_candidates = other_mapper.candidate_ids(
        [
            "synthetic_internal_candidate_1",
            "synthetic_internal_candidate_2",
            "synthetic_internal_candidate_3",
        ]
    )
    id_checks = {
        "PUBLIC_ID_FORMAT": (
            all(OPAQUE_CANDIDATE_RE.fullmatch(value) for value in candidates)
            and all(
                OPAQUE_UNIT_RE.fullmatch(unit["unit_id"])
                for unit in initialize["units"]
            )
        ),
        "REFERENCE_ID_NOT_EMBEDDED": all(
            all(token not in value.lower() for token in ["ref", "event"])
            for value in candidates
        ),
        "HOST_PATH_NOT_EMBEDDED": all("/" not in value for value in candidates),
        "CROSS_RUN_ID_ROTATION": set(candidates).isdisjoint(other_candidates),
    }
    launcher = V2_IMMUTABLE / "policy_bundle/sandbox_launcher"
    launcher_record = json.loads(
        (V2_IMMUTABLE / "immutable_manifest.json").read_text()
    )["assets"]["policy_bundle/sandbox_launcher"]
    launcher_hash_valid = (
        sha256_file(launcher) == launcher_record["sha256"]
    )
    probe_source = (
        V2_IMMUTABLE / "policy_bundle/sentinel_probe_worker.py"
    ).read_text()
    prohibited_tokens = [
        "glob(",
        "os.walk",
        "os.listdir",
        "/proc/",
        "socket.",
        "subprocess",
        "importlib",
        "readlink(",
        "symlink_to(",
    ]
    probe_scope_pass = all(token not in probe_source for token in prohibited_tokens)
    host_launch_pass = (
        host_configuration["status"] == "PASS"
        and launch_configuration["policy_benchmark_mount_count"] == 0
        and launch_configuration["policy_network_mode"] == "SECCOMP_DENY"
        and launch_configuration["policy_capability_count"] == 0
        and launch_configuration["policy_inherited_non_ipc_fd_count"] == 0
    )
    status = all(
        [
            immutable["status"] == "PASS",
            parent["status"] == "PASS",
            prior["status"] == "PASS",
            prior.get("UNEXPECTED_HIDDEN_ASSET_ACCESS_COUNT") == 0,
            host_launch_pass,
            sentinel_pass_count == 4,
            unexpected_access_count == 0,
            controlled_error["status"] == "PASS",
            recorded_configuration_pass,
            all(id_checks.values()),
            launcher_hash_valid,
            probe_scope_pass,
        ]
    )
    payload = {
        "status": "PASS" if status else "FAIL",
        "review_role": (
            "FRESH_POST_PHYSICAL_CONFIGURATION_AND_SENTINEL_REVIEW"
        ),
        "validation_mode": (
            "HOST_CONFIGURATION_PLUS_FIXED_SYNTHETIC_SENTINELS"
        ),
        "prohibited_general_probe_used": False,
        "v2_immutable_status": immutable["status"],
        "parent_asset_status": parent["status"],
        "host_configuration_status": host_configuration["status"],
        "prior_isolation_status": prior["status"],
        "fresh_private_sentinel_records": sentinel_records,
        "fresh_sentinel_results": sentinel_results,
        "NEGATIVE_CAPABILITY_TESTS_TOTAL": 4,
        "NEGATIVE_CAPABILITY_TESTS_PASSED": sentinel_pass_count,
        "UNEXPECTED_HIDDEN_ASSET_ACCESS_COUNT": unexpected_access_count,
        "controlled_error_redaction": controlled_error,
        "launch_configuration": launch_configuration,
        "recorded_run_configuration_review": {
            "status": "PASS" if recorded_configuration_pass else "FAIL",
            "physical_summary_count": len(physical_summaries),
            "replay_summary_count": len(replay_summaries),
        },
        "id_opacity_checks": id_checks,
        "launcher_hash_valid": launcher_hash_valid,
        "fixed_probe_scope_valid": probe_scope_pass,
        "acceptance_rule": "ZERO_UNEXPECTED_SENTINEL_ACCESS",
    }
    atomic_json(V2_AUDITS / "independent_final_review.json", payload)
    atomic_text(
        V2_OUTPUT / "reports/INDEPENDENT_FINAL_REVIEW.md",
        "# V2 Independent Final Review\n\n"
        f"Final review: `{payload['status']}`.\n\n"
        f"- Fixed sentinel tests: {sentinel_pass_count}/4\n"
        f"- Unexpected hidden-asset access: {unexpected_access_count}\n"
        f"- Physical summaries reviewed: {len(physical_summaries)}\n"
        f"- Replay summaries reviewed: {len(replay_summaries)}\n"
        f"- Controlled error redaction: `{controlled_error['status']}`\n\n"
        "This review used configuration evidence and fixed synthetic "
        "sentinels only; no general host probing was performed.\n",
    )
    if not status:
        raise RuntimeError("independent v2 final review failed")
    print(
        json.dumps(
            {
                "INDEPENDENT_FINAL_REVIEW": "PASS",
                "negative_capability_tests": 4,
                "negative_capability_tests_passed": sentinel_pass_count,
                "unexpected_hidden_asset_access_count": 0,
                "physical_summaries": len(physical_summaries),
                "replay_summaries": len(replay_summaries),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
