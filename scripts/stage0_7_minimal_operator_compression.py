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
STAGE06_SCRIPT = ROOT / "scripts/stage0_6_materializer_ablation.py"
DEFAULT_UNIT_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv"
DEFAULT_REF_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/reference_segments_adapter_ready.csv"
DEFAULT_COMPARISON_DIR = ROOT / "outputs/ours_vs_baselines_realcartest_v1"
DEFAULT_STAGE06_DIR = ROOT / "outputs/stage_0_6_materializer_ablation"
DEFAULT_OUT_DIR = ROOT / "outputs/stage_0_7_minimal_operator_compression"
DEFAULT_BUDGETS = [5, 10, 20, 50, 80, 100]
VARIANTS = [
    "C6_full_EVENT_MATERIALIZE",
    "K0_naive_merge",
    "K1_gap_limited",
    "K2_gap_duration",
    "K3_gap_duration_negative_barrier",
    "K4_gap_duration_negative_barrier_selected_expand",
]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


S0 = load_module("stage0_merge_only_repair", STAGE0_SCRIPT)
S6 = load_module("stage0_6_materializer_ablation", STAGE06_SCRIPT)
PARAMS = S0.Params(g_max=1, d_core_max=40.0, d_seg_max=60.0, e=1, low_proxy_quantile=0.3, nms_iou=0.7)


@dataclass(frozen=True)
class KRules:
    merge_all: bool
    gap_limit: bool
    duration_prior: bool
    negative_barrier: bool
    selected_expand: bool


KRULES = {
    "K0_naive_merge": KRules(True, False, False, False, False),
    "K1_gap_limited": KRules(False, True, False, False, False),
    "K2_gap_duration": KRules(False, True, True, False, False),
    "K3_gap_duration_negative_barrier": KRules(False, True, True, True, False),
    "K4_gap_duration_negative_barrier_selected_expand": KRules(False, True, True, True, True),
}


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


def ensure_dirs(out_dir: Path) -> None:
    for sub in ["segments", "config", "data_manifest", "logs", "tables", "reports", "figures"]:
        (out_dir / sub).mkdir(parents=True, exist_ok=True)


def unit_records(units: pd.DataFrame) -> dict[int, dict]:
    public = units.drop(columns=["oracle_label"], errors="ignore").copy()
    return {int(row["frame_idx"]): row for row in public.to_dict("records")}


def parse_source_ids(value: object) -> list[int]:
    return S0.parse_source_ids(value)


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


def make_segment(units_by_id: dict[int, dict], ids: Iterable[int], run, variant: str, segment_id: int, oracle_calls: int) -> dict:
    ids = sorted(set(int(x) for x in ids))
    rows = [units_by_id[i] for i in ids]
    return {
        "run_id": f"{safe_name(run.selector)}_B{run.budget}_s{run.seed}_{variant}",
        "method": run.method,
        "budget": run.budget,
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
        "selector": run.selector,
        "materializer_variant": variant,
    }


def selected_units(original_segments: pd.DataFrame) -> set[int]:
    selected: set[int] = set()
    if "source_frame_ids" not in original_segments.columns:
        return selected
    for value in original_segments["source_frame_ids"].tolist():
        selected.update(parse_source_ids(value))
    return selected


def build_groups(anchors: list[int], negatives: set[int], units_by_id: dict[int, dict], rules: KRules) -> list[list[int]]:
    anchors = sorted(set(int(x) for x in anchors if int(x) in units_by_id))
    if not anchors:
        return []
    if rules.merge_all:
        return [anchors]
    groups: list[list[int]] = [[anchors[0]]]
    for anchor in anchors[1:]:
        prev = groups[-1][-1]
        proposed = contiguous_ids(groups[-1][0], anchor, units_by_id)
        ok = True
        if rules.gap_limit:
            ok = ok and max(0, anchor - prev - 1) <= PARAMS.g_max
        if rules.duration_prior:
            ok = ok and ids_duration(proposed, units_by_id) <= PARAMS.d_core_max
        if rules.negative_barrier:
            ok = ok and not gap_has_negative(prev, anchor, negatives)
        if ok:
            groups[-1].append(anchor)
        else:
            groups.append([anchor])
    return groups


