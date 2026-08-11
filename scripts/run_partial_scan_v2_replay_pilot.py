#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from garc_eval.partial_scan_v2.artifacts import (  # noqa: E402
    atomic_json,
    atomic_text,
    verify_parent_v1_manifest,
    verify_v2_immutable,
)
from garc_eval.partial_scan_v2.config import (  # noqa: E402
    POLICY_IDS,
    REPLAY_BUDGET_SEC,
    SEED,
    V2_AUDITS,
    V2_IMMUTABLE,
    V2_OUTPUT,
    V2_REPLAY,
)
from garc_eval.partial_scan_v2.hidden_evaluator import load_videos  # noqa: E402
from garc_eval.partial_scan_v2.replay_environment import (  # noqa: E402
    ReplayEnvironment,
)
from garc_eval.partial_scan_v2.run_recovery import (  # noqa: E402
    finalize_destination,
    prepare_destination,
)


def public_contract_hash() -> str:
    return json.loads(
        (
            V2_IMMUTABLE
            / "v2_contracts/public_protocol_contract.json"
        ).read_text()
    )["contract_hash"]


def run_one(video_id: str, policy_id: str) -> None:
    if verify_v2_immutable()["status"] != "PASS":
        raise RuntimeError("v2 immutable verification failed")
    if verify_parent_v1_manifest()["status"] != "PASS":
        raise RuntimeError("parent asset verification failed")
    destination = V2_REPLAY / f"{video_id}_{policy_id}"
    prepare_destination(destination, V2_REPLAY, V2_OUTPUT / "repair_log.json")
    environment = ReplayEnvironment(
        video_id=video_id,
        policy_id=policy_id,
        seed=SEED + POLICY_IDS.index(policy_id),
        budget_sec=REPLAY_BUDGET_SEC,
        public_contract_hash=public_contract_hash(),
        private_stderr_log=(
            V2_OUTPUT
            / "private_policy_logs"
            / f"replay_{video_id}_{policy_id}.log"
        ),
    )
    result = environment.run()
    result["summary"]["evaluator_pid"] = os.getpid()
    atomic_text(
        destination / "action_trace.jsonl",
        "".join(
            json.dumps(
                row, sort_keys=True, ensure_ascii=False, allow_nan=False
            )
            + "\n"
            for row in result["trace"]
        ),
    )
    finalize_destination(destination, result["summary"])
    print(
        json.dumps(
            {
                "REPLAY_RUN": "PASS",
                "video_id": video_id,
                "policy_id": policy_id,
                "actions": len(result["trace"]),
            }
        ),
        flush=True,
    )


def run_all() -> None:
    logs = V2_OUTPUT / "replay_run_logs"
    logs.mkdir(parents=True, exist_ok=True)
    for video_id in load_videos().video_id.astype(str):
        for policy_id in POLICY_IDS:
            destination = V2_REPLAY / f"{video_id}_{policy_id}"
            if (destination / "run_summary.json").is_file():
                continue
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "run",
                "--video-id",
                video_id,
                "--policy-id",
                policy_id,
            ]
            with (
                logs / f"{video_id}_{policy_id}.log"
            ).open("w", encoding="utf-8") as handle:
                completed = subprocess.run(
                    command,
                    cwd=ROOT,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                )
            if completed.returncode:
                raise RuntimeError(
                    f"replay child failed: {video_id} {policy_id}"
                )
            print(f"REPLAY_ALL {video_id} {policy_id}", flush=True)
    audit()


def read_trace(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def audit() -> None:
    expected = {
        f"{video_id}_{policy_id}"
        for video_id in load_videos().video_id.astype(str)
        for policy_id in POLICY_IDS
    }
    summaries = []
    rows = []
    actual = set()
    for path in sorted(V2_REPLAY.glob("*/run_summary.json")):
        run_name = path.parent.name
        actual.add(run_name)
        summaries.append(json.loads(path.read_text()))
        rows.extend(read_trace(path.parent / "action_trace.jsonl"))
    required = {
        "policy_request_serialize_sec",
        "ipc_send_sec",
        "policy_decision_sec",
        "ipc_receive_sec",
        "policy_response_validate_sec",
        "environment_action_validate_sec",
        "seek_time_sec",
        "decode_time_sec",
        "model_time_sec",
        "tracker_time_sec",
        "candidate_time_sec",
        "visible_subset_replay_time_sec",
        "total_scan_action_time_sec",
        "total_scheduler_step_time_sec",
        "action_started",
        "action_completed",
    }
    schema_complete = bool(rows) and all(required.issubset(row) for row in rows)
    application = [
        summary["application_attestation"] for summary in summaries
    ]
    application_boundary_same = bool(application) and all(
        row["policy_execution_mode"] == "OUT_OF_PROCESS"
        and row["transport"] == "STDIN_STDOUT_JSONL"
        and row["application_boundary_only"]
        and row["capability_security"] == "NOT_YET_ESTABLISHED"
        for row in application
    )
    unique_policy_processes = len(
        {summary["policy_pid"] for summary in summaries}
    )
    status = (
        actual == expected
        and schema_complete
        and application_boundary_same
        and unique_policy_processes == len(expected)
        and all(row["action_completed"] for row in rows)
    )
    payload = {
        "status": "PASS" if status else "FAIL",
        "expected_run_count": len(expected),
        "actual_run_count": len(summaries),
        "completed_action_count": len(rows),
        "trace_schema_complete": schema_complete,
        "same_application_policy_client_as_physical_contract": application_boundary_same,
        "capability_security": "NOT_YET_ESTABLISHED",
        "fresh_policy_process_count": unique_policy_processes,
        "result_class": "LOGICAL_REPLAY_WITH_ESTIMATED_SCAN_COST",
        "method_ranking_interpretation": "PROHIBITED",
    }
    atomic_json(V2_AUDITS / "replay_trace_audit.json", payload)
    atomic_text(
        V2_OUTPUT / "reports/REPLAY_ISOLATION_REPORT.md",
        "# V2 Replay Isolation Report\n\n"
        f"Replay trace audit: `{payload['status']}`.\n\n"
        f"- Runs: {payload['actual_run_count']}/{payload['expected_run_count']}\n"
        f"- Completed logical actions: {payload['completed_action_count']}\n"
        f"- Fresh isolated policy processes: "
        f"{payload['fresh_policy_process_count']}\n"
        "- Replay uses the same application process boundary as Physical.\n"
        "- Capability security is not established by this audit.\n",
    )
    if not status:
        raise RuntimeError("v2 replay audit failed")
    print(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--video-id", required=True)
    run.add_argument("--policy-id", choices=POLICY_IDS, required=True)
    sub.add_parser("all")
    sub.add_parser("audit")
    args = parser.parse_args()
    if args.command == "run":
        run_one(args.video_id, args.policy_id)
    elif args.command == "all":
        run_all()
    else:
        audit()


if __name__ == "__main__":
    main()
