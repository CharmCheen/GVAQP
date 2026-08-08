#!/usr/bin/env python3
"""Gate-O launcher with a nonsemantic, fail-closed dry-run mode only.

Formal execution is deliberately unavailable from this CLI until a separate
authorization workflow supplies every remaining binding.  This prevents an
operator from using a convenience flag to turn a preflight into an experiment.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from rc_sem.gate_o_physical import nonsemantic_dry_run


def _verify_integrity() -> str:
    """Run the post-commit verifier without loading a model or a video frame."""

    path = ROOT / "scripts/verify_independent_temporal_order_probe_v1.py"
    spec = importlib.util.spec_from_file_location("gate_o_integrity", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load Gate-O integrity verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify(ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate the frozen policy configuration without inference")
    args = parser.parse_args()
    if not args.dry_run:
        raise SystemExit("formal Gate-O execution is unavailable without a separate authorization workflow")
    report = nonsemantic_dry_run(cell_count=35, execution_authorized=False)
    report["integrity_head"] = _verify_integrity()
    report["source_a_binding"] = str(ROOT / "outputs/independent_temporal_order_probe_v1/bindings/source_a_binding.json")
    report["frozen_runtime_model_config"] = str(ROOT / "configs/runtime_models.yaml")
    report["execution_output_root"] = str(ROOT / "outputs/independent_temporal_order_probe_v1/execution")
    report["remaining_required_bindings"] = ["source_B", "source_C", "hardware", "deadline", "frozen_model_artifacts"]
    report["formal_execution_started"] = False
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
