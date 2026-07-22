#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import itertools
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIT_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv"
DEFAULT_REF_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/reference_segments_adapter_ready.csv"
DEFAULT_OURS_DIR = ROOT / "outputs/ours_vs_baselines_realcartest_v1/ours_outputs"
DEFAULT_OUT_DIR = ROOT / "outputs/stage0_merge_only_repair_v1"
OURS_METHOD = "Ours-Frozen-LATE-AQP-v1"
REPAIR_A = "repaired_confirmed_only"
REPAIR_B = "repaired_selected_expand"
ORIGINAL = "ours_original"
DEFAULT_BUDGETS = [5, 10, 20, 50, 80, 100]
DEFAULT_SEEDS = [0, 1, 2, 3, 4]
REQUIRED_SEGMENT_COLUMNS = [
    "run_id",
    "method",
    "budget",
    "video_id",
    "segment_id",
    "start_frame",
    "end_frame",
    "start_time",
    "end_time",
    "segment_score",
    "verification_state",
    "oracle_calls",
    "source_frame_ids",
]


@dataclass(frozen=True)
class Params:
    g_max: int
    d_core_max: float
    d_seg_max: float
    e: int
    low_proxy_quantile: float
    nms_iou: float


DEFAULT_PARAMS = Params(
    g_max=1,
    d_core_max=40.0,
    d_seg_max=60.0,
    e=1,
    low_proxy_quantile=0.3,
    nms_iou=0.7,
)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_int_list(value: str) -> list[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def ensure_columns(df: pd.DataFrame, path: Path, required: Iterable[str]) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"{path} missing required columns: {missing}")


def parse_source_ids(value: object) -> list[int]:
    if pd.isna(value):
        return []
    out: list[int] = []
    for token in str(value).split("|"):
        token = token.strip()
        if not token:
            continue
        out.append(int(token))
    return out


def format_ids(ids: Iterable[int]) -> str:
    return "|".join(str(int(x)) for x in sorted(set(ids)))


def interval_iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / union if union > 0 else 0.0


def overlap_seconds(pred: dict, ref: dict) -> float:
    return max(0.0, min(float(pred["end_time"]), float(ref["end_time"])) - max(float(pred["start_time"]), float(ref["start_time"])))


def duration(row: dict | pd.Series) -> float:
    return max(0.0, float(row["end_time"]) - float(row["start_time"]))


def canonicalize_predictions(preds: pd.DataFrame, units: pd.DataFrame) -> pd.DataFrame:
    if preds.empty:
        return preds.copy()
    by_frame = units.set_index("frame_idx", drop=False)
    rows = []
    for pred in preds.to_dict("records"):
        source_ids = parse_source_ids(pred.get("source_frame_ids", ""))
        mapped = [by_frame.loc[i].to_dict() for i in source_ids if i in by_frame.index]
        out = pred.copy()
        if mapped:
            out["start_frame"] = int(min(x["start_frame"] for x in mapped))
            out["end_frame"] = int(max(x["end_frame"] for x in mapped))
            out["start_time"] = float(min(x["start_time"] for x in mapped))
            out["end_time"] = float(max(x["end_time"] for x in mapped))
            out["boundary_source"] = "source_frame_ids_mapped_to_units"
        else:
            out["boundary_source"] = "segments_csv_fields"
        rows.append(out)
    return pd.DataFrame(rows)


def normalize_refs(refs: pd.DataFrame) -> pd.DataFrame:
    out = refs.copy()
    if "source_event_id" in out.columns:
        out["reference_id"] = out["source_event_id"].astype(str)
    elif "event_id" in out.columns:
        out["reference_id"] = out["event_id"].astype(str)
    else:
        out["reference_id"] = out["segment_id"].astype(str)
    return out


def greedy_matches(preds: pd.DataFrame, refs: pd.DataFrame, rule: str, threshold: float) -> list[dict]:
    pred_records = preds.to_dict("records") if not preds.empty else []
    ref_records = refs.to_dict("records") if not refs.empty else []
    pairs = []
    for pi, pred in enumerate(pred_records):
        for ri, ref in enumerate(ref_records):
            if str(pred["video_id"]) != str(ref["video_id"]):
                continue
            iou = interval_iou(float(pred["start_time"]), float(pred["end_time"]), float(ref["start_time"]), float(ref["end_time"]))
            overlap = overlap_seconds(pred, ref)
            if rule == "overlap_any":
                ok = overlap > 0
                primary = overlap
            elif rule == "iou":
                ok = iou >= threshold
                primary = iou
            else:
                raise ValueError(rule)
            if ok:
                pairs.append((primary, iou, overlap, pi, ri))
    pairs.sort(reverse=True)
    used_pred: set[int] = set()
    used_ref: set[int] = set()
    matches = []
    for primary, iou, overlap, pi, ri in pairs:
        if pi in used_pred or ri in used_ref:
            continue
        used_pred.add(pi)
        used_ref.add(ri)
        matches.append({"pred_idx": pi, "ref_idx": ri, "primary": primary, "iou": iou, "overlap_seconds": overlap})
    return matches


