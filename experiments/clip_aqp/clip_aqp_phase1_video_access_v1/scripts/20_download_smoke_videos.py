#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import pandas as pd

from video_access_common import HF_REPO_ID, OUT, VIDEOS_SMOKE, append_progress, verify_video


PER_FILE_TIMEOUT_SECONDS = 20


def bounded_hf_download(remote_path: str) -> tuple[str, str]:
    code = (
        "from huggingface_hub import hf_hub_download\n"
        f"p=hf_hub_download(repo_id={HF_REPO_ID!r}, repo_type='dataset', filename={remote_path!r})\n"
        "print(p)\n"
    )
    proc = subprocess.run(
        ["python", "-c", code],
        capture_output=True,
        text=True,
        timeout=PER_FILE_TIMEOUT_SECONDS,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"returncode={proc.returncode}").strip())
    path = proc.stdout.strip().splitlines()[-1]
    return path, (proc.stderr or "").strip()


def main() -> int:
    plan = pd.read_csv(OUT / "manifests/nexar_video_access_plan.csv")
    selected = pd.concat(
        [
            plan[(plan["label"] == "positive") & (plan["access_status"].isin(["hf_remote_available", "local_available"]))].head(5),
            plan[(plan["label"] == "negative") & (plan["access_status"].isin(["hf_remote_available", "local_available"]))].head(5),
        ],
        ignore_index=True,
    )
    rows = []
    if selected.empty:
        pd.DataFrame(rows).to_csv(OUT / "manifests/downloaded_smoke_videos.csv", index=False)
        append_progress("download_smoke_videos", "python scripts/20_download_smoke_videos.py", "downloaded=0", failure="no direct HF/local access for smoke videos", next_action="report")
        print("No videos selected for download")
        return 0

    start = time.time()
    for row in selected.itertuples(index=False):
        target = Path(str(row.local_target_path))
        target.parent.mkdir(parents=True, exist_ok=True)
        status = "not_attempted"
        error = ""
        if target.exists() and target.stat().st_size > 0:
            status = "already_exists"
        else:
            try:
                cached, child_stderr = bounded_hf_download(str(row.expected_remote_source))
                shutil.copy2(cached, target)
                status = "downloaded"
                error = child_stderr
            except subprocess.TimeoutExpired:
                status = "download_timeout"
                error = f"hf_hub_download exceeded {PER_FILE_TIMEOUT_SECONDS}s per-file timeout"
            except Exception as exc:
                status = "download_failed"
                error = f"{type(exc).__name__}: {exc}"
        verify = verify_video(target)
        rows.append(
            {
                "video_id": row.video_id,
                "filename": row.filename,
                "label": row.label,
                "expected_remote_source": row.expected_remote_source,
                "local_target_path": str(target),
                "download_status": status,
                "error": error,
                **verify,
                "maps_back_to_manifest": True,
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "manifests/downloaded_smoke_videos.csv", index=False)
    elapsed = time.time() - start
    ok = int(((df["file_exists"]) & (df["file_size"] > 0) & (df["readable"])).sum()) if not df.empty else 0
    append_progress("download_smoke_videos", "python scripts/20_download_smoke_videos.py", f"verified={ok}/{len(df)}, runtime_seconds={elapsed:.2f}", failure="" if ok == len(df) else "some downloads failed", next_action="report")
    print(f"Downloaded/verified videos: {ok}/{len(df)}")
    print(f"Target root: {VIDEOS_SMOKE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
