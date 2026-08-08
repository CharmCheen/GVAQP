from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_independent_temporal_order_probe_v1.py"
SPEC = importlib.util.spec_from_file_location("gate_o_verify", SCRIPT)
assert SPEC and SPEC.loader
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


def contracts() -> tuple[dict, dict, dict]:
    manifest = json.loads(verify.MANIFEST_PATH.read_text(encoding="utf-8"))
    protocol = json.loads(verify.PROTOCOL_PATH.read_text(encoding="utf-8"))
    roles = json.loads(verify.SOURCE_ROLES_PATH.read_text(encoding="utf-8"))
    return manifest, protocol, roles


def test_post_commit_verifier_accepts_descendant_head() -> None:
    manifest, _, _ = contracts()

    head = verify.verify_history(ROOT, manifest)

    assert head != verify.FREEZE_BASE


def test_post_commit_verifier_accepts_current_frozen_bundle() -> None:
    assert verify.verify(ROOT)


def test_manifest_validation_rejects_early_execution_authorization() -> None:
    manifest, _, _ = contracts()
    manifest = copy.deepcopy(manifest)
    manifest["execution_authorized"] = True

    with pytest.raises(RuntimeError, match="execution_authorized"):
        verify.verify_manifest_integrity(manifest)


def test_asset_validation_rejects_hash_mismatch() -> None:
    manifest, _, _ = contracts()
    manifest = copy.deepcopy(manifest)
    asset = next(iter(manifest["assets"]))
    manifest["assets"][asset] = "0" * 64

    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        verify.verify_frozen_assets(ROOT, manifest)


def test_input_validation_rejects_bound_source() -> None:
    _, protocol, roles = contracts()
    roles = copy.deepcopy(roles)
    roles["source_A"]["path"] = "/unexpected/video.mp4"

    with pytest.raises(RuntimeError, match="bound before"):
        verify.verify_blocked_input_state(protocol, roles)


def test_scientific_invariants_require_exact_policy_order() -> None:
    _, protocol, _ = contracts()
    protocol = copy.deepcopy(protocol)
    protocol["policies"] = list(reversed(protocol["policies"]))

    with pytest.raises(RuntimeError, match="policy set/order"):
        verify.verify_scientific_invariants(protocol)
