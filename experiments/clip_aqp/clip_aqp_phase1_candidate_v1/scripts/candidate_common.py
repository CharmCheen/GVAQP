#!/usr/bin/env python3
"""Shared utilities for Phase 1.4 Nexar candidate feasibility.

This stage may use video/GPU only when video files are accessible. Candidate
generation must not use alert_time, event_moment, event_start, or event_end.
Derived boundaries are evaluation-only.
"""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "test_vlm/outputs/clip_aqp_phase1_candidate_v1"
PREV = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1"
DISENTANGLE_REPORT = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_disentangle_v1/reports/NEXAR_200_DISENTANGLE_REPORT.md"
DATASET_ROOT = ROOT / "datasets/casq_external/nexar"

MANIFEST_PATH = PREV / "manifests/nexar_200_manifest.csv"
EVENTS_PATH = PREV / "converted/casq_events_nexar_200.csv"
UNITS_PATH = PREV / "converted/casq_units_nexar_200.csv"

SUBDIRS = [
    "scripts",
    "reports",
    "tables",
    "figures",
    "logs",
    "candidates",
    "features",
    "videos",
    "frames",
    "config",
    "data_manifest",
]

FORBIDDEN_GENERATION_FIELDS = {"alert_time", "event_moment", "event_start", "event_end", "derived_event_start", "derived_event_end"}

CANDIDATE_COLUMNS = [
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

EVAL_COLUMNS = [
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

CERT_COLUMNS = [
    "candidate_name",
    "theta",
    "gamma",
    "delta",
    "block_size",
    "certification_sample_fraction",
    "true_derived_recall",
    "median_LCB_recall",
    "p10_LCB_recall",
    "p90_LCB_recall",
    "fraction_vacuous",
    "certificate_success_rate",
    "GVR",
    "tightness",
    "trials",
    "notes",
]


def ensure_dirs() -> None:
    for name in SUBDIRS:
        (OUT / name).mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def empty_csv(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=columns).to_csv(path, index=False)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def markdown_table(df: pd.DataFrame, max_rows: int = 50) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows)
    lines = ["| " + " | ".join(view.columns) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in view.columns) + " |")
    return "\n".join(lines)


def gpu_info() -> dict:
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            first = proc.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first.split(",")]
            return {
                "gpu_visible": True,
                "gpu_model": parts[0] if len(parts) > 0 else "",
                "gpu_memory_total": parts[1] if len(parts) > 1 else "",
                "driver_version": parts[2] if len(parts) > 2 else "",
                "gpu_used": False,
                "gpu_use_reason": "No video files were accessible, so no GPU inference was run.",
            }
    except Exception as exc:
        return {"gpu_visible": False, "gpu_model": "", "gpu_memory_total": "", "driver_version": "", "gpu_used": False, "gpu_use_reason": f"nvidia-smi failed: {exc}"}
    return {"gpu_visible": False, "gpu_model": "", "gpu_memory_total": "", "driver_version": "", "gpu_used": False, "gpu_use_reason": "No GPU visible."}


def write_placeholder_figures() -> None:
    import matplotlib.pyplot as plt

    ensure_dirs()
    names = [
        "recall_vs_budget_by_candidate.png",
        "returned_duration_vs_recall.png",
        "runtime_vs_recall.png",
        "certificate_success_by_candidate.png",
        "lcb_by_candidate.png",
    ]
    for name in names:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        ax.text(0.5, 0.55, "No accessible Nexar videos", ha="center", va="center", fontsize=12)
        ax.text(0.5, 0.40, "Candidate generation not run", ha="center", va="center", fontsize=10)
        ax.set_axis_off()
        fig.tight_layout()
        fig.savefig(OUT / "figures" / name, dpi=140)
        plt.close(fig)


