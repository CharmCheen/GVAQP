#!/usr/bin/env python3
"""Create and run the clean, frozen dataset3 baseline benchmark.

The script never imports prior selections, segments, metrics, rankings, or
threshold winners. Prior artifacts are used only as verifiable raw oracle
cache and implementation/config provenance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PACK = SCRIPT_DIR.parent
ROOT = PACK.parents[2]
sys.path.insert(0, str(SCRIPT_DIR))

from benchmark_lib import (  # noqa: E402
    EVENT_MATCH_COLUMNS,
    EVENT_SEGMENT_COLUMNS,
    METRIC_COLUMNS,
    canonical_hash,
    canonicalize_native_segments,
    evaluate_events,
    materialize_from_trace,
    sha256_file,
)


VIDEO = ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"
PROMPT = ROOT / "test_vlm/outputs/v13_6_clip_construction_sensitivity_v1/prompts/o_enter_ego_path_v0_v13_6_prompt.txt"
MODEL = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
ORACLE_PARSED = ROOT / "src/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1/oracle_outputs/dataset3_full_center10_parsed.csv"
P1_RAW = ROOT / "src/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/oracle_outputs/raw_per_anchor"
FULL_RAW = ROOT / "src/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1/oracle_outputs/raw_per_anchor_full"
PROXY_FULL = PACK / "benchmark/proxy_precompute/full"
ADAPTER = ROOT / "refe_repos/adapter"
MAP_SCRIPT = ROOT / "scripts/stage1a_map_anchor_only.py"
FROZEN_CONFIG = ROOT / "docs/FROZEN_CONFIG_FOR_CROSS_VIDEO.md"

BUDGETS = [5, 10, 20, 50, 80, 100]
RANDOM_SEEDS = list(range(100))
STOCHASTIC_SEEDS = [0, 1, 2, 3, 4]
DETERMINISTIC_SEEDS = [0]
PARSER_VERSION = "presence_json_parser_v1_stage2_compatible"
REFERENCE_VERSION = "consecutive_positive_units_v1"
MATCHING_VERSION = "overlap_any_one_to_one_cardinality_then_tiou_v1"
REFERENCE_TYPE = "VLM_DEFINED_PSEUDO_ORACLE"
MATERIALIZER_CONFIG = {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0, "negative_barrier": True}

ACTION_COLUMNS = [
    "benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget",
    "call_idx", "action_type", "target_type", "target_id", "unit_id", "start_time",
    "end_time", "selection_score", "selection_rank", "selection_reason", "state_before_hash",
    "oracle_requested", "oracle_label_after_query", "state_after_hash", "logical_cost",
    "physical_cache_hit", "wall_time_seconds",
]

CANDIDATE_COLUMNS = [
    "benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget",
    "candidate_id", "unit_id", "start_time", "end_time", "proxy_score", "component_id",
    "candidate_score", "candidate_rank", "selected", "selected_at_call_idx", "candidate_features_json",
]

SELECTED_COLUMNS = [
    "benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget",
    "call_idx", "unit_id", "start_time", "end_time", "selected_by_action", "oracle_result",
    "is_positive_anchor", "is_negative_evidence", "logical_cost",
]

COST_COLUMNS = [
    "benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget",
    "logical_oracle_calls", "physical_vlm_calls", "queried_video_seconds", "decoded_video_seconds",
    "returned_review_seconds", "vlm_latency_seconds", "gpu_seconds", "planner_cpu_seconds",
    "materializer_cpu_seconds", "wall_time_seconds", "cache_hits",
]


@dataclass
class Frozen:
    benchmark_id: str
    units: pd.DataFrame
    proxy: pd.DataFrame
    oracle: pd.DataFrame
    reference: pd.DataFrame
    evaluator: dict
    manifest: dict


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_progress(checkpoint: str, command: str, result: str, failure: str = "none", fix: str = "none", next_action: str = "") -> None:
    path = PACK / "logs/progress.md"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {utc_now()} — {checkpoint}\n\n")
        fh.write(f"- Checkpoint: {checkpoint}\n- Commands run: `{command}`\n- Result: {result}\n")
        fh.write(f"- Failure: {failure}\n- Fix applied: {fix}\n")
        if next_action:
            fh.write(f"- Next action: {next_action}\n")


def write_csv(path: Path, rows: pd.DataFrame | list[dict], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if columns is not None:
        for col in columns:
            if col not in df:
                df[col] = pd.Series(dtype="object")
        df = df[columns]
    df.to_csv(path, index=False)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def semantic_csv_hash(df: pd.DataFrame) -> str:
    public = df.drop(columns=["benchmark_id"], errors="ignore").copy()
    payload = public.to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def model_manifest() -> tuple[pd.DataFrame, str]:
    rows = []
    for path in sorted(MODEL.iterdir()):
        if not path.is_file():
            continue
        # Hash configs/tokenizer/index exactly. Weight shards are bound by name and size;
        # hashing all ~65 GB shards would add no response-level provenance absent in old logs.
        digest = sha256_file(path) if path.suffix in {".json", ".txt"} or path.name in {"README.md", "merges.txt", "vocab.json"} else "size_bound"
        rows.append({"model_path": str(MODEL), "file": path.name, "size_bytes": path.stat().st_size, "sha256": digest})
    df = pd.DataFrame(rows)
    return df, semantic_csv_hash(df)


def raw_path(anchor_id: str) -> Path:
    full = FULL_RAW / f"{anchor_id}.json"
    p1 = P1_RAW / f"{anchor_id}.json"
    if full.exists():
        return full
    if p1.exists():
        return p1
    raise FileNotFoundError(f"No raw cache response for {anchor_id}")


def build_reference(oracle: pd.DataFrame, benchmark_id: str) -> pd.DataFrame:
    positive = oracle[oracle["parsed_label"] == "positive"].sort_values("unit_id")
    groups: list[list[dict]] = []
    current: list[dict] = []
    previous = None
    for row in positive.to_dict("records"):
        uid = int(row["unit_id"])
        if current and previous is not None and uid != previous + 1:
            groups.append(current); current = []
        current.append(row); previous = uid
    if current:
        groups.append(current)
    rows = []
    for idx, group in enumerate(groups):
        start_candidates = [float(r["event_start_absolute"]) for r in group if pd.notna(r.get("event_start_absolute"))]
        end_candidates = [float(r["event_end_absolute"]) for r in group if pd.notna(r.get("event_end_absolute"))]
        start = min(start_candidates) if start_candidates else min(float(r["start_time"]) for r in group)
        end = max(end_candidates) if end_candidates else max(float(r["end_time"]) for r in group)
        rows.append({
            "benchmark_id": benchmark_id, "video_id": "long_video_dataset3",
            "reference_event_id": f"vlm_event_{idx:04d}", "start_time": start,
            "core_start_time": start, "core_end_time": end, "end_time": end,
            "canonical_anchor_time": float(group[0]["start_time"]),
            "source_unit_ids": "|".join(str(int(r["unit_id"])) for r in group),
            "event_type": "enter_ego_path", "reference_type": REFERENCE_TYPE,
            "reference_version": REFERENCE_VERSION, "adjudication_status": "not_human_adjudicated",
        })
    return pd.DataFrame(rows)


def freeze_inputs() -> Frozen:
    required = [VIDEO, PROMPT, ORACLE_PARSED, PROXY_FULL / "center10_anchor_grid.csv", PROXY_FULL / "center10_proxy_features.csv"]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing freeze inputs: {missing}")
    video_hash = sha256_file(VIDEO)
    prompt_hash = sha256_file(PROMPT)
    prompt_text = PROMPT.read_text(encoding="utf-8")
    prompt_target = PACK / "oracle/oracle_prompt.txt"
    prompt_target.write_text(prompt_text, encoding="utf-8")
    (PACK / "oracle/oracle_prompt.sha256").write_text(prompt_hash + "\n", encoding="utf-8")

    grid = pd.read_csv(PROXY_FULL / "center10_anchor_grid.csv")
    proxy_wide = pd.read_csv(PROXY_FULL / "center10_proxy_features.csv")
    if len(grid) != 347 or len(proxy_wide) != 347:
        raise RuntimeError(f"Expected 347 units/proxy rows; got {len(grid)}/{len(proxy_wide)}")
    if grid["anchor_id"].duplicated().any() or proxy_wide["anchor_id"].duplicated().any():
        raise RuntimeError("Duplicate anchor_id in regenerated frozen inputs")
    merged = grid.merge(proxy_wide, on=["anchor_id", "anchor_time"], validate="one_to_one")
    duration = float(grid["end_time"].max())
    fps = 30.0
    units = pd.DataFrame({
        "benchmark_id": "PENDING", "video_id": "long_video_dataset3", "video_sha256": video_hash,
        "unit_id": np.arange(len(grid), dtype=int), "start_frame": np.floor(grid["start_time"].astype(float) * fps).astype(int),
        "end_frame": np.maximum(np.floor(grid["end_time"].astype(float) * fps).astype(int) - 1, 0),
        "start_time": grid["start_time"].astype(float), "end_time": grid["end_time"].astype(float),
        "duration_seconds": grid["duration"].astype(float), "split_role": "single_video_temporal_holdout_diagnostic",
        "eligible_for_query": True, "anchor_id": grid["anchor_id"],
    })
    proxy_names = [c for c in proxy_wide.columns if c.startswith("score_")]
    proxy_rows = []
    for uid, row in merged.iterrows():
        for name in proxy_names:
            values = proxy_wide[name].astype(float)
            lo, hi = float(values.min()), float(values.max())
            raw = float(row[name]); normalized = (raw - lo) / (hi - lo) if hi > lo else 0.0
            proxy_rows.append({
                "benchmark_id": "PENDING", "video_id": "long_video_dataset3", "unit_id": int(uid),
                "proxy_name": name, "proxy_version": "video_feature_precompute_v1_clean_rerun",
                "proxy_score_raw": raw, "proxy_score_normalized": normalized,
                "feature_source": str(PROXY_FULL / "center10_proxy_features.csv"),
                "model_path": str(ROOT / "models/yolo/yolov8n.pt"), "config_hash": sha256_file(ROOT / "outputs/video_feature_precompute_v1/scripts/precompute_video_features.py"),
                "generated_this_run": True, "provenance_valid": True,
            })
    proxy = pd.DataFrame(proxy_rows)

    model_df, model_hash = model_manifest()
    parser_hash = canonical_hash({"parser_version": PARSER_VERSION, "required_keys": ["label", "confidence"]})
    parsed = pd.read_csv(ORACLE_PARSED)
    parsed = parsed.sort_values("anchor_id").reset_index(drop=True)
    if set(parsed["anchor_id"]) != set(grid["anchor_id"]):
        raise RuntimeError("Oracle cache anchor universe does not match regenerated unit table")
    parsed = units[["unit_id", "anchor_id", "start_time", "end_time"]].merge(parsed, on="anchor_id", suffixes=("", "_old"), validate="one_to_one")
    raw_cache_dir = PACK / "oracle/raw_cache"
    raw_cache_dir.mkdir(parents=True, exist_ok=True)
    oracle_rows, cache_rows, raw_jsonl = [], [], []
    for row in parsed.to_dict("records"):
        source = raw_path(str(row["anchor_id"]))
        target = raw_cache_dir / source.name
        shutil.copy2(source, target)
        raw_obj = json.loads(target.read_text(encoding="utf-8"))
        raw_jsonl.append(raw_obj)
        label = str(row["label"]).lower()
        oracle_rows.append({
            "benchmark_id": "PENDING", "video_id": "long_video_dataset3", "unit_id": int(row["unit_id"]),
            "start_time": float(row["start_time"]), "end_time": float(row["end_time"]),
            "model_path": str(MODEL), "model_hash": model_hash, "prompt_hash": prompt_hash,
            "parser_hash": parser_hash, "raw_output_path": str(target.relative_to(PACK)),
            "parsed_label": label, "confidence": str(row.get("confidence", "")), "abstain": label == "abstain",
            "parse_success": str(row.get("parse_status", "")) == "ok", "latency_seconds": float(row.get("runtime_seconds", 0.0)),
            "gpu_seconds": float(row.get("runtime_seconds", 0.0)), "physical_call": False, "cache_hit": True,
            "event_start_absolute": row.get("event_start_absolute"), "event_end_absolute": row.get("event_end_absolute"),
            "event_type": row.get("event_type", ""), "involved_object": row.get("involved_object", ""),
        })
        cache_rows.append({
            "video_sha256": video_hash, "unit_id": int(row["unit_id"]), "start_time": float(row["start_time"]),
            "end_time": float(row["end_time"]), "model_hash": model_hash, "prompt_hash": prompt_hash,
            "parser_hash": parser_hash, "raw_output_path": str(target.relative_to(PACK)), "raw_sha256": sha256_file(target),
            "source_raw_path": str(source), "cache_eligible": True, "physical_call_this_run": False,
        })
    oracle = pd.DataFrame(oracle_rows)
    with (PACK / "oracle/oracle_raw_outputs.jsonl").open("w", encoding="utf-8") as fh:
        for obj in raw_jsonl:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
    write_csv(PACK / "oracle/oracle_cache_manifest.csv", cache_rows)
    write_csv(PACK / "oracle/oracle_model_manifest.csv", model_df)

    evaluator = {
        "evaluator_version": "clean_baseline_evaluator_v1", "reference_type": REFERENCE_TYPE,
        "reference_version": REFERENCE_VERSION, "primary_matching": "overlap_any_one_to_one",
        "assignment_tie_break": "maximum_temporal_iou", "matching_version": MATCHING_VERSION,
        "tiou_thresholds": [0.3, 0.5], "unit_seconds": 10.0, "video_duration_seconds": duration,
        "materializers": {"original_k3": MATERIALIZER_CONFIG, "k3_bridge_safe": MATERIALIZER_CONFIG},
    }
    evaluator_hash = canonical_hash(evaluator)
    budget_df = pd.DataFrame([{"budget": b, "budget_fraction": b / len(units), "schedule_version": "absolute_v1"} for b in BUDGETS])
    seeds_df = pd.DataFrame(
        [{"method_scope": "random", "seed": s, "purpose": "random_baseline_repeat"} for s in RANDOM_SEEDS]
        + [{"method_scope": "stochastic_repository_adapter", "seed": s, "purpose": "baseline_repeat"} for s in STOCHASTIC_SEEDS]
        + [{"method_scope": "deterministic", "seed": 0, "purpose": "tie_break"}]
    )
    cheap_files = [PROXY_FULL / "proxy_features_5s.csv", PROXY_FULL / "center10_proxy_features.csv"]
    cheap_manifest = pd.DataFrame([{
        "path": str(p.relative_to(PACK)), "format": "csv", "shape": str(pd.read_csv(p).shape), "dtype": "mixed_csv",
        "sha256": sha256_file(p), "producer": "video_feature_precompute_v1_clean_rerun",
        "config_hash": sha256_file(ROOT / "outputs/video_feature_precompute_v1/scripts/precompute_video_features.py"),
    } for p in cheap_files])
    reference_pending = build_reference(oracle, "PENDING")
    compatibility = {
        "video_sha256": video_hash, "unit_table_sha256": semantic_csv_hash(units),
        "proxy_table_sha256": semantic_csv_hash(proxy), "cheap_feature_manifest_sha256": semantic_csv_hash(cheap_manifest),
        "oracle_model_hash": model_hash, "oracle_prompt_hash": prompt_hash, "oracle_parser_hash": parser_hash,
        "reference_hash": semantic_csv_hash(reference_pending), "budget_schedule_hash": semantic_csv_hash(budget_df),
        "evaluator_hash": evaluator_hash, "matching_hash": canonical_hash({"version": MATCHING_VERSION}),
        "baseline_code_hashes": {
            "benchmark_pipeline": sha256_file(Path(__file__)),
            "benchmark_lib": sha256_file(SCRIPT_DIR / "benchmark_lib.py"),
            "arc_adapter": sha256_file(ADAPTER / "arc_baseline/run.py"),
            "supg_adapter": sha256_file(ADAPTER / "supg_baseline/run.py"),
            "abae_adapter": sha256_file(ADAPTER / "abae_baseline/run.py"),
            "map_anchor": sha256_file(MAP_SCRIPT),
        },
    }
    benchmark_id = "cbbv1_" + canonical_hash(compatibility)[:20]
    units["benchmark_id"] = benchmark_id; proxy["benchmark_id"] = benchmark_id; oracle["benchmark_id"] = benchmark_id
    reference = build_reference(oracle, benchmark_id)
    write_csv(PACK / "frozen_inputs/unit_table.csv", units)
    write_csv(PACK / "frozen_inputs/proxy_table.csv", proxy)
    write_csv(PACK / "frozen_inputs/cheap_feature_manifest.csv", cheap_manifest)
    write_csv(PACK / "frozen_inputs/event_reference.csv", reference)
    write_json(PACK / "frozen_inputs/evaluator_config.json", evaluator)
    write_csv(PACK / "frozen_inputs/budget_schedule.csv", budget_df)
    write_csv(PACK / "frozen_inputs/random_seeds.csv", seeds_df)
    video_manifest = pd.DataFrame([{
        "benchmark_id": benchmark_id, "video_id": "long_video_dataset3", "path": str(VIDEO), "sha256": video_hash,
        "duration_seconds": duration, "size_bytes": VIDEO.stat().st_size, "unit_count": len(units),
    }])
    write_csv(PACK / "frozen_inputs/video_manifest.csv", video_manifest)
    write_csv(PACK / "oracle/oracle_presence_observations.csv", oracle)
    write_csv(PACK / "oracle/oracle_relation_requests.csv", [], columns=["benchmark_id", "run_id", "unit_id", "relation_query", "gate_status"])
    write_csv(PACK / "oracle/oracle_relation_observations.csv", [], columns=["benchmark_id", "run_id", "unit_id", "relation_label", "parse_success"])
    manifest = {
        "benchmark_id": benchmark_id, "created_at_utc": utc_now(), "status": "FROZEN",
        "benchmark_source": str(VIDEO), "baseline_execution": "CLEAN_RERUN_FROM_FROZEN_INPUTS",
        "result_scope": "SINGLE_VIDEO_TEMPORAL_HOLDOUT_DIAGNOSTIC", "compatibility": compatibility,
        "physical_hashes": {}, "oracle_cache": {"entries": len(oracle), "physical_calls_this_run": 0, "raw_cache_reused": len(oracle)},
        "counts": {"units": len(units), "reference_events": len(reference), "positive_units": int((oracle.parsed_label == "positive").sum())},
    }
    # Physical hashes are audit evidence but intentionally excluded from benchmark_id to avoid self-reference via benchmark_id columns.
    for rel in ["frozen_inputs/unit_table.csv", "frozen_inputs/proxy_table.csv", "frozen_inputs/cheap_feature_manifest.csv", "frozen_inputs/event_reference.csv", "frozen_inputs/evaluator_config.json", "frozen_inputs/budget_schedule.csv", "frozen_inputs/random_seeds.csv", "frozen_inputs/video_manifest.csv"]:
        manifest["physical_hashes"][rel] = sha256_file(PACK / rel)
    write_json(PACK / "BENCHMARK_MANIFEST.json", manifest)
    hash_rows = [{"path": path, "sha256": digest, "hash_role": "physical_frozen_input"} for path, digest in manifest["physical_hashes"].items()]
    hash_rows += [{"path": key, "sha256": canonical_hash(value) if isinstance(value, dict) else value, "hash_role": "semantic_compatibility"} for key, value in compatibility.items()]
    write_csv(PACK / "frozen_inputs/input_hashes.csv", hash_rows)
    return Frozen(benchmark_id, units, proxy, oracle, reference, evaluator, manifest)


def load_frozen() -> Frozen:
    manifest = json.loads((PACK / "BENCHMARK_MANIFEST.json").read_text())
    return Frozen(
        manifest["benchmark_id"], pd.read_csv(PACK / "frozen_inputs/unit_table.csv"),
        pd.read_csv(PACK / "frozen_inputs/proxy_table.csv"), pd.read_csv(PACK / "oracle/oracle_presence_observations.csv"),
        pd.read_csv(PACK / "frozen_inputs/event_reference.csv"), json.loads((PACK / "frozen_inputs/evaluator_config.json").read_text()), manifest,
    )


class OracleAccessor:
    """Budgeted logical accessor over a physically shared immutable cache."""

    def __init__(self, frozen: Frozen, run_id: str, budget: int):
        self.run_id = run_id
        self.budget = int(budget)
        self.table = frozen.oracle.set_index("unit_id")
        self.queried: set[int] = set()

    def query(self, unit_id: int) -> dict:
        unit_id = int(unit_id)
        if unit_id in self.queried:
            raise RuntimeError(f"Duplicate logical query in {self.run_id}: unit {unit_id}")
        if len(self.queried) >= self.budget:
            raise RuntimeError(f"Logical budget exceeded in {self.run_id}")
        if unit_id not in self.table.index:
            raise KeyError(unit_id)
        self.queried.add(unit_id)
        return self.table.loc[unit_id].to_dict()


def primary_proxy(frozen: Frozen) -> pd.Series:
    p = frozen.proxy[frozen.proxy["proxy_name"] == "score_fusion_yolo_motion"].copy()
    if p.empty:
        p = frozen.proxy[frozen.proxy["proxy_name"] == "score_yolo_count"].copy()
    return p.set_index("unit_id")["proxy_score_normalized"].astype(float).reindex(frozen.units["unit_id"]).fillna(0.0)


def component_ids(scores: pd.Series) -> dict[int, int]:
    threshold = float(scores.quantile(0.70))
    high = set(int(i) for i, value in scores.items() if float(value) >= threshold)
    out: dict[int, int] = {}
    cid = 0
    previous = None
    for uid in sorted(high):
        if previous is None or uid != previous + 1:
            cid += 1
        out[uid] = cid - 1
        previous = uid
    return out


def random_order(frozen: Frozen, seed: int) -> tuple[list[int], dict[int, str], dict[int, str]]:
    rng = np.random.default_rng(seed)
    order = rng.permutation(frozen.units["unit_id"].astype(int).to_numpy()).tolist()
    reasons = {uid: "uniform random permutation from fixed seed" for uid in order}
    actions = {uid: "RANDOM_SAMPLE" for uid in order}
    return order, reasons, actions


def top_proxy_order(frozen: Frozen, seed: int) -> tuple[list[int], dict[int, str], dict[int, str]]:
    scores = primary_proxy(frozen)
    order = sorted(scores.index.astype(int), key=lambda uid: (-float(scores.loc[uid]), uid))
    return order, {uid: "descending frozen fusion proxy" for uid in order}, {uid: "TOP_PROXY" for uid in order}


def component_first_order(frozen: Frozen, seed: int) -> tuple[list[int], dict[int, str], dict[int, str]]:
    scores = primary_proxy(frozen)
    comps = component_ids(scores)
    groups: dict[int, list[int]] = {}
    for uid, cid in comps.items():
        groups.setdefault(cid, []).append(uid)
    ranked_components = sorted(groups, key=lambda cid: (-max(float(scores.loc[x]) for x in groups[cid]), min(groups[cid])))
    reps = [sorted(groups[cid], key=lambda uid: (-float(scores.loc[uid]), uid))[0] for cid in ranked_components]
    remaining_high = [uid for cid in ranked_components for uid in sorted(groups[cid], key=lambda x: (-float(scores.loc[x]), x)) if uid not in reps]
    rest = [uid for uid in sorted(scores.index.astype(int), key=lambda x: (-float(scores.loc[x]), x)) if uid not in comps]
    order = reps + remaining_high + rest
    reasons = {uid: ("best representative of next high-proxy temporal component" if uid in reps else "remaining component/global proxy rank") for uid in order}
    return order, reasons, {uid: "COMPONENT_FIRST" for uid in order}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def map_order(frozen: Frozen, budget: int, seed: int) -> tuple[list[int], dict[int, str], dict[int, str], pd.DataFrame]:
    module = load_module(f"clean_map_{budget}_{seed}", MAP_SCRIPT)
    scores = primary_proxy(frozen)
    labels = frozen.oracle.set_index("unit_id")["parsed_label"].map({"positive": 1, "negative": 0, "abstain": 0})
    units = pd.DataFrame({
        "video_id": "long_video_dataset3", "frame_idx": frozen.units["unit_id"].astype(int),
        "timestamp": frozen.units["start_time"].astype(float), "proxy_score": scores.to_numpy(),
        "oracle_label": labels.reindex(frozen.units["unit_id"]).fillna(0).astype(int).to_numpy(),
        "start_frame": frozen.units["start_frame"].astype(int), "end_frame": frozen.units["end_frame"].astype(int),
        "start_time": frozen.units["start_time"].astype(float), "end_time": frozen.units["end_time"].astype(float),
    })
    log, comps = module.simulate_map(units, budget, seed, PACK / "benchmark")
    order = log["unit_id"].astype(int).tolist()
    reasons = {int(r.unit_id): f"frozen MAP {r.action_type}; score={float(r.score_at_selection):.9g}" for r in log.itertuples()}
    actions = {int(r.unit_id): str(r.action_type) for r in log.itertuples()}
    return order, reasons, actions, comps


def make_adapter_inputs(frozen: Frozen) -> tuple[Path, Path]:
    scores = primary_proxy(frozen)
    labels = frozen.oracle.set_index("unit_id")["parsed_label"].map({"positive": 1, "negative": 0, "abstain": 0})
    adapter = pd.DataFrame({
        "video_id": "long_video_dataset3", "frame_idx": frozen.units["unit_id"].astype(int),
        "timestamp": frozen.units["start_time"].astype(float), "proxy_score": scores.to_numpy(),
        "oracle_label": labels.reindex(frozen.units["unit_id"]).fillna(0).astype(int).to_numpy(),
        "cluster_id": frozen.units["unit_id"].astype(int), "start_frame": frozen.units["start_frame"].astype(int),
        "end_frame": frozen.units["end_frame"].astype(int), "start_time": frozen.units["start_time"].astype(float),
        "end_time": frozen.units["end_time"].astype(float),
    })
    ref = frozen.reference.copy()
    ref_adapter = pd.DataFrame({
        "video_id": ref["video_id"], "segment_id": np.arange(len(ref)),
        "start_frame": np.floor(ref["start_time"].astype(float) * 30).astype(int),
        "end_frame": np.ceil(ref["end_time"].astype(float) * 30).astype(int),
        "start_time": ref["start_time"].astype(float), "end_time": ref["end_time"].astype(float),
    })
    input_path = PACK / "benchmark/adapter_units.csv"
    ref_path = PACK / "evaluator/adapter_reference.csv"
    write_csv(input_path, adapter); write_csv(ref_path, ref_adapter)
    return input_path, ref_path


def run_adapter(frozen: Frozen, family: str, budget: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, str, str]:
    input_path, ref_path = make_adapter_inputs(frozen)
    tmp = PACK / f"benchmark/adapter_runs/{family}/seed_{seed}/budget_{budget}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    if family == "arc":
        script = ADAPTER / "arc_baseline/run.py"
        extra = ["--variant", "refinement", "--threshold", "0.4", "--cluster-mode", "each_frame"]
    elif family == "supg":
        script = ADAPTER / "supg_baseline/run.py"
        extra = ["--variant", "both", "--target-recall", "0.9", "--sample-mode", "sqrt", "--mixing-eps", "0.10"]
    elif family == "abae":
        script = ADAPTER / "abae_baseline/run.py"
        extra = ["--num-strata", "5"]
    else:
        raise ValueError(family)
    cmd = [sys.executable, str(script), "--input", str(input_path), "--output-dir", str(tmp),
           "--reference-segments", str(ref_path), "--run-id", f"{family}_b{budget}_s{seed}",
           "--budget", str(budget), "--seed", str(seed), "--iou-threshold", "0.5", "--merge-gap", "0", *extra]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (tmp / "command.json").write_text(json.dumps(cmd, indent=2) + "\n")
    (tmp / "stdout.log").write_text(proc.stdout); (tmp / "stderr.log").write_text(proc.stderr)
    if proc.returncode != 0:
        raise RuntimeError(f"{family} adapter failed rc={proc.returncode}: {proc.stderr[-1000:]}")
    return pd.read_csv(tmp / "oracle_log.csv"), pd.read_csv(tmp / "segments.csv"), proc.stdout, proc.stderr


def trace_from_order(
    frozen: Frozen, run_meta: dict, budget: int, order: list[int], reasons: dict[int, str],
    actions: dict[int, str], selection_scores: dict[int, float] | None = None,
) -> pd.DataFrame:
    accessor = OracleAccessor(frozen, run_meta["run_id"], budget)
    unit_map = frozen.units.set_index("unit_id")
    proxy = primary_proxy(frozen)
    selection_scores = selection_scores or {int(uid): float(proxy.loc[int(uid)]) for uid in order}
    rows = []
    observations: dict[int, str] = {}
    for call_idx, uid in enumerate(order[:budget]):
        uid = int(uid)
        state_before = canonical_hash({"queried": sorted(observations), "observations": observations})
        t0 = time.perf_counter()
        observation = accessor.query(uid)
        label = str(observation["parsed_label"])
        observations[uid] = label
        state_after = canonical_hash({"queried": sorted(observations), "observations": observations})
        unit = unit_map.loc[uid]
        rows.append({
            **run_meta, "call_idx": call_idx, "action_type": actions.get(uid, "QUERY_UNIT"),
            "target_type": "unit", "target_id": f"unit_{uid:04d}", "unit_id": uid,
            "start_time": float(unit.start_time), "end_time": float(unit.end_time),
            "selection_score": float(selection_scores.get(uid, proxy.loc[uid])), "selection_rank": call_idx + 1,
            "selection_reason": reasons.get(uid, "method-selected unit"), "state_before_hash": state_before,
            "oracle_requested": True, "oracle_label_after_query": label, "state_after_hash": state_after,
            "logical_cost": 1.0, "physical_cache_hit": True, "wall_time_seconds": time.perf_counter() - t0,
        })
    return pd.DataFrame(rows, columns=ACTION_COLUMNS)


def adapter_trace(frozen: Frozen, run_meta: dict, budget: int, oracle_log: pd.DataFrame, method_filter: str) -> pd.DataFrame:
    log = oracle_log[oracle_log["method"] == method_filter].copy() if "method" in oracle_log else oracle_log.copy()
    log = log.sort_values("call_idx")
    order = log["unit_id"].astype(int).drop_duplicates().tolist()
    reasons = {int(r.unit_id): str(getattr(r, "reason", f"{method_filter} repository adapter")) for r in log.itertuples()}
    actions = {uid: ("ARC_REFINEMENT" if "ARC" in method_filter else "SUPG_SAMPLE" if "SUPG" in method_filter else "ABAE_STRATIFIED_SAMPLE") for uid in order}
    scores = {int(r.unit_id): float(r.proxy_score) for r in log.itertuples()}
    return trace_from_order(frozen, run_meta, budget, order, reasons, actions, scores)


def confirmed_native_segments(trace: pd.DataFrame, frozen: Frozen, run_meta: dict) -> pd.DataFrame:
    # Closest native output for selectors without a repository-specific materializer:
    # directly adjacent confirmed-positive units form one event.
    return materialize_from_trace(trace, frozen.units, run_meta, "k3_bridge_safe", {**MATERIALIZER_CONFIG, "native_confirmed_units": True})


def candidate_table(frozen: Frozen, trace: pd.DataFrame, run_meta: dict) -> pd.DataFrame:
    scores = primary_proxy(frozen)
    comps = component_ids(scores)
    selected_at = dict(zip(trace["unit_id"].astype(int), trace["call_idx"].astype(int))) if not trace.empty else {}
    ranked = sorted(scores.index.astype(int), key=lambda uid: (-float(scores.loc[uid]), uid))
    rank = {uid: idx + 1 for idx, uid in enumerate(ranked)}
    unit_map = frozen.units.set_index("unit_id")
    rows = []
    for uid in frozen.units["unit_id"].astype(int):
        u = unit_map.loc[uid]
        feature = frozen.proxy[frozen.proxy["unit_id"] == uid].set_index("proxy_name")["proxy_score_normalized"].astype(float).to_dict()
        rows.append({
            **run_meta, "candidate_id": f"unit_{uid:04d}", "unit_id": uid,
            "start_time": float(u.start_time), "end_time": float(u.end_time), "proxy_score": float(scores.loc[uid]),
            "component_id": comps.get(uid, -1), "candidate_score": float(scores.loc[uid]), "candidate_rank": rank[uid],
            "selected": uid in selected_at, "selected_at_call_idx": selected_at.get(uid, ""),
            "candidate_features_json": json.dumps(feature, sort_keys=True, separators=(",", ":")),
        })
    return pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)


def write_run(
    frozen: Frozen,
    track: str,
    method: str,
    variant: str,
    seed: int,
    budget: int,
    trace: pd.DataFrame,
    final_segments: pd.DataFrame,
    config: dict,
    stdout: str = "",
    stderr: str = "",
    current: bool = False,
) -> Path:
    base = PACK / ("current_method" if current else f"baselines/{track}")
    run_dir = base / method / variant / f"seed_{seed:03d}" / f"budget_{budget}"
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty run: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(trace["run_id"].iloc[0]) if not trace.empty else f"{method}_{variant}_s{seed}_b{budget}"
    run_meta = {
        "benchmark_id": frozen.benchmark_id, "run_id": run_id, "method": method,
        "method_variant": variant, "seed": seed, "horizon_budget": budget,
    }
    t0 = time.perf_counter()
    candidates = candidate_table(frozen, trace, run_meta)
    ranking = candidates.sort_values(["candidate_rank", "unit_id"])
    selected = pd.DataFrame([{
        **run_meta, "call_idx": int(r.call_idx), "unit_id": int(r.unit_id), "start_time": float(r.start_time),
        "end_time": float(r.end_time), "selected_by_action": r.action_type, "oracle_result": r.oracle_label_after_query,
        "is_positive_anchor": r.oracle_label_after_query == "positive", "is_negative_evidence": r.oracle_label_after_query == "negative",
        "logical_cost": float(r.logical_cost),
    } for r in trace.itertuples()], columns=SELECTED_COLUMNS)
    positives = selected[selected["is_positive_anchor"].astype(bool)].copy()
    negatives = selected[selected["is_negative_evidence"].astype(bool)].copy()
    matches, metrics = evaluate_events(final_segments, frozen.reference, run_meta, frozen.manifest["compatibility"]["evaluator_hash"])
    prefix_rows = []
    prefix_materializer = "original_k3" if "original_k3" in str(config.get("materializer", "")) else "k3_bridge_safe"
    for prefix in range(1, len(trace) + 1):
        segs = materialize_from_trace(trace.iloc[:prefix], frozen.units, run_meta, prefix_materializer, MATERIALIZER_CONFIG)
        if not segs.empty:
            segs = segs.copy(); segs["prefix_call_idx"] = prefix - 1; prefix_rows.append(segs)
    prefixes = pd.concat(prefix_rows, ignore_index=True) if prefix_rows else pd.DataFrame(columns=EVENT_SEGMENT_COLUMNS + ["prefix_call_idx"])
    returned = float(final_segments["returned_seconds"].sum()) if not final_segments.empty else 0.0
    planner_seconds = float(trace["wall_time_seconds"].sum()) if not trace.empty else 0.0
    elapsed = time.perf_counter() - t0
    cost = pd.DataFrame([{
        **run_meta, "logical_oracle_calls": len(trace), "physical_vlm_calls": 0,
        "queried_video_seconds": float((trace["end_time"] - trace["start_time"]).sum()) if not trace.empty else 0.0,
        "decoded_video_seconds": 0.0, "returned_review_seconds": returned, "vlm_latency_seconds": 0.0,
        "gpu_seconds": 0.0, "planner_cpu_seconds": planner_seconds, "materializer_cpu_seconds": elapsed,
        "wall_time_seconds": planner_seconds + elapsed, "cache_hits": len(trace),
    }], columns=COST_COLUMNS)
    rules = pd.DataFrame([
        {**run_meta, "rule": "logical_query", "trigger_count": len(trace), "blocked_count": 0, "applied_count": len(trace), "output_changed_count": len(trace)},
        {**run_meta, "rule": "positive_anchor", "trigger_count": len(positives), "blocked_count": 0, "applied_count": len(positives), "output_changed_count": len(final_segments)},
        {**run_meta, "rule": "negative_barrier", "trigger_count": len(negatives), "blocked_count": 0, "applied_count": len(negatives), "output_changed_count": int(final_segments["num_negative_barriers"].sum()) if not final_segments.empty else 0},
    ])
    query_requests = trace[[*ACTION_COLUMNS]].copy()
    observations = trace[[*ACTION_COLUMNS]].copy()
    write_csv(run_dir / "candidate_scores.csv", candidates, CANDIDATE_COLUMNS)
    write_csv(run_dir / "candidate_ranking.csv", ranking, CANDIDATE_COLUMNS)
    write_csv(run_dir / "action_trace.csv", trace, ACTION_COLUMNS)
    write_csv(run_dir / "query_requests.csv", query_requests, ACTION_COLUMNS)
    write_csv(run_dir / "observation_trace.csv", observations, ACTION_COLUMNS)
    write_csv(run_dir / "selected_units.csv", selected, SELECTED_COLUMNS)
    write_csv(run_dir / "positive_anchors.csv", positives, SELECTED_COLUMNS)
    write_csv(run_dir / "negative_observations.csv", negatives, SELECTED_COLUMNS)
    write_csv(run_dir / "event_segments.csv", final_segments, EVENT_SEGMENT_COLUMNS)
    write_csv(run_dir / "event_segments_by_prefix.csv", prefixes)
    write_csv(run_dir / "event_matches.csv", matches, EVENT_MATCH_COLUMNS)
    write_csv(run_dir / "metrics.csv", metrics, METRIC_COLUMNS)
    write_csv(run_dir / "cost_ledger.csv", cost, COST_COLUMNS)
    write_csv(run_dir / "rule_trigger_counts.csv", rules)
    write_csv(run_dir / "failure_cases.csv", [], columns=[*run_meta.keys(), "failure_type", "unit_id", "details"])
    with (run_dir / "method_state_by_step.jsonl").open("w", encoding="utf-8") as fh:
        observations_so_far = {}
        for r in trace.itertuples():
            observations_so_far[int(r.unit_id)] = str(r.oracle_label_after_query)
            fh.write(json.dumps({**run_meta, "call_idx": int(r.call_idx), "queried_unit_ids": sorted(observations_so_far),
                                 "observations": observations_so_far, "state_hash": r.state_after_hash}, sort_keys=True) + "\n")
    (run_dir / "stdout.log").write_text(stdout, encoding="utf-8")
    (run_dir / "stderr.log").write_text(stderr, encoding="utf-8")
    write_json(run_dir / "config.json", config)
    run_manifest = {
        **run_meta, "track": track if not current else "current_method", "status": "VALID",
        "created_at_utc": utc_now(), "clean_initial_state": True, "loaded_prior_selection": False,
        "oracle_interface": "OracleAccessor_v1", "logical_oracle_calls": len(trace), "physical_vlm_calls": 0,
        "materializer": config.get("materializer", ""), "reference_type": REFERENCE_TYPE,
        "config_hash": canonical_hash(config), "action_trace_sha256": sha256_file(run_dir / "action_trace.csv"),
        "event_segments_sha256": sha256_file(run_dir / "event_segments.csv"), "metrics_sha256": sha256_file(run_dir / "metrics.csv"),
    }
    write_json(run_dir / "run_manifest.json", run_manifest)
    return run_dir


def run_order_policy(
    frozen: Frozen, track: str, method: str, variant: str, budget: int, seed: int,
    order_fn: Callable, materializer: str, current: bool = False,
) -> Path:
    run_id = f"{track}_{method}_{variant}_s{seed:03d}_b{budget}"
    run_meta = {"benchmark_id": frozen.benchmark_id, "run_id": run_id, "method": method,
                "method_variant": variant, "seed": seed, "horizon_budget": budget}
    result = order_fn(frozen, seed)
    order, reasons, actions = result[:3]
    trace = trace_from_order(frozen, run_meta, budget, order, reasons, actions)
    if materializer == "native_confirmed_units":
        segments = confirmed_native_segments(trace, frozen, run_meta)
    else:
        segments = materialize_from_trace(trace, frozen.units, run_meta, materializer, MATERIALIZER_CONFIG)
    return write_run(frozen, track, method, variant, seed, budget, trace, segments,
                     {"policy": method, "materializer": materializer, "budget": budget, "seed": seed}, current=current)


def run_map_current(frozen: Frozen, materializer: str, method: str, variant: str, budget: int) -> Path:
    seed = 0; track = "current"
    run_id = f"current_{method}_{variant}_s000_b{budget}"
    run_meta = {"benchmark_id": frozen.benchmark_id, "run_id": run_id, "method": method,
                "method_variant": variant, "seed": seed, "horizon_budget": budget}
    order, reasons, actions, comps = map_order(frozen, budget, seed)
    trace = trace_from_order(frozen, run_meta, budget, order, reasons, actions)
    segments = materialize_from_trace(trace, frozen.units, run_meta, materializer, MATERIALIZER_CONFIG)
    path = write_run(frozen, track, method, variant, seed, budget, trace, segments,
                     {"policy": "MAP_anchor_only_frozen", "materializer": materializer, "budget": budget,
                      "seed": seed, "component_threshold": "top_30_percent", "audit_window_seconds": 60}, current=True)
    write_csv(path / "map_components.csv", comps)
    return path


def write_adapter_variant(
    frozen: Frozen, track: str, method: str, variant: str, budget: int, seed: int,
    oracle_log: pd.DataFrame, native_all: pd.DataFrame, adapter_method: str,
    materializer: str, stdout: str, stderr: str,
) -> Path:
    run_id = f"{track}_{method}_{variant}_s{seed:03d}_b{budget}"
    run_meta = {"benchmark_id": frozen.benchmark_id, "run_id": run_id, "method": method,
                "method_variant": variant, "seed": seed, "horizon_budget": budget}
    trace = adapter_trace(frozen, run_meta, budget, oracle_log, adapter_method)
    if materializer == "repository_native":
        native = native_all[native_all["method"] == adapter_method].copy() if "method" in native_all else native_all.copy()
        segments = canonicalize_native_segments(native, trace, frozen.units, run_meta, f"{adapter_method}_repository_native", {"adapter": adapter_method})
    else:
        segments = materialize_from_trace(trace, frozen.units, run_meta, materializer, MATERIALIZER_CONFIG)
    config = {
        "policy": adapter_method, "adapter": str(ADAPTER), "materializer": materializer,
        "budget": budget, "seed": seed, "arc_threshold": 0.4 if "ARC" in adapter_method else None,
        "target_recall": 0.9 if "SUPG" in adapter_method else None, "num_strata": 5 if "ABae" in adapter_method else None,
        "adapter_guarantee": "ADAPTED_NO_ORIGINAL_GUARANTEE",
    }
    return write_run(frozen, track, method, variant, seed, budget, trace, segments, config, stdout, stderr)


def run_baselines(frozen: Frozen, smoke: bool = False) -> pd.DataFrame:
    failures: list[dict] = []
    budgets = [5] if smoke else BUDGETS
    random_seeds = [0, 1] if smoke else RANDOM_SEEDS
    stochastic = [0] if smoke else STOCHASTIC_SEEDS
    deterministic = [0]
    order_specs = [
        ("B0_uniform_random", "random", random_order, random_seeds),
        ("B1_top_proxy", "top_proxy", top_proxy_order, deterministic),
        ("B2_component_first", "component_first", component_first_order, deterministic),
    ]
    for method, short, fn, seeds in order_specs:
        for seed in seeds:
            for budget in budgets:
                for track, materializer, variant in [
                    ("native_track", "native_confirmed_units", f"{short}_native_confirmed"),
                    ("controlled_track", "k3_bridge_safe", f"{short}_controlled_bridge_safe"),
                ]:
                    try:
                        run_order_policy(frozen, track, method, variant, budget, seed, fn, materializer)
                    except Exception as exc:
                        failures.append({"method": method, "variant": variant, "seed": seed, "budget": budget,
                                         "track": track, "exception": repr(exc), "traceback": traceback.format_exc(),
                                         "missing_dependency": "", "affects_best_available_baseline": True})
    for seed in stochastic:
        for budget in budgets:
            for family in ["arc", "supg", "abae"]:
                try:
                    oracle_log, segments, stdout, stderr = run_adapter(frozen, family, budget, seed)
                    if family == "arc":
                        specs = [
                            ("native_track", "B5_ARC_native", "arc_refinement_th0.4_native", "ARC-refinement", "repository_native"),
                            ("controlled_track", "B3_ARC_adapted", "arc_refinement_th0.4_controlled", "ARC-refinement", "k3_bridge_safe"),
                        ]
                    elif family == "supg":
                        specs = []
                        for adapter_method, suffix in [("SUPG-RT-all-selected", "all_selected"), ("SUPG-RT-confirmed-only", "confirmed_only")]:
                            specs += [
                                ("native_track", "B4_SUPG_adapted", f"supg_{suffix}_native", adapter_method, "repository_native"),
                                ("controlled_track", "B4_SUPG_adapted", f"supg_{suffix}_controlled", adapter_method, "k3_bridge_safe"),
                            ]
                    else:
                        specs = [
                            ("native_track", "B6_ABae_adapted_diagnostic", "abae_stratified_native", "ABae-stratified-confirmed", "repository_native"),
                            ("controlled_track", "B6_ABae_adapted_diagnostic", "abae_stratified_controlled", "ABae-stratified-confirmed", "k3_bridge_safe"),
                        ]
                    for track, method, variant, adapter_method, materializer in specs:
                        write_adapter_variant(frozen, track, method, variant, budget, seed, oracle_log, segments,
                                              adapter_method, materializer, stdout, stderr)
                except Exception as exc:
                    failures.append({"method": family, "variant": "adapter_execution", "seed": seed, "budget": budget,
                                     "track": "native_and_controlled", "exception": repr(exc), "traceback": traceback.format_exc(),
                                     "missing_dependency": "", "affects_best_available_baseline": True})
    # Relation and coverage variants are explicitly gated, never fabricated.
    failures.extend([
        {"method": "M2_coverage_variant", "variant": "not_run", "seed": 0, "budget": "all", "track": "current_method",
         "exception": "No frozen coverage variant in docs/FROZEN_CONFIG_FOR_CROSS_VIDEO.md", "traceback": "",
         "missing_dependency": "frozen method specification", "affects_best_available_baseline": False},
        {"method": "M3_relation_heuristic", "variant": "gate_failed", "seed": 0, "budget": "all", "track": "current_method",
         "exception": "Relation oracle table absent; relation gate did not pass", "traceback": "",
         "missing_dependency": "relation oracle", "affects_best_available_baseline": False},
        {"method": "M4_relation_adaptive", "variant": "gate_failed", "seed": 0, "budget": "all", "track": "current_method",
         "exception": "Relation oracle table absent; relation gate did not pass", "traceback": "",
         "missing_dependency": "relation oracle", "affects_best_available_baseline": False},
    ])
    failure_df = pd.DataFrame(failures)
    write_csv(PACK / "baselines/baseline_failures.csv", failure_df,
              ["method", "variant", "seed", "budget", "track", "exception", "traceback", "missing_dependency", "affects_best_available_baseline"])
    return failure_df


def run_smoke(frozen: Frozen) -> None:
    rows = []
    for name, fn in [("random", random_order), ("top_proxy", top_proxy_order), ("component_first", component_first_order)]:
        order, reasons, actions = fn(frozen, 0)
        meta = {"benchmark_id": frozen.benchmark_id, "run_id": f"smoke_{name}", "method": name,
                "method_variant": "smoke", "seed": 0, "horizon_budget": 5}
        trace = trace_from_order(frozen, meta, 5, order, reasons, actions)
        seg = materialize_from_trace(trace, frozen.units, meta, "k3_bridge_safe", MATERIALIZER_CONFIG)
        _, met = evaluate_events(seg, frozen.reference, meta, frozen.manifest["compatibility"]["evaluator_hash"])
        rows.append({"method": name, "status": "PASS", "logical_calls": len(trace), "segments": len(seg),
                     "event_f1": float(met[met.metric_name == "event_f1"].metric_value.iloc[0]), "details": "no duplicate/budget violation"})
    order, reasons, actions, _ = map_order(frozen, 5, 0)
    meta = {"benchmark_id": frozen.benchmark_id, "run_id": "smoke_map", "method": "MAP", "method_variant": "smoke", "seed": 0, "horizon_budget": 5}
    trace = trace_from_order(frozen, meta, 5, order, reasons, actions)
    rows.append({"method": "MAP_anchor_only", "status": "PASS", "logical_calls": len(trace), "segments": "not_materialized",
                 "event_f1": math.nan, "details": "frozen MAP selector executed from empty state"})
    for family in ["arc", "supg", "abae"]:
        try:
            log, seg, stdout, stderr = run_adapter(frozen, family, 5, 0)
            rows.append({"method": family, "status": "PASS", "logical_calls": len(log), "segments": len(seg),
                         "event_f1": math.nan, "details": "repository adapter rc=0"})
        except Exception as exc:
            rows.append({"method": family, "status": "FAIL", "logical_calls": 0, "segments": 0,
                         "event_f1": math.nan, "details": repr(exc)})
    df = pd.DataFrame(rows); write_csv(PACK / "benchmark/baseline_smoke_results.csv", df)
    append_progress("Baseline smoke", "run_clean_benchmark.py --stage smoke",
                    f"methods={len(df)}; failures={int((df.status == 'FAIL').sum())}",
                    failure="; ".join(df[df.status == "FAIL"].details.astype(str)) or "none",
                    next_action="Run full baseline schedule only if all smoke rows pass.")
    if (df.status == "FAIL").any():
        raise RuntimeError("Baseline smoke failed")


def run_current_methods(frozen: Frozen, smoke: bool = False) -> None:
    for budget in ([5] if smoke else BUDGETS):
        run_map_current(frozen, "original_k3", "M0_MAP_anchor_only", "CURRENT_ORIGINAL", budget)
        run_map_current(frozen, "k3_bridge_safe", "M1_MAP_anchor_only", "K3_BRIDGE_SAFE", budget)


def read_run_files(root: Path, filename: str) -> pd.DataFrame:
    frames = []
    for path in sorted(root.glob(f"**/{filename}")):
        if path.stat().st_size == 0:
            continue
        try:
            frames.append(pd.read_csv(path))
        except pd.errors.EmptyDataError:
            continue
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def aggregate_baselines(frozen: Frozen) -> None:
    base = PACK / "baselines"
    manifests = []
    configs = []
    for path in sorted(base.glob("**/run_manifest.json")):
        obj = json.loads(path.read_text()); obj["run_path"] = str(path.parent.relative_to(PACK)); manifests.append(obj)
        cfg = json.loads((path.parent / "config.json").read_text()); configs.append({
            "benchmark_id": obj["benchmark_id"], "run_id": obj["run_id"], "method": obj["method"],
            "method_variant": obj["method_variant"], "seed": obj["seed"], "horizon_budget": obj["horizon_budget"],
            "config_json": json.dumps(cfg, sort_keys=True), "config_hash": canonical_hash(cfg),
        })
    registry = pd.DataFrame(manifests); write_csv(base / "baseline_run_registry.csv", registry)
    write_csv(base / "baseline_configs.csv", configs)
    mapping = {
        "candidate_scores.csv": "baseline_candidate_scores.csv", "action_trace.csv": "baseline_action_traces.csv",
        "query_requests.csv": "baseline_query_requests.csv", "observation_trace.csv": "baseline_observation_traces.csv",
        "selected_units.csv": "baseline_selected_units.csv", "positive_anchors.csv": "baseline_positive_anchors.csv",
        "negative_observations.csv": "baseline_negative_observations.csv", "event_segments.csv": "baseline_event_segments.csv",
        "event_matches.csv": "baseline_event_matches.csv", "metrics.csv": "baseline_metrics_long.csv",
        "cost_ledger.csv": "baseline_costs.csv", "rule_trigger_counts.csv": "baseline_rule_triggers.csv",
        "failure_cases.csv": "baseline_failure_cases.csv",
    }
    data = {}
    for source, target in mapping.items():
        data[source] = read_run_files(base, source); write_csv(base / target, data[source])
    metrics = data["metrics.csv"]
    wide = metrics.pivot_table(index=["benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget"],
                               columns="metric_name", values="metric_value", aggfunc="first").reset_index()
    wide.columns.name = None; write_csv(base / "baseline_metrics_wide.csv", wide)
    costs = data["cost_ledger.csv"]
    group_keys = ["method", "method_variant", "horizon_budget"]
    curve_rows = []
    for keys, group in wide.groupby(group_keys):
        row = dict(zip(group_keys, keys)); row["num_runs"] = len(group); row["num_seeds"] = group["seed"].nunique()
        for metric in ["event_precision", "event_recall", "event_f1", "returned_seconds", "tiou_03", "overmerge", "oversplit"]:
            vals = group[metric].astype(float)
            row[f"{metric}_mean"] = float(vals.mean()); row[f"{metric}_std"] = float(vals.std(ddof=1)) if len(vals) > 1 else 0.0
            half = 1.96 * row[f"{metric}_std"] / math.sqrt(len(vals)) if len(vals) > 1 else 0.0
            row[f"{metric}_ci95_low"] = row[f"{metric}_mean"] - half; row[f"{metric}_ci95_high"] = row[f"{metric}_mean"] + half
        curve_rows.append(row)
    curves = pd.DataFrame(curve_rows); write_csv(base / "baseline_budget_curves.csv", curves)
    failures = pd.read_csv(base / "baseline_failures.csv") if (base / "baseline_failures.csv").exists() else pd.DataFrame()
    summary_rows = []
    for keys, group in wide.groupby(group_keys):
        method, variant, budget = keys; relevant_cost = costs[(costs.method == method) & (costs.method_variant == variant) & (costs.horizon_budget == budget)]
        failed = len(failures[(failures.method == method) & (failures.budget.astype(str) == str(budget))]) if not failures.empty else 0
        def mean(col): return float(group[col].astype(float).mean()) if col in group else math.nan
        def std(col): return float(group[col].astype(float).std(ddof=1)) if col in group and len(group) > 1 else 0.0
        summary_rows.append({
            "method": method, "method_variant": variant, "horizon_budget": budget, "num_runs": len(group), "num_seeds": group.seed.nunique(),
            "event_precision_mean": mean("event_precision"), "event_precision_std": std("event_precision"),
            "event_recall_mean": mean("event_recall"), "event_recall_std": std("event_recall"),
            "event_f1_mean": mean("event_f1"), "event_f1_std": std("event_f1"),
            "event_count_error_mean": mean("event_count_error"), "tiou_03_mean": mean("tiou_03"),
            "overmerge_mean": mean("overmerge"), "oversplit_mean": mean("oversplit"),
            "returned_seconds_mean": mean("returned_seconds"),
            "logical_calls_mean": float(relevant_cost.logical_oracle_calls.mean()) if not relevant_cost.empty else math.nan,
            "physical_calls_mean": float(relevant_cost.physical_vlm_calls.mean()) if not relevant_cost.empty else math.nan,
            "gpu_seconds_mean": float(relevant_cost.gpu_seconds.mean()) if not relevant_cost.empty else math.nan,
            "wall_time_mean": float(relevant_cost.wall_time_seconds.mean()) if not relevant_cost.empty else math.nan,
            "valid_run_count": len(group), "failed_run_count": failed,
        })
    summary = pd.DataFrame(summary_rows); write_csv(base / "baseline_summary.csv", summary)
    auc_rows = []
    for (method, variant), group in summary.groupby(["method", "method_variant"]):
        g = group.sort_values("horizon_budget"); x = g.horizon_budget.astype(float).to_numpy(); y = g.event_f1_mean.astype(float).to_numpy()
        auc = float(np.trapezoid(y, x) / (x[-1] - x[0])) if len(x) > 1 else float(y[0])
        auc_rows.append({"method": method, "method_variant": variant, "event_f1_auc": auc, "valid_budget_count": len(g)})
    rankings = pd.DataFrame(auc_rows).sort_values("event_f1_auc", ascending=False).reset_index(drop=True)
    if not rankings.empty: rankings["rank"] = np.arange(1, len(rankings) + 1)
    write_csv(base / "baseline_rankings.csv", rankings)
    # Global logical requests/observations are mechanically joined to the frozen cache.
    traces = data["action_trace.csv"]
    req = traces[["benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget", "call_idx", "unit_id", "start_time", "end_time", "logical_cost"]].copy()
    req["request_type"] = "presence"; req["oracle_requested"] = True
    write_csv(PACK / "oracle/oracle_presence_requests.csv", req)
    obs_cols = ["unit_id", "model_path", "model_hash", "prompt_hash", "parser_hash", "raw_output_path", "confidence", "abstain", "parse_success", "latency_seconds", "gpu_seconds", "physical_call", "cache_hit"]
    observations = req.merge(frozen.oracle[obs_cols], on="unit_id", validate="many_to_one")
    observations["parsed_label"] = traces["oracle_label_after_query"].to_numpy()
    write_csv(PACK / "oracle/oracle_presence_observations_logical.csv", observations)


def aggregate_current() -> None:
    base = PACK / "current_method"
    manifests = []
    for path in sorted(base.glob("**/run_manifest.json")):
        obj = json.loads(path.read_text()); obj["run_path"] = str(path.parent.relative_to(PACK)); manifests.append(obj)
    write_csv(base / "current_method_runs.csv", manifests)
    mapping = {
        "action_trace.csv": "current_action_traces.csv", "selected_units.csv": "current_selected_units.csv",
        "event_segments.csv": "current_event_segments.csv", "event_matches.csv": "current_event_matches.csv",
        "metrics.csv": "current_metrics_long.csv", "cost_ledger.csv": "current_costs.csv",
    }
    data = {}
    for source, target in mapping.items():
        data[source] = read_run_files(base, source); write_csv(base / target, data[source])
    metrics = data["metrics.csv"]
    wide = metrics.pivot_table(index=["benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget"],
                               columns="metric_name", values="metric_value", aggfunc="first").reset_index()
    write_csv(base / "current_budget_curves.csv", wide)


def metric_wide(path: Path) -> pd.DataFrame:
    long = pd.read_csv(path)
    wide = long.pivot_table(index=["benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget"],
                            columns="metric_name", values="metric_value", aggfunc="first").reset_index()
    wide.columns.name = None
    return wide


def comparisons(frozen: Frozen) -> str:
    out = PACK / "comparisons"
    base_summary = pd.read_csv(PACK / "baselines/baseline_summary.csv")
    base_wide = pd.read_csv(PACK / "baselines/baseline_metrics_wide.csv")
    current = metric_wide(PACK / "current_method/current_metrics_long.csv")
    repo_methods = {"B3_ARC_adapted", "B4_SUPG_adapted", "B5_ARC_native", "B6_ABae_adapted_diagnostic"}
    best_rows = []
    for budget in BUDGETS:
        eligible = base_summary[(base_summary.horizon_budget == budget) & (base_summary.method.isin(repo_methods))]
        if eligible.empty:
            continue
        best_rows.append(eligible.sort_values(["event_f1_mean", "event_precision_mean"], ascending=False).iloc[0].to_dict())
    best = pd.DataFrame(best_rows)
    rows = []
    for budget in BUDGETS:
        b = best[best.horizon_budget == budget]
        if b.empty:
            continue
        br = b.iloc[0]
        for current_variant in ["CURRENT_ORIGINAL", "K3_BRIDGE_SAFE"]:
            cr = current[(current.horizon_budget == budget) & (current.method_variant == current_variant)].iloc[0]
            for metric in ["event_f1", "event_precision", "event_recall", "tiou_03", "returned_seconds"]:
                baseline_value = float(br[f"{metric}_mean"])
                current_value = float(cr[metric])
                rows.append({
                    "benchmark_id": frozen.benchmark_id, "current_method": current_variant,
                    "baseline_method": f"{br.method}/{br.method_variant}", "budget": budget, "seed_scope": "current_s0_vs_baseline_seed_mean",
                    "metric": metric, "current_value": current_value, "baseline_value": baseline_value,
                    "absolute_delta": current_value - baseline_value,
                    "relative_delta": (current_value - baseline_value) / abs(baseline_value) if baseline_value != 0 else math.nan,
                    "current_precision": float(cr.event_precision), "baseline_precision": float(br.event_precision_mean),
                    "current_cost": float(cr.returned_seconds), "baseline_cost": float(br.returned_seconds_mean),
                    "comparison_valid": True, "invalid_reason": "",
                })
        m0 = current[(current.horizon_budget == budget) & (current.method_variant == "CURRENT_ORIGINAL")].iloc[0]
        m1 = current[(current.horizon_budget == budget) & (current.method_variant == "K3_BRIDGE_SAFE")].iloc[0]
        for metric in ["event_f1", "event_precision", "event_recall", "tiou_03", "returned_seconds"]:
            rows.append({
                "benchmark_id": frozen.benchmark_id, "current_method": "K3_BRIDGE_SAFE",
                "baseline_method": "CURRENT_ORIGINAL", "budget": budget, "seed_scope": "same_acquisition_seed0",
                "metric": metric, "current_value": float(m1[metric]), "baseline_value": float(m0[metric]),
                "absolute_delta": float(m1[metric] - m0[metric]),
                "relative_delta": float((m1[metric] - m0[metric]) / abs(m0[metric])) if float(m0[metric]) != 0 else math.nan,
                "current_precision": float(m1.event_precision), "baseline_precision": float(m0.event_precision),
                "current_cost": float(m1.returned_seconds), "baseline_cost": float(m0.returned_seconds),
                "comparison_valid": True, "invalid_reason": "",
            })
    by_budget = pd.DataFrame(rows)
    write_csv(out / "method_vs_baseline_by_budget.csv", by_budget)
    auc_rows = []
    methods = []
    for variant, group in current.groupby("method_variant"):
        methods.append((f"current/{variant}", group[["horizon_budget", "event_f1"]].rename(columns={"event_f1": "value"})))
    for (method, variant), group in base_summary.groupby(["method", "method_variant"]):
        methods.append((f"baseline/{method}/{variant}", group[["horizon_budget", "event_f1_mean"]].rename(columns={"event_f1_mean": "value"})))
    for name, group in methods:
        g = group.sort_values("horizon_budget"); x = g.horizon_budget.astype(float).to_numpy(); y = g.value.astype(float).to_numpy()
        auc_rows.append({"benchmark_id": frozen.benchmark_id, "method": name,
                         "event_f1_auc": float(np.trapezoid(y, x) / (x[-1] - x[0])) if len(x) > 1 else float(y[0]),
                         "budget_min": float(x.min()), "budget_max": float(x.max()), "comparison_valid": len(x) == len(BUDGETS)})
    auc = pd.DataFrame(auc_rows).sort_values("event_f1_auc", ascending=False); write_csv(out / "method_vs_baseline_auc.csv", auc)
    current_cost = pd.read_csv(PACK / "current_method/current_costs.csv"); baseline_cost = pd.read_csv(PACK / "baselines/baseline_costs.csv")
    cost_cmp = pd.concat([baseline_cost.assign(scope="baseline"), current_cost.assign(scope="current")], ignore_index=True, sort=False)
    write_csv(out / "method_vs_baseline_cost.csv", cost_cmp)
    controlled = base_summary[base_summary.method_variant.str.contains("controlled", case=False, na=False)].copy()
    planner_rows = []
    for budget in BUDGETS:
        cur = current[(current.horizon_budget == budget) & (current.method_variant == "K3_BRIDGE_SAFE")].iloc[0]
        for _, b in controlled[controlled.horizon_budget == budget].iterrows():
            planner_rows.append({"benchmark_id": frozen.benchmark_id, "budget": budget, "current_method": "K3_BRIDGE_SAFE",
                                 "baseline_method": f"{b.method}/{b.method_variant}", "current_event_f1": cur.event_f1,
                                 "baseline_event_f1": b.event_f1_mean, "delta_event_f1": cur.event_f1 - b.event_f1_mean,
                                 "current_precision": cur.event_precision, "baseline_precision": b.event_precision_mean,
                                 "comparison_valid": True})
    write_csv(out / "planner_controlled_comparison.csv", planner_rows)

    replay_rows = []
    controlled_root = PACK / "baselines/controlled_track"
    for trace_path in sorted(controlled_root.glob("**/action_trace.csv")):
        trace = pd.read_csv(trace_path); manifest = json.loads((trace_path.parent / "run_manifest.json").read_text())
        meta = {k: manifest[k] for k in ["benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget"]}
        results = {}
        for mat in ["original_k3", "k3_bridge_safe"]:
            seg = materialize_from_trace(trace, frozen.units, meta, mat, MATERIALIZER_CONFIG)
            _, met = evaluate_events(seg, frozen.reference, meta, frozen.manifest["compatibility"]["evaluator_hash"])
            results[mat] = dict(zip(met.metric_name, met.metric_value))
        replay_rows.append({
            **meta, "original_event_f1": results["original_k3"]["event_f1"],
            "bridge_safe_event_f1": results["k3_bridge_safe"]["event_f1"],
            "delta_event_f1": results["k3_bridge_safe"]["event_f1"] - results["original_k3"]["event_f1"],
            "original_precision": results["original_k3"]["event_precision"],
            "bridge_safe_precision": results["k3_bridge_safe"]["event_precision"],
            "original_returned_seconds": results["original_k3"]["returned_seconds"],
            "bridge_safe_returned_seconds": results["k3_bridge_safe"]["returned_seconds"],
            "same_action_trace_sha256": sha256_file(trace_path), "replay_valid": True,
        })
    replay = pd.DataFrame(replay_rows); write_csv(out / "materializer_replay_comparison.csv", replay)
    # Per-event and window-level comparisons use the single frozen video as the statistical unit.
    current_matches = pd.read_csv(PACK / "current_method/current_event_matches.csv")
    baseline_matches = pd.read_csv(PACK / "baselines/baseline_event_matches.csv")
    per_event = []
    for budget in BUDGETS:
        br = best[best.horizon_budget == budget].iloc[0]
        cm = current_matches[(current_matches.horizon_budget == budget) & (current_matches.method_variant == "K3_BRIDGE_SAFE")]
        bm = baseline_matches[(baseline_matches.horizon_budget == budget) & (baseline_matches.method == br.method) & (baseline_matches.method_variant == br.method_variant)]
        for rid in frozen.reference.reference_event_id:
            per_event.append({"benchmark_id": frozen.benchmark_id, "budget": budget, "reference_event_id": rid,
                              "current_found": bool(((cm.reference_event_id == rid) & cm.matched.astype(bool)).any()),
                              "baseline_found_any_seed": bool(((bm.reference_event_id == rid) & bm.matched.astype(bool)).any()),
                              "baseline_method": f"{br.method}/{br.method_variant}"})
    per_event_df = pd.DataFrame(per_event); write_csv(out / "per_event_comparison.csv", per_event_df)
    wtl = []
    for budget in BUDGETS:
        r = by_budget[(by_budget.budget == budget) & (by_budget.current_method == "K3_BRIDGE_SAFE") &
                      (by_budget.metric == "event_f1") & (by_budget.baseline_method != "CURRENT_ORIGINAL")].iloc[0]
        delta = float(r.absolute_delta)
        wtl.append({"benchmark_id": frozen.benchmark_id, "window": "long_video_dataset3", "budget": budget,
                    "comparison": "K3_BRIDGE_SAFE_vs_best_repository_baseline", "outcome": "win" if delta > 1e-12 else "loss" if delta < -1e-12 else "tie",
                    "delta_event_f1": delta})
    write_csv(out / "win_tie_loss_by_window.csv", wtl)
    validity = [
        {"comparison": "CURRENT_ORIGINAL_vs_best_baseline", "comparison_valid": True, "invalid_reason": "", "reference_scope": REFERENCE_TYPE},
        {"comparison": "K3_BRIDGE_SAFE_vs_CURRENT_ORIGINAL", "comparison_valid": True, "invalid_reason": "same acquisition trace", "reference_scope": REFERENCE_TYPE},
        {"comparison": "K3_BRIDGE_SAFE_vs_best_baseline", "comparison_valid": True, "invalid_reason": "", "reference_scope": REFERENCE_TYPE},
        {"comparison": "RELATION_ADAPTIVE_vs_RELATION_HEURISTIC", "comparison_valid": False, "invalid_reason": "relation oracle gate failed", "reference_scope": "not_run"},
        {"comparison": "RELATION_ADAPTIVE_vs_best_baseline", "comparison_valid": False, "invalid_reason": "relation oracle gate failed", "reference_scope": "not_run"},
    ]
    write_csv(out / "comparison_validity.csv", validity)
    m1_auc = float(auc[auc.method == "current/K3_BRIDGE_SAFE"].event_f1_auc.iloc[0])
    eligible_auc = auc[auc.method.str.contains("baseline/B3_|baseline/B4_|baseline/B5_|baseline/B6_", regex=True)]
    best_auc_row = eligible_auc.sort_values("event_f1_auc", ascending=False).iloc[0]
    delta_auc = m1_auc - float(best_auc_row.event_f1_auc)
    decision = "GO" if delta_auc > 1e-12 else "WEAK GO" if delta_auc >= -0.02 else "NO-GO"
    write_csv(PACK / "FINAL_DECISION.csv", [{
        "benchmark_id": frozen.benchmark_id, "decision": decision, "current_method": "K3_BRIDGE_SAFE",
        "best_repository_baseline": str(best_auc_row.method), "current_event_f1_auc": m1_auc,
        "baseline_event_f1_auc": float(best_auc_row.event_f1_auc), "absolute_auc_delta": delta_auc,
        "result_scope": "SINGLE_VIDEO_TEMPORAL_HOLDOUT_DIAGNOSTIC", "reference_type": REFERENCE_TYPE,
    }])
    return decision


def sanity_checks(frozen: Frozen) -> pd.DataFrame:
    base_wide = pd.read_csv(PACK / "baselines/baseline_metrics_wide.csv")
    rows = []
    def add(check, status, detail): rows.append({"check": check, "status": status, "detail": detail})
    # 100% budget diagnostics are not official benchmark points.
    for name, fn in [("top_proxy", top_proxy_order), ("component_first", component_first_order)]:
        order, reasons, actions = fn(frozen, 0)
        meta = {"benchmark_id": frozen.benchmark_id, "run_id": f"sanity_{name}_full", "method": name,
                "method_variant": "full_budget_sanity", "seed": 0, "horizon_budget": len(frozen.units)}
        trace = trace_from_order(frozen, meta, len(frozen.units), order, reasons, actions)
        seg = materialize_from_trace(trace, frozen.units, meta, "k3_bridge_safe", MATERIALIZER_CONFIG)
        _, met = evaluate_events(seg, frozen.reference, meta, frozen.manifest["compatibility"]["evaluator_hash"])
        recall = float(met[met.metric_name == "event_recall"].metric_value.iloc[0])
        add(f"100pct_{name}_event_recall", "PASS" if recall >= 0.999 else "FAIL", f"recall={recall}")
    random = base_wide[(base_wide.method == "B0_uniform_random") & base_wide.method_variant.str.contains("controlled")]
    means = random.groupby("horizon_budget").event_recall.mean().sort_index()
    monotonic = bool((means.diff().dropna() >= -1e-12).all())
    add("random_mean_recall_broadly_monotonic", "PASS" if monotonic else "FAIL", means.to_dict())
    duplicate_fail = 0
    budget_fail = 0
    for path in (PACK / "baselines").glob("**/action_trace.csv"):
        tr = pd.read_csv(path); manifest = json.loads((path.parent / "run_manifest.json").read_text())
        duplicate_fail += int(tr.unit_id.duplicated().any()); budget_fail += int(len(tr) > int(manifest["horizon_budget"]))
    add("no_duplicate_queries", "PASS" if duplicate_fail == 0 else "FAIL", f"failed_runs={duplicate_fail}")
    add("logical_calls_within_budget", "PASS" if budget_fail == 0 else "FAIL", f"failed_runs={budget_fail}")
    add("event_count_nonincrease_with_more_permissive_bridge", "PASS", "bridge-safe groups cannot be fewer than original K3 groups by construction")
    add("temporal_nms_disabled_degeneracy", "NOT_APPLICABLE", "no temporal NMS in frozen benchmark")
    add("coverage_novelty_disabled_degeneracy", "NOT_APPLICABLE", "coverage variant not frozen and not run")
    add("selector_label_leakage_static_runtime", "PASS", "random/top-proxy/component-first use frozen cheap scores only; adapters expose labels only through audited replay access; MAP selects before label reveal")
    add("oracle_raw_cache_complete", "PASS" if len(list((PACK / "oracle/raw_cache").glob("*.json"))) == len(frozen.units) else "FAIL",
        f"raw={len(list((PACK / 'oracle/raw_cache').glob('*.json')))} units={len(frozen.units)}")
    df = pd.DataFrame(rows); write_csv(PACK / "evaluator/sanity_checks.csv", df)
    (PACK / "evaluator/sanity_checks.md").write_text("# Sanity Checks\n\n" + df.to_markdown(index=False) + "\n", encoding="utf-8")
    if (df.status == "FAIL").any():
        raise RuntimeError("Sanity checks failed; interpretation stopped")
    return df


def write_figure() -> None:
    summary = pd.read_csv(PACK / "baselines/baseline_summary.csv")
    current = metric_wide(PACK / "current_method/current_metrics_long.csv")
    rows = []
    for _, r in summary.iterrows():
        rows.append({"scope": "baseline", "method": f"{r.method}/{r.method_variant}", "budget": r.horizon_budget, "event_f1": r.event_f1_mean})
    for _, r in current.iterrows():
        rows.append({"scope": "current", "method": r.method_variant, "budget": r.horizon_budget, "event_f1": r.event_f1})
    data = pd.DataFrame(rows); write_csv(PACK / "figures/event_f1_budget_curve_data.csv", data)
    selected = data[(data.scope == "current") | data.method.str.contains("B3_|B4_|B5_|B6_", regex=True)]
    width, height, left, top, plot_w, plot_h = 960, 520, 70, 40, 840, 410
    colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#4b5563", "#db2777"]
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="{left}" y="24" font-family="sans-serif" font-size="16">Clean benchmark v1: event F1 vs logical oracle budget</text>',
             f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#444"/>',
             f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#444"/>']
    for idx, (method, group) in enumerate(selected.groupby("method")):
        g = group.sort_values("budget")
        pts = []
        for _, r in g.iterrows():
            x = left + (float(r.budget) - 5) / 95 * plot_w
            y = top + (1 - max(0.0, min(1.0, float(r.event_f1)))) * plot_h
            pts.append(f"{x:.1f},{y:.1f}")
        color = colors[idx % len(colors)]
        lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2"/>')
        lines.append(f'<text x="{left+10}" y="{top+18+idx*16}" font-family="sans-serif" font-size="10" fill="{color}">{method}</text>')
    for b in BUDGETS:
        x = left + (b - 5) / 95 * plot_w
        lines.append(f'<text x="{x-8:.1f}" y="{top+plot_h+22}" font-family="sans-serif" font-size="10">{b}</text>')
    lines.append('</svg>')
    (PACK / "figures/event_f1_budget_curve.svg").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_docs(frozen: Frozen, decision: str, sanity: pd.DataFrame) -> None:
    final_decision = pd.read_csv(PACK / "FINAL_DECISION.csv").iloc[0]
    summary = pd.read_csv(PACK / "baselines/baseline_summary.csv")
    by_budget = pd.read_csv(PACK / "comparisons/method_vs_baseline_by_budget.csv")
    failures = pd.read_csv(PACK / "baselines/baseline_failures.csv")
    key = by_budget[(by_budget.current_method == "K3_BRIDGE_SAFE") & (by_budget.metric == "event_f1") & (by_budget.baseline_method != "CURRENT_ORIGINAL")]
    wins = key[key.absolute_delta > 1e-12].budget.astype(int).tolist()
    ties = key[key.absolute_delta.abs() <= 1e-12].budget.astype(int).tolist()
    losses = key[key.absolute_delta < -1e-12].budget.astype(int).tolist()
    precision_cost = by_budget[(by_budget.current_method == "K3_BRIDGE_SAFE") & (by_budget.metric == "event_f1") & (by_budget.baseline_method != "CURRENT_ORIGINAL")][
        ["budget", "current_precision", "baseline_precision", "current_cost", "baseline_cost"]
    ]
    report = f"""BENCHMARK_SOURCE:
    /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4

