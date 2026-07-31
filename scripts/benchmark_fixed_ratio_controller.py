#!/usr/bin/env python3
"""Benchmark selected R4 over replay manifests and wall-clock budgets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from garc.controller.runner import ReplayControllerRunner
from garc.evaluation.replay import load_replay


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-manifest", required=True, type=Path)
    parser.add_argument("--budgets-sec", nargs="+", type=float, default=[30, 60, 120, 240])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    replay = load_replay(args.video_manifest)
    backend = {int(key): value for key, value in replay["confirm_outcomes"].items()}
    summaries = []
    for budget in args.budgets_sec:
        commit = args.output.parent / f".{args.output.stem}.budget_{budget:g}.commit.json"
        summaries.append({"budget_sec": budget, **ReplayControllerRunner(
            replay["units"], budget, backend, commit_path=commit).run()})
        commit.unlink(missing_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summaries, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
