#!/usr/bin/env python3
"""Freeze the non-semantic input-unblock pipeline before first execution."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/selected_frontier_conversion_v1/input_unblock"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    target = OUT / "input_unblock_pipeline_freeze_v1_2.json"
    if target.exists():
        raise SystemExit("freeze already exists; refusing to overwrite")
    assets = [
        ROOT / "docs/SELECTED_FRONTIER_INPUT_UNBLOCK_PROTOCOL_V1.md",
        ROOT / "docs/SELECTED_FRONTIER_INPUT_UNBLOCK_PROTOCOL_V1_AMENDMENT_1.md",
        ROOT / "docs/SELECTED_FRONTIER_INPUT_UNBLOCK_PROTOCOL_V1_AMENDMENT_2.md",
        ROOT / "docs/SELECTED_FRONTIER_CONVERSION_CALIBRATION_CONTRACT_V1.md",
        ROOT / "scripts/run_selected_frontier_input_unblock_v1.py",
        ROOT / "scripts/freeze_selected_frontier_input_unblock_v1.py",
        ROOT / "outputs/selected_frontier_conversion_v1/input_audit/input_gate_decision.json",
        ROOT / "outputs/selected_frontier_conversion_v1/input_audit/source_independence_audit.json",
        ROOT / "outputs/online_macro_activity_replication/technical_normalization/HANGZHOU_PAIR_CONTENT_IDENTITY_AUDIT.json",
        ROOT / "outputs/psvr_autonomous_research/benchmark_unblock/SOURCE_INDEPENDENCE_AUDIT.json",
    ]
    missing = [str(x.relative_to(ROOT)) for x in assets if not x.is_file()]
    if missing:
        raise SystemExit(f"missing freeze assets: {missing}")
    OUT.mkdir(parents=True, exist_ok=True)
    ffmpeg = subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True, text=True).stdout.splitlines()[0]
    old_freeze = OUT / "input_unblock_pipeline_freeze_v1_1.json"
    value = {"status": "V1_2_DISCLOSURE_FROZEN_WITH_ZERO_CANDIDATES", "created_utc": datetime.now(timezone.utc).isoformat(),
             "python": platform.python_version(), "ffmpeg": ffmpeg,
             "semantic_access_authorized": False, "model_training_authorized": False,
             "supersedes_freeze_sha256": sha(old_freeze),
             "repair_scope": "Disclosure-only amendment for an unrelated pre-pipeline semantic text-search exposure; eligibility and ordering unchanged",
             "assets": {str(x.relative_to(ROOT)): sha(x) for x in assets}}
    target.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
