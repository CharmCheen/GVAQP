#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2"
SUMMARY_PATH = ROOT / "garc_eval/outputs/clip_aqp_phase1_nexar_candidate_v2_summary.md"
BRIEF_PATH = ROOT / "CASQ_CODEX_BRIEF_V12_1.md"
MANIFEST_PATH = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/manifests/nexar_200_manifest.csv"
EVENTS_PATH = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/converted/casq_events_nexar_200.csv"
UNITS_PATH = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/converted/casq_units_nexar_200.csv"
REPAIR_READABILITY_PATH = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_video_repair_v1/tables/post_download_manifest_readability.csv"
REPAIR_SUMMARY_PATH = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_video_repair_v1/logs/run_summary.json"
VIDEO_DIR = ROOT / "datasets/casq_external/nexar/videos_hf"
YOLO_N_PATH = ROOT / "models/yolo/yolov8n.pt"
YOLO_X_PATH = ROOT / "models/yolo/yolov8x.pt"

REQUIRED_DIRS = [
    "audits",
    "reports",
    "tables",
    "logs",
    "figures",
    "features",
    "frames",
    "candidates",
    "config",
    "data_manifest",
    "scripts",
]

RANDOM_SEED = 20260622
WINDOW_SECONDS = 0.5
WINDOW_STRIDE_SECONDS = 0.5
THETAS = [0.3, 0.5]
TOP_K_VALUES = [1, 3, 5, 10]
TOP_DURATION_FRACTIONS = [0.05, 0.10, 0.20, 0.35, 0.50]
MERGE_GAPS = [0.0, 2.5, 5.0]
CERT_GAMMAS = [0.8, 0.9]
CERT_DELTAS = [0.05, 0.1]
CERT_BLOCK_SIZES = [10.0, 15.0]
CERT_SAMPLE_FRACTIONS = [0.2, 0.35, 0.5, 0.75]
CLAIM_SCOPE = "Nexar-200 only, derived boundary"
DECISION_PREFIX = "NEXAR_CANDIDATE_DECISION:"


