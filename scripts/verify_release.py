#!/usr/bin/env python3
from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
WEIGHTS = {".pt", ".pth", ".ckpt", ".safetensors", ".onnx"}
SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-/+=]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?:sk|ghp|github_pat)_[A-Za-z0-9_\-]{20,}"),
)


def local_imports() -> tuple[list[str], list[str]]:
    modules = {"garc"}
    unresolved = []
    imports = []
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
    for name in imports:
        if name.split(".")[0] in modules:
            candidate = ROOT / "src" / Path(*name.split("."))
            if not candidate.with_suffix(".py").exists() and not (candidate / "__init__.py").exists():
                unresolved.append(name)
    return sorted(set(imports)), sorted(set(unresolved))


def main() -> None:
    # The isolated environment is an external dependency installation, not a
    # release artifact. Scanning it creates false positives from library source
    # and shared objects and can never make those files tracked by this repo.
    files = [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts and ".venv" not in path.parts]
    media = [str(path.relative_to(ROOT)) for path in files if path.suffix.lower() in MEDIA]
    weights = [str(path.relative_to(ROOT)) for path in files if path.suffix.lower() in WEIGHTS]
    large = [str(path.relative_to(ROOT)) for path in files if path.stat().st_size > 50 * 1024 * 1024]
    secrets = []
    absolute_runtime_paths = []
    for path in files:
        if path.suffix.lower() in {".py", ".md", ".json", ".yaml", ".yml", ".csv", ".toml"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                secrets.append(str(path.relative_to(ROOT)))
            if path.is_relative_to(ROOT / "src") and re.search(r"/qiuyeqing/|/root/|/home/", text):
                absolute_runtime_paths.append(str(path.relative_to(ROOT)))
    imports, unresolved = local_imports()
    manifest = ROOT / "provenance/migration_manifest.csv"
    migration = list(csv.DictReader(manifest.open(encoding="utf-8"))) if manifest.exists() else []
    migration_hash_mismatch = []
    for row in migration:
        target = ROOT / row["target_path"]
        actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
        if actual != row["content_sha256"]:
            migration_hash_mismatch.append(row["target_path"])
    report = {"pass": not any((media, weights, large, secrets, absolute_runtime_paths, unresolved,
                                migration_hash_mismatch)) and bool(migration),
              "raw_media": media, "model_weights": weights, "files_over_50_mib": large,
              "strong_secret_findings": secrets, "absolute_server_paths_in_runtime": absolute_runtime_paths,
              "local_imports_unresolved": unresolved, "imports": imports,
              "migration_manifest_nonempty": bool(migration),
              "migration_hash_mismatch": sorted(set(migration_hash_mismatch))}
    (ROOT / "provenance/dependency_closure.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
