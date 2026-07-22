from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from garc_eval.psvr_runtime.physical_oracle import verify_physical_oracle_configuration


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_physical_oracle_configuration_binds_every_frozen_input(tmp_path):
    source = tmp_path / "oracle.py"; source.write_text("# frozen\n")
    identities = tmp_path / "identities.jsonl"; identities.write_text("{}\n")
    prompt = tmp_path / "prompt.txt"; prompt.write_text("query\n")
    video = tmp_path / "video.mp4"; video.write_bytes(b"physical-video")
    model_manifest = tmp_path / "model.csv"; model_manifest.write_text("file,sha256,size_bytes\n")
    model = tmp_path / "model"; model.mkdir()
    manifest = tmp_path / "manifest.json"
    payload = {
        "status": "COMPLETE", "oracle_build_id": "strict_oracle_test",
        "input_identities_sha256": _hash(identities),
        "artifact_hashes": {"oracle/STRICT_MODEL_FILE_MANIFEST.csv": _hash(model_manifest)},
        "build_identity": {"configuration": {
            "prompt_sha256": _hash(prompt), "video_sha256": _hash(video),
        }},
    }
    manifest.write_text(json.dumps(payload))
    paths = {
        "frozen_oracle_source": source, "input_identities": identities,
        "prompt": prompt, "video": video, "strict_manifest": manifest,
        "model_manifest": model_manifest,
    }
    configuration = {
        "frozen_oracle_source": str(source), "input_identities_path": str(identities),
        "prompt_path": str(prompt), "video_path": str(video), "model_path": str(model),
        "strict_manifest_path": str(manifest), "model_manifest_path": str(model_manifest),
        "expected_hashes": {name: _hash(path) for name, path in paths.items()},
        "expected_oracle_build_id": "strict_oracle_test",
        "model_file_identity": [],
    }
    verified = verify_physical_oracle_configuration(configuration)
    assert verified["oracle_build_id"] == "strict_oracle_test"

    prompt.write_text("mutated\n")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        verify_physical_oracle_configuration(configuration)
