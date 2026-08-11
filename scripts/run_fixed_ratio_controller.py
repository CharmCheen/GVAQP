#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from garc.controller.runner import ReplayControllerRunner
from garc.evaluation.replay import load_replay


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-manifest", required=True, type=Path)
    parser.add_argument("--query-config", required=True, type=Path)
    parser.add_argument("--budget-sec", required=True, type=float)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    query = yaml.safe_load(args.query_config.read_text(encoding="utf-8"))
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if query.get("mode") not in {"dry-run", "replay"}:
        raise SystemExit("only dry-run/replay is supported; no new Oracle calls are made")
    if config.get("controller_id") != "R4_FIXED_TIME_RATIO_25_75":
        raise SystemExit("only the selected R4 controller is supported")
    expected = {
        "scan_time_target_fraction": 0.25,
        "confirm_time_target_fraction": 0.75,
        "ratio_basis": "cumulative_realized_wallclock",
        "scan_primitive": "ANYTIME_LARGEST_GAP",
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise SystemExit(f"invalid frozen controller config: {key} must be {value!r}")
    replay = load_replay(args.video_manifest)
    backend = {int(key): value for key, value in replay["confirm_outcomes"].items()}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    runner = ReplayControllerRunner(replay["units"], args.budget_sec, backend,
                                    commit_path=args.output_dir / "durable_result.json",
                                    frontier_capacity=int(config["frontier_capacity"]))
    summary = runner.run()
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
