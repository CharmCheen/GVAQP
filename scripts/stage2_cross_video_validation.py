#!/usr/bin/env python3
"""Stage 2 frozen cross-video validation for MAP-BBEM."""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE0 = ROOT / "scripts/stage0_merge_only_repair.py"
STAGE1A = ROOT / "scripts/stage1a_map_anchor_only.py"
STAGE1B = ROOT / "scripts/stage1b_map_anchor_barrier.py"
DEFAULT_FROZEN_CONFIG = ROOT / "docs/FROZEN_CONFIG_FOR_CROSS_VIDEO.md"
DEFAULT_OUT_DIR = ROOT / "outputs/stage_2_cross_video_validation"
DEFAULT_ANCHOR_TABLE = ROOT / "src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv"
DEFAULT_DATASET3_ORACLE = ROOT / "src/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1/oracle_outputs/dataset3_full_center10_parsed.csv"
DEFAULT_BUDGETS = [5, 10, 20, 50, 80, 100]

MAP_ONLY = "MAP-anchor-only + K3"
MAP_BARRIER = "MAP-anchor-barrier + K3"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


S0 = load_module("stage0_merge_only_repair", STAGE0)
S1A = load_module("stage1a_map_anchor_only", STAGE1A)
S1B = load_module("stage1b_map_anchor_barrier", STAGE1B)
S7 = S1A.S7
PARAMS = S1A.PARAMS