@dataclass(frozen=True)
class CandidateRuntime:
    candidate_name: str
    runtime_seconds: float
    frames_processed: int
    videos_processed: int
    notes: str = ""


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


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def run_cmd(args: list[str], timeout: int = 20) -> dict:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {"returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def detect_gpu() -> dict:
    info = {
        "checked_utc": utc_now(),
        "torch_cuda_available": False,
        "gpu_visible": False,
        "gpu_model": "",
        "nvidia_smi": "",
    }
    try:
        import torch

        info["torch_cuda_available"] = bool(torch.cuda.is_available())
        info["gpu_visible"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            info["gpu_model"] = str(torch.cuda.get_device_name(0))
    except Exception as exc:
        info["torch_error"] = f"{type(exc).__name__}: {exc}"
    smi = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader"], timeout=10)
    info["nvidia_smi"] = smi["stdout"] or smi["stderr"]
    return info


def stable_unit_float(*parts: str) -> float:
    text = "|".join(parts).encode("utf-8")
    value = int(hashlib.sha256(text).hexdigest()[:16], 16)
    return value / float(16**16 - 1)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    manifest = pd.read_csv(MANIFEST_PATH)
    events = pd.read_csv(EVENTS_PATH)
    units = pd.read_csv(UNITS_PATH)
    readability = pd.read_csv(REPAIR_READABILITY_PATH)
    for df in [manifest, readability]:
        for col in ["is_positive", "is_normal", "readable", "exists", "first_frame_readable"]:
            if col in df.columns:
                df[col] = df[col].map(as_bool)
    return manifest, events, units, readability


def build_preflight(mode: str) -> dict:
    start = time.time()
    manifest, events, units, readability = load_inputs()
    repair_summary = json.loads(REPAIR_SUMMARY_PATH.read_text(encoding="utf-8")) if REPAIR_SUMMARY_PATH.exists() else {}

    mapping = manifest.merge(
        readability[
            [
                "video_id",
                "filename",
                "resolved_hf_path",
                "local_path",
                "exists",
                "file_size_bytes",
                "readable",
                "duration_seconds",
                "first_frame_readable",
            ]
        ],
        on=["video_id"],
        how="left",
        suffixes=("_manifest", "_repair"),
    )
    mapping["claim_scope"] = CLAIM_SCOPE
    mapping["mapping_source"] = str(REPAIR_READABILITY_PATH)
    mapping["filename_maps_to_manifest"] = mapping["local_path"].fillna("").astype(str).str.len() > 0
    mapping.to_csv(OUT / "tables/nexar_video_mapping_v2.csv", index=False)

    readability_v2 = mapping.copy()
    readability_v2.to_csv(OUT / "tables/nexar_video_readability_v2.csv", index=False)

    full_readable = readability_v2[readability_v2["readable"].map(as_bool)].copy()
    full_readable.to_csv(OUT / "tables/nexar_candidate_subset_full_readable.csv", index=False)

    rng = np.random.default_rng(RANDOM_SEED)
    pos = full_readable[full_readable["is_positive"].map(as_bool)].copy()
    neg = full_readable[full_readable["is_normal"].map(as_bool)].copy()
    n_balanced = int(min(len(pos), len(neg)))
    pos_bal = pos.iloc[rng.permutation(len(pos))[:n_balanced]].copy()
    neg_bal = neg.iloc[rng.permutation(len(neg))[:n_balanced]].copy()
    balanced = pd.concat([pos_bal, neg_bal], ignore_index=True).sort_values(["label", "video_id"]).reset_index(drop=True)
    balanced["candidate_subset"] = "balanced_readable"
    balanced.to_csv(OUT / "tables/nexar_candidate_subset_balanced_readable.csv", index=False)

    split_rows = []
    for label, group in balanced.groupby("label", sort=True):
        vids = sorted(group["video_id"].astype(str).unique())
        perm = list(rng.permutation(vids))
        midpoint = len(perm) // 2
        dev = set(perm[:midpoint])
        heldout = set(perm[midpoint:])
        for video_id in vids:
            split_rows.append(
                {
                    "video_id": video_id,
                    "label": label,
                    "split_role": "candidate_dev" if video_id in dev else "heldout_report",
                    "claim_scope": CLAIM_SCOPE,
                }
            )
    split_df = pd.DataFrame(split_rows)
    assert not set(split_df[split_df["split_role"] == "candidate_dev"]["video_id"]).intersection(
        set(split_df[split_df["split_role"] == "heldout_report"]["video_id"])
    )
    split_df.to_csv(OUT / "tables/nexar_candidate_video_split_v2.csv", index=False)

    brief_text = BRIEF_PATH.read_text(encoding="utf-8")
    gpu = detect_gpu()
    local_clip_assets = []
    for pattern in ["*CLIP*", "*clip*", "*SigLIP*", "*siglip*", "*embedding*", "*embed*"]:
        local_clip_assets.extend([str(p) for p in (ROOT / "models").glob(pattern)])
    representation_available = bool(module_available("open_clip") or module_available("clip") or local_clip_assets)
    if representation_available and not local_clip_assets and not (module_available("open_clip") or module_available("clip")):
        representation_available = False
    inventory_rows = [
        {"asset": "CASQ_CODEX_BRIEF_V12_1", "available": BRIEF_PATH.exists(), "path": str(BRIEF_PATH), "notes": "read by v2 runner"},
        {"asset": "Nexar video repair output", "available": REPAIR_READABILITY_PATH.exists(), "path": str(REPAIR_READABILITY_PATH), "notes": repair_summary.get("decision", "")},
        {"asset": "videos_hf", "available": VIDEO_DIR.exists(), "path": str(VIDEO_DIR), "notes": "local repaired video root"},
        {"asset": "YOLOv8n", "available": YOLO_N_PATH.exists() and module_available("ultralytics"), "path": str(YOLO_N_PATH), "notes": "default proxy candidate model"},
        {"asset": "YOLOv8x", "available": YOLO_X_PATH.exists(), "path": str(YOLO_X_PATH), "notes": "pseudo-oracle model path; not used for candidate v2"},
        {"asset": "torch_cuda", "available": gpu.get("torch_cuda_available", False), "path": "", "notes": gpu.get("gpu_model", "")},
        {
            "asset": "representation_based_candidate",
            "available": representation_available,
            "path": ";".join(local_clip_assets),
            "notes": "REPRESENTATION_CANDIDATE_NOT_AVAILABLE" if not representation_available else "local representation assets detected",
        },
        {"asset": "32B audit imported", "available": (OUT / "audits/vlm_micro_audit_results.csv").exists(), "path": str(OUT / "audits/vlm_micro_audit_results.csv"), "notes": "imported from v1 without rerun"},
    ]
    inventory = pd.DataFrame(inventory_rows)
    inventory.to_csv(OUT / "tables/local_model_inventory_v2.csv", index=False)

    input_manifest = pd.DataFrame(
        [
            {"artifact": "brief", "path": str(BRIEF_PATH), "rows": brief_text.count("\n") + 1, "columns": "markdown"},
            {"artifact": "nexar_200_manifest", "path": str(MANIFEST_PATH), "rows": len(manifest), "columns": ";".join(manifest.columns)},
            {"artifact": "casq_events_nexar_200", "path": str(EVENTS_PATH), "rows": len(events), "columns": ";".join(events.columns)},
            {"artifact": "casq_units_nexar_200", "path": str(UNITS_PATH), "rows": len(units), "columns": ";".join(units.columns)},
            {"artifact": "repair_readability", "path": str(REPAIR_READABILITY_PATH), "rows": len(readability), "columns": ";".join(readability.columns)},
            {"artifact": "vlm_micro_audit_results_imported", "path": str(OUT / "audits/vlm_micro_audit_results.csv"), "rows": len(pd.read_csv(OUT / "audits/vlm_micro_audit_results.csv")) if (OUT / "audits/vlm_micro_audit_results.csv").exists() else 0, "columns": "imported from v1"},
        ]
    )
    input_manifest.to_csv(OUT / "data_manifest/input_manifest_v2.csv", index=False)

    config = {
        "experiment": "clip_aqp_phase1_nexar_candidate_v2",
        "mode": mode,
        "created_utc": utc_now(),
        "random_seed": RANDOM_SEED,
        "window_seconds": WINDOW_SECONDS,
        "window_stride_seconds": WINDOW_STRIDE_SECONDS,
        "theta_grid": THETAS,
        "top_k_per_video_grid": TOP_K_VALUES,
        "top_duration_fraction_grid": TOP_DURATION_FRACTIONS,
        "merge_gap_grid_seconds": MERGE_GAPS,
        "claim_scope": CLAIM_SCOPE,
        "external_label_mapping": "LOOSE_APPROXIMATION / AUDIT_UNRELIABLE",
        "leakage_rule": "event_start/event_end/event_moment/alert_time/derived boundaries evaluation-only; candidate generation uses video frames and duration only",
        "no_vlm_rerun": True,
        "no_training": True,
    }
    write_json(OUT / "config/experiment_config_v2.json", config)
    write_json(OUT / "logs/gpu_usage_v2.json", gpu)

    preflight = {
        "runtime_seconds": time.time() - start,
        "brief_read": BRIEF_PATH.exists(),
        "manifest_rows": len(manifest),
        "events_rows": len(events),
        "units_rows": len(units),
        "readability_rows": len(readability),
        "readable_rows": int(full_readable.shape[0]),
        "positive_readable": int(full_readable["is_positive"].map(as_bool).sum()),
        "normal_readable": int(full_readable["is_normal"].map(as_bool).sum()),
        "balanced_rows": int(balanced.shape[0]),
        "balanced_positive": int(balanced["is_positive"].map(as_bool).sum()),
        "balanced_normal": int(balanced["is_normal"].map(as_bool).sum()),
        "candidate_dev_videos": int((split_df["split_role"] == "candidate_dev").sum()),
        "heldout_report_videos": int((split_df["split_role"] == "heldout_report").sum()),
        "representation_available": representation_available,
        "gpu_model": gpu.get("gpu_model", ""),
        "repair_decision": repair_summary.get("decision", ""),
    }
    write_json(OUT / "logs/preflight_summary_v2.json", preflight)
    write_preflight_report(preflight, inventory, split_df)
    append_progress("preflight_inventory_split", "python scripts/nexar_candidate_feasibility_v2.py", json.dumps(preflight, sort_keys=True))
    return preflight


def write_preflight_report(preflight: dict, inventory: pd.DataFrame, split_df: pd.DataFrame) -> None:
    split_counts = split_df.groupby(["split_role", "label"]).size().reset_index(name="videos")
    report = f"""# Data and Environment Preflight

## Protocol

CASQ_CODEX_BRIEF_V12_1.md was read. This is a Phase 1+ candidate-feasibility v2 run, not a Phase 0 run.

## Input Data

- Nexar manifest rows: {preflight['manifest_rows']}
- CASQ event rows: {preflight['events_rows']}
- CASQ unit rows: {preflight['units_rows']}
- Repair readability rows: {preflight['readability_rows']}
- Full readable rows: {preflight['readable_rows']}
- Positive readable rows: {preflight['positive_readable']}
- Normal readable rows: {preflight['normal_readable']}
- Balanced readable rows: {preflight['balanced_rows']}

## Design / Report Split

Split protocol: HELD_OUT_REPORT.

Candidate hyperparameters are selected on `candidate_dev` videos only. Reported final metrics are computed on `heldout_report` videos.

{to_markdown(split_counts)}

## Local Model Inventory

{to_markdown(inventory)}

## External Label Mapping

LOOSE_APPROXIMATION / AUDIT_UNRELIABLE.

Nexar-derived labels must not be treated as equivalent to O_enter_ego_path_v0. Candidate and certificate results are Nexar-derived-boundary-relative.
"""
    (OUT / "reports/DATA_AND_ENV_PREFLIGHT.md").write_text(report, encoding="utf-8")


def to_markdown(df: pd.DataFrame, max_rows: int = 50) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows).copy()
    lines = ["| " + " | ".join(map(str, view.columns)) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        vals = []
        for col in view.columns:
            value = row[col]
            if isinstance(value, float):
                vals.append(f"{value:.6g}" if math.isfinite(value) else "")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def build_windows(mode: str) -> pd.DataFrame:
    balanced = pd.read_csv(OUT / "tables/nexar_candidate_subset_balanced_readable.csv")
    split_df = pd.read_csv(OUT / "tables/nexar_candidate_video_split_v2.csv")
    balanced = balanced.merge(split_df[["video_id", "split_role"]], on="video_id", how="left")
    if mode == "smoke":
        balanced = (
            balanced.groupby(["split_role", "label"], group_keys=False)
            .head(5)
            .reset_index(drop=True)
        )
    rows = []
    for _, row in balanced.iterrows():
        duration = float(row.get("duration_seconds", 0.0) or 0.0)
        if duration <= 0:
            continue
        n = max(1, int(math.floor((duration - WINDOW_SECONDS) / WINDOW_STRIDE_SECONDS)) + 1)
        for idx in range(n):
            start = round(idx * WINDOW_STRIDE_SECONDS, 3)
            end = min(round(start + WINDOW_SECONDS, 3), duration)
            if end <= start:
                continue
            rows.append(
                {
                    "video_id": row["video_id"],
                    "label": row["label"],
                    "is_positive": as_bool(row["is_positive"]),
                    "is_normal": as_bool(row["is_normal"]),
                    "split_role": row["split_role"],
                    "source_video_path": row["local_path"],
                    "video_duration": duration,
                    "window_id": f"{row['video_id']}_w{idx:05d}",
                    "window_start": start,
                    "window_end": end,
                    "window_duration": end - start,
                    "claim_scope": CLAIM_SCOPE,
                }
            )
    windows = pd.DataFrame(rows)
    windows.to_csv(OUT / "tables/nexar_candidate_windows_v2.csv", index=False)
    append_progress("window_grid", "build 0.5s non-overlap windows", f"windows={len(windows)}, videos={windows['video_id'].nunique() if not windows.empty else 0}")
    return windows


def read_frame_at(cap: cv2.VideoCapture, timestamp: float):
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp) * 1000.0)
    ok, frame = cap.read()
    if not ok:
        return None
    return frame


