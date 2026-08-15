#!/usr/bin/env python3
"""CREP-Min tests: counterexample suite validity + certificates + intervals."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/crep_min"))
GATE = ROOT / "outputs/crep_min_v1"


def test_counterexample_suite_complete_and_consistent():
    suite = json.loads((GATE / "COUNTEREXAMPLES.json").read_text())
    assert len(suite) == 8
    ids = {c["id"] for c in suite}
    assert ids == {f"C{i}" for i in range(1, 9)}
    for c in suite:
        assert "W1" in c["worlds"] and "W2" in c["worlds"]
        assert c["flip"]["W1"] != c["flip"]["W2"] or "tie" in c["flip"]["W1"] + c["flip"]["W2"]
        # every witness must reference the shared log
        assert "log" in c


def test_every_closure_has_witness():
    suite = json.loads((GATE / "COUNTEREXAMPLES.json").read_text())
    closures = {c["closure"] for c in suite}
    expected = {"ACTION_SUPPORT", "CANDIDATE_CREATION", "LEGAL_ACTION_TRANSITION",
                "COMPLETION_CLOCK", "INFORMATION_FLOW", "HIDDEN_GROUPING_TRANSITION",
                "VERSION", "FUTURE_IDENTITY_LEAKAGE"}
    assert expected <= closures


def test_certificates_cover_eight_claims():
    certs = pd.read_csv(GATE / "CLAIM_CERTIFICATES.csv")
    assert len(certs) == 8
    statuses = set()
    for s in certs["replay_status"]:
        for tok in ("CERTIFIED_REPLAYABLE", "PARTIALLY_IDENTIFIABLE", "NOT_IDENTIFIABLE"):
            if tok in s:
                statuses.add(tok)
    assert {"CERTIFIED_REPLAYABLE", "PARTIALLY_IDENTIFIABLE", "NOT_IDENTIFIABLE"} <= statuses
    assert certs["version_hashes"].notna().all()


def test_partial_intervals_exact_over_queried_universe():
    pi = pd.read_csv(GATE / "PARTIAL_INTERVALS.csv")
    # width must be exactly 0 (all queried outcomes recorded -> exact)
    assert (pi["interval_width"] == 0.0).all()
    piu = pd.read_csv(GATE / "PARTIAL_INTERVALS_UNIVERSE.csv")
    assert (piu["full_universe_status"] == "NOT_IDENTIFIABLE").all()


def test_gate_route_is_go():
    m = json.loads((GATE / "CREP_GATE_METRICS.json").read_text())
    assert m["must_pass"] is True
    assert m["paper_potential_reached"] is True
    d = (GATE / "FINAL_DECISION.md").read_text()
    assert "GO_CREP_PAPER_CANDIDATE" in d
