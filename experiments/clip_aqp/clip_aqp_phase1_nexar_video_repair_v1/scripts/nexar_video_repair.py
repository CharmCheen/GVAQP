#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2
import pandas as pd
from huggingface_hub import hf_hub_download, list_repo_files
from huggingface_hub.utils import get_token


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_video_repair_v1"
MANIFEST_PATH = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/manifests/nexar_200_manifest.csv"
PRIOR_REPORT = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1/reports/NEXAR_CANDIDATE_FEASIBILITY_REPORT.md"
PRIOR_MAPPING = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1/tables/nexar_video_mapping.csv"
PRIOR_READABILITY = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1/tables/nexar_video_readability.csv"
VIDEO_DIR = ROOT / "datasets/casq_external/nexar/videos_hf"
REPO_ID = "nexar-ai/nexar_collision_prediction"
REPO_TYPE = "dataset"

DECISION_READY = "VIDEO_REPAIR_DECISION: READY_FOR_NEXAR_CANDIDATE_RERUN"
DECISION_PARTIAL = "VIDEO_REPAIR_DECISION: PARTIAL_READY_USE_READABLE_SUBSET"
DECISION_AUTH = "VIDEO_REPAIR_DECISION: NEED_HF_AUTH"
DECISION_UNSTABLE = "VIDEO_REPAIR_DECISION: HF_DOWNLOAD_UNSTABLE"
DECISION_RESOLUTION = "VIDEO_REPAIR_DECISION: MANIFEST_HF_PATH_RESOLUTION_FAILED"
DECISION_CODE = "VIDEO_REPAIR_DECISION: CODE_REVIEW_NEEDED"

REQUIRED_DIRS = ["scripts", "reports", "tables", "logs", "manifests"]
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dirs() -> None:
    for rel in REQUIRED_DIRS:
        (OUT / rel).mkdir(parents=True, exist_ok=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)


def sanitize(text: object) -> str:
    value = str(text)
    for key in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        token = os.environ.get(key)
        if token:
            value = value.replace(token, "[redacted_hf_token]")
    return value


def append_progress(checkpoint: str, command: str, result: str, failure: str = "", fix: str = "", next_action: str = "") -> None:
    ensure_dirs()
    with (OUT / "logs/progress.md").open("a", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    f"## {utc_now()}",
                    f"- checkpoint: {checkpoint}",
                    f"- commands run: `{command}`",
                    f"- result: {sanitize(result)}",
                    f"- failure if any: {sanitize(failure) if failure else 'none'}",
                    f"- fix applied: {sanitize(fix) if fix else 'none'}",
                    f"- next action: {sanitize(next_action) if next_action else 'none'}",
                    "",
                ]
            )
        )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_cmd(args: list[str], timeout: int = 30) -> dict:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=False, timeout=timeout)
        return {
            "returncode": proc.returncode,
            "stdout": sanitize(proc.stdout.strip()),
            "stderr": sanitize(proc.stderr.strip()),
        }
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": sanitize(f"{type(exc).__name__}: {exc}")}


def hf_auth_status() -> dict:
    commands = [["hf", "auth", "whoami"], ["huggingface-cli", "whoami"]]
    last_error = ""
    for _ in range(5):
        for args in commands:
            if not shutil.which(args[0]):
                continue
            result = run_cmd(args, timeout=45)
            if result["returncode"] == 0 and result["stdout"]:
                username = ""
                for line in result["stdout"].splitlines():
                    line = line.strip()
                    if line.startswith("user="):
                        username = line.split("=", 1)[1].strip()
                        break
                    if line and not line.lower().startswith(("orgs:", "token")):
                        username = line.strip()
                        break
                return {
                    "authenticated": True,
                    "username": username,
                    "method": " ".join(args),
                    "status": "authenticated",
                    "error": "",
                }
            last_error = result["stderr"] or result["stdout"] or f"returncode={result['returncode']}"
        time.sleep(2)
    token_present = bool(get_token())
    if token_present:
        return {
            "authenticated": True,
            "username": "",
            "method": "hf auth whoami retried; local token present",
            "status": "authenticated_token_present_whoami_failed",
            "error": sanitize(last_error)[:1000],
        }
    return {
        "authenticated": False,
        "username": "",
        "method": "hf auth whoami / huggingface-cli whoami",
        "status": "not_authenticated",
        "error": sanitize(last_error or "no successful whoami command")[:1000],
    }


