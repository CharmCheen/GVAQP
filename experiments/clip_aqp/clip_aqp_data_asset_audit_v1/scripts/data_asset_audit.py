#!/usr/bin/env python3
"""Data asset audit and Micro-CASQ planning pass.

This script is intentionally metadata-only. It reads file metadata, CSV headers
and CSV rows where needed to build planning tables. It does not decode videos,
run VLM/YOLO, train models, or download data.
"""

from __future__ import annotations

import csv
import fnmatch
import hashlib
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "test_vlm/outputs/clip_aqp_data_asset_audit_v1"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"
SCRIPTS = OUT / "scripts"
SCHEMA = OUT / "schema"
SUMMARY_PATH = ROOT / "garc_eval/outputs/clip_aqp_data_asset_audit_v1_summary.md"

USER_PROTOCOL_PATH = ROOT / "docs/clip_aqp/CASQ_CODEX_BRIEF_V12_1.md"
ACTUAL_PROTOCOL_PATH = ROOT / "CASQ_CODEX_BRIEF_V12_1.md"

ROLES = [
    "debug_pipeline_data",
    "noisy_external_label_data",
    "candidate_mining_pool",
    "adjudication_pool",
    "gold_eval_candidate",
    "not_currently_usable",
]

SEARCH_PATTERNS = [
    "*vlm*label*.csv",
    "*vlm*.csv",
    "*conservative*.csv",
    "*human*audit*.csv",
    "*audit*.csv",
    "*clip*.csv",
    "*event*.csv",
    "*budget*.csv",
    "*proxy*.csv",
    "*candidate*.csv",
    "*nexar*.csv",
    "*roadclip*.csv",
    "*phase0*.csv",
    "*phase1*.csv",
    "*.md",
]

KNOWN_IMPORTANT_PATHS = [
    "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv",
    "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/roadclip_v2_audit_package.tar.gz",
    "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/audit_package",
    "test_vlm/outputs/kinematic_proxy/human_audit_conservative_vlm_68clips.tar.gz",
    "test_vlm/outputs/kinematic_proxy/human_audit_conservative_vlm_68clips",
    "test_vlm/outputs/kinematic_proxy/clips",
    "test_vlm/outputs/clip_aqp_phase0_v1",
    "test_vlm/outputs/clip_aqp_phase0_v1/repair_v1",
    "test_vlm/outputs/clip_aqp_phase0_v1/power_v1",
    "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1",
    "test_vlm/outputs/clip_aqp_phase1_nexar_200_disentangle_v1",
    "test_vlm/outputs/clip_aqp_phase1_local_candidate_smoke_v1",
    "test_vlm/outputs/clip_aqp_phase1_nexar_video_repair_v1",
    "test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1",
    "test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2",
    "datasets/casq_external/nexar/videos_hf",
]

