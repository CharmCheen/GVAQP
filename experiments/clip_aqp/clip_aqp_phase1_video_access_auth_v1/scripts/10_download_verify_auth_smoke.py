#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pandas as pd

from auth_video_common import HF_REPO_ID, OUT, SMOKE_COLUMNS, append_progress, verify_video


PER_FILE_TIMEOUT_SECONDS = 90
MAX_RETRIES = 2


def bounded_download(hf_path: str) -> tuple[str, str]:
    code = (
        "from huggingface_hub import hf_hub_download\n"
        f"p=hf_hub_download(repo_id={HF_REPO_ID!r}, repo_type='dataset', filename={hf_path!r}, resume_download=True)\n"
        "print(p)\n"
    )
    proc = subprocess.run(["python", "-c", code], capture_output=True, text=True, timeout=PER_FILE_TIMEOUT_SECONDS, check=False)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"returncode={proc.returncode}").strip())
    return proc.stdout.strip().splitlines()[-1], proc.stderr.strip()


def main() -> int:
    auth = pd.read_json(OUT / "manifests/hf_auth_status.json", typ="series").to_dict()
    smoke = pd.read_csv(OUT / "manifests/nexar_auth_smoke_manifest.csv")
    if auth.get("auth_status") != "authenticated":
        rows = []
        for row in smoke.itertuples(index=False):
            verify = verify_video(Path(str(row.local_target_path)))
            status = "already_readable" if verify["readable"] else "not_attempted_auth_missing"
            rows.append(
                {
                    "video_id": row.video_id,
                    "filename": row.filename,
                    "label": row.label,
                    "hf_path": row.hf_path,
                    "local_target_path": row.local_target_path,
                    "auth_download_status": status,
                    "attempt_count": 0,
                    "error": "HF auth missing; download skipped" if status != "already_readable" else "",
                    "maps_back_to_manifest": True,
                    **verify,
                }
            )
        pd.DataFrame(rows).to_csv(OUT / "checks/video_readability_checks.csv", index=False)
        smoke["auth_download_status"] = [r["auth_download_status"] for r in rows]
        smoke["file_size_bytes"] = [r["file_size_bytes"] for r in rows]
        smoke["duration_seconds"] = [r["duration_seconds"] for r in rows]
        smoke["readable"] = [r["readable"] for r in rows]
        smoke.to_csv(OUT / "manifests/nexar_auth_smoke_manifest.csv", index=False)
        append_progress("download_verify_auth_smoke", "python scripts/10_download_verify_auth_smoke.py", "skipped_auth_missing", failure="HF auth missing", next_action="frame smoke/report")
        print("HF auth missing; skipped missing-video downloads")
        return 0

    rows = []
    for row in smoke.itertuples(index=False):
        target = Path(str(row.local_target_path))
        target.parent.mkdir(parents=True, exist_ok=True)
        verify = verify_video(target)
        status = "already_readable" if verify["readable"] else "pending"
        error = ""
        attempts = 0
        if not verify["readable"]:
            for attempt in range(1, MAX_RETRIES + 1):
                attempts = attempt
                try:
                    cached, stderr = bounded_download(str(row.hf_path))
                    shutil.copy2(cached, target)
                    verify = verify_video(target)
                    status = "downloaded_readable" if verify["readable"] else "downloaded_not_readable"
                    error = stderr
                    if verify["readable"]:
                        break
                except subprocess.TimeoutExpired:
                    status = "download_timeout"
                    error = f"hf_hub_download exceeded {PER_FILE_TIMEOUT_SECONDS}s"
                except Exception as exc:
                    status = "download_failed"
                    error = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "video_id": row.video_id,
                "filename": row.filename,
                "label": row.label,
                "hf_path": row.hf_path,
                "local_target_path": str(target),
                "auth_download_status": status,
                "attempt_count": attempts,
                "error": error,
                "maps_back_to_manifest": True,
                **verify,
            }
        )
    checks = pd.DataFrame(rows)
    checks.to_csv(OUT / "checks/video_readability_checks.csv", index=False)
    update = smoke.copy()
    by_video = {row["video_id"]: row for _, row in checks.iterrows()}
    for idx, row in update.iterrows():
        chk = by_video[row["video_id"]]
        update.loc[idx, "auth_download_status"] = chk["auth_download_status"]
        update.loc[idx, "file_size_bytes"] = chk["file_size_bytes"]
        update.loc[idx, "duration_seconds"] = chk["duration_seconds"]
        update.loc[idx, "readable"] = chk["readable"]
    update[SMOKE_COLUMNS].to_csv(OUT / "manifests/nexar_auth_smoke_manifest.csv", index=False)
    readable = int(checks["readable"].astype(bool).sum()) if not checks.empty else 0
    append_progress("download_verify_auth_smoke", "python scripts/10_download_verify_auth_smoke.py", f"readable={readable}/{len(checks)}", failure="" if readable >= 8 else "fewer than 8 readable", next_action="frame smoke/report")
    print(f"readable={readable}/{len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