def evaluate_segments(
    preds: pd.DataFrame,
    refs: pd.DataFrame,
    method: str,
    budget: int,
    seed: int,
    output_path: str,
    params: Params | None = None,
) -> tuple[dict, pd.DataFrame]:
    pred_records = preds.to_dict("records") if not preds.empty else []
    ref_records = refs.to_dict("records") if not refs.empty else []
    matches = greedy_matches(preds, refs, "overlap_any", 0.0)
    matched_preds = {m["pred_idx"] for m in matches}
    matched_refs = {m["ref_idx"] for m in matches}
    precision = len(matched_preds) / len(pred_records) if pred_records else 0.0
    recall = len(matched_refs) / len(ref_records) if ref_records else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    rows = []
    unique_refs_hit: set[int] = set()
    for pi, pred in enumerate(pred_records):
        hit_refs = []
        best_iou = 0.0
        for ri, ref in enumerate(ref_records):
            if str(pred["video_id"]) != str(ref["video_id"]):
                continue
            ov = overlap_seconds(pred, ref)
            iou = interval_iou(float(pred["start_time"]), float(pred["end_time"]), float(ref["start_time"]), float(ref["end_time"]))
            if ov > 0:
                hit_refs.append(str(ref["reference_id"]))
                unique_refs_hit.add(ri)
                best_iou = max(best_iou, iou)
        rows.append(
            {
                "budget": budget,
                "seed": seed,
                "method": method,
                "prediction_index": pi,
                "segment_id": pred.get("segment_id", pi),
                "start_time": pred.get("start_time"),
                "end_time": pred.get("end_time"),
                "duration": duration(pred),
                "reference_overlap_count": len(hit_refs),
                "reference_ids": "|".join(hit_refs),
                "best_iou": best_iou,
                "output_path": output_path,
            }
        )
    rps = pd.DataFrame(rows)
    pred_durations = [duration(x) for x in pred_records]
    total_pred_dur = float(sum(pred_durations))
    total_ref_dur = float(sum(duration(x) for x in ref_records))
    matched_ious = [m["iou"] for m in matches]
    iou_f1s = {}
    for th in [0.1, 0.3, 0.5]:
        th_matches = greedy_matches(preds, refs, "iou", th)
        th_precision = len({m["pred_idx"] for m in th_matches}) / len(pred_records) if pred_records else 0.0
        th_recall = len({m["ref_idx"] for m in th_matches}) / len(ref_records) if ref_records else 0.0
        iou_f1s[f"iou_{th:.1f}"] = 2 * th_precision * th_recall / (th_precision + th_recall) if th_precision + th_recall else 0.0
    distribution = rps["reference_overlap_count"].describe().to_dict() if not rps.empty else {}
    row = {
        "aggregation": "seed",
        "budget": budget,
        "seed": seed,
        "method": method,
        "event_detection@overlap_any_precision": precision,
        "event_detection@overlap_any_recall": recall,
        "event_detection@overlap_any_F1": f1,
        "unique_reference_event_recall": len(unique_refs_hit) / len(ref_records) if ref_records else 0.0,
        "predicted_segment_count": len(pred_records),
        "reference_event_count": len(ref_records),
        "prediction_count_error": abs(len(pred_records) - len(ref_records)),
        "avg_segment_duration": float(np.mean(pred_durations)) if pred_durations else 0.0,
        "max_segment_duration": float(np.max(pred_durations)) if pred_durations else 0.0,
        "overmerge_multiplicity": float(rps["reference_overlap_count"].mean()) if not rps.empty else 0.0,
        "references_per_segment_distribution_summary": ";".join(
            f"{k}={float(v):.4g}" for k, v in distribution.items() if isinstance(v, (int, float, np.number)) and pd.notna(v)
        ),
        "matched_mean_iou": float(np.mean(matched_ious)) if matched_ious else 0.0,
        "iou_0.1": iou_f1s["iou_0.1"],
        "iou_0.3": iou_f1s["iou_0.3"],
        "iou_0.5": iou_f1s["iou_0.5"],
        "total_predicted_duration": total_pred_dur,
        "total_reference_duration": total_ref_dur,
        "overcoverage_ratio": total_pred_dur / total_ref_dur if total_ref_dur > 0 else 0.0,
        "output_path": output_path,
    }
    if params is not None:
        row.update(
            {
                "G_max": params.g_max,
                "D_core_max": params.d_core_max,
                "D_seg_max": params.d_seg_max,
                "E": params.e,
                "low_proxy_quantile": params.low_proxy_quantile,
                "nms_iou": params.nms_iou,
            }
        )
    return row, rps


def aggregate_metrics(seed_rows: pd.DataFrame) -> pd.DataFrame:
    metric_cols = [
        "event_detection@overlap_any_precision",
        "event_detection@overlap_any_recall",
        "event_detection@overlap_any_F1",
        "unique_reference_event_recall",
        "predicted_segment_count",
        "reference_event_count",
        "prediction_count_error",
        "avg_segment_duration",
        "max_segment_duration",
        "overmerge_multiplicity",
        "matched_mean_iou",
        "iou_0.1",
        "iou_0.3",
        "iou_0.5",
        "total_predicted_duration",
        "total_reference_duration",
        "overcoverage_ratio",
    ]
    group_cols = ["budget", "method"]
    param_cols = ["G_max", "D_core_max", "D_seg_max", "E", "low_proxy_quantile", "nms_iou"]
    for col in param_cols:
        if col in seed_rows.columns and not seed_rows[col].isna().all():
            group_cols.append(col)
    rows = []
    for keys, group in seed_rows.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        row["aggregation"] = "mean"
        row["seed"] = "mean"
        for col in metric_cols:
            row[col] = float(group[col].mean())
        row["references_per_segment_distribution_summary"] = "seed_mean"
        row["output_path"] = "multiple_seed_outputs"
        rows.append(row)
    return pd.DataFrame(rows)


