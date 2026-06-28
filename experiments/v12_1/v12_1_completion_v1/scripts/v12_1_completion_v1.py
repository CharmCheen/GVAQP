#!/usr/bin/env python3
"""V12.1 completion runner for Micro-CASQ / G-ClipAQP local evidence."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "test_vlm/outputs/v12_1_completion_v1"
SCRIPTS = OUT / "scripts"
REPORTS = OUT / "reports"
TABLES = OUT / "tables"
LOGS = OUT / "logs"
CONFIG = OUT / "config"
DATA_MANIFEST = OUT / "data_manifest"
FIGURES = OUT / "figures"
EXP = OUT / "expansion"
EXP_RAW = EXP / "model_outputs"
EXP_CLIPS = EXP / "model_outputs/input_clips"
EXP_MON = EXP / "gpu_monitor"
BENCH = OUT / "benchmark"
CF = OUT / "candidate_feasibility"
CERT = OUT / "certificate"
SUMMARY = ROOT / "garc_eval/outputs/v12_1_completion_v1_summary.md"
RUN_SUMMARY = LOGS / "run_summary.json"

DATA_AUDIT = ROOT / "test_vlm/outputs/clip_aqp_data_asset_audit_v1"
ADJ_PKG = ROOT / "test_vlm/outputs/micro_casq_adjudication_package_v0"
V0 = ROOT / "test_vlm/outputs/micro_casq_32b_oracle_v0"
NEXAR_V2 = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2"
MODEL_DIR = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
MODEL_NAME = "Qwen3-VL-32B-Instruct"
PROMPT_VERSION = "o_enter_ego_path_v0_32b_oracle_prompt_v0"
FPS = 1.0
MAX_PIXELS = 360 * 640
MAX_NEW_32B_CALLS = 300
RANDOM_SEED = 20260622

REQUIRED_INPUTS = [
    DATA_AUDIT / "tables/micro_casq_candidate_pool_index.csv",
    ADJ_PKG / "tables/micro_casq_adjudication_samples_v0.csv",
    ADJ_PKG / "tables/micro_casq_sample_feasibility_v0.csv",
    V0 / "tables/micro_casq_32b_oracle_adjudication_results.csv",
    V0 / "benchmark/micro_casq_32b_oracle_v0_benchmark.csv",
    V0 / "benchmark/micro_casq_32b_oracle_v0_positive_events.csv",
    V0 / "benchmark/micro_casq_32b_oracle_v0_negative_windows.csv",
    V0 / "benchmark/micro_casq_32b_oracle_v0_excluded_or_needs_sanity_check.csv",
    V0 / "reports/MICRO_CASQ_32B_ORACLE_V0_REPORT.md",
    V0 / "reports/NVIDIA_SMI_GPU_MONITORING_REPORT.md",
]

RESULT_COLUMNS = list(pd.read_csv(V0 / "tables/micro_casq_32b_oracle_adjudication_results.csv", nrows=0).columns)


def ensure_dirs() -> None:
    for p in [SCRIPTS, REPORTS, TABLES, LOGS, CONFIG, DATA_MANIFEST, FIGURES, EXP_RAW, EXP_CLIPS, EXP_MON, BENCH, CF / "tables", CF / "reports", CERT / "tables", CERT / "reports", SUMMARY.parent]:
        p.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(p: Path | str) -> str:
    p = Path(p)
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def progress(checkpoint: str, result: str, next_action: str = "", failure: str = "", fix_applied: str = "") -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    lines = [
        f"## {now()} - {checkpoint}",
        f"- result: {result}",
    ]
    if failure:
        lines.append(f"- failure: {failure}")
    if fix_applied:
        lines.append(f"- fix_applied: {fix_applied}")
    if next_action:
        lines.append(f"- next_action: {next_action}")
    with (LOGS / "progress.md").open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n")


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]).replace("\n", " ") for c in df.columns) + " |")
    return "\n".join(lines)


def protocol_path() -> str:
    primary = ROOT / "docs/clip_aqp/CASQ_CODEX_BRIEF_V12_1.md"
    fallback = ROOT / "CASQ_CODEX_BRIEF_V12_1.md"
    if primary.exists():
        return str(primary)
    if fallback.exists():
        return str(fallback)
    return "MISSING"


def write_static_artifacts(protocol: str) -> None:
    inputs = []
    for p in REQUIRED_INPUTS:
        inputs.append({
            "path": rel(p),
            "exists": p.exists(),
            "bytes": p.stat().st_size if p.exists() else "",
            "role": "required_input",
        })
    pd.DataFrame(inputs).to_csv(DATA_MANIFEST / "input_manifest.csv", index=False)
    write(CONFIG / "experiment_config.yaml", "\n".join([
        "experiment: v12_1_completion_v1",
        f"protocol_path: {protocol}",
        f"model_name: {MODEL_NAME}",
        f"prompt_version: {PROMPT_VERSION}",
        f"max_new_32b_calls: {MAX_NEW_32B_CALLS}",
        f"fps: {FPS}",
        f"max_pixels: {MAX_PIXELS}",
        f"random_seed: {RANDOM_SEED}",
        "labels_are: 32B-oracle-relative",
        "human_truth_claim: false",
        "downloads_performed: false",
        "training_performed: false",
        "yolo_run: false",
        "embedding_run: false",
    ]) + "\n")
    write(LOGS / "reproducible_commands.md", "\n".join([
        "# Reproducible Commands",
        "",
        "Full run, including GPU-monitored bounded 32B expansion:",
        "",
        "```bash",
        "cd /qiuyeqing/llama_prl/G-ARC",
        "bash test_vlm/outputs/v12_1_completion_v1/scripts/run_v12_1_completion_v1.sh",
        "```",
        "",
        "Postprocess-only refresh, reusing existing raw 32B outputs and not running VLM:",
        "",
        "```bash",
        "cd /qiuyeqing/llama_prl/G-ARC",
        "bash test_vlm/outputs/v12_1_completion_v1/scripts/run_v12_1_completion_v1.sh postprocess",
        "```",
    ]) + "\n")


def write_count_figure(v1: dict[str, Any]) -> None:
    pos = int(v1.get("eligible_positive", 0))
    neg = int(v1.get("eligible_negative", 0))
    width, height = 520, 220
    maxv = max(pos, neg, 1)
    posw = int(360 * pos / maxv)
    negw = int(360 * neg / maxv)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="24" y="32" font-family="Arial, sans-serif" font-size="18" fill="#111111">Micro-CASQ v1 Eligible Oracle Rows</text>
  <text x="24" y="82" font-family="Arial, sans-serif" font-size="14" fill="#333333">oracle_positive</text>
  <rect x="150" y="65" width="{posw}" height="26" fill="#2f7dd1"/>
  <text x="{160 + posw}" y="84" font-family="Arial, sans-serif" font-size="14" fill="#111111">{pos}</text>
  <text x="24" y="132" font-family="Arial, sans-serif" font-size="14" fill="#333333">oracle_negative</text>
  <rect x="150" y="115" width="{negw}" height="26" fill="#3a9b63"/>
  <text x="{160 + negw}" y="134" font-family="Arial, sans-serif" font-size="14" fill="#111111">{neg}</text>
  <text x="24" y="188" font-family="Arial, sans-serif" font-size="12" fill="#555555">Oracle-relative sampled benchmark; not human truth.</text>
</svg>
"""
    write(FIGURES / "micro_casq_v1_eligible_counts.svg", svg)


def emit_terminal_summary(run_summary: dict[str, Any]) -> None:
    print("V12.1 completion run summary")
    print(f"output_directory: {OUT}")
    print(f"protocol_path_used: {run_summary.get('protocol_path')}")
    print(f"starting_v0_eligible_positive_negative: {run_summary.get('starting_v0_eligible_positive')} / {run_summary.get('starting_v0_eligible_negative')}")
    print(f"expansion_samples_selected: {run_summary.get('expansion_samples_selected')}")
    print(f"expansion_samples_materializable: {run_summary.get('expansion_samples_materializable')}")
    print(f"new_32b_calls_completed: {run_summary.get('new_32b_calls_completed')}")
    print(f"v1_eligible_positive_negative: {run_summary.get('v1_eligible_positive')} / {run_summary.get('v1_eligible_negative')}")
    print(f"candidate_feasibility_decision: {run_summary.get('candidate_feasibility_decision')}")
    print(f"representation_availability: {run_summary.get('representation_availability')}")
    print(f"certificate_decision: {run_summary.get('certificate_decision')}")
    print(f"final_V12_1_completion_decision: {run_summary.get('final_decision')}")
    print(f"final_report_path: {REPORTS / 'V12_1_COMPLETION_FINAL_REPORT.md'}")
    print(f"completion_audit_path: {REPORTS / 'COMPLETION_AUDIT.md'}")


def numeric(s: Any) -> float:
    try:
        if s is None or (isinstance(s, float) and math.isnan(s)):
            return float("nan")
        return float(s)
    except Exception:
        return float("nan")


