#!/usr/bin/env python3
"""Post-heldout cost sensitivity for already frozen sequential policies.

This script never selects a new primary method.  It varies only the abstract
SCAN cost and replays the frozen V3, fixed 1:1, current two-stage, and ARC
policies to test whether the mechanism conclusion depends on the nominal 0.1
cost.  Results are explicitly post-heldout diagnostics.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd


def load_study(path: Path):
    spec = importlib.util.spec_from_file_location("sequential_study_for_sensitivity", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def execute(arc_root: Path, output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite {output}")
    study = load_study(Path(__file__).with_name("sequential_unknown_video_study.py"))
    benchmark = arc_root / (
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/"
        "clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py"
    )
    bench = study.load_module("sequential_sensitivity_benchmark", benchmark)
    sys.path.insert(0, str(arc_root / "src"))
    from garc_eval.arc_cached_replay import core as arc_core

    domains, _ = study.load_domains(arc_root)
    primary = domains[study.PRIMARY_DOMAIN]
    methods = (
        "ARC_TWO_STAGE_COMMON",
        "CURRENT_TWO_STAGE_RAW",
        "FIXED_SCAN1_VERIFY1",
        "DYNAMIC_ADAPTIVE_K3_VALUE_V3",
    )
    all_rows = []
    for scan_cost in (0.05, 0.10, 0.20):
        costs = study.SequentialCostConfig(
            scan_cost=scan_cost,
            verify_cost=1.0,
            scan_cell_units=10,
            scan_requires_verify_reserve=True,
        )
        profile = study.fit_profile(
            [domains[name] for name in study.DEVELOPMENT_DOMAINS], costs
        )
        rows = study.run_grid(
            domains=[primary],
            methods=methods,
            profile_for_domain=lambda domain, value=profile: value,
            seeds=study.SEEDS,
            budgets=study.BUDGETS,
            costs=costs,
            arc_core=arc_core,
            bench=bench,
            evaluator_hash=study.EXPECTED_EVALUATOR_HASH,
            output=None,
            phase="post_heldout_cost_sensitivity",
        )
        rows["scan_cost"] = scan_cost
        all_rows.append(rows)
    frame = pd.concat(all_rows, ignore_index=True)
    summary = (
        frame.groupby(["scan_cost", "method"], as_index=False)[
            [
                "anytime_event_recall_auc",
                "anytime_event_f1_auc",
                "event_recall",
                "event_f1",
                "event_precision",
            ]
        ]
        .mean()
    )
    pivot = summary.pivot(index="scan_cost", columns="method", values="anytime_event_recall_auc")
    fixed_dominates_v3 = bool(
        (
            pivot["FIXED_SCAN1_VERIFY1"]
            > pivot["DYNAMIC_ADAPTIVE_K3_VALUE_V3"] + 1e-12
        ).all()
    )
    output.mkdir(parents=True)
    frame.to_csv(output / "per_run_metrics.csv", index=False)
    summary.to_csv(output / "cost_sensitivity_summary.csv", index=False)
    decision = {
        "classification": "post_heldout_diagnostic_not_method_reselection",
        "scan_costs": [0.05, 0.10, 0.20],
        "fixed_1_to_1_anytime_recall_auc_dominates_v3_all_costs": fixed_dominates_v3,
        "decision": (
            "DYNAMIC_SELECTOR_NOT_UNIVERSALLY_SUPERIOR_FIXED_INTERLEAVE_STRONGEST_OBSERVED"
            if fixed_dominates_v3
            else "COST_SENSITIVE_INSUFFICIENT_EVIDENCE"
        ),
        "zero_budget_overrun": bool(frame.zero_budget_overrun.all()),
        "zero_unscanned_verify": bool(frame.zero_unscanned_verify.all()),
    }
    (output / "DECISION.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(decision, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--arc-root", type=Path, default=Path("/root/charm/GVAQP-arc-phys-baseline")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/sequential_unknown_video_cost_sensitivity")
    )
    args = parser.parse_args()
    execute(args.arc_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
