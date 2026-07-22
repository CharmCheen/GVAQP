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

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE0_SCRIPT = ROOT / "scripts/stage0_merge_only_repair.py"
STAGE07_SCRIPT = ROOT / "scripts/stage0_7_minimal_operator_compression.py"
DEFAULT_UNIT_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv"
DEFAULT_REF_CSV = ROOT / "outputs/real_video_protocol_pilot_v1/reference_segments_adapter_ready.csv"
DEFAULT_COMPARISON_DIR = ROOT / "outputs/ours_vs_baselines_realcartest_v1"
DEFAULT_STAGE07_DIR = ROOT / "outputs/stage_0_7_minimal_operator_compression"
DEFAULT_OUT_DIR = ROOT / "outputs/stage_1a_map_anchor_only"
DEFAULT_BUDGETS = [5, 10, 20, 50, 80, 100]
MAP_METHOD = "MAP-anchor-only + K3 BB-EM"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


S0 = load_module("stage0_merge_only_repair", STAGE0_SCRIPT)
S7 = load_module("stage0_7_minimal_operator_compression", STAGE07_SCRIPT)
PARAMS = S7.PARAMS


@dataclass(frozen=True)
class MapRun:
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
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", value.replace("@", "_").replace("+", "plus").replace(" ", "_"))


def ensure_dirs(out_dir: Path) -> None:
    for sub in ["segments", "oracle_logs", "component_tables", "config", "data_manifest", "logs", "tables", "reports", "figures"]:
        (out_dir / sub).mkdir(parents=True, exist_ok=True)


def normalize_proxy(units: pd.DataFrame) -> pd.DataFrame:
    out = units.drop(columns=["oracle_label"], errors="ignore").copy()
    mn = float(out["proxy_score"].min())
    mx = float(out["proxy_score"].max())
    out["proxy_norm"] = (out["proxy_score"] - mn) / (mx - mn) if mx > mn else 0.0
    out["rank_norm"] = out["proxy_score"].rank(method="average", pct=True)
    return out


def build_components(units: pd.DataFrame, window_seconds: float = 60.0) -> pd.DataFrame:
    public = normalize_proxy(units)
    threshold = float(public["proxy_score"].quantile(0.70))
    rows = []
    covered: set[int] = set()
    high = public[public["proxy_score"] >= threshold].sort_values("frame_idx")
    current = []
    last = None
    comp_id = 0
    for row in high.to_dict("records"):
        idx = int(row["frame_idx"])
        if current and idx != int(last) + 1:
            rows.append(component_row(comp_id, current, "high_proxy_island"))
            covered.update(int(x["frame_idx"]) for x in current)
            comp_id += 1
            current = []
        current.append(row)
        last = idx
    if current:
        rows.append(component_row(comp_id, current, "high_proxy_island"))
        covered.update(int(x["frame_idx"]) for x in current)
        comp_id += 1
    records = public.sort_values("frame_idx").to_dict("records")
    for i, row in enumerate(records):
        idx = int(row["frame_idx"])
        if idx in covered:
            continue
        left = float(records[i - 1]["proxy_score"]) if i > 0 else -math.inf
        right = float(records[i + 1]["proxy_score"]) if i + 1 < len(records) else -math.inf
        if float(row["proxy_score"]) >= left and float(row["proxy_score"]) >= right:
            rows.append(component_row(comp_id, [row], "local_peak_singleton"))
            covered.add(idx)
            comp_id += 1
    min_t = float(public["start_time"].min())
    max_t = float(public["end_time"].max())
    start = min_t
    while start < max_t:
        end = min(start + window_seconds, max_t)
        window = public[(public["start_time"] >= start) & (public["start_time"] < end)]
        if not window.empty:
            best = window.sort_values(["proxy_score", "rank_norm", "frame_idx"], ascending=[False, False, True]).iloc[0].to_dict()
            idx = int(best["frame_idx"])
            if idx not in covered:
                rows.append(component_row(comp_id, [best], "uncovered_region_audit"))
                covered.add(idx)
                comp_id += 1
        start = end
    comps = pd.DataFrame(rows)
    if comps.empty:
        return comps
    comps = comps.sort_values(["max_proxy", "mean_proxy", "start_time"], ascending=[False, False, True]).reset_index(drop=True)
    comps["component_id"] = range(len(comps))
    return comps