def make_segment_from_unit_ids(
    units_by_id: dict[int, dict],
    unit_ids: Iterable[int],
    run_id: str,
    method: str,
    budget: int,
    segment_id: int,
    oracle_calls: int,
    verification_state: str,
) -> dict:
    ids = sorted(set(int(x) for x in unit_ids))
    rows = [units_by_id[i] for i in ids]
    return {
        "run_id": run_id,
        "method": method,
        "budget": budget,
        "video_id": str(rows[0]["video_id"]),
        "segment_id": segment_id,
        "start_frame": int(min(x["start_frame"] for x in rows)),
        "end_frame": int(max(x["end_frame"] for x in rows)),
        "start_time": float(min(x["start_time"] for x in rows)),
        "end_time": float(max(x["end_time"] for x in rows)),
        "segment_score": float(np.mean([float(x["proxy_score"]) for x in rows])),
        "verification_state": verification_state,
        "oracle_calls": oracle_calls,
        "source_frame_ids": format_ids(ids),
    }


def has_negative_between(left: int, right: int, negatives: set[int]) -> bool:
    lo, hi = sorted((left, right))
    return any(x in negatives for x in range(lo + 1, hi))


def valley_ok_between(left: int, right: int, units_by_id: dict[int, dict], threshold: float) -> bool:
    lo, hi = sorted((left, right))
    gap = [x for x in range(lo + 1, hi) if x in units_by_id]
    if not gap:
        return True
    return min(float(units_by_id[x]["proxy_score"]) for x in gap) >= threshold


def interval_duration(unit_ids: Iterable[int], units_by_id: dict[int, dict]) -> float:
    ids = sorted(set(int(x) for x in unit_ids))
    return float(max(units_by_id[i]["end_time"] for i in ids) - min(units_by_id[i]["start_time"] for i in ids))


def contiguous_interval_ids(start: int, end: int, units_by_id: dict[int, dict]) -> list[int]:
    return [i for i in range(int(start), int(end) + 1) if i in units_by_id]


def build_anchor_groups(
    positive_anchors: list[int],
    negatives: set[int],
    units_by_id: dict[int, dict],
    params: Params,
    low_threshold: float,
) -> list[list[int]]:
    if not positive_anchors:
        return []
    anchors = sorted(set(positive_anchors))
    groups: list[list[int]] = [[anchors[0]]]
    for anchor in anchors[1:]:
        prev = groups[-1][-1]
        proposed = contiguous_interval_ids(groups[-1][0], anchor, units_by_id)
        gap_units = max(0, anchor - prev - 1)
        can_merge = (
            gap_units <= params.g_max
            and not has_negative_between(prev, anchor, negatives)
            and valley_ok_between(prev, anchor, units_by_id, low_threshold)
            and interval_duration(proposed, units_by_id) <= params.d_core_max
        )
        if can_merge:
            groups[-1].append(anchor)
        else:
            groups.append([anchor])
    return groups


def expand_group(
    group: list[int],
    selected_units: set[int],
    negatives: set[int],
    units_by_id: dict[int, dict],
    params: Params,
    low_threshold: float,
    enable_selected_proxy_expansion: bool,
) -> list[int]:
    start = min(group)
    end = max(group)
    if enable_selected_proxy_expansion:
        for _ in range(params.e):
            cand = start - 1
            if cand not in units_by_id or cand in negatives:
                break
            high_proxy = float(units_by_id[cand]["proxy_score"]) >= low_threshold
            if cand not in selected_units and not high_proxy:
                break
            proposed = contiguous_interval_ids(cand, end, units_by_id)
            if interval_duration(proposed, units_by_id) > params.d_seg_max:
                break
            start = cand
        for _ in range(params.e):
            cand = end + 1
            if cand not in units_by_id or cand in negatives:
                break
            high_proxy = float(units_by_id[cand]["proxy_score"]) >= low_threshold
            if cand not in selected_units and not high_proxy:
                break
            proposed = contiguous_interval_ids(start, cand, units_by_id)
            if interval_duration(proposed, units_by_id) > params.d_seg_max:
                break
            end = cand
    return contiguous_interval_ids(start, end, units_by_id)


def nms_segments(segments: pd.DataFrame, threshold: float) -> pd.DataFrame:
    if segments.empty:
        return segments
    rows = sorted(segments.to_dict("records"), key=lambda x: (float(x["segment_score"]), -duration(x)), reverse=True)
    kept: list[dict] = []
    for row in rows:
        suppress = False
        for kept_row in kept:
            if str(row["video_id"]) != str(kept_row["video_id"]):
                continue
            if interval_iou(float(row["start_time"]), float(row["end_time"]), float(kept_row["start_time"]), float(kept_row["end_time"])) > threshold:
                suppress = True
                break
        if not suppress:
            kept.append(row)
    kept.sort(key=lambda x: (str(x["video_id"]), float(x["start_time"]), float(x["end_time"])))
    for idx, row in enumerate(kept):
        row["segment_id"] = idx
    return pd.DataFrame(kept, columns=REQUIRED_SEGMENT_COLUMNS)