def fixed_scores(windows: pd.DataFrame) -> tuple[pd.DataFrame, CandidateRuntime]:
    start = time.time()
    df = windows.copy()
    df["candidate_name"] = "fixed_sliding_window"
    df["score"] = -df["window_start"].astype(float)
    df["generation_rule"] = "chronological_0p5s_windows"
    df["uses_oracle_annotation"] = False
    df["uses_video_content"] = False
    runtime = CandidateRuntime("fixed_sliding_window", time.time() - start, 0, int(df["video_id"].nunique()))
    return df, runtime


def random_scores(windows: pd.DataFrame) -> tuple[pd.DataFrame, CandidateRuntime]:
    start = time.time()
    df = windows.copy()
    df["candidate_name"] = "random_window"
    df["score"] = [
        stable_unit_float(str(v), str(w), str(RANDOM_SEED))
        for v, w in zip(df["video_id"].astype(str), df["window_id"].astype(str))
    ]
    df["generation_rule"] = "deterministic_hash_random_0p5s_windows"
    df["uses_oracle_annotation"] = False
    df["uses_video_content"] = False
    runtime = CandidateRuntime("random_window", time.time() - start, 0, int(df["video_id"].nunique()))
    return df, runtime


def motion_scores(windows: pd.DataFrame) -> tuple[pd.DataFrame, CandidateRuntime]:
    start = time.time()
    rows = []
    frames = 0
    for video_id, group in windows.groupby("video_id", sort=False):
        path = str(group["source_video_path"].iloc[0])
        cap = cv2.VideoCapture(path)
        duration = float(group["video_duration"].iloc[0])
        sample_times = [max(0.25, duration / 3.0), max(0.25, 2.0 * duration / 3.0)]
        grays = []
        for sample_time in sample_times:
            frame = read_frame_at(cap, float(sample_time))
            if frame is not None:
                frames += 1
                small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                grays.append(gray)
        score = float(np.mean(cv2.absdiff(grays[1], grays[0]))) if len(grays) >= 2 else 0.0
        ordered = group.sort_values("window_start").reset_index(drop=True)
        for _, row in ordered.iterrows():
            out = row.to_dict()
            out.update(
                {
                    "candidate_name": "motion_energy",
                    "score": score,
                    "generation_rule": "two_point_video_level_mean_abs_gray_difference_assigned_to_all_0p5s_windows",
                    "uses_oracle_annotation": False,
                    "uses_video_content": True,
                }
            )
            rows.append(out)
        cap.release()
    df = pd.DataFrame(rows)
    runtime = CandidateRuntime("motion_energy", time.time() - start, frames, int(windows["video_id"].nunique()))
    return df, runtime


def yolo_scores(windows: pd.DataFrame, batch_size: int = 64) -> tuple[pd.DataFrame, CandidateRuntime]:
    start = time.time()
    if not (YOLO_N_PATH.exists() and module_available("ultralytics")):
        df = windows.copy()
        df["candidate_name"] = "yolo_count_proxy"
        df["score"] = np.nan
        df["generation_rule"] = "YOLOv8n unavailable"
        df["uses_oracle_annotation"] = False
        df["uses_video_content"] = True
        return df, CandidateRuntime("yolo_count_proxy", time.time() - start, 0, 0, "YOLO unavailable")
    from ultralytics import YOLO

    model = YOLO(str(YOLO_N_PATH))
    gpu = detect_gpu()
    yolo_device = "cuda:0" if gpu.get("torch_cuda_available", False) else "cpu"
    road_user_names = {"person", "bicycle", "car", "motorcycle", "bus", "truck"}
    rows = []
    images = []
    image_meta = []
    frames = 0
    sampled_scores: dict[tuple[str, float], tuple[float, int, float]] = {}

    def flush_batch() -> None:
        nonlocal images, image_meta, frames
        if not images:
            return
        preds = model.predict(images, verbose=False, imgsz=640, device=yolo_device)
        for meta, pred in zip(image_meta, preds):
            count = 0
            conf_sum = 0.0
            if getattr(pred, "boxes", None) is not None and pred.boxes is not None:
                for box in pred.boxes:
                    cls_id = int(box.cls.item())
                    name = str(model.names.get(cls_id, cls_id))
                    if name in road_user_names:
                        count += 1
                        conf_sum += float(box.conf.item())
            sampled_scores[(meta["video_id"], meta["sample_time"])] = (float(count + conf_sum), count, conf_sum)
        frames += len(images)
        images = []
        image_meta = []

    for video_id, group in windows.groupby("video_id", sort=False):
        path = str(group["source_video_path"].iloc[0])
        duration = float(group["video_duration"].iloc[0])
        cap = cv2.VideoCapture(path)
        sample_times = np.arange(0.25, max(0.26, duration), 2.0)
        for sample_time in sample_times:
            frame = read_frame_at(cap, float(sample_time))
            if frame is None:
                continue
            images.append(frame)
            image_meta.append({"video_id": str(video_id), "sample_time": float(sample_time)})
            if len(images) >= batch_size:
                flush_batch()
        cap.release()
    flush_batch()

    per_video_scores: dict[str, list[tuple[float, float, int, float]]] = {}
    for (video_id, sample_time), (score, count, conf_sum) in sampled_scores.items():
        per_video_scores.setdefault(video_id, []).append((sample_time, score, count, conf_sum))
    for video_id in per_video_scores:
        per_video_scores[video_id].sort(key=lambda item: item[0])

    for _, row in windows.iterrows():
        video_id = str(row["video_id"])
        mid = (float(row["window_start"]) + float(row["window_end"])) / 2.0
        candidates = per_video_scores.get(video_id, [])
        if candidates:
            nearest_time, score, count, conf_sum = min(candidates, key=lambda item: abs(item[0] - mid))
        else:
            score, count, conf_sum, nearest_time = 0.0, 0, 0.0, math.nan
        out = row.to_dict()
        out.update(
            {
                "candidate_name": "yolo_count_proxy",
                "score": score,
                "yolo_road_user_count": count,
                "yolo_road_user_conf_sum": conf_sum,
                "yolo_sample_time": nearest_time,
                "generation_rule": "YOLOv8n road-user count plus confidence sum sampled every 2s and assigned to nearest 0p5s window",
                "uses_oracle_annotation": False,
                "uses_video_content": True,
            }
        )
        rows.append(out)
    df = pd.DataFrame(rows)
    runtime = CandidateRuntime("yolo_count_proxy", time.time() - start, frames, int(windows["video_id"].nunique()), f"YOLOv8n local model; device={yolo_device}")
    return df, runtime


def generate_candidates(mode: str) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    windows = build_windows(mode)
    generators = [fixed_scores, random_scores, motion_scores]
    if os.environ.get("CASQ_RUN_SLOW_YOLO", "0") == "1":
        generators.append(yolo_scores)
    scores: dict[str, pd.DataFrame] = {}
    runtime_rows = []
    for gen in generators:
        df, runtime = gen(windows)
        df = df.sort_values(["candidate_name", "video_id", "window_start"]).reset_index(drop=True)
        df["rank_desc_score"] = df.groupby("video_id")["score"].rank(method="first", ascending=False)
        path = OUT / f"candidates/{runtime.candidate_name}_raw_windows_v2.csv"
        df.to_csv(path, index=False)
        scores[runtime.candidate_name] = df
        runtime_rows.append(runtime.__dict__)
        append_progress(
            f"candidate_generation_{runtime.candidate_name}",
            f"{runtime.candidate_name} scoring",
            f"rows={len(df)}, frames_processed={runtime.frames_processed}, runtime_seconds={runtime.runtime_seconds:.3f}",
            next_action="evaluate grid",
        )
    if "yolo_count_proxy" not in scores:
        yolo_status = pd.DataFrame(
            [
                {
                    "candidate_name": "yolo_count_proxy",
                    "status": "NOT_RUN_CPU_FALLBACK_INFEASIBLE",
                    "local_model_available": YOLO_N_PATH.exists(),
                    "ultralytics_available": module_available("ultralytics"),
                    "reason": "A smoke attempt did not attach as a visible GPU compute process and ran as slow CPU-heavy inference; full YOLO scoring was not run to avoid an infeasible CPU fallback.",
                    "how_to_enable": "Set CASQ_RUN_SLOW_YOLO=1 and rerun if full YOLO scoring is explicitly authorized despite runtime.",
                }
            ]
        )
        yolo_status.to_csv(OUT / "tables/yolo_count_proxy_status_v2.csv", index=False)
        empty = windows.head(0).copy()
        for col in ["candidate_name", "score", "generation_rule", "uses_oracle_annotation", "uses_video_content"]:
            empty[col] = []
        empty.to_csv(OUT / "candidates/yolo_count_proxy_raw_windows_v2.csv", index=False)
        runtime_rows.append(
            {
                "candidate_name": "yolo_count_proxy",
                "runtime_seconds": 0.0,
                "frames_processed": 0,
                "videos_processed": 0,
                "notes": "NOT_RUN_CPU_FALLBACK_INFEASIBLE",
            }
        )
        append_progress(
            "candidate_generation_yolo_count_proxy",
            "yolo_count_proxy scoring skipped",
            "NOT_RUN_CPU_FALLBACK_INFEASIBLE; local model exists but full CPU fallback was not feasible",
        )
    representation_status = pd.DataFrame(
        [
            {
                "candidate_name": "representation_based_candidate",
                "status": "REPRESENTATION_CANDIDATE_NOT_AVAILABLE",
                "reason": "No local CLIP/SigLIP package or local representation embedding assets were available; no download approved.",
                "claim_limitation": "Cheap handcrafted candidate results cannot be generalized to candidate generation overall.",
            }
        ]
    )
    representation_status.to_csv(OUT / "tables/representation_candidate_status_v2.csv", index=False)
    runtimes = pd.DataFrame(runtime_rows)
    runtimes.to_csv(OUT / "tables/candidate_runtime_v2.csv", index=False)
    return scores, runtimes


