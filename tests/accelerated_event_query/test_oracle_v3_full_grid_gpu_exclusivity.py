import subprocess

import pytest

from garc_eval.accelerated_event_query.oracle_v3_full_grid_runner import (
    authenticate_gpu_exclusivity,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_analyzer import (
    _validate_gpu_exclusivity_snapshot,
)


def test_gpu_exclusivity_accepts_exact_idle_targets(monkeypatch):
    def output(command, text):
        assert text is True
        if "--query-gpu=index,uuid,utilization.gpu,memory.used" in command:
            return "1, GPU-one, 0, 4\n2, GPU-two, 0, 4\n"
        return ""

    monkeypatch.setattr(subprocess, "check_output", output)
    result = authenticate_gpu_exclusivity([1, 2])
    assert result["authenticated_exclusive_idle"] is True
    assert result["compute_contexts"] == []


@pytest.mark.parametrize(
    ("gpu_rows", "apps"),
    [
        ("1, GPU-one, 1, 4\n2, GPU-two, 0, 4\n", ""),
        ("1, GPU-one, 0, 1024\n2, GPU-two, 0, 4\n", ""),
        ("1, GPU-one, 0, 4\n2, GPU-two, 0, 4\n", "GPU-two, 999, 400\n"),
    ],
)
def test_gpu_exclusivity_rejects_changed_execution_profile(
    monkeypatch, gpu_rows, apps
):
    def output(command, text):
        assert text is True
        if "--query-gpu=index,uuid,utilization.gpu,memory.used" in command:
            return gpu_rows
        return apps

    monkeypatch.setattr(subprocess, "check_output", output)
    with pytest.raises(RuntimeError, match="exclusivity/idleness"):
        authenticate_gpu_exclusivity([1, 2])


def test_analyzer_rejects_gpu_snapshot_uuid_or_idle_mutation():
    snapshot = {
        "physical_gpu_ids": [1, 2],
        "gpus": [
            {"index": 1, "uuid": "GPU-one", "utilization_percent": 0, "memory_used_mib": 4},
            {"index": 2, "uuid": "GPU-two", "utilization_percent": 0, "memory_used_mib": 4},
        ],
        "compute_contexts": [],
        "maximum_memory_used_mib": 16,
        "maximum_utilization_percent": 0,
        "authenticated_exclusive_idle": True,
    }
    _validate_gpu_exclusivity_snapshot(
        snapshot, [1, 2], {1: "GPU-one", 2: "GPU-two"}
    )
    changed = {**snapshot, "gpus": [{**snapshot["gpus"][0], "uuid": "GPU-other"}, snapshot["gpus"][1]]}
    with pytest.raises(RuntimeError, match="UUID"):
        _validate_gpu_exclusivity_snapshot(
            changed, [1, 2], {1: "GPU-one", 2: "GPU-two"}
        )
