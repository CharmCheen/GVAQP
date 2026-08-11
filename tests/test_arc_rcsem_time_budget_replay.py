from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).parents[1] / "experiments" / "arc_rcsem_time_budget_replay.py"
SPEC = importlib.util.spec_from_file_location("arc_rcsem_time_budget_replay", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_call_capacity_pays_cold_load_before_any_call():
    assert MODULE.call_capacity(14.0, 14.2, 25.0) == 0
    assert MODULE.call_capacity(39.1, 14.2, 25.0) == 0
    assert MODULE.call_capacity(39.2, 14.2, 25.0) == 1


def test_call_capacity_rejects_invalid_verify_cost():
    with pytest.raises(ValueError, match="positive"):
        MODULE.call_capacity(60.0, 10.0, 0.0)


def test_same_prompt_probe_profile_is_loaded():
    probe = Path("/root/charm/GVAQP/outputs/binary_smdp_value_v1/hangzhou_physical")
    if not probe.exists():
        pytest.skip("shared physical probe not mounted")
    profile = MODULE.load_cost_profile(probe)
    assert profile["prompt_sha256"] == MODULE.PROMPT_SHA256
    assert profile["completed_call_count"] == 4
    assert profile["unique_clip_count"] == 3
    assert profile["mean_complete_path_call_seconds"] > 0
