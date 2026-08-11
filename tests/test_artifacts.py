import json
from pathlib import Path

from garc.audit.artifacts import artifact_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_curated_result_artifact_consistency():
    expected = json.loads((ROOT / "results/manifests/artifact_manifest.json").read_text())["artifacts"]
    actual = artifact_manifest(ROOT / "results")["artifacts"]
    actual.pop("manifests/artifact_manifest.json")
    assert actual == expected