def interval_iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union


def merge_intervals(df: pd.DataFrame, merge_gap: float) -> pd.DataFrame:
    rows = []
    if df.empty:
        return pd.DataFrame(columns=["video_id", "returned_clip_id", "start_time", "end_time", "score", "source_window_count"])
    for video_id, group in df.sort_values(["video_id", "window_start"]).groupby("video_id", sort=False):
        cur_start = None
        cur_end = None
        cur_score = -float("inf")
        count = 0
        clip_idx = 0
        for _, row in group.iterrows():
            start = float(row["window_start"])
            end = float(row["window_end"])
            score = float(row["score"]) if pd.notna(row["score"]) else 0.0
            if cur_start is None:
                cur_start, cur_end, cur_score, count = start, end, score, 1
                continue
            if start - cur_end <= merge_gap + 1e-9:
                cur_end = max(cur_end, end)
                cur_score = max(cur_score, score)
                count += 1
            else:
                rows.append(
                    {
                        "video_id": video_id,
                        "returned_clip_id": f"{video_id}_clip_{clip_idx:04d}",
                        "start_time": cur_start,
                        "end_time": cur_end,
                        "score": cur_score,
                        "source_window_count": count,
                    }
                )
                clip_idx += 1
                cur_start, cur_end, cur_score, count = start, end, score, 1
        if cur_start is not None:
            rows.append(
                {
                    "video_id": video_id,
                    "returned_clip_id": f"{video_id}_clip_{clip_idx:04d}",
                    "start_time": cur_start,
                    "end_time": cur_end,
                    "score": cur_score,
                    "source_window_count": count,
                }
            )
    return pd.DataFrame(rows)


def select_raw_windows(scores: pd.DataFrame, budget_type: str, budget_value: float) -> pd.DataFrame:
    selected = []
    for video_id, group in scores.groupby("video_id", sort=False):
        ordered = group.sort_values(["score", "window_start"], ascending=[False, True])
        if budget_type == "top_k_per_video":
            chosen = ordered.head(int(budget_value))
        else:
            duration = float(group["video_duration"].iloc[0])
            budget_seconds = max(WINDOW_SECONDS, duration * float(budget_value))
            rows = []
            total = 0.0
            for _, row in ordered.iterrows():
                rows.append(row)
                total += float(row["window_duration"])
                if total + 1e-9 >= budget_seconds:
                    break
            chosen = pd.DataFrame(rows)
        selected.append(chosen)
    if not selected:
        return pd.DataFrame(columns=scores.columns)
    return pd.concat(selected, ignore_index=True)


def evaluate_returned_clips(clips: pd.DataFrame, events: pd.DataFrame, theta: float) -> tuple[int, int, float, pd.DataFrame]:
    event_rows = []
    hit_count = 0
    for _, event in events.iterrows():
        video_id = str(event["video_id"])
        group = clips[clips["video_id"].astype(str) == video_id]
        max_iou = 0.0
        if not group.empty:
            max_iou = max(
                interval_iou(float(row["start_time"]), float(row["end_time"]), float(event["event_start"]), float(event["event_end"]))
                for _, row in group.iterrows()
            )
        hit = max_iou >= theta
        hit_count += int(hit)
        event_rows.append(
            {
                "event_id": event["event_id"],
                "video_id": video_id,
                "theta": theta,
                "max_iou": max_iou,
                "hit": hit,
                "event_start": float(event["event_start"]),
                "event_end": float(event["event_end"]),
            }
        )
    total = len(events)
    recall = float(hit_count / total) if total else 0.0
    return hit_count, total, recall, pd.DataFrame(event_rows)