def write_schema_mapping() -> None:
    text = "\n".join(
        [
            "inputs:",
            f"  manifest: {MANIFEST_PATH}",
            f"  casq_events: {EVENTS_PATH}",
            f"  casq_units: {UNITS_PATH}",
            "candidate_generation_forbidden_fields:",
            *[f"  - {field}" for field in sorted(FORBIDDEN_GENERATION_FIELDS)],
            "evaluation_only_fields:",
            "  - event_start",
            "  - event_end",
            "  - event_midpoint",
            "candidate_columns:",
            *[f"  - {col}" for col in CANDIDATE_COLUMNS],
            "evaluation_columns:",
            *[f"  - {col}" for col in EVAL_COLUMNS],
            "",
        ]
    )
    (OUT / "config/schema_mapping.yaml").write_text(text, encoding="utf-8")


def write_experiment_config() -> None:
    write_json(
        OUT / "config/experiment_config.json",
        {
            "experiment": "clip_aqp_phase1_candidate_v1",
            "created_utc": utc_now(),
            "dataset_root": str(DATASET_ROOT),
            "manifest_path": str(MANIFEST_PATH),
            "events_path": str(EVENTS_PATH),
            "units_path": str(UNITS_PATH),
            "phase1_3_report": str(DISENTANGLE_REPORT),
            "smoke_subset": {"positive_videos": 50, "normal_videos": 50},
            "full_subset_if_accessible": {"positive_videos": 200, "normal_videos": 200},
            "frame_rates": {"main": 1, "smoke_optional": 2},
            "candidate_generators": ["fixed_sliding_window", "motion_energy", "yolo_count_proxy", "clip_or_siglip_text_score", "optional_small_vlm_score"],
            "candidate_generation_forbidden_fields": sorted(FORBIDDEN_GENERATION_FIELDS),
            "evaluation_thetas": [0.3, 0.5],
            "budgets": {"top_k_per_video": [1, 3, 5, 10], "top_duration_fraction": [0.05, 0.10, 0.20, 0.35, 0.50]},
            "merge_gaps": [0.0, 2.5, 5.0],
            "certification": {"gamma": [0.8, 0.9], "delta": [0.05, 0.1], "block_size": [10, 15], "sample_fraction": [0.2, 0.35, 0.5, 0.75], "trials": 200},
        },
    )


def write_input_manifest() -> None:
    rows = []
    for name, path in [("nexar_200_manifest", MANIFEST_PATH), ("casq_events_nexar_200", EVENTS_PATH), ("casq_units_nexar_200", UNITS_PATH), ("phase1_3_report", DISENTANGLE_REPORT)]:
        if path.suffix == ".csv" and path.exists():
            df = pd.read_csv(path)
            rows.append({"input_name": name, "path": str(path), "exists": True, "rows": len(df), "columns": ";".join(df.columns)})
        else:
            rows.append({"input_name": name, "path": str(path), "exists": path.exists(), "rows": "", "columns": ""})
    pd.DataFrame(rows).to_csv(OUT / "data_manifest/input_manifest.csv", index=False)


def write_empty_downstream_tables() -> None:
    empty_csv(OUT / "tables/frame_index.csv", ["video_id", "frame_id", "timestamp", "frame_path", "source_video_path"])
    empty_csv(OUT / "tables/candidate_eval_results.csv", EVAL_COLUMNS)
    empty_csv(OUT / "tables/candidate_certificate_results.csv", CERT_COLUMNS)
    pd.DataFrame(
        [
            {"constraint": "sample_split == certification", "passed": "not_applicable_no_access"},
            {"constraint": "used_for_design == false", "passed": "not_applicable_no_access"},
            {"constraint": "used_for_repair == false", "passed": "not_applicable_no_access"},
            {"constraint": "UCB_M_O >= M_hat_O - 1e-9", "passed": "not_applicable_no_access"},
            {"constraint": "LCB_Y_O <= Y_hat_O + 1e-9", "passed": "not_applicable_no_access"},
        ]
    ).to_csv(OUT / "tables/candidate_certificate_validity_constraints.csv", index=False)

