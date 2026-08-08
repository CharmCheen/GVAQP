#!/usr/bin/env python3
"""Verify Gate O after provenance-only commits.

The original freeze writer deliberately reconstructs the manifest at the
current commit.  That is correct while creating the freeze, but is not an
appropriate post-commit check: later provenance-only commits must be allowed
when every frozen scientific asset is unchanged.  This verifier checks the
freeze commit as an ancestor, then independently checks the frozen contents
and the still-blocked pre-input state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "outputs/independent_temporal_order_probe_v1/contracts"
MANIFEST_PATH = CONTRACTS / "freeze_manifest.json"
PROTOCOL_PATH = CONTRACTS / "protocol_spec.json"
SOURCE_ROLES_PATH = CONTRACTS / "source_roles.json"
BINDING_PATH = ROOT / "outputs/independent_temporal_order_probe_v1/bindings/source_a_binding.json"
POLICY_BINDING_PATH = ROOT / "outputs/independent_temporal_order_probe_v1/bindings/policy_runner_binding.json"
FREEZE_BASE = "620378413b1f5f3cd3ed304e701fc480d8d17ba3"
EXPECTED_STATUS = "PROTOCOL_FROZEN_INPUTS_UNBOUND_EXECUTION_BLOCKED"
SOURCE_A_PATH = ROOT / "data/realcam/guangzhou.mp4"
SOURCE_A_SHA256 = "4cef5c884ac879fd00bcc7962707b5f0f5e6dec6ac97e5ec8d247561ce2ec1c6"
EXPECTED_ASSETS = frozenset(
    {
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py",
        "configs/prompts/confirm_visual.yaml",
        "configs/runtime_models.yaml",
        "docs/INDEPENDENT_TEMPORAL_ORDER_PROBE_CONTRACT_V1.md",
        "outputs/independent_temporal_order_probe_v1/contracts/protocol_spec.json",
        "outputs/independent_temporal_order_probe_v1/contracts/source_roles.json",
        "outputs/psvr_two_video_loop/final_proxy/FINAL_PROXY_CONFIG.json",
        "scripts/freeze_independent_temporal_order_probe_v1.py",
        "src/rc_sem/metrics.py",
        "src/rc_sem/sequential.py",
        "src/rc_sem/sequential_policies.py",
    }
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
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing required Gate-O contract: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def git_output(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def verify_history(root: Path, manifest: dict[str, Any]) -> str:
    base = manifest.get("git_commit_at_protocol_freeze")
    if base != FREEZE_BASE:
        raise RuntimeError(f"unexpected Gate-O freeze base: {base!r}")
    if manifest.get("current_git_commit") != FREEZE_BASE:
        raise RuntimeError("freeze manifest no longer records the original freeze commit")
    try:
        git_output(root, "cat-file", "-e", f"{FREEZE_BASE}^{{commit}}")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Gate-O freeze base commit is unavailable locally") from exc
    head = git_output(root, "rev-parse", "HEAD")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", FREEZE_BASE, head],
        cwd=root,
        text=True,
        check=False,
    )
    if ancestor.returncode != 0:
        raise RuntimeError(
            "current HEAD is not a descendant of the Gate-O freeze base; refusing verification"
        )
    return head


def verify_manifest_integrity(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != "INDEPENDENT_TEMPORAL_ORDER_PROBE_FREEZE_V1":
        raise RuntimeError("unexpected freeze manifest schema")
    if manifest.get("status") != EXPECTED_STATUS:
        raise RuntimeError("freeze manifest status is not the blocked pre-input state")
    if manifest.get("execution_authorized") is not False:
        raise RuntimeError("execution_authorized must remain false")
    if manifest.get("new_oracle_calls_authorized") is not False:
        raise RuntimeError("new oracle calls must remain unauthorized")
    assets = manifest.get("assets")
    if not isinstance(assets, dict) or set(assets) != EXPECTED_ASSETS:
        raise RuntimeError("freeze manifest does not contain the exact 11 frozen assets")
    payload = dict(manifest)
    recorded = payload.pop("manifest_content_sha256_excluding_self", None)
    if recorded != canonical_hash(payload):
        raise RuntimeError("freeze manifest self-integrity hash mismatch")


def verify_frozen_assets(root: Path, manifest: dict[str, Any]) -> None:
    for relative, expected in manifest["assets"].items():
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"missing frozen asset: {relative}")
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"frozen asset SHA-256 mismatch: {relative}")


def verify_blocked_input_state(protocol: dict[str, Any], roles: dict[str, Any]) -> None:
    if protocol.get("status") != "PROTOCOL_FROZEN_INPUTS_UNBOUND":
        raise RuntimeError("protocol is not in the frozen pre-input state")
    if protocol.get("execution_authorized") is not False:
        raise RuntimeError("protocol execution authorization changed")
    if protocol.get("new_oracle_calls_authorized") is not False:
        raise RuntimeError("protocol oracle authorization changed")
    if roles.get("status") != "UNBOUND_EXECUTION_BLOCKED":
        raise RuntimeError("source roles are not in the unbound blocked state")
    if roles.get("new_oracle_calls_authorized") is not False:
        raise RuntimeError("source roles authorize oracle calls")
    if roles.get("primary_policy_runs_authorized") is not False:
        raise RuntimeError("source roles authorize policy runs")
    for source_id in ("source_A", "source_B", "source_C"):
        source = roles.get(source_id)
        if not isinstance(source, dict):
            raise RuntimeError(f"missing {source_id} role")
        for field in ("path", "video_sha256", "source_manifest_path", "capture_session_id"):
            if source.get(field) != "TBD_NOT_BOUND":
                raise RuntimeError(f"{source_id}.{field} is bound before the binding workflow")


def verify_source_a_binding(
    root: Path, manifest: dict[str, Any], binding_path: Path | None = None
) -> bool:
    """Validate the non-frozen researcher-attested Source-A sidecar, if present."""

    path = binding_path or root / BINDING_PATH.relative_to(ROOT)
    if not path.exists():
        return False
    binding = load_json(path)
    if binding.get("schema_version") != "INDEPENDENT_TEMPORAL_ORDER_PROBE_SOURCE_A_BINDING_V1":
        raise RuntimeError("unexpected Source-A binding schema")
    if binding.get("status") != "SOURCE_A_BOUND_EXECUTION_STILL_BLOCKED":
        raise RuntimeError("Source-A binding must preserve the blocked execution state")
    if binding.get("execution_authorized") is not False:
        raise RuntimeError("Source-A binding authorizes execution")
    if binding.get("new_oracle_calls_authorized") is not False:
        raise RuntimeError("Source-A binding authorizes new oracle calls")
    if binding.get("freeze_base_commit") != FREEZE_BASE:
        raise RuntimeError("Source-A binding has the wrong freeze base")
    if binding.get("freeze_manifest_sha256") != sha256_file(root / MANIFEST_PATH.relative_to(ROOT)):
        raise RuntimeError("Source-A binding does not match the freeze manifest")
    source = binding.get("source_a")
    if not isinstance(source, dict):
        raise RuntimeError("Source-A binding is missing source_a")
    expected = {
        "source_id": "guangzhou_gate_o_source_a",
        "source_role": "independent_temporal_order_probe_source_a",
        "absolute_video_path": str(SOURCE_A_PATH),
        "video_sha256": SOURCE_A_SHA256,
        "duration_seconds": 4238.25,
        "resolution": "1280x720",
        "codec": "H.264",
        "container": "MP4",
        "file_size_bytes": 967490055,
        "independence_basis": "RESEARCHER_ATTESTATION",
        "source_url": "NOT_REQUIRED_BY_RESEARCHER_ATTESTATION",
        "platform_asset_id": "NOT_REQUIRED_BY_RESEARCHER_ATTESTATION",
        "capture_session_id": "researcher_attested_guangzhou_source_a",
        "capture_session_id_kind": "RESEARCH_EXPERIMENT_IDENTIFIER_NOT_PLATFORM_CAPTURE_ID",
    }
    for key, value in expected.items():
        if source.get(key) != value:
            raise RuntimeError(f"Source-A binding mismatch: {key}")
    video_path = Path(str(source["absolute_video_path"]))
    if not video_path.is_file() or sha256_file(video_path) != SOURCE_A_SHA256:
        raise RuntimeError("bound Source-A video is unavailable or hash-mismatched")
    audit = binding.get("automatic_independence_audit")
    if not isinstance(audit, dict) or audit.get("status") != "NO_KNOWN_REPOSITORY_LINEAGE_MATCH":
        raise RuntimeError("Source-A automatic independence audit is missing or changed")
    if any(audit.get(key) is not True for key in ("no_filename_match", "no_sha256_match", "no_known_development_lineage_match")):
        raise RuntimeError("Source-A automatic independence audit did not pass")
    if any(binding.get(key) is not False for key in ("semantic_opened", "proxy_opened", "semantic_oracle_called")):
        raise RuntimeError("Source-A binding records prohibited semantic/proxy access")
    payload = dict(binding)
    recorded = payload.pop("binding_payload_sha256", None)
    if recorded != canonical_hash(payload):
        raise RuntimeError("Source-A binding self-integrity hash mismatch")
    return True


def verify_policy_runner_binding(
    root: Path, manifest: dict[str, Any], binding_path: Path | None = None
) -> bool:
    """Validate the post-freeze hash binding for the exact Gate-O runner."""

    path = binding_path or root / POLICY_BINDING_PATH.relative_to(ROOT)
    if not path.exists():
        return False
    binding = load_json(path)
    if binding.get("schema_version") != "INDEPENDENT_TEMPORAL_ORDER_PROBE_POLICY_RUNNER_BINDING_V1":
        raise RuntimeError("unexpected Gate-O policy runner binding schema")
    if binding.get("status") != "POLICY_RUNNER_BOUND_EXECUTION_STILL_BLOCKED":
        raise RuntimeError("policy runner binding must preserve blocked execution")
    if binding.get("execution_authorized") is not False or binding.get("new_oracle_calls_authorized") is not False:
        raise RuntimeError("policy runner binding authorizes execution or oracle calls")
    if binding.get("freeze_base_commit") != FREEZE_BASE:
        raise RuntimeError("policy runner binding has wrong freeze base")
    if binding.get("freeze_manifest_sha256") != sha256_file(root / MANIFEST_PATH.relative_to(ROOT)):
        raise RuntimeError("policy runner binding does not match freeze manifest")
    if tuple(binding.get("policy_ids", ())) != EXPECTED_POLICIES:
        raise RuntimeError("policy runner binding policy set/order changed")
    expected_paths = {
        "src/rc_sem/gate_o_physical.py",
        "scripts/run_independent_temporal_order_probe_v1.py",
    }
    implementation = binding.get("implementation_sha256")
    if not isinstance(implementation, dict) or set(implementation) != expected_paths:
        raise RuntimeError("policy runner binding implementation path set changed")
    for relative, expected in implementation.items():
        if sha256_file(root / relative) != expected:
            raise RuntimeError(f"policy runner implementation hash mismatch: {relative}")
    payload = dict(binding)
    recorded = payload.pop("binding_payload_sha256", None)
    if recorded != canonical_hash(payload):
        raise RuntimeError("policy runner binding self-integrity hash mismatch")
    return True


def verify_scientific_invariants(protocol: dict[str, Any]) -> None:
    policy_ids = tuple(item.get("policy_id") for item in protocol.get("policies", []))
    if policy_ids != EXPECTED_POLICIES:
        raise RuntimeError(f"frozen policy set/order changed: {policy_ids}")
    if protocol.get("metrics", {}).get("primary_view") != "equal_wall_clock":
        raise RuntimeError("equal wall-clock is no longer the primary view")
    if protocol.get("metrics", {}).get("equal_call_role") != "diagnostic_only":
        raise RuntimeError("equal-call diagnostic role changed")
    sys.path.insert(0, str(ROOT / "src"))
    from rc_sem.sequential_policies import space_filling_order

    first = space_filling_order(35)
    second = space_filling_order(35)
    if first != second or len(first) != 35 or set(first) != set(range(35)):
        raise RuntimeError("temporal-bisection is not a deterministic complete permutation")
    if first[:6] != (17, 8, 26, 3, 12, 21):
        raise RuntimeError("35-cell temporal-bisection prefix changed")


def verify(root: Path = ROOT) -> str:
    manifest = load_json(root / MANIFEST_PATH.relative_to(ROOT))
    protocol = load_json(root / PROTOCOL_PATH.relative_to(ROOT))
    roles = load_json(root / SOURCE_ROLES_PATH.relative_to(ROOT))
    verify_manifest_integrity(manifest)
    head = verify_history(root, manifest)
    verify_frozen_assets(root, manifest)
    verify_blocked_input_state(protocol, roles)
    verify_source_a_binding(root, manifest)
    verify_policy_runner_binding(root, manifest)
    verify_scientific_invariants(protocol)
    return head


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    head = verify()
    source_a_state = "Source A bound" if BINDING_PATH.exists() else "Source A unbound"
    print(f"PASS: Gate-O post-commit integrity is intact at {head}; {source_a_state}; execution remains blocked")


if __name__ == "__main__":
    main()