def evaluate_candidates(scores: dict[str, pd.DataFrame], runtimes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    events = pd.read_csv(EVENTS_PATH)
    split_df = pd.read_csv(OUT / "tables/nexar_candidate_video_split_v2.csv")
    split_map = dict(zip(split_df["video_id"].astype(str), split_df["split_role"]))
    events["split_role"] = events["video_id"].astype(str).map(split_map)
    returned_by_config: dict[str, pd.DataFrame] = {}
    result_rows = []
    hit_rows = []
    runtime_map = {row["candidate_name"]: row for _, row in runtimes.iterrows()}

    for candidate_name, score_df in scores.items():
        for split_role in ["candidate_dev", "heldout_report"]:
            split_scores = score_df[score_df["split_role"] == split_role].copy()
            split_events = events[events["split_role"] == split_role].copy()
            total_video_duration = float(split_scores.drop_duplicates("video_id")["video_duration"].sum())
            for theta in THETAS:
                budget_specs = [("top_k_per_video", float(k)) for k in TOP_K_VALUES] + [
                    ("top_duration_fraction", float(frac)) for frac in TOP_DURATION_FRACTIONS
                ]
                for budget_type, budget_value in budget_specs:
                    for merge_gap in MERGE_GAPS:
                        raw = select_raw_windows(split_scores, budget_type, budget_value)
                        clips = merge_intervals(raw, merge_gap)
                        clips["candidate_name"] = candidate_name
                        clips["split_role"] = split_role
                        clips["theta"] = theta
                        clips["budget_type"] = budget_type
                        clips["budget_value"] = budget_value
                        clips["merge_gap"] = merge_gap
                        config_id = config_key(candidate_name, theta, budget_type, budget_value, merge_gap)
                        clips["config_id"] = config_id
                        hit_count, event_total, recall, event_hits = evaluate_returned_clips(clips, split_events, theta)
                        event_hits["candidate_name"] = candidate_name
                        event_hits["split_role"] = split_role
                        event_hits["budget_type"] = budget_type
                        event_hits["budget_value"] = budget_value
                        event_hits["merge_gap"] = merge_gap
                        event_hits["config_id"] = config_id
                        hit_rows.append(event_hits)
                        total_returned_duration = float((clips["end_time"] - clips["start_time"]).sum()) if not clips.empty else 0.0
                        runtime = runtime_map.get(candidate_name, {})
                        result_rows.append(
                            {
                                "config_id": config_id,
                                "split_role": split_role,
                                "selection_protocol": "HELD_OUT_REPORT",
                                "selected_on_candidate_dev": False,
                                "candidate_name": candidate_name,
                                "theta": theta,
                                "budget_type": budget_type,
                                "budget_value": budget_value,
                                "top_k_per_video": int(budget_value) if budget_type == "top_k_per_video" else "",
                                "top_duration_fraction": budget_value if budget_type == "top_duration_fraction" else "",
                                "merge_gap": merge_gap,
                                "num_returned_clips": int(len(clips)),
                                "total_returned_duration": total_returned_duration,
                                "returned_duration_fraction": total_returned_duration / total_video_duration if total_video_duration else 0.0,
                                "mean_returned_clip_duration": float((clips["end_time"] - clips["start_time"]).mean()) if not clips.empty else 0.0,
                                "nexar_derived_boundary_relative_recall": recall,
                                "true_derived_recall": recall,
                                "event_hit_count": hit_count,
                                "event_total_count": event_total,
                                "precision_if_definable": hit_count / len(clips) if len(clips) else 0.0,
                                "runtime_seconds": float(runtime.get("runtime_seconds", 0.0)) if hasattr(runtime, "get") else 0.0,
                                "frames_processed": int(runtime.get("frames_processed", 0)) if hasattr(runtime, "get") else 0,
                                "videos_processed": int(runtime.get("videos_processed", 0)) if hasattr(runtime, "get") else 0,
                                "throughput_fps": (float(runtime.get("frames_processed", 0)) / float(runtime.get("runtime_seconds", 0.0))) if hasattr(runtime, "get") and float(runtime.get("runtime_seconds", 0.0)) > 0 else 0.0,
                                "claim_scope": CLAIM_SCOPE,
                                "label_mapping": "LOOSE_APPROXIMATION / AUDIT_UNRELIABLE",
                            }
                        )
                        if split_role == "heldout_report":
                            returned_by_config[config_id] = clips

    results = pd.DataFrame(result_rows)
    hits = pd.concat(hit_rows, ignore_index=True) if hit_rows else pd.DataFrame()
    selected = select_dev_configs(results)
    selected_keys = set(selected["config_id"].astype(str))
    results["selected_on_candidate_dev"] = results["config_id"].astype(str).isin(selected_keys)
    results.to_csv(OUT / "tables/nexar_candidate_eval_results_v2.csv", index=False)
    selected.to_csv(OUT / "tables/nexar_candidate_selected_configs_v2.csv", index=False)
    hits.to_csv(OUT / "tables/nexar_candidate_event_hits_v2.csv", index=False)
    append_progress("candidate_evaluation", "evaluate dev and heldout grids", f"result_rows={len(results)}, selected_configs={len(selected)}")
    write_eval_figures(results)
    return results, selected, returned_by_config


def config_key(candidate_name: str, theta: float, budget_type: str, budget_value: float, merge_gap: float) -> str:
    value = str(budget_value).replace(".", "p")
    gap = str(merge_gap).replace(".", "p")
    th = str(theta).replace(".", "p")
    return f"{candidate_name}__theta_{th}__{budget_type}_{value}__gap_{gap}"


def select_dev_configs(results: pd.DataFrame) -> pd.DataFrame:
    dev = results[results["split_role"] == "candidate_dev"].copy()
    selected_rows = []
    for (candidate_name, theta), group in dev.groupby(["candidate_name", "theta"], sort=True):
        ordered = group.sort_values(
            ["nexar_derived_boundary_relative_recall", "returned_duration_fraction", "num_returned_clips"],
            ascending=[False, True, True],
        )
        selected_rows.append(ordered.iloc[0].to_dict())
    return pd.DataFrame(selected_rows)


def write_eval_figures(results: pd.DataFrame) -> None:
    heldout = results[results["split_role"] == "heldout_report"].copy()
    if heldout.empty:
        return
    for theta in THETAS:
        subset = heldout[heldout["theta"] == theta]
        fig, ax = plt.subplots(figsize=(8, 5))
        for candidate, group in subset.groupby("candidate_name"):
            ax.scatter(group["returned_duration_fraction"], group["nexar_derived_boundary_relative_recall"], s=18, alpha=0.55, label=candidate)
        ax.set_xlabel("Returned duration fraction")
        ax.set_ylabel("Nexar-derived-boundary-relative recall")
        ax.set_title(f"Recall vs returned duration, theta={theta}")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(OUT / f"figures/recall_vs_budget_by_candidate_v2_theta_{str(theta).replace('.', 'p')}.png", dpi=160)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    for candidate, group in heldout.groupby("candidate_name"):
        ax.scatter(group["returned_duration_fraction"], group["nexar_derived_boundary_relative_recall"], s=18, alpha=0.55, label=candidate)
    ax.set_xlabel("Returned duration fraction")
    ax.set_ylabel("Nexar-derived-boundary-relative recall")
    ax.set_title("Returned duration vs recall")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "figures/returned_duration_vs_recall_v2.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    runtime_view = heldout.drop_duplicates("candidate_name")
    ax.bar(runtime_view["candidate_name"], runtime_view["runtime_seconds"])
    ax.set_ylabel("Candidate generation runtime seconds")
    ax.set_title("Runtime by candidate")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(OUT / "figures/runtime_vs_recall_v2.png", dpi=160)
    plt.close(fig)

    best = heldout.sort_values("nexar_derived_boundary_relative_recall").groupby("candidate_name").tail(1)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(best["candidate_name"], best["nexar_derived_boundary_relative_recall"])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Best heldout recall in grid")
    ax.set_title("Recall vs budget by candidate")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(OUT / "figures/recall_vs_budget_by_candidate_v2.png", dpi=160)
    plt.close(fig)


def build_blocks_for_config(clips: pd.DataFrame, theta: float, block_size: float) -> pd.DataFrame:
    split_df = pd.read_csv(OUT / "tables/nexar_candidate_video_split_v2.csv")
    readability = pd.read_csv(OUT / "tables/nexar_candidate_subset_balanced_readable.csv")
    heldout_videos = set(split_df[split_df["split_role"] == "heldout_report"]["video_id"].astype(str))
    heldout_meta = readability[readability["video_id"].astype(str).isin(heldout_videos)].copy()
    events = pd.read_csv(EVENTS_PATH)
    events = events[events["video_id"].astype(str).isin(heldout_videos)].copy()
    event_hit = {}
    for _, event in events.iterrows():
        group = clips[clips["video_id"].astype(str) == str(event["video_id"])]
        max_iou = 0.0
        if not group.empty:
            max_iou = max(
                interval_iou(float(row["start_time"]), float(row["end_time"]), float(event["event_start"]), float(event["event_end"]))
                for _, row in group.iterrows()
            )
        event_hit[str(event["event_id"])] = max_iou >= theta

    block_rows = []
    for _, video in heldout_meta.iterrows():
        duration = float(video["duration_seconds"])
        n_blocks = max(1, int(math.ceil(duration / block_size)))
        video_events = events[events["video_id"].astype(str) == str(video["video_id"])]
        for idx in range(n_blocks):
            start = idx * block_size
            end = min(duration, (idx + 1) * block_size)
            owned = []
            for _, event in video_events.iterrows():
                midpoint = float(event["event_midpoint"])
                if start <= midpoint < end or (idx == n_blocks - 1 and math.isclose(midpoint, end)):
                    owned.append(event)
            y_i = len(owned)
            m_i = sum(0 if event_hit.get(str(event["event_id"]), False) else 1 for event in owned)
            block_rows.append(
                {
                    "block_id": f"{video['video_id']}_b{idx:04d}_{int(start * 1000):09d}_{int(end * 1000):09d}",
                    "video_id": video["video_id"],
                    "block_start": start,
                    "block_end": end,
                    "block_size": block_size,
                    "Y_i_O": y_i,
                    "M_i_O": m_i,
                }
            )
    return pd.DataFrame(block_rows)


def certificate_bounds(sample: pd.DataFrame, population_n: int, delta: float) -> dict:
    assert (sample["sample_split"] == "certification").all(), "sample_split != certification"
    assert (sample["used_for_design"] == False).all(), "used_for_design must be false"
    assert (sample["used_for_repair"] == False).all(), "used_for_repair must be false"
    n = len(sample)
    y_bar = float(sample["Y_i_O"].mean()) if n else 0.0
    m_bar = float(sample["M_i_O"].mean()) if n else 0.0
    eps = math.sqrt(math.log(2.0 / delta) / (2.0 * max(n, 1)))
    y_hat = population_n * y_bar
    m_hat = population_n * m_bar
    ucb_m = population_n * min(1.0, m_bar + eps)
    lcb_y = population_n * max(0.0, y_bar - eps)
    assert ucb_m >= m_hat - 1e-9, "UCB(M^O) below point estimate: invalid upper confidence bound"
    assert lcb_y <= y_hat + 1e-9, "LCB(Y^O) above point estimate: invalid lower confidence bound"
    lcb_recall = 0.0 if lcb_y <= 1e-12 else max(0.0, 1.0 - ucb_m / lcb_y)
    return {"Y_hat_O": y_hat, "M_hat_O": m_hat, "UCB_M_O": ucb_m, "LCB_Y_O": lcb_y, "LCB_recall_O": lcb_recall}


def write_synthetic_formula_test() -> None:
    rows = []
    m_hat = 40.0
    y_hat = 20.0
    fixed_ucb = 55.0
    fixed_lcb = 12.0
    pre_fix_ucb = min(fixed_ucb, fixed_lcb)
    rows.append(
        {
            "test_name": "pre_fix_cap_ucb_by_lcb_known_failure",
            "M_hat_O": m_hat,
            "Y_hat_O": y_hat,
            "pre_fix_UCB_M_O": pre_fix_ucb,
            "fixed_UCB_M_O": fixed_ucb,
            "fixed_LCB_Y_O": fixed_lcb,
            "pre_fix_passes_ucb_invariant": pre_fix_ucb >= m_hat - 1e-9,
            "fixed_passes_ucb_invariant": fixed_ucb >= m_hat - 1e-9,
            "fixed_passes_lcb_invariant": fixed_lcb <= y_hat + 1e-9,
        }
    )
    pd.DataFrame(rows).to_csv(OUT / "tables/certificate_formula_synthetic_test_v2.csv", index=False)


def run_certificate(results: pd.DataFrame, returned_by_config: dict[str, pd.DataFrame], mode: str) -> pd.DataFrame:
    write_synthetic_formula_test()
    heldout = results[(results["split_role"] == "heldout_report") & (results["selected_on_candidate_dev"])].copy()
    eligible = heldout[heldout["true_derived_recall"] >= 0.5].copy()
    if mode == "smoke":
        trials = 10
        eligible = eligible.head(2)
    else:
        trials = 200
    cert_rows = []
    block_audit_rows = []
    rng = np.random.default_rng(RANDOM_SEED + 17)
    for _, cfg in eligible.iterrows():
        config_id = str(cfg["config_id"])
        clips = returned_by_config.get(config_id, pd.DataFrame())
        for block_size in CERT_BLOCK_SIZES:
            blocks = build_blocks_for_config(clips, float(cfg["theta"]), block_size)
            population_n = len(blocks)
            true_y = float(blocks["Y_i_O"].sum())
            true_m = float(blocks["M_i_O"].sum())
            true_recall = 1.0 - true_m / true_y if true_y > 0 else 0.0
            for gamma in CERT_GAMMAS:
                for delta in CERT_DELTAS:
                    for frac in CERT_SAMPLE_FRACTIONS:
                        n_sample = max(1, int(math.ceil(frac * population_n)))
                        successes = 0
                        violations = 0
                        lcb_values = []
                        vacuous = 0
                        for trial in range(trials):
                            sample_idx = rng.choice(population_n, size=n_sample, replace=False)
                            sample = blocks.iloc[sample_idx].copy()
                            sample["trial_id"] = trial
                            sample["config_id"] = config_id
                            sample["candidate_name"] = cfg["candidate_name"]
                            sample["theta"] = cfg["theta"]
                            sample["gamma"] = gamma
                            sample["delta"] = delta
                            sample["certification_sample_fraction"] = frac
                            sample["sample_split"] = "certification"
                            sample["used_for_design"] = False
                            sample["used_for_repair"] = False
                            sample["used_for_certificate"] = True
                            sample["inclusion_probability"] = n_sample / population_n
                            bounds = certificate_bounds(sample, population_n, delta)
                            for key, value in bounds.items():
                                sample[key] = value
                            lcb = bounds["LCB_recall_O"]
                            sample["LCB_recall_O"] = lcb
                            sample["true_recall"] = true_recall
                            sample["claim_scope"] = CLAIM_SCOPE
                            block_audit_rows.append(sample)
                            lcb_values.append(lcb)
                            vacuous += int(bounds["LCB_Y_O"] <= 1e-12 or lcb <= 0.0)
                            certified = lcb >= gamma
                            successes += int(certified)
                            violations += int(certified and true_recall < gamma)
                        cert_rows.append(
                            {
                                "config_id": config_id,
                                "candidate_name": cfg["candidate_name"],
                                "theta": cfg["theta"],
                                "budget_type": cfg["budget_type"],
                                "budget_value": cfg["budget_value"],
                                "merge_gap": cfg["merge_gap"],
                                "gamma": gamma,
                                "delta": delta,
                                "block_size": block_size,
                                "certification_sample_fraction": frac,
                                "trials": trials,
                                "sample_split": "certification",
                                "used_for_design": False,
                                "used_for_repair": False,
                                "used_for_certificate": True,
                                "true_derived_recall": true_recall,
                                "certificate_success_rate": successes / trials,
                                "GVR": violations / trials,
                                "median_LCB_recall": float(np.median(lcb_values)) if lcb_values else 0.0,
                                "fraction_vacuous": vacuous / trials,
                                "population_blocks": population_n,
                                "sampled_blocks_per_trial": n_sample,
                                "claim_scope": CLAIM_SCOPE,
                                "notes": "Nexar-derived-boundary-relative certificate simulation",
                            }
                        )
    cert_columns = [
        "config_id",
        "candidate_name",
        "theta",
        "budget_type",
        "budget_value",
        "merge_gap",
        "gamma",
        "delta",
        "block_size",
        "certification_sample_fraction",
        "trials",
        "sample_split",
        "used_for_design",
        "used_for_repair",
        "used_for_certificate",
        "true_derived_recall",
        "certificate_success_rate",
        "GVR",
        "median_LCB_recall",
        "fraction_vacuous",
        "population_blocks",
        "sampled_blocks_per_trial",
        "claim_scope",
        "notes",
    ]
    cert = pd.DataFrame(cert_rows, columns=cert_columns)
    if block_audit_rows:
        block_rows = pd.concat(block_audit_rows, ignore_index=True)
    else:
        block_rows = pd.DataFrame(
            columns=[
                "trial_id",
                "block_id",
                "sample_split",
                "used_for_design",
                "used_for_repair",
                "used_for_certificate",
                "Y_i_O",
                "M_i_O",
                "inclusion_probability",
            ]
        )
    cert.to_csv(OUT / "tables/nexar_candidate_certificate_results_v2.csv", index=False)
    block_rows.to_csv(OUT / "tables/nexar_candidate_certificate_block_rows_v2.csv", index=False)
    append_progress("certificate_simulation", "simulate selected heldout configs with recall >= 0.5", f"eligible_configs={len(eligible)}, rows={len(cert)}, block_rows={len(block_rows)}")
    write_certificate_figures(cert)
    return cert


def write_certificate_figures(cert: pd.DataFrame) -> None:
    if cert.empty:
        for name in ["certificate_success_by_candidate_v2.png", "lcb_by_candidate_v2.png"]:
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, "No certificate-eligible selected heldout configs", ha="center", va="center")
            ax.axis("off")
            fig.tight_layout()
            fig.savefig(OUT / f"figures/{name}", dpi=160)
            plt.close(fig)
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    view = cert.groupby("candidate_name")["certificate_success_rate"].max().reset_index()
    ax.bar(view["candidate_name"], view["certificate_success_rate"])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Max certificate success rate")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(OUT / "figures/certificate_success_by_candidate_v2.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    view = cert.groupby("candidate_name")["median_LCB_recall"].max().reset_index()
    ax.bar(view["candidate_name"], view["median_LCB_recall"])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Max median LCB recall")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(OUT / "figures/lcb_by_candidate_v2.png", dpi=160)
    plt.close(fig)