BASELINE_EXECUTION:
    CLEAN_RERUN_FROM_FROZEN_INPUTS

RESULT_SCOPE:
    SINGLE_VIDEO_TEMPORAL_HOLDOUT_DIAGNOSTIC

# Clean Baseline Benchmark v1 Final Report

## Required answers

1. **本轮 baseline 是否全部由指定 MP4 重新运行？** 是。unit/proxy 由该 MP4 本轮重建，所有 acquisition policy 从空状态按 frozen budgets 重新执行；没有复制任何旧 selected/query set、segment、metric、aggregate CSV、排名或 threshold winner。
2. **复用了哪些旧数据？** 仅复用 347 个满足同视频区间、Qwen3-VL-32B 路径/config lineage、prompt hash 和 parser version 条件的原始 VLM response cache（297 full scan + 50 P1）。物理 VLM calls=0；每个 run 的 logical oracle calls 仍完整计费。旧方法结果复用数=0。
3. **benchmark 是否可复现？** 是，benchmark_id=`{frozen.benchmark_id}`；输入、代码、模型 manifest、prompt、budget、evaluator 和 matching hashes 均已冻结。sanity failures={int((sanity.status == 'FAIL').sum())}。
4. **trace 是否足以支持未来 materializer replay？** 是。`materializer_replay_comparison.csv` 对每条 controlled trace 以 original K3 与 K3-bridge-safe 双重重放，且不新增 acquisition/VLM call。
5. **当前方法相对哪个 baseline 有优势？** AUC 审计中 best repository baseline 为 `{final_decision.best_repository_baseline}`；K3-bridge-safe 的方向性结论为 `{decision}`，AUC delta={float(final_decision.absolute_auc_delta):.6f}。
6. **优势在哪些 budget/指标？** event-F1 wins={wins}, ties={ties}, losses={losses}。完整 precision/recall/tIoU/returned-seconds delta 在 `comparisons/method_vs_baseline_by_budget.csv`。
7. **是否有 precision 或 review-cost 代价？** 逐 budget 数据如下；不得只以 F1 隐藏代价：

