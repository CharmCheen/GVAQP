from __future__ import annotations

import hashlib
import json
from pathlib import Path


def artifact_manifest(root: Path) -> dict:
    root = Path(root)
    artifacts = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        artifacts[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"artifact_count": len(artifacts), "artifacts": artifacts}


def verify_manifest(root: Path, manifest_path: Path) -> dict:
    expected = json.loads(Path(manifest_path).read_text(encoding="utf-8"))["artifacts"]
    actual = artifact_manifest(root)["artifacts"]
    return {"pass": expected == actual, "missing": sorted(set(expected) - set(actual)),
            "unexpected": sorted(set(actual) - set(expected)),
            "mismatched": sorted(key for key in expected.keys() & actual.keys() if expected[key] != actual[key])}