def parse_hf_path(path: str) -> dict:
    p = Path(path)
    is_video = p.suffix.lower() in VIDEO_EXTS
    parts = path.split("/")
    split = parts[0] if len(parts) >= 3 else ""
    label = parts[1] if len(parts) >= 3 else ""
    return {
        "hf_path": path,
        "split": split,
        "label": label,
        "filename": p.name,
        "basename": p.stem,
        "is_video": is_video,
    }


def list_hf_video_files() -> pd.DataFrame:
    table_path = OUT / "tables/hf_repo_video_files.csv"
    try:
        files = list_repo_files(REPO_ID, repo_type=REPO_TYPE)
        rows = [parse_hf_path(path) for path in files]
        df = pd.DataFrame(rows)
        df.to_csv(table_path, index=False)
        append_progress("hf_repo_listing", "list_repo_files", f"repo_files={len(df)}, video_files={int(df['is_video'].sum())}")
        return df
    except Exception as exc:
        if table_path.exists():
            df = pd.read_csv(table_path)
            append_progress(
                "hf_repo_listing",
                "list_repo_files with cached fallback",
                f"used_cached_table={table_path}, rows={len(df)}",
                failure=f"{type(exc).__name__}: {exc}",
            )
            return df
        raise


def bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def filename_for_row(row: pd.Series) -> str:
    video_id = str(row.get("video_id", "")).strip()
    if video_id and video_id.lower() != "nan":
        return Path(video_id).name if Path(video_id).suffix else f"{video_id}.mp4"
    local_video_path = str(row.get("local_video_path", "")).strip()
    if local_video_path and local_video_path.lower() != "nan":
        return Path(local_video_path).name
    return ""


def resolve_manifest(manifest: pd.DataFrame, hf_df: pd.DataFrame) -> pd.DataFrame:
    video_df = hf_df[hf_df["is_video"].astype(bool)].copy()
    exact_path = set(video_df["hf_path"])
    by_filename: dict[str, list[str]] = {}
    by_basename: dict[str, list[str]] = {}
    for _, row in video_df.iterrows():
        by_filename.setdefault(str(row["filename"]), []).append(str(row["hf_path"]))
        by_basename.setdefault(str(row["basename"]), []).append(str(row["hf_path"]))

    rows = []
    for idx, row in manifest.reset_index(drop=True).iterrows():
        filename = filename_for_row(row)
        basename = Path(filename).stem if filename else str(row.get("video_id", "")).strip()
        label = str(row.get("label", "")).strip()
        split = str(row.get("split", "")).strip() or "train"
        resolved = ""
        method = ""
        status = "unresolved"
        notes = ""

        manifest_path_fields = [
            col
            for col in manifest.columns
            if col.lower() in {"hf_path", "repo_path", "dataset_path", "relative_path", "relative_video_path"}
        ]
        for col in manifest_path_fields:
            candidate = str(row.get(col, "")).strip()
            if candidate and candidate in exact_path:
                resolved = candidate
                method = f"exact_hf_path:{col}"
                break

        if not resolved and filename in by_filename:
            matches = by_filename[filename]
            if len(matches) == 1:
                resolved = matches[0]
                method = "exact_filename"
            else:
                label_matches = [m for m in matches if f"/{label}/" in m or (label == "normal" and "/negative/" in m)]
                resolved = sorted(label_matches or matches)[0]
                method = "exact_filename_label_tiebreak" if label_matches else "exact_filename_first_sorted"
                notes = f"duplicate filename matches={len(matches)}"

        if not resolved and basename in by_basename:
            matches = by_basename[basename]
            if len(matches) == 1:
                resolved = matches[0]
                method = "basename"
            else:
                label_matches = [m for m in matches if f"/{label}/" in m or (label == "normal" and "/negative/" in m)]
                resolved = sorted(label_matches or matches)[0]
                method = "basename_label_tiebreak" if label_matches else "basename_first_sorted"
                notes = f"duplicate basename matches={len(matches)}"

        if not resolved and filename:
            candidate = f"{Path(str(row.get('video_id', filename))).stem}.mp4"
            if candidate in by_filename:
                resolved = sorted(by_filename[candidate])[0]
                method = "video_id_plus_mp4"

        if not resolved and filename:
            hf_label = "positive" if bool_value(row.get("is_positive", False)) else "negative"
            guesses = [
                f"{split}/{hf_label}/{filename}",
                f"train/{hf_label}/{filename}",
                f"test-private/{hf_label}/{filename}",
            ]
            for guess in guesses:
                if guess in exact_path:
                    resolved = guess
                    method = "label_aware_path_guess"
                    break

        if resolved:
            status = "resolved"
        else:
            notes = notes or "no matching HF video path found"

        local_expected = str(VIDEO_DIR / resolved) if resolved else ""
        rows.append(
            {
                "manifest_row_id": idx,
                "video_id": row.get("video_id", ""),
                "filename": filename,
                "label": label,
                "is_positive": bool_value(row.get("is_positive", False)),
                "is_normal": bool_value(row.get("is_normal", False)),
                "resolved_hf_path": resolved,
                "resolve_status": status,
                "resolve_method": method,
                "local_expected_path": local_expected,
                "notes": notes,
            }
        )

    target_df = pd.DataFrame(rows)
    target_df.to_csv(OUT / "manifests/nexar_200_target_video_manifest.csv", index=False)
    append_progress(
        "manifest_hf_resolution",
        "resolve manifest rows against hf_repo_video_files.csv",
        f"rows={len(target_df)}, resolved={int((target_df['resolve_status'] == 'resolved').sum())}",
        failure="" if (target_df["resolve_status"] == "resolved").all() else "some manifest rows unresolved",
    )
    return target_df