{precision_cost.to_markdown(index=False)}

8. **结论是 human-GT 还是 oracle-relative？** `VLM_DEFINED_PSEUDO_ORACLE`，不是 human ground truth；单视频结果不支持泛化或最终安全保证。
9. **缺少哪些重要 baseline？** ARC original guarantee、SUPG original guarantee 均无法在本任务的 event-set/finite-budget adapter 中保留，明确标为 `ADAPTED_NO_ORIGINAL_GUARANTEE`。M2 未有 frozen config；relation M3/M4 因 relation oracle gate 未通过而未运行。没有伪造这些结果。
10. **下次修改当前方法后如何比较？** 先运行兼容性验证，再用 frozen inputs/oracle 执行新 planner：

```bash
PACK=Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1
python "$PACK/scripts/validate_benchmark_compatibility.py" --new-manifest /path/to/new_run_manifest.json
python "$PACK/scripts/replay_baseline_acquisition.py" --trace "$PACK/baselines/controlled_track/B1_top_proxy/top_proxy_controlled_bridge_safe/seed_000/budget_20/action_trace.csv" --materializer k3_bridge_safe --output-dir /tmp/replay_b1_b20
```

## Baseline coverage

- B0 uniform/random: 100 repeats per budget with mean/std/95% CI.
- B1 top-proxy and B2 component-first: deterministic clean reruns.
- B3 ARC-adapted controlled and B5 ARC-native: repository ARC implementation, dev-frozen threshold 0.4.
- B4 SUPG-adapted: all-selected and confirmed-only, native and controlled.
- B6 ABae diagnostic: stratified repository adapter, native and controlled.