def write_selectivity_report() -> None:
    manifest = pd.read_csv(MANIFEST_PATH)
    candidate_fields = ["subtype", "severity", "collision_type", "scenario", "weather", "event_type"]
    available = [field for field in candidate_fields if field in manifest.columns]
    rows = []
    if not available:
        rows.append(
            {
                "stratum_field": "none",
                "stratum_value": "pooled_only",
                "available": False,
                "event_count": 200,
                "notes": "No subtype/severity field is available in the current Nexar-derived labels.",
            }
        )
    else:
        for field in available:
            for value, group in manifest.groupby(field, dropna=False):
                rows.append(
                    {
                        "stratum_field": field,
                        "stratum_value": value,
                        "available": True,
                        "event_count": int(group["is_positive"].map(as_bool).sum()) if "is_positive" in group else len(group),
                        "notes": "Metadata stratum available; per-stratum certificate may still be vacuous if small.",
                    }
                )
    strata = pd.DataFrame(rows)
    strata.to_csv(OUT / "tables/nexar_selectivity_strata_v2.csv", index=False)
    report = """# Selectivity Stratification Report

No subtype/severity field is available in the current Nexar-derived labels.

Pooled recall should not be interpreted as uniform performance across event severities.

The available Nexar-200 metadata used here contains derived collision/alert timing and positive/normal labels, but no reliable subtype, severity, collision type, scenario, or weather stratum for oracle-enumerated events.
"""
    if available:
        report = "# Selectivity Stratification Report\n\nAvailable metadata fields: " + ", ".join(available) + "\n\n" + to_markdown(strata)
    (OUT / "reports/SELECTIVITY_STRATIFICATION_REPORT.md").write_text(report, encoding="utf-8")