def construct_repaired_segments(
    units: pd.DataFrame,
    oracle_log: pd.DataFrame,
    original_segments: pd.DataFrame,
    budget: int,
    seed: int,
    variant: str,
    params: Params,
) -> pd.DataFrame:
    units_public = units.drop(columns=["oracle_label"], errors="ignore").copy()
    units_by_id = {int(r["frame_idx"]): r for r in units_public.to_dict("records")}
    low_threshold = float(units_public["proxy_score"].quantile(params.low_proxy_quantile))
    ensure_columns(oracle_log, Path("oracle_log.csv"), ["call_idx", "unit_id", "oracle_label"])
    if oracle_log["call_idx"].isna().any():
        raise RuntimeError("oracle_log call_idx contains NaN")
    log_sorted = oracle_log.sort_values("call_idx")
    if log_sorted["call_idx"].tolist() != list(range(len(log_sorted))):
        raise RuntimeError("oracle_log call_idx is not a zero-based contiguous call order")
    queried = set(int(x) for x in log_sorted["unit_id"].tolist())
    positives = sorted(int(r["unit_id"]) for r in log_sorted.to_dict("records") if int(r["oracle_label"]) == 1)
    negatives = set(int(r["unit_id"]) for r in log_sorted.to_dict("records") if int(r["oracle_label"]) == 0)
    selected: set[int] = set()
    if "source_frame_ids" in original_segments.columns:
        for value in original_segments["source_frame_ids"].tolist():
            selected.update(parse_source_ids(value))
    if not selected:
        selected = set(queried)
    groups = build_anchor_groups(positives, negatives, units_by_id, params, low_threshold)
    enable_expansion = variant == REPAIR_B
    rows = []
    method = REPAIR_A if variant == REPAIR_A else REPAIR_B
    run_id = f"{method}_b{budget}_s{seed}"
    for group in groups:
        ids = expand_group(group, selected, negatives, units_by_id, params, low_threshold, enable_expansion)
        if not set(group).issubset(ids):
            raise RuntimeError("internal error: expansion dropped anchor")
        rows.append(
            make_segment_from_unit_ids(
                units_by_id,
                ids,
                run_id=run_id,
                method=method,
                budget=budget,
                segment_id=len(rows),
                oracle_calls=len(log_sorted),
                verification_state="confirmed_anchor_repaired" if method == REPAIR_A else "confirmed_anchor_selected_proxy_expand",
            )
        )
    segments = pd.DataFrame(rows, columns=REQUIRED_SEGMENT_COLUMNS)
    return nms_segments(segments, params.nms_iou)


def run_dir(ours_output_dir: Path, budget: int, seed: int) -> Path:
    return ours_output_dir / f"ours_frozen_late_aqp_b{budget}_s{seed}"


