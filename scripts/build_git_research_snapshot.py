#!/usr/bin/env python3
"""Build an auditable inclusion/exclusion plan for the research snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/git_research_snapshot"
LIMIT = 50 * 1024 * 1024
TARGET_OUTPUTS = (
    "outputs/partial_scan_pilot_v1/",
    "outputs/partial_scan_pilot_v2/",
    "outputs/partial_scan_method_development_v1/",
    "outputs/partial_scan_method_development_v2/",
    "outputs/scan_optimization_headroom_audit_v1/",
    "outputs/scan_innovation_agentic_loop_v1/",
    "outputs/macro_region_proxy_optimization_v1/",
    "outputs/multi_fidelity_region_preview_v1/",
    "outputs/scan_confirm_decision_v1/",
    "outputs/scan_confirm_common_utility_v1/",
    "outputs/selected_frontier_conversion_v1/",
    "outputs/online_macro_activity_replication/",
    "outputs/psvr_autonomous_research/benchmark_unblock/",
)
TARGET_CODE = (
    "src/garc_eval/partial_scan_v2/",
    "src/garc_eval/scan_confirm_controller/",
    "src/garc_eval/scan_headroom/",
    "src/garc_eval/scan_scheduler/",
    "scripts/", "tests/partial_scan_v2/", "tests/scan_confirm_controller/",
    "tests/scan_headroom/", "tests/scan_scheduler/", "configs/", "docs/",
    "benchmarks/partial_scan_pilot_v1/",
)
PROHIBITED_MEDIA = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv",
                    ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".svg"}
WEIGHTS = {".pt", ".pth", ".ckpt", ".onnx", ".safetensors", ".bin", ".engine"}
ARRAY_CACHE = {".npy", ".npz", ".pkl", ".pickle", ".joblib", ".feather"}
ARCHIVES = {".zip", ".gz", ".tar", ".tgz", ".7z"}
CACHE_PARTS = {"__pycache__", ".pytest_cache", ".cache", ".mypy_cache", ".ruff_cache",
               ".ipynb_checkpoints", ".venv", "venv", "env", "site-packages"}


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def zpaths(data: bytes) -> list[str]:
    return [x.decode("utf-8", "surrogateescape") for x in data.split(b"\0") if x]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def is_provenance(path: str) -> bool:
    return path.startswith("data/realcam/") and path.endswith((".source.json", ".source_attestation.md"))


def base_include(path: str) -> bool:
    return (path in {".gitignore", "pytest.ini"}
            or path.startswith(TARGET_CODE)
            or path.startswith(TARGET_OUTPUTS)
            or path.startswith("outputs/git_research_snapshot/")
            or is_provenance(path))


def exclusion_reason(path: str, size: int) -> str | None:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in PROHIBITED_MEDIA:
        return "RAW_OR_INTERMEDIATE_MEDIA"
    if suffix in WEIGHTS:
        return "MODEL_WEIGHT_OR_ENGINE"
    if any(part in CACHE_PARTS for part in p.parts) or suffix in {".pyc", ".tmp", ".temp"}:
        return "CACHE_OR_TEMPORARY_FILE"
    if suffix in ARRAY_CACHE:
        return "GENERATED_ARRAY_OR_CACHE"
    if suffix in ARCHIVES:
        return "ARCHIVE_NOT_SUITABLE_FOR_SNAPSHOT"
    if suffix == ".log":
        return "NONFROZEN_LOG_EXCLUDED"
    if size > LIMIT:
        return "OVER_50_MIB_NO_GIT_LFS"
    return None


def nearest_manifest(path: Path) -> str:
    for parent in [path.parent, *path.parents]:
        if parent == ROOT.parent:
            break
        candidate = parent / "artifact_hash_manifest.json"
        if candidate.is_file():
            return str(candidate.relative_to(ROOT))
    sidecar = Path(str(path) + ".source.json")
    if sidecar.is_file():
        return str(sidecar.relative_to(ROOT))
    return "NOT_FOUND"


def ignored_prohibited() -> Iterable[str]:
    for current, dirs, files in os.walk(ROOT):
        cur = Path(current)
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            p = cur / name
            rel = str(p.relative_to(ROOT))
            suffix = p.suffix.lower()
            if (suffix in PROHIBITED_MEDIA | WEIGHTS | ARRAY_CACHE | ARCHIVES
                    or any(part in CACHE_PARTS for part in p.parts)
                    or suffix in {".pyc", ".tmp", ".temp"}
                    or p.stat().st_size > LIMIT):
                yield rel


def secret_scan(paths: list[str]) -> tuple[list[dict], list[dict]]:
    strong_patterns = [
        ("OPENAI_STYLE_KEY", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
        ("HF_TOKEN", re.compile(r"\bhf_[A-Za-z0-9]{20,}")),
        ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
        ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
        ("BEARER_CREDENTIAL", re.compile(r"(?i)Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/-]{12,}")),
    ]
    context = re.compile(r"(?i)\b(API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY|AWS_|OPENAI_|HF_TOKEN|Authorization:|Bearer|cookie|credentials)\b")
    strong, reviewed = [], []
    for rel in paths:
        p = ROOT / rel
        if p.suffix.lower() in {".parquet", ".so", ".o"} or not p.is_file() or p.stat().st_size > 10 * 1024 * 1024:
            continue
        try:
            lines = p.read_text(errors="strict").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for no, line in enumerate(lines, 1):
            found_strong = False
            for kind, pattern in strong_patterns:
                if pattern.search(line):
                    strong.append({"path": rel, "line": no, "type": kind})
                    found_strong = True
            if not found_strong and context.search(line):
                reviewed.append({"path": rel, "line": no, "type": "CONTEXT_TERM_REVIEWED_NO_VALUE_REPORTED"})
    return strong, reviewed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-summary", type=Path)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    changed = set(zpaths(git("diff", "--name-only", "-z")))
    untracked = set(zpaths(git("ls-files", "--others", "--exclude-standard", "-z")))
    tracked = set(zpaths(git("ls-files", "-z")))
    candidate_paths = changed | untracked
    candidate_paths.add("scripts/build_git_research_snapshot.py")
    candidate_paths.add("scripts/run_git_snapshot_checks.py")
    # Snapshot deliverables are generated during this run and explicitly included.
    snapshot_names = ["FILE_INVENTORY.csv", "INCLUDED_FILES.csv", "EXCLUDED_FILES.csv",
                      "LARGE_FILE_AUDIT.csv", "SECRET_SCAN_REPORT.md", "GIT_SNAPSHOT_REPORT.md",
                      "TEST_RESULTS.json", "CONSISTENCY_AUDIT.json", "STAGING_PATHS.txt",
                      "REPAIR_LOG.json"]
    candidate_paths.update(f"outputs/git_research_snapshot/{x}" for x in snapshot_names)

    ignored = set(ignored_prohibited())
    all_paths = sorted(candidate_paths | ignored)
    included, excluded, inventory = [], [], []
    for index, rel in enumerate(all_paths, 1):
        p = ROOT / rel
        exists = p.is_file()
        size = p.stat().st_size if exists else 0
        reason = exclusion_reason(rel, size) if exists else None
        disposition = "EXCLUDED"
        why = reason or "OUTSIDE_FROZEN_RESEARCH_SNAPSHOT_SCOPE"
        if rel.startswith("outputs/git_research_snapshot/") and not exists:
            disposition, why = "INCLUDED", "GENERATED_SNAPSHOT_DELIVERABLE"
        elif exists and base_include(rel) and reason is None:
            disposition, why = "INCLUDED", "FROZEN_RESEARCH_CODE_DOCUMENT_OR_RESULT"
        # These files are outputs of this builder. Hashing their previous contents and
        # then overwriting them would make the inventory's digest claims stale.
        digest = ("SELF_GENERATED_NOT_SELF_HASHED"
                  if rel.startswith("outputs/git_research_snapshot/")
                  else (sha256(p) if exists else "GENERATED_AFTER_INVENTORY"))
        row = {"path": rel, "git_state": "MODIFIED" if rel in changed else ("UNTRACKED" if rel in untracked else ("TRACKED" if rel in tracked else "IGNORED")),
               "size_bytes": size, "sha256": digest, "disposition": disposition, "reason": why,
               "artifact_manifest": nearest_manifest(p) if exists else "NOT_APPLICABLE"}
        inventory.append(row)
        (included if disposition == "INCLUDED" else excluded).append(row)
        if index % 500 == 0:
            print(f"hashed {index}/{len(all_paths)}", flush=True)

    strong, reviewed = secret_scan([x["path"] for x in included if (ROOT / x["path"]).is_file()])
    if strong:
        blocked = {x["path"] for x in strong}
        moved = [x for x in included if x["path"] in blocked]
        included = [x for x in included if x["path"] not in blocked]
        for row in moved:
            row["disposition"] = "EXCLUDED"; row["reason"] = "BLOCKED_SECRET"
            excluded.append(row)

    fields = ["path", "git_state", "size_bytes", "sha256", "disposition", "reason", "artifact_manifest"]
    write_csv(OUT / "FILE_INVENTORY.csv", inventory, fields)
    write_csv(OUT / "INCLUDED_FILES.csv", sorted(included, key=lambda x: x["path"]), fields)
    write_csv(OUT / "EXCLUDED_FILES.csv", sorted(excluded, key=lambda x: x["path"]), fields)
    large = [x for x in inventory if int(x["size_bytes"]) > LIMIT]
    write_csv(OUT / "LARGE_FILE_AUDIT.csv", large, fields)

    secret_lines = ["# Secret Scan Report", "", f"Status: `{'BLOCKED' if strong else 'PASS'}`", "",
                    "No secret values are reproduced in this report.", "",
                    f"Strong credential findings: {len(strong)}", f"Context-only reviewed matches: {len(reviewed)}", ""]
    if strong:
        secret_lines += ["## Blocking findings", ""] + [f"- `{x['path']}:{x['line']}` — `{x['type']}`" for x in strong]
    secret_lines += ["", "## Context-only matches", ""] + [f"- `{x['path']}:{x['line']}` — `{x['type']}`" for x in reviewed[:1000]]
    if len(reviewed) > 1000:
        secret_lines.append(f"- ... {len(reviewed)-1000} additional context-only matches omitted from prose; no credential-value pattern matched.")
    (OUT / "SECRET_SCAN_REPORT.md").write_text("\n".join(secret_lines) + "\n")

    staging = sorted(x["path"] for x in included)
    (OUT / "STAGING_PATHS.txt").write_text("\n".join(staging) + "\n")
    test = json.loads(args.test_summary.read_text()) if args.test_summary and args.test_summary.exists() else {"status": "PENDING"}
    branch = git("rev-parse", "--abbrev-ref", "HEAD").decode().strip()
    head = git("rev-parse", "HEAD").decode().strip()
    inc_bytes = sum(int(x["size_bytes"]) for x in included)
    exc_bytes = sum(int(x["size_bytes"]) for x in excluded)
    report = f"""# Git Research Snapshot Report