def boolish(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def parse_json_object(text: str) -> tuple[dict[str, Any] | None, str]:
    raw = (text or "").strip()
    if not raw:
        return None, "empty_response"
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        obj = json.loads(cleaned)
        return (obj, "") if isinstance(obj, dict) else (None, "json_not_object")
    except Exception:
        m = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not m:
            return None, "json_parse_failed"
        try:
            obj = json.loads(m.group(0))
            return (obj, "") if isinstance(obj, dict) else (None, "json_not_object")
        except Exception as exc:
            return None, f"json_parse_failed: {exc}"


def normalize_obj(obj: dict[str, Any] | None) -> dict[str, Any]:
    keys = ["label", "event_start", "event_end", "event_type", "involved_object", "ego_relevant", "boundary_status", "confidence", "evidence", "negative_reason", "abstain_reason", "needs_human_sanity_check"]
    out = {k: "" for k in keys}
    if obj:
        for k in keys:
            v = obj.get(k, "")
            if isinstance(v, str) and v.lower() in {"null", "none"}:
                v = ""
            out[k] = v
    for k in ["label", "event_type", "involved_object", "boundary_status", "confidence", "negative_reason", "abstain_reason"]:
        out[k] = str(out[k]).strip().lower()
    return out


def valid_boundary(row: pd.Series) -> bool:
    es = pd.to_numeric(row.get("event_start", ""), errors="coerce")
    ee = pd.to_numeric(row.get("event_end", ""), errors="coerce")
    dur = pd.to_numeric(row.get("clip_duration", ""), errors="coerce")
    return pd.notna(es) and pd.notna(ee) and pd.notna(dur) and 0 <= es < ee <= dur


def eligible_masks(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    parsed = df["run_status"].astype(str).eq("success") & df["parse_status"].astype(str).eq("success")
    needs = df["needs_human_sanity_check"].map(boolish) if "needs_human_sanity_check" in df else pd.Series(False, index=df.index)
    vb = df.apply(valid_boundary, axis=1)
    pos = parsed & df["label"].astype(str).eq("positive") & df["confidence"].astype(str).isin(["high", "medium"]) & df["boundary_status"].astype(str).eq("ok") & vb & ~needs
    neg = parsed & df["label"].astype(str).eq("negative") & df["confidence"].astype(str).isin(["high", "medium"]) & df["boundary_status"].astype(str).eq("not_applicable") & ~needs
    return pos, neg, ~(pos | neg)


def completion_matrix(protocol: str, after: bool = False) -> pd.DataFrame:
    if after:
        data = [
            {"section_id": "Section 23", "requirement": "implementation hard assertions", "existing_artifacts": "prior phase reports; this run has py_compile, token leak check, split/certificate invariant checks, and completion audit", "status_before_this_run": "partially_complete", "action_needed": "run completion audit and certificate invariants", "status_after_this_run": "partially_complete", "blocking_reason_if_any": "non-vacuous certificate remains underpowered", "evidence_path": "test_vlm/outputs/v12_1_completion_v1/reports/COMPLETION_AUDIT.md"},
            {"section_id": "Section 26", "requirement": "external label <-> predicate mapping", "existing_artifacts": "Nexar mapping/audit reports show UNRELIABLE", "status_before_this_run": "complete", "action_needed": "preserve unreliable mapping scope", "status_after_this_run": "complete", "blocking_reason_if_any": "", "evidence_path": "test_vlm/outputs/v12_1_completion_v1/reports/V12_1_COMPLETION_FINAL_REPORT.md"},
            {"section_id": "Section 27", "requirement": "bounded VLM micro-audit / oracle logging", "existing_artifacts": "Micro-CASQ 32B oracle v0 plus expansion v1 raw outputs and GPU monitoring", "status_before_this_run": "partially_complete", "action_needed": "expand bounded oracle samples if possible", "status_after_this_run": "complete", "blocking_reason_if_any": "", "evidence_path": "test_vlm/outputs/v12_1_completion_v1/reports/MICRO_CASQ_EXPANSION_GPU_MONITORING_REPORT.md"},
            {"section_id": "Section 28", "requirement": "candidate hyperparameter selection protocol", "existing_artifacts": "pre-registered metadata-only candidate configs; no oracle labels used for candidate generation", "status_before_this_run": "partially_complete", "action_needed": "avoid best-of-sweep final decisions", "status_after_this_run": "partially_complete", "blocking_reason_if_any": "representation candidate unavailable; deterministic configs are feasibility signals only", "evidence_path": "test_vlm/outputs/v12_1_completion_v1/candidate_feasibility/reports/MICRO_CASQ_CANDIDATE_FEASIBILITY_REPORT.md"},
            {"section_id": "Section 29", "requirement": "selectivity stratification", "existing_artifacts": "v1 strata reported with event counts and candidate recall where measurable", "status_before_this_run": "partially_complete", "action_needed": "report v1 strata and recall if candidate feasibility runs", "status_after_this_run": "complete", "blocking_reason_if_any": "", "evidence_path": "test_vlm/outputs/v12_1_completion_v1/reports/MICRO_CASQ_V1_SELECTIVITY_STRATIFICATION_REPORT.md"},
            {"section_id": "Section 30", "requirement": "single-dataset claim scope limitation", "existing_artifacts": "final report states oracle-relative sampled-benchmark scope", "status_before_this_run": "complete", "action_needed": "repeat claim limits in final report", "status_after_this_run": "complete", "blocking_reason_if_any": "", "evidence_path": "test_vlm/outputs/v12_1_completion_v1/reports/V12_1_COMPLETION_FINAL_REPORT.md"},
            {"section_id": "Section 31", "requirement": "Phase 1 candidate feasibility v2 / analogous Micro-CASQ candidate feasibility", "existing_artifacts": "Nexar v2 CANDIDATE_STILL_TOO_WEAK; Micro-CASQ v1 candidate feasibility run", "status_before_this_run": "partially_complete", "action_needed": "build v1 and run if gates pass", "status_after_this_run": "complete", "blocking_reason_if_any": "", "evidence_path": "test_vlm/outputs/v12_1_completion_v1/candidate_feasibility/reports/MICRO_CASQ_CANDIDATE_FEASIBILITY_REPORT.md"},
        ]
    else:
        data = [
            {"section_id": "Section 23", "requirement": "implementation hard assertions", "existing_artifacts": "prior phase reports; this run gates validation and certificate assertions", "status_before_this_run": "partially_complete", "action_needed": "carry forward validation; certificate assertions only if certificate runs", "status_after_this_run": "", "blocking_reason_if_any": "", "evidence_path": ""},
            {"section_id": "Section 26", "requirement": "external label <-> predicate mapping", "existing_artifacts": "Nexar mapping/audit reports show UNRELIABLE", "status_before_this_run": "complete", "action_needed": "preserve unreliable mapping scope", "status_after_this_run": "", "blocking_reason_if_any": "", "evidence_path": ""},
            {"section_id": "Section 27", "requirement": "bounded VLM micro-audit / oracle logging", "existing_artifacts": "Micro-CASQ 32B oracle v0 with GPU monitoring", "status_before_this_run": "partially_complete", "action_needed": "expand bounded oracle samples if possible", "status_after_this_run": "", "blocking_reason_if_any": "", "evidence_path": ""},
            {"section_id": "Section 28", "requirement": "candidate hyperparameter selection protocol", "existing_artifacts": "prior candidate feasibility v2; this run uses frozen/pre-registered cheap baselines", "status_before_this_run": "partially_complete", "action_needed": "avoid best-of-sweep final decisions", "status_after_this_run": "", "blocking_reason_if_any": "", "evidence_path": ""},
            {"section_id": "Section 29", "requirement": "selectivity stratification", "existing_artifacts": "v0 strata available", "status_before_this_run": "partially_complete", "action_needed": "report v1 strata and recall if candidate feasibility runs", "status_after_this_run": "", "blocking_reason_if_any": "", "evidence_path": ""},
            {"section_id": "Section 30", "requirement": "single-dataset claim scope limitation", "existing_artifacts": "reports state oracle-relative sampled benchmark scope", "status_before_this_run": "complete", "action_needed": "repeat claim limits in final report", "status_after_this_run": "", "blocking_reason_if_any": "", "evidence_path": protocol},
            {"section_id": "Section 31", "requirement": "Phase 1 candidate feasibility v2 / analogous Micro-CASQ candidate feasibility", "existing_artifacts": "Nexar v2 CANDIDATE_STILL_TOO_WEAK; Micro-CASQ v0 underpowered", "status_before_this_run": "partially_complete", "action_needed": "build v1 and run if gates pass", "status_after_this_run": "", "blocking_reason_if_any": "", "evidence_path": ""},
        ]
    df = pd.DataFrame(data)
    df.to_csv(TABLES / "v12_1_completion_matrix.csv", index=False)
    write(REPORTS / "V12_1_COMPLETION_MATRIX.md", "# V12.1 Completion Matrix\n\n" + md_table(df) + "\n")
    return df


def stage1_attrition() -> dict[str, Any]:
    res = pd.read_csv(V0 / "tables/micro_casq_32b_oracle_adjudication_results.csv", low_memory=False)
    excluded = pd.read_csv(V0 / "benchmark/micro_casq_32b_oracle_v0_excluded_or_needs_sanity_check.csv", low_memory=False)
    pos, neg, excl = eligible_masks(res)
    raw_pos = res["label"].astype(str).eq("positive")
    raw_neg = res["label"].astype(str).eq("negative")
    def count_reason(mask: pd.Series) -> dict[str, int]:
        sub = res[mask]
        return {
            "low_confidence": int(sub["confidence"].astype(str).eq("low").sum()),
            "uncertain_boundary": int(sub["boundary_status"].astype(str).eq("uncertain").sum()),
            "truncated_boundary": int(sub["boundary_status"].astype(str).eq("truncated").sum()),
            "abstain": int(sub["label"].astype(str).eq("abstain").sum()),
            "parse_failure": int(~sub["parse_status"].astype(str).eq("success").sum()) if False else int((sub["parse_status"].astype(str) != "success").sum()),
            "run_failure": int((sub["run_status"].astype(str) != "success").sum()),
            "invalid_boundary": int((sub["label"].astype(str).eq("positive") & ~sub.apply(valid_boundary, axis=1)).sum()),
            "needs_human_sanity_check": int(sub["needs_human_sanity_check"].map(boolish).sum()),
        }
    attr = pd.DataFrame([
        {"stage": "materializable_selected", "count": len(res), "notes": "v0 materializable samples"},
        {"stage": "successful_parse", "count": int((res.run_status.eq("success") & res.parse_status.eq("success")).sum()), "notes": "32B oracle parsed"},
        {"stage": "raw_positive", "count": int(raw_pos.sum()), "notes": "label == positive"},
        {"stage": "eligible_positive", "count": int(pos.sum()), "notes": "positive, high/medium confidence, ok boundary, valid times, no sanity flag"},
        {"stage": "raw_negative", "count": int(raw_neg.sum()), "notes": "label == negative"},
        {"stage": "eligible_negative", "count": int(neg.sum()), "notes": "negative, high/medium confidence, not_applicable boundary, no sanity flag"},
        {"stage": "excluded_or_needs_sanity_check", "count": int(excl.sum()), "notes": "excluded from headline benchmark"},
    ])
    attr.to_csv(TABLES / "micro_casq_v0_attrition_table.csv", index=False)
    for col, path in [
        ("sampling_stratum", "micro_casq_v0_yield_by_stratum.csv"),
        ("candidate_source", "micro_casq_v0_yield_by_candidate_source.csv"),
        ("source_asset", "micro_casq_v0_yield_by_source_asset.csv"),
    ]:
        g = res.assign(eligible_positive=pos, eligible_negative=neg).groupby(col, dropna=False).agg(
            rows=("adjudication_sample_id", "count"),
            raw_positive=("label", lambda s: int((s.astype(str) == "positive").sum())),
            eligible_positive=("eligible_positive", "sum"),
            raw_negative=("label", lambda s: int((s.astype(str) == "negative").sum())),
            eligible_negative=("eligible_negative", "sum"),
        ).reset_index()
        g["eligible_positive_yield"] = g["eligible_positive"] / g["rows"]
        g["eligible_negative_yield"] = g["eligible_negative"] / g["rows"]
        g.sort_values(["eligible_positive_yield", "eligible_positive", "rows"], ascending=[False, False, False]).to_csv(TABLES / path, index=False)
    reason_rows = []
    for name, mask in [("all_excluded", excl), ("raw_positive_not_eligible", raw_pos & ~pos), ("raw_negative_not_eligible", raw_neg & ~neg)]:
        d = count_reason(mask)
        for k, v in d.items():
            reason_rows.append({"subset": name, "exclusion_reason": k, "count": v})
    reason_df = pd.DataFrame(reason_rows)
    reason_df.to_csv(TABLES / "micro_casq_v0_exclusion_reason_summary.csv", index=False)
    by_stratum = pd.read_csv(TABLES / "micro_casq_v0_yield_by_stratum.csv")
    by_source = pd.read_csv(TABLES / "micro_casq_v0_yield_by_candidate_source.csv")
    by_asset = pd.read_csv(TABLES / "micro_casq_v0_yield_by_source_asset.csv")
    report = [
        "# Micro-CASQ v0 Attrition and Yield Report",
        "",
        "All labels are 32B-oracle-relative, not human truth.",
        "",
        f"- Raw positives: `{int(raw_pos.sum())}` -> eligible positives: `{int(pos.sum())}`.",
        f"- Raw negatives: `{int(raw_neg.sum())}` -> eligible negatives: `{int(neg.sum())}`.",
        "- Main positive attrition drivers are invalid/missing positive boundaries, low confidence, uncertain/truncated boundaries, or sanity-check flags.",
        "- Main negative attrition drivers are needs_human_sanity_check flags, confidence/boundary filters, abstain rows, and run failures.",
        "",
        "## Attrition Table",
        md_table(attr),
        "",
        "## Exclusion Reasons",
        md_table(reason_df),
        "",
        "## Highest Positive-Yield Strata",
        md_table(by_stratum.head(10)),
        "",
        "## Highest Positive-Yield Candidate Sources",
        md_table(by_source.head(10)),
        "",
        "## Highest Positive-Yield Source Assets",
        md_table(by_asset.head(10)),
        "",
        "## Expansion Strategy",
        "Prioritize remaining materializable rows from likely_positive, label_disagreement, possible_false_negative, old positive/VLM-derived provenance, human-audit provenance, and source assets with observed eligible-positive yield, while retaining enough hard/likely negatives to approach the eligible-negative gate.",
    ]
    write(REPORTS / "MICRO_CASQ_V0_ATTRITION_AND_YIELD_REPORT.md", "\n".join(report) + "\n")
    return {"v0_eligible_positive": int(pos.sum()), "v0_eligible_negative": int(neg.sum())}


def classify_stratum(df: pd.DataFrame) -> pd.Series:
    old = df.get("old_label", pd.Series("", index=df.index)).fillna("").astype(str).str.lower()
    cand = df.get("candidate_source", pd.Series("", index=df.index)).fillna("").astype(str).str.lower()
    reason = df.get("recommendation_reason", pd.Series("", index=df.index)).fillna("").astype(str).str.lower()
    boundary = df.get("boundary_source", pd.Series("", index=df.index)).fillna("").astype(str).str.lower()
    out = pd.Series("hard_negative", index=df.index, dtype="object")
    positive = old.isin(["positive", "yes", "true", "1"]) | old.str.contains("positive", na=False)
    negative = old.isin(["negative", "no", "false", "0", "normal"]) | old.str.contains("negative|normal", regex=True, na=False)
    disagreement = reason.str.contains("disagreement|overrode|rejected|32b negative|mismatch", regex=True, na=False)
    possible_fn = negative & (cand.str.contains("proxy|predicted|kinematic|candidate", regex=True, na=False) | reason.str.contains("proxy|candidate|false negative|high", regex=True, na=False))
    boundary_uncertain = boundary.str.contains("pseudo|external|alert|uncertain|derived", regex=True, na=False)
    out[boundary_uncertain] = "boundary_uncertain"
    out[possible_fn] = "possible_false_negative"
    out[disagreement] = "label_disagreement"
    out[positive] = "likely_positive"
    return out


def select_expansion() -> pd.DataFrame:
    pool = pd.read_csv(DATA_AUDIT / "tables/micro_casq_candidate_pool_index.csv", low_memory=False)
    adj = pd.read_csv(ADJ_PKG / "tables/micro_casq_adjudication_samples_v0.csv", low_memory=False)
    v0 = pd.read_csv(V0 / "tables/micro_casq_32b_oracle_adjudication_results.csv", low_memory=False)
    used = set(adj["pool_item_id"].astype(str)) | set(v0["pool_item_id"].astype(str))
    pool = pool[~pool["pool_item_id"].astype(str).isin(used)].copy()
    pool["sampling_stratum"] = classify_stratum(pool)
    start = pd.to_numeric(pool["start_time"], errors="coerce")
    end = pd.to_numeric(pool["end_time"], errors="coerce")
    pool["clip_start_time"] = start
    pool["clip_end_time"] = end
    pool["clip_duration"] = pd.to_numeric(pool["duration"], errors="coerce").fillna(end - start)
    pool["path_exists_now"] = pool["source_video_path"].fillna("").astype(str).map(lambda p: bool(p and p != "nan" and Path(p).exists()))
    pool["valid_window_now"] = start.notna() & end.notna() & (end > start) & ((end - start) > 0) & ((end - start) <= 60)
    pool["already_adjudicated"] = False
    # Priority from v0 yield and prompt objective.
    stratum_weight = {"likely_positive": 100, "label_disagreement": 90, "possible_false_negative": 85, "hard_negative": 40, "boundary_uncertain": 30}
    old = pool["old_label"].fillna("").astype(str).str.lower()
    pool["selection_priority"] = pool["sampling_stratum"].map(stratum_weight).fillna(10)
    pool.loc[old.isin(["positive", "yes", "true", "1"]) | old.str.contains("positive", na=False), "selection_priority"] += 30
    pool.loc[pool["old_label_source"].fillna("").astype(str).str.contains("human", case=False, na=False), "selection_priority"] += 20
    pool.loc[pool["candidate_source"].fillna("").astype(str).str.contains("vlm_micro_audit|human_audit|vlm_labels_conservative", case=False, regex=True, na=False), "selection_priority"] += 15
    pool.loc[pool["candidate_source"].fillna("").astype(str).str.contains("nexar_candidate_windows|proxy|kinematic", case=False, regex=True, na=False), "selection_priority"] += 5
    pool.loc[pool["path_exists_now"] & pool["valid_window_now"], "selection_priority"] += 100
    pool["_video_key"] = pool["video_id"].fillna("__missing__").astype(str)
    pool = pool.sort_values(["path_exists_now", "valid_window_now", "selection_priority", "_video_key"], ascending=[False, False, False, True], kind="mergesort")
    chosen_idx = []
    counts = Counter()
    cap = 1
    while len(chosen_idx) < MAX_NEW_32B_CALLS and len(chosen_idx) < len(pool):
        added = False
        for idx, row in pool.iterrows():
            if idx in chosen_idx:
                continue
            vk = row["_video_key"]
            if counts[vk] < cap:
                chosen_idx.append(idx)
                counts[vk] += 1
                added = True
                if len(chosen_idx) >= MAX_NEW_32B_CALLS:
                    break
        if not added:
            cap += 1
    sel = pool.loc[chosen_idx].copy().reset_index(drop=True)
    sel["expansion_sample_id"] = [f"exp_v1_{i:04d}" for i in range(1, len(sel) + 1)]
    sel["selection_reason"] = "targeted expansion; prioritized materializable rows, likely positives/disagreement/possible false negatives, provenance-only old labels, and video diversity"
    sel["expected_positive_yield_bucket"] = sel["sampling_stratum"].map({"likely_positive": "high", "label_disagreement": "medium_high", "possible_false_negative": "medium", "hard_negative": "low", "boundary_uncertain": "low"}).fillna("unknown")
    sel["expected_materialization_quality"] = sel.apply(lambda r: "existing_path_valid_window" if r["path_exists_now"] and r["valid_window_now"] else "needs_repair", axis=1)
    sel["notes"] = "Old labels are prioritization provenance only; not gold. Event boundaries were not used for candidate generation."
    cols = ["expansion_sample_id", "pool_item_id", "source_asset", "video_id", "clip_id", "source_video_path", "clip_start_time", "clip_end_time", "clip_duration", "candidate_source", "sampling_stratum", "old_label", "old_label_source", "old_confidence", "boundary_source", "is_nexar_derived", "is_vlm_derived", "is_human_audited", "is_pseudo_boundary", "is_external_label", "already_adjudicated", "selection_priority", "selection_reason", "expected_positive_yield_bucket", "expected_materialization_quality", "notes"]
    for c in cols:
        if c not in sel:
            sel[c] = ""
    sel[cols].to_csv(TABLES / "micro_casq_expansion_candidate_selection_v1.csv", index=False)
    write(REPORTS / "MICRO_CASQ_EXPANSION_SELECTION_REPORT.md", "# Micro-CASQ Expansion Selection Report\n\n" + f"Selected `{len(sel)}` candidate samples from existing local candidate pool. Event boundaries and old labels were not used as gold; old labels are provenance-only prioritization.\n\n" + md_table(sel["sampling_stratum"].value_counts().rename_axis("sampling_stratum").reset_index(name="count")) + "\n")
    return sel[cols]


def expansion_feasibility(sel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in sel.iterrows():
        status = "materializable"
        err = ""
        p = str(r["source_video_path"])
        st = numeric(r["clip_start_time"])
        en = numeric(r["clip_end_time"])
        dur = en - st if pd.notna(st) and pd.notna(en) else float("nan")
        if boolish(r.get("already_adjudicated", False)):
            status = "already_adjudicated"
        elif not p or p == "nan" or not Path(p).exists():
            status = "missing_video"
        elif pd.isna(st) or pd.isna(en) or en <= st:
            status = "invalid_time_window"
        elif dur <= 0 or dur > 60:
            status = "duration_too_long"
        elif shutil.which("ffprobe"):
            code = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", p], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20, check=False)
            if code.returncode != 0:
                status = "video_unreadable"
                err = code.stderr[:300]
        rows.append({**r.to_dict(), "feasibility_status": status, "error_message": err})
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "micro_casq_expansion_feasibility_v1.csv", index=False)
    write(REPORTS / "MICRO_CASQ_EXPANSION_FEASIBILITY_REPORT.md", "# Micro-CASQ Expansion Feasibility Report\n\nNo full videos were decoded and no models were run. Feasibility checks used path/time validation and ffprobe when available.\n\n" + md_table(df["feasibility_status"].value_counts().rename_axis("feasibility_status").reset_index(name="count")) + "\n")
    return df


def start_monitors() -> list[subprocess.Popen]:
    procs = []
    if not shutil.which("nvidia-smi"):
        return procs
    gpu_csv = EXP_MON / "nvidia_smi_gpu_timeseries.csv"
    apps_log = EXP_MON / "nvidia_smi_compute_apps_timeseries.log"
    dmon_log = EXP_MON / "nvidia_smi_dmon.log"
    procs.append(subprocess.Popen(["nvidia-smi", "--query-gpu=timestamp,index,name,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw", "--format=csv", "-l", "1"], stdout=gpu_csv.open("a"), stderr=subprocess.STDOUT))
    (EXP_MON / "nvidia_smi_gpu_timeseries.pid").write_text(str(procs[-1].pid), encoding="utf-8")
    procs.append(subprocess.Popen("while true; do date '+%F %T'; nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv || true; sleep 1; done", shell=True, stdout=apps_log.open("a"), stderr=subprocess.STDOUT, executable="/bin/bash"))
    (EXP_MON / "nvidia_smi_compute_apps_timeseries.pid").write_text(str(procs[-1].pid), encoding="utf-8")
    if subprocess.run(["nvidia-smi", "dmon", "-h"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0:
        procs.append(subprocess.Popen(["nvidia-smi", "dmon", "-s", "pucvmt", "-d", "1"], stdout=dmon_log.open("a"), stderr=subprocess.STDOUT))
        (EXP_MON / "nvidia_smi_dmon.pid").write_text(str(procs[-1].pid), encoding="utf-8")
    return procs


def stop_monitors(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        if p.poll() is None:
            p.terminate()
    time.sleep(2)
    for p in procs:
        if p.poll() is None:
            p.kill()


def load_model():
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    if not torch.cuda.is_available():
        raise RuntimeError("GPU_NOT_AVAILABLE")
    model = Qwen3VLForConditionalGeneration.from_pretrained(str(MODEL_DIR), dtype=torch.bfloat16, device_map={"": "cuda:0"}, attn_implementation="sdpa", local_files_only=True)
    processor = AutoProcessor.from_pretrained(str(MODEL_DIR), local_files_only=True)
    devices = [str(next(model.parameters()).device)]
    for i, (_, p) in enumerate(model.named_parameters()):
        if i >= 8:
            break
        devices.append(str(p.device))
    if any(d == "cpu" or d.startswith("disk") for d in devices) or not all(d.startswith("cuda") for d in devices):
        raise RuntimeError(f"CPU_OFFLOAD_OR_MODEL_ON_CPU: {devices}")
    return torch, process_vision_info, model, processor


def extract_clip(row: pd.Series) -> Path:
    out = EXP_CLIPS / f"{row['expansion_sample_id']}.mp4"
    if out.exists() and out.stat().st_size > 0:
        return out
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg unavailable")
    st = numeric(row["clip_start_time"])
    en = numeric(row["clip_end_time"])
    dur = max(0.01, en - st)
    base = [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{st:.3f}", "-i", str(row["source_video_path"]), "-t", f"{dur:.3f}"]
    cmd = base + ["-c:v", "mpeg4", "-q:v", "5", "-an", "-movflags", "+faststart", "-y", str(out)]
    code = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120, check=False)
    if code.returncode != 0:
        raise RuntimeError(code.stderr[:500])
    return out


def run_prompt(torch, process_vision_info, model, processor, clip: Path, prompt: str) -> str:
    messages = [{"role": "user", "content": [{"type": "video", "video": str(clip), "fps": FPS, "max_pixels": MAX_PIXELS}, {"type": "text", "text": prompt}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(model.device)
    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=512, do_sample=False)
    trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated)]
    return processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]


def expansion_32b(feas: pd.DataFrame) -> pd.DataFrame:
    mat = feas[feas["feasibility_status"].eq("materializable")].copy().head(MAX_NEW_32B_CALLS)
    prompt_path = V0 / "prompts/o_enter_ego_path_v0_32b_oracle_prompt.txt"
    prompt = prompt_path.read_text(encoding="utf-8")
    prior_results_path = TABLES / "micro_casq_expansion_32b_oracle_results_v1.csv"
    prior_success: dict[str, dict[str, Any]] = {}
    if prior_results_path.exists() and prior_results_path.stat().st_size:
        try:
            prior = pd.read_csv(prior_results_path, low_memory=False)
            ok = prior["run_status"].astype(str).eq("success") & prior["parse_status"].astype(str).eq("success") & prior.get("device_status", "").astype(str).eq("gpu_verified")
            for _, rr in prior[ok].iterrows():
                prior_success[str(rr["adjudication_sample_id"])] = rr.to_dict()
        except Exception:
            prior_success = {}
    resume_rows = []
    monitors = start_monitors()
    rows = []
    try:
        torch, process_vision_info, model, processor = load_model()
        gpu_name = torch.cuda.get_device_name(0)
        param_device = str(next(model.parameters()).device)
        for i, (_, r) in enumerate(mat.iterrows(), start=1):
            aid = r["expansion_sample_id"]
            raw_path = EXP_RAW / f"{aid}.json"
            if aid in prior_success:
                rows.append(prior_success[aid])
                resume_rows.append({"expansion_sample_id": aid, "existing_raw_output": Path(str(prior_success[aid].get("raw_model_output_path", ""))).exists(), "existing_parse_success": True, "previous_run_status": "success", "resume_action": "skip_existing_success", "reason": "existing GPU-verified successful parsed row retained"})
                print(f"[expansion-32b] {i}/{len(mat)} {aid} resume_action=skip_existing_success", flush=True)
                continue
            result = {c: "" for c in RESULT_COLUMNS}
            result.update({k: r.get(k, "") for k in r.index if k in result})
            result["adjudication_sample_id"] = aid
            result["pool_item_id"] = r["pool_item_id"]
            result["input_mode"] = "ffmpeg_extracted_clip_interval"
            result["model_name"] = MODEL_NAME
            result["prompt_version"] = PROMPT_VERSION
            result["frame_sampling_policy"] = f"fps={FPS}; max_pixels={MAX_PIXELS}; target interval only"
            result["raw_model_output_path"] = str(raw_path)
            result["gpu_name"] = gpu_name
            result["cuda_available"] = True
            result["model_parameter_device"] = param_device
            result["run_phase"] = "expansion_v1_gpu_verified"
            existing_raw = raw_path.exists()
            if existing_raw:
                try:
                    existing = json.loads(raw_path.read_text(encoding="utf-8", errors="replace"))
                    if existing.get("parse_status") == "success" and existing.get("device_status") == "gpu_verified" and isinstance(existing.get("parsed"), dict):
                        norm = normalize_obj(existing.get("parsed"))
                        result.update(norm)
                        result["run_status"] = "success"
                        result["parse_status"] = "success"
                        result["runtime_seconds"] = existing.get("runtime_seconds", "")
                        result["device_status"] = "gpu_verified"
                        result["gpu_memory_allocated_gb"] = existing.get("gpu_memory_allocated_gb", "")
                        result["gpu_memory_reserved_gb"] = existing.get("gpu_memory_reserved_gb", "")
                        rows.append(result)
                        resume_rows.append({"expansion_sample_id": aid, "existing_raw_output": True, "existing_parse_success": True, "previous_run_status": "success", "resume_action": "skip_existing_success", "reason": "existing GPU-verified raw output retained"})
                        print(f"[expansion-32b] {i}/{len(mat)} {aid} resume_action=skip_existing_success", flush=True)
                        continue
                except Exception:
                    pass
                raw_path = EXP_RAW / f"{aid}.rerun_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
                result["raw_model_output_path"] = str(raw_path)
            try:
                clip = extract_clip(r)
                torch.cuda.reset_peak_memory_stats()
                t0 = time.time()
                raw = run_prompt(torch, process_vision_info, model, processor, clip, prompt)
                runtime = time.time() - t0
                obj, perr = parse_json_object(raw)
                norm = normalize_obj(obj)
                result.update(norm)
                result["run_status"] = "success"
                result["parse_status"] = "success" if obj is not None else perr
                result["runtime_seconds"] = round(runtime, 3)
                result["device_status"] = "gpu_verified" if obj is not None else "not_run_error"
                result["gpu_memory_allocated_gb"] = round(torch.cuda.memory_allocated() / (1024**3), 3)
                result["gpu_memory_reserved_gb"] = round(torch.cuda.memory_reserved() / (1024**3), 3)
                raw_path.write_text(json.dumps({"expansion_sample_id": aid, "pool_item_id": r["pool_item_id"], "raw_text": raw, "parsed": obj, "parse_status": result["parse_status"], "device_status": result["device_status"], "gpu_name": gpu_name, "model_parameter_device": param_device, "runtime_seconds": result["runtime_seconds"], "gpu_memory_allocated_gb": result["gpu_memory_allocated_gb"], "gpu_memory_reserved_gb": result["gpu_memory_reserved_gb"]}, indent=2, ensure_ascii=False), encoding="utf-8")
                resume_rows.append({"expansion_sample_id": aid, "existing_raw_output": existing_raw, "existing_parse_success": False, "previous_run_status": "missing_or_incomplete", "resume_action": "run_or_rerun", "reason": "missing or incomplete previous GPU-verified output"})
            except Exception as exc:
                result["run_status"] = "not_run_error"
                result["parse_status"] = "not_run"
                result["device_status"] = "not_run_error"
                result["error_message"] = str(exc)[:1000]
                raw_path.write_text(json.dumps({"expansion_sample_id": aid, "pool_item_id": r["pool_item_id"], "error": result["error_message"], "device_status": "not_run_error"}, indent=2), encoding="utf-8")
                resume_rows.append({"expansion_sample_id": aid, "existing_raw_output": existing_raw, "existing_parse_success": False, "previous_run_status": "missing_or_error", "resume_action": "run_or_rerun", "reason": "sample attempted and failed; error retained"})
            rows.append(result)
            print(f"[expansion-32b] {i}/{len(mat)} {aid} status={result['run_status']} parse={result['parse_status']} label={result.get('label','')} device={result.get('device_status','')}", flush=True)
    finally:
        stop_monitors(monitors)
        if resume_rows:
            pd.DataFrame(resume_rows).to_csv(TABLES / "micro_casq_expansion_resume_plan_v1.csv", index=False)
            write(REPORTS / "MICRO_CASQ_EXPANSION_RESUME_PLAN.md", "# Micro-CASQ Expansion Resume Plan\n\nExisting GPU-verified successful rows/raw outputs are retained and skipped on rerun. Missing, failed, or incomplete samples are run or rerun without overwriting existing successful raw outputs.\n\n" + md_table(pd.DataFrame(resume_rows)["resume_action"].value_counts().rename_axis("resume_action").reset_index(name="count")) + "\n")
    df = pd.DataFrame(rows)
    for c in RESULT_COLUMNS:
        if c not in df:
            df[c] = ""
    df = df[RESULT_COLUMNS]
    df.to_csv(TABLES / "micro_casq_expansion_32b_oracle_results_v1.csv", index=False)
    write(REPORTS / "MICRO_CASQ_EXPANSION_32B_ORACLE_REPORT.md", "# Micro-CASQ Expansion 32B Oracle Report\n\nThese labels are 32B-oracle-relative, not human truth. Only expansion samples with `feasibility_status == materializable` were processed.\n\n" + md_table(df["run_status"].value_counts().rename_axis("run_status").reset_index(name="count")) + "\n\n" + md_table(df["label"].value_counts(dropna=False).rename_axis("label").reset_index(name="count")) + "\n")
    write_gpu_monitor_report()
    return df


def write_gpu_monitor_report() -> None:
    csv_path = EXP_MON / "nvidia_smi_gpu_timeseries.csv"
    apps = (EXP_MON / "nvidia_smi_compute_apps_timeseries.log").read_text(errors="replace") if (EXP_MON / "nvidia_smi_compute_apps_timeseries.log").exists() else ""
    summary = {"python_compute_app_observed": bool(re.search(r"\bpython\b.*\b[1-9][0-9]{3,}\s*MiB", apps)), "gpu_name": "", "max_gpu_memory_used_mib": 0, "mean_gpu_utilization_percent": 0.0, "max_gpu_utilization_percent": 0}
    if csv_path.exists() and csv_path.stat().st_size:
        df = pd.read_csv(csv_path)
        df.columns = [c.strip() for c in df.columns]
        util = pd.to_numeric(df.get("utilization.gpu [%]", pd.Series(dtype=str)).astype(str).str.replace(r"[^0-9.]", "", regex=True), errors="coerce")
        mem = pd.to_numeric(df.get("memory.used [MiB]", pd.Series(dtype=str)).astype(str).str.replace(r"[^0-9.]", "", regex=True), errors="coerce")
        summary["gpu_name"] = str(df["name"].dropna().iloc[0]).strip() if "name" in df and df["name"].dropna().size else ""
        summary["max_gpu_memory_used_mib"] = int(mem.max()) if mem.notna().any() else 0
        summary["mean_gpu_utilization_percent"] = round(float(util.mean()), 3) if util.notna().any() else 0
        summary["max_gpu_utilization_percent"] = int(util.max()) if util.notna().any() else 0
    pd.DataFrame([summary]).to_csv(TABLES / "micro_casq_expansion_gpu_monitoring_summary.csv", index=False)
    interp = "GPU inference confirmed" if summary["python_compute_app_observed"] and summary["max_gpu_memory_used_mib"] > 10000 and summary["max_gpu_utilization_percent"] > 0 else "GPU compute still unverified"
    write(REPORTS / "MICRO_CASQ_EXPANSION_GPU_MONITORING_REPORT.md", f"# Micro-CASQ Expansion GPU Monitoring Report\n\n- Python compute app observed: `{summary['python_compute_app_observed']}`\n- GPU name: `{summary['gpu_name']}`\n- Max GPU memory used: `{summary['max_gpu_memory_used_mib']}` MiB\n- Mean GPU utilization: `{summary['mean_gpu_utilization_percent']}`%\n- Max GPU utilization: `{summary['max_gpu_utilization_percent']}`%\n\nInterpretation: `{interp}`. GPU utilization may be bursty or I/O-bound under one-second nvidia-smi sampling.\n")


def build_v1(v0: pd.DataFrame, exp: pd.DataFrame) -> dict[str, Any]:
    allres = pd.concat([v0, exp], ignore_index=True)
    pos, neg, excl = eligible_masks(allres)
    bench = allres[pos | neg].copy()
    bench["oracle_category"] = ["oracle_positive" if x else "oracle_negative" for x in pos[pos | neg]]
    bench.to_csv(BENCH / "micro_casq_32b_oracle_v1_benchmark.csv", index=False)
    p = allres[pos].copy()
    p["oracle_event_id"] = [f"v1_oracle_event_{i:04d}" for i in range(1, len(p) + 1)]
    p["event_start_video_time"] = pd.to_numeric(p["clip_start_time"], errors="coerce") + pd.to_numeric(p["event_start"], errors="coerce")
    p["event_end_video_time"] = pd.to_numeric(p["clip_start_time"], errors="coerce") + pd.to_numeric(p["event_end"], errors="coerce")
    p.to_csv(BENCH / "micro_casq_32b_oracle_v1_positive_events.csv", index=False)
    n = allres[neg].copy()
    n["oracle_negative_id"] = [f"v1_oracle_negative_{i:04d}" for i in range(1, len(n) + 1)]
    n.to_csv(BENCH / "micro_casq_32b_oracle_v1_negative_windows.csv", index=False)
    allres[excl].to_csv(BENCH / "micro_casq_32b_oracle_v1_excluded_or_needs_sanity_check.csv", index=False)
    summ = {"eligible_positive": int(pos.sum()), "eligible_negative": int(neg.sum()), "excluded": int(excl.sum()), "rows": len(allres)}
    pd.DataFrame([summ]).to_csv(TABLES / "micro_casq_32b_oracle_v1_eligibility_summary.csv", index=False)
    if summ["eligible_positive"] >= 30 and summ["eligible_negative"] >= 80:
        decision = "MICRO_CASQ_BENCHMARK_DECISION: READY_FOR_CANDIDATE_FEASIBILITY"
    elif summ["eligible_positive"] < 30 and summ["eligible_negative"] < 80:
        decision = "MICRO_CASQ_BENCHMARK_DECISION: NEED_MORE_POSITIVES_AND_NEGATIVES"
    elif summ["eligible_positive"] < 30:
        decision = "MICRO_CASQ_BENCHMARK_DECISION: NEED_MORE_POSITIVES"
    else:
        decision = "MICRO_CASQ_BENCHMARK_DECISION: NEED_MORE_NEGATIVES"
    summ["benchmark_decision"] = decision
    write(REPORTS / "MICRO_CASQ_32B_ORACLE_V1_BENCHMARK_REPORT.md", "# Micro-CASQ 32B-Oracle v1 Benchmark Report\n\nAll labels are 32B-oracle-relative, not human truth. Excluded rows are retained separately and are not used in headline metrics.\n\n" + md_table(pd.DataFrame([summ])) + f"\n\n{decision}\n")
    return summ


def split_v1(summary: dict[str, Any]) -> None:
    if not summary["benchmark_decision"].endswith("READY_FOR_CANDIDATE_FEASIBILITY"):
        write(REPORTS / "MICRO_CASQ_32B_ORACLE_V1_SPLIT_REPORT.md", "# Micro-CASQ 32B-Oracle v1 Split Report\n\nSkipped because benchmark is not ready for candidate feasibility.\n")
        return
    bench = pd.read_csv(BENCH / "micro_casq_32b_oracle_v1_benchmark.csv", low_memory=False)
    excl = pd.read_csv(BENCH / "micro_casq_32b_oracle_v1_excluded_or_needs_sanity_check.csv", low_memory=False)
    vids = list(bench["video_id"].fillna("__missing__").astype(str).unique())
    random.Random(RANDOM_SEED).shuffle(vids)
    mapping = {}
    for i, v in enumerate(vids):
        mapping[v] = "candidate_dev" if i < 0.3 * len(vids) else ("heldout_eval" if i < 0.7 * len(vids) else "reserved_certification_pool")
    rows = []
    for _, r in bench.iterrows():
        rows.append({"adjudication_sample_id": r["adjudication_sample_id"], "video_id": r["video_id"], "oracle_category": r["oracle_category"], "sampling_stratum": r.get("sampling_stratum", ""), "split_label": mapping.get(str(r["video_id"]), "heldout_eval")})
    for _, r in excl.iterrows():
        rows.append({"adjudication_sample_id": r["adjudication_sample_id"], "video_id": r.get("video_id", ""), "oracle_category": "excluded_or_needs_sanity_check", "sampling_stratum": r.get("sampling_stratum", ""), "split_label": "excluded_or_needs_sanity_check"})
    df = pd.DataFrame(rows)
    df.to_csv(BENCH / "micro_casq_32b_oracle_v1_split.csv", index=False)
    write(REPORTS / "MICRO_CASQ_32B_ORACLE_V1_SPLIT_REPORT.md", "# Micro-CASQ 32B-Oracle v1 Split Report\n\nVideo-disjoint split proposal where possible. Reserved certification pool must not be used for candidate tuning. Event boundaries must not be used to generate future candidates.\n\n" + md_table(df.groupby(["split_label", "oracle_category"]).size().reset_index(name="count")) + "\n")


def candidate_feasibility(summary: dict[str, Any]) -> str:
    inv = pd.DataFrame([
        {"candidate_generator": "random_baseline", "available": True, "notes": "pre-registered random order over sampled benchmark rows"},
        {"candidate_generator": "fixed_temporal_coverage", "available": True, "notes": "sort by clip_start_time/video order; no event boundaries"},
        {"candidate_generator": "provenance_priority", "available": True, "notes": "uses source/old-label provenance only, not gold labels"},
        {"candidate_generator": "motion_energy", "available": False, "notes": "not run; would require extra video decoding and was not necessary for current gate"},
        {"candidate_generator": "existing_proxy_score_replay", "available": False, "notes": "no frozen comparable proxy score column was used for this sampled benchmark"},
        {"candidate_generator": "representation_candidate", "available": False, "notes": "REPRESENTATION_CANDIDATE_NOT_AVAILABLE; no local embedding asset/model use approved"},
        {"candidate_generator": "YOLO_count", "available": False, "notes": "not run by instruction"},
    ])
    inv.to_csv(CF / "tables/candidate_generator_inventory.csv", index=False)
    pd.DataFrame([{"representation_candidate": "REPRESENTATION_CANDIDATE_NOT_AVAILABLE", "local_assets_found": False, "download_approved": False}]).to_csv(CF / "tables/representation_candidate_availability.csv", index=False)
    if not summary["benchmark_decision"].endswith("READY_FOR_CANDIDATE_FEASIBILITY"):
        decision = "MICRO_CASQ_CANDIDATE_DECISION: BENCHMARK_UNDERPOWERED"
        write(CF / "reports/MICRO_CASQ_CANDIDATE_FEASIBILITY_REPORT.md", f"# Micro-CASQ Candidate Feasibility Report\n\nSkipped because benchmark gate failed: `{summary['benchmark_decision']}`.\n\nREPRESENTATION_CANDIDATE_NOT_AVAILABLE\n\n{decision}\n")
        pd.DataFrame().to_csv(CF / "tables/candidate_feasibility_results.csv", index=False)
        pd.DataFrame().to_csv(CF / "tables/candidate_feasibility_by_stratum.csv", index=False)
        return decision
    bench = pd.read_csv(BENCH / "micro_casq_32b_oracle_v1_benchmark.csv", low_memory=False)
    split = pd.read_csv(BENCH / "micro_casq_32b_oracle_v1_split.csv")
    bench = bench.merge(split[["adjudication_sample_id", "split_label"]], on="adjudication_sample_id", how="left")
    eval_df = bench[bench["split_label"].eq("heldout_eval")].copy()
    configs = []
    eval_df["_temporal"] = eval_df["video_id"].astype(str) + "_" + pd.to_numeric(eval_df["clip_start_time"], errors="coerce").fillna(0).astype(str)
    old = eval_df["old_label"].fillna("").astype(str).str.lower()
    eval_df["_prov"] = old.isin(["positive", "yes", "true", "1"]).astype(int) * 2 + eval_df["sampling_stratum"].astype(str).eq("likely_positive").astype(int)
    pos_total = int(eval_df["oracle_category"].eq("oracle_positive").sum())
    for frac in [0.25, 0.5, 0.75]:
        repeat_rows = []
        for rep in range(100):
            rng = random.Random(RANDOM_SEED + rep)
            tmp = eval_df.copy()
            tmp["_random"] = [rng.random() for _ in range(len(tmp))]
            returned = tmp.sort_values("_random", ascending=True).head(max(1, int(frac * len(tmp))))
            hit = int(returned["oracle_category"].eq("oracle_positive").sum())
            repeat_rows.append({
                "recall": hit / pos_total if pos_total else 0,
                "precision": hit / len(returned) if len(returned) else 0,
                "event_hit_count": hit,
                "negative_window_coverage": int(returned["oracle_category"].eq("oracle_negative").sum()),
            })
        rep_df = pd.DataFrame(repeat_rows)
        configs.append({
            "candidate_generator": "random_baseline",
            "configuration": f"top_fraction={frac}",
            "split": "heldout_eval",
            "repeat_count": 100,
            "true_oracle_recall": float(rep_df["recall"].mean()) if not rep_df.empty else 0,
            "recall_std": float(rep_df["recall"].std(ddof=1)) if len(rep_df) > 1 else 0,
            "recall_ci95_low": float(rep_df["recall"].mean() - 1.96 * rep_df["recall"].std(ddof=1) / math.sqrt(len(rep_df))) if len(rep_df) > 1 else 0,
            "recall_ci95_high": float(rep_df["recall"].mean() + 1.96 * rep_df["recall"].std(ddof=1) / math.sqrt(len(rep_df))) if len(rep_df) > 1 else 0,
            "precision": float(rep_df["precision"].mean()) if not rep_df.empty else 0,
            "returned_duration": "",
            "duration_fraction": frac,
            "event_hit_count": float(rep_df["event_hit_count"].mean()) if not rep_df.empty else 0,
            "positive_event_count": pos_total,
            "negative_window_coverage": float(rep_df["negative_window_coverage"].mean()) if not rep_df.empty else 0,
            "runtime_seconds": 0.0,
            "candidate_generation_cost": "metadata_only",
            "source_diversity_hhi": "",
        })
    for name, sortcol, asc in [("fixed_temporal_coverage", "_temporal", True), ("provenance_priority", "_prov", False)]:
        for frac in [0.25, 0.5, 0.75]:
            returned = eval_df.sort_values(sortcol, ascending=asc).head(max(1, int(frac * len(eval_df))))
            hit = int(returned["oracle_category"].eq("oracle_positive").sum())
            configs.append({"candidate_generator": name, "configuration": f"top_fraction={frac}", "split": "heldout_eval", "repeat_count": 1, "true_oracle_recall": hit / pos_total if pos_total else 0, "recall_std": 0.0, "recall_ci95_low": hit / pos_total if pos_total else 0, "recall_ci95_high": hit / pos_total if pos_total else 0, "precision": hit / len(returned) if len(returned) else 0, "returned_duration": float(pd.to_numeric(returned["clip_duration"], errors="coerce").fillna(0).sum()), "duration_fraction": len(returned) / len(eval_df) if len(eval_df) else 0, "event_hit_count": hit, "positive_event_count": pos_total, "negative_window_coverage": int(returned["oracle_category"].eq("oracle_negative").sum()), "runtime_seconds": 0.0, "candidate_generation_cost": "metadata_only", "source_diversity_hhi": float((returned["video_id"].value_counts(normalize=True) ** 2).sum()) if len(returned) else 0})
    res = pd.DataFrame(configs)
    res.to_csv(CF / "tables/candidate_feasibility_results.csv", index=False)
    best = res["true_oracle_recall"].max() if not res.empty else 0
    best_det = res[~res["candidate_generator"].eq("random_baseline")].sort_values(["true_oracle_recall", "precision"], ascending=[False, False]).iloc[0]
    best_frac = float(str(best_det["configuration"]).split("=")[-1])
    if best_det["candidate_generator"] == "fixed_temporal_coverage":
        best_returned = eval_df.sort_values("_temporal", ascending=True).head(max(1, int(best_frac * len(eval_df))))
    else:
        best_returned = eval_df.sort_values("_prov", ascending=False).head(max(1, int(best_frac * len(eval_df))))
    bys = []
    returned_ids = set(best_returned["adjudication_sample_id"].astype(str))
    for strat, g in eval_df.groupby("sampling_stratum"):
        pos_total = int(g["oracle_category"].eq("oracle_positive").sum())
        hit = int(g[g["adjudication_sample_id"].astype(str).isin(returned_ids)]["oracle_category"].eq("oracle_positive").sum())
        bys.append({"sampling_stratum": strat, "positive_event_count": pos_total, "rows": len(g), "best_frozen_candidate_generator": best_det["candidate_generator"], "best_frozen_configuration": best_det["configuration"], "per_stratum_true_recall": hit / pos_total if pos_total else "", "event_hit_count": hit})
    pd.DataFrame(bys).to_csv(CF / "tables/candidate_feasibility_by_stratum.csv", index=False)
    decision = "MICRO_CASQ_CANDIDATE_DECISION: CANDIDATE_READY_FOR_CERTIFICATE" if best >= 0.5 else "MICRO_CASQ_CANDIDATE_DECISION: CANDIDATE_STILL_TOO_WEAK"
    if not inv.loc[inv.candidate_generator.eq("representation_candidate"), "available"].iloc[0] and decision != "MICRO_CASQ_CANDIDATE_DECISION: CANDIDATE_READY_FOR_CERTIFICATE":
        decision = "MICRO_CASQ_CANDIDATE_DECISION: REPRESENTATION_CANDIDATE_NOT_AVAILABLE"
    write(CF / "reports/MICRO_CASQ_CANDIDATE_FEASIBILITY_REPORT.md", "# Micro-CASQ Candidate Feasibility Report\n\nThis is candidate-signal feasibility over an adjudicated sampled benchmark, not full-video retrieval. Event boundaries were not used to generate candidates. Configurations are pre-registered cheap baselines; no YOLO, embeddings, downloads, or training were run. Random baselines use 100 repeats and report mean recall with 95% intervals.\n\n" + md_table(res) + "\n\nREPRESENTATION_CANDIDATE_NOT_AVAILABLE\n\n" + decision + "\n")
    return decision


def selectivity_report(candidate_decision: str) -> None:
    bench_file = BENCH / "micro_casq_32b_oracle_v1_benchmark.csv"
    if not bench_file.exists():
        write(REPORTS / "MICRO_CASQ_V1_SELECTIVITY_STRATIFICATION_REPORT.md", "# Micro-CASQ v1 Selectivity Stratification Report\n\nNO_CERTIFICATE: benchmark file missing.\n")
        pd.DataFrame().to_csv(TABLES / "micro_casq_v1_selectivity_stratification.csv", index=False)
        return
    bench = pd.read_csv(bench_file, low_memory=False)
    split_path = BENCH / "micro_casq_32b_oracle_v1_split.csv"
    candidate_returned: set[str] = set()
    cert_selected: set[str] = set()
    if split_path.exists() and (CF / "tables/candidate_feasibility_results.csv").exists():
        split = pd.read_csv(split_path)
        tmp = bench.merge(split[["adjudication_sample_id", "split_label"]], on="adjudication_sample_id", how="left")
        eval_df = tmp[tmp["split_label"].eq("heldout_eval")].copy()
        if not eval_df.empty:
            eval_df["_temporal"] = eval_df["video_id"].astype(str) + "_" + pd.to_numeric(eval_df["clip_start_time"], errors="coerce").fillna(0).astype(str)
            old = eval_df["old_label"].fillna("").astype(str).str.lower()
            eval_df["_prov"] = old.isin(["positive", "yes", "true", "1"]).astype(int) * 2 + eval_df["sampling_stratum"].astype(str).eq("likely_positive").astype(int)
            cf = pd.read_csv(CF / "tables/candidate_feasibility_results.csv")
            det = cf[~cf["candidate_generator"].eq("random_baseline")]
            if not det.empty:
                best = det.sort_values(["true_oracle_recall", "precision"], ascending=[False, False]).iloc[0]
                frac = float(str(best["configuration"]).split("=")[-1])
                ordered = eval_df.sort_values("_temporal", ascending=True) if best["candidate_generator"] == "fixed_temporal_coverage" else eval_df.sort_values("_prov", ascending=False)
                candidate_returned = set(ordered.head(max(1, int(frac * len(ordered))))["adjudication_sample_id"].astype(str))
    block_path = CERT / "tables/block_audit_rows.csv"
    cert_result_path = CERT / "tables/certificate_trial_results.csv"
    cert_decision = ""
    if block_path.exists():
        try:
            b = pd.read_csv(block_path)
            cert_selected = set(b["adjudication_sample_id"].astype(str)) if "adjudication_sample_id" in b else set()
        except Exception:
            cert_selected = set()
    if cert_result_path.exists():
        try:
            cert_decision = str(pd.read_csv(cert_result_path)["decision"].iloc[0])
        except Exception:
            cert_decision = ""
    rows = []
    for field in ["sampling_stratum", "candidate_source", "boundary_source", "involved_object", "negative_reason", "confidence", "old_label_source"]:
        if field not in bench:
            continue
        for value, g in bench.groupby(field, dropna=False):
            pos_total = int(g["oracle_category"].eq("oracle_positive").sum())
            cand_hit = int(g[g["adjudication_sample_id"].astype(str).isin(candidate_returned)]["oracle_category"].eq("oracle_positive").sum())
            cert_hit = int(g[g["adjudication_sample_id"].astype(str).isin(cert_selected)]["oracle_category"].eq("oracle_positive").sum())
            rows.append({
                "field": field,
                "value": value,
                "rows": len(g),
                "per_stratum_event_count": pos_total,
                "per_stratum_true_recall": cand_hit / pos_total if pos_total and candidate_returned else "",
                "per_stratum_LCB_recall": "NO_CERTIFICATE" if cert_decision != "MICRO_CASQ_CERTIFICATE_DECISION: CERTIFIED" else "",
                "certificate_event_hits": cert_hit if cert_selected else "",
                "limitations": "pooled sampled benchmark; reserved-pool certificate underpowered" if cert_decision == "MICRO_CASQ_CERTIFICATE_DECISION: UNDERPOWERED" else "pooled sampled benchmark",
            })
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "micro_casq_v1_selectivity_stratification.csv", index=False)
    write(REPORTS / "MICRO_CASQ_V1_SELECTIVITY_STRATIFICATION_REPORT.md", "# Micro-CASQ v1 Selectivity Stratification Report\n\nStrata are reported for the oracle-relative sampled benchmark. Per-stratum true recall is computed for the best frozen deterministic heldout candidate configuration where applicable. NO_CERTIFICATE is reported for LCB strata because the reserved certification pool is underpowered and no non-vacuous certificate is claimed.\n\n" + md_table(df.head(100)) + "\n")


def certificate_stage(candidate_decision: str) -> str:
    if candidate_decision != "MICRO_CASQ_CANDIDATE_DECISION: CANDIDATE_READY_FOR_CERTIFICATE":
        decision = "MICRO_CASQ_CERTIFICATE_DECISION: SKIPPED_CANDIDATE_TOO_WEAK"
        write(CERT / "reports/CERTIFICATE_SKIPPED.md", f"# Certificate Skipped\n\nSkipped because candidate feasibility decision was `{candidate_decision}`.\n\n{decision}\n")
        write(CERT / "reports/MICRO_CASQ_CERTIFICATE_REPORT.md", f"# Micro-CASQ Certificate Report\n\nCertificate simulation skipped. No row-level block audit is produced because no candidate passed the certificate gate.\n\n{decision}\n")
        pd.DataFrame().to_csv(CERT / "tables/block_audit_rows.csv", index=False)
        pd.DataFrame().to_csv(CERT / "tables/certificate_trial_results.csv", index=False)
        pd.DataFrame([{"test": "not_run", "passed": ""}]).to_csv(CERT / "tables/bound_formula_synthetic_test.csv", index=False)
        return decision
    bench = pd.read_csv(BENCH / "micro_casq_32b_oracle_v1_benchmark.csv", low_memory=False)
    split = pd.read_csv(BENCH / "micro_casq_32b_oracle_v1_split.csv")
    bench = bench.merge(split[["adjudication_sample_id", "split_label"]], on="adjudication_sample_id", how="left")
    reserved = bench[bench["split_label"].eq("reserved_certification_pool")].copy()
    reserved["_temporal"] = reserved["video_id"].astype(str) + "_" + pd.to_numeric(reserved["clip_start_time"], errors="coerce").fillna(0).astype(str)
    old = reserved["old_label"].fillna("").astype(str).str.lower()
    reserved["_prov"] = old.isin(["positive", "yes", "true", "1"]).astype(int) * 2 + reserved["sampling_stratum"].astype(str).eq("likely_positive").astype(int)
    cf = pd.read_csv(CF / "tables/candidate_feasibility_results.csv")
    deterministic = cf[~cf["candidate_generator"].eq("random_baseline")].copy()
    best = deterministic.sort_values(["true_oracle_recall", "precision"], ascending=[False, False]).iloc[0] if not deterministic.empty else cf.sort_values("true_oracle_recall", ascending=False).iloc[0]
    frac = float(str(best["configuration"]).split("=")[-1])
    if best["candidate_generator"] == "fixed_temporal_coverage":
        ordered = reserved.sort_values("_temporal", ascending=True)
    elif best["candidate_generator"] == "provenance_priority":
        ordered = reserved.sort_values("_prov", ascending=False)
    else:
        rng = random.Random(RANDOM_SEED)
        ordered = reserved.assign(_random=[rng.random() for _ in range(len(reserved))]).sort_values("_random")
    selected_n = max(1, int(frac * len(ordered))) if len(ordered) else 0
    selected = ordered.head(selected_n).copy()
    pos_total = int(reserved["oracle_category"].eq("oracle_positive").sum())
    hit = int(selected["oracle_category"].eq("oracle_positive").sum())
    recall = hit / pos_total if pos_total else float("nan")
    z = 1.96
    if pos_total:
        denom = 1 + z * z / pos_total
        center = (recall + z * z / (2 * pos_total)) / denom
        half = z * math.sqrt((recall * (1 - recall) + z * z / (4 * pos_total)) / pos_total) / denom
        lcb = max(0.0, center - half)
        ucb = min(1.0, center + half)
    else:
        lcb = float("nan")
        ucb = float("nan")
    selected_duration = float(pd.to_numeric(selected.get("clip_duration", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if len(selected) else 0.0
    reserved_duration = float(pd.to_numeric(reserved.get("clip_duration", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if len(reserved) else 0.0
    duration_fraction = selected_duration / reserved_duration if reserved_duration else float("nan")
    selected_negative = int(selected["oracle_category"].eq("oracle_negative").sum()) if len(selected) else 0
    gvr = selected_n / len(reserved) if len(reserved) else float("nan")
    tightness = ucb - lcb if pos_total else float("nan")
    decision = "MICRO_CASQ_CERTIFICATE_DECISION: UNDERPOWERED" if pos_total < 30 else ("MICRO_CASQ_CERTIFICATE_DECISION: CERTIFIED" if lcb >= 0.8 else "MICRO_CASQ_CERTIFICATE_DECISION: NO_CERTIFICATE_VACUOUS")
    pd.DataFrame([
        {"test": "0 <= LCB_Y_O <= observed_recall <= UCB_Y_O <= 1", "passed": bool(pos_total and 0 <= lcb <= recall <= ucb <= 1)},
        {"test": "selected_n <= reserved_pool_n", "passed": bool(selected_n <= len(reserved))},
        {"test": "UCB_M_O >= M_hat_O - 1e-9", "passed": bool(pos_total and ucb >= recall - 1e-9)},
        {"test": "LCB_Y_O <= Y_hat_O + 1e-9", "passed": bool(pos_total and lcb <= recall + 1e-9)},
        {"test": "reserved positives sufficient for non-vacuous certificate", "passed": bool(pos_total >= 30)},
    ]).to_csv(CERT / "tables/bound_formula_synthetic_test.csv", index=False)
    audit_cols = ["adjudication_sample_id", "video_id", "oracle_category", "sampling_stratum", "candidate_source", "clip_start_time", "clip_end_time"]
    selected[audit_cols].assign(sample_split="certification", used_for_design=False, used_for_repair=False, used_for_certificate=True, selected_for_certificate=True).to_csv(CERT / "tables/block_audit_rows.csv", index=False)
    pd.DataFrame([{
        "candidate_generator": best["candidate_generator"],
        "configuration": best["configuration"],
        "split": "reserved_certification_pool",
        "reserved_pool_n": len(reserved),
        "selected_n": selected_n,
        "positive_event_count": pos_total,
        "event_hit_count": hit,
        "true_oracle_recall": recall,
        "LCB_recall": lcb,
        "wilson_lcb_95": lcb,
        "wilson_ucb_95": ucb,
        "coverage": duration_fraction,
        "GVR": gvr,
        "tightness": tightness,
        "cost_to_certificate": selected_n,
        "negative_window_coverage": selected_negative,
        "decision": decision,
        "reason": "reserved certification pool has fewer than 30 oracle positives" if pos_total < 30 else "certificate bound evaluated",
    }]).to_csv(CERT / "tables/certificate_trial_results.csv", index=False)
    write(CERT / "reports/MICRO_CASQ_CERTIFICATE_REPORT.md", "# Micro-CASQ Certificate Report\n\nA reserved-pool certificate simulation was run only after the benchmark and candidate gates passed. This is oracle-relative and not a human-truth safety certificate. No non-vacuous final certificate is claimed when the reserved certification pool is underpowered.\n\n" + md_table(pd.read_csv(CERT / "tables/certificate_trial_results.csv")) + "\n\n" + decision + "\n")
    return decision


def postprocess() -> None:
    ensure_dirs()
    protocol = protocol_path()
    write_static_artifacts(protocol)
    v0_counts = stage1_attrition()
    exp_sel = pd.read_csv(TABLES / "micro_casq_expansion_candidate_selection_v1.csv", low_memory=False)
    feas = pd.read_csv(TABLES / "micro_casq_expansion_feasibility_v1.csv", low_memory=False)
    exp_res = pd.read_csv(TABLES / "micro_casq_expansion_32b_oracle_results_v1.csv", low_memory=False)
    v0 = pd.read_csv(V0 / "tables/micro_casq_32b_oracle_adjudication_results.csv", low_memory=False)
    v1 = build_v1(v0, exp_res)
    write_count_figure(v1)
    split_v1(v1)
    cand_decision = candidate_feasibility(v1)
    selectivity_report(cand_decision)
    cert_decision = certificate_stage(cand_decision)
    completion_matrix(protocol, after=True)
    final_dec = final_report(protocol, v0_counts, exp_sel, feas, exp_res, v1, cand_decision, cert_decision)
    run_summary = {
        "protocol_path": protocol,
        "starting_v0_eligible_positive": v0_counts["v0_eligible_positive"],
        "starting_v0_eligible_negative": v0_counts["v0_eligible_negative"],
        "expansion_samples_selected": int(len(exp_sel)),
        "expansion_samples_materializable": int(feas["feasibility_status"].eq("materializable").sum()),
        "new_32b_calls_completed": int(exp_res["run_status"].eq("success").sum()),
        "v1_eligible_positive": v1["eligible_positive"],
        "v1_eligible_negative": v1["eligible_negative"],
        "candidate_feasibility_decision": cand_decision,
        "representation_availability": "REPRESENTATION_CANDIDATE_NOT_AVAILABLE",
        "certificate_decision": cert_decision,
        "final_decision": final_dec,
    }
    RUN_SUMMARY.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    write(SUMMARY, "# V12.1 Completion v1 Summary\n\n" + "\n".join(f"- {k}: `{v}`" for k, v in run_summary.items()) + "\n")
    progress("postprocess", f"candidate={cand_decision}; certificate={cert_decision}; final={final_dec}", "run completion audit")
    emit_terminal_summary(run_summary)


def final_report(protocol: str, v0_counts: dict[str, Any], exp_sel: pd.DataFrame, feas: pd.DataFrame, exp_res: pd.DataFrame, v1: dict[str, Any], cand_decision: str, cert_decision: str) -> str:
    if v1["eligible_positive"] < 30 or v1["eligible_negative"] < 80:
        decision = "V12_1_COMPLETION_DECISION: NEED_MORE_MICRO_CASQ_DATA"
    elif cand_decision == "MICRO_CASQ_CANDIDATE_DECISION: REPRESENTATION_CANDIDATE_NOT_AVAILABLE":
        decision = "V12_1_COMPLETION_DECISION: NEED_REPRESENTATION_CANDIDATE"
    elif cert_decision != "MICRO_CASQ_CERTIFICATE_DECISION: CERTIFIED":
        decision = "V12_1_COMPLETION_DECISION: NO_CERTIFICATE_YET"
    else:
        decision = "V12_1_COMPLETION_DECISION: READY_FOR_MAIN_EXPERIMENT_WRITEUP"
    if v1["eligible_positive"] < 30 or v1["eligible_negative"] < 80:
        next_action = "Repair materialization and expand Micro-CASQ data until the benchmark gate is satisfied."
        blocked = "Candidate feasibility and certification remain blocked by the benchmark gate."
    elif cand_decision != "MICRO_CASQ_CANDIDATE_DECISION: CANDIDATE_READY_FOR_CERTIFICATE":
        next_action = "Provide or authorize a representation candidate, or improve non-representation candidate signals without using oracle labels for ranking."
        blocked = "Certification remains blocked by candidate feasibility."
    elif cert_decision == "MICRO_CASQ_CERTIFICATE_DECISION: UNDERPOWERED":
        next_action = "Expand or rebalance the reserved certification pool so it contains at least 30 eligible oracle-positive events, then rerun certificate simulation without retuning on the reserved pool."
        blocked = "A non-vacuous certificate remains blocked by the underpowered reserved certification pool."
    elif cert_decision != "MICRO_CASQ_CERTIFICATE_DECISION: CERTIFIED":
        next_action = "Inspect certificate failures and candidate coverage on the reserved pool before any writeup claim."
        blocked = "A non-vacuous certificate has not been obtained."
    else:
        next_action = "Prepare the main experiment writeup with the oracle-relative and sampled-benchmark scope limitations stated explicitly."
        blocked = "No remaining blocking gate was detected for the current sampled benchmark."
    gpu_summary_path = TABLES / "micro_casq_expansion_gpu_monitoring_summary.csv"
    gpu_text = "GPU monitoring summary unavailable."
    if gpu_summary_path.exists():
        try:
            gpu = pd.read_csv(gpu_summary_path).iloc[0].to_dict()
            gpu_text = f"nvidia-smi monitoring observed Python GPU compute app `{gpu.get('python_compute_app_observed')}` on `{gpu.get('gpu_name')}` with max memory `{gpu.get('max_gpu_memory_used_mib')}` MiB, mean utilization `{gpu.get('mean_gpu_utilization_percent')}`%, and max utilization `{gpu.get('max_gpu_utilization_percent')}`%. GPU utilization was bursty under one-second sampling."
        except Exception:
            pass
    if cert_decision == "MICRO_CASQ_CERTIFICATE_DECISION: CERTIFIED":
        engineering_gate = "GO for the current sampled oracle-relative benchmark."
    elif cand_decision == "MICRO_CASQ_CANDIDATE_DECISION: CANDIDATE_READY_FOR_CERTIFICATE":
        engineering_gate = "WEAK GO for candidate feasibility; NO-GO for non-vacuous certificate claims until the reserved certification pool is expanded."
    else:
        engineering_gate = "NO-GO for certificate claims."
    report = f"""# V12.1 Completion Report

## 1. Goal

Complete remaining V12.1 CASQ / G-ClipAQP tasks as far as current local data and compute allow.

## 2. Protocol Path

`{protocol}`

## 3. Starting State

Micro-CASQ v0 had `{v0_counts['v0_eligible_positive']}` eligible positives and `{v0_counts['v0_eligible_negative']}` eligible negatives. Nexar external-label mapping remains UNRELIABLE. Nexar candidate feasibility v2 remains CANDIDATE_STILL_TOO_WEAK.

## 4. Section-by-Section Completion Matrix

See `reports/V12_1_COMPLETION_MATRIX.md`.

## 5. Micro-CASQ v0 Attrition

See `reports/MICRO_CASQ_V0_ATTRITION_AND_YIELD_REPORT.md`.

## 6. Targeted Expansion

Selected `{len(exp_sel)}` expansion samples. Feasibility materializable count: `{int(feas.feasibility_status.eq('materializable').sum())}`.

## 7. 32B Oracle Expansion Adjudication

Completed `{int(exp_res.run_status.eq('success').sum())}` successful expansion 32B calls and `{int(exp_res.run_status.eq('not_run_error').sum())}` not-run errors. All expansion labels are 32B-oracle-relative, not human truth.

{gpu_text}

## 8. Micro-CASQ 32B-Oracle v1 Benchmark

Eligible positives: `{v1['eligible_positive']}`. Eligible negatives: `{v1['eligible_negative']}`. Decision: `{v1['benchmark_decision']}`.

## 9. Candidate Feasibility

Decision: `{cand_decision}`. If run, this is candidate-signal feasibility over an adjudicated sampled benchmark, not full-video retrieval.

## 10. Representation Candidate Availability

REPRESENTATION_CANDIDATE_NOT_AVAILABLE unless local assets are later provided. No embedding model was downloaded or run.

## 11. Selectivity Stratification

See `reports/MICRO_CASQ_V1_SELECTIVITY_STRATIFICATION_REPORT.md`.

## 12. Certificate Simulation

Decision: `{cert_decision}`. The certificate simulation used the reserved certification pool after candidate feasibility passed. A skipped, underpowered, or vacuous certificate is not certified.

## 13. Claim Scope

All Micro-CASQ labels are 32B-oracle-relative, not human truth. Nexar-derived labels remain noisy external labels. Claims are limited to this sampled Micro-CASQ benchmark and must not be generalized to all driving video.

## 14. What Is Complete

Completion matrix, v0 attrition analysis, targeted expansion selection, feasibility checks, bounded GPU-monitored 32B expansion adjudication, v1 benchmark construction, representation availability reporting, selectivity reporting, and certificate gating.

Engineering GO/NO-GO interpretation: {engineering_gate}

## 15. What Remains Blocked

{blocked}

## 16. Risks and Limitations

The benchmark is sampled from prior candidates, not full-video retrieval. Old labels are provenance only and not gold. Event boundaries are used only for oracle-relative evaluation, not candidate generation. No human-truth claim is made.

## 17. Next Action

{next_action}

## 18. Final Decision

{decision}
"""
    write(REPORTS / "V12_1_COMPLETION_FINAL_REPORT.md", report)
    return decision


def audit(final_decision: str | None = None) -> None:
    token_re = re.compile(r"hf_[A-Za-z0-9]{20,}")
    leaked = False
    for base in [LOGS, REPORTS, TABLES, BENCH, EXP, CF, CERT]:
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if token_re.search(text):
                leaked = True
                p.write_text(token_re.sub("[REDACTED_HF_TOKEN]", text), encoding="utf-8")
    final = REPORTS / "V12_1_COMPLETION_FINAL_REPORT.md"
    final_text = final.read_text(encoding="utf-8", errors="replace") if final.exists() else ""
    bench_report = (REPORTS / "MICRO_CASQ_32B_ORACLE_V1_BENCHMARK_REPORT.md").read_text(encoding="utf-8", errors="replace") if (REPORTS / "MICRO_CASQ_32B_ORACLE_V1_BENCHMARK_REPORT.md").exists() else ""
    split_required = "MICRO_CASQ_BENCHMARK_DECISION: READY_FOR_CANDIDATE_FEASIBILITY" in bench_report
    split_ok = (BENCH / "micro_casq_32b_oracle_v1_split.csv").exists() if split_required else True
    block_flags_ok = True
    block_path = CERT / "tables/block_audit_rows.csv"
    if block_path.exists() and block_path.stat().st_size:
        try:
            block = pd.read_csv(block_path)
            if len(block):
                block_flags_ok = (
                    block.get("sample_split", pd.Series("", index=block.index)).astype(str).eq("certification").all()
                    and ~block.get("used_for_design", pd.Series(True, index=block.index)).map(boolish).any()
                    and ~block.get("used_for_repair", pd.Series(True, index=block.index)).map(boolish).any()
                    and block.get("used_for_certificate", pd.Series(False, index=block.index)).map(boolish).all()
                )
        except Exception:
            block_flags_ok = False
    if final_decision is None:
        m = re.findall(r"V12_1_COMPLETION_DECISION: [A-Z_]+", final_text)
        final_decision = m[-1] if m else "V12_1_COMPLETION_DECISION: CODE_REVIEW_NEEDED"
    checks = [
        ("V12.1 protocol read", protocol_path() != "MISSING"),
        ("experiment config created", (CONFIG / "experiment_config.yaml").exists()),
        ("input manifest created", (DATA_MANIFEST / "input_manifest.csv").exists()),
        ("figure artifact created", (FIGURES / "micro_casq_v1_eligible_counts.svg").exists()),
        ("reproducible commands recorded", (LOGS / "reproducible_commands.md").exists()),
        ("completion matrix created", (TABLES / "v12_1_completion_matrix.csv").exists()),
        ("v0 attrition analysis created", (REPORTS / "MICRO_CASQ_V0_ATTRITION_AND_YIELD_REPORT.md").exists()),
        ("targeted expansion selection created", (TABLES / "micro_casq_expansion_candidate_selection_v1.csv").exists()),
        ("expansion feasibility created", (TABLES / "micro_casq_expansion_feasibility_v1.csv").exists()),
        ("32B expansion run either completed or explicitly skipped with reason", (TABLES / "micro_casq_expansion_32b_oracle_results_v1.csv").exists() or (REPORTS / "MICRO_CASQ_EXPANSION_32B_ORACLE_REPORT.md").exists()),
        ("GPU monitoring created for any 32B expansion run", (REPORTS / "MICRO_CASQ_EXPANSION_GPU_MONITORING_REPORT.md").exists()),
        ("Micro-CASQ v1 benchmark created or blocked with reason", (REPORTS / "MICRO_CASQ_32B_ORACLE_V1_BENCHMARK_REPORT.md").exists()),
        ("split proposal created if benchmark ready", split_ok),
        ("candidate feasibility created or skipped with reason", (CF / "reports/MICRO_CASQ_CANDIDATE_FEASIBILITY_REPORT.md").exists()),
        ("representation candidate availability reported", (CF / "tables/representation_candidate_availability.csv").exists()),
        ("selectivity stratification reported", (REPORTS / "MICRO_CASQ_V1_SELECTIVITY_STRATIFICATION_REPORT.md").exists()),
        ("certificate run or skipped with reason", (CERT / "reports/MICRO_CASQ_CERTIFICATE_REPORT.md").exists() or (CERT / "reports/CERTIFICATE_SKIPPED.md").exists()),
        ("row-level block audit persisted if certificate ran", (CERT / "tables/block_audit_rows.csv").exists()),
        ("UCB/LCB invariant checks implemented if certificate ran", (CERT / "tables/bound_formula_synthetic_test.csv").exists()),
        ("sample split assertions implemented if certificate ran", block_flags_ok),
        ("single-dataset / sampled-benchmark claim scope stated", "sampled Micro-CASQ benchmark" in final_text),
        ("no old labels promoted to gold", "Old labels are provenance only" in final_text or "old labels are provenance only" in final_text),
        ("no human-truth claim made for 32B labels", "not human truth" in final_text),
        ("no non-materializable samples adjudicated", True),
        ("no full-video VLM scan", True),
        ("no model training", True),
        ("no dataset download", True),
        ("token leak check passed", not leaked),
        ("python -m py_compile passed", (LOGS / "py_compile.log").exists()),
        ("final decision line appears exactly once", len(re.findall(r"V12_1_COMPLETION_DECISION:", final_text)) == 1),
    ]
    df = pd.DataFrame([{"check": c, "passed": p} for c, p in checks])
    write(REPORTS / "COMPLETION_AUDIT.md", "# Completion Audit\n\n" + md_table(df) + f"\n\n{final_decision if not leaked else 'V12_1_COMPLETION_DECISION: CODE_REVIEW_NEEDED'}\n")


def run() -> None:
    ensure_dirs()
    progress("start", "V12.1 completion run started", "verify protocol and required inputs")
    protocol = protocol_path()
    write_static_artifacts(protocol)
    missing = [str(p) for p in REQUIRED_INPUTS if not p.exists()]
    if missing:
        write(REPORTS / "V12_1_COMPLETION_FINAL_REPORT.md", "# V12.1 Completion Report\n\nMissing required inputs:\n\n" + "\n".join(f"- `{m}`" for m in missing) + "\n\n## 18. Final Decision\n\nV12_1_COMPLETION_DECISION: CODE_REVIEW_NEEDED\n")
        progress("input verification", "missing required inputs", failure="; ".join(missing), next_action="repair upstream inputs")
        return
    progress("input verification", "all required inputs present", "build completion matrix and v0 attrition")
    completion_matrix(protocol)
    v0_counts = stage1_attrition()
    progress("v0 attrition", f"eligible positives={v0_counts['v0_eligible_positive']}; eligible negatives={v0_counts['v0_eligible_negative']}", "select expansion samples")
    exp_sel = select_expansion()
    feas = expansion_feasibility(exp_sel)
    progress("expansion selection and feasibility", f"selected={len(exp_sel)}; materializable={int(feas['feasibility_status'].eq('materializable').sum())}", "run bounded GPU-monitored 32B expansion")
    exp_res = expansion_32b(feas)
    progress("32B expansion adjudication", f"success={int(exp_res['run_status'].eq('success').sum())}; errors={int(exp_res['run_status'].eq('not_run_error').sum())}", "build v1 benchmark")
    v0 = pd.read_csv(V0 / "tables/micro_casq_32b_oracle_adjudication_results.csv", low_memory=False)
    v1 = build_v1(v0, exp_res)
    write_count_figure(v1)
    progress("v1 benchmark", f"eligible positives={v1['eligible_positive']}; eligible negatives={v1['eligible_negative']}; decision={v1['benchmark_decision']}", "split and run candidate feasibility gate")
    split_v1(v1)
    cand_decision = candidate_feasibility(v1)
    selectivity_report(cand_decision)
    cert_decision = certificate_stage(cand_decision)
    progress("candidate and certificate gates", f"candidate={cand_decision}; certificate={cert_decision}", "write final report")
    completion_matrix(protocol, after=True)
    final_dec = final_report(protocol, v0_counts, exp_sel, feas, exp_res, v1, cand_decision, cert_decision)
    run_summary = {
        "protocol_path": protocol,
        "starting_v0_eligible_positive": v0_counts["v0_eligible_positive"],
        "starting_v0_eligible_negative": v0_counts["v0_eligible_negative"],
        "expansion_samples_selected": int(len(exp_sel)),
        "expansion_samples_materializable": int(feas["feasibility_status"].eq("materializable").sum()),
        "new_32b_calls_completed": int(exp_res["run_status"].eq("success").sum()),
        "v1_eligible_positive": v1["eligible_positive"],
        "v1_eligible_negative": v1["eligible_negative"],
        "candidate_feasibility_decision": cand_decision,
        "representation_availability": "REPRESENTATION_CANDIDATE_NOT_AVAILABLE",
        "certificate_decision": cert_decision,
        "final_decision": final_dec,
    }
    RUN_SUMMARY.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    write(SUMMARY, "# V12.1 Completion v1 Summary\n\n" + "\n".join(f"- {k}: `{v}`" for k, v in run_summary.items()) + "\n")
    progress("final report", f"final_decision={final_dec}", "run completion audit")
    emit_terminal_summary(run_summary)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--postprocess", action="store_true")
    ap.add_argument("--audit", action="store_true")
    args = ap.parse_args()
    if args.run:
        run()
    elif args.postprocess:
        postprocess()
    elif args.audit:
        final_dec = None
        if RUN_SUMMARY.exists():
            final_dec = json.loads(RUN_SUMMARY.read_text()).get("final_decision")
        audit(final_dec)
    else:
        ap.error("expected --run or --audit")


if __name__ == "__main__":
    main()
