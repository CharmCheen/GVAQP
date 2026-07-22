from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from garc_eval.psvr_runtime import ActionLedger, start_materializer_service
from garc_eval.psvr_runtime.runner import canonical_hash, strict_indexed_json_paths


ROOT = Path(__file__).resolve().parents[2]
BENCH = (
    ROOT
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run"
    / "clean_baseline_benchmark_v2_strict"
)
MATERIALIZER = BENCH / "scripts/benchmark_lib.py"
UNITS = BENCH / "frozen_inputs/units.csv"
REFERENCE = BENCH / "frozen_inputs/event_reference.csv"

RUN_CONFIG = {
    "benchmark_id": "cbbv2_514c0d360fd5b2a4b5fe",
    "run_id": "persistent_k3_boundary_test",
    "method": "test",
    "method_variant": "legal_evidence_only",
    "seed": 0,
    "horizon_budget": 2,
}


def _load_frozen_materializer():
    name = "test_frozen_psvr_materializer"
    spec = importlib.util.spec_from_file_location(name, MATERIALIZER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _public_unit_rows() -> list[dict]:
    # The frozen units table is the explicit public metadata schema accepted by
    # the service; the adversarial test below proves that it is an exact schema.
    return pd.read_csv(UNITS).to_dict("records")


@pytest.fixture(scope="module")
def materializer_service():
    service = start_materializer_service(MATERIALIZER)
    try:
        assert service.initialization["worker_uid"] == 65534
        assert service.initialization["worker_root"] == "/"
        yield service
    finally:
        service.close()


@pytest.mark.parametrize(
    "trace_rows",
    [
        [],
        [
            {"unit_id": 50, "oracle_label_after_query": "positive"},
            {"unit_id": 51, "oracle_label_after_query": "positive"},
        ],
    ],
    ids=("empty", "adjacent_positive"),
)
def test_persistent_k3_matches_frozen_materializer(materializer_service, trace_rows):
    """The persistent boundary changes process lifetime, not K3 semantics."""

    unit_rows = _public_unit_rows()
    actual = materializer_service.materialize(trace_rows, unit_rows, dict(RUN_CONFIG))

    frozen = _load_frozen_materializer()
    trace = pd.DataFrame(trace_rows, columns=["unit_id", "oracle_label_after_query"])
    units = pd.DataFrame(unit_rows)
    expected = frozen.materialize_from_trace(
        trace,
        units,
        dict(RUN_CONFIG),
        "k3_bridge_safe",
        {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0},
    ).to_dict("records")

    assert actual == expected
    if trace_rows:
        assert len(actual) == 1
        assert actual[0]["anchor_unit_ids"] == "50|51"
        assert actual[0]["verification_state"] == "oracle_confirmed"
    else:
        assert actual == []


def test_persistent_materializer_rejects_nonpublic_units_and_reference_paths(materializer_service):
    """Neither unit metadata nor run metadata may smuggle evaluator capabilities."""

    unit_rows = _public_unit_rows()
    poisoned_units = [dict(row) for row in unit_rows]
    poisoned_units[0]["reference_event_id"] = "reference_event_0000"
    with pytest.raises((RuntimeError, ValueError)):
        materializer_service.materialize([], poisoned_units, dict(RUN_CONFIG))

    poisoned_config = {**RUN_CONFIG, "reference_event_path": str(REFERENCE.resolve())}
    with pytest.raises((RuntimeError, ValueError)):
        materializer_service.materialize([], unit_rows, poisoned_config)

    malformed_units = [{"unit_id": 0, "start_time": 0.0}]
    with pytest.raises((RuntimeError, ValueError)):
        materializer_service.materialize([], malformed_units, dict(RUN_CONFIG))

    # Rejected messages must not poison the persistent service or widen its state.
    assert materializer_service.materialize([], unit_rows, dict(RUN_CONFIG)) == []


def _read_ledger(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_action_ledger_is_a_valid_hash_chain(tmp_path):
    ticks = iter((1_100_000_000, 1_300_000_000, 1_700_000_000))
    path = tmp_path / "actions.jsonl"
    ledger = ActionLedger(path, run_start_ns=1_000_000_000, clock_ns=lambda: next(ticks))
    ledger.append("RUN_STARTED", run_index=0)
    ledger.append("ADMISSION_DECISION", admitted=False)
    ledger.append("RUN_COMPLETE", deadline_met=True)

    rows = _read_ledger(path)
    assert [row["previous_event_sha256"] for row in rows] == [
        None,
        rows[0]["event_sha256"],
        rows[1]["event_sha256"],
    ]
    assert all(row["run_start_ns"] == 1_000_000_000 for row in rows)
    assert [row["elapsed_seconds"] for row in rows] == pytest.approx([0.1, 0.3, 0.7])
    for row in rows:
        claimed = row.pop("event_sha256")
        assert claimed == canonical_hash(row)


def test_action_ledger_detects_tampering_when_an_attempt_path_is_reopened(tmp_path):
    path = tmp_path / "tampered.jsonl"
    ledger = ActionLedger(path, run_start_ns=1_000_000_000, clock_ns=lambda: 1_100_000_000)
    ledger.append("RUN_STARTED", run_index=0)

    row = _read_ledger(path)[0]
    row["run_index"] = 999
    path.write_text(json.dumps(row, sort_keys=True) + "\n")

    with pytest.raises((RuntimeError, ValueError)):
        ActionLedger(path, run_start_ns=1_000_000_000, clock_ns=lambda: 1_200_000_000)
    assert len(_read_ledger(path)) == 1


def test_action_ledger_never_resumes_or_appends_to_an_existing_attempt(tmp_path):
    path = tmp_path / "existing.jsonl"
    ledger = ActionLedger(path, run_start_ns=1_000_000_000, clock_ns=lambda: 1_100_000_000)
    ledger.append("RUN_STARTED", run_index=0)
    original = path.read_bytes()

    with pytest.raises((FileExistsError, RuntimeError, ValueError)):
        ActionLedger(path, run_start_ns=1_000_000_000, clock_ns=lambda: 1_200_000_000)
    assert path.read_bytes() == original


@pytest.mark.parametrize("prefix", ("sample", "run"))
def test_strict_indexed_json_paths_excludes_sidecars_and_malformed_names(tmp_path, prefix):
    accepted = [tmp_path / f"{prefix}_002.json", tmp_path / f"{prefix}_000.json"]
    rejected = [
        tmp_path / f"{prefix}_001_oracle.json",
        tmp_path / f"{prefix}_001_snapshot.json",
        tmp_path / f"{prefix}_003.jsonl",
        tmp_path / f"{prefix}_12.json",
        tmp_path / f"{prefix}_0000.json",
        tmp_path / f"{prefix}_-01.json",
        tmp_path / f"other_001.json",
    ]
    for path in accepted + rejected:
        path.write_text("{}\n")

    assert strict_indexed_json_paths(tmp_path, prefix) == [
        tmp_path / f"{prefix}_000.json",
        tmp_path / f"{prefix}_002.json",
    ]