Repository: `{ROOT}`  
Branch: `{branch}`  
Pre-commit HEAD: `{head}`  
Date: `{date.today().isoformat()}`

## Frozen research scope

- Code: `src/garc_eval/partial_scan_v2`, `scan_scheduler`, `scan_headroom`, `scan_confirm_controller`; related `scripts`, `tests`, and `configs`.
- Contracts and documentation: partial-SCAN, SafeCoveragePolicy, YOLO-guided scheduling, macro-region proxy, multi-fidelity preview, SCAN-CONFIRM, common utility, and selected-Frontier input calibration.
- Results: the thirteen explicitly audited output stages plus `benchmarks/partial_scan_pilot_v1`.
- Provenance: hash-bound `*.source.json` and `*.source_attestation.md`; raw media remains excluded.

Included files: {len(included)}  
Included bytes: {inc_bytes}  
Excluded files: {len(excluded)}  
Excluded bytes: {exc_bytes}

## Large files and sensitive material

Git LFS is not installed/configured. Every file over 50 MiB is excluded from this commit and recorded with SHA-256 in `LARGE_FILE_AUDIT.csv`. Raw media, extracted images, model weights, generated arrays/caches, archives, and temporary files are excluded. Secret scan status: `{'BLOCKED' if strong else 'PASS'}`; reports contain locations and types only, never values.

