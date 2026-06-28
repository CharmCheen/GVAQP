#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1"
MANIFEST_PATH = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/manifests/nexar_200_manifest.csv"
EVENTS_PATH = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/converted/casq_events_nexar_200.csv"
UNITS_PATH = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/converted/casq_units_nexar_200.csv"
VIDEO_DIR = ROOT / "datasets/casq_external/nexar/videos_hf"
SUMMARY_PATH = ROOT / "garc_eval/outputs/clip_aqp_phase1_nexar_candidate_v1_summary.md"

REQUIRED_DIRS = [
    "scripts",
    "reports",
    "tables",
    "figures",
    "logs",
    "frames",
    "features",
    "candidates",
    "audits",
    "config",
    "data_manifest",
]

DECISION_VIDEO_FAILED = "NEXAR_CANDIDATE_DECISION: VIDEO_MAPPING_OR_READABILITY_FAILED"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dirs() -> None:
    for rel in REQUIRED_DIRS:
        (OUT / rel).mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)


def append_progress(checkpoint: str, command: str, result: str, failure: str = "", fix: str = "", next_action: str = "") -> None:
    ensure_dirs()
    with (OUT / "logs/progress.md").open("a", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    f"## {utc_now()}",
                    f"- checkpoint: {checkpoint}",
                    f"- commands run: `{command}`",
                    f"- result: {result}",
                    f"- failure if any: {failure or 'none'}",
                    f"- fix applied: {fix or 'none'}",
                    f"- next action: {next_action or 'none'}",
                    "",
                ]
            )
        )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sh(args: list[str], timeout: int = 20) -> dict:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}


