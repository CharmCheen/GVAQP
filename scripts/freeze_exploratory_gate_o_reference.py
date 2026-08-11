#!/usr/bin/env python3
"""Seal the completed exploratory evaluator-only reference without inference."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    merged: dict[int, dict] = {}
    shards: dict[str, str] = {}
    for path in sorted(RUN.glob("reference_labels*.json")):
        shards[path.name] = sha256(path)
        for raw_id, result in json.loads(path.read_text(encoding="utf-8")).items():
            unit_id = int(raw_id)
            if unit_id in merged and merged[unit_id].get("raw_sha256") != result.get("raw_sha256"):
                raise RuntimeError(f"conflicting duplicate reference label: {unit_id}")
            merged[unit_id] = result
    failures = []
    for unit_id in range(424):
        result = merged.get(unit_id)
        if not result or result.get("label") not in {"positive", "negative", "abstain"}:
            failures.append(unit_id)
    if failures:
        raise RuntimeError(f"reference is incomplete or invalid: {failures[:10]}")
    payload = {str(unit_id): merged[unit_id] for unit_id in range(424)}
    combined = RUN / "reference_labels.json"
    combined.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    prompt = ROOT / "configs/prompts/confirm_visual.yaml"
    freeze = {
        "schema_version": "EXPLORATORY_GUANGZHOU_EVALUATOR_REFERENCE_FREEZE_V1",
        "scientific_status": "EXPLORATORY_DEVELOPMENT_PHYSICAL_RESULT",
        "reference_status": "COMPLETE_ACCEPTED_424_OF_424",
        "reference_labels_canonical_sha256": canonical_hash(payload),
        "reference_labels_file_sha256": sha256(combined),
        "reference_shards_sha256": shards,
        "accepted_label_counts": {label: sum(row["label"] == label for row in merged.values()) for label in ("positive", "negative", "abstain")},
        "failures_or_retries": [],
        "oracle": {"model_path": "models/Qwen3-VL-8B-Instruct", "dtype": "bfloat16", "model_tree_sha256": canonical_hash([{ "path": str(path.relative_to(ROOT / "models/Qwen3-VL-8B-Instruct")), "sha256": sha256(path)} for path in sorted((ROOT / "models/Qwen3-VL-8B-Instruct").rglob("*")) if path.is_file()])},
        "prompt": {"path": "configs/prompts/confirm_visual.yaml", "sha256": sha256(prompt)},
        "unit_definition": {"unit_seconds": 10.0, "origin_seconds": 0.0, "unit_count": 424, "final_unit_may_be_truncated": True},
        "event_materializer": {"implementation": "src/rc_sem/exploratory_gate_o.py:event_groups", "max_gap_units": 1, "sha256": sha256(ROOT / "src/rc_sem/exploratory_gate_o.py")},
        "evaluator": {"implementation": "src/rc_sem/exploratory_gate_o.py:event_recall,event_f1,right_continuous_auc", "sha256": sha256(ROOT / "src/rc_sem/exploratory_gate_o.py")},
    }
    (RUN / "REFERENCE_FREEZE.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(freeze, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