## Verification

Test summary status: `{test.get('status', 'PENDING')}`. Detailed counts and skipped checks are recorded in `TEST_RESULTS.json` and `CONSISTENCY_AUDIT.json`. No Oracle, VLM, GPU research run, or new method experiment is part of this snapshot task.

The inventory uses `SELF_GENERATED_NOT_SELF_HASHED` for every file under `outputs/git_research_snapshot/`; these builder outputs are deliberately not assigned stale hashes from a prior generation. Artifact entries reported as unsupported use a manifest schema not supported by the generic verifier and are not counted as verified.

## Frozen conclusions and limitations

```text
SELECTED_SCAN_POLICY = SAFE_COVERAGE_POLICY
DEFAULT_SCAN_MODE = ANYTIME_LARGEST_GAP
SELECTED_CONTROLLER = R4_FIXED_TIME_RATIO_25_75

YOLO_GUIDED_REGION_SCHEDULING = CLOSED
MYOPIC_VPS_SIGNAL = NOT_ESTABLISHED
COMMON_UTILITY_ALIGNMENT_V1 = NOT_ESTABLISHED
REGION_VALUE_PROXY_SIGNAL = NOT_ESTABLISHED
MULTI_FIDELITY_PREVIEW_SIGNAL = NOT_ESTABLISHED
RATIO_ANCHORED_CONTROLLER = BLOCKED
BANDIT = DEFERRED
SMDP = DEFERRED
RL = PROHIBITED

FORMAL_GENERALIZATION = NOT_ESTABLISHED
ADAPTIVE_CONTROL = NOT_ESTABLISHED
SELECTED_FRONTIER_CALIBRATION = BLOCKED_INPUT_INSUFFICIENT
```

This commit is a local auditable snapshot, not a new scientific evaluation.
"""
    (OUT / "GIT_SNAPSHOT_REPORT.md").write_text(report)
    print(json.dumps({"included": len(included), "included_bytes": inc_bytes,
                      "excluded": len(excluded), "excluded_bytes": exc_bytes,
                      "large": len(large), "strong_secrets": len(strong)}, indent=2))
    if strong:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