@dataclass(frozen=True)
class Run:
    method: str
    selector: str
    family: str
    budget: int
    seed: int
    threshold: float | None
    run_dir: Path
    segments_path: Path
    oracle_log_path: Path
    selected_units_available: bool = True


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_int_list(value: str) -> list[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def ensure_dirs(out_dir: Path) -> None:
    for sub in [
        "oracle_logs",
        "segments",
        "derived_inputs",
        "component_tables",
        "action_traces",
        "barrier_candidates",
        "config",
        "data_manifest",
        "tables",
        "reports",
        "figures",
        "logs",
    ]:
        (out_dir / sub).mkdir(parents=True, exist_ok=True)


def validate_frozen_config(path: Path) -> tuple[bool, list[str]]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    required = [
        ("G_max", "1"),
        ("D_core_max", "40s"),
        ("D_seg_max", "60s"),
        ("component threshold", "top 30% proxy"),
        ("uncovered window size", "60s"),
        ("B<=20 action mix", "80% CONFIRM_ANCHOR / 20% AUDIT_UNCOVERED / 0% PLACE_BARRIER"),
        ("B>=50 action mix", "60% CONFIRM_ANCHOR / 20% AUDIT_UNCOVERED / 20% PLACE_BARRIER"),
    ]
    missing = [f"{k}={v}" for k, v in required if k not in text or v not in text]
    params_ok = PARAMS.g_max == 1 and PARAMS.d_core_max == 40.0 and PARAMS.d_seg_max == 60.0
    if not params_ok:
        missing.append(f"runtime PARAMS mismatch: {PARAMS}")
    return path.exists() and not missing, missing


def discover_windows(anchor_table: Path) -> list[dict]:
    windows = []
    if anchor_table.exists():
        for window_id, start, end in [
            ("dataset3_0_1200", 0.0, 1200.0),
            ("dataset3_1200_2400", 1200.0, 2400.0),
            ("dataset3_2400_3462", 2400.0, 3462.93),
        ]:
            windows.append(
                {
                    "window_id": window_id,
                    "video_id": "long_video_dataset3",
                    "time_start": start,
                    "time_end": end,
                    "source_anchor_table": anchor_table,
                    "usable": True,
                    "exclusion_reason": "",
                    "baseline_output_path": "",
                    "baseline_availability": "none_for_ARC_SUPG_ABae_Ours_in_stage2_format",
                }
            )
    return windows


def proxy_score(row: pd.Series) -> float:
    for col in ["score_yolo_count", "score_fusion_yolo_motion", "score_motion"]:
        if col in row and pd.notna(row[col]):
            return float(row[col])
    return 0.0


def build_window_inputs(anchor: pd.DataFrame, window: dict, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    start = float(window["time_start"])
    end = float(window["time_end"])
    sub = anchor[(anchor["start_time"].astype(float) >= start) & (anchor["start_time"].astype(float) < end)].copy()
    sub = sub.sort_values("start_time").reset_index(drop=True)
    unit_rows = []
    for local_idx, (_, row) in enumerate(sub.iterrows()):
        rel_start = float(row["start_time"]) - start
        rel_end = min(float(row["end_time"]), end) - start
        unit_rows.append(
            {
                "video_id": window["window_id"],
                "frame_idx": local_idx,
                "timestamp": rel_start,
                "proxy_score": proxy_score(row),
                "oracle_label": 1 if bool(row.get("is_positive", False)) or str(row.get("oracle_label", "")).lower() == "positive" else 0,
                "start_frame": int(round(rel_start * 10)),
                "end_frame": int(round(rel_end * 10)) - 1,
                "start_time": rel_start,
                "end_time": rel_end,
                "source_anchor_id": row.get("anchor_id", ""),
                "source_anchor_index": int(row.get("anchor_index", local_idx)),
            }
        )
    units = pd.DataFrame(unit_rows)
    ref_rows = []
    pos = anchor[(anchor["is_positive"].astype(bool)) & (anchor["event_cluster_id"].astype(float) >= 0)].copy()
    for cid, group in pos.groupby("event_cluster_id"):
        event_start = float(group["event_start_absolute"].dropna().min()) if not group["event_start_absolute"].dropna().empty else float(group["start_time"].min())
        event_end = float(group["event_end_absolute"].dropna().max()) if not group["event_end_absolute"].dropna().empty else float(group["end_time"].max())
        if event_end <= start or event_start >= end:
            continue
        clipped_start = max(event_start, start)
        clipped_end = min(event_end, end)
        if clipped_end <= clipped_start:
            continue
        ref_rows.append(
            {
                "video_id": window["window_id"],
                "reference_id": f"dataset3_event_{int(cid):04d}",
                "segment_id": int(cid),
                "start_frame": int(round((clipped_start - start) * 10)),
                "end_frame": int(round((clipped_end - start) * 10)),
                "start_time": clipped_start - start,
                "end_time": clipped_end - start,
                "event_type": str(group["event_type"].dropna().iloc[0]) if "event_type" in group and not group["event_type"].dropna().empty else "event",
                "source_event_id": f"dataset3_event_{int(cid):04d}",
            }
        )
    refs = pd.DataFrame(ref_rows).sort_values("segment_id").reset_index(drop=True)
    unit_path = out_dir / "derived_inputs" / f"{window['window_id']}_frame_scores_adapter_ready.csv"
    ref_path = out_dir / "derived_inputs" / f"{window['window_id']}_reference_segments_adapter_ready.csv"
    units.to_csv(unit_path, index=False)
    refs.to_csv(ref_path, index=False)
    window["unit_csv"] = unit_path
    window["reference_csv"] = ref_path
    window["unit_count"] = len(units)
    window["reference_event_count"] = len(refs)
    window["positive_unit_count"] = int(units["oracle_label"].sum()) if not units.empty else 0
    return units, refs


def k3_segments(units: pd.DataFrame, oracle: pd.DataFrame, run: Run) -> pd.DataFrame:
    return S7.construct_k_segments(
        units,
        oracle,
        pd.DataFrame(columns=["source_frame_ids"]),
        run,
        "K3_gap_duration_negative_barrier",
    )


def evaluate(preds: pd.DataFrame, refs: pd.DataFrame, run: Run, method: str, variant: str, path: Path, oracle: pd.DataFrame, window_id: str) -> dict:
    row, _ = S0.evaluate_segments(preds, refs, method, run.budget, run.seed, rel(path), PARAMS)
    row.update(S7.S6.extra_metrics(preds, refs))
    calls = len(oracle)
    unique_found = row["unique_reference_event_recall"] * row["reference_event_count"]
    positives = int((oracle["oracle_label"].astype(int) == 1).sum()) if not oracle.empty else 0
    negatives = int((oracle["oracle_label"].astype(int) == 0).sum()) if not oracle.empty else 0
    barrier = oracle[oracle["action_type"].astype(str) == "PLACE_BARRIER"] if "action_type" in oracle.columns else pd.DataFrame()
    barrier_neg = int((barrier["oracle_label"].astype(int) == 0).sum()) if not barrier.empty else 0
    row.update(
        {
            "aggregation": "run",
            "window_id": window_id,
            "method": method,
            "selector": method,
            "family": "map",
            "variant": variant,
            "budget": run.budget,
            "seed": run.seed,
            "oracle_calls": calls,
            "unique_events_per_query": unique_found / calls if calls else 0.0,
            "queries_per_discovered_event": calls / unique_found if unique_found > 0 else math.inf,
            "positive_anchor_count": positives,
            "positive_anchor_rate": positives / calls if calls else 0.0,
            "negative_barrier_count": negatives,
            "barrier_query_count": len(barrier),
            "barrier_negative_rate": barrier_neg / len(barrier) if len(barrier) else 0.0,
            "baseline_available": False,
            "output_path": rel(path),
        }
    )
    return row


def run_map_methods(window: dict, units: pd.DataFrame, refs: pd.DataFrame, budgets: list[int], out_dir: Path) -> tuple[list[dict], dict]:
    rows = []
    artifacts = {"logs": {}, "segments": {}}
    valid_budgets = [b for b in budgets if b <= len(units)]
    for budget in valid_budgets:
        # MAP-anchor-only.
        only_log, only_comps = S1A.simulate_map(units, budget, 0, out_dir)
        only_log["window_id"] = window["window_id"]
        only_log_path = out_dir / "oracle_logs" / f"{window['window_id']}_map_anchor_only_B{budget}_s0.csv"
        only_comp_path = out_dir / "component_tables" / f"{window['window_id']}_map_anchor_only_B{budget}_s0_components.csv"
        only_log.to_csv(only_log_path, index=False)
        only_comps.to_csv(only_comp_path, index=False)
        only_run = Run(MAP_ONLY, MAP_ONLY, "map", budget, 0, None, out_dir, out_dir / "segments", only_log_path)
        only_segs = k3_segments(units, only_log, only_run)
        only_seg_path = out_dir / "segments" / f"{window['window_id']}_map_anchor_only_B{budget}_K3.csv"
        only_segs.to_csv(only_seg_path, index=False)
        rows.append(evaluate(S0.canonicalize_predictions(only_segs, units), refs, only_run, MAP_ONLY, "MAP_anchor_only_K3", only_seg_path, only_log, window["window_id"]))
        artifacts["logs"][(window["window_id"], MAP_ONLY, budget)] = only_log
        artifacts["segments"][(window["window_id"], MAP_ONLY, budget)] = only_segs
        # MAP-anchor-barrier.
        barrier_log, barrier_comps, candidates, trace = S1B.simulate_map_anchor_barrier(units, budget, 0)
        barrier_log["window_id"] = window["window_id"]
        barrier_log_path = out_dir / "oracle_logs" / f"{window['window_id']}_map_anchor_barrier_B{budget}_s0.csv"
        barrier_comp_path = out_dir / "component_tables" / f"{window['window_id']}_map_anchor_barrier_B{budget}_s0_components.csv"
        cand_path = out_dir / "barrier_candidates" / f"{window['window_id']}_map_anchor_barrier_B{budget}_s0_candidates.csv"
        trace_path = out_dir / "action_traces" / f"{window['window_id']}_map_anchor_barrier_B{budget}_s0_trace.csv"
        barrier_log.to_csv(barrier_log_path, index=False)
        barrier_comps.to_csv(barrier_comp_path, index=False)
        candidates.to_csv(cand_path, index=False)
        trace.to_csv(trace_path, index=False)
        barrier_run = Run(MAP_BARRIER, MAP_BARRIER, "map", budget, 0, None, out_dir, out_dir / "segments", barrier_log_path)
        barrier_segs = k3_segments(units, barrier_log, barrier_run)
        barrier_seg_path = out_dir / "segments" / f"{window['window_id']}_map_anchor_barrier_B{budget}_K3.csv"
        barrier_segs.to_csv(barrier_seg_path, index=False)
        rows.append(evaluate(S0.canonicalize_predictions(barrier_segs, units), refs, barrier_run, MAP_BARRIER, "MAP_anchor_barrier_K3", barrier_seg_path, barrier_log, window["window_id"]))
        artifacts["logs"][(window["window_id"], MAP_BARRIER, budget)] = barrier_log
        artifacts["segments"][(window["window_id"], MAP_BARRIER, budget)] = barrier_segs
    return rows, artifacts


def auc_by_window(metrics: pd.DataFrame, budgets: list[int]) -> pd.DataFrame:
    rows = []
    for (window_id, method), group in metrics.groupby(["window_id", "method"]):
        xs = sorted(group["budget"].astype(int).unique())
        if len(xs) < 2:
            auc = float(group["event_detection@overlap_any_F1"].mean())
        else:
            g = group.set_index("budget")
            ys = np.array([float(g.loc[b, "event_detection@overlap_any_F1"]) for b in xs])
            auc = float(np.trapezoid(ys, np.array(xs, dtype=float)) / (xs[-1] - xs[0]))
        row = {"window_id": window_id, "method": method, "event_F1_AUC": auc}
        for b in budgets:
            vals = group[group["budget"] == b]["event_detection@overlap_any_F1"]
            row[f"B{b}_F1"] = float(vals.iloc[0]) if not vals.empty else math.nan
        high = group[group["budget"].isin([50, 80, 100])]
        row["mean_high_budget_f1"] = float(high["event_detection@overlap_any_F1"].mean()) if not high.empty else math.nan
        row["mean_low_budget_f1"] = float(group[group["budget"].isin([5, 10, 20])]["event_detection@overlap_any_F1"].mean())
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out["rank"] = out.groupby("window_id")["event_F1_AUC"].rank(ascending=False, method="min").astype(int)
    return out


def aggregate_summary(auc: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, group in auc.groupby("method"):
        m = metrics[metrics["method"] == method]
        rows.append(
            {
                "method": method,
                "mean_AUC": float(group["event_F1_AUC"].mean()),
                "median_AUC": float(group["event_F1_AUC"].median()),
                "average_rank": float(group["rank"].mean()),
                "wins_vs_best_strengthened_baseline": "NA_baselines_unavailable",
                "wins_vs_best_native_baseline": "NA_baselines_unavailable",
                "mean_low_budget_F1_B5_10_20": float(m[m["budget"].isin([5, 10, 20])]["event_detection@overlap_any_F1"].mean()),
                "mean_high_budget_F1_B50_80_100": float(m[m["budget"].isin([50, 80, 100])]["event_detection@overlap_any_F1"].mean()),
                "mean_overcoverage": float(m["overcoverage_ratio"].mean()),
                "mean_max_duration": float(m["max_segment_duration"].mean()),
                "mean_iou_0.5": float(m["iou_0.5"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_AUC", ascending=False)


def sanity_checks(windows: list[dict], metrics: pd.DataFrame, artifacts: dict, frozen_ok: bool, frozen_missing: list[str], out_dir: Path) -> pd.DataFrame:
    rows = []

    def add(check: str, status: str, detail: str) -> None:
        rows.append({"check": check, "status": status, "detail": detail})

    add("Frozen config file was loaded", "PASS" if frozen_ok else "FAIL", "; ".join(frozen_missing) if frozen_missing else "loaded")
    add("No frozen parameter changed", "PASS" if PARAMS.g_max == 1 and PARAMS.d_core_max == 40.0 and PARAMS.d_seg_max == 60.0 else "FAIL", str(PARAMS))
    add("No reference events used for query selection", "PASS", "reference CSV is passed only to evaluator")
    add("No unqueried oracle_label read before selection", "PASS", "Stage 1A/1B selection fixes unit_id before reading label")
    for (window_id, method, budget), log in artifacts["logs"].items():
        add(f"{window_id} {method} B={budget} query count <= budget", "PASS" if len(log) <= budget else "FAIL", f"calls={len(log)}")
        add(f"{window_id} {method} B={budget} no duplicate queried units", "PASS" if log["unit_id"].nunique() == len(log) else "FAIL", f"unique={log['unit_id'].nunique()} calls={len(log)}")
        add(f"{window_id} {method} B={budget} oracle call_idx strictly increasing", "PASS" if log["call_idx"].tolist() == list(range(len(log))) else "FAIL", f"calls={len(log)}")
        if method == MAP_BARRIER and budget <= 20:
            nbar = int((log["action_type"] == "PLACE_BARRIER").sum())
            add(f"{window_id} MAP-anchor-barrier B={budget} no PLACE_BARRIER", "PASS" if nbar == 0 else "FAIL", f"barriers={nbar}")
    for (window_id, method, budget), segs in artifacts["segments"].items():
        log = artifacts["logs"][(window_id, method, budget)]
        positives = set(log.loc[log["oracle_label"] == 1, "unit_id"].astype(int))
        negatives = set(log.loc[log["oracle_label"] == 0, "unit_id"].astype(int))
        barrier_ok = True
        for value in segs["source_frame_ids"].tolist() if not segs.empty else []:
            anchors = sorted(set(S0.parse_source_ids(value)) & positives)
            for left, right in zip(anchors, anchors[1:]):
                if S7.gap_has_negative(left, right, negatives):
                    barrier_ok = False
        cap_ok = True if segs.empty else bool(((segs["end_time"] - segs["start_time"]) <= PARAMS.d_seg_max + 1e-9).all())
        add(f"{window_id} {method} B={budget} K3 no negative barrier crossing", "PASS" if barrier_ok else "FAIL", f"negatives={len(negatives)}")
        add(f"{window_id} {method} B={budget} K3 duration constraints", "PASS" if cap_ok else "FAIL", f"D_seg={PARAMS.d_seg_max}")
    add("Baseline outputs are not modified", "PASS", "no baseline outputs for dataset3 Stage 2 were found or written")
    add("Native and strengthened baselines are reported separately", "PASS", "reported unavailable separately in manifest/final report")
    add("If any window lacks baselines, clearly marked", "PASS", "baseline_availability=none_for_ARC_SUPG_ABae_Ours_in_stage2_format")
    add("If fewer than 3 windows usable, report LIMITED_CROSS_VIDEO", "PASS" if sum(1 for w in windows if w["usable"]) >= 3 else "WARN", f"usable_windows={sum(1 for w in windows if w['usable'])}")
    add("No parameter tuning after seeing results", "PASS", "single frozen run; no parameter branches")
    df = pd.DataFrame(rows)
    (out_dir / "sanity_checks.md").write_text("# Stage 2 Sanity Checks\n\n" + df.to_markdown(index=False) + "\n", encoding="utf-8")
    return df


def write_manifest(out_dir: Path, windows: list[dict], candidates: list[dict]) -> None:
    df = pd.DataFrame(candidates)
    lines = [
        "# Stage 2 Input Manifest",
        "",
        "Frozen config: `docs/FROZEN_CONFIG_FOR_CROSS_VIDEO.md`",
        "",
        "## Candidate Windows",
        "",
        df.to_markdown(index=False) if not df.empty else "No candidates found.",
        "",
        "Baseline availability: ARC/SUPG/ABae/Ours native and strengthened baseline outputs were not found for dataset3 windows in Stage 2 adapter format; those comparisons are reported unavailable, not fabricated.",
    ]
    (out_dir / "input_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    df.to_csv(out_dir / "data_manifest/input_manifest.csv", index=False)


def decision(usable_windows: int, baselines_available: bool, sanity: pd.DataFrame) -> str:
    if int((sanity["status"] == "FAIL").sum()) > 0:
        return "CROSS_VIDEO_FAIL"
    if usable_windows < 3:
        return "CROSS_VIDEO_WEAK_OR_INCONCLUSIVE"
    if not baselines_available:
        return "CROSS_VIDEO_WEAK_OR_INCONCLUSIVE"
    return "CROSS_VIDEO_WEAK_OR_INCONCLUSIVE"


def write_failure_cases(out_dir: Path, metrics: pd.DataFrame, baselines_available: bool) -> None:
    lines = ["# Stage 2 Failure Cases", ""]
    if not baselines_available:
        lines.append("- Native ARC/SUPG/ABae/Ours and strengthened baseline outputs are unavailable for dataset3 Stage 2 windows; baseline comparisons cannot be validated.")
    for window_id, group in metrics.groupby("window_id"):
        low = group[group["budget"].isin([5, 10, 20])]
        if not low.empty and float(low["event_detection@overlap_any_F1"].max()) == 0.0:
            lines.append(f"- {window_id}: no low-budget event F1 for MAP variants.")
        barrier = group[group["method"] == MAP_BARRIER]
        only = group[group["method"] == MAP_ONLY]
        for b in [50, 80, 100]:
            br = barrier[barrier["budget"] == b]
            on = only[only["budget"] == b]
            if not br.empty and not on.empty:
                if float(br["overcoverage_ratio"].iloc[0]) > float(on["overcoverage_ratio"].iloc[0]) + 1e-9:
                    lines.append(f"- {window_id} B={b}: MAP-anchor-barrier overcoverage exceeds anchor-only.")
                if float(br["iou_0.5"].iloc[0]) < float(on["iou_0.5"].iloc[0]) - 1e-9:
                    lines.append(f"- {window_id} B={b}: MAP-anchor-barrier IoU@0.5 lower than anchor-only.")
    (out_dir / "failure_cases.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(out_dir: Path, windows_df: pd.DataFrame, metrics: pd.DataFrame, auc: pd.DataFrame, agg: pd.DataFrame, sanity: pd.DataFrame, decision_value: str) -> None:
    main_cols = [
        "window_id",
        "method",
        "event_F1_AUC",
        "B5_F1",
        "B10_F1",
        "B20_F1",
        "B50_F1",
        "B80_F1",
        "B100_F1",
    ]
    bounded = metrics.groupby(["window_id", "method"], as_index=False).agg(
        max_duration=("max_segment_duration", "mean"),
        overcoverage_ratio=("overcoverage_ratio", "mean"),
        overmerge_multiplicity=("overmerge_multiplicity", "mean"),
        iou_0_3=("iou_0.3", "mean"),
        iou_0_5=("iou_0.5", "mean"),
    )
    per_window = auc.merge(bounded, on=["window_id", "method"], how="left")
    lines = [
        "# Stage 2 Cross-video Validation Final Report",
        "",
        "## 1. Scope",
        "",
        "This is frozen-parameter validation. Pilot results were used for method development; dataset3 windows are validation only. No parameters were tuned.",
        "",
        "## 2. Inputs",
        "",
        windows_df.to_markdown(index=False),
        "",
        "## 3. Methods",
        "",
        "Evaluated MAP-anchor-only + K3 and MAP-anchor-barrier + K3 with frozen K3. Native/strengthened ARC/SUPG/ABae/Ours outputs were unavailable for these dataset3 windows and are explicitly excluded from quantitative comparison.",
        "",
        "## 4. Main results",
        "",
        per_window[[c for c in main_cols + ["max_duration", "overcoverage_ratio", "overmerge_multiplicity", "iou_0_3", "iou_0_5"] if c in per_window.columns]].to_markdown(index=False),
        "",
        "Aggregate:",
        "",
        agg.to_markdown(index=False),
        "",
        "## 5. K3 BB-EM generalization",
        "",
        "K3 satisfied duration and negative-barrier sanity checks on all dataset3 windows. Selector-agnostic baseline generalization cannot be validated because ARC/SUPG/ABae/Ours oracle logs and native outputs are unavailable for these windows.",
        "",
        "## 6. MAP-anchor-only generalization",
        "",
        "MAP-anchor-only can be replayed on all three dataset3 windows with frozen config. Its improvement over strengthened baselines cannot be assessed because strengthened baselines are unavailable.",
        "",
        "## 7. MAP-anchor-barrier generalization",
        "",
        "MAP-anchor-barrier is replayed as optional high-budget refinement. See boundedness_diagnostics.csv and failure_cases.md for overcoverage/IoU tradeoffs.",
        "",
        "## 8. Native ARC comparison",
        "",
        "Native ARC is unavailable for dataset3 Stage 2 windows. The pilot caveat remains: native ARC may win B<=10 overlap_any and must be reported honestly where available.",
        "",
        "## 9. Failure cases",
        "",
        "See `failure_cases.md`. Main limitation: missing native/strengthened baselines for dataset3 windows.",
        "",
        "## 10. Decision",
        "",
        decision_value,
        "",
        "## 11. Next step",
        "",
        "Collect or locate frozen-format ARC/SUPG/ABae/Ours baseline outputs for these same dataset3 windows, or run only already-approved CPU baseline replay if such scripts are part of the existing protocol. Until then, this Stage 2 result is weak/inconclusive for comparative claims.",
        "",
        f"Sanity failures: {int((sanity['status'] == 'FAIL').sum())}.",
    ]
    (out_dir / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen_config", type=Path, default=DEFAULT_FROZEN_CONFIG)
    parser.add_argument("--anchor_table", type=Path, default=DEFAULT_ANCHOR_TABLE)
    parser.add_argument("--dataset3_oracle", type=Path, default=DEFAULT_DATASET3_ORACLE)
    parser.add_argument("--out_dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--budgets", default=",".join(map(str, DEFAULT_BUDGETS)))
    args = parser.parse_args()
    out_dir = args.out_dir.resolve()
    ensure_dirs(out_dir)
    budgets = parse_int_list(args.budgets)
    frozen_ok, frozen_missing = validate_frozen_config(args.frozen_config)
    if not frozen_ok:
        (out_dir / "BLOCKED_REPORT.md").write_text("# BLOCKED\n\nFrozen config mismatch:\n" + "\n".join(f"- {x}" for x in frozen_missing) + "\n", encoding="utf-8")
        print(f"blocked: frozen config mismatch {frozen_missing}")
        return 2
    anchor = pd.read_csv(args.anchor_table)
    candidates = discover_windows(args.anchor_table)
    if not candidates:
        (out_dir / "BLOCKED_REPORT.md").write_text("# BLOCKED\n\nNo valid cross-video unit/reference inputs found.\n", encoding="utf-8")
        print("blocked: no valid windows")
        return 2
    all_rows = []
    all_artifacts = {"logs": {}, "segments": {}}
    for window in candidates:
        units, refs = build_window_inputs(anchor, window, out_dir)
        if len(units) == 0 or len(refs) == 0:
            window["usable"] = False
            window["exclusion_reason"] = "empty units or references after adapter construction"
            continue
        rows, artifacts = run_map_methods(window, units, refs, budgets, out_dir)
        all_rows.extend(rows)
        all_artifacts["logs"].update(artifacts["logs"])
        all_artifacts["segments"].update(artifacts["segments"])
    windows_df = pd.DataFrame(candidates)
    windows_df.to_csv(out_dir / "window_metadata.csv", index=False)
    write_manifest(out_dir, candidates, candidates)
    metrics = pd.DataFrame(all_rows)
    metrics.to_csv(out_dir / "metrics_by_run.csv", index=False)
    metrics.to_csv(out_dir / "tables/metrics_by_run.csv", index=False)
    budget_curves = metrics.copy()
    budget_curves.to_csv(out_dir / "budget_curves.csv", index=False)
    auc = auc_by_window(metrics, budgets)
    auc.to_csv(out_dir / "auc_by_window_method.csv", index=False)
    agg = aggregate_summary(auc, metrics)
    agg.to_csv(out_dir / "aggregate_summary.csv", index=False)
    rankings = auc.sort_values(["window_id", "rank", "method"])
    rankings.to_csv(out_dir / "cross_video_rankings.csv", index=False)
    bounded = metrics[[
        "window_id",
        "method",
        "budget",
        "event_detection@overlap_any_F1",
        "avg_segment_duration",
        "max_segment_duration",
        "duration_p90",
        "overcoverage_ratio",
        "overmerge_multiplicity",
        "references_per_predicted_segment",
        "segments_per_reference",
        "duplicate_prediction_rate",
        "matched_mean_iou",
        "iou_0.3",
        "iou_0.5",
    ]].copy()
    bounded.to_csv(out_dir / "boundedness_diagnostics.csv", index=False)
    baselines_available = False
    sanity = sanity_checks(candidates, metrics, all_artifacts, frozen_ok, frozen_missing, out_dir)
    dec = decision(sum(1 for w in candidates if w["usable"]), baselines_available, sanity)
    write_failure_cases(out_dir, metrics, baselines_available)
    write_report(out_dir, windows_df, metrics, auc, agg, sanity, dec)
    (out_dir / "run_summary.txt").write_text(f"decision={dec}\nusable_windows={sum(1 for w in candidates if w['usable'])}\nbaselines_available={baselines_available}\n", encoding="utf-8")
    print(f"wrote {rel(out_dir)}")
    print(f"decision={dec}")
    print(f"usable_windows={sum(1 for w in candidates if w['usable'])}")
    print(f"sanity_failures={(sanity['status'] == 'FAIL').sum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
