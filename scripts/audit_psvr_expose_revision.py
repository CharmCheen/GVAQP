#!/usr/bin/env python3
"""Audit durable identity and completion of a frozen H-EXPOSE2 revision matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPOSE = ROOT / "outputs/psvr_two_video_loop/h_expose2"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def durable_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def identity(method: str, family: str, task: str, deadline: str, replicate: int) -> str:
    return f"{method}__{family}__{task}__{deadline}__replicate_{replicate:02d}"


def audit(revision_method: str) -> dict[str, Any]:
    base = EXPOSE / f"revision_{revision_method}"
    raw = base / "raw"
    config_path = base / "RESOLVED_CONFIG.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    scope = config["job_scope"]
    expected = sorted(
        identity(method, family, task, deadline, int(replicate))
        for method, family, task, deadline, replicate in product(
            scope["methods"], scope["families"], scope["tasks"],
            scope["deadlines"], scope["replicates"]
        )
    )
    expected_set = set(expected)
    complete_paths = sorted(raw.glob("*/attempt_*/complete.json"))
    failed_paths = sorted(raw.glob("*/attempt_*/failed.json"))
    started_paths = sorted(raw.glob("*/attempt_*/started.json"))
    by_cell: dict[str, list[Path]] = {}
    invalid: list[dict[str, Any]] = []
    missing_snapshots: list[dict[str, str]] = []
    schedule_incomplete: list[str] = []
    deadline_misses: list[str] = []
    replays = 0
    future_accesses = 0
    visibility_violations = 0

    for path in complete_paths:
        cell = path.parents[1].name
        by_cell.setdefault(cell, []).append(path)
        reasons: list[str] = []
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            invalid.append({"cell": cell, "path": str(path), "reasons": [f"unreadable_json:{exc}"]})
            continue
        started_path = path.with_name("started.json")
        started = json.loads(started_path.read_text(encoding="utf-8")) if started_path.is_file() else {}
        job = row.get("job", {})
        expected_cell = identity(
            str(job.get("method", "")), str(job.get("family", "")),
            str(job.get("task_id", "")), str(job.get("deadline_name", "")),
            int(job.get("replicate", -1)),
        )
        if row.get("status") != "ok":
            reasons.append("status_not_ok")
        if cell not in expected_set or expected_cell != cell:
            reasons.append("cell_identity_mismatch")
        if row.get("config_hash") != config.get("config_hash"):
            reasons.append("complete_config_hash_mismatch")
        if started.get("config_hash") != config.get("config_hash"):
            reasons.append("started_config_hash_mismatch")
        if started.get("job") != job:
            reasons.append("started_complete_job_mismatch")
        if row.get("run_id") != started.get("run_id"):
            reasons.append("started_complete_run_id_mismatch")
        if int(row.get("scan_actions", -1)) != int(row.get("target_scan_actions", -2)) or int(
            row.get("verify_opportunities", -1)
        ) != int(row.get("target_verify_opportunities", -2)):
            schedule_incomplete.append(cell)
        if not bool(row.get("deadline_met")):
            deadline_misses.append(cell)
        replays += int(row.get("cache_replay_calls", 0))
        future_accesses += int(row.get("future_proxy_accesses", 0))
        visibility_violations += int(row.get("candidate_observation_violations", 0))
        visibility_violations += int(row.get("reference_visibility_violations", 0))
        checkpoints = row.get("checkpoints", [])
        checkpoint_paths = [Path(str(point.get("snapshot_path", ""))) for point in checkpoints]
        final_snapshot = Path(str(row.get("final_snapshot_path", "")))
        for snapshot in [*checkpoint_paths, final_snapshot]:
            if not snapshot.is_file():
                missing_snapshots.append({"cell": cell, "path": str(snapshot)})
        if not checkpoints or not final_snapshot.is_file() or final_snapshot != checkpoint_paths[-1]:
            reasons.append("invalid_final_snapshot_reference")
        ledger = Path(str(row.get("action_ledger_path", "")))
        if not ledger.is_file() or sha256_file(ledger) != row.get("action_ledger_sha256"):
            reasons.append("invalid_action_ledger_identity")
        if reasons:
            invalid.append({"cell": cell, "path": str(path), "reasons": reasons})

    present = set(by_cell) & expected_set
    duplicates = {cell: [str(path) for path in paths] for cell, paths in by_cell.items() if len(paths) > 1}
    unexpected = sorted(set(by_cell) - expected_set)
    missing = sorted(expected_set - present)
    failed = []
    for path in failed_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            payload = {"error": f"unreadable_json:{exc}"}
        failed.append({"cell": path.parents[1].name, "path": str(path), "payload": payload})
    invalid_cells = sorted({row["cell"] for row in invalid})
    valid_cells = sorted(present - set(invalid_cells))
    result = {
        "audit_id": "H_EXPOSE2_REVISION_RESUME_AUDIT_V1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_directory": str(base),
        "experiment_id": config.get("experiment_id"),
        "config_hash": config.get("config_hash"),
        "expected_cells": len(expected),
        "expected_cell_ids": expected,
        "completed_cells": len(present),
        "valid_cells": len(valid_cells),
        "valid_cell_ids": valid_cells,
        "missing_cells": missing,
        "duplicate_cells": duplicates,
        "unexpected_cells": unexpected,
        "failed_cells": failed,
        "invalid_cells": invalid,
        "started_artifacts": len(started_paths),
        "complete_artifacts": len(complete_paths),
        "failed_artifacts": len(failed_paths),
        "deadline_misses": sorted(set(deadline_misses)),
        "incomplete_schedules": sorted(set(schedule_incomplete)),
        "replays": replays,
        "future_accesses": future_accesses,
        "visibility_violations": visibility_violations,
        "missing_snapshots": missing_snapshots,
        "resume_required": bool(missing or invalid_cells),
        "artifact_identity_gate": "PASS" if not (missing or duplicates or unexpected or invalid) else "FAIL",
        "heldout_opened": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision-method", required=True)
    parser.add_argument("--completion-gate", action="store_true")
    args = parser.parse_args()
    result = audit(args.revision_method)
    base = EXPOSE / f"revision_{args.revision_method}"
    durable_json(base / "RESUME_AUDIT.json", result)
    if args.completion_gate:
        gate = {
            "gate_id": "H_EXPOSE2_REVISION_COMPLETION_GATE_V1",
            "experiment_id": result["experiment_id"],
            "expected_cells": result["expected_cells"],
            "completed_cells": result["completed_cells"],
            "valid_cells": result["valid_cells"],
            "schedules_complete": result["expected_cells"] - len(result["incomplete_schedules"]),
            "deadline_misses": len(result["deadline_misses"]),
            "failed_cells": len(result["failed_cells"]),
            "duplicate_cells": len(result["duplicate_cells"]),
            "replays": result["replays"],
            "future_accesses": result["future_accesses"],
            "visibility_violations": result["visibility_violations"],
            "missing_snapshots": len(result["missing_snapshots"]),
            "heldout_opened": False,
        }
        gate["REVISION_COMPLETION_GATE"] = "PASS" if (
            gate["expected_cells"] == gate["completed_cells"] == gate["valid_cells"] == 72
            and gate["schedules_complete"] == 72
            and gate["failed_cells"] == gate["duplicate_cells"] == 0
            and gate["replays"] == gate["future_accesses"] == gate["visibility_violations"] == 0
            and gate["missing_snapshots"] == 0
        ) else "FAIL"
        durable_json(base / "REVISION_COMPLETION_GATE.json", gate)
        result["completion_gate"] = gate
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