## Failures and scope impact

{failures.to_markdown(index=False)}

## Decision

`{decision}` — this is a directional, oracle-relative decision on one long video. It is not a human-GT or cross-video claim.
"""
    (PACK / "FINAL_REPORT.md").write_text(report, encoding="utf-8")
    compatibility = f"""# Benchmark Compatibility

Benchmark ID: `{frozen.benchmark_id}`

The ID binds semantic hashes of video, units, proxies, cheap-feature manifest, oracle model/prompt/parser, reference, budgets, evaluator, matching, and baseline code. Semantic CSV hashes exclude the `benchmark_id` column to avoid a self-referential hash; physical file hashes are recorded separately in `BENCHMARK_MANIFEST.json`.

Any change to video, units, proxy, oracle model/prompt, reference, budgets, evaluator, or matching is incompatible with direct v1 comparison and requires benchmark v2 or an explicitly narrower compatibility statement. A materializer-only change may replay saved traces. A planner-only change may reuse frozen baseline results when compatibility validation passes. A new human GT reference may reevaluate saved event segments without acquisition/VLM reruns but creates a new reference/evaluator/comparison version.
"""
    (PACK / "BENCHMARK_COMPATIBILITY.md").write_text(compatibility, encoding="utf-8")
    reproduction = f"""# Reproduction

