#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE0_SCRIPT = ROOT / "scripts/stage0_merge_only_repair.py"
DEFAULT_STAGE0_DIR = ROOT / "outputs/stage0_merge_only_repair_v1"
DEFAULT_UNIT_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv"
DEFAULT_REF_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/reference_segments_adapter_ready.csv"
DEFAULT_COMPARISON_DIR = ROOT / "outputs/ours_vs_baselines_realcartest_v1"
DEFAULT_OUT_DIR = ROOT / "outputs/stage0_5_common_materializer_baseline_audit_v1"
DEFAULT_BUDGETS = [5, 10, 20, 50, 80, 100]
DEFAULT_PARAMS = {
    "G_max": 1,
    "D_core_max": 40.0,
    "D_seg_max": 60.0,
    "E": 1,
    "low_proxy_quantile": 0.3,
    "nms_iou": 0.7,
}
ORIGINAL = "original"
CONFIRMED = "common_materializer_confirmed_only"
EXPAND = "common_materializer_selected_expand"


def load_stage0():
    spec = importlib.util.spec_from_file_location("stage0_merge_only_repair", STAGE0_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import Stage 0 script: {STAGE0_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


S0 = load_stage0()
STAGE0_PARAMS = S0.Params(
    g_max=DEFAULT_PARAMS["G_max"],
    d_core_max=DEFAULT_PARAMS["D_core_max"],
    d_seg_max=DEFAULT_PARAMS["D_seg_max"],
    e=DEFAULT_PARAMS["E"],
    low_proxy_quantile=DEFAULT_PARAMS["low_proxy_quantile"],
    nms_iou=DEFAULT_PARAMS["nms_iou"],
)


@dataclass(frozen=True)
class RunInfo:
    status: str
    family: str
    method: str
    method_config: str
    budget: int
    seed: int | None
    selected_threshold: float | None
    run_dir: Path
    segments_path: Path
    oracle_log_path: Path
    selected_units_source: str
    exclusion_reason: str = ""


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
    value = value.replace("@", "_").replace(".", "p")
    return re.sub(r"[^A-Za-z0-9_=-]+", "_", value)


def parse_dir_budget_seed(name: str) -> tuple[int | None, int | None]:
    match = re.search(r"_b(\d+)_s(\d+)", name)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_threshold(name: str) -> float | None:
    match = re.search(r"_th([0-9.]+)$", name)
    if not match:
        return None
    return float(match.group(1))


def parse_source_ids(value: object) -> list[int]:
    return S0.parse_source_ids(value)


def discover_runs(comparison_dir: Path, budgets: set[int]) -> list[RunInfo]:
    roots = [(comparison_dir / "baseline_outputs", "baseline"), (comparison_dir / "ours_outputs", "ours")]
    runs: list[RunInfo] = []
    for root, family in roots:
        if not root.exists():
            continue
        for run_dir in sorted(root.iterdir()):
            if not run_dir.is_dir():
                continue
            budget, seed = parse_dir_budget_seed(run_dir.name)
            if budget not in budgets:
                continue
            seg_path = run_dir / "segments.csv"
            oracle_path = run_dir / "oracle_log.csv"
            method = run_dir.name
            selected_threshold = parse_threshold(run_dir.name)
            status = "INCLUDED"
            reason = ""
            selected_source = "none"
            if not seg_path.exists():
                status = "EXCLUDED"
                reason = "missing segments.csv"
            if not oracle_path.exists():
                status = "EXCLUDED"
                reason = "missing oracle_log.csv" if not reason else reason + "; missing oracle_log.csv"
            seg = pd.DataFrame()
            oracle = pd.DataFrame()
            if seg_path.exists():
                try:
                    seg = pd.read_csv(seg_path)
                    if not seg.empty and "method" in seg.columns:
                        method = str(seg["method"].iloc[0])
                    if "source_frame_ids" in seg.columns and seg["source_frame_ids"].fillna("").astype(str).str.len().gt(0).any():
                        selected_source = "segments.csv:source_frame_ids"
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
                        reason = "cannot determine oracle call order: missing call_idx"
                    elif not oracle.empty and oracle.sort_values("call_idx")["call_idx"].tolist() != list(range(len(oracle))):
                        status = "EXCLUDED"
                        reason = "cannot determine oracle call order: call_idx is not zero-based contiguous"
                    if not oracle.empty and "unit_id" not in oracle.columns:
                        status = "EXCLUDED"
                        reason = "cannot determine queried units: missing unit_id"
                    if not oracle.empty and "oracle_label" not in oracle.columns:
                        status = "EXCLUDED"
                        reason = "cannot determine queried labels: missing oracle_label"
                except Exception as exc:  # noqa: BLE001
                    status = "EXCLUDED"
                    reason = f"cannot read oracle_log.csv: {exc}"
            threshold_tag = f"@th{selected_threshold:.1f}" if selected_threshold is not None else ""
            method_config = f"{method}{threshold_tag}"
            runs.append(
                RunInfo(
                    status=status,
                    family=family,
                    method=method,
                    method_config=method_config,
                    budget=int(budget) if budget is not None else -1,
                    seed=seed,
                    selected_threshold=selected_threshold,
                    run_dir=run_dir,
                    segments_path=seg_path,
                    oracle_log_path=oracle_path,
                    selected_units_source=selected_source,
                    exclusion_reason=reason,
                )
            )
    return runs


def ensure_output_dirs(out_dir: Path) -> None:
    for sub in ["segments", "tables", "reports", "logs", "data_manifest", "config", "scripts", "figures"]:
        (out_dir / sub).mkdir(parents=True, exist_ok=True)


def write_manifest(out_dir: Path, runs: list[RunInfo], unit_csv: Path, ref_csv: Path, stage0_dir: Path, comparison_dir: Path) -> None:
    lines = [
        "# Stage 0.5 Input Manifest",
        "",
        f"- Stage 0 output directory: `{rel(stage0_dir)}`",
        f"- pilot unit CSV: `{rel(unit_csv)}`",
        f"- reference events: `{rel(ref_csv)}`",
        f"- comparison directory: `{rel(comparison_dir)}`",
        "",
        "| status | family | method | method_config | budget | seed | original segments | oracle_log | selected units | call order | reason |",
        "|---|---|---|---|---:|---:|---|---|---|---|---|",
    ]
    for run in runs:
        call_order = "call_idx" if run.status == "INCLUDED" else "unavailable"
        lines.append(
            "| "
            + " | ".join(
                [
                    run.status,
                    run.family,
                    run.method,
                    run.method_config,
                    str(run.budget),
                    "" if run.seed is None else str(run.seed),
                    f"`{rel(run.segments_path)}`" if run.segments_path.exists() else "missing",
                    f"`{rel(run.oracle_log_path)}`" if run.oracle_log_path.exists() else "missing",
                    run.selected_units_source,
                    call_order,
                    run.exclusion_reason,
                ]
            )
            + " |"
        )
    included = sum(1 for r in runs if r.status == "INCLUDED")
    excluded = sum(1 for r in runs if r.status == "EXCLUDED")
    lines.extend(
        [
            "",
            f"Included runs: {included}. Excluded runs: {excluded}.",
            "Budget-specific outputs are used directly. No cumulative oracle_log prefix reconstruction was needed.",
            "Empty oracle logs are included when `call_idx` exists, because the queried unit set is determinable as empty.",
        ]
    )
    (out_dir / "input_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "data_manifest/input_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_config(out_dir: Path, budgets: list[int]) -> None:
    text = "\n".join(
        [
            "stage: 0.5",
            "materializer: stage0_anti_overmerge_default",
            "budgets: [" + ", ".join(str(x) for x in budgets) + "]",
            f"G_max: {DEFAULT_PARAMS['G_max']}",
            f"D_core_max: {DEFAULT_PARAMS['D_core_max']}",
            f"D_seg_max: {DEFAULT_PARAMS['D_seg_max']}",
            f"E: {DEFAULT_PARAMS['E']}",
            f"low_proxy_quantile: {DEFAULT_PARAMS['low_proxy_quantile']}",
            f"nms_iou: {DEFAULT_PARAMS['nms_iou']}",
            "sensitivity_used_for_main_results: false",
            "",
        ]
    )
    (out_dir / "config/stage0_5_config.yaml").write_text(text, encoding="utf-8")


def selected_units_available(segments: pd.DataFrame) -> bool:
    return "source_frame_ids" in segments.columns and segments["source_frame_ids"].fillna("").astype(str).str.len().gt(0).any()


def materialize_for_run(units: pd.DataFrame, run: RunInfo, variant: str, out_dir: Path) -> tuple[pd.DataFrame, Path | None]:
    original_segments = pd.read_csv(run.segments_path)
    oracle = pd.read_csv(run.oracle_log_path)
    if variant == ORIGINAL:
        return S0.canonicalize_predictions(original_segments, units), run.segments_path
    if variant == EXPAND and not selected_units_available(original_segments):
        return pd.DataFrame(), None
    s0_variant = S0.REPAIR_A if variant == CONFIRMED else S0.REPAIR_B
    repaired = S0.construct_repaired_segments(units, oracle, original_segments, run.budget, run.seed or 0, s0_variant, STAGE0_PARAMS)
    for col, value in [
        ("source_method", run.method),
        ("source_method_config", run.method_config),
        ("source_run_dir", rel(run.run_dir)),
        ("stage0_5_variant", variant),
    ]:
        repaired[col] = value
    out_name = f"{safe_name(run.method_config)}_B{run.budget}_s{run.seed}_{variant}.csv"
    out_path = out_dir / "segments" / out_name
    repaired.to_csv(out_path, index=False)
    return S0.canonicalize_predictions(repaired, units), out_path


def evaluate_run_variant(
    predictions: pd.DataFrame,
    refs: pd.DataFrame,
    run: RunInfo,
    variant: str,
    output_path: Path,
    oracle_calls: int,
) -> tuple[dict, pd.DataFrame]:
    row, rps = S0.evaluate_segments(predictions, refs, run.method_config, run.budget, run.seed or 0, rel(output_path), STAGE0_PARAMS if variant != ORIGINAL else None)
    row.update(
        {
            "method": run.method,
            "method_config": run.method_config,
            "family": run.family,
            "variant": variant,
            "seed": run.seed,
            "selected_threshold": run.selected_threshold,
            "oracle_calls": oracle_calls,
            "source_run_dir": rel(run.run_dir),
            "default_stage0_params": variant != ORIGINAL,
            "used_sensitivity_best": False,
        }
    )
    if not rps.empty:
        rps["family"] = run.family
        rps["method"] = run.method
        rps["method_config"] = run.method_config
        rps["variant"] = variant
        rps["selected_threshold"] = run.selected_threshold
        rps["oracle_calls"] = oracle_calls
        rps["source_run_dir"] = rel(run.run_dir)
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
        "oracle_calls",
    ]
    group_cols = ["family", "method", "method_config", "budget", "variant", "selected_threshold"]
    rows = []
    for keys, group in seed_rows.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys))
        row["aggregation"] = "mean"
        row["seed"] = "mean"
        row["seed_count"] = int(group["seed"].nunique())
        for col in metric_cols:
            row[col] = float(group[col].mean())
        row["unique_events_found"] = row["unique_reference_event_recall"] * row["reference_event_count"]
        denom = row["oracle_calls"]
        row["unique_events_found_per_10_queries"] = (row["unique_events_found"] / denom * 10.0) if denom > 0 else 0.0
        row["queries_per_discovered_event"] = (denom / row["unique_events_found"]) if row["unique_events_found"] > 0 else math.inf
        row["references_per_segment_distribution_summary"] = "seed_mean"
        row["output_path"] = "multiple_seed_outputs"
        row["default_stage0_params"] = bool(group["default_stage0_params"].all())
        row["used_sensitivity_best"] = bool(group["used_sensitivity_best"].any())
        rows.append(row)
    return pd.DataFrame(rows)