def detect_gpu() -> dict:
    info = {
        "checked_utc": utc_now(),
        "gpu_visible": False,
        "gpu_used": False,
        "gpu_model": "",
        "torch_cuda_available": False,
        "notes": "No YOLO or visual feature extraction was run because the video access gate failed before candidate generation.",
    }
    try:
        import torch

        info["torch_cuda_available"] = bool(torch.cuda.is_available())
        info["gpu_visible"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            info["gpu_model"] = str(torch.cuda.get_device_name(0))
    except Exception as exc:
        info["notes"] = f"torch GPU check failed: {type(exc).__name__}: {exc}"
    return info


def ffprobe_duration(path: Path) -> tuple[float, bool, str]:
    result = sh(
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
        timeout=15,
    )
    if result["returncode"] != 0:
        return 0.0, False, result["stderr"][:500]
    try:
        duration = float(result["stdout"].splitlines()[0])
    except Exception as exc:
        return 0.0, False, f"parse_error: {type(exc).__name__}: {exc}; stdout={result['stdout'][:120]}"
    return duration, math.isfinite(duration) and duration > 0, ""


def opencv_probe(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    opened = bool(cap.isOpened())
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = float(frame_count / fps) if fps > 0 and frame_count > 0 else 0.0
    first_frame_readable = False
    if opened:
        ok, _ = cap.read()
        first_frame_readable = bool(ok)
    cap.release()
    return {
        "opencv_opened": opened,
        "opencv_duration_seconds": duration,
        "opencv_fps": fps,
        "opencv_frame_count": frame_count,
        "opencv_width": width,
        "opencv_height": height,
        "first_frame_readable": first_frame_readable,
    }


def normalize_rel(path: Path) -> str:
    return str(path).replace("\\", "/")


def build_video_index(video_dir: Path) -> tuple[list[Path], dict[str, Path]]:
    files = sorted(p for p in video_dir.rglob("*.mp4") if p.is_file())
    index: dict[str, Path] = {}
    for path in files:
        rel = normalize_rel(path.relative_to(video_dir))
        keys = {
            path.name,
            path.stem,
            rel,
            f"{path.stem}.mp4",
        }
        for key in keys:
            index.setdefault(key, path)
    return files, index


def match_manifest_row(row: pd.Series, index: dict[str, Path], video_dir: Path) -> tuple[str, str, Path | None]:
    video_id = str(row.get("video_id", "")).strip()
    local_video_path = str(row.get("local_video_path", "")).strip()
    candidates: list[tuple[str, str]] = []
    if video_id:
        candidates.extend(
            [
                ("exact_filename", video_id),
                ("basename", Path(video_id).name),
                ("video_id_plus_mp4", f"{Path(video_id).stem}.mp4"),
            ]
        )
    if local_video_path:
        local_path = Path(local_video_path)
        candidates.append(("basename", local_path.name))
        rel_parts = local_path.parts[-3:]
        if rel_parts:
            candidates.append(("relative_path", normalize_rel(Path(*rel_parts))))
    for method, key in candidates:
        if key in index:
            return method, key, index[key]
    return "unmatched", "", None


def audit_mapping_and_readability() -> dict:
    start = time.time()
    manifest = pd.read_csv(MANIFEST_PATH)
    events = pd.read_csv(EVENTS_PATH)
    units = pd.read_csv(UNITS_PATH)
    files, index = build_video_index(VIDEO_DIR)

    mapping_rows = []
    readability_rows = []
    for _, row in manifest.iterrows():
        method, key, path = match_manifest_row(row, index, VIDEO_DIR)
        mapped = path is not None
        file_exists = bool(path and path.exists())
        file_size = int(path.stat().st_size) if file_exists else 0
        ff_duration = 0.0
        ff_ok = False
        ff_error = ""
        cv_meta = {
            "opencv_opened": False,
            "opencv_duration_seconds": 0.0,
            "opencv_fps": 0.0,
            "opencv_frame_count": 0,
            "opencv_width": 0,
            "opencv_height": 0,
            "first_frame_readable": False,
        }
        if file_exists and file_size > 0:
            ff_duration, ff_ok, ff_error = ffprobe_duration(path)
            cv_meta = opencv_probe(path)
        duration_readable = bool(ff_ok or cv_meta["opencv_duration_seconds"] > 0)
        readable = bool(file_exists and file_size > 0 and duration_readable and cv_meta["first_frame_readable"])
        common = {
            "dataset": row.get("dataset", ""),
            "video_id": row.get("video_id", ""),
            "split": row.get("split", ""),
            "label": row.get("label", ""),
            "is_positive": bool(row.get("is_positive", False)),
            "is_normal": bool(row.get("is_normal", False)),
            "manifest_local_video_path": row.get("local_video_path", ""),
            "matched_video_path": str(path) if path else "",
            "match_method": method,
            "match_key": key,
            "filename_maps_to_manifest": mapped,
        }
        mapping_rows.append(common)
        readability_rows.append(
            {
                **common,
                "file_exists": file_exists,
                "file_size_bytes": file_size,
                "file_size_gt_zero": file_size > 0,
                "duration_readable": duration_readable,
                "ffprobe_duration_seconds": ff_duration,
                "ffprobe_ok": ff_ok,
                "ffprobe_error": ff_error,
                **cv_meta,
                "readable": readable,
            }
        )

    mapping_df = pd.DataFrame(mapping_rows)
    readability_df = pd.DataFrame(readability_rows)
    mapping_df.to_csv(OUT / "tables/nexar_video_mapping.csv", index=False)
    readability_df.to_csv(OUT / "tables/nexar_video_readability.csv", index=False)

    positive = manifest[manifest["is_positive"].astype(bool)].head(50).copy()
    normal = manifest[manifest["is_normal"].astype(bool)].head(50).copy()
    smoke = pd.concat([positive, normal], ignore_index=True)
    smoke = smoke.merge(
        readability_df[["video_id", "matched_video_path", "readable"]],
        on="video_id",
        how="left",
    )
    smoke["subset"] = "stage_a_smoke_requested"
    smoke["subset_status"] = smoke["readable"].map(lambda x: "readable" if bool(x) else "not_readable_or_unmapped")
    smoke.to_csv(OUT / "tables/nexar_candidate_subset_smoke.csv", index=False)

    full = manifest.merge(
        readability_df[["video_id", "matched_video_path", "readable"]],
        on="video_id",
        how="left",
    )
    full["subset"] = "stage_b_nexar_200_requested"
    full["subset_status"] = full["readable"].map(lambda x: "readable" if bool(x) else "not_readable_or_unmapped")
    full.to_csv(OUT / "tables/nexar_candidate_subset_200.csv", index=False)

    # Empty schema-only outputs for downstream stages that are intentionally skipped by the access gate.
    pd.DataFrame(
        columns=[
            "video_id",
            "frame_id",
            "timestamp",
            "frame_path",
            "source_video_path",
            "subset",
            "extraction_fps",
        ]
    ).to_csv(OUT / "tables/nexar_frame_index.csv", index=False)

    pd.DataFrame(
        columns=[
            "subset",
            "candidate_name",
            "theta",
            "budget_type",
            "budget_value",
            "merge_gap",
            "num_returned_clips",
            "total_returned_duration",
            "mean_returned_clip_duration",
            "true_derived_recall",
            "event_hit_count",
            "event_total_count",
            "precision_if_definable",
            "runtime_seconds",
            "frames_processed",
            "videos_processed",
            "throughput_fps",
        ]
    ).to_csv(OUT / "tables/nexar_candidate_eval_results.csv", index=False)

    pd.DataFrame(
        columns=[
            "candidate_name",
            "gamma",
            "delta",
            "block_size",
            "certification_sample_fraction",
            "trials",
            "sample_split",
            "used_for_design",
            "used_for_repair",
            "certificate_success_rate",
            "GVR",
            "median_LCB_recall",
            "notes",
        ]
    ).to_csv(OUT / "tables/nexar_candidate_certificate_results.csv", index=False)

    for candidate_name in [
        "fixed_sliding_window",
        "random_window",
        "motion_energy",
        "yolo_count_proxy",
        "existing_local_candidate_pipeline",
        "optional_clip_or_siglip_score",
    ]:
        pd.DataFrame(
            columns=[
                "subset",
                "candidate_name",
                "video_id",
                "returned_clip_id",
                "start_time",
                "end_time",
                "score",
                "rank",
                "generation_rule",
                "uses_oracle_annotation",
                "uses_video_content",
                "model_name",
                "runtime_seconds",
                "notes",
            ]
        ).to_csv(OUT / f"candidates/stage_not_run_{candidate_name}.csv", index=False)

    total = len(readability_df)
    mapped = int(readability_df["filename_maps_to_manifest"].sum())
    readable = int(readability_df["readable"].sum())
    readable_rate = float(readable / total) if total else 0.0
    pos_readable = int(readability_df[readability_df["is_positive"]]["readable"].sum())
    normal_readable = int(readability_df[readability_df["is_normal"]]["readable"].sum())
    elapsed = time.time() - start
    input_manifest = pd.DataFrame(
        [
            {"artifact": "manifest", "path": str(MANIFEST_PATH), "rows": len(manifest), "columns": ";".join(manifest.columns)},
            {"artifact": "events", "path": str(EVENTS_PATH), "rows": len(events), "columns": ";".join(events.columns)},
            {"artifact": "units", "path": str(UNITS_PATH), "rows": len(units), "columns": ";".join(units.columns)},
            {"artifact": "video_dir", "path": str(VIDEO_DIR), "rows": len(files), "columns": "mp4 files"},
        ]
    )
    input_manifest.to_csv(OUT / "data_manifest/input_manifest.csv", index=False)

    config = {
        "experiment": "clip_aqp_phase1_nexar_candidate_v1",
        "created_utc": utc_now(),
        "random_seed": 20260622,
        "no_download": True,
        "no_vlm_oracle": True,
        "no_training": True,
        "leakage_rule": "event_start/event_end/event_moment/alert_time evaluation-only; mapping/readability used no event timing fields",
        "video_access_gate_min_readable_fraction": 0.80,
        "stage_a_requested": "50 positive videos + 50 normal videos",
        "stage_b_requested": "200 positive videos + 200 normal videos",
        "candidate_generation_status": "skipped because video mapping/readability gate failed",
    }
    write_json(OUT / "config/experiment_config.json", config)

    audit = {
        "runtime_seconds": elapsed,
        "manifest_rows": total,
        "video_files_found_under_videos_hf": len(files),
        "mapped_rows": mapped,
        "readable_rows": readable,
        "readable_fraction": readable_rate,
        "positive_readable_rows": pos_readable,
        "normal_readable_rows": normal_readable,
        "access_gate_passed": readable_rate >= 0.80,
        "decision": DECISION_VIDEO_FAILED if readable_rate < 0.80 else "ACCESS_GATE_PASSED",
    }
    write_json(OUT / "audits/video_access_gate.json", audit)
    append_progress(
        "video_mapping_readability_gate",
        "python scripts/nexar_candidate_feasibility.py",
        f"manifest_rows={total}, files_found={len(files)}, mapped={mapped}, readable={readable}, readable_fraction={readable_rate:.4f}",
        failure="" if readable_rate >= 0.80 else "readable fraction below required 0.80",
        next_action="stop with VIDEO_MAPPING_OR_READABILITY_FAILED" if readable_rate < 0.80 else "candidate generation",
    )
    return audit


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


def write_report(audit: dict, gpu: dict) -> None:
    readability = pd.read_csv(OUT / "tables/nexar_video_readability.csv")
    by_label = (
        readability.groupby("label", dropna=False)
        .agg(rows=("video_id", "count"), mapped=("filename_maps_to_manifest", "sum"), readable=("readable", "sum"))
        .reset_index()
    )
    by_label["readable_fraction"] = by_label["readable"] / by_label["rows"]
    smoke = pd.read_csv(OUT / "tables/nexar_candidate_subset_smoke.csv")
    full = pd.read_csv(OUT / "tables/nexar_candidate_subset_200.csv")

    report = f"""# Nexar Candidate Feasibility Report

## 1. Goal

Evaluate whether practical video-content candidate generators can produce high-recall returned clips on the Nexar derived-boundary benchmark after the Nexar videos were expected to be available.

## 2. Why this follows Phase 1.3

Phase 1.3 found candidate quality to be the main bottleneck. This run starts with the required video access gate before any candidate generation, because candidate recall and certificate results would be uninterpretable if the Nexar-200 videos cannot be mapped and read.

## 3. Video access and mapping

- Manifest rows: `{audit['manifest_rows']}`
- `.mp4` files found under `videos_hf`: `{audit['video_files_found_under_videos_hf']}`
- Mapped manifest rows: `{audit['mapped_rows']}`
- Readable manifest rows: `{audit['readable_rows']}`
- Readable fraction: `{audit['readable_fraction']:.4f}`
- Required readable fraction: `0.8000`

Readability by manifest label:

{markdown_table(by_label)}

Full mapping table: `tables/nexar_video_mapping.csv`.
Full readability table: `tables/nexar_video_readability.csv`.

## 4. Subset construction

The requested Stage A and Stage B subset tables were written, but both are marked with readability status. Candidate generation was not run because the access gate failed.

- Stage A rows requested: `{len(smoke)}`
- Stage A readable rows: `{int(smoke['readable'].sum())}`
- Stage B rows requested: `{len(full)}`
- Stage B readable rows: `{int(full['readable'].sum())}`

## 5. Frame extraction

Not run. The required `tables/nexar_frame_index.csv` schema-only file was written. Extracting frames from a partial, label-skewed subset would violate the staged evaluation gate.

## 6. Candidate generators

Not run because fewer than 80% of Nexar-200 manifest videos were readable. Schema-only candidate CSVs were written under `candidates/` with `stage_not_run_*` names to document the fail-closed state.

## 7. Leakage controls

The mapping/readability gate used filenames, basenames, relative paths, file existence, file size, ffprobe/OpenCV duration, and first-frame readability only. It did not use `event_start`, `event_end`, `event_moment`, or `alert_time` for generation, ranking, threshold tuning, or window selection. No practical candidate rows were generated, and all candidate-stage outputs remain empty.

## 8. Candidate recall vs budget

Not run. `tables/nexar_candidate_eval_results.csv` is schema-only because the video access gate failed before frame extraction or candidate generation.

## 9. Runtime / GPU usage

- GPU visible: `{gpu.get('gpu_visible')}`
- GPU used: `{gpu.get('gpu_used')}`
- GPU model: `{gpu.get('gpu_model')}`
- Runtime seconds for access audit: `{audit['runtime_seconds']:.3f}`
- Frames processed: `0`
- Videos processed for candidate generation: `0`
- Throughput fps: `not applicable`

## 10. Certificate results for promising candidates

Not run. No candidate reached the evaluation stage, so there were no promising candidates to certify. `tables/nexar_candidate_certificate_results.csv` is schema-only.

## 11. Limitations of derived boundaries

The Nexar event intervals are derived from metadata and are not human-adjudicated event boundaries. Even if videos were complete, results would be pseudo-oracle/derived-boundary evaluation, not human ground truth.

## 12. Recommendation

Repair or complete the local Nexar video mirror so that at least 80% of the 400 manifest rows are mapped and readable. The current `videos_hf` tree is heavily incomplete for this benchmark, with positive videos absent from the mapped readable set.

{DECISION_VIDEO_FAILED}
"""
    (OUT / "reports/NEXAR_CANDIDATE_FEASIBILITY_REPORT.md").write_text(report, encoding="utf-8")

    summary = f"""# Nexar Candidate Feasibility Summary

- Output directory: `{OUT}`
- Manifest rows: `{audit['manifest_rows']}`
- Videos found under `videos_hf`: `{audit['video_files_found_under_videos_hf']}`
- Readable manifest rows: `{audit['readable_rows']}` (`{audit['readable_fraction']:.4f}`)
- Candidate generation: not run because the 80% video access gate failed.
- Report: `{OUT / 'reports/NEXAR_CANDIDATE_FEASIBILITY_REPORT.md'}`

{DECISION_VIDEO_FAILED}
"""
    SUMMARY_PATH.write_text(summary, encoding="utf-8")
    append_progress(
        "report_summary",
        "python scripts/nexar_candidate_feasibility.py",
        f"wrote report and summary with decision {DECISION_VIDEO_FAILED}",
    )


def main() -> int:
    ensure_dirs()
    gpu = detect_gpu()
    write_json(OUT / "logs/gpu_usage.json", gpu)
    audit = audit_mapping_and_readability()
    write_report(audit, gpu)
    print(json.dumps({"decision": audit["decision"], "readable_fraction": audit["readable_fraction"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