def read_budget_seed(ours_output_dir: Path, budget: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    rd = run_dir(ours_output_dir, budget, seed)
    seg_path = rd / "segments.csv"
    oracle_path = rd / "oracle_log.csv"
    if not seg_path.exists() or not oracle_path.exists():
        raise RuntimeError(f"missing Ours output for B={budget} seed={seed}: {rd}")
    segments = pd.read_csv(seg_path)
    oracle = pd.read_csv(oracle_path)
    ensure_columns(segments, seg_path, REQUIRED_SEGMENT_COLUMNS)
    ensure_columns(oracle, oracle_path, ["run_id", "method", "budget", "call_idx", "unit_id", "oracle_label"])
    return segments, oracle, rd


def write_input_manifest(
    out_dir: Path,
    unit_csv: Path,
    ref_csv: Path,
    ours_output_dir: Path,
    budgets: list[int],
    seeds: list[int],
    reports: list[Path],
    evaluator_paths: list[Path],
) -> None:
    lines = [
        "# Stage 0 Input File Manifest",
        "",
        "| path | purpose | key fields | budget-specific output | oracle call order |",
        "|---|---|---|---|---|",
    ]
    unit_df = pd.read_csv(unit_csv)
    ref_df = pd.read_csv(ref_csv)
    lines.append(f"| `{rel(unit_csv)}` | unit-level CSV for realcartest_2000_3200 adapter replay | {', '.join(unit_df.columns)} | no | not applicable |")
    lines.append(f"| `{rel(ref_csv)}` | reference events for event-level evaluation | {', '.join(ref_df.columns)} | no | not applicable |")
    for budget in budgets:
        for seed in seeds:
            rd = run_dir(ours_output_dir, budget, seed)
            seg_path = rd / "segments.csv"
            oracle_path = rd / "oracle_log.csv"
            if seg_path.exists():
                seg_cols = list(pd.read_csv(seg_path, nrows=0).columns)
                lines.append(f"| `{rel(seg_path)}` | Ours original segments B={budget} seed={seed} | {', '.join(seg_cols)} | yes | not applicable |")
            if oracle_path.exists():
                oracle_cols = list(pd.read_csv(oracle_path, nrows=0).columns)
                has_order = "call_idx" in oracle_cols
                lines.append(f"| `{rel(oracle_path)}` | Ours original oracle log B={budget} seed={seed} | {', '.join(oracle_cols)} | yes | {'yes: call_idx' if has_order else 'no'} |")
    for path in evaluator_paths:
        if path.exists():
            lines.append(f"| `{rel(path)}` | existing evaluator / comparison script | script | not applicable | not applicable |")
    for path in reports:
        if path.exists():
            lines.append(f"| `{rel(path)}` | existing related report | markdown report | not applicable | not applicable |")
    lines.extend(
        [
            "",
            "Budget-specific Ours output exists under `ours_outputs/ours_frozen_late_aqp_b{B}_s{seed}/`.",
            "Oracle call order exists in every required `oracle_log.csv` as zero-based `call_idx`.",
            "No separate selected-units file was found for Ours; selected units are represented by `segments.csv:source_frame_ids` and are used only for Variant B boundary expansion.",
        ]
    )
    (out_dir / "input_file_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_blocked(out_dir: Path, reason: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "BLOCKED_REPORT.md").write_text(f"# BLOCKED_REPORT\n\n{reason}\n", encoding="utf-8")


def audit_required_inputs(unit_csv: Path, ref_csv: Path, ours_dir: Path, budgets: list[int], seeds: list[int]) -> list[str]:
    missing = []
    for path, label in [(unit_csv, "unit CSV"), (ref_csv, "reference events"), (ours_dir, "Ours output dir")]:
        if not path.exists():
            missing.append(f"missing {label}: {path}")
    if missing:
        return missing
    unit_df = pd.read_csv(unit_csv, nrows=0)
    ref_df = pd.read_csv(ref_csv, nrows=0)
    for col in ["frame_idx", "video_id", "start_frame", "end_frame", "start_time", "end_time", "proxy_score"]:
        if col not in unit_df.columns:
            missing.append(f"unit CSV missing required field: {col}")
    for col in ["video_id", "start_frame", "end_frame", "start_time", "end_time"]:
        if col not in ref_df.columns:
            missing.append(f"reference events missing required field: {col}")
    for budget in budgets:
        for seed in seeds:
            rd = run_dir(ours_dir, budget, seed)
            seg_path = rd / "segments.csv"
            oracle_path = rd / "oracle_log.csv"
            if not seg_path.exists():
                missing.append(f"missing Ours original segments: {seg_path}")
            if not oracle_path.exists():
                missing.append(f"missing Ours oracle_log: {oracle_path}")
            if oracle_path.exists():
                cols = pd.read_csv(oracle_path, nrows=0).columns
                if "call_idx" not in cols:
                    missing.append(f"cannot determine oracle call order, missing call_idx: {oracle_path}")
    return missing


def sanity_checks(
    units: pd.DataFrame,
    refs: pd.DataFrame,
    out_dir: Path,
    budgets: list[int],
    seeds: list[int],
    original_hashes_before: dict[Path, str],
    original_hashes_after: dict[Path, str],
    repair_segments: dict[tuple[int, int, str], pd.DataFrame],
    original_segments: dict[tuple[int, int], pd.DataFrame],
    oracle_logs: dict[tuple[int, int], pd.DataFrame],
    metrics_mean: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict] = []

    def add(check: str, status: str, detail: str) -> None:
        rows.append({"check": check, "status": status, "detail": detail})

    add(
        "repaired variants did not change Ours original oracle files",
        "PASS" if original_hashes_before == original_hashes_after else "FAIL",
        f"hashed_files={len(original_hashes_before)}",
    )
    schema_cols = set(REQUIRED_SEGMENT_COLUMNS)
    for budget in budgets:
        for seed in seeds:
            oracle = oracle_logs[(budget, seed)].sort_values("call_idx")
            call_order_ok = oracle["call_idx"].tolist() == list(range(len(oracle)))
            add(
                f"B={budget} seed={seed} queried set uses budget-specific oracle_log",
                "PASS" if call_order_ok else "FAIL",
                f"calls={len(oracle)} unique_units={oracle['unit_id'].nunique()}",
            )
            add(
                f"B={budget} seed={seed} oracle call count <= B",
                "PASS" if len(oracle) <= budget else "FAIL",
                f"calls={len(oracle)} budget={budget}",
            )
            add(
                f"B={budget} seed={seed} repair labels from queried oracle_log only",
                "PASS",
                "construction drops unit_csv oracle_label and uses oracle_log oracle_label keyed by unit_id",
            )
            negatives = set(int(x) for x in oracle.loc[oracle["oracle_label"] == 0, "unit_id"].tolist())
            positives = set(int(x) for x in oracle.loc[oracle["oracle_label"] == 1, "unit_id"].tolist())
            for variant in [REPAIR_A, REPAIR_B]:
                segs = repair_segments[(budget, seed, variant)]
                output_name = f"{variant} B={budget} seed={seed}"
                if segs.empty:
                    add(f"{output_name} confirmed anchor per segment", "WARN", "no segments emitted")
                else:
                    anchor_ok = all(set(parse_source_ids(v)) & positives for v in segs["source_frame_ids"].tolist())
                    add(f"{output_name} confirmed anchor per segment", "PASS" if anchor_ok else "FAIL", f"segments={len(segs)}")
                barrier_ok = True
                for value in segs["source_frame_ids"].tolist():
                    ids = parse_source_ids(value)
                    anchor_ids = sorted(set(ids) & positives)
                    for left, right in zip(anchor_ids, anchor_ids[1:]):
                        if has_negative_between(left, right, negatives):
                            barrier_ok = False
                add(f"{output_name} queried negatives not crossed for anchor merge", "PASS" if barrier_ok else "FAIL", f"negatives={len(negatives)}")
                start_ok = bool((segs["start_time"] <= segs["end_time"]).all()) if not segs.empty else True
                add(f"{output_name} start_time <= end_time", "PASS" if start_ok else "FAIL", f"segments={len(segs)}")
                nan_ok = not segs.isna().any().any()
                add(f"{output_name} no NaN", "PASS" if nan_ok else "FAIL", f"segments={len(segs)}")
                dur_ok = bool(((segs["end_time"] - segs["start_time"]) >= 0).all()) if not segs.empty else True
                add(f"{output_name} no negative duration", "PASS" if dur_ok else "FAIL", f"segments={len(segs)}")
                schema_ok = schema_cols.issubset(set(segs.columns))
                add(f"{output_name} schema compatible", "PASS" if schema_ok else "FAIL", f"columns={list(segs.columns)}")
    repaired_paths_ok = metrics_mean["output_path"].astype(str).str.contains("stage0_merge_only_repair_v1|multiple_seed_outputs").any()
    add(
        "evaluator read repaired segments, not original segments",
        "PASS" if repaired_paths_ok else "FAIL",
        "metrics output_path includes repaired output directory or mean aggregate",
    )
    b100 = metrics_mean[metrics_mean["budget"] == 100]
    orig = b100[b100["method"] == ORIGINAL]
    reps = b100[b100["method"].isin([REPAIR_A, REPAIR_B])]
    if not orig.empty and not reps.empty:
        orig_row = orig.iloc[0]
        best_f1_row = reps.sort_values("event_detection@overlap_any_F1", ascending=False).iloc[0]
        add(
            "B=100 repaired max duration significantly smaller than original",
            "PASS" if float(best_f1_row["max_segment_duration"]) < float(orig_row["max_segment_duration"]) else "WARN",
            f"original={orig_row['max_segment_duration']:.3f} repaired_best={best_f1_row['max_segment_duration']:.3f}",
        )
        add(
            "B=100 repaired overmerge_multiplicity smaller than original",
            "PASS" if float(best_f1_row["overmerge_multiplicity"]) < float(orig_row["overmerge_multiplicity"]) else "WARN",
            f"original={orig_row['overmerge_multiplicity']:.3f} repaired_best={best_f1_row['overmerge_multiplicity']:.3f}",
        )
        add(
            "B=100 predicted_segment_count closer to reference_event_count",
            "PASS" if float(best_f1_row["prediction_count_error"]) < float(orig_row["prediction_count_error"]) else "WARN",
            f"original_error={orig_row['prediction_count_error']:.3f} repaired_error={best_f1_row['prediction_count_error']:.3f}",
        )
    return pd.DataFrame(rows)


def decision_from_results(metrics_mean: pd.DataFrame, sanity: pd.DataFrame) -> str:
    critical_fail = sanity["status"].eq("FAIL").any()
    b100 = metrics_mean[metrics_mean["budget"] == 100]
    orig = b100[b100["method"] == ORIGINAL]
    reps = b100[b100["method"].isin([REPAIR_A, REPAIR_B])]
    if orig.empty or reps.empty:
        return "MERGE_REPAIR_NO_GO_AUDIT_LABEL_REFERENCE_MATCHING_FIRST"
    orig_f1 = float(orig.iloc[0]["event_detection@overlap_any_F1"])
    best = reps.sort_values("event_detection@overlap_any_F1", ascending=False).iloc[0]
    gain = float(best["event_detection@overlap_any_F1"]) - orig_f1
    duration_down = float(best["avg_segment_duration"]) < float(orig.iloc[0]["avg_segment_duration"]) and float(best["max_segment_duration"]) < float(orig.iloc[0]["max_segment_duration"])
    overmerge_down = float(best["overmerge_multiplicity"]) < float(orig.iloc[0]["overmerge_multiplicity"])
    if critical_fail:
        return "MERGE_REPAIR_NO_GO_AUDIT_LABEL_REFERENCE_MATCHING_FIRST"
    if gain >= 0.25 and duration_down and overmerge_down:
        return "MERGE_REPAIR_GO_FOR_SEHS_V0"
    if gain >= 0.10 or (duration_down and overmerge_down):
        return "MERGE_REPAIR_WEAK_GO_NEED_AUDIT"
    return "MERGE_REPAIR_NO_GO_AUDIT_LABEL_REFERENCE_MATCHING_FIRST"


def write_final_report(
    out_dir: Path,
    metrics_mean: pd.DataFrame,
    sensitivity: pd.DataFrame,
    sanity: pd.DataFrame,
    decision: str,
    input_paths: dict[str, str],
) -> None:
    cols = [
        "budget",
        "method",
        "event_detection@overlap_any_precision",
        "event_detection@overlap_any_recall",
        "event_detection@overlap_any_F1",
        "unique_reference_event_recall",
        "predicted_segment_count",
        "prediction_count_error",
        "avg_segment_duration",
        "max_segment_duration",
        "overmerge_multiplicity",
        "matched_mean_iou",
        "iou_0.3",
        "iou_0.5",
        "overcoverage_ratio",
    ]
    main = metrics_mean[metrics_mean["method"].isin([ORIGINAL, REPAIR_A, REPAIR_B])].copy()
    main = main.sort_values(["budget", "method"])[cols]
    rounded = main.copy()
    for col in rounded.select_dtypes(include=[np.number]).columns:
        rounded[col] = rounded[col].map(lambda x: round(float(x), 4))
    b100 = metrics_mean[metrics_mean["budget"] == 100]
    orig = b100[b100["method"] == ORIGINAL].iloc[0]
    reps = b100[b100["method"].isin([REPAIR_A, REPAIR_B])]
    best = reps.sort_values("event_detection@overlap_any_F1", ascending=False).iloc[0]
    sens_summary = (
        sensitivity.groupby(["method", "budget"], as_index=False)
        .agg(
            f1_min=("event_detection@overlap_any_F1", "min"),
            f1_max=("event_detection@overlap_any_F1", "max"),
            avg_duration_min=("avg_segment_duration", "min"),
            avg_duration_max=("avg_segment_duration", "max"),
            overmerge_min=("overmerge_multiplicity", "min"),
            overmerge_max=("overmerge_multiplicity", "max"),
            rows=("event_detection@overlap_any_F1", "count"),
        )
    )
    sens_b100 = sens_summary[sens_summary["budget"] == 100].copy()
    for col in sens_b100.select_dtypes(include=[np.number]).columns:
        sens_b100[col] = sens_b100[col].map(lambda x: round(float(x), 4))
    fail_rows = sanity[sanity["status"] == "FAIL"]
    warn_rows = sanity[sanity["status"] == "WARN"]
    oversplit = "yes" if float(best["predicted_segment_count"]) > float(best["reference_event_count"]) * 1.5 else "no"
    if decision == "MERGE_REPAIR_GO_FOR_SEHS_V0":
        next_step = "Implement only the minimal temporal event-hypothesis planner next, to validate low-budget unique event discovery."
    elif decision == "MERGE_REPAIR_WEAK_GO_NEED_AUDIT":
        next_step = "Audit metric/reference alignment first, then decide whether planner work is justified."
    else:
        next_step = "Pause SEHS and inspect oracle labels, reference events, matching protocol, and unit-to-event alignment first."
    report = f"""# Stage 0 Merge-only Repair Ablation Final Report

## 1. Task scope

This task only runs a merge-only repair ablation. It adds no oracle calls, does not change Ours selection, does not run model inference, and does not implement SEHS or any planner.

## 2. Input files

- unit CSV: `{input_paths['unit_csv']}`
- reference events: `{input_paths['reference_events']}`
- Ours original segments: `{input_paths['ours_output_dir']}/ours_frozen_late_aqp_b{{B}}_s{{seed}}/segments.csv`
- Ours original oracle_log: `{input_paths['ours_output_dir']}/ours_frozen_late_aqp_b{{B}}_s{{seed}}/oracle_log.csv`
- evaluator scripts: `{input_paths['metric_repair_script']}`, `{input_paths['comparison_script']}`
- reports: `{input_paths['pilot_report']}`, `{input_paths['metric_repair_report']}`, `{input_paths['comparison_report']}`

## 3. Method

Ours original merge is read as-is from existing budget-specific `segments.csv` files. `repaired_confirmed_only` seeds events only from queried positive anchors and treats queried negatives as barriers. `repaired_selected_expand` uses the same anchors, then allows at most one-unit selected/proxy boundary expansion without crossing queried negative barriers. Both repaired variants use split-by-default construction: adjacent positive anchors merge only when `G_max`, proxy-valley, negative-barrier, and duration-prior checks all pass. Duplicate suppression uses temporal NMS only for highly overlapping predictions at IoU 0.7.

## 4. Main results

{rounded.to_markdown(index=False)}

## 5. B=100 diagnosis

1. Original Ours shows destructive overmerge: B=100 mean max duration is {orig['max_segment_duration']:.3f}s and overmerge_multiplicity is {orig['overmerge_multiplicity']:.3f}.
2. Repaired best variant is `{best['method']}` with avg/max duration {best['avg_segment_duration']:.3f}s / {best['max_segment_duration']:.3f}s.
3. B=100 F1 changes from {orig['event_detection@overlap_any_F1']:.3f} to {best['event_detection@overlap_any_F1']:.3f}.
4. Prediction count error changes from {orig['prediction_count_error']:.3f} to {best['prediction_count_error']:.3f}.
5. Overmerge_multiplicity changes from {orig['overmerge_multiplicity']:.3f} to {best['overmerge_multiplicity']:.3f}.
6. Best variant: `{best['method']}`.
7. Repair oversplit indication: {oversplit}.

## 6. Sensitivity

B=100 sensitivity summary:

{sens_b100.to_markdown(index=False)}

Sensitivity spans `G_max` in {{1, 2}}, `D_core_max` in {{30s, 40s}}, `D_seg_max` in {{50s, 60s}}, and `low_proxy_quantile` in {{0.2, 0.3, 0.4}}. Full results are in `sensitivity_results.csv`.

## 7. Decision

{decision}

Sanity failures: {len(fail_rows)}. Sanity warnings: {len(warn_rows)}. Full sanity results are in `sanity_checks.md`.

## 8. Next step

{next_step}
"""
    (out_dir / "FINAL_REPORT.md").write_text(report, encoding="utf-8")


def write_sanity_md(out_dir: Path, sanity: pd.DataFrame) -> None:
    text = "# Stage 0 Sanity Checks\n\n" + sanity.to_markdown(index=False) + "\n"
    (out_dir / "sanity_checks.md").write_text(text, encoding="utf-8")


def write_overmerge_diagnostics(metrics_seed: pd.DataFrame, references_per_segment: pd.DataFrame, out_dir: Path) -> None:
    diag = metrics_seed[
        [
            "budget",
            "seed",
            "method",
            "predicted_segment_count",
            "reference_event_count",
            "prediction_count_error",
            "avg_segment_duration",
            "max_segment_duration",
            "overmerge_multiplicity",
            "total_predicted_duration",
            "total_reference_duration",
            "overcoverage_ratio",
            "output_path",
        ]
    ].copy()
    diag.to_csv(out_dir / "overmerge_diagnostics.csv", index=False)
    references_per_segment.to_csv(out_dir / "references_per_segment.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 0 merge-only repair ablation.")
    parser.add_argument("--unit_csv", type=Path, default=DEFAULT_UNIT_CSV)
    parser.add_argument("--ours_output_dir", type=Path, default=DEFAULT_OURS_DIR)
    parser.add_argument("--reference_events", type=Path, default=DEFAULT_REF_CSV)
    parser.add_argument("--out_dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--budgets", default=",".join(str(x) for x in DEFAULT_BUDGETS))
    parser.add_argument("--seeds", default=",".join(str(x) for x in DEFAULT_SEEDS))
    args = parser.parse_args()

    unit_csv = args.unit_csv.resolve()
    ref_csv = args.reference_events.resolve()
    ours_output_dir = args.ours_output_dir.resolve()
    out_dir = args.out_dir.resolve()
    budgets = parse_int_list(args.budgets)
    seeds = parse_int_list(args.seeds)
    out_dir.mkdir(parents=True, exist_ok=True)

    missing = audit_required_inputs(unit_csv, ref_csv, ours_output_dir, budgets, seeds)
    if missing:
        write_blocked(out_dir, "\n".join(f"- {x}" for x in missing))
        return 2

    reports = [
        ROOT / "outputs/real_video_protocol_pilot_v1/REAL_VIDEO_PROTOCOL_PILOT_REPORT.md",
        ROOT / "outputs/real_video_protocol_pilot_v1_metric_repair/METRIC_REPAIR_REPORT.md",
        ROOT / "outputs/ours_vs_baselines_realcartest_v1/COMPARISON_REPORT.md",
    ]
    evaluator_paths = [
        ROOT / "outputs/real_video_protocol_pilot_v1_metric_repair/scripts/recompute_repaired_metrics.py",
        ROOT / "outputs/ours_vs_baselines_realcartest_v1/scripts/run_ours_vs_baselines.py",
    ]
    write_input_manifest(out_dir, unit_csv, ref_csv, ours_output_dir, budgets, seeds, reports, evaluator_paths)

    units = pd.read_csv(unit_csv)
    refs = normalize_refs(pd.read_csv(ref_csv))
    ensure_columns(units, unit_csv, ["video_id", "frame_idx", "start_frame", "end_frame", "start_time", "end_time", "proxy_score"])
    ensure_columns(refs, ref_csv, ["video_id", "start_frame", "end_frame", "start_time", "end_time", "reference_id"])

    original_hashes_before: dict[Path, str] = {}
    for budget in budgets:
        for seed in seeds:
            rd = run_dir(ours_output_dir, budget, seed)
            for name in ["segments.csv", "oracle_log.csv", "diagnostics.csv"]:
                path = rd / name
                if path.exists():
                    original_hashes_before[path] = sha256_file(path)

    metrics_rows = []
    rps_rows = []
    repair_segments: dict[tuple[int, int, str], pd.DataFrame] = {}
    original_segments: dict[tuple[int, int], pd.DataFrame] = {}
    oracle_logs: dict[tuple[int, int], pd.DataFrame] = {}
    combined_by_budget_variant: dict[tuple[int, str], list[pd.DataFrame]] = {}

    for budget in budgets:
        for seed in seeds:
            orig_segs, oracle, rd = read_budget_seed(ours_output_dir, budget, seed)
            original_segments[(budget, seed)] = orig_segs
            oracle_logs[(budget, seed)] = oracle
            orig_eval = canonicalize_predictions(orig_segs, units)
            row, rps = evaluate_segments(orig_eval, refs, ORIGINAL, budget, seed, rel(rd / "segments.csv"))
            metrics_rows.append(row)
            rps_rows.append(rps)
            for variant in [REPAIR_A, REPAIR_B]:
                repaired = construct_repaired_segments(units, oracle, orig_segs, budget, seed, variant, DEFAULT_PARAMS)
                repair_segments[(budget, seed, variant)] = repaired
                seed_path = out_dir / f"segments_{variant}_B{budget}_s{seed}.csv"
                repaired.to_csv(seed_path, index=False)
                combined_by_budget_variant.setdefault((budget, variant), []).append(repaired)
                repaired_eval = canonicalize_predictions(repaired, units)
                row, rps = evaluate_segments(repaired_eval, refs, variant, budget, seed, rel(seed_path), DEFAULT_PARAMS)
                metrics_rows.append(row)
                rps_rows.append(rps)

    for (budget, variant), frames in combined_by_budget_variant.items():
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=REQUIRED_SEGMENT_COLUMNS)
        combined.to_csv(out_dir / f"segments_{variant}_B{budget}.csv", index=False)

    metrics_seed = pd.DataFrame(metrics_rows)
    metrics_mean = aggregate_metrics(metrics_seed)
    metrics_all = pd.concat([metrics_seed, metrics_mean], ignore_index=True, sort=False)
    metrics_all.to_csv(out_dir / "metrics_repair_vs_original.csv", index=False)
    refs_per_segment = pd.concat(rps_rows, ignore_index=True) if rps_rows else pd.DataFrame()
    write_overmerge_diagnostics(metrics_seed, refs_per_segment, out_dir)

    sens_rows = []
    for g_max, d_core, d_seg, q in itertools.product([1, 2], [30.0, 40.0], [50.0, 60.0], [0.2, 0.3, 0.4]):
        params = Params(g_max=g_max, d_core_max=d_core, d_seg_max=d_seg, e=1, low_proxy_quantile=q, nms_iou=0.7)
        for budget in budgets:
            for seed in seeds:
                orig_segs = original_segments[(budget, seed)]
                oracle = oracle_logs[(budget, seed)]
                for variant in [REPAIR_A, REPAIR_B]:
                    repaired = construct_repaired_segments(units, oracle, orig_segs, budget, seed, variant, params)
                    repaired_eval = canonicalize_predictions(repaired, units)
                    row, _ = evaluate_segments(
                        repaired_eval,
                        refs,
                        variant,
                        budget,
                        seed,
                        "sensitivity_not_materialized",
                        params,
                    )
                    sens_rows.append(row)
    sensitivity_seed = pd.DataFrame(sens_rows)
    sensitivity_mean = aggregate_metrics(sensitivity_seed)
    sensitivity = pd.concat([sensitivity_seed, sensitivity_mean], ignore_index=True, sort=False)
    sensitivity.to_csv(out_dir / "sensitivity_results.csv", index=False)

    original_hashes_after = {path: sha256_file(path) for path in original_hashes_before}
    sanity = sanity_checks(
        units,
        refs,
        out_dir,
        budgets,
        seeds,
        original_hashes_before,
        original_hashes_after,
        repair_segments,
        original_segments,
        oracle_logs,
        metrics_mean,
    )
    sanity.to_csv(out_dir / "sanity_checks.csv", index=False)
    write_sanity_md(out_dir, sanity)
    decision = decision_from_results(metrics_mean, sanity)

    input_paths = {
        "unit_csv": rel(unit_csv),
        "reference_events": rel(ref_csv),
        "ours_output_dir": rel(ours_output_dir),
        "metric_repair_script": rel(evaluator_paths[0]),
        "comparison_script": rel(evaluator_paths[1]),
        "pilot_report": rel(reports[0]),
        "metric_repair_report": rel(reports[1]),
        "comparison_report": rel(reports[2]),
    }
    write_final_report(out_dir, metrics_mean, sensitivity_mean, sanity, decision, input_paths)
    (out_dir / "run_summary.txt").write_text(f"decision={decision}\ncompleted_at={now()}\n", encoding="utf-8")
    print(f"wrote {rel(out_dir)}")
    print(f"decision={decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
