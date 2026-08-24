#!/usr/bin/env python3
"""Run oracle-agnostic DATB-SV over an existing replay manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from garc.datb_sv import DatbSVConfig, DatbSVReplayRunner
from garc.evaluation.replay import load_replay


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", required=True, type=Path)
    parser.add_argument("--deadline-sec", required=True, type=float)
    parser.add_argument("--scan-cost-upper-sec", required=True, type=float)
    parser.add_argument("--verify-cost-upper-sec", required=True, type=float)
    parser.add_argument("--commit-reserve-sec", type=float, default=0.0)
    parser.add_argument("--frontier-capacity", type=int, default=10)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    replay = load_replay(args.replay)
    metadata = replay.get("metadata", {})
    if metadata.get("requires_new_inference") is True:
        raise SystemExit("CPU replay refuses manifests that require new inference")
    backend = {int(key): value for key, value in replay["confirm_outcomes"].items()}
    config = DatbSVConfig(
        deadline_sec=args.deadline_sec,
        scan_cost_upper_sec=args.scan_cost_upper_sec,
        verify_cost_upper_sec=args.verify_cost_upper_sec,
        commit_reserve_sec=args.commit_reserve_sec,
        frontier_capacity=args.frontier_capacity,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    runner = DatbSVReplayRunner(
        replay["units"],
        backend,
        config,
        commit_path=args.output_dir / "durable_result.json",
        oracle_metadata=metadata.get("oracle", {}),
    )
    summary = runner.run()
    summary.update({
        "replay_sha256": sha256(args.replay),
        "replay_source_unchanged": True,
    })
    (args.output_dir / "trace.json").write_text(
        json.dumps(runner.trace, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

