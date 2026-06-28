#!/usr/bin/env python3
from __future__ import annotations

import json

import pandas as pd

from local_candidate_common import OUT, append_progress, markdown_table


def choose_decision(eval_df: pd.DataFrame, status: pd.DataFrame) -> str:
    if eval_df.empty:
        return "VIDEO_OR_LABEL_MAPPING_FAILED"
    if not bool((status["uses_oracle_annotation"].astype(bool) == False).all()):
        return "CODE_REVIEW_NEEDED"
    if {"fixed_sliding_window", "random", "motion_energy"}.issubset(set(eval_df["candidate_name"])):
        return "PIPELINE_READY_FOR_NEXAR_VIDEO"
    return "LOCAL_DATA_TOO_WEAK_FOR_EVALUATION"


def main() -> int:
    video = pd.read_csv(OUT / "tables/local_video_inventory.csv")
    labels = pd.read_csv(OUT / "tables/local_label_inventory.csv")
    units = pd.read_csv(OUT / "tables/local_smoke_units.csv")
    frames = pd.read_csv(OUT / "tables/local_frame_index.csv")
    status = pd.read_csv(OUT / "tables/local_candidate_generation_status.csv")
    eval_df = pd.read_csv(OUT / "tables/local_candidate_eval_results.csv")
    gpu = json.loads((OUT / "logs/gpu_usage.json").read_text())
    decision = choose_decision(eval_df, status)

    best = eval_df[eval_df["k"] == eval_df["k"].min()].sort_values("enrichment_over_random", ascending=False).head(10) if not eval_df.empty else eval_df
    lines = [
        "# Local Candidate Smoke Report",
        "",
        "## 1. Goal",
        "",
        "Smoke-test video-content candidate generators on local videos and clips already present in the G-ARC project. This is pipeline feasibility/debugging only, not a replacement for Nexar-200 or clean event-boundary evaluation.",
        "",
        "## 2. Local video inventory",
        "",
        f"Inventoried local video files: `{len(video)}`. Readable files: `{int(video['readable'].sum())}`.",
        "",
        markdown_table(video[["video_path", "file_size_bytes", "duration_seconds", "readable", "source_category"]], max_rows=20),
        "",
        "## 3. Local label inventory",
        "",
        f"Inventoried local label/proxy files: `{len(labels)}`.",
        "",
        markdown_table(labels[["file_path", "row_count", "has_clip_id", "has_start_end", "has_oracle_label", "has_human_label", "has_proxy_score"]], max_rows=20),
        "",
        "## 4. Smoke dataset construction",
        "",
        f"Built `{len(units)}` local-pseudo units from `kinematic_proxy` clips. `has_clean_event_boundary` is false for all units; no event_start/event_end boundaries were fabricated.",
        "",
        markdown_table(units.head(12)),
        "",
        "## 5. Candidate generators",
        "",
        markdown_table(status),
        "",
        "## 6. Evaluation metrics and limitations",
        "",
        "Because clean event boundaries are absent, evaluation is unit-level enrichment against available conservative VLM/human-audit labels. Metrics are positive coverage, precision@k, enrichment over the local positive base rate, returned duration, runtime, and throughput where available. These are local-pseudo debugging metrics, not strict event IoU recall.",
        "",
        "## 7. Results",
        "",
        markdown_table(best),
        "",
        "Full results: `tables/local_candidate_eval_results.csv`.",
        "",
        "## 8. Runtime / GPU usage",
        "",
        f"GPU visible: `{gpu.get('gpu_visible')}`. GPU used: `{gpu.get('gpu_used')}`. GPU model: `{gpu.get('gpu_model')}`. YOLO status: `{gpu.get('status')}`. Frames processed by YOLO: `{gpu.get('frames_processed', '')}`. YOLO throughput fps: `{gpu.get('throughput_fps', '')}`.",
        "",
        "## 9. What can transfer to Nexar once videos are available",
        "",
        "- Local media inventory, frame extraction, fixed-window generation, motion scoring, YOLO count features, candidate CSV schema, and unit-level evaluation code paths can transfer directly.",
        "- The evaluation target must change from local-pseudo clip labels to Nexar derived-boundary or clean event-boundary evaluation when videos are available.",
        "- Certificate claims still require the repaired block/event audit and must not use these local pseudo labels as human ground truth.",
        "",
        "## 10. Recommendation",
        "",
    ]
    if decision == "PIPELINE_READY_FOR_NEXAR_VIDEO":
        lines.append("Use this code path as the bounded candidate smoke pipeline once Nexar videos are accessible. Keep local results as debugging evidence only.")
    elif decision == "LOCAL_PROXY_HAS_SIGNAL":
        lines.append("The local proxy has signal, but Nexar transfer still needs video access and clean evaluation.")
    elif decision == "LOCAL_DATA_TOO_WEAK_FOR_EVALUATION":
        lines.append("The pipeline runs, but local labels are too weak for meaningful candidate-quality conclusions.")
    elif decision == "VIDEO_OR_LABEL_MAPPING_FAILED":
        lines.append("Fix local video/label mapping before running Nexar candidate smoke.")
    else:
        lines.append("Review code and leakage checks before interpreting results.")
    lines.extend(["", f"LOCAL_CANDIDATE_DECISION: {decision}", ""])
    (OUT / "reports/LOCAL_CANDIDATE_SMOKE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    append_progress("report", "python scripts/50_generate_local_report.py", f"decision={decision}", next_action="py_compile and completion audit")
    print(f"LOCAL_CANDIDATE_DECISION: {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

