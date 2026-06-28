#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from video_access_common import OUT, VIDEOS_SMOKE, append_progress, markdown_table


VALID_DECISIONS = [
    "READY_FOR_10_VIDEO_SMOKE",
    "NEED_HF_AUTH_OR_LICENSE",
    "NEED_KAGGLE_MANUAL_ACCESS",
    "NEED_MANUAL_UPLOAD_OF_VIDEOS",
    "NEXAR_VIDEO_ACCESS_NOT_AVAILABLE",
]


def choose_decision(hf: dict, kaggle: dict, downloaded: pd.DataFrame) -> str:
    if not downloaded.empty:
        ok = ((downloaded["file_exists"]) & (downloaded["file_size"] > 0) & (downloaded["readable"]) & (downloaded["maps_back_to_manifest"])).sum()
        if int(ok) >= 10:
            return "READY_FOR_10_VIDEO_SMOKE"
        if "download_status" in downloaded.columns and downloaded["download_status"].astype(str).str.contains("timeout").any():
            return "NEED_HF_AUTH_OR_LICENSE"
    err = f"{hf.get('error_type', '')} {hf.get('error', '')}".lower()
    if "gated" in err or "401" in err or "403" in err or "auth" in err or "license" in err:
        return "NEED_HF_AUTH_OR_LICENSE"
    if kaggle.get("kaggle_cli_installed") and not kaggle.get("kaggle_credentials_exist"):
        return "NEED_KAGGLE_MANUAL_ACCESS"
    if not hf.get("list_files_ok") and not kaggle.get("kaggle_cli_installed"):
        return "NEED_MANUAL_UPLOAD_OF_VIDEOS"
    return "NEXAR_VIDEO_ACCESS_NOT_AVAILABLE"


def main() -> int:
    local = pd.read_csv(OUT / "manifests/local_video_file_search.csv")
    match = pd.read_csv(OUT / "manifests/local_manifest_match.csv")
    plan = pd.read_csv(OUT / "manifests/nexar_video_access_plan.csv")
    downloaded_path = OUT / "manifests/downloaded_smoke_videos.csv"
    downloaded = pd.read_csv(downloaded_path) if downloaded_path.exists() and downloaded_path.stat().st_size > 0 else pd.DataFrame()
    hf = json.loads((OUT / "manifests/huggingface_access_status.json").read_text())
    kaggle = json.loads((OUT / "manifests/kaggle_access_status.json").read_text())
    decision = choose_decision(hf, kaggle, downloaded)

    hf_counts = plan["access_status"].value_counts().reset_index()
    hf_counts.columns = ["access_status", "count"]
    smoke_plan = plan[plan["needed_for_smoke_subset"]].head(20)
    downloaded_view = downloaded[["video_id", "label", "download_status", "file_size", "duration", "readable", "maps_back_to_manifest"]] if not downloaded.empty else downloaded

    lines = [
        "# Nexar Video Access Report",
        "",
        "## 1. Goal",
        "",
        "Resolve whether Nexar videos for the Phase 1.4 candidate feasibility benchmark can be accessed through local files, Hugging Face, Kaggle, or manual upload. This run did not run VLMs, GPU inference, training, candidate generation, or full-dataset download.",
        "",
        "## 2. Local File Search",
        "",
        f"Local media files found under the target Nexar root and broader datasets tree: `{len(local)}`. Manifest rows with an existing local file before HF download: `{int(match['local_exists'].sum())}`.",
        "",
        markdown_table(match.head(20)),
        "",
        "## 3. Hugging Face Access",
        "",
        f"Dataset repo checked: `{hf.get('repo_id')}`. `huggingface-cli` installed: `{hf.get('huggingface_cli')}`. Python `datasets` installed: `{hf.get('datasets_available')}`. Repo info ok: `{hf.get('repo_info_ok')}`. File listing ok: `{hf.get('list_files_ok')}`. File count: `{hf.get('file_count')}`. Repo gated: `{hf.get('repo_gated')}`.",
        "",
        markdown_table(hf_counts),
        "",
        "## 4. Kaggle Access",
        "",
        f"Kaggle CLI installed: `{kaggle.get('kaggle_cli_installed')}`. Credentials exist: `{kaggle.get('kaggle_credentials_exist')}`. Status: `{kaggle.get('status')}`. No Kaggle download was attempted.",
        "",
        "## 5. Download Plan",
        "",
        "The plan maps every Nexar-200 manifest row to a target path and expected remote source where available. The first 50 positive and 50 normal rows are marked as the Phase 1.4 smoke subset.",
        "",
        markdown_table(smoke_plan, max_rows=20),
        "",
        "## 6. Controlled Smoke Download",
        "",
        f"Target directory: `{VIDEOS_SMOKE}`. Download cap: 5 positive and 5 normal videos.",
        "",
        markdown_table(downloaded_view, max_rows=20),
        "",
        "## 7. Verification",
        "",
        "Verification requires file exists, file size > 0, readable duration from ffprobe or OpenCV, and filename mapping back to the Nexar-200 manifest.",
        "",
    ]
    if not downloaded.empty:
        ok = int(((downloaded["file_exists"]) & (downloaded["file_size"] > 0) & (downloaded["readable"]) & (downloaded["maps_back_to_manifest"])).sum())
        lines.append(f"Verified videos: `{ok}/{len(downloaded)}`.")
    else:
        lines.append("Verified videos: `0/0`.")
    lines.extend(
        [
            "",
            "## 8. Recommendation",
            "",
        ]
    )
    if decision == "READY_FOR_10_VIDEO_SMOKE":
        lines.append("Proceed with Phase 1.4 candidate feasibility on the 10 downloaded smoke videos first. Do not expand to 200/200 until frame extraction and candidate generation runtime are measured.")
    elif decision == "NEED_HF_AUTH_OR_LICENSE":
        lines.append("HF metadata access works, but the controlled unauthenticated smoke download did not verify all 10 videos. Configure an HF token or complete any required HF access step, then rerun the access audit.")
    elif decision == "NEED_KAGGLE_MANUAL_ACCESS":
        lines.append("Configure Kaggle credentials and complete any required competition or dataset access acceptance before rerunning.")
    elif decision == "NEED_MANUAL_UPLOAD_OF_VIDEOS":
        lines.append("Manually upload or link the required smoke videos under the Nexar dataset root before rerunning.")
    else:
        lines.append("No usable direct video access path was confirmed. Recheck dataset source names or obtain the smoke videos manually.")
    lines.extend(["", f"VIDEO_ACCESS_DECISION: {decision}", ""])

    (OUT / "reports/NEXAR_VIDEO_ACCESS_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    append_progress("video_access_report", "python scripts/30_generate_video_access_report.py", f"decision={decision}", next_action="py_compile and completion audit")
    print(f"VIDEO_ACCESS_DECISION: {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