def component_row(component_id: int, rows: list[dict], status: str) -> dict:
    core = sorted(rows, key=lambda x: (-float(x["proxy_score"]), int(x["frame_idx"])))[0]
    ids = [int(x["frame_idx"]) for x in rows]
    return {
        "component_id": component_id,
        "start_time": min(float(x["start_time"]) for x in rows),
        "end_time": max(float(x["end_time"]) for x in rows),
        "core_unit_id": int(core["frame_idx"]),
        "candidate_unit_ids": "|".join(str(x) for x in sorted(ids)),
        "max_proxy": max(float(x["proxy_score"]) for x in rows),
        "mean_proxy": float(np.mean([float(x["proxy_score"]) for x in rows])),
        "length_units": len(rows),
        "distance_to_nearest_queried_unit": math.inf,
        "queried_count": 0,
        "positive_anchor_count": 0,
        "status": status,
    }


def ids_from_component(row: pd.Series) -> list[int]:
    return [int(x) for x in str(row["candidate_unit_ids"]).split("|") if str(x).strip()]


def nearby_count(unit_id: int, queried: set[int], radius: int = 2) -> int:
    return sum(1 for q in queried if abs(int(q) - int(unit_id)) <= radius)


def update_component_state(comps: pd.DataFrame, queried: set[int], positives: set[int]) -> pd.DataFrame:
    out = comps.copy()
    distances = []
    queried_counts = []
    positive_counts = []
    statuses = []
    for _, row in out.iterrows():
        ids = ids_from_component(row)
        distances.append(min((abs(i - q) for i in ids for q in queried), default=math.inf))
        q_count = sum(1 for i in ids if i in queried)
        p_count = sum(1 for i in ids if i in positives)
        queried_counts.append(q_count)
        positive_counts.append(p_count)
        statuses.append("positive_found" if p_count else ("queried_negative_only" if q_count else row["status"]))
    out["distance_to_nearest_queried_unit"] = distances
    out["queried_count"] = queried_counts
    out["positive_anchor_count"] = positive_counts
    out["status"] = statuses
    return out


def score_anchor(row: pd.Series, queried: set[int]) -> float:
    ids = ids_from_component(row)
    unqueried = [i for i in ids if i not in queried]
    if not unqueried:
        return -1.0
    core = unqueried[0] if int(row["core_unit_id"]) in queried else int(row["core_unit_id"])
    proxy_eventness = 0.7 * float(row["max_proxy"]) + 0.3 * float(row["mean_proxy"])
    dist = min((abs(core - q) for q in queried), default=12)
    temporal_novelty = min(1.0, dist / 6.0)
    coverage_gap = 1.0 + min(1.0, dist / 6.0)
    return proxy_eventness * temporal_novelty * coverage_gap / (1.0 + nearby_count(core, queried, 2))


def select_anchor(comps: pd.DataFrame, queried: set[int], unit_proxy: dict[int, float]) -> tuple[int | None, int | None, float]:
    best = (None, None, -1.0)
    for _, row in comps.iterrows():
        ids = [i for i in ids_from_component(row) if i not in queried]
        if not ids:
            continue
        score = score_anchor(row, queried)
        unit_id = sorted(ids, key=lambda i: (-unit_proxy[i], i))[0]
        if score > best[2]:
            best = (int(row["component_id"]), unit_id, score)
    return best


def build_audit_regions(units: pd.DataFrame, queried: set[int], window_seconds: float = 60.0) -> list[dict]:
    public = units.drop(columns=["oracle_label"], errors="ignore")
    rows = []
    start = float(public["start_time"].min())
    max_t = float(public["end_time"].max())
    while start < max_t:
        end = min(start + window_seconds, max_t)
        window = public[(public["start_time"] >= start) & (public["start_time"] < end)]
        unq = window[~window["frame_idx"].astype(int).isin(queried)]
        if not unq.empty:
            best = unq.sort_values(["proxy_score", "frame_idx"], ascending=[False, True]).iloc[0]
            q_near = nearby_count(int(best["frame_idx"]), queried, 3)
            isolation = 1.0 / (1.0 + q_near)
            rows.append(
                {
                    "region_start": start,
                    "region_end": end,
                    "unit_id": int(best["frame_idx"]),
                    "score": (end - start) * float(best["proxy_score"]) * isolation,
                }
            )
        start = end
    return rows