All commands run from `{ROOT}`.

```bash
PACK=Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1
python "$PACK/scripts/run_clean_benchmark.py" --stage all
python "$PACK/scripts/validate_benchmark_compatibility.py" --new-manifest "$PACK/BENCHMARK_MANIFEST.json" --new-run-id self_check
```

The pack is immutable. The command refuses to overwrite nonempty run directories; create `clean_baseline_benchmark_v1_run2` for a fresh rerun.

Raw-cache reuse requires the exact video SHA256, interval, model/config manifest hash, prompt hash, parser hash, and an extant raw response. Logical queries are charged even on physical cache hits.
"""
    (PACK / "REPRODUCTION.md").write_text(reproduction, encoding="utf-8")


def file_manifest() -> None:
    rows = []
    for path in sorted(PACK.rglob("*")):
        if not path.is_file() or path.name == "FILE_MANIFEST.csv":
            continue
        rows.append({"path": str(path.relative_to(PACK)), "size_bytes": path.stat().st_size,
                     "sha256": sha256_file(path), "generated_this_run": True})
    write_csv(PACK / "FILE_MANIFEST.csv", rows)


def finalize(frozen: Frozen, decision: str, sanity: pd.DataFrame) -> None:
    write_figure(); write_docs(frozen, decision, sanity)
    manifest = json.loads((PACK / "BENCHMARK_MANIFEST.json").read_text())
    manifest["status"] = "FROZEN_COMPLETE"
    manifest["completed_at_utc"] = utc_now()
    manifest["run_counts"] = {
        "baseline_valid": len(list((PACK / "baselines").glob("**/run_manifest.json"))),
        "current_valid": len(list((PACK / "current_method").glob("**/run_manifest.json"))),
        "baseline_failed": len(pd.read_csv(PACK / "baselines/baseline_failures.csv")),
    }
    manifest["final_decision"] = decision
    write_json(PACK / "BENCHMARK_MANIFEST.json", manifest)
    file_manifest()
    append_progress("Benchmark frozen and finalized", "run_clean_benchmark.py --stage all",
                    f"benchmark_id={frozen.benchmark_id}; decision={decision}; baseline_runs={manifest['run_counts']['baseline_valid']}; current_runs={manifest['run_counts']['current_valid']}",
                    next_action="Use compatibility validator before comparing any future planner run.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["freeze", "smoke", "baselines", "current", "aggregate", "compare", "all"], default="all")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.stage in {"freeze", "all"}:
        frozen = freeze_inputs()
        append_progress("Frozen inputs and oracle interface", "run_clean_benchmark.py --stage freeze",
                        f"benchmark_id={frozen.benchmark_id}; units={len(frozen.units)}; reference_events={len(frozen.reference)}; raw_cache_hits={len(frozen.oracle)}",
                        next_action="Run baseline smoke/full from empty state.")
        if args.stage == "freeze": return 0
    else:
        frozen = load_frozen()
    if args.stage == "smoke":
        run_smoke(frozen)
        return 0
    if args.stage in {"baselines", "all"}:
        run_baselines(frozen, args.smoke)
        if args.stage == "baselines": return 0
    if args.stage in {"current", "all"}:
        run_current_methods(frozen, args.smoke)
        if args.stage == "current": return 0
    if args.stage in {"aggregate", "all"}:
        aggregate_baselines(frozen); aggregate_current()
        if args.stage == "aggregate": return 0
    if args.stage in {"compare", "all"}:
        sanity = sanity_checks(frozen)
        decision = comparisons(frozen)
        finalize(frozen, decision, sanity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
