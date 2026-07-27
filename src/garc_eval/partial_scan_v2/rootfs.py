from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterable

from .artifacts import atomic_json, canonical_hash, recursive_manifest, sha256_file
from .config import (
    POLICY_GID,
    POLICY_ROOTFS,
    POLICY_UID,
    V2_IMMUTABLE,
    V2_ISOLATION,
)


SYSTEM_PYTHON = Path("/usr/bin/python3.10")
SYSTEM_STDLIB = Path("/usr/lib/python3.10")
ROOTFS_MARKER = "partial_scan_policy_v2_rootfs.json"


def policy_bundle_hash() -> str:
    assets = recursive_manifest(V2_IMMUTABLE / "policy_bundle")
    return canonical_hash(assets)


def _copy_absolute(source: Path, root: Path) -> Path:
    destination = root / str(source).lstrip("/")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source.resolve(), destination)
    return destination


def _ldd_paths(path: Path) -> set[Path]:
    process = subprocess.run(
        ["ldd", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    paths: set[Path] = set()
    for line in process.stdout.splitlines():
        for token in re.findall(r"(/[^\s()]+)", line):
            candidate = Path(token)
            if candidate.is_file():
                paths.add(candidate)
    return paths


def _stdlib_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {"__pycache__", "site-packages", "dist-packages", "test", "tests"}
    return {name for name in names if name in ignored or name.endswith(".pyc")}


def _set_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_symlink():
            continue
        if path.is_dir():
            path.chmod(0o555)
        elif path in {
            root / "usr/bin/python3.10",
            root / "lib64/ld-linux-x86-64.so.2",
        }:
            path.chmod(0o555)
        else:
            path.chmod(0o444)
    root.chmod(0o555)
    scratch = root / "tmp"
    scratch.chmod(0o700)
    os.chown(scratch, POLICY_UID, POLICY_GID)


def build_policy_rootfs(force: bool = False) -> dict:
    bundle_hash = policy_bundle_hash()
    marker = POLICY_ROOTFS / ROOTFS_MARKER
    if marker.is_file() and not force:
        existing = json.loads(marker.read_text())
        if existing.get("policy_bundle_hash") == bundle_hash:
            return existing
    if POLICY_ROOTFS.exists():
        shutil.rmtree(POLICY_ROOTFS)
    POLICY_ROOTFS.mkdir(parents=True, mode=0o755)
    (POLICY_ROOTFS / "usr/bin").mkdir(parents=True)
    (POLICY_ROOTFS / "usr/lib").mkdir(parents=True)
    _copy_absolute(SYSTEM_PYTHON, POLICY_ROOTFS)
    shutil.copytree(
        SYSTEM_STDLIB,
        POLICY_ROOTFS / "usr/lib/python3.10",
        symlinks=False,
        ignore=_stdlib_ignore,
    )
    binaries: list[Path] = [SYSTEM_PYTHON]
    binaries.extend(
        path
        for path in SYSTEM_STDLIB.rglob("*.so")
        if path.is_file()
    )
    dependencies: set[Path] = set()
    for binary in binaries:
        dependencies.update(_ldd_paths(binary))
    for dependency in sorted(dependencies):
        _copy_absolute(dependency, POLICY_ROOTFS)
    policy = POLICY_ROOTFS / "policy"
    policy.mkdir()
    for name in [
        "policy_worker.py",
        "sentinel_probe_worker.py",
        "synthetic_error_worker.py",
    ]:
        shutil.copy2(V2_IMMUTABLE / "policy_bundle" / name, policy / name)
    scratch = POLICY_ROOTFS / "tmp"
    scratch.mkdir()
    marker_payload = {
        "rootfs_backend": "TMPFS_CHROOT_DEDICATED_UID_SECCOMP",
        "rootfs_path": str(POLICY_ROOTFS),
        "policy_bundle_hash": bundle_hash,
        "system_python_sha256": sha256_file(SYSTEM_PYTHON),
        "python_version": subprocess.run(
            [str(SYSTEM_PYTHON), "--version"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "benchmark_mount_present": False,
        "proc_mount_present": False,
        "etc_mount_present": False,
        "network_filter": "SECCOMP_ERRNO_BLOCK",
        "policy_uid": POLICY_UID,
        "policy_gid": POLICY_GID,
    }
    marker.write_text(json.dumps(marker_payload, sort_keys=True) + "\n")
    _set_read_only(POLICY_ROOTFS)
    manifest = recursive_manifest(POLICY_ROOTFS)
    marker_payload.update(
        {
            "rootfs_asset_count": len(manifest),
            "rootfs_manifest_hash": canonical_hash(manifest),
            "root_entries": sorted(path.name for path in POLICY_ROOTFS.iterdir()),
        }
    )
    atomic_json(V2_ISOLATION / "runtime_rootfs_manifest.json", {
        **marker_payload,
        "assets": manifest,
    })
    return marker_payload


def clear_private_scratch() -> None:
    scratch = POLICY_ROOTFS / "tmp"
    if not scratch.is_dir():
        raise RuntimeError("policy rootfs not built")
    scratch.chmod(0o700)
    for child in list(scratch.iterdir()):
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)
    os.chown(scratch, POLICY_UID, POLICY_GID)


def rootfs_forbidden_asset_audit() -> dict:
    forbidden_names = {
        "reference_events.csv",
        "candidate_event_map.parquet",
        "runtime.json",
        "action_trace.jsonl",
        "raw_candidates.json",
    }
    matches = [
        str(path.relative_to(POLICY_ROOTFS))
        for path in POLICY_ROOTFS.rglob("*")
        if path.is_file() and path.name in forbidden_names
    ]
    forbidden_roots = [
        POLICY_ROOTFS / "qiuyeqing",
        POLICY_ROOTFS / "benchmarks",
        POLICY_ROOTFS / "proc",
    ]
    return {
        "status": (
            "PASS"
            if not matches and not any(path.exists() for path in forbidden_roots)
            else "FAIL"
        ),
        "forbidden_asset_name_matches": matches,
        "host_workspace_root_present": (POLICY_ROOTFS / "qiuyeqing").exists(),
        "benchmark_mount_present": (POLICY_ROOTFS / "benchmarks").exists(),
        "proc_mount_present": (POLICY_ROOTFS / "proc").exists(),
        "root_entries": sorted(path.name for path in POLICY_ROOTFS.iterdir()),
    }


def host_isolation_configuration_audit() -> dict:
    """Audit only the dedicated policy root and frozen launch configuration."""
    launcher_source = (
        V2_IMMUTABLE / "policy_bundle/sandbox_launcher.c"
    ).read_text()
    policy_files = sorted(
        path.name
        for path in (POLICY_ROOTFS / "policy").iterdir()
        if path.is_file()
    )
    expected_policy_files = [
        "policy_worker.py",
        "sentinel_probe_worker.py",
        "synthetic_error_worker.py",
    ]
    scratch = POLICY_ROOTFS / "tmp"
    read_only_violations = []
    for path in POLICY_ROOTFS.rglob("*"):
        if path == scratch or scratch in path.parents or path.is_symlink():
            continue
        mode = path.stat().st_mode & 0o777
        if mode & 0o022:
            read_only_violations.append(str(path.relative_to(POLICY_ROOTFS)))
    scratch_mode = scratch.stat().st_mode & 0o777
    scratch_private = (
        scratch_mode == 0o700
        and scratch.stat().st_uid == POLICY_UID
        and scratch.stat().st_gid == POLICY_GID
    )
    rootfs_assets = rootfs_forbidden_asset_audit()
    launcher_checks = {
        "chroot_fail_closed": "chroot(argv[1]) != 0" in launcher_source,
        "dedicated_uid_gid": (
            "setgid(gid) != 0" in launcher_source
            and "setuid(uid) != 0" in launcher_source
        ),
        "capability_bounding_set_dropped": (
            "PR_CAPBSET_DROP" in launcher_source
        ),
        "no_new_privileges": "PR_SET_NO_NEW_PRIVS" in launcher_source,
        "seccomp_filter": "PR_SET_SECCOMP" in launcher_source,
        "network_syscalls_denied": (
            "DENY_SYSCALL(__NR_socket)" in launcher_source
            and "DENY_SYSCALL(__NR_connect)" in launcher_source
        ),
        "non_ipc_fds_closed": (
            "descriptor = 3" in launcher_source
            and "close(descriptor)" in launcher_source
        ),
        "environment_rebuilt": (
            "clean_env[0]" in launcher_source
            and "execve(argv[4], &argv[4], clean_env)" in launcher_source
        ),
        "working_directory_policy_only": (
            'chdir("/policy")' in launcher_source
        ),
    }
    status = all(
        [
            rootfs_assets["status"] == "PASS",
            not read_only_violations,
            scratch_private,
            policy_files == expected_policy_files,
            all(launcher_checks.values()),
            str(POLICY_ROOTFS).startswith("/dev/shm/"),
        ]
    )
    return {
        "status": "PASS" if status else "FAIL",
        "POLICY_EXECUTION_MODE": "OUT_OF_PROCESS",
        "POLICY_BENCHMARK_MOUNT_COUNT": 0,
        "POLICY_NETWORK_MODE": "SECCOMP_DENY",
        "POLICY_CAPABILITY_COUNT": 0,
        "POLICY_ENVIRONMENT_KEYS": [
            "POLICY_PROTOCOL_VERSION",
            "POLICY_RUN_ID",
            "PYTHONUNBUFFERED",
        ],
        "POLICY_INHERITED_FD_COUNT": 3,
        "POLICY_INHERITED_NON_IPC_FD_COUNT": 0,
        "POLICY_ROOTFS_READ_ONLY": not read_only_violations,
        "POLICY_PRIVATE_TMP": scratch_private,
        "POLICY_WORKING_DIRECTORY": "/policy",
        "POLICY_HOST_PID_NAMESPACE": "HOST_SHARED_LIMITATION",
        "POLICY_HOST_PID_VISIBILITY": "NONE_NO_PROC_MOUNT",
        "POLICY_PROC_MOUNT": False,
        "POLICY_BUNDLE_FILES": policy_files,
        "POLICY_BUNDLE_EXPECTED_FILES": expected_policy_files,
        "rootfs_read_only_violations": read_only_violations,
        "launcher_configuration_checks": launcher_checks,
        "rootfs_asset_audit": rootfs_assets,
        "audit_scope": (
            "DEDICATED_POLICY_ROOT_AND_FROZEN_LAUNCH_CONFIGURATION_ONLY"
        ),
    }
