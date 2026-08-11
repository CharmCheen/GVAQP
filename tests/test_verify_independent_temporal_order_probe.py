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


def test_source_a_binding_rejects_hash_mismatch(tmp_path: Path) -> None:
    manifest, _, _ = contracts()
    binding = json.loads(verify.BINDING_PATH.read_text(encoding="utf-8")) if verify.BINDING_PATH.exists() else None
    if binding is None:
        pytest.skip("Source A has not been bound yet")
    binding["source_a"]["video_sha256"] = "0" * 64
    binding["binding_payload_sha256"] = verify.canonical_hash(
        {key: value for key, value in binding.items() if key != "binding_payload_sha256"}
    )
    artifact = tmp_path / "outputs/independent_temporal_order_probe_v1/bindings/source_a_binding.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps(binding), encoding="utf-8")
    with pytest.raises(RuntimeError, match="video_sha256"):
        verify.verify_source_a_binding(ROOT, manifest, artifact)


def test_policy_runner_binding_rejects_implementation_tampering(tmp_path: Path) -> None:
    manifest, _, _ = contracts()
    binding = json.loads(verify.POLICY_BINDING_PATH.read_text(encoding="utf-8"))
    binding["implementation_sha256"]["src/rc_sem/gate_o_physical.py"] = "0" * 64
    binding["binding_payload_sha256"] = verify.canonical_hash(
        {key: value for key, value in binding.items() if key != "binding_payload_sha256"}
    )
    artifact = tmp_path / "policy_runner_binding.json"
    artifact.write_text(json.dumps(binding), encoding="utf-8")
    with pytest.raises(RuntimeError, match="implementation hash mismatch"):
        verify.verify_policy_runner_binding(ROOT, manifest, artifact)


def test_scientific_invariants_require_exact_policy_order() -> None:
    _, protocol, _ = contracts()
    protocol = copy.deepcopy(protocol)
    protocol["policies"] = list(reversed(protocol["policies"]))

    with pytest.raises(RuntimeError, match="policy set/order"):
        verify.verify_scientific_invariants(protocol)