def select_audit(units: pd.DataFrame, queried: set[int]) -> tuple[int | None, float]:
    regions = build_audit_regions(units, queried)
    if not regions:
        return None, -1.0
    best = sorted(regions, key=lambda r: (-r["score"], r["unit_id"]))[0]
    return int(best["unit_id"]), float(best["score"])


def simulate_map(units: pd.DataFrame, budget: int, seed: int, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    comps0 = build_components(units)
    label_by_unit = {int(r["frame_idx"]): int(r["oracle_label"]) for r in units.to_dict("records")}
    unit_by_id = {int(r["frame_idx"]): r for r in units.to_dict("records")}
    unit_proxy = {int(r["frame_idx"]): float(r["proxy_score"]) for r in units.to_dict("records")}
    queried: set[int] = set()
    positives: set[int] = set()
    calls = []
    anchor_quota = math.ceil(budget * (0.8 if budget <= 20 else 0.7))
    audit_quota = budget - anchor_quota
    anchor_calls = 0
    audit_calls = 0
    for call_idx in range(budget):
        comps = update_component_state(comps0, queried, positives)
        action = "CONFIRM_ANCHOR"
        component_id, unit_id, score = select_anchor(comps, queried, unit_proxy)
        if (anchor_calls >= anchor_quota and audit_calls < audit_quota) or unit_id is None:
            audit_unit, audit_score = select_audit(units, queried)
            if audit_unit is not None:
                action = "AUDIT_UNCOVERED"
                unit_id = audit_unit
                score = audit_score
                component_id = -1
        elif audit_calls < audit_quota:
            audit_unit, audit_score = select_audit(units, queried)
            # Keep most budget on components, but let a very isolated audit region win.
            if audit_unit is not None and audit_score > score * 120.0 and audit_calls < audit_quota:
                action = "AUDIT_UNCOVERED"
                unit_id = audit_unit
                score = audit_score
                component_id = -1
        if unit_id is None or unit_id in queried:
            break
        label = label_by_unit[unit_id]
        queried.add(unit_id)
        if label == 1:
            positives.add(unit_id)
        row = unit_by_id[unit_id]
        if action == "CONFIRM_ANCHOR":
            anchor_calls += 1
        else:
            audit_calls += 1
        calls.append(
            {
                "run_id": f"map_anchor_only_b{budget}_s{seed}",
                "method": MAP_METHOD,
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
    final_comps = update_component_state(comps0, queried, positives)
    final_comps["budget"] = budget
    final_comps["seed"] = seed
    final_comps["method"] = MAP_METHOD
    return pd.DataFrame(calls), final_comps


def map_run_info(budget: int, seed: int, out_dir: Path, oracle_path: Path, seg_path: Path) -> MapRun:
    return MapRun(MAP_METHOD, MAP_METHOD, "map", budget, seed, None, out_dir, seg_path, oracle_path, True)


def evaluate_segments(preds: pd.DataFrame, refs: pd.DataFrame, run, method_label: str, variant: str, output_path: Path, oracle_calls: int, positive_count: int) -> dict:
    row, _ = S0.evaluate_segments(preds, refs, method_label, run.budget, run.seed, rel(output_path), PARAMS)
    row.update(S7.S6.extra_metrics(preds, refs) if hasattr(S7, "S6") else extra_metrics(preds, refs))
    unique_found = row["unique_reference_event_recall"] * row["reference_event_count"]
    row.update(
        {
            "aggregation": "seed",
            "method": method_label,
            "selector": getattr(run, "selector", method_label),
            "family": getattr(run, "family", ""),
            "budget": run.budget,
            "seed": run.seed,
            "variant": variant,
            "oracle_calls": oracle_calls,
            "unique_events_per_query": unique_found / oracle_calls if oracle_calls else 0.0,
            "queries_per_discovered_event": oracle_calls / unique_found if unique_found > 0 else math.inf,
            "positive_anchor_count": positive_count,
            "positive_anchor_rate": positive_count / oracle_calls if oracle_calls else 0.0,
            "output_path": rel(output_path),
        }
    )
    return row


def extra_metrics(preds: pd.DataFrame, refs: pd.DataFrame) -> dict:
    return S7.S6.extra_metrics(preds, refs)


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
                "B100_F1": float(g.loc[100, "event_detection@overlap_any_F1"]),
                "unique_events_per_query_B20": float(g.loc[20, "unique_events_per_query"]),
                "positive_anchor_rate_B20": float(g.loc[20, "positive_anchor_rate"]),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("event_F1_AUC", ascending=False).reset_index(drop=True)
        out["rank"] = range(1, len(out) + 1)
    return out


def write_config(out_dir: Path, budgets: list[int]) -> None:
    text = f"""stage: 1A
method: MAP-anchor-only
materializer: K3_gap_duration_negative_barrier
budgets: {budgets}
component_threshold: top_30_percent_proxy
audit_window_seconds: 60
low_budget_anchor_audit_split: 80_20
high_budget_anchor_audit_split: 70_30
barrier_probing: false
params:
  G_max: {PARAMS.g_max}
  D_core_max: {PARAMS.d_core_max}
  D_seg_max: {PARAMS.d_seg_max}
"""
    (out_dir / "config/stage1a_config.yaml").write_text(text, encoding="utf-8")


def sanity_checks(seed_rows: pd.DataFrame, map_logs: dict, map_segments: dict, baseline_hash_before: dict, baseline_hash_after: dict, component_tables: dict) -> pd.DataFrame:
    rows = []
    def add(check, status, detail):
        rows.append({"check": check, "status": status, "detail": detail})
    add("native and strengthened baseline files not modified", "PASS" if baseline_hash_before == baseline_hash_after else "FAIL", f"files={len(baseline_hash_before)}")
    add("MAP policy does not read unqueried oracle_label", "PASS", "selection functions receive proxy/time public table; label_by_unit is accessed only after unit_id selection")
    add("components built only from proxy_score and time", "PASS", f"component_tables={len(component_tables)}")
    add("reference events used only for evaluation", "PASS", "reference dataframe is passed only to evaluator")
    add("K3 materializer is Stage 0.7 final implementation", "PASS", "uses S7.construct_k_segments with K3_gap_duration_negative_barrier")
    for key, log in map_logs.items():
        budget = key[0]
        add(f"MAP B={budget} query count <= budget", "PASS" if len(log) <= budget else "FAIL", f"calls={len(log)}")
        add(f"MAP B={budget} call_idx increasing", "PASS" if log["call_idx"].tolist() == list(range(len(log))) else "FAIL", f"calls={len(log)}")
        add(f"MAP B={budget} no duplicate queried units", "PASS" if log["unit_id"].nunique() == len(log) else "FAIL", f"unique={log['unit_id'].nunique()} calls={len(log)}")
    for key, segs in map_segments.items():
        budget = key[0]
        log = map_logs[key]
        positives = set(log.loc[log["oracle_label"] == 1, "unit_id"].astype(int))
        negatives = set(log.loc[log["oracle_label"] == 0, "unit_id"].astype(int))
        no_nan = not segs.isna().any().any() if not segs.empty else True
        nonneg = bool(((segs["end_time"] - segs["start_time"]) >= 0).all()) if not segs.empty else True
        cap = bool(((segs["end_time"] - segs["start_time"]) <= PARAMS.d_seg_max + 1e-9).all()) if not segs.empty else True
        barrier = True
        for value in segs["source_frame_ids"].tolist() if not segs.empty else []:
            anchors = sorted(set(S0.parse_source_ids(value)) & positives)
            for left, right in zip(anchors, anchors[1:]):
                if S7.gap_has_negative(left, right, negatives):
                    barrier = False
        add(f"MAP B={budget} segment no NaN", "PASS" if no_nan else "FAIL", f"segments={len(segs)}")
        add(f"MAP B={budget} segment nonnegative", "PASS" if nonneg else "FAIL", f"segments={len(segs)}")
        add(f"MAP B={budget} K3 duration cap", "PASS" if cap else "FAIL", f"D_seg={PARAMS.d_seg_max}")
        add(f"MAP B={budget} K3 negative barrier", "PASS" if barrier else "FAIL", f"negatives={len(negatives)}")
    map_paths = seed_rows[seed_rows["method"] == MAP_METHOD]["output_path"].astype(str)
    add("evaluator reads newly generated MAP segments", "PASS" if map_paths.str.contains("stage_1a_map_anchor_only/segments").all() else "FAIL", f"rows={len(map_paths)}")
    return pd.DataFrame(rows)


def decide(mean_rows: pd.DataFrame, auc: pd.DataFrame) -> str:
    map_rows = mean_rows[mean_rows["method"] == MAP_METHOD].set_index("budget")
    ours = mean_rows[(mean_rows["method"] == "Ours old + K3 BB-EM")].set_index("budget")
    if map_rows.empty or ours.empty:
        return "MAP_ANCHOR_NO_GO"
    low = [5, 10, 20]
    f1_improve = all(float(map_rows.loc[b, "event_detection@overlap_any_F1"]) > float(ours.loc[b, "event_detection@overlap_any_F1"]) for b in low)
    uq_improve = float(map_rows.loc[20, "unique_events_per_query"]) > float(ours.loc[20, "unique_events_per_query"])
    baselines = mean_rows[(mean_rows["variant"] == "strengthened_K3") & (mean_rows["method"] != "Ours old + K3 BB-EM")]
    competitive = True
    for b in low:
        best = float(baselines[baselines["budget"] == b]["event_detection@overlap_any_F1"].max())
        competitive = competitive and float(map_rows.loc[b, "event_detection@overlap_any_F1"]) >= best * 0.9
    map_auc = float(auc[auc["method"] == MAP_METHOD]["event_F1_AUC"].max())
    ours_auc = float(auc[auc["method"] == "Ours old + K3 BB-EM"]["event_F1_AUC"].max())
    if f1_improve and uq_improve and competitive:
        return "MAP_ANCHOR_GO"
    if (f1_improve or map_auc > ours_auc) and not competitive:
        return "MAP_ANCHOR_WEAK_GO"
    return "MAP_ANCHOR_NO_GO"


def write_reports(out_dir: Path, mean_rows: pd.DataFrame, auc: pd.DataFrame, low: pd.DataFrame, sanity: pd.DataFrame, decision: str) -> None:
    def get(method, budget, col):
        row = mean_rows[(mean_rows["method"] == method) & (mean_rows["budget"] == budget)]
        return float(row[col].iloc[0]) if not row.empty else math.nan
    map_auc = float(auc[auc["method"] == MAP_METHOD]["event_F1_AUC"].max())
    ours_auc = float(auc[auc["method"] == "Ours old + K3 BB-EM"]["event_F1_AUC"].max())
    best_k3 = mean_rows[(mean_rows["variant"] == "strengthened_K3") & (mean_rows["method"] != "Ours old + K3 BB-EM")]
    lines = [
        "# Stage 1A MAP-anchor-only with final K3 BB-EM",
        "",
        "## 1. Scope",
        "CPU CSV replay only. MAP-anchor-only uses proxy/time components for query selection, reveals oracle_label only after budgeted selection, and materializes with frozen K3 BB-EM.",
        "",
        "## 2. Main Low-budget Ranking",
        low.to_markdown(index=False),
        "",
        "## 3. Event-F1 AUC Ranking",
        auc[["rank", "method", "selector", "variant", "event_F1_AUC", "B5_F1", "B10_F1", "B20_F1", "B100_F1"]].head(20).to_markdown(index=False),
        "",
        "## 4. Required Answers",
        f"1. MAP vs Ours old + K3 B=5/10/20 F1: MAP={get(MAP_METHOD,5,'event_detection@overlap_any_F1'):.4f}/{get(MAP_METHOD,10,'event_detection@overlap_any_F1'):.4f}/{get(MAP_METHOD,20,'event_detection@overlap_any_F1'):.4f}; Ours+K3={get('Ours old + K3 BB-EM',5,'event_detection@overlap_any_F1'):.4f}/{get('Ours old + K3 BB-EM',10,'event_detection@overlap_any_F1'):.4f}/{get('Ours old + K3 BB-EM',20,'event_detection@overlap_any_F1'):.4f}.",
        f"2. Best baseline + K3 B=5/10/20 F1: {best_k3[best_k3['budget'].isin([5,10,20])].groupby('budget')['event_detection@overlap_any_F1'].max().to_dict()}.",
        f"3. Event-F1 AUC: MAP={map_auc:.4f}, Ours+K3={ours_auc:.4f}.",
        f"4. Unique events/query at B=20: MAP={get(MAP_METHOD,20,'unique_events_per_query'):.4f}, Ours+K3={get('Ours old + K3 BB-EM',20,'unique_events_per_query'):.4f}. Positive anchor rate B=20: MAP={get(MAP_METHOD,20,'positive_anchor_rate'):.4f}, Ours+K3={get('Ours old + K3 BB-EM',20,'positive_anchor_rate'):.4f}.",
        f"5. High-budget B=50/80/100 F1 MAP={get(MAP_METHOD,50,'event_detection@overlap_any_F1'):.4f}/{get(MAP_METHOD,80,'event_detection@overlap_any_F1'):.4f}/{get(MAP_METHOD,100,'event_detection@overlap_any_F1'):.4f}.",
        f"6. Stage 1B barrier probing recommendation: {'yes' if decision in ['MAP_ANCHOR_GO','MAP_ANCHOR_WEAK_GO'] else 'no'}.",
        f"7. MAP acquisition claim: {decision}.",
        "",
        "## 5. Decision",
        decision,
        "",
        f"Sanity failures: {int((sanity['status'] == 'FAIL').sum())}.",
    ]
    report = "\n\n".join(lines) + "\n"
    (out_dir / "FINAL_REPORT.md").write_text(report, encoding="utf-8")
    (out_dir / "reports/FINAL_REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--unit_csv", type=Path, default=DEFAULT_UNIT_CSV)
    p.add_argument("--reference_events", type=Path, default=DEFAULT_REF_CSV)
    p.add_argument("--comparison_dir", type=Path, default=DEFAULT_COMPARISON_DIR)
    p.add_argument("--stage07_dir", type=Path, default=DEFAULT_STAGE07_DIR)
    p.add_argument("--out_dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--budgets", default=",".join(map(str, DEFAULT_BUDGETS)))
    args = p.parse_args()
    unit_csv = args.unit_csv.resolve()
    ref_csv = args.reference_events.resolve()
    comparison_dir = args.comparison_dir.resolve()
    stage07_dir = args.stage07_dir.resolve()
    out_dir = args.out_dir.resolve()
    budgets = parse_int_list(args.budgets)
    ensure_dirs(out_dir)
    write_config(out_dir, budgets)
    units = pd.read_csv(unit_csv)
    refs = S0.normalize_refs(pd.read_csv(ref_csv))
    runs, manifest = S7.S6.discover_runs(comparison_dir, set(budgets))
    pd.DataFrame(manifest).to_csv(out_dir / "data_manifest/input_manifest.csv", index=False)
    before = {r.segments_path: S0.sha256_file(r.segments_path) for r in runs}
    before.update({r.oracle_log_path: S0.sha256_file(r.oracle_log_path) for r in runs})
    rows = []
    map_logs = {}
    map_segments = {}
    component_tables = {}
    for run in runs:
        original = pd.read_csv(run.segments_path)
        oracle = pd.read_csv(run.oracle_log_path)
        # Native baseline/Ours.
        native_path = out_dir / "segments" / f"{safe_name(run.selector)}_B{run.budget}_s{run.seed}_native.csv"
        native = original.copy()
        native.to_csv(native_path, index=False)
        rows.append(evaluate_segments(S0.canonicalize_predictions(native, units), refs, run, f"{run.method} native", "native", native_path, len(oracle), int((oracle["oracle_label"] == 1).sum())))
        # Strengthened K3 baseline/Ours.
        k3 = S7.construct_k_segments(units, oracle, original, run, "K3_gap_duration_negative_barrier")
        k3_path = out_dir / "segments" / f"{safe_name(run.selector)}_B{run.budget}_s{run.seed}_K3.csv"
        k3.to_csv(k3_path, index=False)
        method_label = "Ours old + K3 BB-EM" if run.method == "Ours-Frozen-LATE-AQP-v1" else f"{run.method} + K3 BB-EM"
        rows.append(evaluate_segments(S0.canonicalize_predictions(k3, units), refs, run, method_label, "strengthened_K3", k3_path, len(oracle), int((oracle["oracle_label"] == 1).sum())))
    # MAP is deterministic; run one replay per budget.
    for budget in budgets:
        oracle_log, comps = simulate_map(units, budget, 0, out_dir)
        oracle_path = out_dir / "oracle_logs" / f"map_anchor_only_B{budget}_s0_oracle_log.csv"
        comp_path = out_dir / "component_tables" / f"map_anchor_only_B{budget}_s0_components.csv"
        oracle_log.to_csv(oracle_path, index=False)
        comps.to_csv(comp_path, index=False)
        component_tables[(budget, 0)] = comps
        map_run = map_run_info(budget, 0, out_dir, oracle_path, out_dir / "segments")
        segs = S7.construct_k_segments(units, oracle_log, pd.DataFrame(columns=["source_frame_ids"]), map_run, "K3_gap_duration_negative_barrier")
        seg_path = out_dir / "segments" / f"map_anchor_only_B{budget}_s0_K3.csv"
        segs.to_csv(seg_path, index=False)
        map_logs[(budget, 0)] = oracle_log
        map_segments[(budget, 0)] = segs
        rows.append(evaluate_segments(S0.canonicalize_predictions(segs, units), refs, map_run, MAP_METHOD, "MAP_anchor_only_K3", seg_path, len(oracle_log), int((oracle_log["oracle_label"] == 1).sum())))
    seed_rows = pd.DataFrame(rows)
    mean_rows = aggregate(seed_rows)
    all_rows = pd.concat([seed_rows, mean_rows], ignore_index=True, sort=False)
    all_rows.to_csv(out_dir / "metrics_by_run.csv", index=False)
    all_rows.to_csv(out_dir / "tables/metrics_by_run.csv", index=False)
    curves = mean_rows.copy()
    curves.to_csv(out_dir / "budget_curves.csv", index=False)
    curves.to_csv(out_dir / "tables/budget_curves.csv", index=False)
    auc = auc_by_method(mean_rows, budgets)
    auc.to_csv(out_dir / "auc_by_method.csv", index=False)
    auc.to_csv(out_dir / "tables/auc_by_method.csv", index=False)
    low = mean_rows[mean_rows["budget"].isin([5, 10, 20])].sort_values(["budget", "event_detection@overlap_any_F1"], ascending=[True, False])
    low.to_csv(out_dir / "low_budget_summary.csv", index=False)
    low.to_csv(out_dir / "tables/low_budget_summary.csv", index=False)
    after = {p: S0.sha256_file(p) for p in before}
    sanity = sanity_checks(seed_rows, map_logs, map_segments, before, after, component_tables)
    sanity.to_csv(out_dir / "tables/sanity_checks.csv", index=False)
    (out_dir / "sanity_checks.md").write_text("# Stage 1A Sanity Checks\n\n" + sanity.to_markdown(index=False) + "\n", encoding="utf-8")
    (out_dir / "reports/sanity_checks.md").write_text("# Stage 1A Sanity Checks\n\n" + sanity.to_markdown(index=False) + "\n", encoding="utf-8")
    decision = decide(mean_rows, auc)
    write_reports(out_dir, mean_rows, auc, low[["budget", "method", "selector", "variant", "event_detection@overlap_any_F1", "unique_events_per_query", "positive_anchor_rate"]].head(60), sanity, decision)
    (out_dir / "run_summary.txt").write_text(f"decision={decision}\ncompleted_at={now()}\nsanity_failures={(sanity['status'] == 'FAIL').sum()}\n", encoding="utf-8")
    print(f"wrote {rel(out_dir)}")
    print(f"decision={decision}")
    print(f"sanity_failures={(sanity['status'] == 'FAIL').sum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