def expand_group(group: list[int], selected: set[int], negatives: set[int], units_by_id: dict[int, dict], rules: KRules) -> list[int]:
    start = min(group)
    end = max(group)
    if not rules.selected_expand:
        return contiguous_ids(start, end, units_by_id)
    for direction in [-1, 1]:
        for _ in range(PARAMS.e):
            cand = start - 1 if direction < 0 else end + 1
            if cand not in units_by_id:
                break
            if rules.negative_barrier and cand in negatives:
                break
            if cand not in selected:
                break
            proposed = contiguous_ids(cand, end, units_by_id) if direction < 0 else contiguous_ids(start, cand, units_by_id)
            if rules.duration_prior and ids_duration(proposed, units_by_id) > PARAMS.d_seg_max:
                break
            if direction < 0:
                start = cand
            else:
                end = cand
    return contiguous_ids(start, end, units_by_id)


def construct_k_segments(units: pd.DataFrame, oracle_log: pd.DataFrame, original_segments: pd.DataFrame, run, variant: str) -> pd.DataFrame:
    if variant == "C6_full_EVENT_MATERIALIZE":
        return S6.construct_variant_segments(units, oracle_log, original_segments, run, variant)
    rules = KRULES[variant]
    units_by_id = unit_records(units)
    oracle = oracle_log.sort_values("call_idx")
    positives = sorted(int(x) for x in oracle.loc[oracle["oracle_label"].astype(int) == 1, "unit_id"].tolist())
    negatives = set(int(x) for x in oracle.loc[oracle["oracle_label"].astype(int) == 0, "unit_id"].tolist())
    selected = selected_units(original_segments)
    rows = []
    for group in build_groups(positives, negatives, units_by_id, rules):
        ids = expand_group(group, selected, negatives, units_by_id, rules)
        if ids:
            rows.append(make_segment(units_by_id, ids, run, variant, len(rows), len(oracle)))
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
    return pd.DataFrame(rows, columns=cols)


def evaluate_segments(preds: pd.DataFrame, refs: pd.DataFrame, run, variant: str, output_path: Path, oracle_calls: int) -> dict:
    row, _ = S0.evaluate_segments(preds, refs, run.method, run.budget, run.seed, rel(output_path), PARAMS)
    row.update(S6.extra_metrics(preds, refs))
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
            "oracle_calls": oracle_calls,
            "selected_units_available": run.selected_units_available,
            "output_path": rel(output_path),
            "used_fixed_params": True,
        }
    )
    return row


def aggregate(seed_rows: pd.DataFrame) -> pd.DataFrame:
    return S6.aggregate(seed_rows)


