#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from auth_video_common import OUT, PREV_REPORT, append_progress, markdown_table


VALID_DECISIONS = [
    "READY_FOR_CANDIDATE_SMOKE",
    "NEED_HF_AUTH_OR_LICENSE",
    "DOWNLOAD_UNSTABLE_RETRY_NEEDED",
    "NEED_MANUAL_UPLOAD_OF_VIDEOS",
    "CODE_REVIEW_NEEDED",
]


def choose_decision(auth: dict, checks: pd.DataFrame, manifest: pd.DataFrame) -> str:
    if auth.get("auth_status") != "authenticated":
        return "NEED_HF_AUTH_OR_LICENSE"
    if checks.empty or len(checks) != len(manifest):
        return "CODE_REVIEW_NEEDED"
    good = int(((checks["file_exists"]) & (checks["file_size_bytes"] > 0) & (checks["readable"]) & (checks["frame_read_ok"]) & (checks["maps_back_to_manifest"])).sum())
    if good >= 8:
        return "READY_FOR_CANDIDATE_SMOKE"
    if checks["auth_download_status"].astype(str).str.contains("timeout|failed", regex=True).any():
        return "DOWNLOAD_UNSTABLE_RETRY_NEEDED"
    return "NEED_MANUAL_UPLOAD_OF_VIDEOS"


def main() -> int:
    auth = pd.read_json(OUT / "manifests/hf_auth_status.json", typ="series").to_dict()
    manifest = pd.read_csv(OUT / "manifests/nexar_auth_smoke_manifest.csv")
    checks = pd.read_csv(OUT / "checks/video_readability_checks.csv")
    frame_status = pd.read_csv(OUT / "checks/frame_smoke_status.csv")
    frame_index = pd.read_csv(OUT / "checks/frame_smoke_index.csv")
    decision = choose_decision(auth, checks, manifest)

    auth_public = pd.DataFrame(
        [
            {
                "auth_status": auth.get("auth_status"),
                "hf_cli_available": auth.get("hf_cli_available"),
                "huggingface_cli_available": auth.get("huggingface_cli_available"),
                "whoami_returncode": auth.get("whoami_returncode"),
                "whoami_user": auth.get("whoami_user") if auth.get("auth_status") == "authenticated" else "",
                "message": "token never printed; auth checked via CLI whoami",
            }
        ]
    )
    prev_summary = "Previous audit found HF repo public/listable with 2,857 files, Nexar-200 filenames mapped to HF paths, Kaggle not configured, and 1/10 unauthenticated smoke videos verified before remaining downloads timed out."
    readable_count = int(checks["readable"].astype(bool).sum()) if not checks.empty else 0
    frame_read_count = int(checks["frame_read_ok"].astype(bool).sum()) if "frame_read_ok" in checks else 0

    lines = [
        "# Nexar Authenticated Video Access Report",
        "",
        "## 1. Goal",
        "",
        "Rerun Nexar video access with Hugging Face authentication and proceed only to a bounded 10-video smoke test. This run did not run VLMs, train models, run GPU inference, or run candidate generation.",
        "",
        "## 2. HF auth status",
        "",
        markdown_table(auth_public),
        "",
        "## 3. Previous access result summary",
        "",
        prev_summary,
        "",
        f"Prior report: `{PREV_REPORT}`.",
        "",
        "## 4. Authenticated smoke manifest",
        "",
        markdown_table(manifest),
        "",
        "## 5. Download results",
        "",
        markdown_table(checks[["video_id", "label", "auth_download_status", "attempt_count", "file_size_bytes", "duration_seconds", "readable"]]),
        "",
        "## 6. Video readability verification",
        "",
        f"Readable videos: `{readable_count}/{len(checks)}`. Videos with at least one frame read: `{frame_read_count}/{len(checks)}`.",
        "",
        markdown_table(checks[["video_id", "file_exists", "file_size_bytes", "duration_seconds", "readable", "frame_read_ok", "maps_back_to_manifest"]]),
        "",
        "## 7. Frame smoke result",
        "",
        markdown_table(frame_status),
        "",
        f"Frame index rows: `{len(frame_index)}`.",
        "",
        "## 8. Remaining blockers",
        "",
    ]
    if decision == "NEED_HF_AUTH_OR_LICENSE":
        lines.append("HF CLI is available, but this environment is not logged in. Missing-video downloads were intentionally skipped to avoid unauthenticated retries and token leakage.")
    elif decision == "DOWNLOAD_UNSTABLE_RETRY_NEEDED":
        lines.append("HF auth exists, but fewer than 8/10 smoke videos verified because downloads failed or timed out.")
    elif decision == "READY_FOR_CANDIDATE_SMOKE":
        lines.append("No access blocker remains for a bounded candidate smoke test on the verified videos.")
    elif decision == "NEED_MANUAL_UPLOAD_OF_VIDEOS":
        lines.append("HF paths are known, but direct download did not provide enough readable videos; manually upload the smoke videos.")
    else:
        lines.append("Manifest mapping or verification outputs are inconsistent and need code review.")
    lines.extend(
        [
            "",
            "## 9. Recommendation",
            "",
        ]
    )
    if decision == "NEED_HF_AUTH_OR_LICENSE":
        lines.append("Run `hf auth login` or otherwise configure a valid Hugging Face token outside the logs, then rerun `scripts/run_nexar_auth_video_access.sh`.")
    elif decision == "READY_FOR_CANDIDATE_SMOKE":
        lines.append("Proceed to a bounded Phase 1.4 candidate smoke on these videos only; do not expand to full Nexar without a separate approval.")
    else:
        lines.append("Resolve the blocker above before candidate generation.")
    lines.extend(["", f"VIDEO_AUTH_DECISION: {decision}", ""])

    (OUT / "reports/NEXAR_AUTH_VIDEO_ACCESS_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    append_progress("auth_video_report", "python scripts/30_generate_auth_video_report.py", f"decision={decision}", next_action="py_compile and completion audit")
    print(f"VIDEO_AUTH_DECISION: {decision}")
    if decision not in VALID_DECISIONS:
        raise AssertionError(f"invalid decision {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

