"""Narrow, marker-gated recovery for interrupted V2 application runs."""
from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from .artifacts import atomic_json, utc_now


INCOMPLETE_RUN_MARKER = ".partial_scan_incomplete_run"


def prepare_destination(destination: Path, run_root: Path, repair_log: Path) -> None:
    root = run_root.resolve()
    target = destination.resolve()
    if target == root or root not in target.parents:
        raise ValueError("destination must be a child of its V2 run root")
    if target.exists():
        if (target / "run_summary.json").exists():
            raise FileExistsError("completed destination must not be overwritten")
        if not (target / INCOMPLETE_RUN_MARKER).is_file():
            raise FileExistsError("existing destination lacks incomplete-run marker")
        shutil.rmtree(target)
        _append_repair_log(repair_log, target, "REMOVED_VALID_INCOMPLETE_DESTINATION")
    target.mkdir(parents=True, exist_ok=False)
    (target / INCOMPLETE_RUN_MARKER).write_text("incomplete\n", encoding="utf-8")


def finalize_destination(destination: Path, summary: dict[str, Any]) -> None:
    marker = destination / INCOMPLETE_RUN_MARKER
    if not marker.is_file():
        raise RuntimeError("incomplete-run marker missing before finalization")
    marker.unlink()
    atomic_json(destination / "run_summary.json", summary)


def _append_repair_log(repair_log: Path, destination: Path, action: str) -> None:
    entries: list[dict[str, Any]] = []
    if repair_log.is_file():
        import json
        entries = json.loads(repair_log.read_text(encoding="utf-8"))
    entries.append({"timestamp_utc": utc_now(), "action": action, "destination": str(destination)})
    atomic_json(repair_log, entries)