def ffprobe_duration(path: Path) -> tuple[float, bool]:
    if not path.exists() or path.stat().st_size <= 0:
        return 0.0, False
    result = run_cmd(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        timeout=20,
    )
    if result["returncode"] != 0 or not result["stdout"]:
        return 0.0, False
    try:
        duration = float(result["stdout"].splitlines()[0])
    except Exception:
        return 0.0, False
    return duration, math.isfinite(duration) and duration > 0


def probe_video(path: Path) -> dict:
    file_size = int(path.stat().st_size) if path.exists() else 0
    duration, duration_ok = ffprobe_duration(path)
    first_frame_readable = False
    cv_duration = 0.0
    if path.exists() and file_size > 0:
        cap = cv2.VideoCapture(str(path))
        if cap.isOpened():
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            cv_duration = float(frame_count / fps) if fps > 0 and frame_count > 0 else 0.0
            ok, _ = cap.read()
            first_frame_readable = bool(ok)
        cap.release()
    chosen_duration = duration if duration_ok else cv_duration
    return {
        "file_size_bytes": file_size,
        "readable": bool(file_size > 0 and (duration_ok or cv_duration > 0) and first_frame_readable),
        "duration_seconds": chosen_duration,
        "first_frame_readable": first_frame_readable,
    }


