#!/usr/bin/env python3
"""Acquire only the files required by the two frozen Gate A encoders."""

import argparse
import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download, try_to_load_from_cache

PACKAGE = Path(__file__).resolve().parents[1]
FROZEN = {
    "openai/clip-vit-base-patch32": {
        "revision": "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268",
        "files": ["config.json", "preprocessor_config.json", "merges.txt",
                  "pytorch_model.bin", "special_tokens_map.json", "tokenizer.json",
                  "tokenizer_config.json", "vocab.json"],
    },
    "microsoft/xclip-base-patch32": {
        "revision": "a2e27a78a2b5d802e894b8a1ef14f3a8ce490963",
        "files": ["config.json", "preprocessor_config.json", "merges.txt",
                  "model.safetensors", "special_tokens_map.json", "tokenizer.json",
                  "tokenizer_config.json", "vocab.json"],
    },
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8",
                                     dir=path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
        temporary = handle.name
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PACKAGE / "config/gate_a_frozen.json")
    parser.add_argument("--output", type=Path, default=PACKAGE / "outputs/gate_a_final/model_file_manifest.csv")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    configured = {
        config["methods"]["image_text"]["model_id"]: config["methods"]["image_text"]["revision"],
        config["methods"]["video_text"]["model_id"]: config["methods"]["video_text"]["revision"],
    }
    if configured != {repo: spec["revision"] for repo, spec in FROZEN.items()}:
        raise RuntimeError("GATE_A_CONFIG_BLOCKED: configured models differ from frozen allowlist")
    api = HfApi()
    rows = []
    for repo, spec in FROZEN.items():
        resolved = api.model_info(repo, revision=spec["revision"]).sha
        if resolved != spec["revision"]:
            raise RuntimeError(f"revision mismatch for {repo}: {resolved}")
        for filename in spec["files"]:
            cached_before = try_to_load_from_cache(repo, filename, revision=spec["revision"])
            start = utc_now()
            path = hf_hub_download(repo, filename, revision=spec["revision"])
            end = utc_now()
            rows.append({
                "source_repository": repo, "requested_revision": spec["revision"],
                "resolved_revision": resolved, "filename": filename,
                "size_bytes": Path(path).stat().st_size, "sha256": sha256(path),
                "download_start_utc": start, "download_end_utc": end,
                "cache_path": str(Path(path).resolve()),
                "cache_hit_before": bool(cached_before),
            })
            atomic_csv(args.output, rows)
            print(f"sealed {repo}/{filename} cache_hit={bool(cached_before)}", flush=True)
    print(args.output)


if __name__ == "__main__":
    main()