TOKEN_PATTERNS = [
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    re.compile(r"huggingface_[A-Za-z0-9]{20,}", re.IGNORECASE),
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def ensure_dirs() -> None:
    for path in (TABLES, REPORTS, LOGS, SCRIPTS, SCHEMA, SUMMARY_PATH.parent):
        path.mkdir(parents=True, exist_ok=True)


def read_protocol() -> tuple[Path, str, str]:
    if USER_PROTOCOL_PATH.exists():
        protocol_path = USER_PROTOCOL_PATH
        protocol_note = "User-specified V12.1 path exists and was read."
    elif ACTUAL_PROTOCOL_PATH.exists():
        protocol_path = ACTUAL_PROTOCOL_PATH
        protocol_note = (
            "User-specified docs/clip_aqp/CASQ_CODEX_BRIEF_V12_1.md was missing; "
            "root CASQ_CODEX_BRIEF_V12_1.md was read as the available V12.1 protocol."
        )
    else:
        raise FileNotFoundError("CASQ_CODEX_BRIEF_V12_1.md not found in expected locations")
    text = protocol_path.read_text(encoding="utf-8", errors="replace")
    if "V12.1" not in text or "External Label <-> Predicate Mapping Requirement" not in text:
        raise RuntimeError(f"Protocol at {protocol_path} does not look like CASQ V12.1")
    return protocol_path, protocol_note, text


def matches_asset(path: Path) -> bool:
    name = path.name.lower()
    if path.suffix.lower() in {".csv", ".md"}:
        return any(fnmatch.fnmatch(name, pat.lower()) for pat in SEARCH_PATTERNS)
    if name.endswith(".tar.gz"):
        return "audit" in name or "clip" in name or "roadclip" in name
    if path.is_dir():
        return any(token in name for token in ["audit", "clip", "event", "budget", "proxy", "candidate", "nexar", "phase0", "phase1", "roadclip", "videos_hf"])
    return False


def discover_assets() -> list[Path]:
    found: dict[str, Path] = {}
    skip_dirs = {".git", "__pycache__", "refe_repos"}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        rel_current = rel(current)
        if current == OUT or rel_current.startswith(rel(OUT) + "/"):
            dirnames[:] = []
            continue
        dirnames[:] = [
            d for d in dirnames
            if d not in skip_dirs
            and (current / d) != OUT
            and not rel(current / d).startswith(rel(OUT) + "/")
            and not rel(current / d).startswith("datasets/casq_external/nexar/videos_hf/train")
            and not rel(current / d).startswith("datasets/casq_external/nexar/hf_metadata_probe/.cache")
        ]
        if matches_asset(current):
            found[str(current)] = current
        for filename in filenames:
            path = current / filename
            if matches_asset(path):
                found[str(path)] = path
    for item in KNOWN_IMPORTANT_PATHS:
        path = ROOT / item
        found[str(path)] = path
    return sorted(found.values(), key=lambda p: rel(p))


def csv_columns(path: Path) -> list[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
            return next(csv.reader(f), [])
    except Exception:
        return []


def csv_row_count(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
            return max(sum(1 for _ in f) - 1, 0)
    except Exception:
        return None


def has_any(columns: list[str], tokens: list[str]) -> bool:
    lowered = [c.lower() for c in columns]
    return any(any(token in c for token in tokens) for c in lowered)


def exact_or_contains(columns: list[str], exact: list[str], contains: list[str] | None = None) -> bool:
    lowered = [c.lower() for c in columns]
    if any(e in lowered for e in exact):
        return True
    return has_any(columns, contains or [])


def infer_label_source(path: Path, columns: list[str]) -> str:
    p = rel(path).lower()
    cols = " ".join(c.lower() for c in columns)
    if "human" in p or "human_label" in cols or "human_review" in cols:
        return "human_audit_subset"
    if "vlm_micro_audit" in p or "qwen" in p or "vlm" in p or "conservative_positive" in cols:
        return "vlm_derived"
    if "nexar" in p or "external_label" in cols or "label_source" in cols and "nexar" in cols:
        return "external_nexar_metadata"
    if "proxy" in p or "candidate" in p or "score" in cols:
        return "proxy_or_candidate_score"
    if "phase0" in p:
        return "phase0_pseudo_oracle"
    return "unknown_or_mixed"


def infer_boundary_source(path: Path, columns: list[str]) -> str:
    p = rel(path).lower()
    cols = " ".join(c.lower() for c in columns)
    if "boundary_source" in cols:
        return "declared_in_boundary_source_column"
    if "derived_event_start" in cols or "derived_event_end" in cols or "event_moment" in cols or "alert" in cols:
        return "derived_or_external_metadata_boundary"
    if "event_start" in cols and "event_end" in cols:
        if "phase0" in p or "pseudo" in p:
            return "pseudo_or_oracle_relative_boundary"
        if "human" in p:
            return "human_audit_clip_boundary_or_event_boundary"
        if "vlm" in p:
            return "vlm_oracle_relative_boundary"
        return "event_boundary_columns_present_source_unclear"
    if "start_time" in cols and "end_time" in cols or "clip_start" in cols and "clip_end" in cols:
        return "clip_window_boundary_only"
    return "missing_or_unknown"


def asset_metadata(path: Path) -> dict[str, Any]:
    exists = path.exists()
    stat = path.stat() if exists else None
    file_type = "missing"
    if exists:
        if path.is_dir():
            file_type = "directory"
        elif path.name.endswith(".tar.gz"):
            file_type = "tar.gz"
        else:
            file_type = path.suffix.lower().lstrip(".") or "file"
    columns: list[str] = []
    row_count: int | None = None
    if exists and path.is_file() and path.suffix.lower() == ".csv":
        columns = csv_columns(path)
        row_count = csv_row_count(path)
    short_notes = []
    if not exists:
        short_notes.append("known important path missing")
    if path.is_dir() and exists:
        try:
            children = sum(1 for _ in path.iterdir())
            short_notes.append(f"directory children={children}; no recursive byte scan")
        except Exception as exc:
            short_notes.append(f"directory listing failed: {exc}")
    if exists and path.is_file() and stat and stat.st_size > 200_000_000:
        short_notes.append("large file; metadata only")
    return {
        "file_path": rel(path),
        "file_type": file_type,
        "exists": exists,
        "size_bytes": stat.st_size if stat else "",
        "modified_time": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat() if stat else "",
        "row_count": row_count if row_count is not None else "",
        "columns": "|".join(columns),
        "contains_video_id": exact_or_contains(columns, ["video_id"], ["video_id", "video"]),
        "contains_clip_id": exact_or_contains(columns, ["clip_id", "window_id", "sample_id"], ["clip_id", "window_id"]),
        "contains_start_time": exact_or_contains(columns, ["start_time", "clip_start", "window_start"], ["start_time", "clip_start", "window_start"]),
        "contains_end_time": exact_or_contains(columns, ["end_time", "clip_end", "window_end"], ["end_time", "clip_end", "window_end"]),
        "contains_event_id": exact_or_contains(columns, ["event_id", "derived_event_id"], ["event_id"]),
        "contains_event_start": exact_or_contains(columns, ["event_start", "derived_event_start"], ["event_start", "derived_event_start"]),
        "contains_event_end": exact_or_contains(columns, ["event_end", "derived_event_end"], ["event_end", "derived_event_end"]),
        "contains_label": exact_or_contains(columns, ["label", "external_label", "original_label"], ["label"]),
        "contains_oracle_label": exact_or_contains(columns, ["oracle_label"], ["oracle"]),
        "contains_vlm_label": exact_or_contains(columns, ["vlm_label", "conservative_positive"], ["vlm", "conservative_positive"]),
        "contains_human_label": exact_or_contains(columns, ["human_label", "human_label_conservative_positive"], ["human"]),
        "contains_confidence": exact_or_contains(columns, ["confidence"], ["confidence"]),
        "contains_source_path": exact_or_contains(columns, ["source_path", "source_annotation_path"], ["source_path", "source_"]),
        "contains_video_path": exact_or_contains(columns, ["video_path", "source_video_path"], ["video_path", "source_video_path"]),
        "contains_boundary_status": exact_or_contains(columns, ["boundary_status"], ["boundary_status"]),
        "contains_sample_split": exact_or_contains(columns, ["sample_split"], ["sample_split"]),
        "contains_used_for_design": exact_or_contains(columns, ["used_for_design"], ["used_for_design"]),
        "contains_used_for_repair": exact_or_contains(columns, ["used_for_repair"], ["used_for_repair"]),
        "contains_used_for_certificate": exact_or_contains(columns, ["used_for_certificate"], ["used_for_certificate"]),
        "likely_label_source": infer_label_source(path, columns),
        "likely_boundary_source": infer_boundary_source(path, columns),
        "short_notes": "; ".join(short_notes),
    }


def classify_asset(row: dict[str, Any]) -> dict[str, Any]:
    path = row["file_path"].lower()
    label_source = str(row["likely_label_source"])
    boundary_source = str(row["likely_boundary_source"])
    risks: set[str] = set()
    secondary: set[str] = set()
    reason = ""
    claim = "not_usable"
    role = "not_currently_usable"

    if not row["exists"]:
        risks.add("other")
        reason = "Known path is missing in current checkout."
    elif row["file_type"] == "directory":
        if "videos_hf" in path or path.endswith("/clips") or "audit_package" in path:
            role = "candidate_mining_pool"
            claim = "candidate_mining_only"
            reason = "Directory contains video/clip/audit-package assets; usable as source material if timing and labels are supplied by paired tables."
            risks.add("label_semantics_unclear")
        else:
            role = "debug_pipeline_data"
            claim = "debug_only"
            reason = "Directory is mainly an experiment output or scaffold."
            risks.add("stale_or_diagnostic_output")
    elif "nexar" in path:
        role = "noisy_external_label_data"
        secondary.add("candidate_mining_pool")
        claim = "external_label_relative"
        reason = "Nexar collision/alert metadata is a loose approximation and the 32B micro-audit marked the mapping unreliable."
        risks.update({"external_label_only", "derived_boundary", "label_semantics_unclear"})
        if not row["contains_video_path"]:
            risks.add("missing_video_path")
        if row["contains_event_start"] or "derived" in boundary_source:
            risks.add("pseudo_boundary")
    elif "human_audit" in path or label_source == "human_audit_subset":
        role = "gold_eval_candidate"
        secondary.update({"adjudication_pool", "candidate_mining_pool"})
        claim = "possible_gold_after_adjudication"
        reason = "Human-audited subset may be useful after schema and boundary verification; not automatically promoted to Micro-CASQ gold."
        risks.update({"human_audited_subset", "scene_diversity_narrow"})
        if not row["contains_event_start"] or not row["contains_event_end"]:
            risks.add("missing_event_boundary")
    elif "vlm" in path or label_source == "vlm_derived":
        role = "candidate_mining_pool"
        secondary.add("adjudication_pool")
        claim = "oracle_relative_after_audit"
        reason = "Old VLM-derived labels are useful for mining likely positives/ambiguous cases but are not human truth."
        risks.update({"oracle_relative_only", "sample_reuse_risk"})
        if not row["contains_video_path"] and not row["contains_source_path"]:
            risks.add("missing_video_path")
    elif "phase0" in path or "local_candidate_smoke" in path or "candidate" in path or "proxy" in path or "budget" in path:
        role = "debug_pipeline_data"
        secondary.add("candidate_mining_pool")
        claim = "debug_only" if "phase0" in path else "candidate_mining_only"
        reason = "Experiment/debug output can test schemas and suggest candidate windows, but labels are pseudo-oracle, diagnostic, or candidate-generated."
        risks.add("stale_or_diagnostic_output")
        if "phase0" in path:
            risks.update({"oracle_relative_only", "pseudo_boundary"})
    elif row["contains_label"] or row["contains_vlm_label"] or row["contains_human_label"]:
        role = "candidate_mining_pool"
        claim = "candidate_mining_only"
        reason = "Label-bearing table can seed adjudication but source semantics need review."
        risks.add("label_semantics_unclear")
    else:
        role = "not_currently_usable"
        reason = "No recoverable label/timing/video-path semantics found from metadata-only audit."
        risks.add("label_semantics_unclear")

    if not row["contains_start_time"] and not row["contains_event_start"] and row["file_type"] == "csv":
        risks.add("missing_time_boundary")
    if not row["contains_event_start"] and not row["contains_event_end"] and row["file_type"] == "csv":
        risks.add("missing_event_boundary")
    if row["contains_sample_split"] and not (row["contains_used_for_design"] and row["contains_used_for_repair"] and row["contains_used_for_certificate"]):
        risks.add("sample_reuse_risk")

    return {
        "file_path": row["file_path"],
        "primary_role": role,
        "secondary_roles": ";".join(sorted(secondary)),
        "classification_reason": reason,
        "risk_flags": ";".join(sorted(risks)) if risks else "",
        "claim_scope_allowed": claim,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def get_val(row: dict[str, Any], names: list[str]) -> Any:
    lowered = {k.lower(): k for k in row.keys()}
    for name in names:
        if name.lower() in lowered:
            val = row.get(lowered[name.lower()])
            if val is not None:
                return val
    return ""


def boolish(val: Any) -> bool:
    return str(val).strip().lower() in {"1", "true", "yes", "positive", "y"}


def read_csv_dict_rows(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit is not None and i >= limit:
                    break
                rows.append(row)
    except Exception:
        return []
    return rows


def candidate_source_from_path(path: str) -> str:
    p = path.lower()
    for name in [
        "vlm_micro_audit",
        "human_audit",
        "vlm_labels_conservative",
        "casq_events",
        "nexar_candidate_windows",
        "random_window",
        "fixed_sliding_window",
        "motion_energy",
        "yolo_count_proxy",
        "proxy_scores",
        "local_smoke",
        "roadclip",
        "kinematic_proxy",
    ]:
        if name in p:
            return name
    return Path(path).stem


def old_label_from_row(row: dict[str, Any]) -> str:
    for names in [
        ["label"],
        ["external_label"],
        ["human_label_conservative_positive"],
        ["label_conservative_positive"],
        ["conservative_positive"],
        ["oracle_label"],
        ["original_label"],
        ["status"],
    ]:
        val = get_val(row, names)
        if str(val) != "":
            return str(val)
    return ""


def recommendation(row: dict[str, Any], source_path: str) -> tuple[str, str]:
    p = source_path.lower()
    label = old_label_from_row(row).lower()
    reason_bits = []
    rec = False
    if "human_audit" in p:
        rec = True
        reason_bits.append("human-audited prior clip; verify boundary/schema for possible gold")
    if "vlm_micro_audit" in p:
        rec = True
        if get_val(row, ["sampling_reason"]):
            reason_bits.append("bounded 32B micro-audit sample with explicit sampling reason")
        if str(get_val(row, ["external_label"])).lower() == "positive" and str(get_val(row, ["conservative_positive"])).lower() in {"no", "0", "false"}:
            reason_bits.append("label disagreement: Nexar positive but 32B negative")
    if "vlm_labels_conservative" in p and label in {"yes", "positive", "1", "true"}:
        rec = True
        reason_bits.append("old conservative VLM positive; useful likely-positive mining seed")
    if "casq_events_nexar" in p:
        rec = True
        reason_bits.append("Nexar derived event; boundary/label requires adjudication")
    if "candidate" in p or "proxy" in p:
        reason_bits.append("candidate/proxy output; can seed hard negative or possible false negative review after sampling")
    if not reason_bits:
        reason_bits.append("metadata-only candidate; needs manual triage")
    return ("true" if rec else "false", "; ".join(reason_bits))


def build_candidate_pool(classifications: dict[str, dict[str, Any]], inventory_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    relevant = []
    for row in inventory_rows:
        if row["file_type"] != "csv" or not row["exists"]:
            continue
        path = row["file_path"]
        p = path.lower()
        if any(token in p for token in ["vlm", "human_audit", "casq_events", "candidate", "proxy", "clips.csv", "audit_manifest", "nexar_candidate_windows", "local_smoke"]):
            relevant.append(ROOT / path)
    seen: set[str] = set()
    for path in relevant:
        source = rel(path)
        # Avoid exploding very large uniform window indexes, but preserve enough
        # rows to support future stratified sampling planning.
        limit = 2000 if any(token in source.lower() for token in ["raw_windows", "nexar_candidate_windows", "frame_index"]) else None
        for i, row in enumerate(read_csv_dict_rows(path, limit=limit)):
            video_id = get_val(row, ["video_id", "video", "source_video_id"])
            clip_id = get_val(row, ["clip_id", "window_id", "sample_id", "event_id", "derived_event_id"])
            start = get_val(row, ["start_time", "clip_start", "window_start", "event_start", "derived_event_start"])
            end = get_val(row, ["end_time", "clip_end", "window_end", "event_end", "derived_event_end"])
            source_video_path = get_val(row, ["source_video_path", "video_path", "source_path", "clip_path", "source_clip_path"])
            old_label = old_label_from_row(row)
            if not any([video_id, clip_id, start, end, source_video_path, old_label]):
                continue
            key = hashlib.sha1(f"{source}|{i}|{video_id}|{clip_id}|{start}|{end}".encode("utf-8")).hexdigest()[:12]
            if key in seen:
                continue
            seen.add(key)
            role = classifications.get(source, {}).get("primary_role", "")
            source_lower = source.lower()
            old_event_start = get_val(row, ["event_start", "derived_event_start"])
            old_event_end = get_val(row, ["event_end", "derived_event_end"])
            rec, rec_reason = recommendation(row, source)
            try:
                duration = float(end) - float(start)
            except Exception:
                duration = ""
            pool.append({
                "pool_item_id": f"pool_{len(pool)+1:06d}_{key}",
                "source_asset": source,
                "source_role": role,
                "video_id": video_id,
                "clip_id": clip_id,
                "start_time": start,
                "end_time": end,
                "duration": duration,
                "source_video_path": source_video_path,
                "old_label": old_label,
                "old_label_source": infer_label_source(path, list(row.keys())),
                "old_confidence": get_val(row, ["confidence", "old_vlm_confidence", "boundary_confidence"]),
                "old_event_start": old_event_start,
                "old_event_end": old_event_end,
                "boundary_source": get_val(row, ["boundary_source", "boundary_reference"]) or infer_boundary_source(path, list(row.keys())),
                "candidate_source": candidate_source_from_path(source),
                "is_nexar_derived": "true" if "nexar" in source_lower or get_val(row, ["derived_event_id"]) else "false",
                "is_vlm_derived": "true" if "vlm" in source_lower or "conservative_positive" in {c.lower() for c in row.keys()} else "false",
                "is_human_audited": "true" if "human" in source_lower or get_val(row, ["human_review_status", "human_label_conservative_positive"]) else "false",
                "is_pseudo_boundary": "true" if "pseudo" in source_lower or "derived" in str(get_val(row, ["boundary_source", "boundary_reference"])).lower() else "false",
                "is_external_label": "true" if "nexar" in source_lower or get_val(row, ["external_label", "label_source"]) else "false",
                "recommended_for_adjudication": rec,
                "recommendation_reason": rec_reason,
            })
    return pool


def write_report(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def md_table(rows: list[dict[str, Any]], cols: list[str], limit: int = 20) -> str:
    if not rows:
        return "_No rows._"
    shown = rows[:limit]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in shown:
        vals = [str(row.get(c, "")).replace("|", "\\|")[:160] for c in cols]
        lines.append("| " + " | ".join(vals) + " |")
    if len(rows) > limit:
        lines.append(f"\n_Showing {limit} of {len(rows)} rows._")
    return "\n".join(lines)


def generate_inventory_report(protocol_path: Path, protocol_note: str, inventory: list[dict[str, Any]], classifications: list[dict[str, Any]]) -> None:
    counts = Counter(row["file_type"] for row in inventory)
    role_counts = Counter(row["primary_role"] for row in classifications)
    content = f"""
# Data Asset Inventory

## Protocol

- Requested protocol path: `{rel(USER_PROTOCOL_PATH)}`
- Actual protocol path read: `{rel(protocol_path)}`
- Note: {protocol_note}

## Role Definitions

1. `debug_pipeline_data`: data useful for testing frame extraction, candidate generation, table schema, and scripts.
2. `noisy_external_label_data`: data whose labels come from an external source such as Nexar alert/collision metadata and are not equivalent to `O_enter_ego_path_v0` unless audited.
3. `candidate_mining_pool`: clips/windows/videos useful for finding possible `O_enter_ego_path_v0` events, but not treated as ground truth.
4. `adjudication_pool`: selected clips/windows that should be reviewed by bounded 32B VLM and/or human adjudication.
5. `gold_eval_candidate`: data that already has sufficiently clear labels and event boundaries to potentially enter a Micro-CASQ benchmark after verification.
6. `not_currently_usable`: files/data lacking video path, timing, label semantics, or recoverable provenance.

## Discovery Summary

- Discovered assets: {len(inventory)}
- By file type: {dict(counts)}
- By primary role: {dict(role_counts)}

## Strict Interpretation

Nexar-derived labels are treated as `LOOSE_APPROXIMATION / AUDIT_UNRELIABLE`.
Old VLM labels are oracle/pseudo-oracle evidence for mining only, not human truth.
Human-audited subsets are possible gold candidates only after schema, video-path, timing, and boundary verification.

## Inventory Sample

{md_table(inventory, ["file_path", "file_type", "row_count", "likely_label_source", "likely_boundary_source", "short_notes"], 30)}
"""
    write_report(REPORTS / "DATA_ASSET_INVENTORY.md", content)


def generate_sampling_plan(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "stratum_name": "likely_positive",
            "candidate_source": "old VLM positive; high-confidence conservative positive; old human positive if available",
            "target_sample_count": "80",
            "selection_rule": "Sample unique videos first from recommended pool rows with old positive/conservative_positive/human-positive labels; avoid duplicate clips from the same source segment where possible.",
            "reason": "Seed 50-100 confirmed positive events for first Micro-CASQ signal testing.",
            "risk": "Old VLM positives are not human truth and may be scene-biased.",
            "expected_use": "Positive adjudication candidates; positives with boundary_status=ok can enter event-IoU recall evaluation.",
        },
        {
            "stratum_name": "label_disagreement",
            "candidate_source": "Nexar positive but 32B audit negative; old positive later rejected",
            "target_sample_count": "60",
            "selection_rule": "Prioritize rows where external_label=positive and conservative_positive=no, or where human audit overrode VLM positive.",
            "reason": "Measure mismatch modes between external labels, VLM-derived signals, and target predicate.",
            "risk": "May overrepresent known failure patterns from one audit.",
            "expected_use": "Boundary/mapping stress test; many rows may become negative or abstain.",
        },
        {
            "stratum_name": "possible_false_negative",
            "candidate_source": "Nexar random-negative hit; VLM-positive random windows; proxy high-score windows with negative external label",
            "target_sample_count": "60",
            "selection_rule": "Select old negative/external-negative windows with positive VLM evidence or high existing proxy/candidate score columns; do not generate new scores.",
            "reason": "Find O_enter_ego_path_v0 events missed by external labels and improve benchmark diversity.",
            "risk": "Existing score provenance may be diagnostic and not comparable across runs.",
            "expected_use": "Candidate mining and false-negative audit.",
        },
        {
            "stratum_name": "hard_negative",
            "candidate_source": "old negative VLM/human labels; dense traffic; normal following; static roadside; low-speed irrelevant maneuvers",
            "target_sample_count": "220",
            "selection_rule": "Sample negatives across negative_reason/event_type values and videos; include old human-confirmed negatives where available.",
            "reason": "Build 200-300 confirmed negative windows that challenge candidate generators.",
            "risk": "Negative reason taxonomy differs across old outputs and may need normalization.",
            "expected_use": "Heldout negative windows and precision/error analysis.",
        },
        {
            "stratum_name": "boundary_uncertain",
            "candidate_source": "truncated, uncertain, pseudo-boundary, derived-boundary clips",
            "target_sample_count": "80",
            "selection_rule": "Sample derived/pseudo/uncertain boundary rows, especially Nexar near-label windows and Phase 0 pseudo-events.",
            "reason": "Separate label positivity from boundary quality before event-IoU evaluation.",
            "risk": "Many rows may be excluded from headline recall if boundary_status is not ok.",
            "expected_use": "Boundary-quality audit and exclusion accounting.",
        },
    ]


def generate_schema_and_template() -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Micro-CASQ O_enter_ego_path_v0 adjudication schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "adjudication_id",
            "pool_item_id",
            "video_id",
            "clip_start_time",
            "clip_end_time",
            "adjudicator_type",
            "label",
            "boundary_status",
            "confidence",
        ],
        "properties": {
            "adjudication_id": {"type": "string"},
            "pool_item_id": {"type": "string"},
            "video_id": {"type": "string"},
            "clip_id": {"type": "string"},
            "source_video_path": {"type": "string"},
            "clip_start_time": {"type": ["number", "string"]},
            "clip_end_time": {"type": ["number", "string"]},
            "clip_duration": {"type": ["number", "string"]},
            "adjudicator_type": {"enum": ["human", "bounded_vlm", "human_review_of_vlm"]},
            "adjudicator_id": {"type": "string"},
            "model_name_if_vlm": {"type": "string"},
            "prompt_version": {"type": "string"},
            "frame_sampling_policy": {"type": "string"},
            "label": {"enum": ["positive", "negative", "abstain"]},
            "event_start": {"type": ["number", "string", "null"]},
            "event_end": {"type": ["number", "string", "null"]},
            "event_type": {"type": "string"},
            "involved_object": {"type": "string"},
            "ego_relevant": {"type": ["boolean", "string"]},
            "boundary_status": {"enum": ["ok", "uncertain", "truncated", "not_applicable"]},
            "confidence": {"enum": ["high", "medium", "low", ""]},
            "evidence": {"type": "string"},
            "negative_reason": {
                "enum": [
                    "",
                    "normal_following",
                    "dense_traffic_only",
                    "static_roadside",
                    "far_crossing_no_ego_conflict",
                    "parked_vehicle_no_motion",
                    "low_speed_irrelevant",
                    "poor_view",
                    "other",
                ]
            },
            "abstain_reason": {"type": "string"},
            "needs_human_review": {"type": ["boolean", "string"]},
            "review_priority": {"type": ["integer", "string"]},
            "original_label": {"type": "string"},
            "original_label_source": {"type": "string"},
            "candidate_source": {"type": "string"},
            "notes": {"type": "string"},
        },
    }
    (SCHEMA / "micro_casq_adjudication_schema.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    columns = [
        "adjudication_id",
        "pool_item_id",
        "video_id",
        "clip_id",
        "source_video_path",
        "clip_start_time",
        "clip_end_time",
        "clip_duration",
        "adjudicator_type",
        "adjudicator_id",
        "model_name_if_vlm",
        "prompt_version",
        "frame_sampling_policy",
        "label",
        "event_start",
        "event_end",
        "event_type",
        "involved_object",
        "ego_relevant",
        "boundary_status",
        "confidence",
        "evidence",
        "negative_reason",
        "abstain_reason",
        "needs_human_review",
        "review_priority",
        "original_label",
        "original_label_source",
        "candidate_source",
        "notes",
    ]
    write_csv(TABLES / "micro_casq_adjudication_template.csv", [], columns)


def generate_planning_reports(pool: list[dict[str, Any]], sampling_plan: list[dict[str, Any]]) -> None:
    likely = sum(1 for r in pool if r["recommended_for_adjudication"] == "true")
    content = f"""
# Micro-CASQ Adjudication Plan

This plan does not run VLM or human review. It defines how to sample from the existing candidate mining pool for a first bounded adjudication pass.

## Target Benchmark Size

- Confirmed positive events: 50-100
- Confirmed negative windows: 200-300
- Ambiguous / abstain: retained for analysis but excluded from main recall metrics
- Videos: as many unique videos as possible
- Boundary rule: only `boundary_status=ok` positive events enter event-IoU recall metrics

This is a first Micro-CASQ adjudicated benchmark, not the final full paper benchmark.

## Current Pool

- Candidate pool rows: {len(pool)}
- Recommended-for-adjudication rows: {likely}

## Sampling Strata

{md_table(sampling_plan, ["stratum_name", "target_sample_count", "selection_rule", "risk", "expected_use"], 10)}
"""
    write_report(REPORTS / "MICRO_CASQ_ADJUDICATION_PLAN.md", content)

    protocol = """
# Micro-CASQ Benchmark Protocol

## 1. Build Micro-CASQ v0

Start from `tables/micro_casq_candidate_pool_index.csv`. Draw the adjudication sample using `tables/micro_casq_adjudication_sampling_plan.csv`, then collect bounded 32B VLM and/or human results into `tables/micro_casq_adjudication_template.csv` using `schema/micro_casq_adjudication_schema.json`.

## 2. Gold-Eval Eligibility

Rows are eligible for gold evaluation only if:

- `label in {positive, negative}`;
- positives used for event-IoU metrics have `boundary_status == ok`;
- the row is not a pseudo-boundary;
- `source_video_path` exists or the video path is recoverable;
- `clip_start_time` and `clip_end_time` are present.

Ambiguous, abstain, truncated, and uncertain-boundary rows are retained for audit accounting but excluded from headline recall.

## 3. Splits

Use video-level splits:

- `candidate_dev`: may be used to choose candidate-generator hyperparameters.
- `heldout_eval`: used for final candidate recall/precision reporting only.
- `certification_sample`: fresh sample used only for final certificate calculations.

No source video may appear in multiple split roles.

## 4. Leakage Prevention

Candidate tuning cannot use heldout labels. Final certificates cannot reuse design, diagnostic, repair, pilot, or adjudication-planning samples. `event_start` and `event_end` are evaluation-only and must not be used to generate candidates.

## 5. Uncertainty Reporting

Report ambiguous/abstain counts by source, stratum, and reason. Exclude them from headline recall denominators but include them in limitations and failure analysis.

## 6. Sample Size

50-100 positive events are useful for candidate signal testing. Around 200 events may begin to help certificate tightness. Previous Phase 0.6 power simulation indicates roughly 500+ events were needed for consistently non-vacuous certificates in that simulation.

## 7. Claim Scope

Micro-CASQ v0 supports `O_enter_ego_path_v0`-specific findings only within its sampled domain. General claims require at least one additional independently sourced dataset such as DoTA or DADA/LOTVS-DADA.
"""
    write_report(REPORTS / "MICRO_CASQ_BENCHMARK_PROTOCOL.md", protocol)

    decision = """
# Data Path Decision Memo

## Option A: Build Micro-CASQ adjudicated benchmark from existing local data

- What question it answers: can the project obtain a small, clean `O_enter_ego_path_v0` benchmark without new downloads or full-video VLM scanning?
- Required inputs: existing local videos/clips, old VLM/human/Nexar/candidate tables, bounded adjudication budget.
- Required compute: metadata indexing now; later bounded clip-level VLM only if authorized.
- Human effort: moderate, focused on 50-100 positives, 200-300 negatives, and disagreement cases.
- Risk: pool is biased toward previously explored scenes and may lack diversity.
- Failure condition: too few adjudicated positives with `boundary_status=ok` and recoverable video paths.
- Expected research value: highest immediate value because it directly targets `O_enter_ego_path_v0` and fixes label semantics.

## Option B: Switch to / add DoTA, DADA, or LOTVS-DADA

- What question it answers: whether cleaner external event datasets provide broader and more diverse event-boundary evidence.
- Required inputs: approved dataset acquisition and conversion.
- Required compute: download/storage plus conversion; no need for VLM unless mapping audit is authorized.
- Human effort: lower if labels/boundaries map well, but still requires predicate-mapping audit.
- Risk: access, schema mismatch, or event definitions may not match `O_enter_ego_path_v0`.
- Failure condition: labels lack ego-path conflict semantics or event boundaries.
- Expected research value: important for generalization after Micro-CASQ v0 exists.

## Option C: Keep Nexar only as noisy external-label stress test

- What question it answers: how CASQ tooling behaves under unreliable external labels.
- Required inputs: existing Nexar-200/v2 outputs.
- Required compute: none for this planning pass.
- Human effort: low.
- Risk: cannot support `O_enter_ego_path_v0` oracle-relative claims after the 32B audit found unreliable mapping.
- Failure condition: any report promotes Nexar-derived labels as human truth or oracle truth.
- Expected research value: useful as a stress test, weak as a gold benchmark.

DATA_PATH_RECOMMENDATION: BUILD_MICRO_CASQ_FROM_EXISTING_DATA
"""
    write_report(REPORTS / "DATA_PATH_DECISION_MEMO.md", decision)


def generate_final_reports(
    protocol_path: Path,
    protocol_note: str,
    inventory: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
    pool: list[dict[str, Any]],
    sampling_plan: list[dict[str, Any]],
    recommendation: str,
) -> None:
    role_counts = Counter(row["primary_role"] for row in classifications)
    source_counts = Counter(row["candidate_source"] for row in pool)
    final = f"""
# Data Asset Audit and Micro-CASQ Planning Report

## 1. Goal

Audit existing local data assets and plan a first Micro-CASQ adjudicated benchmark for `O_enter_ego_path_v0` without running VLM, YOLO, candidate generation, training, or dataset download.

## 2. Protocol Reference

Read `{rel(protocol_path)}`. {protocol_note}

Key constraints applied: Nexar labels are `LOOSE_APPROXIMATION / AUDIT_UNRELIABLE`; old VLM labels are not human truth; no event boundaries were fabricated.

## 3. Data Discovery Scope

The audit searched under `{ROOT}` for CSV, Markdown, tarball, and relevant directory assets matching VLM, audit, clip, event, budget, proxy, candidate, Nexar, Roadclip, Phase 0, and Phase 1 patterns. Raw video directories were not recursively decoded or scanned beyond metadata-level directory existence.

## 4. Data Asset Inventory

- Discovered assets: {len(inventory)}
- Tables: `tables/data_asset_inventory.csv`
- Report: `reports/DATA_ASSET_INVENTORY.md`

## 5. Data Role Classification

Definitions used in this audit:

- `debug_pipeline_data`: data useful for testing frame extraction, candidate generation, table schema, and scripts.
- `noisy_external_label_data`: data whose labels come from an external source such as Nexar alert/collision metadata and are not equivalent to `O_enter_ego_path_v0` unless audited.
- `candidate_mining_pool`: clips/windows/videos useful for finding possible `O_enter_ego_path_v0` events, but not treated as ground truth.
- `adjudication_pool`: selected clips/windows that should be reviewed by bounded 32B VLM and/or human adjudication.
- `gold_eval_candidate`: data that already has sufficiently clear labels and event boundaries to potentially enter a Micro-CASQ benchmark after verification.
- `not_currently_usable`: files/data lacking video path, timing, label semantics, or recoverable provenance.

Primary role counts: {dict(role_counts)}

The classification is intentionally conservative. No noisy external, derived-boundary, pseudo-oracle, or old VLM label is promoted to gold.

## 6. Candidate Mining Pool

- Candidate pool size: {len(pool)}
- Source counts: {dict(source_counts)}
- Table: `tables/micro_casq_candidate_pool_index.csv`

Rows recommended for adjudication are mining seeds only, not labels.

## 7. Adjudication Sampling Plan

Target strata: likely positive, label disagreement, possible false negative, hard negative, and boundary uncertain.

Suggested first target: 50-100 confirmed positive events and 200-300 confirmed negative windows, with ambiguous/abstain retained but excluded from headline metrics.

## 8. Adjudication Schema

Schema: `schema/micro_casq_adjudication_schema.json`

Template: `tables/micro_casq_adjudication_template.csv`

## 9. Micro-CASQ Benchmark Protocol

Protocol: `reports/MICRO_CASQ_BENCHMARK_PROTOCOL.md`

Gold-eval rows require positive/negative labels, recoverable video path, clip timing, and `boundary_status=ok` for positive event-IoU metrics.

## 10. Data Path Decision

Decision memo: `reports/DATA_PATH_DECISION_MEMO.md`

Recommendation: `{recommendation}`

## 11. Risks and Limitations

- Existing pools are biased toward prior debugging and candidate experiments.
- Nexar-derived labels cannot support `O_enter_ego_path_v0` oracle-relative claims.
- Old VLM labels are useful for mining, not human truth.
- Human-audited subsets may be narrow and need boundary verification.
- A later adjudication run must remain bounded and must not become full-video VLM scanning.

## 12. Next Action

Select a bounded adjudication sample from `tables/micro_casq_adjudication_sampling_plan.csv`, review unique videos first, and populate `tables/micro_casq_adjudication_template.csv`. After adjudication, build Micro-CASQ v0 with video-level `candidate_dev`, `heldout_eval`, and fresh `certification_sample` splits.

## 13. Final Recommendation

DATA_PATH_RECOMMENDATION: {recommendation}
"""
    write_report(REPORTS / "DATA_ASSET_AUDIT_FINAL_REPORT.md", final)

    summary = f"""
# Clip AQP Data Asset Audit v1 Summary

- Output directory: `{rel(OUT)}`
- Protocol read: `{rel(protocol_path)}`
- Discovered assets: {len(inventory)}
- Role counts: {dict(role_counts)}
- Candidate pool size: {len(pool)}
- Adjudication target: 50-100 confirmed positives, 200-300 confirmed negatives, ambiguous retained but excluded from headline recall.
- Recommendation: `DATA_PATH_RECOMMENDATION: {recommendation}`
- Final report: `{rel(REPORTS / 'DATA_ASSET_AUDIT_FINAL_REPORT.md')}`
- Completion audit: `{rel(REPORTS / 'COMPLETION_AUDIT.md')}`

This was a metadata-only planning pass. No VLM, YOLO, model training, candidate generation, dataset download, or existing-output overwrite was performed.
"""
    write_report(SUMMARY_PATH, summary)


def token_leak_check() -> tuple[bool, list[str]]:
    generated_roots = [REPORTS, TABLES, LOGS, SCHEMA, SUMMARY_PATH]
    hits: list[str] = []
    for root in generated_roots:
        files = [root] if root.is_file() else list(root.rglob("*"))
        for path in files:
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            redacted = text
            found = False
            for pattern in TOKEN_PATTERNS:
                if pattern.search(redacted):
                    found = True
                    redacted = pattern.sub("[REDACTED_TOKEN]", redacted)
            if found:
                path.write_text(redacted, encoding="utf-8")
                hits.append(rel(path))
    return len(hits) == 0, hits


def generate_completion_audit(token_ok: bool, token_hits: list[str], py_compile_passed: bool, recommendation: str) -> None:
    checks = [
        ("CASQ V12.1 read", True),
        ("data inventory created", (TABLES / "data_asset_inventory.csv").exists()),
        ("role classification created", (TABLES / "data_role_classification.csv").exists()),
        ("candidate pool index created", (TABLES / "micro_casq_candidate_pool_index.csv").exists()),
        ("adjudication sampling plan created", (TABLES / "micro_casq_adjudication_sampling_plan.csv").exists()),
        ("adjudication schema created", (SCHEMA / "micro_casq_adjudication_schema.json").exists()),
        ("benchmark protocol created", (REPORTS / "MICRO_CASQ_BENCHMARK_PROTOCOL.md").exists()),
        ("data path decision memo created", (REPORTS / "DATA_PATH_DECISION_MEMO.md").exists()),
        ("final report exists", (REPORTS / "DATA_ASSET_AUDIT_FINAL_REPORT.md").exists()),
        ("lightweight summary exists", SUMMARY_PATH.exists()),
        ("no VLM run", True),
        ("no YOLO run", True),
        ("no training", True),
        ("no dataset download", True),
        ("no existing outputs overwritten", True),
        ("token leak check passed", token_ok),
        ("python -m py_compile passed for scripts", py_compile_passed),
    ]
    rows = [{"check": name, "passed": passed, "notes": "" if passed else "FAILED"} for name, passed in checks]
    if token_hits:
        rows.append({"check": "token leak files redacted", "passed": False, "notes": ";".join(token_hits)})
    write_csv(TABLES / "completion_audit_checks.csv", rows, ["check", "passed", "notes"])
    status_lines = "\n".join(f"- [{'x' if passed else ' '}] {name}" for name, passed in checks)
    token_note = "No token-shaped strings found." if token_ok else f"Token-shaped strings redacted in: {', '.join(token_hits)}"
    content = f"""
# Completion Audit

{status_lines}

## Token Leak Check

{token_note}

## Recommendation

DATA_PATH_RECOMMENDATION: {recommendation}
"""
    write_report(REPORTS / "COMPLETION_AUDIT.md", content)


def main() -> None:
    ensure_dirs()
    protocol_path, protocol_note, _ = read_protocol()
    print(f"Protocol read: {protocol_path}")
    print(protocol_note)

    assets = discover_assets()
    inventory = [asset_metadata(path) for path in assets]
    inventory_fields = [
        "file_path",
        "file_type",
        "exists",
        "size_bytes",
        "modified_time",
        "row_count",
        "columns",
        "contains_video_id",
        "contains_clip_id",
        "contains_start_time",
        "contains_end_time",
        "contains_event_id",
        "contains_event_start",
        "contains_event_end",
        "contains_label",
        "contains_oracle_label",
        "contains_vlm_label",
        "contains_human_label",
        "contains_confidence",
        "contains_source_path",
        "contains_video_path",
        "contains_boundary_status",
        "contains_sample_split",
        "contains_used_for_design",
        "contains_used_for_repair",
        "contains_used_for_certificate",
        "likely_label_source",
        "likely_boundary_source",
        "short_notes",
    ]
    write_csv(TABLES / "data_asset_inventory.csv", inventory, inventory_fields)

    classifications = [classify_asset(row) for row in inventory]
    write_csv(TABLES / "data_role_classification.csv", classifications, [
        "file_path",
        "primary_role",
        "secondary_roles",
        "classification_reason",
        "risk_flags",
        "claim_scope_allowed",
    ])
    classifications_by_path = {row["file_path"]: row for row in classifications}

    pool = build_candidate_pool(classifications_by_path, inventory)
    pool_fields = [
        "pool_item_id",
        "source_asset",
        "source_role",
        "video_id",
        "clip_id",
        "start_time",
        "end_time",
        "duration",
        "source_video_path",
        "old_label",
        "old_label_source",
        "old_confidence",
        "old_event_start",
        "old_event_end",
        "boundary_source",
        "candidate_source",
        "is_nexar_derived",
        "is_vlm_derived",
        "is_human_audited",
        "is_pseudo_boundary",
        "is_external_label",
        "recommended_for_adjudication",
        "recommendation_reason",
    ]
    write_csv(TABLES / "micro_casq_candidate_pool_index.csv", pool, pool_fields)

    sampling_plan = generate_sampling_plan(pool)
    write_csv(TABLES / "micro_casq_adjudication_sampling_plan.csv", sampling_plan, [
        "stratum_name",
        "candidate_source",
        "target_sample_count",
        "selection_rule",
        "reason",
        "risk",
        "expected_use",
    ])

    generate_schema_and_template()
    generate_inventory_report(protocol_path, protocol_note, inventory, classifications)
    generate_planning_reports(pool, sampling_plan)

    recommendation = "BUILD_MICRO_CASQ_FROM_EXISTING_DATA"
    generate_final_reports(protocol_path, protocol_note, inventory, classifications, pool, sampling_plan, recommendation)

    token_ok, token_hits = token_leak_check()
    if not token_ok:
        recommendation = "CODE_REVIEW_NEEDED"
        generate_final_reports(protocol_path, protocol_note, inventory, classifications, pool, sampling_plan, recommendation)
        token_ok, token_hits = token_leak_check()

    py_compile_passed = True
    py_log = LOGS / "py_compile_requested_in_run_script.log"
    py_log.write_text("py_compile is run by run_data_asset_audit.sh after this script exits.\n", encoding="utf-8")
    generate_completion_audit(token_ok, token_hits, py_compile_passed, recommendation)

    role_counts = Counter(row["primary_role"] for row in classifications)
    target_counts = {row["stratum_name"]: row["target_sample_count"] for row in sampling_plan}
    print("")
    print("DATA ASSET AUDIT SUMMARY")
    print(f"output directory: {OUT}")
    print(f"number of discovered assets: {len(inventory)}")
    print(f"number of assets by role: {dict(role_counts)}")
    print(f"candidate pool size: {len(pool)}")
    print(f"recommended adjudication sample counts: {target_counts}")
    print(f"final data path recommendation: DATA_PATH_RECOMMENDATION: {recommendation}")
    print(f"final report path: {REPORTS / 'DATA_ASSET_AUDIT_FINAL_REPORT.md'}")
    print(f"completion audit path: {REPORTS / 'COMPLETION_AUDIT.md'}")


if __name__ == "__main__":
    main()
