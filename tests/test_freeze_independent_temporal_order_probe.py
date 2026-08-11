from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/freeze_independent_temporal_order_probe_v1.py"
SPEC = importlib.util.spec_from_file_location("gate_o_freeze", SCRIPT)
assert SPEC and SPEC.loader
freeze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freeze)


def load_contracts() -> tuple[dict, dict]:
    protocol = json.loads(freeze.PROTOCOL.read_text(encoding="utf-8"))
    roles = json.loads(freeze.ROLES.read_text(encoding="utf-8"))
    return protocol, roles


def test_bisection_order_is_deterministic_permutation() -> None:
    order = freeze.bisection_order(35)

    assert order[:6] == (17, 8, 26, 3, 12, 21)
    assert len(order) == 35
    assert set(order) == set(range(35))


def test_manifest_blocks_execution_while_inputs_are_unbound() -> None:
    manifest = freeze.build_manifest()

    assert manifest["status"] == "PROTOCOL_FROZEN_INPUTS_UNBOUND_EXECUTION_BLOCKED"
    assert manifest["execution_authorized"] is False
    assert manifest["new_oracle_calls_authorized"] is False
    assert len(manifest["assets"]) == len(freeze.FROZEN_ASSETS)
    assert all(len(digest) == 64 for digest in manifest["assets"].values())


def test_protocol_validation_rejects_early_execution_authorization() -> None:
    protocol, roles = load_contracts()
    protocol = copy.deepcopy(protocol)
    protocol["execution_authorized"] = True

    with pytest.raises(RuntimeError, match="must not authorize execution"):
        freeze.validate_protocol(protocol, roles)
