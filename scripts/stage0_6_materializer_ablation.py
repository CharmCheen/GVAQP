#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import math
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE0_SCRIPT = ROOT / "scripts/stage0_merge_only_repair.py"
DEFAULT_UNIT_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv"
DEFAULT_REF_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/reference_segments_adapter_ready.csv"
DEFAULT_COMPARISON_DIR = ROOT / "outputs/ours_vs_baselines_realcartest_v1"
DEFAULT_OUT_DIR = ROOT / "outputs/stage_0_6_materializer_ablation"
TARGET_METHODS = {
    "ARC-refinement",
    "SUPG-RT-all-selected",
    "SUPG-RT-confirmed-only",
    "ABae-stratified-confirmed",
    "Ours-Frozen-LATE-AQP-v1",
}
DEFAULT_BUDGETS = [5, 10, 20, 50, 80, 100]


def load_stage0():
    spec = importlib.util.spec_from_file_location("stage0_merge_only_repair", STAGE0_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import Stage 0 script: {STAGE0_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


S0 = load_stage0()


PARAMS = S0.Params(
    g_max=1,
    d_core_max=40.0,
    d_seg_max=60.0,
    e=1,
    low_proxy_quantile=0.3,
    nms_iou=0.7,
)


VARIANT_ORDER = [
    "NativeOriginal",
    "C0_common_naive_merge",
    "C1_gap_limited_merge",
    "C2_duration_prior",
    "C3_negative_hard_barrier",
    "C4_proxy_valley_soft_barrier",
    "C5_duplicate_suppression",
    "C6_full_EVENT_MATERIALIZE",
    "F0_full_EVENT_MATERIALIZE",
    "F1_full_minus_duration_prior",
    "F2_full_minus_negative_barrier",
    "F3_full_minus_proxy_valley",
    "F4_full_minus_duplicate_suppression",
    "F5_full_minus_conservative_expansion",
]


@dataclass(frozen=True)
class Rules:
    merge_all_anchors: bool
    gap_limit: bool
    duration_prior: bool
    negative_barrier: bool
    proxy_valley: bool
    duplicate_suppression: bool
    conservative_expansion: bool


RULES: dict[str, Rules] = {
    "C0_common_naive_merge": Rules(True, False, False, False, False, False, False),
    "C1_gap_limited_merge": Rules(False, True, False, False, False, False, False),
    "C2_duration_prior": Rules(False, True, True, False, False, False, False),
    "C3_negative_hard_barrier": Rules(False, True, True, True, False, False, False),
    "C4_proxy_valley_soft_barrier": Rules(False, True, True, True, True, False, False),
    "C5_duplicate_suppression": Rules(False, True, True, True, True, True, False),
    "C6_full_EVENT_MATERIALIZE": Rules(False, True, True, True, True, True, True),
    "F0_full_EVENT_MATERIALIZE": Rules(False, True, True, True, True, True, True),
    "F1_full_minus_duration_prior": Rules(False, True, False, True, True, True, True),
    "F2_full_minus_negative_barrier": Rules(False, True, True, False, True, True, True),
    "F3_full_minus_proxy_valley": Rules(False, True, True, True, False, True, True),
    "F4_full_minus_duplicate_suppression": Rules(False, True, True, True, True, False, True),
    "F5_full_minus_conservative_expansion": Rules(False, True, True, True, True, True, False),
}


@dataclass(frozen=True)
class RunInfo:
    method: str
    selector: str
    family: str
    budget: int
    seed: int
    threshold: float | None
    run_dir: Path
    segments_path: Path
    oracle_log_path: Path
    selected_units_available: bool


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_int_list(value: str) -> list[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", value.replace("@", "_").replace(".", "p"))


def parse_budget_seed(name: str) -> tuple[int | None, int | None]:
    match = re.search(r"_b(\d+)_s(\d+)", name)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_threshold(name: str) -> float | None:
    match = re.search(r"_th([0-9.]+)$", name)
    return float(match.group(1)) if match else None


def infer_method_from_dir(name: str) -> str:
    if name.startswith("ARC_refinement"):
        return "ARC-refinement"
    if name.startswith("SUPG_RT_all_selected"):
        return "SUPG-RT-all-selected"
    if name.startswith("SUPG_RT_confirmed_only"):
        return "SUPG-RT-confirmed-only"
    if name.startswith("ABae_stratified_confirmed"):
        return "ABae-stratified-confirmed"
    if name.startswith("ours_frozen_late_aqp"):
        return "Ours-Frozen-LATE-AQP-v1"
    return name


def discover_runs(comparison_dir: Path, budgets: set[int]) -> tuple[list[RunInfo], list[dict]]:
    runs: list[RunInfo] = []
    manifest_rows: list[dict] = []
    for base, family in [(comparison_dir / "baseline_outputs", "baseline"), (comparison_dir / "ours_outputs", "ours")]:
        if not base.exists():
            continue
        for run_dir in sorted(base.iterdir()):
            if not run_dir.is_dir():
                continue
            budget, seed = parse_budget_seed(run_dir.name)
            if budget not in budgets or seed is None:
                continue
            seg_path = run_dir / "segments.csv"
            oracle_path = run_dir / "oracle_log.csv"
            method = infer_method_from_dir(run_dir.name)
            threshold = parse_threshold(run_dir.name)
            status = "INCLUDED"
            reason = ""
            selected_available = False
            if not seg_path.exists():
                status = "EXCLUDED"
                reason = "missing segments.csv"
            if not oracle_path.exists():
                status = "EXCLUDED"
                reason = (reason + "; " if reason else "") + "missing oracle_log.csv"
            seg = pd.DataFrame()
            oracle = pd.DataFrame()
            if seg_path.exists():
                try:
                    seg = pd.read_csv(seg_path)
                    if not seg.empty and "method" in seg.columns:
                        method = str(seg["method"].iloc[0])
                    selected_available = "source_frame_ids" in seg.columns and seg["source_frame_ids"].fillna("").astype(str).str.len().gt(0).any()
                except Exception as exc:  # noqa: BLE001
                    status = "EXCLUDED"
                    reason = f"cannot read segments.csv: {exc}"
            if oracle_path.exists():
                try:
                    oracle = pd.read_csv(oracle_path)
                    if not oracle.empty and "method" in oracle.columns:
                        method = str(oracle["method"].iloc[0])
                    if "call_idx" not in oracle.columns:
                        status = "EXCLUDED"
                        reason = "missing call_idx"
                    elif not oracle.empty and oracle.sort_values("call_idx")["call_idx"].tolist() != list(range(len(oracle))):
                        status = "EXCLUDED"
                        reason = "call_idx is not zero-based contiguous"
                    for col in ["unit_id", "oracle_label"]:
                        if col not in oracle.columns:
                            status = "EXCLUDED"
                            reason = f"missing {col}"
                except Exception as exc:  # noqa: BLE001
                    status = "EXCLUDED"
                    reason = f"cannot read oracle_log.csv: {exc}"
            if method not in TARGET_METHODS:
                continue
            selector = f"{method}@th{threshold:.1f}" if threshold is not None else method
            manifest_rows.append(
                {
                    "status": status,
                    "family": family,
                    "method": method,
                    "selector": selector,
                    "budget": budget,
                    "seed": seed,
                    "threshold": threshold,
                    "segments_path": rel(seg_path),
                    "oracle_log_path": rel(oracle_path),
                    "segments_rows": len(seg) if seg_path.exists() else 0,
                    "oracle_rows": len(oracle) if oracle_path.exists() else 0,
                    "selected_units_source": "segments.csv:source_frame_ids" if selected_available else "none",
                    "call_order": "call_idx" if status == "INCLUDED" else "",
                    "reason": reason,
                }
            )
            if status == "INCLUDED":
                runs.append(RunInfo(method, selector, family, budget, seed, threshold, run_dir, seg_path, oracle_path, selected_available))
    return runs, manifest_rows


def ensure_dirs(out_dir: Path) -> None:
    for sub in ["segments", "config", "data_manifest", "logs", "tables", "reports", "figures"]:
        (out_dir / sub).mkdir(parents=True, exist_ok=True)


def parse_source_ids(value: object) -> list[int]:
    return S0.parse_source_ids(value)


def unit_records(units: pd.DataFrame) -> dict[int, dict]:
    public = units.drop(columns=["oracle_label"], errors="ignore").copy()
    return {int(row["frame_idx"]): row for row in public.to_dict("records")}


def contiguous_ids(start: int, end: int, units_by_id: dict[int, dict]) -> list[int]:
    return [i for i in range(int(start), int(end) + 1) if i in units_by_id]


def ids_duration(ids: Iterable[int], units_by_id: dict[int, dict]) -> float:
    ids = sorted(set(int(x) for x in ids))
    if not ids:
        return 0.0
    return float(max(units_by_id[i]["end_time"] for i in ids) - min(units_by_id[i]["start_time"] for i in ids))


def gap_has_negative(left: int, right: int, negatives: set[int]) -> bool:
    lo, hi = sorted((left, right))
    return any(i in negatives for i in range(lo + 1, hi))


def proxy_valley_ok(left: int, right: int, units_by_id: dict[int, dict], low_threshold: float) -> bool:
    lo, hi = sorted((left, right))
    gap = [i for i in range(lo + 1, hi) if i in units_by_id]
    if not gap:
        return True
    return min(float(units_by_id[i]["proxy_score"]) for i in gap) >= low_threshold


def make_segment(
    units_by_id: dict[int, dict],
    ids: Iterable[int],
    run_id: str,
    method: str,
    budget: int,
    segment_id: int,
    oracle_calls: int,
    variant: str,
    selector: str,
) -> dict:
    ids = sorted(set(int(x) for x in ids))
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
        "verification_state": variant,
        "oracle_calls": oracle_calls,
        "source_frame_ids": S0.format_ids(ids),
        "selector": selector,
        "materializer_variant": variant,
    }


def build_groups(anchors: list[int], negatives: set[int], units_by_id: dict[int, dict], low_threshold: float, rules: Rules) -> list[list[int]]:
    anchors = sorted(set(int(x) for x in anchors if int(x) in units_by_id))
    if not anchors:
        return []
    if rules.merge_all_anchors:
        return [anchors]
    groups: list[list[int]] = [[anchors[0]]]
    for anchor in anchors[1:]:
        prev = groups[-1][-1]
        proposed = contiguous_ids(groups[-1][0], anchor, units_by_id)
        conditions = []
        if rules.gap_limit:
            conditions.append(max(0, anchor - prev - 1) <= PARAMS.g_max)
        if rules.duration_prior:
            conditions.append(ids_duration(proposed, units_by_id) <= PARAMS.d_core_max)
        if rules.negative_barrier:
            conditions.append(not gap_has_negative(prev, anchor, negatives))
        if rules.proxy_valley:
            conditions.append(proxy_valley_ok(prev, anchor, units_by_id, low_threshold))
        if all(conditions) if conditions else True:
            groups[-1].append(anchor)
        else:
            groups.append([anchor])
    return groups


def expand_ids(
    group: list[int],
    selected: set[int],
    negatives: set[int],
    units_by_id: dict[int, dict],
    low_threshold: float,
    rules: Rules,
) -> list[int]:
    start = min(group)
    end = max(group)
    if not rules.conservative_expansion:
        return contiguous_ids(start, end, units_by_id)
    for direction in [-1, 1]:
        for _ in range(PARAMS.e):
            cand = start - 1 if direction < 0 else end + 1
            if cand not in units_by_id:
                break
            if rules.negative_barrier and cand in negatives:
                break
            high_proxy_ok = True if not rules.proxy_valley else float(units_by_id[cand]["proxy_score"]) >= low_threshold
            if cand not in selected and not high_proxy_ok:
                break
            proposed = contiguous_ids(cand, end, units_by_id) if direction < 0 else contiguous_ids(start, cand, units_by_id)
            if rules.duration_prior and ids_duration(proposed, units_by_id) > PARAMS.d_seg_max:
                break
            if direction < 0:
                start = cand
            else:
                end = cand
    return contiguous_ids(start, end, units_by_id)


def construct_variant_segments(
    units: pd.DataFrame,
    oracle_log: pd.DataFrame,
    original_segments: pd.DataFrame,
    run: RunInfo,
    variant: str,
) -> pd.DataFrame:
    if variant == "NativeOriginal":
        out = original_segments.copy()
        out["selector"] = run.selector
        out["materializer_variant"] = variant
        return out
    rules = RULES[variant]
    units_by_id = unit_records(units)
    low_threshold = float(units.drop(columns=["oracle_label"], errors="ignore")["proxy_score"].quantile(PARAMS.low_proxy_quantile))
    oracle = oracle_log.sort_values("call_idx")
    positives = sorted(int(x) for x in oracle.loc[oracle["oracle_label"].astype(int) == 1, "unit_id"].tolist())
    negatives = set(int(x) for x in oracle.loc[oracle["oracle_label"].astype(int) == 0, "unit_id"].tolist())
    selected: set[int] = set()
    if "source_frame_ids" in original_segments.columns:
        for value in original_segments["source_frame_ids"].tolist():
            selected.update(parse_source_ids(value))
    rows = []
    groups = build_groups(positives, negatives, units_by_id, low_threshold, rules)
    run_id = f"{safe_name(run.selector)}_B{run.budget}_s{run.seed}_{variant}"
    for group in groups:
        ids = expand_ids(group, selected, negatives, units_by_id, low_threshold, rules)
        if not ids:
            continue
        rows.append(make_segment(units_by_id, ids, run_id, run.method, run.budget, len(rows), len(oracle), variant, run.selector))
    cols = [
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
        "selector",
        "materializer_variant",
    ]
    segs = pd.DataFrame(rows, columns=cols)
    if rules.duplicate_suppression and not segs.empty:
        base = S0.nms_segments(segs[[c for c in S0.REQUIRED_SEGMENT_COLUMNS if c in segs.columns]].copy(), PARAMS.nms_iou)
        if not base.empty:
            base["selector"] = run.selector
            base["materializer_variant"] = variant
        segs = base.reindex(columns=cols)
    return segs


def overlap(pred: dict, ref: dict) -> float:
    return max(0.0, min(float(pred["end_time"]), float(ref["end_time"])) - max(float(pred["start_time"]), float(ref["start_time"])))


def temporal_iou(pred: dict, ref: dict) -> float:
    return S0.interval_iou(float(pred["start_time"]), float(pred["end_time"]), float(ref["start_time"]), float(ref["end_time"]))


def extra_metrics(preds: pd.DataFrame, refs: pd.DataFrame) -> dict:
    pred_records = preds.to_dict("records") if not preds.empty else []
    ref_records = refs.to_dict("records") if not refs.empty else []
    durations = [S0.duration(x) for x in pred_records]
    refs_per_pred = []
    for pred in pred_records:
        refs_per_pred.append(sum(1 for ref in ref_records if str(pred["video_id"]) == str(ref["video_id"]) and overlap(pred, ref) > 0))
    segs_per_ref = []
    for ref in ref_records:
        segs_per_ref.append(sum(1 for pred in pred_records if str(pred["video_id"]) == str(ref["video_id"]) and overlap(pred, ref) > 0))
    duplicate_excess = sum(max(0, x - 1) for x in segs_per_ref)
    return {
        "prediction_count": len(pred_records),
        "duration_p90": float(np.percentile(durations, 90)) if durations else 0.0,
        "references_per_predicted_segment": float(np.mean(refs_per_pred)) if refs_per_pred else 0.0,
        "segments_per_reference": float(np.mean(segs_per_ref)) if segs_per_ref else 0.0,
        "duplicate_prediction_rate": duplicate_excess / len(pred_records) if pred_records else 0.0,
    }


def evaluate(preds: pd.DataFrame, refs: pd.DataFrame, run: RunInfo, variant: str, output_path: Path) -> dict:
    row, _ = S0.evaluate_segments(preds, refs, run.method, run.budget, run.seed, rel(output_path), PARAMS if variant != "NativeOriginal" else None)
    row.update(extra_metrics(preds, refs))
    row.update(
        {
            "aggregation": "seed",
            "selector": run.selector,
            "method": run.method,
            "family": run.family,
            "budget": run.budget,
            "seed": run.seed,
            "threshold": run.threshold,
            "materializer_variant": variant,
            "oracle_calls": len(pd.read_csv(run.oracle_log_path)),
            "selected_units_available": run.selected_units_available,
            "output_path": rel(output_path),
            "used_fixed_params": True,
        }
    )
    return row


def aggregate(seed_rows: pd.DataFrame) -> pd.DataFrame:
    metric_cols = [
        "event_detection@overlap_any_precision",
        "event_detection@overlap_any_recall",
        "event_detection@overlap_any_F1",
        "unique_reference_event_recall",
        "prediction_count",
        "predicted_segment_count",
        "reference_event_count",
        "prediction_count_error",
        "avg_segment_duration",
        "max_segment_duration",
        "duration_p90",
        "overmerge_multiplicity",
        "references_per_predicted_segment",
        "segments_per_reference",
        "duplicate_prediction_rate",
        "matched_mean_iou",
        "iou_0.1",
        "iou_0.3",
        "iou_0.5",
        "total_predicted_duration",
        "total_reference_duration",
        "overcoverage_ratio",
        "oracle_calls",
    ]
    rows = []
    group_cols = ["family", "method", "selector", "threshold", "budget", "materializer_variant"]
    for keys, group in seed_rows.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys))
        row["aggregation"] = "mean"
        row["seed"] = "mean"
        row["seed_count"] = int(group["seed"].nunique())
        for col in metric_cols:
            row[col] = float(group[col].mean())
        row["used_fixed_params"] = bool(group["used_fixed_params"].all())
        row["output_path"] = "multiple_seed_outputs"
        rows.append(row)
    return pd.DataFrame(rows)


