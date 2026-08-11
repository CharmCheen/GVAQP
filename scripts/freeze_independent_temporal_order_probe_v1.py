#!/usr/bin/env python3
"""Freeze or verify the Gate-O temporal-order probe protocol.

This script intentionally refuses to authorize execution while source/hardware
bindings are incomplete. It hashes the preregistration and all inherited
operator contracts so later implementation or input binding cannot silently
change the protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/independent_temporal_order_probe_v1/contracts"
PROTOCOL = OUT / "protocol_spec.json"
ROLES = OUT / "source_roles.json"
MANIFEST = OUT / "freeze_manifest.json"

FROZEN_ASSETS = (
    "docs/INDEPENDENT_TEMPORAL_ORDER_PROBE_CONTRACT_V1.md",
    "outputs/independent_temporal_order_probe_v1/contracts/protocol_spec.json",
    "outputs/independent_temporal_order_probe_v1/contracts/source_roles.json",
    "configs/prompts/confirm_visual.yaml",
    "configs/runtime_models.yaml",
    "outputs/psvr_two_video_loop/final_proxy/FINAL_PROXY_CONFIG.json",
    "src/rc_sem/sequential.py",
    "src/rc_sem/sequential_policies.py",
    "src/rc_sem/metrics.py",
    "scripts/freeze_independent_temporal_order_probe_v1.py",
    "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py",
)

EXPECTED_POLICIES = (
    "A_CHRONOLOGICAL_FIXED_SCAN1_VERIFY1",
    "B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1",
    "C_CHRONOLOGICAL_SCAN_THEN_VERIFY",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def bisection_order(cell_count: int) -> tuple[int, ...]:
    queue = [(0, cell_count - 1)]
    order: list[int] = []
    while queue:
        left, right = queue.pop(0)
        if left > right:
            continue
        middle = (left + right) // 2
        order.append(middle)
        queue.append((left, middle - 1))
        queue.append((middle + 1, right))
    return tuple(order)


def validate_protocol(protocol: dict, roles: dict) -> None:
    if protocol["schema_version"] != "INDEPENDENT_TEMPORAL_ORDER_PROBE_PROTOCOL_V1":
        raise RuntimeError("unexpected protocol schema")
    if protocol["status"] != "PROTOCOL_FROZEN_INPUTS_UNBOUND":
        raise RuntimeError("protocol status is not the pre-input freeze state")
    if protocol["execution_authorized"] or protocol["new_oracle_calls_authorized"]:
        raise RuntimeError("pre-input protocol must not authorize execution/oracle calls")
    methods = tuple(row["policy_id"] for row in protocol["policies"])
    if methods != EXPECTED_POLICIES:
        raise RuntimeError(f"policy set/order changed: {methods}")
    if bisection_order(35)[:6] != (17, 8, 26, 3, 12, 21):
        raise RuntimeError("temporal-bisection implementation does not match frozen diagnostic")
    if protocol["metrics"]["primary_view"] != "equal_wall_clock":
        raise RuntimeError("equal wall-clock must remain primary")
    if protocol["metrics"]["equal_call_role"] != "diagnostic_only":
        raise RuntimeError("equal-call role changed")
    if protocol["decision"]["epsilon_auc_absolute"] != 0.01:
        raise RuntimeError("practical AUC threshold changed")
    if roles["status"] != "UNBOUND_EXECUTION_BLOCKED":
        raise RuntimeError("source role status changed before binding")
    for key in ("source_A", "source_B", "source_C"):
        if roles[key]["path"] != "TBD_NOT_BOUND":
            raise RuntimeError(f"{key} was partially bound outside the binding workflow")
    if roles["new_oracle_calls_authorized"] or roles["primary_policy_runs_authorized"]:
        raise RuntimeError("unbound source registry must block execution")


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def build_manifest() -> dict:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    roles = json.loads(ROLES.read_text(encoding="utf-8"))
    validate_protocol(protocol, roles)
    assets = {}
    for relative in FROZEN_ASSETS:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"missing frozen asset: {relative}")
        assets[relative] = sha256_file(path)
    payload = {
        "schema_version": "INDEPENDENT_TEMPORAL_ORDER_PROBE_FREEZE_V1",
        "status": "PROTOCOL_FROZEN_INPUTS_UNBOUND_EXECUTION_BLOCKED",
        "created_utc": protocol["created_utc"],
        "git_commit_at_protocol_freeze": protocol["git_commit_at_protocol_freeze"],
        "current_git_commit": git_output("rev-parse", "HEAD"),
        "worktree_dirty_at_manifest_write": bool(git_output("status", "--porcelain")),
        "assets": assets,
        "protocol_canonical_sha256": canonical_hash(protocol),
        "source_roles_canonical_sha256": canonical_hash(roles),
        "execution_authorized": False,
        "new_oracle_calls_authorized": False,
        "blocking_requirements": roles["execution_blockers"],
        "next_allowed_action": "bind independent source identities and target hardware without opening semantic/proxy outcomes",
    }
    payload["manifest_content_sha256_excluding_self"] = canonical_hash(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = build_manifest()
    if args.check:
        if not MANIFEST.is_file():
            raise SystemExit("freeze manifest missing")
        actual = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if actual != expected:
            raise SystemExit("freeze manifest mismatch")
        print("PASS: Gate-O protocol freeze is intact; execution remains blocked")
        return
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WROTE {MANIFEST}")
    print("STATUS: PROTOCOL_FROZEN_INPUTS_UNBOUND_EXECUTION_BLOCKED")


if __name__ == "__main__":
    main()
