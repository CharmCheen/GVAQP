#!/usr/bin/env python3
"""Freeze strict benchmark semantics and audit planner-facing inputs."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PACK = Path(__file__).resolve().parents[1]
BLOCKED_V2 = PACK.parent / "clean_baseline_benchmark_v2"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def main() -> None:
    analysis = PACK / "analysis"; evaluator = PACK / "evaluator"; configs = PACK / "configs"
    analysis.mkdir(exist_ok=True); evaluator.mkdir(exist_ok=True); configs.mkdir(exist_ok=True)
    manifest = json.loads((PACK / "BENCHMARK_MANIFEST.json").read_text())
    public_rows = []
    for relative in ["frozen_inputs/units.csv", "frozen_inputs/public_proxy.csv"]:
        frame = pd.read_csv(PACK / relative, nrows=0)
        forbidden = [column for column in frame.columns if any(token in column.lower() for token in ["label", "oracle", "reference", "ground_truth"])]
        public_rows.append({"path": relative, "forbidden_columns": "|".join(forbidden), "status": "PASS" if not forbidden else "FAIL"})
    pd.DataFrame(public_rows).to_csv(evaluator / "pre_execution_planner_leakage_audit.csv", index=False)
    if any(row["status"] != "PASS" for row in public_rows):
        raise RuntimeError("Planner-facing strict input contains a forbidden evaluator column")

    old = pd.read_csv(BLOCKED_V2 / "frozen_inputs/oracle_observations.csv")[["unit_id", "parsed_label", "event_start_absolute", "event_end_absolute"]]
    new = pd.read_csv(PACK / "frozen_inputs/oracle_observations.csv")[["unit_id", "parsed_label", "event_start_absolute", "event_end_absolute"]]
    diff = old.merge(new, on="unit_id", suffixes=("_blocked_v2", "_strict"), validate="one_to_one")
    diff["label_changed"] = diff.parsed_label_blocked_v2.astype(str) != diff.parsed_label_strict.astype(str)
    diff["boundaries_changed"] = (
        diff.event_start_absolute_blocked_v2.fillna("").astype(str) != diff.event_start_absolute_strict.fillna("").astype(str)
    ) | (
        diff.event_end_absolute_blocked_v2.fillna("").astype(str) != diff.event_end_absolute_strict.fillna("").astype(str)
    )
    diff.to_csv(analysis / "BLOCKED_V2_STRICT_ORACLE_DIFF.csv", index=False)
    old_ref = pd.read_csv(BLOCKED_V2 / "frozen_inputs/event_reference.csv")
    new_ref = pd.read_csv(PACK / "frozen_inputs/event_reference.csv")
    old_semantic = old_ref.drop(columns=["benchmark_id"], errors="ignore").to_csv(index=False, lineterminator="\n")
    new_semantic = new_ref.drop(columns=["benchmark_id"], errors="ignore").to_csv(index=False, lineterminator="\n")
    atomic_text(analysis / "BLOCKED_V2_STRICT_REFERENCE_DIFF.md", f"# Blocked-v2 to strict reference diff\n\n- blocked-v2 events: {len(old_ref)}\n- strict events: {len(new_ref)}\n- oracle labels changed: {int(diff.label_changed.sum())}\n- oracle boundaries changed: {int(diff.boundaries_changed.sum())}\n- semantic reference changed: {str(old_semantic != new_semantic).lower()}\n\nThis is evaluator-only post-hoc evidence; it is never available to an online planner.\n")

    protected = [
        "BENCHMARK_ID.txt",
        "configs/EXPECTED_RUN_MATRIX.csv", "configs/BASELINE_CONFIG_MANIFEST.csv",
        "configs/SEED_MANIFEST.csv", "configs/FROZEN_BUDGETS.json",
        "configs/PUBLIC_PROXY_RETENTION_MANIFEST.json",
        "benchmark/proxy_precompute/full/center10_anchor_grid.csv",
        "benchmark/proxy_precompute/full/center10_proxy_features.csv",
        "benchmark/proxy_precompute/full/coarse_5s_clip_grid.csv",
        "benchmark/proxy_precompute/full/precompute_summary.csv",
        "benchmark/proxy_precompute/full/proxy_features_5s.csv",
        "benchmark/proxy_precompute/full/sanity_checks.csv",
        "benchmark/proxy_precompute/full/video_metadata.json",
        "frozen_inputs/units.csv", "frozen_inputs/public_proxy.csv",
        "frozen_inputs/oracle_observations.csv", "frozen_inputs/event_reference.csv",
        "oracle/STRICT_ORACLE_COMPLETE.json", "oracle/STRICT_ORACLE_BUILD_MANIFEST.json",
        "oracle/input_identities.jsonl", "oracle/oracle_cache_manifest.csv",
        "oracle/oracle_prompt.txt", "scripts/benchmark_lib.py",
        "scripts/run_clean_benchmark_v2_strict.py",
    ]
    hashes = {relative: sha(PACK / relative) for relative in protected}
    snapshot = {
        "benchmark_id": manifest["benchmark_id"],
        "compatibility_sha256": canonical_hash(manifest["compatibility"]),
        "frozen_at_utc": now(),
        "protected_file_hashes": hashes,
        "rule": "Compatibility payload and protected inputs/code must not change after baseline execution begins.",
    }
    atomic_text(configs / "FROZEN_SEMANTIC_HASHES.json", json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    state_path = PACK / "RUN_STATE.json"; state = json.loads(state_path.read_text())
    state.update({"phase": "semantic_freeze", "phase_status": "completed", "last_checkpoint_time": now()})
    atomic_text(state_path, json.dumps(state, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"benchmark_id": manifest["benchmark_id"], "label_changes": int(diff.label_changed.sum()),
                      "reference_events": len(new_ref), "semantic_snapshot_sha256": sha(configs / "FROZEN_SEMANTIC_HASHES.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
