"""A5 registry checks; no development runner or scientific execution."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/psvr_rollout_r2b_a5"


def test_a5_original_identity_product_is_complete_and_bound() -> None:
    manifest = json.loads((OUT / "A5_DEVELOPMENT_UNIVERSE_MANIFEST.json").read_text())
    identities = json.loads((OUT / "A5_AUTHORIZED_IDENTITY_UNIVERSE.json").read_text())
    assert manifest["expected_scientific_identity_count"] == 390
    assert identities["count"] == 390 == len(identities["identities"])
    assert len({item["identity_hash"] for item in identities["identities"]}) == 390
    assert {item["development_universe_hash"] for item in identities["identities"]} == {manifest["development_universe_hash"]}


def test_a5_runtime_rows_are_not_silently_authorized() -> None:
    audit = json.loads((OUT / "A5_RUNTIME_6_ROW_AUDIT.json").read_text())
    assert len(audit["rows"]) == 6
    assert {row["classification"] for row in audit["rows"]} == {"UNAUTHORIZED_POSTHOC_CONFIGURATION"}
    assert all(not row["authorized_scientific"] for row in audit["rows"])
