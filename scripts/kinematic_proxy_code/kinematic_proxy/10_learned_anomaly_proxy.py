#!/usr/bin/env python3
"""Feasibility check for a learned traffic-anomaly proxy.

This script intentionally does not fabricate anomaly scores. It searches only
configured local directories for a runnable traffic anomaly detector, checkpoint,
and inference entrypoint. If the required pieces are missing, it writes a
blocking report and exits successfully.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, load_config, validate_base_paths


DEFAULT_SEARCH_DIRS = [
    Path("/qiuyeqing/llama_prl/G-ARC/test_vlm"),
    Path("/qiuyeqing/llama_prl/G-ARC/refe_repos"),
    Path("/qiuyeqing/llama_prl/G-ARC/models"),
    Path("/qiuyeqing/llama_prl/G-ARC/try_or_no"),
]

KEYWORDS = [
    "dota",
    "detection-of-traffic-anomaly",
    "traffic anomaly",
    "traffic_anomaly",
    "anomaly_detection",
    "learned anomaly",
    "future object localization",
    "hf2",
]

INFERENCE_KEYWORDS = ["inference", "infer", "demo", "predict", "test"]
WEIGHT_SUFFIXES = {".pth", ".pt", ".ckpt", ".pkl", ".onnx", ".bin", ".safetensors"}
TEXT_SUFFIXES = {".py", ".sh", ".yaml", ".yml", ".md", ".txt", ".json", ".toml", ".cfg"}
SKIP_DIRS = {".git", "__pycache__", ".ipynb_checkpoints"}
SKIP_SUBPATHS = [
    "/models/vlm",
    "/try_or_no/academic-research-skills",
    "/try_or_no/outputs",
    "/test_vlm/outputs",
]
MAX_TEXT_BYTES = 2_000_000


def norm_text(value: str) -> str:
    return value.replace("-", "_").replace(" ", "_").lower()


def contains_keyword(value: str, keywords: list[str] = KEYWORDS) -> bool:
    raw = value.lower()
    normalized = norm_text(value)
    for keyword in keywords:
        if keyword in raw or norm_text(keyword) in normalized:
            return True
    return False


def contains_detector_context(value: str) -> bool:
    raw = value.lower()
    normalized = norm_text(value)
    if contains_keyword(value):
        return True
    has_video_anomaly_detection = "video anomaly detection" in raw or "video_anomaly_detection" in normalized
    has_accident_detector = ("accident" in raw or "crash" in raw) and any(
        word in raw for word in ["detect", "anticipat", "predict", "recognition"]
    )
    has_vad_token = (" vad " in f" {raw} " or "/vad" in raw or "_vad" in raw or "-vad" in raw) and "anomaly" in raw
    return has_video_anomaly_detection or has_accident_detector or has_vad_token


def configured_search_dirs(cfg: dict) -> list[Path]:
    learned_cfg = cfg.get("learned_anomaly_proxy") or {}
    dirs = learned_cfg.get("search_dirs") or [str(p) for p in DEFAULT_SEARCH_DIRS]
    result = []
    for item in dirs:
        path = Path(item)
        if path.exists():
            result.append(path)
    return result


def should_skip_path(path: Path) -> bool:
    path_str = str(path)
    return any(part in path_str for part in SKIP_SUBPATHS)


def walk_allowed(search_dirs: list[Path]):
    for root in search_dirs:
        if root.is_file():
            if not should_skip_path(root):
                yield root
            continue
        for current, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            current_path = Path(current)
            dirs[:] = [d for d in dirs if not should_skip_path(current_path / d)]
            if should_skip_path(current_path):
                continue
            yield current_path
            for name in files:
                yield current_path / name


def safe_read_text(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def is_current_feasibility_file(path: Path) -> bool:
    name = path.name
    if name in {"10_learned_anomaly_proxy.py", "README.md", "config.yaml"}:
        return True
    return "BLOCKED_learned_anomaly_proxy" in str(path)


def collect_findings(search_dirs: list[Path]) -> dict:
    findings = {
        "searched_dirs": [str(p) for p in search_dirs],
        "candidate_dirs": [],
        "candidate_text_files": [],
        "candidate_weight_files": [],
        "all_weight_files": [],
        "candidate_inference_files": [],
        "installed_repos": [],
    }
    seen = {key: set() for key in findings if key != "searched_dirs"}

    for path in walk_allowed(search_dirs):
        path_str = str(path)
        if path.is_dir():
            if (path / ".git").is_dir():
                seen["installed_repos"].add(path_str)
            if contains_detector_context(path.name) or contains_detector_context(path_str):
                seen["candidate_dirs"].add(path_str)
            continue

        suffix = path.suffix.lower()
        if suffix in WEIGHT_SUFFIXES:
            seen["all_weight_files"].add(path_str)
            if contains_detector_context(path_str):
                seen["candidate_weight_files"].add(path_str)
            continue

        if suffix not in TEXT_SUFFIXES:
            continue

        if is_current_feasibility_file(path):
            continue

        name_is_relevant = contains_detector_context(path_str)
        text = ""
        if not name_is_relevant:
            text = safe_read_text(path)
        text_is_relevant = contains_detector_context(text) if text else False
        if name_is_relevant or text_is_relevant:
            seen["candidate_text_files"].add(path_str)
            lower_path = path.name.lower()
            lower_text = text.lower() if text else ""
            if any(k in lower_path for k in INFERENCE_KEYWORDS) or any(k in lower_text for k in INFERENCE_KEYWORDS):
                seen["candidate_inference_files"].add(path_str)

    for key, values in seen.items():
        findings[key] = sorted(values)
    return findings


def is_runnable(findings: dict) -> bool:
    has_repo_or_code = bool(findings["candidate_dirs"] or findings["candidate_text_files"])
    has_weights = bool(findings["candidate_weight_files"])
    has_entrypoint = bool(findings["candidate_inference_files"])
    return has_repo_or_code and has_weights and has_entrypoint


def bullet_list(items: list[str], limit: int = 80) -> list[str]:
    if not items:
        return ["- none"]
    lines = [f"- `{item}`" for item in items[:limit]]
    if len(items) > limit:
        lines.append(f"- ... {len(items) - limit} more omitted")
    return lines


def write_blocked_report(path: Path, findings: dict, output_dir: Path, learned_cfg: dict) -> None:
    scores_path = Path(learned_cfg.get("scores_csv", output_dir / "learned_anomaly_scores.csv"))
    augmented_path = Path(learned_cfg.get("augmented_proxy_scores_csv", output_dir / "proxy_scores_augmented.csv"))
    lines = [
        "# BLOCKED: Learned Anomaly Proxy Feasibility Check",
        "",
        "No runnable local DoTA / traffic anomaly / learned anomaly proxy was found. No learned anomaly scores were generated, and no learned-anomaly budget simulation was run.",
        "",
        "## Searched Directories",
        "",
    ]
    lines.extend(bullet_list(findings["searched_dirs"]))
    lines.extend(["", "## Installed Local Repositories Found", ""])
    lines.extend(bullet_list(findings["installed_repos"]))
    lines.extend(["", "## Candidate Traffic-Anomaly Directories", ""])
    lines.extend(bullet_list(findings["candidate_dirs"]))
    lines.extend(["", "## Candidate Traffic-Anomaly Text Files", ""])
    lines.extend(bullet_list(findings["candidate_text_files"]))
    lines.extend(["", "## Candidate Pretrained Weights", ""])
    lines.extend(bullet_list(findings["candidate_weight_files"]))
    lines.extend(["", "## All Local Weight-Like Files Observed", ""])
    lines.extend(bullet_list(findings["all_weight_files"]))
    lines.extend(["", "## Candidate Inference / Demo Entrypoints", ""])
    lines.extend(bullet_list(findings["candidate_inference_files"]))
    lines.extend(
        [
            "",
            "## Why This Is Blocked",
            "",
            "- No DoTA / traffic anomaly detector repository was found under the allowed search directories.",
            "- No pretrained traffic-anomaly checkpoint was found. The local weight-like files observed are VLM, YOLO, or otherwise unrelated assets, not learned anomaly detector weights.",
            "- No traffic-anomaly inference or demo entrypoint was found.",
            "- Because there is no runnable detector, producing `score_learned_anomaly` would be fabricated and is not allowed.",
            "",
            "## Minimum User-Provided Resources Needed",
            "",
            "Provide the following local resources before this route can be evaluated:",
            "",
            "- `repo path`: path to a DoTA / traffic anomaly / video anomaly detector repository.",
            "- `checkpoint path`: pretrained weights compatible with that repository.",
            "- `inference command`: command that accepts either clip videos, frame directories, or an annotation/table format and emits frame-level or clip-level anomaly scores.",
            "- `expected input format`: one of raw video clips, extracted frames, optical flow, bbox tracks, or DoTA-format annotations.",
            "- `score semantics`: whether larger scores mean more anomalous and whether scores are calibrated per frame or per clip.",
            "",
            "## Planned Adapter Contract Once Resources Exist",
            "",
            f"- Per-clip learned scores should be written to `{scores_path}`.",
            "- Required columns: `clip_id,start_time,end_time,clip_path,score_learned_anomaly,score_source,score_aggregation,runtime_sec,status,error_message`.",
            "- If detector output is frame-level, aggregate to clip level using max or top-k mean and document the aggregation.",
            f"- Merge `score_learned_anomaly` into `{augmented_path}` alongside existing `score_count`, `score_naive`, and `score_kinematic`.",
            "- Only after real scores exist should `05_budget_simulation.py` be extended/run with learned-anomaly methods such as `top_learned_anomaly`, `temporal_nms_learned_anomaly`, and learned ensembles.",
            "",
            "## Recommendation",
            "",
            "- Continue using count / naive proxies plus temporal NMS, proxy-triggered expansion, and conservative VLM pseudo-GT as the main experimental line.",
            "- Do not invest in the DoTA / learned anomaly route until a concrete local repo, checkpoint, and inference command are available.",
            "- Do not resume blind kinematic-v0 tuning as the main path.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check feasibility of a learned traffic-anomaly proxy.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--limit", type=int, default=0, help="Reserved for future inference smoke tests. Feasibility checks ignore it.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    learned_cfg = cfg.get("learned_anomaly_proxy") or {}
    report_path = Path(learned_cfg.get("blocked_report_md", output_dir / "BLOCKED_learned_anomaly_proxy.md"))

    search_dirs = configured_search_dirs(cfg)
    findings = collect_findings(search_dirs)
    if is_runnable(findings):
        # The current project has no generic detector API contract. Reaching this
        # branch means a candidate exists, but a specific adapter still needs to
        # be implemented for that detector's input/output format.
        write_blocked_report(report_path, findings, output_dir, learned_cfg)
        print(f"blocked_report={report_path}")
        print("status=candidate_found_but_no_detector_specific_adapter")
        return

    write_blocked_report(report_path, findings, output_dir, learned_cfg)
    print(f"blocked_report={report_path}")
    print("status=no_runnable_learned_anomaly_proxy")


if __name__ == "__main__":
    main()
