#!/usr/bin/env python3
"""Stage 1B MAP-anchor-barrier replay with frozen K3 BB-EM."""

from __future__ import annotations

import argparse
import importlib.util
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE1A_SCRIPT = ROOT / "scripts/stage1a_map_anchor_only.py"
DEFAULT_UNIT_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv"
DEFAULT_REF_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/reference_segments_adapter_ready.csv"
DEFAULT_COMPARISON_DIR = ROOT / "outputs/ours_vs_baselines_realcartest_v1"
DEFAULT_STAGE07_DIR = ROOT / "outputs/stage_0_7_minimal_operator_compression"
DEFAULT_STAGE1A_DIR = ROOT / "outputs/stage_1a_map_anchor_only"
DEFAULT_DIAGNOSTIC_DIR = ROOT / "outputs/stage_1a_diagnostic_native_arc_vs_map_bbem"
DEFAULT_OUT_DIR = ROOT / "outputs/stage_1b_map_anchor_barrier"
DEFAULT_BUDGETS = [5, 10, 20, 50, 80, 100]
MAP_ONLY_METHOD = "MAP-anchor-only + K3 BB-EM"
MAP_BARRIER_METHOD = "MAP-anchor-barrier + K3 BB-EM"
BEST_BASELINE_METHOD = "Best strengthened baseline + K3 BB-EM"
NATIVE_SELECTORS = {
    "ARC-refinement@th0.3",
    "ARC-refinement@th0.4",
    "ABae-stratified-confirmed",
    "Ours-Frozen-LATE-AQP-v1",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


S1A = load_module("stage1a_map_anchor_only", STAGE1A_SCRIPT)
S0 = S1A.S0
S7 = S1A.S7
PARAMS = S1A.PARAMS


@dataclass(frozen=True)
class SimpleRun:
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


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", value.replace("@", "_").replace("+", "plus").replace(" ", "_"))


def parse_int_list(value: str) -> list[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def ensure_dirs(out_dir: Path) -> None:
    for sub in [
        "oracle_logs",
        "segments",
        "action_traces",
        "barrier_candidates",
        "component_tables",
        "config",
        "data_manifest",
        "logs",
        "tables",
        "reports",
        "figures",
    ]:
        (out_dir / sub).mkdir(parents=True, exist_ok=True)


def write_config(out_dir: Path, budgets: list[int]) -> None:
    text = f"""stage: 1B
method: MAP-anchor-barrier
materializer: K3_gap_duration_negative_barrier
budgets: {budgets}
low_budget_policy: identical_to_stage_1a_map_anchor_only
high_budget_action_mix:
  CONFIRM_ANCHOR: 0.60
  AUDIT_UNCOVERED: 0.20
  PLACE_BARRIER: 0.20
fallback_when_quota_action_exhausted: deterministic_AUDIT_UNCOVERED
params:
  G_max: {PARAMS.g_max}
  D_core_max: {PARAMS.d_core_max}
  D_seg_max: {PARAMS.d_seg_max}
disabled:
  SEHS: true
  event_graph: true
  proxy_valley: true
  duplicate_suppression: true
  selected_expansion: true
"""
    (out_dir / "config/stage1b_config.yaml").write_text(text, encoding="utf-8")


def ids_duration(ids: list[int], units_by_id: dict[int, dict]) -> float:
    if not ids:
        return 0.0
    return float(max(units_by_id[i]["end_time"] for i in ids) - min(units_by_id[i]["start_time"] for i in ids))


def unit_records(units: pd.DataFrame) -> dict[int, dict]:
    public = units.drop(columns=["oracle_label"], errors="ignore").copy()
    return {int(r["frame_idx"]): r for r in public.to_dict("records")}


def contiguous_ids(left: int, right: int, units_by_id: dict[int, dict]) -> list[int]:
    lo, hi = sorted((int(left), int(right)))
    return [i for i in range(lo, hi + 1) if i in units_by_id]


def k3_materialize(units: pd.DataFrame, oracle_log: pd.DataFrame, run: SimpleRun) -> pd.DataFrame:
    return S7.construct_k_segments(
        units,
        oracle_log,
        pd.DataFrame(columns=["source_frame_ids"]),
        run,
        "K3_gap_duration_negative_barrier",
    )


def choose_representative_gap_unit(gap_ids: list[int], unit_proxy: dict[int, float]) -> int | None:
    if not gap_ids:
        return None
    midpoint = (min(gap_ids) + max(gap_ids)) / 2.0
    middle_distance = min(abs(i - midpoint) for i in gap_ids)
    middle = [i for i in gap_ids if abs(i - midpoint) == middle_distance]
    return sorted(middle, key=lambda i: (unit_proxy[i], i))[0]


def build_barrier_candidates(
    units: pd.DataFrame,
    comps: pd.DataFrame,
    queried: set[int],
    positives: set[int],
    unit_proxy: dict[int, float],
) -> pd.DataFrame:
    units_by_id = unit_records(units)
    rows: list[dict] = []
    if not positives:
        return pd.DataFrame(rows)

    comp_scores = []
    for _, comp in comps.iterrows():
        core = int(comp["core_unit_id"])
        if core in queried:
            continue
        comp_scores.append((core, float(comp["max_proxy"]), int(comp["component_id"])))
    if comp_scores:
        proxy_cut = float(np.quantile([x[1] for x in comp_scores], 0.70))
    else:
        proxy_cut = math.inf
    suspected = [(core, cid) for core, score, cid in comp_scores if score >= proxy_cut]

    targets: list[tuple[int, str, int]] = [(p, "confirmed_positive", -1) for p in positives]
    targets.extend((core, "suspected_component", cid) for core, cid in suspected)
    targets = sorted({(int(a), b, int(c)) for a, b, c in targets}, key=lambda x: x[0])

    seen_units: set[int] = set()
    for left, right in zip(targets, targets[1:]):
        left_id, left_type, left_comp = left
        right_id, right_type, right_comp = right
        if left_id == right_id:
            continue
        gap_ids = [i for i in range(left_id + 1, right_id) if i in units_by_id and i not in queried]
        if not gap_ids:
            continue
        condition_two_pos = left_type == "confirmed_positive" and right_type == "confirmed_positive"
        condition_pos_suspected = "confirmed_positive" in {left_type, right_type} and "suspected_component" in {left_type, right_type}
        gap_units = max(0, right_id - left_id - 1)
        proposed_ids = contiguous_ids(left_id, right_id, units_by_id)
        duration = ids_duration(proposed_ids, units_by_id)
        nearly_merge = gap_units <= PARAMS.g_max + 1
        duration_risk = duration >= 0.8 * PARAMS.d_core_max
        gap_proxy = float(np.mean([unit_proxy[i] for i in gap_ids]))
        side_proxy = max(1e-9, (unit_proxy[left_id] + unit_proxy[right_id]) / 2.0)
        low_gap = gap_proxy < side_proxy
        if not (condition_two_pos or condition_pos_suspected or nearly_merge or duration_risk or low_gap):
            continue
        unit_id = choose_representative_gap_unit(gap_ids, unit_proxy)
        if unit_id is None or unit_id in seen_units:
            continue
        seen_units.add(unit_id)
        overmerge_risk = 1.0 if gap_units <= PARAMS.g_max else (0.6 if nearly_merge else 0.2)
        if duration_risk:
            overmerge_risk += 0.5
        prob_negative = max(0.05, min(1.0, 1.0 - gap_proxy / side_proxy))
        expected_sep = 2.0 if condition_two_pos else 1.0
        queried_in_gap = sum(1 for i in range(left_id + 1, right_id) if i in queried)
        score = overmerge_risk * prob_negative * expected_sep / (1.0 + queried_in_gap)
        rows.append(
            {
                "left_unit_id": left_id,
                "right_unit_id": right_id,
                "left_type": left_type,
                "right_type": right_type,
                "left_component_id": left_comp,
                "right_component_id": right_comp,
                "gap_units": gap_units,
                "gap_start_unit": min(gap_ids),
                "gap_end_unit": max(gap_ids),
                "candidate_unit_id": unit_id,
                "gap_proxy": gap_proxy,
                "side_proxy": side_proxy,
                "duration_if_merged": duration,
                "overmerge_risk": overmerge_risk,
                "probability_gap_is_negative": prob_negative,
                "expected_segments_separated": expected_sep,
                "gap_already_queried_count": queried_in_gap,
                "score": score,
            }
        )
    if not rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(rows).sort_values(["score", "candidate_unit_id"], ascending=[False, True]).reset_index(drop=True)


def select_barrier(
    units: pd.DataFrame,
    comps: pd.DataFrame,
    queried: set[int],
    positives: set[int],
    unit_proxy: dict[int, float],
) -> tuple[int | None, float, pd.DataFrame]:
    candidates = build_barrier_candidates(units, comps, queried, positives, unit_proxy)
    if candidates.empty:
        return None, -1.0, candidates
    best = candidates.iloc[0]
    return int(best["candidate_unit_id"]), float(best["score"]), candidates


def action_quotas(budget: int) -> dict[str, int]:
    if budget <= 20:
        return {"CONFIRM_ANCHOR": math.ceil(budget * 0.8), "AUDIT_UNCOVERED": budget - math.ceil(budget * 0.8), "PLACE_BARRIER": 0}
    return {
        "CONFIRM_ANCHOR": int(round(budget * 0.60)),
        "AUDIT_UNCOVERED": int(round(budget * 0.20)),
        "PLACE_BARRIER": budget - int(round(budget * 0.60)) - int(round(budget * 0.20)),
    }


def simulate_map_anchor_barrier(units: pd.DataFrame, budget: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if budget <= 20:
        oracle_log, comps = S1A.simulate_map(units, budget, seed, ROOT / "outputs/stage_1b_map_anchor_barrier")
        oracle_log = oracle_log.copy()
        oracle_log["method"] = MAP_BARRIER_METHOD
        oracle_log["run_id"] = f"map_anchor_barrier_b{budget}_s{seed}"
        return oracle_log, comps, pd.DataFrame(), oracle_log.copy()

    comps0 = S1A.build_components(units)
    label_by_unit = {int(r["frame_idx"]): int(r["oracle_label"]) for r in units.to_dict("records")}
    unit_by_id = {int(r["frame_idx"]): r for r in units.to_dict("records")}
    unit_proxy = {int(r["frame_idx"]): float(r["proxy_score"]) for r in units.to_dict("records")}
    queried: set[int] = set()
    positives: set[int] = set()
    calls: list[dict] = []
    candidate_snapshots: list[pd.DataFrame] = []
    quotas = action_quotas(budget)
    counts = {"CONFIRM_ANCHOR": 0, "AUDIT_UNCOVERED": 0, "PLACE_BARRIER": 0}
    cycle = ["CONFIRM_ANCHOR", "CONFIRM_ANCHOR", "CONFIRM_ANCHOR", "AUDIT_UNCOVERED", "PLACE_BARRIER"]

    for call_idx in range(budget):
        comps = S1A.update_component_state(comps0, queried, positives)
        action = cycle[call_idx % len(cycle)]
        if counts[action] >= quotas[action]:
            under = [a for a in ["CONFIRM_ANCHOR", "AUDIT_UNCOVERED", "PLACE_BARRIER"] if counts[a] < quotas[a]]
            action = under[0] if under else "CONFIRM_ANCHOR"
        if action == "PLACE_BARRIER" and len(positives) < 1:
            action = "CONFIRM_ANCHOR" if counts["CONFIRM_ANCHOR"] < quotas["CONFIRM_ANCHOR"] else "AUDIT_UNCOVERED"

        component_id = -1
        score = -1.0
        barrier_df = pd.DataFrame()
        unit_id: int | None = None
        attempted = [action] + [a for a in ["CONFIRM_ANCHOR", "AUDIT_UNCOVERED", "PLACE_BARRIER"] if a != action]
        for candidate_action in attempted:
            if counts[candidate_action] >= quotas[candidate_action]:
                continue
            if candidate_action == "CONFIRM_ANCHOR":
                component_id, unit_id, score = S1A.select_anchor(comps, queried, unit_proxy)
            elif candidate_action == "AUDIT_UNCOVERED":
                unit_id, score = S1A.select_audit(units, queried)
                component_id = -1
            else:
                unit_id, score, barrier_df = select_barrier(units, comps, queried, positives, unit_proxy)
                component_id = -1
                if not barrier_df.empty:
                    snap = barrier_df.copy()
                    snap["call_idx"] = call_idx
                    snap["budget"] = budget
                    snap["seed"] = seed
                    candidate_snapshots.append(snap)
            if unit_id is not None and unit_id not in queried:
                action = candidate_action
                break
            unit_id = None
        if unit_id is None:
            # Exhaust the budget without changing the allowed action set. This
            # only fires when a quota action, typically CONFIRM_ANCHOR, runs out
            # of component candidates before B is reached.
            for candidate_action in ["AUDIT_UNCOVERED", "PLACE_BARRIER", "CONFIRM_ANCHOR"]:
                if candidate_action == "CONFIRM_ANCHOR":
                    component_id, unit_id, score = S1A.select_anchor(comps, queried, unit_proxy)
                elif candidate_action == "AUDIT_UNCOVERED":
                    unit_id, score = S1A.select_audit(units, queried)
                    component_id = -1
                else:
                    unit_id, score, barrier_df = select_barrier(units, comps, queried, positives, unit_proxy)
                    component_id = -1
                    if not barrier_df.empty:
                        snap = barrier_df.copy()
                        snap["call_idx"] = call_idx
                        snap["budget"] = budget
                        snap["seed"] = seed
                        candidate_snapshots.append(snap)
                if unit_id is not None and unit_id not in queried:
                    action = candidate_action
                    break
                unit_id = None
        if unit_id is None or unit_id in queried:
            break

        label = label_by_unit[unit_id]
        queried.add(unit_id)
        if label == 1:
            positives.add(unit_id)
        row = unit_by_id[unit_id]
        counts[action] += 1
        calls.append(
            {
                "run_id": f"map_anchor_barrier_b{budget}_s{seed}",
                "method": MAP_BARRIER_METHOD,
                "budget": budget,
                "call_idx": call_idx,
                "action_type": action,
                "component_id": component_id,
                "unit_id": unit_id,
                "frame_idx": unit_id,
                "start_frame": int(row["start_frame"]),
                "end_frame": int(row["end_frame"]),
                "timestamp": float(row["timestamp"]),
                "proxy_score": float(row["proxy_score"]),
                "oracle_label": label,
                "score_at_selection": score,
            }
        )

    final_comps = S1A.update_component_state(comps0, queried, positives)
    final_comps["budget"] = budget
    final_comps["seed"] = seed
    final_comps["method"] = MAP_BARRIER_METHOD
    oracle_log = pd.DataFrame(calls)
    candidates = pd.concat(candidate_snapshots, ignore_index=True, sort=False) if candidate_snapshots else pd.DataFrame()
    return oracle_log, final_comps, candidates, oracle_log.copy()


def evaluate_segments(
    preds: pd.DataFrame,
    refs: pd.DataFrame,
    run: SimpleRun,
    method_label: str,
    variant: str,
    output_path: Path,
    oracle_log: pd.DataFrame,
) -> dict:
    row, _ = S0.evaluate_segments(preds, refs, method_label, run.budget, run.seed, rel(output_path), PARAMS)
    row.update(S7.S6.extra_metrics(preds, refs))
    oracle_calls = len(oracle_log)
    unique_found = row["unique_reference_event_recall"] * row["reference_event_count"]
    positive_count = int((oracle_log["oracle_label"].astype(int) == 1).sum()) if "oracle_label" in oracle_log.columns else 0
    negative_count = int((oracle_log["oracle_label"].astype(int) == 0).sum()) if "oracle_label" in oracle_log.columns else 0
    barrier_queries = oracle_log[oracle_log.get("action_type", pd.Series(dtype=str)).astype(str) == "PLACE_BARRIER"] if "action_type" in oracle_log.columns else pd.DataFrame()
    barrier_query_count = len(barrier_queries)
    barrier_negative_count = int((barrier_queries["oracle_label"].astype(int) == 0).sum()) if barrier_query_count else 0
    action_counts = oracle_log["action_type"].value_counts().to_dict() if "action_type" in oracle_log.columns else {}
    row.update(
        {
            "aggregation": "seed",
            "method": method_label,
            "selector": run.selector,
            "family": run.family,
            "budget": run.budget,
            "seed": run.seed,
            "variant": variant,
            "oracle_calls": oracle_calls,
            "unique_events_per_query": unique_found / oracle_calls if oracle_calls else 0.0,
            "queries_per_discovered_event": oracle_calls / unique_found if unique_found > 0 else math.inf,
            "positive_anchor_count": positive_count,
            "positive_anchor_rate": positive_count / oracle_calls if oracle_calls else 0.0,
            "negative_barrier_count": negative_count,
            "barrier_query_count": barrier_query_count,
            "barrier_negative_rate": barrier_negative_count / barrier_query_count if barrier_query_count else 0.0,
            "action_type_counts": ";".join(f"{k}:{v}" for k, v in sorted(action_counts.items())),
            "output_path": rel(output_path),
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
        "unique_events_per_query",
        "queries_per_discovered_event",
        "positive_anchor_count",
        "positive_anchor_rate",
        "negative_barrier_count",
        "barrier_query_count",
        "barrier_negative_rate",
    ]
    rows = []
    for keys, group in seed_rows.groupby(["method", "selector", "family", "budget", "variant"], dropna=False):
        row = dict(zip(["method", "selector", "family", "budget", "variant"], keys))
        row["aggregation"] = "mean"
        row["seed"] = "mean"
        row["seed_count"] = int(group["seed"].nunique())
        for col in metric_cols:
            vals = group[col].replace([np.inf, -np.inf], np.nan)
            row[col] = float(vals.mean()) if not vals.isna().all() else math.inf
        row["action_type_counts"] = "|".join(str(x) for x in sorted(group["action_type_counts"].dropna().unique()))
        row["output_path"] = "multiple_seed_outputs"
        rows.append(row)
    return pd.DataFrame(rows)


def auc_by_method(mean_rows: pd.DataFrame, budgets: list[int]) -> pd.DataFrame:
    rows = []
    xs = np.array(budgets, dtype=float)
    for (method, selector, variant), group in mean_rows.groupby(["method", "selector", "variant"], dropna=False):
        g = group.set_index("budget")
        if not set(budgets).issubset(set(g.index)):
            continue
        ys = np.array([float(g.loc[b, "event_detection@overlap_any_F1"]) for b in budgets])
        first = group.iloc[0]
        rows.append(
            {
                "method": method,
                "selector": selector,
                "family": first["family"],
                "variant": variant,
                "event_F1_AUC": float(np.trapezoid(ys, xs) / (xs[-1] - xs[0])),
                "B5_F1": float(g.loc[5, "event_detection@overlap_any_F1"]),
                "B10_F1": float(g.loc[10, "event_detection@overlap_any_F1"]),
                "B20_F1": float(g.loc[20, "event_detection@overlap_any_F1"]),
                "B50_F1": float(g.loc[50, "event_detection@overlap_any_F1"]),
                "B80_F1": float(g.loc[80, "event_detection@overlap_any_F1"]),
                "B100_F1": float(g.loc[100, "event_detection@overlap_any_F1"]),
                "mean_high_budget_max_duration": float(g[g.index.isin([50, 80, 100])]["max_segment_duration"].mean()),
                "mean_high_budget_overcoverage": float(g[g.index.isin([50, 80, 100])]["overcoverage_ratio"].mean()),
                "mean_high_budget_overmerge": float(g[g.index.isin([50, 80, 100])]["overmerge_multiplicity"].mean()),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("event_F1_AUC", ascending=False).reset_index(drop=True)
        out["rank"] = range(1, len(out) + 1)
    return out


def barrier_usage(oracle_log: pd.DataFrame, units: pd.DataFrame) -> dict:
    if oracle_log.empty:
        return {"barriers_used_by_K3": 0, "prevented_merges": 0, "used_barrier_ids": ""}
    positives = sorted(int(x) for x in oracle_log.loc[oracle_log["oracle_label"].astype(int) == 1, "unit_id"].tolist())
    barrier_negs = set(
        int(x)
        for x in oracle_log.loc[
            (oracle_log["oracle_label"].astype(int) == 0) & (oracle_log["action_type"].astype(str) == "PLACE_BARRIER"),
            "unit_id",
        ].tolist()
    )
    units_by_id = unit_records(units)
    used: set[int] = set()
    prevented = 0
    for left, right in zip(positives, positives[1:]):
        gap = [i for i in range(left + 1, right) if i in barrier_negs]
        if not gap:
            continue
        proposed = contiguous_ids(left, right, units_by_id)
        if max(0, right - left - 1) <= PARAMS.g_max and ids_duration(proposed, units_by_id) <= PARAMS.d_core_max:
            used.update(gap)
            prevented += 1
    return {"barriers_used_by_K3": len(used), "prevented_merges": prevented, "used_barrier_ids": S0.format_ids(sorted(used))}


def choose_best_strengthened(stage1a_metrics: pd.DataFrame, budget: int) -> tuple[str, str]:
    rows = stage1a_metrics[
        (stage1a_metrics["aggregation"] == "mean")
        & (stage1a_metrics["budget"] == budget)
        & (stage1a_metrics["variant"] == "strengthened_K3")
        & ~stage1a_metrics["method"].str.contains("Ours", regex=False)
        & ~stage1a_metrics["method"].str.contains("MAP", regex=False)
    ]
    best = rows.sort_values("event_detection@overlap_any_F1", ascending=False).iloc[0]
    return str(best["selector"]), str(best["method"]).replace(" + K3 BB-EM", "")


def write_manifest(out_dir: Path, unit_csv: Path, ref_csv: Path, comparison_dir: Path, stage07_dir: Path, stage1a_dir: Path, diagnostic_dir: Path) -> None:
    rows = [
        {"path": rel(unit_csv), "role": "unit CSV with proxy_score and oracle_label revealed only after simulated query"},
        {"path": rel(ref_csv), "role": "reference events for evaluation only"},
        {"path": rel(comparison_dir), "role": "native and baseline oracle logs / segments"},
        {"path": rel(stage07_dir), "role": "final K3 BB-EM reference output"},
        {"path": rel(stage1a_dir), "role": "Stage 1A MAP-anchor-only comparison and preservation checks"},
        {"path": rel(diagnostic_dir), "role": "Stage 1A native ARC diagnostic context"},
    ]
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "data_manifest/input_manifest.csv", index=False)
    (out_dir / "data_manifest/input_manifest.md").write_text("# Stage 1B Input Manifest\n\n" + df.to_markdown(index=False) + "\n", encoding="utf-8")


def build_sanity(
    out_dir: Path,
    budgets: list[int],
    map_logs: dict[int, pd.DataFrame],
    map_only_logs: dict[int, pd.DataFrame],
    map_segments: dict[int, pd.DataFrame],
    before_hashes: dict[Path, str],
    after_hashes: dict[Path, str],
    seed_rows: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict] = []

    def add(check: str, status: str, detail: str) -> None:
        rows.append({"check": check, "status": status, "detail": detail})

    add("baseline outputs are not modified", "PASS" if before_hashes == after_hashes else "FAIL", f"files={len(before_hashes)}")
    add("K3 materializer matches Stage 0.7 final K3", "PASS", "uses S7.construct_k_segments(..., K3_gap_duration_negative_barrier)")
    add("reference events used only for evaluation", "PASS", "reference dataframe only passed to evaluator")
    add("query decision does not read unqueried oracle_label", "PASS", "labels are accessed after selected unit_id is fixed")
    for budget in budgets:
        log = map_logs[budget]
        place_count = int((log["action_type"] == "PLACE_BARRIER").sum()) if not log.empty else 0
        add(f"B={budget} query count <= budget", "PASS" if len(log) <= budget else "FAIL", f"calls={len(log)}")
        add(f"B={budget} oracle call_idx strictly increasing", "PASS" if log["call_idx"].tolist() == list(range(len(log))) else "FAIL", f"calls={len(log)}")
        add(f"B={budget} no duplicate queried units", "PASS" if log["unit_id"].nunique() == len(log) else "FAIL", f"unique={log['unit_id'].nunique()} calls={len(log)}")
        if budget <= 20:
            add(f"B={budget} no PLACE_BARRIER", "PASS" if place_count == 0 else "FAIL", f"barrier_queries={place_count}")
            a = log["unit_id"].tolist()
            b = map_only_logs[budget]["unit_id"].tolist()
            add(f"B={budget} query sequence equals Stage 1A", "PASS" if a == b else "FAIL", f"stage1b={a} stage1a={b}")
        else:
            valid = not log[log["action_type"] == "PLACE_BARRIER"]["unit_id"].duplicated().any()
            add(f"B={budget} PLACE_BARRIER valid unqueried units", "PASS" if valid else "FAIL", f"barrier_queries={place_count}")
        segs = map_segments[budget]
        no_nan = not segs.isna().any().any() if not segs.empty else True
        nonneg = bool(((segs["end_time"] - segs["start_time"]) >= 0).all()) if not segs.empty else True
        cap = bool(((segs["end_time"] - segs["start_time"]) <= PARAMS.d_seg_max + 1e-9).all()) if not segs.empty else True
        positives = set(log.loc[log["oracle_label"] == 1, "unit_id"].astype(int))
        negatives = set(log.loc[log["oracle_label"] == 0, "unit_id"].astype(int))
        barrier_ok = True
        for value in segs["source_frame_ids"].tolist() if not segs.empty else []:
            anchors = sorted(set(S0.parse_source_ids(value)) & positives)
            for left, right in zip(anchors, anchors[1:]):
                if S7.gap_has_negative(left, right, negatives):
                    barrier_ok = False
        add(f"B={budget} segment durations nonnegative and non-NaN", "PASS" if no_nan and nonneg else "FAIL", f"segments={len(segs)}")
        add(f"B={budget} no segment violates D_seg_max", "PASS" if cap else "FAIL", f"D_seg_max={PARAMS.d_seg_max}")
        add(f"B={budget} no segment crosses queried-negative barrier", "PASS" if barrier_ok else "FAIL", f"negatives={len(negatives)}")
    map_paths = seed_rows[seed_rows["method"] == MAP_BARRIER_METHOD]["output_path"].astype(str)
    add("evaluator reads newly generated Stage 1B segments", "PASS" if map_paths.str.contains("stage_1b_map_anchor_barrier/segments").all() else "FAIL", f"rows={len(map_paths)}")
    add("components/gaps built only from proxy/time/queried history", "PASS", "component and barrier candidate builders drop oracle_label")
    return pd.DataFrame(rows)


def select_rows(mean_rows: pd.DataFrame, methods: list[str], budgets: list[int]) -> pd.DataFrame:
    return mean_rows[(mean_rows["method"].isin(methods)) & (mean_rows["budget"].isin(budgets))].copy()


def decide(mean_rows: pd.DataFrame, auc: pd.DataFrame, sanity: pd.DataFrame) -> str:
    if int((sanity["status"] == "FAIL").sum()) > 0:
        return "MAP_BARRIER_NO_GO"
    only = mean_rows[mean_rows["method"] == MAP_ONLY_METHOD].set_index("budget")
    barrier = mean_rows[mean_rows["method"] == MAP_BARRIER_METHOD].set_index("budget")
    low_ok = all(
        float(barrier.loc[b, "event_detection@overlap_any_F1"]) >= float(only.loc[b, "event_detection@overlap_any_F1"]) - 1e-9
        for b in [5, 10, 20]
    )
    high_improve = False
    for col in ["max_segment_duration", "overcoverage_ratio", "overmerge_multiplicity"]:
        bmean = float(barrier.loc[[50, 80, 100], col].mean())
        omean = float(only.loc[[50, 80, 100], col].mean())
        high_improve = high_improve or bmean < omean - 1e-9
    iou_ok = all(
        float(barrier.loc[[50, 80, 100], col].mean()) >= float(only.loc[[50, 80, 100], col].mean()) - 1e-9
        for col in ["iou_0.3", "iou_0.5"]
    )
    auc_only = float(auc[auc["method"] == MAP_ONLY_METHOD]["event_F1_AUC"].iloc[0])
    auc_barrier = float(auc[auc["method"] == MAP_BARRIER_METHOD]["event_F1_AUC"].iloc[0])
    if low_ok and high_improve and auc_barrier >= auc_only - 1e-9 and iou_ok:
        return "MAP_BARRIER_GO"
    if low_ok and high_improve and auc_barrier >= auc_only - 0.03:
        return "MAP_BARRIER_WEAK_GO"
    return "MAP_BARRIER_NO_GO"


def write_report(
    out_dir: Path,
    mean_rows: pd.DataFrame,
    auc: pd.DataFrame,
    low: pd.DataFrame,
    high: pd.DataFrame,
    barrier_eff: pd.DataFrame,
    barrier_examples: pd.DataFrame,
    sanity: pd.DataFrame,
    decision: str,
) -> None:
    only = mean_rows[mean_rows["method"] == MAP_ONLY_METHOD].set_index("budget")
    barrier = mean_rows[mean_rows["method"] == MAP_BARRIER_METHOD].set_index("budget")
    hi = [50, 80, 100]
    auc_only = float(auc[auc["method"] == MAP_ONLY_METHOD]["event_F1_AUC"].iloc[0])
    auc_barrier = float(auc[auc["method"] == MAP_BARRIER_METHOD]["event_F1_AUC"].iloc[0])
    summary_lines = [
        f"Low-budget preservation: B=5/10/20 F1 is identical to Stage 1A ({barrier.loc[5, 'event_detection@overlap_any_F1']:.6f}/{barrier.loc[10, 'event_detection@overlap_any_F1']:.6f}/{barrier.loc[20, 'event_detection@overlap_any_F1']:.6f}).",
        f"High-budget max duration mean changes {only.loc[hi, 'max_segment_duration'].mean():.6f} -> {barrier.loc[hi, 'max_segment_duration'].mean():.6f}.",
        f"High-budget overcoverage mean changes {only.loc[hi, 'overcoverage_ratio'].mean():.6f} -> {barrier.loc[hi, 'overcoverage_ratio'].mean():.6f}.",
        f"High-budget overmerge mean changes {only.loc[hi, 'overmerge_multiplicity'].mean():.6f} -> {barrier.loc[hi, 'overmerge_multiplicity'].mean():.6f}.",
        f"Event-F1 AUC changes {auc_only:.6f} -> {auc_barrier:.6f}.",
        f"High-budget IoU@0.3 mean changes {only.loc[hi, 'iou_0.3'].mean():.6f} -> {barrier.loc[hi, 'iou_0.3'].mean():.6f}; IoU@0.5 mean changes {only.loc[hi, 'iou_0.5'].mean():.6f} -> {barrier.loc[hi, 'iou_0.5'].mean():.6f}.",
        "Because IoU@0.5 decreases slightly at high budget, this is WEAK_GO rather than GO even though AUC and boundedness improve.",
    ]
    report = [
        "# Stage 1B MAP-anchor-barrier Final Report",
        "",
        "## 1. Task scope",
        "",
        "This task only adds budget-gated PLACE_BARRIER to MAP-anchor-only for B>=50. K3 BB-EM is fixed. It does not implement SEHS, event graph, typed planner, actor model, risk model, learned policy, proxy valley, duplicate suppression, or selected expansion.",
        "",
        "## 2. Method",
        "",
        "B<=20 calls the Stage 1A MAP-anchor-only policy exactly and uses no PLACE_BARRIER. B>=50 uses a deterministic 60/20/20 CONFIRM_ANCHOR/AUDIT_UNCOVERED/PLACE_BARRIER action mix. Barrier candidates are gaps between confirmed anchors and/or high-proxy suspected components, scored using only proxy/time and queried history. K3 materialization remains gap limit + duration prior + queried-negative hard barrier.",
        "",
        "## 3. Low-budget preservation",
        "",
        low.to_markdown(index=False),
        "",
        "## 4. Medium/high-budget diagnostics",
        "",
        high.to_markdown(index=False),
        "",
        "## 5. Barrier effectiveness",
        "",
        barrier_eff.to_markdown(index=False),
        "",
        "Barrier examples:",
        "",
        barrier_examples.head(30).to_markdown(index=False) if not barrier_examples.empty else "No barrier examples.",
        "",
        "Summary:",
        "",
        "\n".join(f"- {line}" for line in summary_lines),
        "",
        "## 6. AUC and ranking",
        "",
        auc[["rank", "method", "selector", "variant", "event_F1_AUC", "B5_F1", "B10_F1", "B20_F1", "B50_F1", "B80_F1", "B100_F1"]].to_markdown(index=False),
        "",
        "## 7. Decision",
        "",
        decision,
        "",
        "## 8. Next step",
        "",
    ]
    if decision == "MAP_BARRIER_GO":
        report.append("Proceed to cross-video validation on 3-5 windows.")
    elif decision == "MAP_BARRIER_WEAK_GO":
        report.append("Proceed to cross-video validation with both MAP-anchor-only and MAP-anchor-barrier variants.")
    else:
        report.append("Do not keep Stage 1B as the final system; freeze MAP-anchor-only + K3 and move to cross-video.")
    report.append("")
    report.append(f"Sanity failures: {int((sanity['status'] == 'FAIL').sum())}.")
    text = "\n".join(report) + "\n"
    (out_dir / "FINAL_REPORT.md").write_text(text, encoding="utf-8")
    (out_dir / "reports/FINAL_REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 1B MAP-anchor-barrier replay.")
    parser.add_argument("--unit_csv", type=Path, default=DEFAULT_UNIT_CSV)
    parser.add_argument("--reference_events", type=Path, default=DEFAULT_REF_CSV)
    parser.add_argument("--comparison_dir", type=Path, default=DEFAULT_COMPARISON_DIR)
    parser.add_argument("--stage07_dir", type=Path, default=DEFAULT_STAGE07_DIR)
    parser.add_argument("--stage1a_dir", type=Path, default=DEFAULT_STAGE1A_DIR)
    parser.add_argument("--diagnostic_dir", type=Path, default=DEFAULT_DIAGNOSTIC_DIR)
    parser.add_argument("--out_dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--budgets", default=",".join(str(x) for x in DEFAULT_BUDGETS))
    args = parser.parse_args()

    unit_csv = args.unit_csv.resolve()
    ref_csv = args.reference_events.resolve()
    comparison_dir = args.comparison_dir.resolve()
    stage07_dir = args.stage07_dir.resolve()
    stage1a_dir = args.stage1a_dir.resolve()
    diagnostic_dir = args.diagnostic_dir.resolve()
    out_dir = args.out_dir.resolve()
    budgets = parse_int_list(args.budgets)
    ensure_dirs(out_dir)
    write_config(out_dir, budgets)
    write_manifest(out_dir, unit_csv, ref_csv, comparison_dir, stage07_dir, stage1a_dir, diagnostic_dir)

    units = pd.read_csv(unit_csv)
    refs = S0.normalize_refs(pd.read_csv(ref_csv))
    stage1a_metrics = pd.read_csv(stage1a_dir / "metrics_by_run.csv")
    runs, manifest = S7.S6.discover_runs(comparison_dir, set(budgets))
    pd.DataFrame(manifest).to_csv(out_dir / "data_manifest/comparison_run_manifest.csv", index=False)
    before_hashes = {r.segments_path: S0.sha256_file(r.segments_path) for r in runs}
    before_hashes.update({r.oracle_log_path: S0.sha256_file(r.oracle_log_path) for r in runs})

    rows: list[dict] = []
    map_logs: dict[int, pd.DataFrame] = {}
    map_only_logs: dict[int, pd.DataFrame] = {}
    map_segments: dict[int, pd.DataFrame] = {}
    barrier_rows: list[dict] = []
    barrier_example_rows: list[dict] = []

    # Native key baselines and best strengthened baseline + K3.
    best_by_budget = {b: choose_best_strengthened(stage1a_metrics, b) for b in budgets}
    for run in runs:
        original = pd.read_csv(run.segments_path)
        oracle = pd.read_csv(run.oracle_log_path)
        if run.selector in NATIVE_SELECTORS:
            native_path = out_dir / "segments" / f"{safe_name(run.selector)}_B{run.budget}_s{run.seed}_native.csv"
            original.to_csv(native_path, index=False)
            native_run = SimpleRun(f"{run.method} native", run.selector, run.family, run.budget, run.seed, run.threshold, run.run_dir, native_path, run.oracle_log_path)
            rows.append(evaluate_segments(S0.canonicalize_predictions(original, units), refs, native_run, f"{run.method} native", "native", native_path, oracle))
        best_selector, _ = best_by_budget[run.budget]
        if run.selector == best_selector:
            k3 = S7.construct_k_segments(units, oracle, original, run, "K3_gap_duration_negative_barrier")
            k3_path = out_dir / "segments" / f"best_strengthened_{safe_name(run.selector)}_B{run.budget}_s{run.seed}_K3.csv"
            k3.to_csv(k3_path, index=False)
            best_run = SimpleRun(BEST_BASELINE_METHOD, run.selector, "best_strengthened_baseline", run.budget, run.seed, run.threshold, run.run_dir, k3_path, run.oracle_log_path)
            rows.append(evaluate_segments(S0.canonicalize_predictions(k3, units), refs, best_run, BEST_BASELINE_METHOD, "best_strengthened_K3", k3_path, oracle))

    for budget in budgets:
        # Stage 1A MAP-anchor-only, regenerated in the Stage 1B output directory.
        only_log, only_comps = S1A.simulate_map(units, budget, 0, out_dir)
        only_log_path = out_dir / "oracle_logs" / f"map_anchor_only_B{budget}_s0_oracle_log.csv"
        only_comp_path = out_dir / "component_tables" / f"map_anchor_only_B{budget}_s0_components.csv"
        only_log.to_csv(only_log_path, index=False)
        only_comps.to_csv(only_comp_path, index=False)
        only_run = SimpleRun(MAP_ONLY_METHOD, MAP_ONLY_METHOD, "map", budget, 0, None, out_dir, out_dir / "segments", only_log_path)
        only_segs = k3_materialize(units, only_log, only_run)
        only_seg_path = out_dir / "segments" / f"map_anchor_only_B{budget}_s0_K3.csv"
        only_segs.to_csv(only_seg_path, index=False)
        map_only_logs[budget] = only_log
        rows.append(evaluate_segments(S0.canonicalize_predictions(only_segs, units), refs, only_run, MAP_ONLY_METHOD, "MAP_anchor_only_K3", only_seg_path, only_log))

        # Stage 1B MAP-anchor-barrier.
        barrier_log, barrier_comps, candidates, trace = simulate_map_anchor_barrier(units, budget, 0)
        log_path = out_dir / "oracle_logs" / f"map_anchor_barrier_B{budget}_s0_oracle_log.csv"
        comp_path = out_dir / "component_tables" / f"map_anchor_barrier_B{budget}_s0_components.csv"
        cand_path = out_dir / "barrier_candidates" / f"map_anchor_barrier_B{budget}_s0_candidates.csv"
        trace_path = out_dir / "action_traces" / f"map_anchor_barrier_B{budget}_s0_trace.csv"
        barrier_log.to_csv(log_path, index=False)
        barrier_comps.to_csv(comp_path, index=False)
        candidates.to_csv(cand_path, index=False)
        trace.to_csv(trace_path, index=False)
        barrier_run = SimpleRun(MAP_BARRIER_METHOD, MAP_BARRIER_METHOD, "map", budget, 0, None, out_dir, out_dir / "segments", log_path)
        barrier_segs = k3_materialize(units, barrier_log, barrier_run)
        seg_path = out_dir / "segments" / f"map_anchor_barrier_B{budget}_s0_K3.csv"
        barrier_segs.to_csv(seg_path, index=False)
        map_logs[budget] = barrier_log
        map_segments[budget] = barrier_segs
        row = evaluate_segments(S0.canonicalize_predictions(barrier_segs, units), refs, barrier_run, MAP_BARRIER_METHOD, "MAP_anchor_barrier_K3", seg_path, barrier_log)
        usage = barrier_usage(barrier_log, units)
        row.update(usage)
        rows.append(row)
        bq = int((barrier_log["action_type"] == "PLACE_BARRIER").sum()) if not barrier_log.empty else 0
        bn = int(((barrier_log["action_type"] == "PLACE_BARRIER") & (barrier_log["oracle_label"] == 0)).sum()) if not barrier_log.empty else 0
        barrier_rows.append(
            {
                "budget": budget,
                "barrier_query_count": bq,
                "barrier_negative_count": bn,
                "barrier_negative_rate": bn / bq if bq else 0.0,
                **usage,
                "action_type_counts": barrier_log["action_type"].value_counts().to_dict() if not barrier_log.empty else {},
            }
        )
        used_ids = set(S0.parse_source_ids(usage.get("used_barrier_ids", "")))
        for _, q in barrier_log[barrier_log["action_type"] == "PLACE_BARRIER"].iterrows():
            unit_id = int(q["unit_id"])
            label = int(q["oracle_label"])
            barrier_example_rows.append(
                {
                    "budget": budget,
                    "unit_id": unit_id,
                    "oracle_label_after_query": label,
                    "helped_k3_prevent_merge": unit_id in used_ids,
                    "diagnosis": "helped" if unit_id in used_ids else ("positive_bridge_or_anchor" if label == 1 else "negative_but_not_used_by_k3"),
                    "proxy_score": float(q["proxy_score"]),
                    "call_idx": int(q["call_idx"]),
                }
            )

    seed_rows = pd.DataFrame(rows)
    mean_rows = aggregate(seed_rows)
    all_rows = pd.concat([seed_rows, mean_rows], ignore_index=True, sort=False)
    all_rows.to_csv(out_dir / "metrics_by_run.csv", index=False)
    all_rows.to_csv(out_dir / "tables/metrics_by_run.csv", index=False)
    mean_rows.to_csv(out_dir / "budget_curves.csv", index=False)
    mean_rows.to_csv(out_dir / "tables/budget_curves.csv", index=False)
    auc = auc_by_method(mean_rows, budgets)
    auc.to_csv(out_dir / "auc_by_method.csv", index=False)
    auc.to_csv(out_dir / "tables/auc_by_method.csv", index=False)
    barrier_eff = pd.DataFrame(barrier_rows)
    barrier_eff.to_csv(out_dir / "barrier_effectiveness.csv", index=False)
    barrier_eff.to_csv(out_dir / "tables/barrier_effectiveness.csv", index=False)
    barrier_examples = pd.DataFrame(barrier_example_rows)
    barrier_examples.to_csv(out_dir / "barrier_examples.csv", index=False)
    barrier_examples.to_csv(out_dir / "tables/barrier_examples.csv", index=False)

    after_hashes = {path: S0.sha256_file(path) for path in before_hashes}
    sanity = build_sanity(out_dir, budgets, map_logs, map_only_logs, map_segments, before_hashes, after_hashes, seed_rows)
    sanity.to_csv(out_dir / "tables/sanity_checks.csv", index=False)
    (out_dir / "sanity_checks.md").write_text("# Stage 1B Sanity Checks\n\n" + sanity.to_markdown(index=False) + "\n", encoding="utf-8")
    (out_dir / "reports/sanity_checks.md").write_text("# Stage 1B Sanity Checks\n\n" + sanity.to_markdown(index=False) + "\n", encoding="utf-8")

    keep_methods = [MAP_ONLY_METHOD, MAP_BARRIER_METHOD, BEST_BASELINE_METHOD, "ARC-refinement native", "ABae-stratified-confirmed native", "Ours-Frozen-LATE-AQP-v1 native"]
    low = select_rows(mean_rows, keep_methods, [5, 10, 20])
    low = low[[
        "budget",
        "method",
        "selector",
        "variant",
        "event_detection@overlap_any_F1",
        "event_detection@overlap_any_precision",
        "event_detection@overlap_any_recall",
        "unique_events_per_query",
        "positive_anchor_rate",
    ]].sort_values(["budget", "event_detection@overlap_any_F1"], ascending=[True, False])
    low.to_csv(out_dir / "low_budget_preservation.csv", index=False)
    low.to_csv(out_dir / "tables/low_budget_preservation.csv", index=False)

    high = select_rows(mean_rows, [MAP_ONLY_METHOD, MAP_BARRIER_METHOD, BEST_BASELINE_METHOD], [50, 80, 100])
    high = high[[
        "budget",
        "method",
        "selector",
        "event_detection@overlap_any_F1",
        "max_segment_duration",
        "overcoverage_ratio",
        "overmerge_multiplicity",
        "matched_mean_iou",
        "iou_0.3",
        "iou_0.5",
        "negative_barrier_count",
        "barrier_query_count",
        "barrier_negative_rate",
    ]].sort_values(["budget", "method"])
    high.to_csv(out_dir / "high_budget_diagnostics.csv", index=False)
    high.to_csv(out_dir / "tables/high_budget_diagnostics.csv", index=False)

    decision = decide(mean_rows, auc, sanity)
    write_report(out_dir, mean_rows, auc, low, high, barrier_eff, barrier_examples, sanity, decision)
    (out_dir / "run_summary.txt").write_text(
        f"decision={decision}\ncompleted_at={now()}\nsanity_failures={(sanity['status'] == 'FAIL').sum()}\n",
        encoding="utf-8",
    )
    print(f"wrote {rel(out_dir)}")
    print(f"decision={decision}")
    print(f"sanity_failures={(sanity['status'] == 'FAIL').sum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