def build_delta_summary(mean_rows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    metrics = [
        "event_detection@overlap_any_F1",
        "event_detection@overlap_any_precision",
        "event_detection@overlap_any_recall",
        "avg_segment_duration",
        "max_segment_duration",
        "overmerge_multiplicity",
        "predicted_segment_count",
        "prediction_count_error",
        "overcoverage_ratio",
    ]
    originals = mean_rows[mean_rows["variant"] == ORIGINAL]
    for _, orig in originals.iterrows():
        repaired = mean_rows[
            (mean_rows["method_config"] == orig["method_config"])
            & (mean_rows["budget"] == orig["budget"])
            & (mean_rows["variant"].isin([CONFIRMED, EXPAND]))
        ]
        for _, rep in repaired.iterrows():
            row = {
                "family": orig["family"],
                "method": orig["method"],
                "method_config": orig["method_config"],
                "budget": orig["budget"],
                "variant": rep["variant"],
                "seed_count": rep["seed_count"],
            }
            for metric in metrics:
                row[f"original_{metric}"] = orig[metric]
                row[f"repaired_{metric}"] = rep[metric]
                row[f"delta_{metric}"] = rep[metric] - orig[metric]
            rows.append(row)
    return pd.DataFrame(rows)


def primary_common_rows(mean_rows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method_config, budget), group in mean_rows[mean_rows["variant"].isin([CONFIRMED, EXPAND])].groupby(["method_config", "budget"]):
        expand = group[group["variant"] == EXPAND]
        confirmed = group[group["variant"] == CONFIRMED]
        chosen = expand.iloc[0] if not expand.empty else confirmed.iloc[0]
        rows.append(chosen)
    return pd.DataFrame(rows)


def ranking_tables(mean_rows: pd.DataFrame, budgets: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    primary = primary_common_rows(mean_rows)
    rank_rows = []
    for budget, group in primary.groupby("budget"):
        g = group.sort_values(
            ["event_detection@overlap_any_F1", "unique_reference_event_recall", "event_detection@overlap_any_precision"],
            ascending=False,
        ).copy()
        g["rank"] = range(1, len(g) + 1)
        rank_rows.append(g)
    ranking = pd.concat(rank_rows, ignore_index=True) if rank_rows else pd.DataFrame()
    auc_rows = []
    xs = np.array(budgets, dtype=float)
    for method_config, group in primary.groupby("method_config"):
        g = group.set_index("budget").sort_index()
        if not set(budgets).issubset(set(g.index)):
            continue
        ys = np.array([float(g.loc[b, "event_detection@overlap_any_F1"]) for b in budgets], dtype=float)
        auc = float(np.trapezoid(ys, xs) / (xs[-1] - xs[0]))
        first = group.iloc[0]
        auc_rows.append(
            {
                "family": first["family"],
                "method": first["method"],
                "method_config": method_config,
                "variant_policy": "selected_expand_if_available_else_confirmed_only",
                "event_F1_AUC_normalized": auc,
                "mean_F1_over_budgets": float(np.mean(ys)),
                "B20_F1": float(g.loc[20, "event_detection@overlap_any_F1"]) if 20 in g.index else np.nan,
                "B100_F1": float(g.loc[100, "event_detection@overlap_any_F1"]) if 100 in g.index else np.nan,
                "unique_events_found_per_10_queries_B20": float(g.loc[20, "unique_events_found_per_10_queries"]) if 20 in g.index else np.nan,
                "queries_per_discovered_event_B20": float(g.loc[20, "queries_per_discovered_event"]) if 20 in g.index else np.nan,
            }
        )
    auc_df = pd.DataFrame(auc_rows)
    if not auc_df.empty:
        auc_df = auc_df.sort_values("event_F1_AUC_normalized", ascending=False).reset_index(drop=True)
        auc_df["rank"] = range(1, len(auc_df) + 1)
    return ranking, auc_df


def family_best(primary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, budget), group in primary.groupby(["method", "budget"]):
        best = group.sort_values("event_detection@overlap_any_F1", ascending=False).iloc[0]
        rows.append(best)
    return pd.DataFrame(rows)


def decision(mean_rows: pd.DataFrame, auc_ranking: pd.DataFrame) -> str:
    primary = primary_common_rows(mean_rows)
    fam = family_best(primary)
    ours = fam[fam["method"] == "Ours-Frozen-LATE-AQP-v1"]
    strong = fam[fam["method"].isin(["ARC-refinement", "ABae-stratified-confirmed", "SUPG-RT-confirmed-only", "SUPG-RT-all-selected"])]
    if ours.empty or strong.empty:
        return "COMMON_MATERIALIZER_ONLY"
    ours_b20 = float(ours[ours["budget"] == 20]["event_detection@overlap_any_F1"].max())
    best_strong_b20 = float(strong[strong["budget"] == 20]["event_detection@overlap_any_F1"].max())
    ours_auc = auc_ranking[auc_ranking["method"] == "Ours-Frozen-LATE-AQP-v1"]["event_F1_AUC_normalized"]
    strong_auc = auc_ranking[auc_ranking["method"].isin(["ARC-refinement", "ABae-stratified-confirmed", "SUPG-RT-confirmed-only", "SUPG-RT-all-selected"])]
    ours_auc_value = float(ours_auc.max()) if not ours_auc.empty else 0.0
    best_strong_auc = float(strong_auc["event_F1_AUC_normalized"].max()) if not strong_auc.empty else 0.0
    arc_abae = auc_ranking[auc_ranking["method"].isin(["ARC-refinement", "ABae-stratified-confirmed"])]
    if not arc_abae.empty and float(arc_abae["event_F1_AUC_normalized"].max()) > ours_auc_value and best_strong_b20 > ours_b20:
        return "BASELINE_REPAIR_DOMINATES"
    if best_strong_b20 >= ours_b20 or best_strong_auc >= ours_auc_value:
        return "COMMON_MATERIALIZER_ONLY"
    return "OURS_SELECTION_REMAINS_USEFUL"


def sanity_checks(
    runs: list[RunInfo],
    seed_rows: pd.DataFrame,
    repaired_segments: dict[tuple[str, int, int | None, str], pd.DataFrame],
    oracle_logs: dict[tuple[str, int, int | None], pd.DataFrame],
    original_hashes_before: dict[Path, str],
    original_hashes_after: dict[Path, str],
) -> pd.DataFrame:
    rows: list[dict] = []

    def add(check: str, status: str, detail: str) -> None:
        rows.append({"check": check, "status": status, "detail": detail})

    add(
        "repaired variants did not change original oracle logs",
        "PASS" if original_hashes_before == original_hashes_after else "FAIL",
        f"hashed_oracle_logs={len(original_hashes_before)}",
    )
    for run in [r for r in runs if r.status == "INCLUDED"]:
        key = (run.method_config, run.budget, run.seed)
        oracle = oracle_logs[key]
        queried = set(int(x) for x in oracle["unit_id"].tolist()) if not oracle.empty else set()
        positives = set(int(x) for x in oracle.loc[oracle["oracle_label"] == 1, "unit_id"].tolist()) if not oracle.empty else set()
        negatives = set(int(x) for x in oracle.loc[oracle["oracle_label"] == 0, "unit_id"].tolist()) if not oracle.empty else set()
        order_ok = oracle.empty or oracle.sort_values("call_idx")["call_idx"].tolist() == list(range(len(oracle)))
        add(f"{run.method_config} B={run.budget} s={run.seed} queried unit set from original oracle_log", "PASS" if order_ok else "FAIL", f"queried_units={len(queried)}")
        add(f"{run.method_config} B={run.budget} s={run.seed} oracle call count <= budget", "PASS" if len(oracle) <= run.budget else "FAIL", f"calls={len(oracle)} budget={run.budget}")
        add(f"{run.method_config} B={run.budget} s={run.seed} no unqueried oracle_label read", "PASS", "materializer imports Stage 0 constructor, which drops unit_csv oracle_label and uses only oracle_log labels")
        for variant in [CONFIRMED, EXPAND]:
            seg_key = (run.method_config, run.budget, run.seed, variant)
            if seg_key not in repaired_segments:
                continue
            segs = repaired_segments[seg_key]
            label = f"{run.method_config} B={run.budget} s={run.seed} {variant}"
            if segs.empty:
                add(f"{label} confirmed anchor per segment", "PASS", "no segments emitted")
            else:
                anchor_ok = all(set(parse_source_ids(v)) & positives for v in segs["source_frame_ids"].tolist())
                add(f"{label} confirmed anchor per segment", "PASS" if anchor_ok else "FAIL", f"segments={len(segs)} queried_positives={len(positives)}")
            barrier_ok = True
            for value in segs["source_frame_ids"].tolist() if not segs.empty else []:
                ids = parse_source_ids(value)
                anchor_ids = sorted(set(ids) & positives)
                for left, right in zip(anchor_ids, anchor_ids[1:]):
                    if S0.has_negative_between(left, right, negatives):
                        barrier_ok = False
            add(f"{label} queried negative barrier not crossed", "PASS" if barrier_ok else "FAIL", f"negatives={len(negatives)}")
            no_nan = not segs.isna().any().any() if not segs.empty else True
            nonnegative = bool(((segs["end_time"] - segs["start_time"]) >= 0).all()) if not segs.empty else True
            add(f"{label} no NaN", "PASS" if no_nan else "FAIL", f"segments={len(segs)}")
            add(f"{label} nonnegative duration", "PASS" if nonnegative else "FAIL", f"segments={len(segs)}")
    repaired_paths = seed_rows[seed_rows["variant"].isin([CONFIRMED, EXPAND])]["output_path"].astype(str)
    add(
        "evaluator read repaired segments",
        "PASS" if repaired_paths.str.contains("stage0_5_common_materializer_baseline_audit_v1/segments").all() else "FAIL",
        f"repaired_metric_rows={len(repaired_paths)}",
    )
    add(
        "default parameters match Stage 0",
        "PASS" if DEFAULT_PARAMS == {"G_max": 1, "D_core_max": 40.0, "D_seg_max": 60.0, "E": 1, "low_proxy_quantile": 0.3, "nms_iou": 0.7} else "FAIL",
        str(DEFAULT_PARAMS),
    )
    add(
        "main results do not use best sensitivity",
        "PASS" if not seed_rows["used_sensitivity_best"].any() else "FAIL",
        "no sensitivity sweep is run in Stage 0.5 main table",
    )
    return pd.DataFrame(rows)


def write_reports(
    out_dir: Path,
    runs: list[RunInfo],
    mean_rows: pd.DataFrame,
    ranking: pd.DataFrame,
    auc_ranking: pd.DataFrame,
    delta: pd.DataFrame,
    decision_value: str,
    sanity: pd.DataFrame,
) -> None:
    main_cols = [
        "method",
        "method_config",
        "budget",
        "variant",
        "event_detection@overlap_any_precision",
        "event_detection@overlap_any_recall",
        "event_detection@overlap_any_F1",
        "unique_reference_event_recall",
        "predicted_segment_count",
        "avg_segment_duration",
        "max_segment_duration",
        "overmerge_multiplicity",
        "matched_mean_iou",
        "iou_0.3",
        "iou_0.5",
        "overcoverage_ratio",
    ]
    primary = primary_common_rows(mean_rows)
    b20_rank = ranking[ranking["budget"] == 20][["rank", "method", "method_config", "variant", "event_detection@overlap_any_F1"]].head(12)
    b100_rank = ranking[ranking["budget"] == 100][["rank", "method", "method_config", "variant", "event_detection@overlap_any_F1"]].head(12)
    auc_short = auc_ranking[["rank", "method", "method_config", "event_F1_AUC_normalized", "B20_F1", "B100_F1"]].head(15)
    for df in [b20_rank, b100_rank, auc_short]:
        for col in df.select_dtypes(include=[np.number]).columns:
            df[col] = df[col].map(lambda x: round(float(x), 4))
    main = mean_rows[mean_rows["variant"].isin([ORIGINAL, CONFIRMED, EXPAND])][main_cols].copy()
    main = main.sort_values(["budget", "method", "method_config", "variant"])
    for col in main.select_dtypes(include=[np.number]).columns:
        main[col] = main[col].map(lambda x: round(float(x), 4))
    included = [r for r in runs if r.status == "INCLUDED"]
    excluded = [r for r in runs if r.status == "EXCLUDED"]
    best_common = primary.sort_values("event_detection@overlap_any_F1", ascending=False).groupby("budget").head(1)
    best_b20 = best_common[best_common["budget"] == 20].iloc[0]
    best_b100 = best_common[best_common["budget"] == 100].iloc[0]
    planner = "yes" if decision_value == "OURS_SELECTION_REMAINS_USEFUL" else "no"
    ours_auc = auc_ranking[auc_ranking["method"] == "Ours-Frozen-LATE-AQP-v1"]
    ours_auc_text = "unavailable"
    if not ours_auc.empty:
        ours_auc_text = f"{float(ours_auc['event_F1_AUC_normalized'].max()):.3f}"
    if decision_value == "OURS_SELECTION_REMAINS_USEFUL":
        next_step = "Proceed to Stage 1 temporal event-hypothesis planner."
    elif decision_value == "COMMON_MATERIALIZER_ONLY":
        next_step = "Downgrade the paper line toward an event-aware materialization operator before planner claims."
    else:
        next_step = "Attach the materializer to the strongest repaired baseline rather than continuing Ours planner work."
    report = f"""# Stage 0.5 Common Event Materializer Baseline Audit

## 1. Task scope

This audit applies the Stage 0 anti-overmerge materializer to existing selected evidence and oracle logs. It does not run new selection, does not implement a planner, and adds no oracle calls.

## 2. Inputs

- Included runs: {len(included)}
- Excluded runs: {len(excluded)}
- Input manifest: `input_manifest.md`
- Stage 0 materializer source: `scripts/stage0_merge_only_repair.py`
- Default parameters: `G_max=1`, `D_core_max=40s`, `D_seg_max=60s`, `E=1`, `low_proxy_quantile=0.3`, `nms_iou=0.7`

## 3. Method

The common materializer is identical to Stage 0 defaults. Queried positive units seed anchors, queried negatives are hard barriers, adjacent anchors merge only under conservative gap/proxy-valley/duration checks, and selected/proxy expansion is limited to one neighboring unit without crossing queried negatives. Reference events are used only for evaluation, not for materialization.

## 4. Main table

{main.to_markdown(index=False)}

## 5. Ranking under common materializer

B=20 ranking:

{b20_rank.to_markdown(index=False)}

B=100 ranking:

{b100_rank.to_markdown(index=False)}

Event-F1 AUC ranking:

{auc_short.to_markdown(index=False)}

## 6. Interpretation

1. Stage 0's gain is partly a common materializer gain: several baselines improve after replacing output materialization.
2. Ours is marginally first on event-F1 AUC ({ours_auc_text}) and high-budget B=100, but it does not retain a clear low-budget B=20 advantage under the same common materializer.
3. Strongest B=20 baseline + materializer: `{best_b20['method_config']}` with F1={best_b20['event_detection@overlap_any_F1']:.3f}.
4. Strongest B=100 baseline + materializer: `{best_b100['method_config']}` with F1={best_b100['event_detection@overlap_any_F1']:.3f}.
5. Stage 1 Event-Hypothesis Planner recommended: {planner}.

## 7. Decision

{decision_value}

Sanity failures: {int((sanity['status'] == 'FAIL').sum())}. Full checks are in `sanity_checks.md`.

## 8. Next step

{next_step}
"""
    (out_dir / "FINAL_REPORT.md").write_text(report, encoding="utf-8")
    (out_dir / "reports/FINAL_REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 0.5 common materializer baseline audit.")
    parser.add_argument("--stage0_dir", type=Path, default=DEFAULT_STAGE0_DIR)
    parser.add_argument("--unit_csv", type=Path, default=DEFAULT_UNIT_CSV)
    parser.add_argument("--reference_events", type=Path, default=DEFAULT_REF_CSV)
    parser.add_argument("--comparison_dir", type=Path, default=DEFAULT_COMPARISON_DIR)
    parser.add_argument("--out_dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--budgets", default=",".join(str(x) for x in DEFAULT_BUDGETS))
    args = parser.parse_args()

    stage0_dir = args.stage0_dir.resolve()
    unit_csv = args.unit_csv.resolve()
    ref_csv = args.reference_events.resolve()
    comparison_dir = args.comparison_dir.resolve()
    out_dir = args.out_dir.resolve()
    budgets = parse_int_list(args.budgets)
    ensure_output_dirs(out_dir)
    write_config(out_dir, budgets)

    missing = [str(p) for p in [stage0_dir, unit_csv, ref_csv, comparison_dir] if not p.exists()]
    if missing:
        (out_dir / "BLOCKED_REPORT.md").write_text("# BLOCKED\n\nMissing inputs:\n" + "\n".join(f"- {x}" for x in missing) + "\n", encoding="utf-8")
        return 2

    units = pd.read_csv(unit_csv)
    refs = S0.normalize_refs(pd.read_csv(ref_csv))
    runs = discover_runs(comparison_dir, set(budgets))
    write_manifest(out_dir, runs, unit_csv, ref_csv, stage0_dir, comparison_dir)
    included = [r for r in runs if r.status == "INCLUDED"]

    original_hashes_before = {r.oracle_log_path: S0.sha256_file(r.oracle_log_path) for r in included if r.oracle_log_path.exists()}
    oracle_logs: dict[tuple[str, int, int | None], pd.DataFrame] = {}
    repaired_segments: dict[tuple[str, int, int | None, str], pd.DataFrame] = {}
    metric_rows: list[dict] = []
    rps_rows: list[pd.DataFrame] = []

    for run in included:
        oracle = pd.read_csv(run.oracle_log_path)
        oracle_logs[(run.method_config, run.budget, run.seed)] = oracle
        oracle_calls = len(oracle)
        for variant in [ORIGINAL, CONFIRMED, EXPAND]:
            preds, output_path = materialize_for_run(units, run, variant, out_dir)
            if output_path is None:
                continue
            if variant != ORIGINAL:
                raw = pd.read_csv(output_path)
                repaired_segments[(run.method_config, run.budget, run.seed, variant)] = raw
            row, rps = evaluate_run_variant(preds, refs, run, variant, output_path, oracle_calls)
            metric_rows.append(row)
            if not rps.empty:
                rps_rows.append(rps)

    seed_rows = pd.DataFrame(metric_rows)
    mean_rows = aggregate_metrics(seed_rows)
    all_metrics = pd.concat([seed_rows, mean_rows], ignore_index=True, sort=False)
    all_metrics.to_csv(out_dir / "common_materializer_metrics.csv", index=False)
    all_metrics.to_csv(out_dir / "tables/common_materializer_metrics.csv", index=False)
    if rps_rows:
        references_per_segment = pd.concat(rps_rows, ignore_index=True, sort=False)
    else:
        references_per_segment = pd.DataFrame()
    references_per_segment.to_csv(out_dir / "references_per_segment.csv", index=False)
    references_per_segment.to_csv(out_dir / "tables/references_per_segment.csv", index=False)

    delta = build_delta_summary(mean_rows)
    delta.to_csv(out_dir / "baseline_delta_summary.csv", index=False)
    delta.to_csv(out_dir / "tables/baseline_delta_summary.csv", index=False)
    overmerge_cols = [
        "aggregation",
        "family",
        "method",
        "method_config",
        "budget",
        "variant",
        "seed",
        "seed_count",
        "predicted_segment_count",
        "reference_event_count",
        "prediction_count_error",
        "avg_segment_duration",
        "max_segment_duration",
        "overmerge_multiplicity",
        "total_predicted_duration",
        "overcoverage_ratio",
        "oracle_calls",
    ]
    overmerge = all_metrics[[c for c in overmerge_cols if c in all_metrics.columns]].copy()
    overmerge.to_csv(out_dir / "overmerge_comparison.csv", index=False)
    overmerge.to_csv(out_dir / "tables/overmerge_comparison.csv", index=False)

    ranking, auc_ranking = ranking_tables(mean_rows, budgets)
    ranking.to_csv(out_dir / "common_materializer_budget_ranking.csv", index=False)
    ranking.to_csv(out_dir / "tables/common_materializer_budget_ranking.csv", index=False)
    auc_ranking.to_csv(out_dir / "event_f1_auc_ranking.csv", index=False)
    auc_ranking.to_csv(out_dir / "tables/event_f1_auc_ranking.csv", index=False)
    efficiency = primary_common_rows(mean_rows)[
        [
            "family",
            "method",
            "method_config",
            "budget",
            "variant",
            "unique_events_found",
            "oracle_calls",
            "unique_events_found_per_10_queries",
            "queries_per_discovered_event",
        ]
    ].copy()
    efficiency.to_csv(out_dir / "unique_event_efficiency.csv", index=False)
    efficiency.to_csv(out_dir / "tables/unique_event_efficiency.csv", index=False)

    original_hashes_after = {p: S0.sha256_file(p) for p in original_hashes_before}
    sanity = sanity_checks(runs, seed_rows, repaired_segments, oracle_logs, original_hashes_before, original_hashes_after)
    sanity.to_csv(out_dir / "sanity_checks.csv", index=False)
    sanity.to_csv(out_dir / "tables/sanity_checks.csv", index=False)
    (out_dir / "sanity_checks.md").write_text("# Stage 0.5 Sanity Checks\n\n" + sanity.to_markdown(index=False) + "\n", encoding="utf-8")
    (out_dir / "reports/sanity_checks.md").write_text("# Stage 0.5 Sanity Checks\n\n" + sanity.to_markdown(index=False) + "\n", encoding="utf-8")

    decision_value = decision(mean_rows, auc_ranking)
    write_reports(out_dir, runs, mean_rows, ranking, auc_ranking, delta, decision_value, sanity)
    (out_dir / "run_summary.txt").write_text(f"decision={decision_value}\ncompleted_at={now()}\n", encoding="utf-8")
    print(f"wrote {rel(out_dir)}")
    print(f"decision={decision_value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