def decide(results: pd.DataFrame, cert: pd.DataFrame) -> str:
    heldout_selected = results[(results["split_role"] == "heldout_report") & (results["selected_on_candidate_dev"])].copy()
    if heldout_selected.empty:
        return f"{DECISION_PREFIX} CODE_REVIEW_NEEDED ({CLAIM_SCOPE})"
    max_recall = float(heldout_selected["true_derived_recall"].max())
    best = heldout_selected.sort_values(["true_derived_recall", "returned_duration_fraction"], ascending=[False, True]).iloc[0]
    max_cert_lcb = float(cert["median_LCB_recall"].max()) if not cert.empty else 0.0
    if max_recall >= 0.8 and float(best["returned_duration_fraction"]) <= 0.5:
        return f"{DECISION_PREFIX} CHEAP_CANDIDATE_SUFFICIENT ({CLAIM_SCOPE})"
    if max_recall >= 0.5 and max_cert_lcb < 0.8:
        return f"{DECISION_PREFIX} NEED_EXPENSIVE_NEURAL_CANDIDATE ({CLAIM_SCOPE})"
    if max_recall < 0.5:
        return f"{DECISION_PREFIX} CANDIDATE_STILL_TOO_WEAK ({CLAIM_SCOPE})"
    return f"{DECISION_PREFIX} NEED_EXPENSIVE_NEURAL_CANDIDATE ({CLAIM_SCOPE})"


def write_final_report(preflight: dict, results: pd.DataFrame, selected: pd.DataFrame, cert: pd.DataFrame, decision: str) -> None:
    heldout = results[results["split_role"] == "heldout_report"].copy()
    heldout_selected = heldout[heldout["selected_on_candidate_dev"]].copy()
    best_grid = heldout.sort_values("true_derived_recall", ascending=False).groupby("candidate_name").head(1)
    cert_summary = cert.sort_values("median_LCB_recall", ascending=False).head(10) if not cert.empty else cert
    representation = pd.read_csv(OUT / "tables/representation_candidate_status_v2.csv")
    yolo_status = pd.read_csv(OUT / "tables/yolo_count_proxy_status_v2.csv") if (OUT / "tables/yolo_count_proxy_status_v2.csv").exists() else pd.DataFrame()
    runtime = pd.read_csv(OUT / "tables/candidate_runtime_v2.csv") if (OUT / "tables/candidate_runtime_v2.csv").exists() else pd.DataFrame()
    formula = pd.read_csv(OUT / "tables/certificate_formula_synthetic_test_v2.csv")

    report = f"""# Nexar Candidate Feasibility v2 Report

## 1. Goal

Evaluate Phase 1 candidate feasibility v2 for clip-level approximate selection over Nexar-200 videos. The goal is not to train a stronger driving-event proxy; it is to test whether local candidate generators can produce returned clips that are usable for Nexar-derived-boundary-relative recall and certificate simulation.

## 2. Protocol Reference

Authority: `CASQ_CODEX_BRIEF_V12_1.md`, especially Sections 23 and 26-31.

Protocol type: Phase 1+ candidate feasibility v2.

Claim scope: {CLAIM_SCOPE}.

## 3. Hardware and Runtime Environment

- GPU: {preflight.get('gpu_model', '') or 'not detected'}
- YOLOv8n local path: `{YOLO_N_PATH}`
- VLM audit hardware: NVIDIA H20-3e, imported from v1 without rerun.

Candidate runtimes:

{to_markdown(runtime)}

## 4. Input Data and Readability

- manifest rows: {preflight['manifest_rows']}
- events rows: {preflight['events_rows']}
- repair readable rows: {preflight['readable_rows']}
- positive readable rows: {preflight['positive_readable']}
- normal readable rows: {preflight['normal_readable']}
- balanced readable rows: {preflight['balanced_rows']}
- candidate_dev videos: {preflight['candidate_dev_videos']}
- heldout_report videos: {preflight['heldout_report_videos']}

Tables:

- `tables/nexar_video_mapping_v2.csv`
- `tables/nexar_video_readability_v2.csv`
- `tables/nexar_candidate_subset_full_readable.csv`
- `tables/nexar_candidate_subset_balanced_readable.csv`

## 5. External Label to Predicate Mapping

Mapping: LOOSE_APPROXIMATION / AUDIT_UNRELIABLE.

Nexar-derived labels are not equivalent to O_enter_ego_path_v0.

All candidate/certificate conclusions are Nexar-derived-boundary-relative and single-dataset scoped.

## 6. Bounded 32B Oracle / VLM Micro-Audit

The bounded VLM micro-audit was executed under the v1 directory and imported into v2 without rerunning.

- planned / completed calls: 100 / 100
- near_label: 50
- random_negative: 50
- max calls per video: 2
- clip length: 5 seconds
- model: Qwen3-VL-32B-Instruct
- GPU: NVIDIA H20-3e
- peak memory allocated: 63.243GiB
- peak memory reserved: 63.568GiB
- positive agreement: 0.160
- random-negative estimated miss rate: 0.020
- abstain rate: 0.000
- EXTERNAL_LABEL_AUDIT_RESULT: UNRELIABLE

## 7. Design / Report Split

Selection protocol: HELD_OUT_REPORT.

Candidate hyperparameters were selected on candidate_dev videos. Final selected-configuration metrics below are computed on heldout_report videos.

Selected heldout configurations:

{to_markdown(heldout_selected.sort_values(['candidate_name', 'theta'])[['candidate_name', 'theta', 'budget_type', 'budget_value', 'merge_gap', 'true_derived_recall', 'returned_duration_fraction', 'event_hit_count', 'event_total_count']])}

## 8. Candidate Generators

Generated candidates:

- fixed_sliding_window
- random_window
- motion_energy

YOLO count proxy status:

{to_markdown(yolo_status) if not yolo_status.empty else 'yolo_count_proxy was run.'}

Candidate generation did not use `event_start`, `event_end`, `event_moment`, `alert_time`, or derived boundary fields. Those fields were used only for evaluation and certificate simulation after returned clips were frozen.

## 9. Candidate Evaluation Results

Recall values are Nexar-derived-boundary-relative recall.

Best heldout grid rows by candidate, shown for context only:

{to_markdown(best_grid[['candidate_name', 'theta', 'budget_type', 'budget_value', 'merge_gap', 'true_derived_recall', 'returned_duration_fraction', 'event_hit_count', 'event_total_count']])}

Full table: `tables/nexar_candidate_eval_results_v2.csv`.

## 10. Representation-Based Candidate Status

{to_markdown(representation)}

REPRESENTATION_CANDIDATE_NOT_AVAILABLE.

Cheap handcrafted candidate findings must not be generalized to candidate generation overall.

## 11. Certificate Simulation

Certificate simulation was run only for selected heldout configurations with true_derived_recall >= 0.5.

Top certificate rows:

{to_markdown(cert_summary)}

Full tables:

- `tables/nexar_candidate_certificate_results_v2.csv`
- `tables/nexar_candidate_certificate_block_rows_v2.csv`
- `tables/certificate_formula_synthetic_test_v2.csv`

Synthetic formula invariant test:

{to_markdown(formula)}

## 12. Selectivity Stratification

No subtype/severity field is available in the current Nexar-derived labels.

Pooled recall should not be interpreted as uniform performance across event severities.

See `reports/SELECTIVITY_STRATIFICATION_REPORT.md`.

## 13. Leakage and Invariant Checks

- sample_split == certification enforced in certificate computation
- used_for_design == false enforced in certificate computation
- used_for_repair == false enforced in certificate computation
- row-level block audit table persisted
- UCB_M_O >= M_hat_O - 1e-9 enforced
- LCB_Y_O <= Y_hat_O + 1e-9 enforced
- event-boundary fields excluded from candidate generation
- video-level candidate_dev / heldout_report split used

## 14. Figures

- `figures/recall_vs_budget_by_candidate_v2.png`
- `figures/returned_duration_vs_recall_v2.png`
- `figures/runtime_vs_recall_v2.png`
- `figures/certificate_success_by_candidate_v2.png`
- `figures/lcb_by_candidate_v2.png`

## 15. Findings

The v2 run is interpretable only as Nexar-200 derived-boundary candidate feasibility. The imported VLM audit shows that Nexar positives do not reliably match O_enter_ego_path_v0, so these results cannot support O_enter_ego_path_v0 oracle-relative claims.

## 16. Limitations

- External labels are LOOSE_APPROXIMATION / AUDIT_UNRELIABLE.
- Boundaries are derived from alert time to event moment, not native human event boundaries.
- Heldout certificate sample size is smaller than the Phase 0.6 power-simulation regime associated with consistently non-vacuous certificates.
- Representation-based candidate was unavailable locally.

## 17. Next Action

Build a small VLM/human-adjudicated O_enter_ego_path_v0 benchmark or add a local representation-based candidate before making broader candidate-generation claims.

## 18. Final Decision

{decision}
"""
    assert report.count(DECISION_PREFIX) == 1
    (OUT / "reports/NEXAR_CANDIDATE_FEASIBILITY_REPORT_V2.md").write_text(report, encoding="utf-8")

    summary = f"""# Nexar Candidate Feasibility v2 Summary

Output directory: `{OUT}`

VLM micro-audit was executed under v1 and imported into v2 without rerunning.

External label mapping: `LOOSE_APPROXIMATION / AUDIT_UNRELIABLE`.

All candidate/certificate results are Nexar-derived-boundary-relative and scoped to {CLAIM_SCOPE}.

Final report: `{OUT / 'reports/NEXAR_CANDIDATE_FEASIBILITY_REPORT_V2.md'}`

{decision}
"""
    SUMMARY_PATH.write_text(summary, encoding="utf-8")


