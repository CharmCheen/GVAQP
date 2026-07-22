import importlib.util
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/run_psvr_two_video_physical.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("test_bottleneck_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def units(count: int) -> pd.DataFrame:
    return pd.DataFrame({
        "unit_id": range(count),
        "start_time": [10.0 * index for index in range(count)],
        "end_time": [10.0 * (index + 1) for index in range(count)],
        "duration_seconds": [10.0] * count,
    })


def test_s0_is_exact_historical_uniform_order():
    runner = load_runner()
    assert runner.uniform_temporal_order(9) == [4, 1, 6, 2, 7, 0, 3, 5, 8]


def test_s1_is_reference_blind_farthest_center_order():
    runner = load_runner()
    assert runner.coverage_recovery_order(units(9)) == [4, 0, 8, 2, 6, 1, 3, 5, 7]


def test_s1_payload_needs_only_public_temporal_columns():
    runner = load_runner()
    public = units(7)
    with_forbidden = public.assign(parsed_label="positive", reference_event_id="event")
    assert runner.coverage_recovery_order(public) == runner.coverage_recovery_order(
        with_forbidden
    )


def test_stage_controller_bootstraps_then_consumes_persistent_frontier():
    runner = load_runner()
    decide = runner.stage_conditioned_should_verify
    assert not decide(
        completed_scans=9,
        coarse_cell_count=24,
        persistent_candidate_count=9,
        retained_temporal_cells=9,
    )
    assert decide(
        completed_scans=10,
        coarse_cell_count=24,
        persistent_candidate_count=10,
        retained_temporal_cells=10,
    )
    assert not decide(
        completed_scans=24,
        coarse_cell_count=24,
        persistent_candidate_count=1,
        retained_temporal_cells=1,
    )
    assert decide(
        completed_scans=24,
        coarse_cell_count=24,
        persistent_candidate_count=1,
        retained_temporal_cells=2,
    )
