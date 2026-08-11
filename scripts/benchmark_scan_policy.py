#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from garc.scan import PublicUnit, SafeCoveragePolicy
from garc.scan.policy import POLICY_IDS, SafeCoverageConfig
from garc.scan.runner import run_scan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-manifest", required=True, type=Path)
    parser.add_argument("--max-actions", type=int, default=20)
    args = parser.parse_args()
    manifest = json.loads(args.video_manifest.read_text(encoding="utf-8"))
    units = [PublicUnit(str(row["unit_id"]), float(row["start_sec"]), float(row["end_sec"])) for row in manifest["units"]]
    result = {name: [row["unit_id"] for row in run_scan(units, args.max_actions,
              policy=SafeCoveragePolicy(SafeCoverageConfig(name)))] for name in sorted(POLICY_IDS)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