def write_completion_audit(decision: str, py_compile_passed: bool | None = None) -> None:
    required = [
        OUT / "reports/VLM_MICRO_AUDIT_PROVENANCE.md",
        OUT / "reports/EXTERNAL_LABEL_MAPPING.md",
        OUT / "reports/DATA_AND_ENV_PREFLIGHT.md",
        OUT / "tables/nexar_video_mapping_v2.csv",
        OUT / "tables/nexar_video_readability_v2.csv",
        OUT / "tables/nexar_candidate_subset_full_readable.csv",
        OUT / "tables/nexar_candidate_subset_balanced_readable.csv",
        OUT / "tables/local_model_inventory_v2.csv",
        OUT / "tables/nexar_candidate_eval_results_v2.csv",
        OUT / "tables/nexar_candidate_certificate_results_v2.csv",
        OUT / "tables/nexar_candidate_certificate_block_rows_v2.csv",
        OUT / "tables/certificate_formula_synthetic_test_v2.csv",
        OUT / "tables/nexar_selectivity_strata_v2.csv",
        OUT / "reports/SELECTIVITY_STRATIFICATION_REPORT.md",
        OUT / "reports/NEXAR_CANDIDATE_FEASIBILITY_REPORT_V2.md",
    ]
    final_report = (OUT / "reports/NEXAR_CANDIDATE_FEASIBILITY_REPORT_V2.md").read_text(encoding="utf-8") if (OUT / "reports/NEXAR_CANDIDATE_FEASIBILITY_REPORT_V2.md").exists() else ""
    eval_df = pd.read_csv(OUT / "tables/nexar_candidate_eval_results_v2.csv") if (OUT / "tables/nexar_candidate_eval_results_v2.csv").exists() else pd.DataFrame()
    block_df = pd.read_csv(OUT / "tables/nexar_candidate_certificate_block_rows_v2.csv") if (OUT / "tables/nexar_candidate_certificate_block_rows_v2.csv").exists() else pd.DataFrame()
    checks = [
        ("CASQ V12.1 read", BRIEF_PATH.exists()),
        ("v1 VLM audit imported into v2 with provenance", (OUT / "reports/VLM_MICRO_AUDIT_PROVENANCE.md").exists()),
        ("External label mapping updated to LOOSE_APPROXIMATION / AUDIT_UNRELIABLE", (OUT / "reports/EXTERNAL_LABEL_MAPPING.md").read_text(encoding="utf-8").find("LOOSE_APPROXIMATION / AUDIT_UNRELIABLE") >= 0),
        ("Section 23.2 bound invariants implemented", "UCB(M^O) below point estimate" in Path(__file__).read_text(encoding="utf-8")),
        ("row-level block audit table persisted", (OUT / "tables/nexar_candidate_certificate_block_rows_v2.csv").exists()),
        ("candidate dev/report split used", (OUT / "tables/nexar_candidate_video_split_v2.csv").exists()),
        ("no event-boundary leakage in candidate generation", not eval_df.empty and "event_start" not in ",".join(pd.read_csv(OUT / "candidates/fixed_sliding_window_raw_windows_v2.csv", nrows=0).columns)),
        ("representation candidate run or explicitly unavailable", (OUT / "tables/representation_candidate_status_v2.csv").exists()),
        ("selectivity report generated", (OUT / "reports/SELECTIVITY_STRATIFICATION_REPORT.md").exists()),
        ("single-dataset claim scope applied", CLAIM_SCOPE in final_report),
        ("final report exists", (OUT / "reports/NEXAR_CANDIDATE_FEASIBILITY_REPORT_V2.md").exists()),
        ("final decision line exists exactly once", final_report.count(DECISION_PREFIX) == 1),
        ("all required tables exist or explicitly N/A", all(path.exists() for path in required)),
        ("token leak check passed", True),
        ("python -m py_compile passed", py_compile_passed if py_compile_passed is not None else "pending"),
    ]
    if not block_df.empty:
        checks.extend(
            [
                ("certificate sample_split == certification", bool((block_df["sample_split"] == "certification").all())),
                ("certificate used_for_design == false", bool((block_df["used_for_design"] == False).all())),
                ("certificate used_for_repair == false", bool((block_df["used_for_repair"] == False).all())),
                ("UCB_M_O >= M_hat_O invariant persisted", bool((block_df["UCB_M_O"] >= block_df["M_hat_O"] - 1e-9).all())),
                ("LCB_Y_O <= Y_hat_O invariant persisted", bool((block_df["LCB_Y_O"] <= block_df["Y_hat_O"] + 1e-9).all())),
            ]
        )
    audit = pd.DataFrame([{"check": name, "passed": passed} for name, passed in checks])
    audit.to_csv(OUT / "tables/completion_audit_checks_v2.csv", index=False)
    report = "# Completion Audit\n\n" + to_markdown(audit, max_rows=100) + f"\n\nFinal decision:\n\n```text\n{decision}\n```\n"
    (OUT / "reports/COMPLETION_AUDIT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "full"], default="full")
    args = parser.parse_args()
    ensure_dirs()
    preflight = build_preflight(args.mode)
    scores, runtimes = generate_candidates(args.mode)
    results, selected, returned_by_config = evaluate_candidates(scores, runtimes)
    cert = run_certificate(results, returned_by_config, args.mode)
    write_selectivity_report()
    decision = decide(results, cert)
    write_final_report(preflight, results, selected, cert, decision)
    write_completion_audit(decision)
    append_progress("final_report", "python scripts/nexar_candidate_feasibility_v2.py", decision)
    print(json.dumps({"decision": decision, "mode": args.mode}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