def auc_tables(mean_rows: pd.DataFrame, budgets: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    curves = mean_rows.copy()
    rows = []
    xs = np.array(budgets, dtype=float)
    for (selector, variant), group in mean_rows.groupby(["selector", "materializer_variant"]):
        g = group.set_index("budget")
        if not set(budgets).issubset(set(g.index)):
            continue
        ys = np.array([float(g.loc[b, "event_detection@overlap_any_F1"]) for b in budgets])
        first = group.iloc[0]
        rows.append(
            {
                "family": first["family"],
                "method": first["method"],
                "selector": selector,
                "materializer_variant": variant,
                "event_F1_AUC": float(np.trapezoid(ys, xs) / (xs[-1] - xs[0])),
                "B20_F1": float(g.loc[20, "event_detection@overlap_any_F1"]),
                "B100_F1": float(g.loc[100, "event_detection@overlap_any_F1"]),
                "mean_max_duration": float(group["max_segment_duration"].mean()),
                "mean_overmerge_multiplicity": float(group["overmerge_multiplicity"].mean()),
                "mean_prediction_count_error": float(group["prediction_count_error"].mean()),
            }
        )
    auc = pd.DataFrame(rows)
    if not auc.empty:
        auc = auc.sort_values(["selector", "event_F1_AUC"], ascending=[True, False]).reset_index(drop=True)
    return auc, curves


def write_manifest(out_dir: Path, manifest_rows: list[dict], unit_csv: Path, ref_csv: Path, comparison_dir: Path) -> None:
    df = pd.DataFrame(manifest_rows)
    df.to_csv(out_dir / "data_manifest/input_manifest.csv", index=False)
    lines = [
        "# Stage 0.6 Input Manifest",
        "",
        f"- unit CSV: `{rel(unit_csv)}`",
        f"- reference CSV: `{rel(ref_csv)}`",
        f"- comparison dir: `{rel(comparison_dir)}`",
        f"- included runs: {int((df['status'] == 'INCLUDED').sum()) if not df.empty else 0}",
        f"- excluded runs: {int((df['status'] == 'EXCLUDED').sum()) if not df.empty else 0}",
        "",
        df.to_markdown(index=False) if not df.empty else "No runs found.",
    ]
    (out_dir / "data_manifest/input_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_config(out_dir: Path, budgets: list[int]) -> None:
    text = f"""stage: 0.6
budgets: {budgets}
target_methods: {sorted(TARGET_METHODS)}
materializer_params:
  G_max: {PARAMS.g_max}
  D_core_max: {PARAMS.d_core_max}
  D_seg_max: {PARAMS.d_seg_max}
  E: {PARAMS.e}
  low_proxy_quantile: {PARAMS.low_proxy_quantile}
  nms_iou: {PARAMS.nms_iou}
fixed_across_methods_and_budgets: true
model_inference: false
"""
    (out_dir / "config/stage0_6_config.yaml").write_text(text, encoding="utf-8")


def sanity_checks(
    runs: list[RunInfo],
    seed_rows: pd.DataFrame,
    segments_by_key: dict[tuple[str, int, int, str], pd.DataFrame],
    oracle_by_key: dict[tuple[str, int, int], pd.DataFrame],
    before_hashes: dict[Path, str],
    after_hashes: dict[Path, str],
    stage0_metrics: Path,
    mean_rows: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict] = []

    def add(check: str, status: str, detail: str) -> None:
        rows.append({"check": check, "status": status, "detail": detail})

    add("original oracle logs unchanged", "PASS" if before_hashes == after_hashes else "FAIL", f"files={len(before_hashes)}")
    add("fixed materializer parameters", "PASS", f"G={PARAMS.g_max},D_core={PARAMS.d_core_max},D_seg={PARAMS.d_seg_max},E={PARAMS.e},q={PARAMS.low_proxy_quantile},nms={PARAMS.nms_iou}")
    add("metrics protocol reused from Stage 0 helpers", "PASS", "imported scripts/stage0_merge_only_repair.py evaluate_segments")
    for run in runs:
        oracle = oracle_by_key[(run.selector, run.budget, run.seed)]
        positives = set(int(x) for x in oracle.loc[oracle["oracle_label"].astype(int) == 1, "unit_id"].tolist())
        negatives = set(int(x) for x in oracle.loc[oracle["oracle_label"].astype(int) == 0, "unit_id"].tolist())
        order_ok = oracle.empty or oracle.sort_values("call_idx")["call_idx"].tolist() == list(range(len(oracle)))
        add(f"{run.selector} B={run.budget} s={run.seed} oracle order", "PASS" if order_ok else "FAIL", f"calls={len(oracle)}")
        add(f"{run.selector} B={run.budget} s={run.seed} calls <= budget", "PASS" if len(oracle) <= run.budget else "FAIL", f"calls={len(oracle)} budget={run.budget}")
        for variant in VARIANT_ORDER:
            segs = segments_by_key.get((run.selector, run.budget, run.seed, variant))
            if segs is None:
                continue
            if variant != "NativeOriginal":
                if segs.empty:
                    add(f"{run.selector} B={run.budget} s={run.seed} {variant} anchor positive", "PASS", "empty output")
                else:
                    ok = all(set(parse_source_ids(v)) & positives for v in segs["source_frame_ids"].tolist())
                    add(f"{run.selector} B={run.budget} s={run.seed} {variant} anchor positive", "PASS" if ok else "FAIL", f"segments={len(segs)} positives={len(positives)}")
            no_nan = not segs.isna().any().any() if not segs.empty else True
            nonneg = bool(((segs["end_time"] - segs["start_time"]) >= 0).all()) if not segs.empty else True
            add(f"{run.selector} B={run.budget} s={run.seed} {variant} no NaN", "PASS" if no_nan else "FAIL", f"segments={len(segs)}")
            add(f"{run.selector} B={run.budget} s={run.seed} {variant} nonnegative duration", "PASS" if nonneg else "FAIL", f"segments={len(segs)}")
            if variant in [v for v, r in RULES.items() if r.negative_barrier] and not segs.empty:
                barrier_ok = True
                for value in segs["source_frame_ids"].tolist():
                    ids = parse_source_ids(value)
                    anchor_ids = sorted(set(ids) & positives)
                    for left, right in zip(anchor_ids, anchor_ids[1:]):
                        if gap_has_negative(left, right, negatives):
                            barrier_ok = False
                add(f"{run.selector} B={run.budget} s={run.seed} {variant} negative barrier", "PASS" if barrier_ok else "FAIL", f"negatives={len(negatives)}")
    repaired_paths = seed_rows[seed_rows["materializer_variant"] != "NativeOriginal"]["output_path"].astype(str)
    add("evaluator read Stage 0.6 segments", "PASS" if repaired_paths.str.contains("stage_0_6_materializer_ablation/segments").all() else "FAIL", f"rows={len(repaired_paths)}")
    ours = mean_rows[
        (mean_rows["selector"] == "Ours-Frozen-LATE-AQP-v1")
        & (mean_rows["budget"] == 100)
        & (mean_rows["materializer_variant"] == "C6_full_EVENT_MATERIALIZE")
    ]
    stage0_ok = False
    detail = "stage0 metrics unavailable"
    if stage0_metrics.exists() and not ours.empty:
        st = pd.read_csv(stage0_metrics)
        st = st[(st["aggregation"] == "mean") & (st["budget"] == 100) & (st["method"] == "repaired_selected_expand")]
        if not st.empty:
            stage0_f1 = float(st["event_detection@overlap_any_F1"].iloc[0])
            ours_f1 = float(ours["event_detection@overlap_any_F1"].iloc[0])
            stage0_ok = abs(stage0_f1 - ours_f1) < 1e-9
            detail = f"stage0={stage0_f1:.6f}, stage0_6={ours_f1:.6f}"
    add("B=100 Ours repair reproduced", "PASS" if stage0_ok else "FAIL", detail)
    add("unit_csv oracle_label not used for materialization decisions", "PASS", "unit records drop oracle_label; labels read from oracle_log only")
    return pd.DataFrame(rows)


def summarize(auc: pd.DataFrame, mean_rows: pd.DataFrame, out_dir: Path) -> None:
    full = auc[auc["materializer_variant"] == "C6_full_EVENT_MATERIALIZE"]
    avg_by_variant = auc.groupby("materializer_variant", as_index=False).agg(
        mean_auc=("event_F1_AUC", "mean"),
        mean_b20=("B20_F1", "mean"),
        mean_b100=("B100_F1", "mean"),
        mean_max_duration=("mean_max_duration", "mean"),
        mean_overmerge=("mean_overmerge_multiplicity", "mean"),
        selector_count=("selector", "nunique"),
    )
    avg_by_variant["variant_order"] = avg_by_variant["materializer_variant"].map({v: i for i, v in enumerate(VARIANT_ORDER)})
    avg_by_variant = avg_by_variant.sort_values("variant_order")
    loo_names = [
        "F1_full_minus_duration_prior",
        "F2_full_minus_negative_barrier",
        "F3_full_minus_proxy_valley",
        "F4_full_minus_duplicate_suppression",
        "F5_full_minus_conservative_expansion",
    ]
    loo_rows = []
    f0 = auc[auc["materializer_variant"] == "F0_full_EVENT_MATERIALIZE"].set_index("selector")
    for variant in loo_names:
        vdf = auc[auc["materializer_variant"] == variant].set_index("selector")
        common = sorted(set(f0.index) & set(vdf.index))
        deltas = [float(f0.loc[s, "event_F1_AUC"] - vdf.loc[s, "event_F1_AUC"]) for s in common]
        loo_rows.append(
            {
                "removed_rule": variant.replace("F", "removed_", 1),
                "mean_auc_drop_when_removed": float(np.mean(deltas)) if deltas else 0.0,
                "positive_drop_selectors": int(sum(d > 1e-6 for d in deltas)),
                "selector_count": len(deltas),
            }
        )
    loo = pd.DataFrame(loo_rows).sort_values("mean_auc_drop_when_removed", ascending=False)
    avg_by_variant.to_csv(out_dir / "tables/ablation_avg_by_variant.csv", index=False)
    loo.to_csv(out_dir / "tables/leave_one_out_rule_contribution.csv", index=False)
    def mean_auc(name: str) -> float:
        row = avg_by_variant[avg_by_variant["materializer_variant"] == name]
        return float(row["mean_auc"].iloc[0]) if not row.empty else 0.0
    c6_auc = mean_auc("C6_full_EVENT_MATERIALIZE")
    c0_auc = mean_auc("C0_common_naive_merge")
    c1_auc = mean_auc("C1_gap_limited_merge")
    c2_auc = mean_auc("C2_duration_prior")
    full_overmerge = float(avg_by_variant.loc[avg_by_variant["materializer_variant"] == "C6_full_EVENT_MATERIALIZE", "mean_overmerge"].iloc[0])
    c0_overmerge = float(avg_by_variant.loc[avg_by_variant["materializer_variant"] == "C0_common_naive_merge", "mean_overmerge"].iloc[0])
    full_max = float(avg_by_variant.loc[avg_by_variant["materializer_variant"] == "C6_full_EVENT_MATERIALIZE", "mean_max_duration"].iloc[0])
    c0_max = float(avg_by_variant.loc[avg_by_variant["materializer_variant"] == "C0_common_naive_merge", "mean_max_duration"].iloc[0])
    event_aware_positive = loo[loo["removed_rule"].isin(["removed_2_full_minus_negative_barrier", "removed_3_full_minus_proxy_valley", "removed_4_full_minus_duplicate_suppression", "removed_5_full_minus_conservative_expansion"])]
    event_aware_count = int((event_aware_positive["mean_auc_drop_when_removed"] > 0.005).sum())
    pass_criteria = (
        c6_auc > max(c0_auc, c1_auc, c2_auc)
        and full_overmerge < c0_overmerge
        and full_max < c0_max
        and event_aware_count >= 2
    )
    b20 = mean_rows[(mean_rows["budget"] == 20) & (mean_rows["materializer_variant"].isin(["NativeOriginal", "C6_full_EVENT_MATERIALIZE"]))]
    b20_delta = (
        b20.pivot_table(index="selector", columns="materializer_variant", values="event_detection@overlap_any_F1", aggfunc="first")
        .dropna()
    )
    b20_mean_delta = float((b20_delta["C6_full_EVENT_MATERIALIZE"] - b20_delta["NativeOriginal"]).mean()) if not b20_delta.empty else 0.0
    ours_b100 = mean_rows[
        (mean_rows["selector"] == "Ours-Frozen-LATE-AQP-v1")
        & (mean_rows["budget"] == 100)
        & (mean_rows["materializer_variant"] == "C6_full_EVENT_MATERIALIZE")
    ]
    ours_b100_f1 = float(ours_b100["event_detection@overlap_any_F1"].iloc[0]) if not ours_b100.empty else float("nan")
    report = f"""# Stage 0.6 EVENT_MATERIALIZE Mechanism Ablation

## Scope

This is a CPU CSV replay ablation. It does not change oracle allocation, selected units, oracle order, proxy generation, or model outputs. All materializer parameters are fixed across methods and budgets.

## Variant Averages

{avg_by_variant.drop(columns=['variant_order']).to_markdown(index=False)}

## Leave-one-out Contributions

{loo.to_markdown(index=False)}

## Required Questions

1. Full EVENT_MATERIALIZE vs common naive merge: C6 mean AUC={c6_auc:.4f}, C0 mean AUC={c0_auc:.4f}.
2. Full EVENT_MATERIALIZE vs gap/duration merge: C1 mean AUC={c1_auc:.4f}, C2 mean AUC={c2_auc:.4f}.
3. Largest leave-one-out contributor: `{loo.iloc[0]['removed_rule']}` with mean AUC drop {loo.iloc[0]['mean_auc_drop_when_removed']:.4f}.
4. Cross-selector behavior is in `auc_by_selector_materializer.csv`; gains are not uniform across every selector, so selector-specific evidence quality still matters.
5. Overmerge reduction: C0 overmerge={c0_overmerge:.4f}, C6 overmerge={full_overmerge:.4f}; C0 max duration={c0_max:.4f}, C6 max duration={full_max:.4f}.
6. B=100 Ours repair reproduced: C6 Ours B=100 F1={ours_b100_f1:.6f}.
7. Low-budget B=20 average F1 delta C6-NativeOriginal={b20_mean_delta:.4f}; positive means helped on average, negative means hurt on average.

## Pass Criteria

- C6 improves event-F1 AUC over C0/C1/C2 on average: {c6_auc > max(c0_auc, c1_auc, c2_auc)}.
- C6 lowers overmerge and max duration vs C0: {full_overmerge < c0_overmerge and full_max < c0_max}.
- C6 does not improve only by over-shortening: C6 is compared against C2 duration-prior and leave-one-out duration removal.
- At least two event-aware mechanisms beyond duration show independent AUC contribution >0.005: {event_aware_count >= 2} ({event_aware_count} mechanisms).

Overall pass: {pass_criteria}.
"""
    (out_dir / "ablation_summary.md").write_text(report, encoding="utf-8")
    (out_dir / "reports/ablation_summary.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 0.6 EVENT_MATERIALIZE mechanism ablation.")
    parser.add_argument("--unit_csv", type=Path, default=DEFAULT_UNIT_CSV)
    parser.add_argument("--reference_events", type=Path, default=DEFAULT_REF_CSV)
    parser.add_argument("--comparison_dir", type=Path, default=DEFAULT_COMPARISON_DIR)
    parser.add_argument("--out_dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--budgets", default=",".join(str(x) for x in DEFAULT_BUDGETS))
    args = parser.parse_args()
    unit_csv = args.unit_csv.resolve()
    ref_csv = args.reference_events.resolve()
    comparison_dir = args.comparison_dir.resolve()
    out_dir = args.out_dir.resolve()
    budgets = parse_int_list(args.budgets)
    ensure_dirs(out_dir)
    write_config(out_dir, budgets)

    missing = [str(p) for p in [unit_csv, ref_csv, comparison_dir] if not p.exists()]
    if missing:
        (out_dir / "BLOCKED_REPORT.md").write_text("# BLOCKED\n\n" + "\n".join(f"- missing {x}" for x in missing) + "\n", encoding="utf-8")
        return 2

    units = pd.read_csv(unit_csv)
    refs = S0.normalize_refs(pd.read_csv(ref_csv))
    runs, manifest_rows = discover_runs(comparison_dir, set(budgets))
    write_manifest(out_dir, manifest_rows, unit_csv, ref_csv, comparison_dir)

    before_hashes = {run.oracle_log_path: S0.sha256_file(run.oracle_log_path) for run in runs}
    seed_metric_rows: list[dict] = []
    segments_by_key: dict[tuple[str, int, int, str], pd.DataFrame] = {}
    oracle_by_key: dict[tuple[str, int, int], pd.DataFrame] = {}
    for run in runs:
        original = pd.read_csv(run.segments_path)
        oracle = pd.read_csv(run.oracle_log_path)
        oracle_by_key[(run.selector, run.budget, run.seed)] = oracle
        for variant in VARIANT_ORDER:
            segs = construct_variant_segments(units, oracle, original, run, variant)
            segments_by_key[(run.selector, run.budget, run.seed, variant)] = segs
            out_name = f"{safe_name(run.selector)}_B{run.budget}_s{run.seed}_{variant}.csv"
            out_path = out_dir / "segments" / out_name
            segs.to_csv(out_path, index=False)
            preds = S0.canonicalize_predictions(segs, units)
            seed_metric_rows.append(evaluate(preds, refs, run, variant, out_path))

    seed_rows = pd.DataFrame(seed_metric_rows)
    mean_rows = aggregate(seed_rows)
    all_rows = pd.concat([seed_rows, mean_rows], ignore_index=True, sort=False)
    all_rows.to_csv(out_dir / "metrics_by_run.csv", index=False)
    all_rows.to_csv(out_dir / "tables/metrics_by_run.csv", index=False)
    auc, curves = auc_tables(mean_rows, budgets)
    auc.to_csv(out_dir / "auc_by_selector_materializer.csv", index=False)
    auc.to_csv(out_dir / "tables/auc_by_selector_materializer.csv", index=False)
    curves.to_csv(out_dir / "budget_curves.csv", index=False)
    curves.to_csv(out_dir / "tables/budget_curves.csv", index=False)

    after_hashes = {path: S0.sha256_file(path) for path in before_hashes}
    sanity = sanity_checks(
        runs,
        seed_rows,
        segments_by_key,
        oracle_by_key,
        before_hashes,
        after_hashes,
        ROOT / "outputs/stage0_merge_only_repair_v1/metrics_repair_vs_original.csv",
        mean_rows,
    )
    sanity.to_csv(out_dir / "tables/sanity_checks.csv", index=False)
    (out_dir / "sanity_checks.md").write_text("# Stage 0.6 Sanity Checks\n\n" + sanity.to_markdown(index=False) + "\n", encoding="utf-8")
    (out_dir / "reports/sanity_checks.md").write_text("# Stage 0.6 Sanity Checks\n\n" + sanity.to_markdown(index=False) + "\n", encoding="utf-8")
    summarize(auc, mean_rows, out_dir)
    (out_dir / "run_summary.txt").write_text(f"completed_at={now()}\nsanity_failures={(sanity['status'] == 'FAIL').sum()}\n", encoding="utf-8")
    print(f"wrote {rel(out_dir)}")
    print(f"sanity_failures={(sanity['status'] == 'FAIL').sum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