def local_inventory() -> pd.DataFrame:
    rows = []
    for path in sorted(VIDEO_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTS:
            continue
        meta = probe_video(path)
        rows.append(
            {
                "local_path": str(path),
                "filename": path.name,
                "relative_path_under_videos_hf": str(path.relative_to(VIDEO_DIR)).replace("\\", "/"),
                **meta,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "local_path",
                "filename",
                "relative_path_under_videos_hf",
                "file_size_bytes",
                "readable",
                "duration_seconds",
                "first_frame_readable",
            ]
        )
    df.to_csv(OUT / "tables/local_videos_hf_inventory.csv", index=False)
    append_progress("local_inventory", "scan videos_hf", f"local_video_files={len(df)}, readable={int(df['readable'].sum()) if len(df) else 0}")
    return df


def match_local(target_df: pd.DataFrame, inventory_df: pd.DataFrame, output_name: str) -> pd.DataFrame:
    by_rel = {str(row["relative_path_under_videos_hf"]): row for _, row in inventory_df.iterrows()}
    by_name: dict[str, list[pd.Series]] = {}
    for _, row in inventory_df.iterrows():
        by_name.setdefault(str(row["filename"]), []).append(row)

    rows = []
    for _, target in target_df.iterrows():
        resolved = str(target.get("resolved_hf_path", "") or "")
        filename = str(target.get("filename", "") or "")
        matched = None
        status = "missing"
        notes = ""
        if resolved and resolved in by_rel:
            matched = by_rel[resolved]
            status = "matched_exact_relative_path"
        elif filename in by_name:
            label = str(target.get("label", ""))
            candidates = by_name[filename]
            label_matches = [
                r
                for r in candidates
                if f"/{label}/" in str(r["relative_path_under_videos_hf"])
                or (label == "normal" and "/negative/" in str(r["relative_path_under_videos_hf"]))
            ]
            matched = sorted(label_matches or candidates, key=lambda r: str(r["relative_path_under_videos_hf"]))[0]
            status = "matched_filename_label_tiebreak" if label_matches else "matched_filename"
            if len(candidates) > 1:
                notes = f"duplicate local filename matches={len(candidates)}"
        readable = bool(matched is not None and matched["readable"])
        rows.append(
            {
                "manifest_row_id": int(target["manifest_row_id"]),
                "video_id": target["video_id"],
                "filename": filename,
                "label": target["label"],
                "resolved_hf_path": resolved,
                "local_match_status": status,
                "local_matched_path": str(matched["local_path"]) if matched is not None else "",
                "readable": readable,
                "notes": notes,
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"tables/{output_name}", index=False)
    return df


def copy_from_hf_cache(cached_path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return
    if cached_path.resolve() == destination.resolve():
        return
    shutil.copy2(cached_path, destination)


def download_one_child(resolved: str, destination_text: str) -> int:
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")
    destination = Path(destination_text)
    try:
        cached = Path(
            hf_hub_download(
                repo_id=REPO_ID,
                filename=resolved,
                repo_type=REPO_TYPE,
                local_dir=str(VIDEO_DIR),
            )
        )
        copy_from_hf_cache(cached, destination)
        ok = destination.exists() and destination.stat().st_size > 0
        print(json.dumps({"ok": ok, "local_path": str(destination), "file_size_bytes": destination.stat().st_size if ok else 0}, sort_keys=True))
        return 0 if ok else 2
    except Exception as exc:
        print(json.dumps({"ok": False, "error": sanitize(f"{type(exc).__name__}: {exc}")[:1000]}, sort_keys=True), file=sys.stderr)
        return 1


def download_missing(target_df: pd.DataFrame, pre_match: pd.DataFrame) -> pd.DataFrame:
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")
    pre_by_id = pre_match.set_index("manifest_row_id").to_dict("index")
    rows = []
    for _, target in target_df.iterrows():
        row_id = int(target["manifest_row_id"])
        resolved = str(target.get("resolved_hf_path", "") or "")
        label = str(target.get("label", ""))
        existing = pre_by_id.get(row_id, {})
        local_path = Path(str(target.get("local_expected_path", "") or "")) if resolved else Path("")
        if not resolved:
            rows.append(
                {
                    "manifest_row_id": row_id,
                    "video_id": target["video_id"],
                    "label": label,
                    "resolved_hf_path": resolved,
                    "download_status": "skipped_unresolved_hf_path",
                    "local_path": "",
                    "file_size_bytes": 0,
                    "attempts": 0,
                    "error": "unresolved_hf_path",
                }
            )
            continue
        if bool(existing.get("readable", False)):
            matched_path = Path(str(existing.get("local_matched_path", "")))
            rows.append(
                {
                    "manifest_row_id": row_id,
                    "video_id": target["video_id"],
                    "label": label,
                    "resolved_hf_path": resolved,
                    "download_status": "skipped_already_readable",
                    "local_path": str(matched_path),
                    "file_size_bytes": int(matched_path.stat().st_size) if matched_path.exists() else 0,
                    "attempts": 0,
                    "error": "",
                }
            )
            continue

        attempts = 0
        status = "failed"
        error = ""
        for attempt in range(1, 4):
            attempts = attempt
            result = run_cmd(
                [sys.executable, str(Path(__file__).resolve()), "--download-one", resolved, str(local_path)],
                timeout=240,
            )
            if result["returncode"] == 0 and local_path.exists() and local_path.stat().st_size > 0:
                status = "downloaded"
                error = ""
                break
            if result["returncode"] == -1:
                error = f"download_timeout_or_subprocess_error: {result['stderr'][:800]}"
            else:
                error = (result["stderr"] or result["stdout"] or f"download_subprocess_returncode={result['returncode']}")[:1000]
            if local_path.exists() and local_path.stat().st_size > 0:
                status = "downloaded"
                error = ""
                break
            else:
                time.sleep(min(2 * attempt, 5))
        rows.append(
            {
                "manifest_row_id": row_id,
                "video_id": target["video_id"],
                "label": label,
                "resolved_hf_path": resolved,
                "download_status": status,
                "local_path": str(local_path),
                "file_size_bytes": int(local_path.stat().st_size) if local_path.exists() else 0,
                "attempts": attempts,
                "error": error,
            }
        )
        if row_id % 25 == 0:
            append_progress("download_progress", "hf_hub_download targeted manifest rows", f"processed_manifest_row_id={row_id}")
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "tables/download_repair_results.csv", index=False)
    status_counts = dict(Counter(df["download_status"]))
    append_progress("download_repair", "hf_hub_download missing/unreadable manifest targets", json.dumps(status_counts, sort_keys=True))
    return df


def post_download_readability(target_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, target in target_df.iterrows():
        path = Path(str(target.get("local_expected_path", "") or ""))
        exists = bool(str(path) and path.exists())
        meta = probe_video(path) if exists else {"file_size_bytes": 0, "readable": False, "duration_seconds": 0.0, "first_frame_readable": False}
        rows.append(
            {
                "manifest_row_id": int(target["manifest_row_id"]),
                "video_id": target["video_id"],
                "filename": target["filename"],
                "label": target["label"],
                "is_positive": bool_value(target["is_positive"]),
                "is_normal": bool_value(target["is_normal"]),
                "resolved_hf_path": target["resolved_hf_path"],
                "local_path": str(path) if str(path) else "",
                "exists": exists,
                **meta,
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "tables/post_download_manifest_readability.csv", index=False)
    return df


def aggregate_stats(readability: pd.DataFrame) -> dict:
    total = len(readability)
    readable = int(readability["readable"].sum())
    pos = readability[readability["is_positive"].astype(bool)]
    normal = readability[readability["is_normal"].astype(bool)]
    stats = {
        "total_manifest_rows": total,
        "readable_rows": readable,
        "readable_fraction": readable / total if total else 0.0,
        "positive_readable": int(pos["readable"].sum()),
        "positive_total": len(pos),
        "positive_readable_fraction": int(pos["readable"].sum()) / len(pos) if len(pos) else 0.0,
        "normal_readable": int(normal["readable"].sum()),
        "normal_total": len(normal),
        "normal_readable_fraction": int(normal["readable"].sum()) / len(normal) if len(normal) else 0.0,
    }
    write_json(OUT / "tables/post_download_readability_stats.json", stats)
    return stats


def decide(auth: dict, target_df: pd.DataFrame, download_df: pd.DataFrame, stats: dict) -> str:
    if not auth.get("authenticated"):
        return DECISION_AUTH
    unresolved = int((target_df["resolve_status"] != "resolved").sum())
    if unresolved > max(5, int(0.05 * len(target_df))):
        return DECISION_RESOLUTION
    inconsistent = (
        stats["readable_rows"] > stats["total_manifest_rows"]
        or stats["positive_readable"] > stats["positive_total"]
        or stats["normal_readable"] > stats["normal_total"]
    )
    if inconsistent:
        return DECISION_CODE
    failed_downloads = download_df[download_df["download_status"].eq("failed")]
    if len(failed_downloads) > 0 and stats["readable_fraction"] < 0.95:
        return DECISION_UNSTABLE
    if stats["readable_fraction"] >= 0.95 and stats["positive_readable_fraction"] >= 0.95:
        return DECISION_READY
    if stats["readable_rows"] >= 100 and stats["positive_readable"] >= 50 and stats["normal_readable"] >= 50:
        return DECISION_PARTIAL
    if len(failed_downloads) > 0:
        return DECISION_UNSTABLE
    return DECISION_RESOLUTION


def markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows).copy()
    lines = ["| " + " | ".join(view.columns) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        vals = []
        for col in view.columns:
            value = row[col]
            if isinstance(value, float):
                vals.append(f"{value:.4g}" if math.isfinite(value) else "")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_report(
    auth: dict,
    manifest: pd.DataFrame,
    hf_df: pd.DataFrame,
    target_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    pre_match: pd.DataFrame,
    download_df: pd.DataFrame,
    post_df: pd.DataFrame,
    stats: dict,
    decision: str,
) -> None:
    manifest_summary = pd.DataFrame(
        [
            {"metric": "total_rows", "value": len(manifest)},
            {"metric": "positive_rows", "value": int(manifest["is_positive"].map(bool_value).sum())},
            {"metric": "normal_negative_rows", "value": int(manifest["is_normal"].map(bool_value).sum())},
            {"metric": "available_columns", "value": ", ".join(manifest.columns)},
            {"metric": "filename_video_id_fields", "value": "video_id, local_video_path"},
        ]
    )
    resolve_summary = target_df.groupby(["resolve_status", "resolve_method"], dropna=False).size().reset_index(name="rows")
    pre_summary = pre_match.groupby(["label"], dropna=False).agg(rows=("video_id", "count"), readable=("readable", "sum")).reset_index()
    download_summary = download_df.groupby("download_status", dropna=False).size().reset_index(name="rows")
    remaining = post_df[~post_df["readable"].astype(bool)][
        ["manifest_row_id", "video_id", "label", "resolved_hf_path", "local_path", "exists", "file_size_bytes", "readable"]
    ]
    previous_failure = ""
    if PRIOR_REPORT.exists():
        previous_failure = "Previous candidate gate report exists and recorded 76 / 400 readable rows with 0 readable positives."
    else:
        previous_failure = "Previous candidate gate report was not found at the expected path."

    report = f"""# Nexar Video Repair Report

## 1. Goal

Repair Nexar-200 video mapping by downloading exactly the videos required by `nexar_200_manifest.csv`, preserving Hugging Face relative paths under `videos_hf`.

## 2. Why previous candidate run failed

{previous_failure}

Prior artifacts used:

- `{PRIOR_REPORT}`
- `{PRIOR_MAPPING}`
- `{PRIOR_READABILITY}`

## 3. HF authentication status

- Status: `{auth.get('status')}`
- Username: `{auth.get('username')}`
- Method: `{auth.get('method')}`

No Hugging Face token is printed or logged.

## 4. Manifest summary

{markdown_table(manifest_summary)}

## 5. HF path resolution

- HF repo files listed: `{len(hf_df)}`
- HF video files listed: `{int(hf_df['is_video'].sum()) if len(hf_df) else 0}`
- Manifest rows resolved: `{int((target_df['resolve_status'] == 'resolved').sum())} / {len(target_df)}`

{markdown_table(resolve_summary, max_rows=30)}

Target manifest: `manifests/nexar_200_target_video_manifest.csv`.

## 6. Pre-download local inventory

- Local video files under `videos_hf`: `{len(inventory_df)}`
- Readable local video files under `videos_hf`: `{int(inventory_df['readable'].sum()) if len(inventory_df) else 0}`

Manifest-local match before download:

{markdown_table(pre_summary)}

Explicit pre-download counts:

- readable positive rows: `{int(pre_match[(pre_match['label'] == 'positive') & pre_match['readable']].shape[0])}`
- readable normal rows: `{int(pre_match[(pre_match['label'] == 'normal') & pre_match['readable']].shape[0])}`
- missing positive rows: `{int(pre_match[(pre_match['label'] == 'positive') & ~pre_match['readable']].shape[0])}`
- missing normal rows: `{int(pre_match[(pre_match['label'] == 'normal') & ~pre_match['readable']].shape[0])}`

## 7. Download repair result

{markdown_table(download_summary)}

Download table: `tables/download_repair_results.csv`.

## 8. Post-download readability

- total_manifest_rows: `{stats['total_manifest_rows']}`
- readable_rows: `{stats['readable_rows']}`
- readable_fraction: `{stats['readable_fraction']:.4f}`
- positive_readable: `{stats['positive_readable']} / {stats['positive_total']}` (`{stats['positive_readable_fraction']:.4f}`)
- normal_readable: `{stats['normal_readable']} / {stats['normal_total']}` (`{stats['normal_readable_fraction']:.4f}`)

Post-download table: `tables/post_download_manifest_readability.csv`.

## 9. Remaining missing/unreadable files

Remaining unreadable manifest rows: `{len(remaining)}`.

{markdown_table(remaining, max_rows=30)}

## 10. Recommendation

Do not run candidate generation in this repair step. If the decision is `READY_FOR_NEXAR_CANDIDATE_RERUN`, rerun the Nexar candidate feasibility pipeline against the repaired `videos_hf` tree. If only partial readiness is reached, use an explicitly documented readable subset rather than claiming Nexar-200 completion.

{decision}
"""
    (OUT / "reports/NEXAR_VIDEO_REPAIR_REPORT.md").write_text(report, encoding="utf-8")
    append_progress("report", "write NEXAR_VIDEO_REPAIR_REPORT.md", f"decision={decision}")


def write_auth_blocked_report(auth: dict) -> None:
    empty_download = pd.DataFrame(
        columns=["manifest_row_id", "video_id", "label", "resolved_hf_path", "download_status", "local_path", "file_size_bytes", "attempts", "error"]
    )
    empty_download.to_csv(OUT / "tables/download_repair_results.csv", index=False)
    report = f"""# Nexar Video Repair Report

## 1. Goal

Repair Nexar-200 video mapping by downloading exactly the videos required by `nexar_200_manifest.csv`.

## 2. Why previous candidate run failed

The previous candidate gate failed because too few manifest videos were readable.

## 3. HF authentication status

- Status: `{auth.get('status')}`
- Username: ``
- Method: `{auth.get('method')}`

No Hugging Face token is printed or logged.

## 4. Manifest summary

Not loaded beyond the authentication gate.

## 5. HF path resolution

Not run.

## 6. Pre-download local inventory

Not run.

## 7. Download repair result

Not run.

## 8. Post-download readability

Not run.

## 9. Remaining missing/unreadable files

Unknown because authentication is required before listing/downloading dataset files.

## 10. Recommendation

Authenticate Hugging Face locally and rerun `scripts/run_nexar_video_repair.sh`.

{DECISION_AUTH}
"""
    (OUT / "reports/NEXAR_VIDEO_REPAIR_REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--download-one":
        return download_one_child(sys.argv[2], sys.argv[3])

    ensure_dirs()
    start = time.time()
    auth = hf_auth_status()
    write_json(OUT / "logs/hf_auth_status.json", auth)
    append_progress("hf_auth", "hf auth whoami / huggingface-cli whoami", f"status={auth['status']}, username={auth.get('username', '')}")
    if not auth["authenticated"]:
        write_auth_blocked_report(auth)
        print(json.dumps({"decision": DECISION_AUTH, "authenticated": False}, sort_keys=True))
        return 0

    manifest = pd.read_csv(MANIFEST_PATH)
    write_json(
        OUT / "logs/manifest_summary.json",
        {
            "path": str(MANIFEST_PATH),
            "total_rows": len(manifest),
            "positive_rows": int(manifest["is_positive"].map(bool_value).sum()),
            "normal_rows": int(manifest["is_normal"].map(bool_value).sum()),
            "columns": list(manifest.columns),
            "filename_video_id_fields": ["video_id", "local_video_path"],
        },
    )
    append_progress("manifest_audit", "read nexar_200_manifest.csv", f"rows={len(manifest)}, columns={len(manifest.columns)}")

    hf_df = list_hf_video_files()
    target_df = resolve_manifest(manifest, hf_df)
    inventory_df = local_inventory()
    pre_match = match_local(target_df, inventory_df, "pre_download_manifest_local_match.csv")
    append_progress(
        "pre_download_match",
        "match target manifest to local inventory",
        (
            f"readable_positive={int(pre_match[(pre_match['label'] == 'positive') & pre_match['readable']].shape[0])}, "
            f"readable_normal={int(pre_match[(pre_match['label'] == 'normal') & pre_match['readable']].shape[0])}"
        ),
    )

    unresolved = int((target_df["resolve_status"] != "resolved").sum())
    if unresolved > max(5, int(0.05 * len(target_df))):
        download_df = pd.DataFrame(
            columns=["manifest_row_id", "video_id", "label", "resolved_hf_path", "download_status", "local_path", "file_size_bytes", "attempts", "error"]
        )
        download_df.to_csv(OUT / "tables/download_repair_results.csv", index=False)
        post_df = post_download_readability(target_df)
        stats = aggregate_stats(post_df)
        decision = DECISION_RESOLUTION
        write_report(auth, manifest, hf_df, target_df, inventory_df, pre_match, download_df, post_df, stats, decision)
        print(json.dumps({"decision": decision, "unresolved": unresolved}, sort_keys=True))
        return 0

    download_df = download_missing(target_df, pre_match)
    post_df = post_download_readability(target_df)
    stats = aggregate_stats(post_df)
    decision = decide(auth, target_df, download_df, stats)
    write_json(OUT / "logs/run_summary.json", {"decision": decision, "runtime_seconds": time.time() - start, **stats})
    write_report(auth, manifest, hf_df, target_df, inventory_df, pre_match, download_df, post_df, stats, decision)
    print(json.dumps({"decision": decision, "readable_fraction": stats["readable_fraction"], "positive_readable_fraction": stats["positive_readable_fraction"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