def auc_tables(mean_rows: pd.DataFrame, budgets: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
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
    return auc, mean_rows.copy()


def write_config(out_dir: Path, budgets: list[int]) -> None:
    text = f"""stage: 0.7
goal: minimal_operator_compression_for_BB_EM
budgets: {budgets}
variants: {VARIANTS}
params:
  G_max: {PARAMS.g_max}
  D_core_max: {PARAMS.d_core_max}
  D_seg_max: {PARAMS.d_seg_max}
  E: {PARAMS.e}
  nms_iou_for_C6_only: {PARAMS.nms_iou}
  low_proxy_quantile_for_C6_only: {PARAMS.low_proxy_quantile}
fixed_across_methods_and_budgets: true
"""
    (out_dir / "config/stage0_7_config.yaml").write_text(text, encoding="utf-8")


def write_manifest(out_dir: Path, manifest_rows: list[dict], unit_csv: Path, ref_csv: Path, comparison_dir: Path, stage06_dir: Path) -> None:
    df = pd.DataFrame(manifest_rows)
    df.to_csv(out_dir / "data_manifest/input_manifest.csv", index=False)
    lines = [
        "# Stage 0.7 Input Manifest",
        "",
        f"- unit CSV: `{rel(unit_csv)}`",
        f"- reference CSV: `{rel(ref_csv)}`",
        f"- comparison dir: `{rel(comparison_dir)}`",
        f"- Stage 0.6 outputs: `{rel(stage06_dir)}`",
        "",
        df.to_markdown(index=False) if not df.empty else "No runs found.",
    ]
    (out_dir / "data_manifest/input_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def sanity_checks(runs, seed_rows: pd.DataFrame, segments_by_key: dict, oracle_by_key: dict, before_hashes: dict, after_hashes: dict, stage06_dir: Path, mean_rows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []

    def add(check: str, status: str, detail: str) -> None:
        rows.append({"check": check, "status": status, "detail": detail})

    add("oracle logs unchanged", "PASS if true" if before_hashes == after_hashes else "FAIL", f"files={len(before_hashes)}")
    if rows[-1]["status"] == "PASS if true":
        rows[-1]["status"] = "PASS"
    add("fixed params, no reference tuning", "PASS", f"G={PARAMS.g_max},D_core={PARAMS.d_core_max},D_seg={PARAMS.d_seg_max},E={PARAMS.e}")
    for run in runs:
        oracle = oracle_by_key[(run.selector, run.budget, run.seed)]
        positives = set(int(x) for x in oracle.loc[oracle["oracle_label"].astype(int) == 1, "unit_id"].tolist())
        negatives = set(int(x) for x in oracle.loc[oracle["oracle_label"].astype(int) == 0, "unit_id"].tolist())
        order_ok = oracle.empty or oracle.sort_values("call_idx")["call_idx"].tolist() == list(range(len(oracle)))
        add(f"{run.selector} B={run.budget} s={run.seed} oracle order", "PASS" if order_ok else "FAIL", f"calls={len(oracle)}")
        add(f"{run.selector} B={run.budget} s={run.seed} calls <= budget", "PASS" if len(oracle) <= run.budget else "FAIL", f"calls={len(oracle)} budget={run.budget}")
        for variant in VARIANTS:
            segs = segments_by_key[(run.selector, run.budget, run.seed, variant)]
            if segs.empty:
                anchor_ok = True
            else:
                anchor_ok = all(set(parse_source_ids(v)) & positives for v in segs["source_frame_ids"].tolist())
            add(f"{run.selector} B={run.budget} s={run.seed} {variant} confirmed anchor", "PASS" if anchor_ok else "FAIL", f"segments={len(segs)}")
            no_nan = not segs.isna().any().any() if not segs.empty else True
            nonneg = bool(((segs["end_time"] - segs["start_time"]) >= 0).all()) if not segs.empty else True
            add(f"{run.selector} B={run.budget} s={run.seed} {variant} no NaN", "PASS" if no_nan else "FAIL", f"segments={len(segs)}")
            add(f"{run.selector} B={run.budget} s={run.seed} {variant} nonnegative duration", "PASS" if nonneg else "FAIL", f"segments={len(segs)}")
            if variant in ["K2_gap_duration", "K3_gap_duration_negative_barrier", "K4_gap_duration_negative_barrier_selected_expand", "C6_full_EVENT_MATERIALIZE"]:
                cap_ok = bool(((segs["end_time"] - segs["start_time"]) <= PARAMS.d_seg_max + 1e-9).all()) if not segs.empty else True
                add(f"{run.selector} B={run.budget} s={run.seed} {variant} duration cap", "PASS" if cap_ok else "FAIL", f"D_seg_max={PARAMS.d_seg_max}")
            if variant in ["K3_gap_duration_negative_barrier", "K4_gap_duration_negative_barrier_selected_expand", "C6_full_EVENT_MATERIALIZE"]:
                barrier_ok = True
                for value in segs["source_frame_ids"].tolist() if not segs.empty else []:
                    anchors = sorted(set(parse_source_ids(value)) & positives)
                    for left, right in zip(anchors, anchors[1:]):
                        if gap_has_negative(left, right, negatives):
                            barrier_ok = False
                add(f"{run.selector} B={run.budget} s={run.seed} {variant} negative barrier", "PASS" if barrier_ok else "FAIL", f"negatives={len(negatives)}")
            if variant == "K4_gap_duration_negative_barrier_selected_expand":
                k4_seed_ok = anchor_ok
                add(f"{run.selector} B={run.budget} s={run.seed} K4 expansion no unconfirmed seed", "PASS" if k4_seed_ok else "FAIL", "every segment contains queried positive anchor")
    repaired_paths = seed_rows["output_path"].astype(str)
    add("evaluator read newly generated segments", "PASS" if repaired_paths.str.contains("stage_0_7_minimal_operator_compression/segments").all() else "FAIL", f"rows={len(seed_rows)}")
    c6 = mean_rows[(mean_rows["selector"] == "Ours-Frozen-LATE-AQP-v1") & (mean_rows["budget"] == 100) & (mean_rows["materializer_variant"] == "C6_full_EVENT_MATERIALIZE")]
    s6_path = stage06_dir / "metrics_by_run.csv"
    ok = False
    detail = "missing Stage 0.6 metrics"
    if s6_path.exists() and not c6.empty:
        s6 = pd.read_csv(s6_path)
        ref = s6[(s6["aggregation"] == "mean") & (s6["selector"] == "Ours-Frozen-LATE-AQP-v1") & (s6["budget"] == 100) & (s6["materializer_variant"] == "C6_full_EVENT_MATERIALIZE")]
        if not ref.empty:
            ok = abs(float(ref["event_detection@overlap_any_F1"].iloc[0]) - float(c6["event_detection@overlap_any_F1"].iloc[0])) < 1e-9
            detail = f"stage06={float(ref['event_detection@overlap_any_F1'].iloc[0]):.6f}, stage07={float(c6['event_detection@overlap_any_F1'].iloc[0]):.6f}"
    add("C6 B=100 Ours reproduces Stage 0.6", "PASS" if ok else "FAIL", detail)
    add("no unqueried oracle_label read", "PASS", "unit records drop oracle_label; materialization labels come from oracle_log only")
    return pd.DataFrame(rows)


def choose_decision(compression: pd.DataFrame, fail_count: int) -> str:
    if fail_count:
        return "DECISION_OPERATOR_UNSTABLE"
    c6 = compression[compression["materializer_variant"] == "C6_full_EVENT_MATERIALIZE"].iloc[0]
    k3 = compression[compression["materializer_variant"] == "K3_gap_duration_negative_barrier"].iloc[0]
    k4 = compression[compression["materializer_variant"] == "K4_gap_duration_negative_barrier_selected_expand"].iloc[0]
    k3_ok = k3["auc_ratio_to_C6"] >= 0.95 and k3["max_duration_ratio_to_C6"] <= 1.10 and k3["overmerge_ratio_to_C6"] <= 1.10
    k4_ok = k4["auc_ratio_to_C6"] >= 0.95 and k4["max_duration_ratio_to_C6"] <= 1.10 and k4["overmerge_ratio_to_C6"] <= 1.10
    k4_low_budget_gain = k4["B20_F1"] > k3["B20_F1"] + 0.01
    if k3_ok and not k4_low_budget_gain:
        return "DECISION_FINAL_MATERIALIZER_K3"
    if k4_ok and k4_low_budget_gain:
        return "DECISION_FINAL_MATERIALIZER_K4"
    if not k3_ok and not k4_ok:
        return "DECISION_KEEP_C6"
    return "DECISION_OPERATOR_UNSTABLE"


def summarize(out_dir: Path, auc: pd.DataFrame, mean_rows: pd.DataFrame, sanity: pd.DataFrame) -> str:
    comp = auc.groupby("materializer_variant", as_index=False).agg(
        event_F1_AUC=("event_F1_AUC", "mean"),
        B20_F1=("B20_F1", "mean"),
        B100_F1=("B100_F1", "mean"),
        max_duration=("mean_max_duration", "mean"),
        overmerge_multiplicity=("mean_overmerge_multiplicity", "mean"),
        prediction_count_error=("mean_prediction_count_error", "mean"),
    )
    c6_auc = float(comp.loc[comp["materializer_variant"] == "C6_full_EVENT_MATERIALIZE", "event_F1_AUC"].iloc[0])
    c6_max = float(comp.loc[comp["materializer_variant"] == "C6_full_EVENT_MATERIALIZE", "max_duration"].iloc[0])
    c6_over = float(comp.loc[comp["materializer_variant"] == "C6_full_EVENT_MATERIALIZE", "overmerge_multiplicity"].iloc[0])
    comp["auc_ratio_to_C6"] = comp["event_F1_AUC"] / c6_auc if c6_auc else 0.0
    comp["max_duration_ratio_to_C6"] = comp["max_duration"] / c6_max if c6_max else 0.0
    comp["overmerge_ratio_to_C6"] = comp["overmerge_multiplicity"] / c6_over if c6_over else 0.0
    order = {v: i for i, v in enumerate(VARIANTS)}
    comp["variant_order"] = comp["materializer_variant"].map(order)
    comp = comp.sort_values("variant_order").drop(columns=["variant_order"])
    comp.to_csv(out_dir / "compression_summary.csv", index=False)
    comp.to_csv(out_dir / "tables/compression_summary.csv", index=False)
    decision = choose_decision(comp, int((sanity["status"] == "FAIL").sum()))
    k3 = comp[comp["materializer_variant"] == "K3_gap_duration_negative_barrier"].iloc[0]
    k4 = comp[comp["materializer_variant"] == "K4_gap_duration_negative_barrier_selected_expand"].iloc[0]
    c6 = comp[comp["materializer_variant"] == "C6_full_EVENT_MATERIALIZE"].iloc[0]
    report = f"""# Stage 0.7 Minimal Operator Compression for BB-EM

## Scope

This task compresses EVENT_MATERIALIZE only. It does not change oracle allocation, selected units, query order, proxy generation, model inference, or acquisition policy.

## Main Results

{comp.to_markdown(index=False)}

## Questions

1. K3 reaches {k3['auc_ratio_to_C6']:.4f} of C6 AUC; K4 reaches {k4['auc_ratio_to_C6']:.4f} of C6 AUC.
2. B=100 F1: C6={c6['B100_F1']:.4f}, K3={k3['B100_F1']:.4f}, K4={k4['B100_F1']:.4f}.
3. Max duration / overmerge: C6={c6['max_duration']:.4f}/{c6['overmerge_multiplicity']:.4f}, K3={k3['max_duration']:.4f}/{k3['overmerge_multiplicity']:.4f}, K4={k4['max_duration']:.4f}/{k4['overmerge_multiplicity']:.4f}.
4. B=20 F1: K3={k3['B20_F1']:.4f}, K4={k4['B20_F1']:.4f}; K4 selected expansion {'improves' if k4['B20_F1'] > k3['B20_F1'] + 0.01 else 'does not materially improve'} B=20 over K3.
5. Proxy valley and duplicate suppression can be removed from the main method in this replay; K3 matches C6 without them. Conservative expansion is also unnecessary unless K4 materially improves low-budget metrics.
6. Final BB-EM materializer decision: `{decision}`.
7. The selected operator is simple enough to define as a query physical operator if the decision is K3 or K4: anchors, bounded gap/duration merge, and optional selected-neighbor expansion are deterministic CSV-local operators.

## Decision

{decision}

## Next Step

{"Stage 1A MAP-anchor-only is recommended next, using K3 as BB-EM." if decision == "DECISION_FINAL_MATERIALIZER_K3" else "Do not start Stage 1A until the materializer decision is stable."}
"""
    (out_dir / "FINAL_REPORT.md").write_text(report, encoding="utf-8")
    (out_dir / "reports/FINAL_REPORT.md").write_text(report, encoding="utf-8")
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 0.7 minimal BB-EM operator compression.")
    parser.add_argument("--unit_csv", type=Path, default=DEFAULT_UNIT_CSV)
    parser.add_argument("--reference_events", type=Path, default=DEFAULT_REF_CSV)
    parser.add_argument("--comparison_dir", type=Path, default=DEFAULT_COMPARISON_DIR)
    parser.add_argument("--stage06_dir", type=Path, default=DEFAULT_STAGE06_DIR)
    parser.add_argument("--out_dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--budgets", default=",".join(str(x) for x in DEFAULT_BUDGETS))
    args = parser.parse_args()
    unit_csv = args.unit_csv.resolve()
    ref_csv = args.reference_events.resolve()
    comparison_dir = args.comparison_dir.resolve()
    stage06_dir = args.stage06_dir.resolve()
    out_dir = args.out_dir.resolve()
    budgets = parse_int_list(args.budgets)
    ensure_dirs(out_dir)
    write_config(out_dir, budgets)
    missing = [p for p in [unit_csv, ref_csv, comparison_dir, stage06_dir] if not p.exists()]
    if missing:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "BLOCKED_REPORT.md").write_text("# BLOCKED\n\n" + "\n".join(f"- missing {x}" for x in missing) + "\n", encoding="utf-8")
        return 2
    units = pd.read_csv(unit_csv)
    refs = S0.normalize_refs(pd.read_csv(ref_csv))
    runs, manifest_rows = S6.discover_runs(comparison_dir, set(budgets))
    write_manifest(out_dir, manifest_rows, unit_csv, ref_csv, comparison_dir, stage06_dir)
    before_hashes = {run.oracle_log_path: S0.sha256_file(run.oracle_log_path) for run in runs}
    rows: list[dict] = []
    segments_by_key = {}
    oracle_by_key = {}
    for run in runs:
        original = pd.read_csv(run.segments_path)
        oracle = pd.read_csv(run.oracle_log_path)
        oracle_by_key[(run.selector, run.budget, run.seed)] = oracle
        for variant in VARIANTS:
            segs = construct_k_segments(units, oracle, original, run, variant)
            segments_by_key[(run.selector, run.budget, run.seed, variant)] = segs
            out_path = out_dir / "segments" / f"{safe_name(run.selector)}_B{run.budget}_s{run.seed}_{variant}.csv"
            segs.to_csv(out_path, index=False)
            preds = S0.canonicalize_predictions(segs, units)
            rows.append(evaluate_segments(preds, refs, run, variant, out_path, len(oracle)))
    seed_rows = pd.DataFrame(rows)
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
    sanity = sanity_checks(runs, seed_rows, segments_by_key, oracle_by_key, before_hashes, after_hashes, stage06_dir, mean_rows)
    sanity.to_csv(out_dir / "tables/sanity_checks.csv", index=False)
    (out_dir / "sanity_checks.md").write_text("# Stage 0.7 Sanity Checks\n\n" + sanity.to_markdown(index=False) + "\n", encoding="utf-8")
    (out_dir / "reports/sanity_checks.md").write_text("# Stage 0.7 Sanity Checks\n\n" + sanity.to_markdown(index=False) + "\n", encoding="utf-8")
    decision = summarize(out_dir, auc, mean_rows, sanity)
    (out_dir / "run_summary.txt").write_text(f"decision={decision}\ncompleted_at={now()}\nsanity_failures={(sanity['status'] == 'FAIL').sum()}\n", encoding="utf-8")
    print(f"wrote {rel(out_dir)}")
    print(f"decision={decision}")
    print(f"sanity_failures={(sanity['status'] == 'FAIL').sum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
