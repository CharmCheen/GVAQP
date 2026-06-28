#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pandas as pd

from video_access_common import HF_REPO_ID, OUT, append_progress, load_manifest, local_target_for, run_cmd, smoke_subset, write_json


def hf_file_listing() -> tuple[dict, list[str]]:
    status = {
        "repo_id": HF_REPO_ID,
        "huggingface_cli": bool(run_cmd(["bash", "-lc", "command -v huggingface-cli"])["stdout"]),
        "hf_cli": bool(run_cmd(["bash", "-lc", "command -v hf"])["stdout"]),
        "huggingface_hub_available": importlib.util.find_spec("huggingface_hub") is not None,
        "datasets_available": importlib.util.find_spec("datasets") is not None,
        "repo_info_ok": False,
        "repo_private": "",
        "repo_gated": "",
        "list_files_ok": False,
        "file_count": 0,
        "error_type": "",
        "error": "",
    }
    files: list[str] = []
    if not status["huggingface_hub_available"]:
        status["error_type"] = "missing_dependency"
        status["error"] = "huggingface_hub is not installed"
        return status, files
    try:
        from huggingface_hub import HfApi

        api = HfApi()
        info = api.repo_info(repo_id=HF_REPO_ID, repo_type="dataset")
        status["repo_info_ok"] = True
        status["repo_private"] = getattr(info, "private", "")
        status["repo_gated"] = getattr(info, "gated", "")
        files = api.list_repo_files(repo_id=HF_REPO_ID, repo_type="dataset")
        status["list_files_ok"] = True
        status["file_count"] = len(files)
    except Exception as exc:
        status["error_type"] = type(exc).__name__
        status["error"] = str(exc)
    return status, files


def kaggle_status() -> dict:
    cli = run_cmd(["bash", "-lc", "command -v kaggle"])
    cred_path = Path("~/.kaggle/kaggle.json").expanduser()
    return {
        "kaggle_cli_installed": bool(cli["stdout"]),
        "kaggle_cli_path": cli["stdout"],
        "kaggle_credentials_exist": cred_path.exists(),
        "kaggle_credentials_mode": oct(cred_path.stat().st_mode & 0o777) if cred_path.exists() else "",
        "checked_without_download": True,
        "status": "not_configured" if not cli["stdout"] or not cred_path.exists() else "configured_not_used_because_hf_access_available",
    }


def build_plan(manifest: pd.DataFrame, hf_files: list[str]) -> pd.DataFrame:
    hf_by_name_label = {}
    for path in hf_files:
        parts = path.split("/")
        if len(parts) >= 3 and parts[-1].lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
            label = parts[-2]
            hf_by_name_label[(parts[-1], label)] = path

    smoke_ids = set(smoke_subset(manifest)["video_id"].astype(str))
    rows = []
    for row in manifest.itertuples(index=False):
        label_dir = "positive" if bool(row.is_positive) else "negative"
        filename = str(row.video_id)
        remote = hf_by_name_label.get((filename, label_dir), "")
        target = local_target_for(label_dir, filename)
        local_exists = target.exists() or Path(str(row.local_video_path)).exists()
        if local_exists:
            access_status = "local_available"
            action = "use_local_file"
        elif remote:
            access_status = "hf_remote_available"
            action = "download_smoke_only" if filename in smoke_ids else "not_needed_for_smoke"
        else:
            access_status = "not_found_in_local_or_hf_listing"
            action = "manual_upload_or_check_source"
        rows.append(
            {
                "video_id": row.video_id,
                "filename": filename,
                "label": label_dir,
                "needed_for_smoke_subset": filename in smoke_ids,
                "expected_remote_source": remote,
                "local_target_path": str(target),
                "access_status": access_status,
                "required_action": action,
                "notes": "HF listing metadata only; no full dataset download performed.",
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    manifest = load_manifest()
    hf_status, hf_files = hf_file_listing()
    kaggle = kaggle_status()

    write_json(OUT / "manifests/huggingface_access_status.json", hf_status)
    write_json(OUT / "manifests/kaggle_access_status.json", kaggle)
    pd.DataFrame({"repo_file": hf_files}).to_csv(OUT / "manifests/huggingface_file_listing.csv", index=False)
    plan = build_plan(manifest, hf_files)
    plan.to_csv(OUT / "manifests/nexar_video_access_plan.csv", index=False)

    hf_smoke_available = int(((plan["needed_for_smoke_subset"]) & (plan["access_status"] == "hf_remote_available")).sum())
    append_progress("remote_access_audit", "python scripts/10_remote_access_audit.py", f"hf_list_ok={hf_status['list_files_ok']}, hf_files={len(hf_files)}, hf_smoke_available={hf_smoke_available}, kaggle={kaggle['status']}", next_action="controlled 10-video HF download if available")
    print(f"HF list ok: {hf_status['list_files_ok']} files={len(hf_files)} smoke_available={hf_smoke_available}")
    print(f"Kaggle status: {kaggle['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

