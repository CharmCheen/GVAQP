"""Strengthened, shared-operator baseline evaluation for VERA.

All physical-order comparisons reuse the exact frozen EVENT_ENUMERATE outputs;
only the public ordering policy changes.  Native strict-baseline results remain
separate because their query object is 10-second UNIT_PRESENCE, not an event
enumeration relation fragment.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .contract import reconcile_owned_fragments
from .evaluate_physical import (
    _benchmark_module,
    _complete_results,
    _dense_fallback_segments,
    _enumeration_fragments,
    _evaluate,
    _metric_dict,
    _segments,
)
from .physical_common import PACKAGE, PHYSICAL, ROOT, STRICT, atomic_text, load_json, verify_freeze


DARE = ROOT / "DARE_AQP_Experiment_v1/outputs/gate_a_final"
BUDGET_GRID = [5, 10, 20, 50, 80, 100]


def _unit_order_from_csv(path: Path) -> list[int]:
    frame = pd.read_csv(path).sort_values("rank")
    return frame.unit_id.astype(int).tolist()


def _selected_unit_order(
    table: pd.DataFrame,
    method: str,
    variant: str,
    seed: int,
    all_units: list[int],
) -> list[int]:
    subset = table[
        (table.method == method)
        & (table.method_variant == variant)
        & (table.seed == seed)
    ]
    if subset.empty:
        raise RuntimeError(f"missing selected-unit order: {method}/{variant}/seed={seed}")
    horizon = int(subset.horizon_budget.max())
    observed = subset[subset.horizon_budget == horizon].sort_values("call_idx").unit_id.astype(int).tolist()
    unique = list(dict.fromkeys(observed))
    return unique + [unit_id for unit_id in all_units if unit_id not in set(unique)]


def _window_order_from_units(
    unit_order: list[int],
    enum_tasks: list[dict[str, Any]],
    units: pd.DataFrame,
) -> list[str]:
    rank = {unit_id: index for index, unit_id in enumerate(unit_order)}
    scored = []
    for task in enum_tasks:
        mask = (units.start_time < float(task["core_end"])) & (units.end_time > float(task["core_start"]))
        owned_units = units.loc[mask, "unit_id"].astype(int).tolist()
        first = min(rank.get(unit_id, len(rank) + unit_id) for unit_id in owned_units)
        scored.append((first, float(task["core_start"]), task["window_id"]))
    return [window_id for _, _, window_id in sorted(scored)]


def _curve_for_order(
    name: str,
    seed: int,
    order: list[str],
    result_by_window: dict[str, dict[str, Any]],
    benchmark: Any,
    reference: pd.DataFrame,
    units: pd.DataFrame,
    timeline_end: float,
    fallback_fragments: list[dict[str, Any]],
    fallback_results: list[dict[str, Any]],
) -> pd.DataFrame:
    fragments: list[dict[str, Any]] = []
    cumulative_gpu = 0.0
    rows = []
    for index, window_id in enumerate(order, 1):
        result = result_by_window[window_id]
        cumulative_gpu += float(result.get("decision_gpu_seconds") or 0.0)
        fragments.extend(_enumeration_fragments([result], timeline_end, ownership=True))
        predicted = _segments(reconcile_owned_fragments(fragments), units, f"{name}_s{seed}_{index}")
        _, metrics = _evaluate(benchmark, predicted, reference, f"{name}_s{seed}_{index}")
        values = _metric_dict(metrics)
        rows.append({
            "method": name,
            "seed": seed,
            "prefix_calls": index,
            "last_window_id": window_id,
            "cumulative_gpu_seconds": cumulative_gpu,
            "event_precision": values["event_precision"],
            "event_recall": values["event_recall"],
            "event_f1": values["event_f1"],
            "predicted_event_count": values["predicted_event_count"],
        })
    if fallback_results:
        cumulative_gpu += sum(float(row.get("decision_gpu_seconds") or 0.0) for row in fallback_results)
        predicted = _segments(
            reconcile_owned_fragments(fragments) + fallback_fragments,
            units,
            f"{name}_s{seed}_with_fallback",
        )
        _, metrics = _evaluate(benchmark, predicted, reference, f"{name}_s{seed}_with_fallback")
        values = _metric_dict(metrics)
        rows.append({
            "method": name,
            "seed": seed,
            "prefix_calls": len(order) + len(fallback_results),
            "last_window_id": "DENSE_FALLBACK_COMPLETE",
            "cumulative_gpu_seconds": cumulative_gpu,
            "event_precision": values["event_precision"],
            "event_recall": values["event_recall"],
            "event_f1": values["event_f1"],
            "predicted_event_count": values["predicted_event_count"],
        })
    return pd.DataFrame(rows)


def _same_cost_summary(curves: pd.DataFrame, dense_median_gpu: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    point_rows = []
    summary_rows = []
    for (method, seed), group in curves.groupby(["method", "seed"]):
        group = group.sort_values("cumulative_gpu_seconds")
        seed_points = []
        for budget in BUDGET_GRID:
            eligible = group[group.cumulative_gpu_seconds <= budget * dense_median_gpu + 1e-12]
            row = eligible.iloc[-1] if not eligible.empty else None
            point = {
                "method": method,
                "seed": seed,
                "dense_equivalent_unit_budget": budget,
                "event_f1": float(row.event_f1) if row is not None else 0.0,
                "event_recall": float(row.event_recall) if row is not None else 0.0,
                "actual_gpu_seconds": float(row.cumulative_gpu_seconds) if row is not None else 0.0,
                "physical_calls": int(row.prefix_calls) if row is not None else 0,
            }
            seed_points.append(point)
            point_rows.append(point)
        points = pd.DataFrame(seed_points)
        auc = float(
            np.trapezoid(points.event_f1, points.dense_equivalent_unit_budget)
            / (max(BUDGET_GRID) - min(BUDGET_GRID))
        )
        final = group.iloc[-1]
        row = {
            "method": method,
            "seed": seed,
            "same_cost_event_f1_auc": auc,
            "full_event_precision": float(final.event_precision),
            "full_event_recall": float(final.event_recall),
            "full_event_f1": float(final.event_f1),
            "full_gpu_seconds": float(final.cumulative_gpu_seconds),
            "full_physical_calls": int(final.prefix_calls),
        }
        for threshold in [0.5, 0.8, 0.9]:
            reached = group[group.event_recall >= threshold]
            row[f"calls_to_recall_{int(threshold*100)}"] = int(reached.iloc[0].prefix_calls) if not reached.empty else math.nan
            row[f"gpu_to_recall_{int(threshold*100)}"] = float(reached.iloc[0].cumulative_gpu_seconds) if not reached.empty else math.nan
        summary_rows.append(row)
    return pd.DataFrame(point_rows), pd.DataFrame(summary_rows)


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, group in summary.groupby("method"):
        row = {"method": method, "seeds": len(group)}
        for column in [
            "same_cost_event_f1_auc", "full_event_precision", "full_event_recall",
            "full_event_f1", "full_gpu_seconds", "full_physical_calls",
            "calls_to_recall_50", "gpu_to_recall_50", "calls_to_recall_80",
            "gpu_to_recall_80", "calls_to_recall_90", "gpu_to_recall_90",
        ]:
            values = group[column].astype(float)
            row[f"{column}_mean"] = float(values.mean()) if values.notna().any() else math.nan
            row[f"{column}_std"] = float(values.std(ddof=0)) if values.notna().any() else math.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values("same_cost_event_f1_auc_mean", ascending=False)


def _native_baselines(dense_median_gpu: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranking = pd.read_csv(STRICT / "baselines/baseline_rankings.csv")
    chosen = [
        ("native_ARC", "B5_ARC_native", "arc_refinement_th0.4_native"),
        ("random_uniform", "B0_uniform_random", "random_native_confirmed"),
        ("public_proxy", "B1_top_proxy", "top_proxy_native_confirmed"),
        ("SUPG_adapted", "B4_SUPG_adapted", "supg_confirmed_only_native"),
        ("ABae_adapted", "B6_ABae_adapted_diagnostic", "abae_stratified_native"),
    ]
    rows = []
    for label, method, variant in chosen:
        item = ranking[(ranking.method == method) & (ranking.method_variant == variant)].iloc[0]
        rows.append({
            "comparison": label,
            "query_object": "10-second UNIT_PRESENCE then event materialization",
            "event_f1_auc": float(item.event_f1_auc),
            "auc_budget_grid": "5|10|20|50|80|100 dense-unit calls",
            "physical_cost_basis": "existing physical labels; current-A100 cost rescaled",
            "deployable": True,
        })
    current = pd.read_csv(STRICT / "current_method/current_budget_curves.csv")
    m1 = current[current.method_variant == "K3_BRIDGE_SAFE"].sort_values("horizon_budget")
    map_auc = float(np.trapezoid(m1.event_f1, m1.horizon_budget) / (m1.horizon_budget.max() - m1.horizon_budget.min()))
    rows.append({
        "comparison": "MAP_M1", "query_object": "10-second UNIT_PRESENCE then K3-safe",
        "event_f1_auc": map_auc, "auc_budget_grid": "5|10|20|50|80|100 dense-unit calls",
        "physical_cost_basis": "existing physical labels; current-A100 cost rescaled", "deployable": True,
    })
    dare_auc = pd.read_csv(DARE / "evaluation/event_f1_auc.csv")
    clip_auc = float(dare_auc.loc[dare_auc.signal_id == "image_text", "event_f1_auc"].iloc[0])
    rows.append({
        "comparison": "CLIP_retrieve_then_ground", "query_object": "CLIP unit retrieval then K3-safe",
        "event_f1_auc": clip_auc, "auc_budget_grid": "5|10|20|50|80|100 dense-unit calls",
        "physical_cost_basis": "378.93s cold CLIP index plus exact-unit calls", "deployable": True,
    })
    rows.extend([
        {
            "comparison": "dense_10s_Qwen3VL", "query_object": "all 347 UNIT_PRESENCE calls",
            "event_f1_auc": math.nan, "auc_budget_grid": "full endpoint only",
            "physical_cost_basis": f"347 * {dense_median_gpu:.6f}s current-A100 median", "deployable": True,
        },
        {
            "comparison": "evaluator_only_oracle", "query_object": "hindsight reference ordering",
            "event_f1_auc": 0.919626, "auc_budget_grid": "5|10|20|50|80|100",
            "physical_cost_basis": "ceiling; not deployable", "deployable": False,
        },
    ])
    native = pd.DataFrame(rows)

    curves = []
    summary = pd.read_csv(STRICT / "baselines/baseline_summary.csv")
    for label, method, variant in chosen:
        subset = summary[(summary.method == method) & (summary.method_variant == variant)]
        for row in subset.itertuples():
            curves.append({
                "method": label, "budget": int(row.horizon_budget),
                "estimated_gpu_seconds": int(row.horizon_budget) * dense_median_gpu,
                "event_precision": float(row.event_precision_mean),
                "event_recall": float(row.event_recall_mean),
                "event_f1": float(row.event_f1_mean),
                "source": "strict_native_baseline",
            })
    for row in m1.itertuples():
        curves.append({
            "method": "MAP_M1", "budget": int(row.horizon_budget),
            "estimated_gpu_seconds": int(row.horizon_budget) * dense_median_gpu,
            "event_precision": float(row.event_precision), "event_recall": float(row.event_recall),
            "event_f1": float(row.event_f1), "source": "strict_current_method",
        })
    clip = pd.read_csv(DARE / "evaluation/per_budget_event_metrics.csv")
    clip = clip[clip.signal_id == "image_text"]
    for row in clip.itertuples():
        curves.append({
            "method": "CLIP_retrieve_then_ground", "budget": int(row.budget),
            "estimated_gpu_seconds": int(row.budget) * dense_median_gpu,
            "event_precision": float(row.event_precision), "event_recall": float(row.event_recall),
            "event_f1": float(row.event_f1), "source": "DARE_gate_A",
        })
    curves.extend([
        {
            "method": "dense_10s_Qwen3VL", "budget": 347,
            "estimated_gpu_seconds": 347 * dense_median_gpu,
            "event_precision": 1.0, "event_recall": 1.0, "event_f1": 1.0,
            "source": "reference_defining_dense_endpoint",
        },
    ])
    return native, pd.DataFrame(curves)


def _pareto(points: pd.DataFrame) -> pd.DataFrame:
    out = points.copy()
    flags = []
    for row in out.itertuples():
        dominated = ((out.estimated_gpu_seconds <= row.estimated_gpu_seconds + 1e-12)
                     & (out.event_f1 >= row.event_f1 - 1e-12)
                     & ((out.estimated_gpu_seconds < row.estimated_gpu_seconds - 1e-12)
                        | (out.event_f1 > row.event_f1 + 1e-12))).any()
        flags.append(not bool(dominated))
    out["pareto_optimal"] = flags
    return out.sort_values(["estimated_gpu_seconds", "event_f1"])


def evaluate() -> None:
    config = verify_freeze()
    if not (PHYSICAL / "PHYSICAL_DECISION.json").exists():
        raise RuntimeError("run evaluate_physical before strengthened baselines")
    (PACKAGE / "baselines").mkdir(parents=True, exist_ok=True)
    (PACKAGE / "results").mkdir(parents=True, exist_ok=True)
    sample = load_json(PHYSICAL / "SAMPLE_MANIFEST.json")
    units = pd.read_csv(STRICT / "frozen_inputs/unit_table.csv")
    reference = pd.read_csv(STRICT / "frozen_inputs/event_reference.csv")
    results = _complete_results()
    enum_results = [r for r in results if r.get("operator") == "EVENT_ENUMERATE"]
    if len(enum_results) != 70:
        raise RuntimeError(f"expected 70 enumeration outputs, got {len(enum_results)}")
    result_by_window = {r["task"]["window_id"]: r for r in enum_results}
    fallback_results = [r for r in results if r.get("operator") == "DENSE_UNIT_FALLBACK"]
    fallback_fragments = _dense_fallback_segments(results, units)
    enum_tasks = [x for x in sample["execution_order"] if x["operator"] == "EVENT_ENUMERATE"]
    all_units = units.unit_id.astype(int).tolist()
    selected = pd.read_csv(STRICT / "baselines/baseline_selected_units.csv")
    current = pd.read_csv(STRICT / "current_method/current_selected_units.csv")

    orders: list[tuple[str, int, list[str]]] = []
    orders.append(("VERA_chronological", 0, [x["window_id"] for x in enum_tasks]))
    public_order = _unit_order_from_csv(DARE / "sealed_rankings/current_proxy.csv")
    clip_order = _unit_order_from_csv(DARE / "sealed_rankings/image_text.csv")
    orders.append(("public_proxy_plus_EVENT_ENUMERATE", 0, _window_order_from_units(public_order, enum_tasks, units)))
    orders.append(("CLIP_RTG_plus_EVENT_ENUMERATE", 0, _window_order_from_units(clip_order, enum_tasks, units)))
    map_units = _selected_unit_order(current, "M1_MAP_anchor_only", "K3_BRIDGE_SAFE", 0, all_units)
    orders.append(("MAP_M1_plus_EVENT_ENUMERATE", 0, _window_order_from_units(map_units, enum_tasks, units)))
    for seed in range(5):
        for name, method, variant in [
            ("ARC_plus_EVENT_ENUMERATE", "B5_ARC_native", "arc_refinement_th0.4_native"),
            ("SUPG_plus_EVENT_ENUMERATE", "B4_SUPG_adapted", "supg_confirmed_only_native"),
            ("ABae_plus_EVENT_ENUMERATE", "B6_ABae_adapted_diagnostic", "abae_stratified_native"),
        ]:
            unit_order = _selected_unit_order(selected, method, variant, seed, all_units)
            orders.append((name, seed, _window_order_from_units(unit_order, enum_tasks, units)))
    for seed in range(100):
        rng = np.random.default_rng(20260711 + seed)
        window_order = [x["window_id"] for x in enum_tasks]
        rng.shuffle(window_order)
        orders.append(("uniform_random_plus_EVENT_ENUMERATE", seed, window_order))
    event_counts = []
    for task in enum_tasks:
        count = int(((reference.canonical_anchor_time >= task["core_start"])
                     & (reference.canonical_anchor_time < task["core_end"])).sum())
        event_counts.append((-count, task["core_start"], task["window_id"]))
    orders.append(("EVALUATOR_ORACLE_plus_EVENT_ENUMERATE", 0, [x[2] for x in sorted(event_counts)]))

    benchmark = _benchmark_module()
    timeline_end = float(config["video"]["duration_seconds"])
    curves = pd.concat([
        _curve_for_order(
            name, seed, order, result_by_window, benchmark, reference, units, timeline_end,
            fallback_fragments, fallback_results,
        )
        for name, seed, order in orders
    ], ignore_index=True)
    curves.to_csv(PACKAGE / "baselines/SHARED_OPERATOR_PREFIX_CURVES.csv", index=False)
    ledger = pd.read_csv(PHYSICAL / "CALL_LEDGER.csv")
    dense_median_gpu = float(
        ledger.loc[ledger.operator == "DENSE_UNIT_CALIBRATION", "decision_gpu_seconds"].median()
    )
    points, per_seed = _same_cost_summary(curves, dense_median_gpu)
    aggregate = _aggregate(per_seed)
    points.to_csv(PACKAGE / "baselines/SHARED_OPERATOR_SAME_COST_GRID.csv", index=False)
    per_seed.to_csv(PACKAGE / "baselines/SHARED_OPERATOR_PER_SEED.csv", index=False)
    aggregate.to_csv(PACKAGE / "baselines/STRENGTHENED_BASELINE_COMPARISON.csv", index=False)

    native, native_curves = _native_baselines(dense_median_gpu)
    native.to_csv(PACKAGE / "baselines/NATIVE_QUERY_OBJECT_COMPARISON.csv", index=False)
    native_curves.to_csv(PACKAGE / "baselines/NATIVE_COST_CURVES.csv", index=False)
    vera_points = curves[curves.method == "VERA_chronological"].copy()
    vera_points = vera_points.rename(columns={"cumulative_gpu_seconds": "estimated_gpu_seconds"})
    vera_points["budget"] = vera_points.prefix_calls
    vera_points["source"] = "new_physical_EVENT_ENUMERATE"
    pareto_inputs = pd.concat([
        native_curves[["method", "budget", "estimated_gpu_seconds", "event_precision", "event_recall", "event_f1", "source"]],
        vera_points[["method", "budget", "estimated_gpu_seconds", "event_precision", "event_recall", "event_f1", "source"]],
    ], ignore_index=True)
    _pareto(pareto_inputs).to_csv(PACKAGE / "results/PARETO_FRONTIER.csv", index=False)

    physical_decision = load_json(PHYSICAL / "PHYSICAL_DECISION.json")
    vera = aggregate[aggregate.method == "VERA_chronological"].iloc[0]
    deployable = aggregate[~aggregate.method.str.startswith("EVALUATOR_")]
    best_auc = float(deployable.same_cost_event_f1_auc_mean.max())
    tied = deployable[np.isclose(deployable.same_cost_event_f1_auc_mean, best_auc)].method.tolist()
    best_deployable = deployable.iloc[0]
    best_label = "ALL_DEPLOYABLE_TIED" if len(tied) == len(deployable) else "|".join(tied)
    report = f"""# Strengthened baseline evaluation

Two comparisons are intentionally separated. Native ARC/SUPG/ABae/MAP/CLIP rows retain their frozen 10-second `UNIT_PRESENCE` query object. The shared-operator experiment instead reorders the exact same 70 physical `EVENT_ENUMERATE` outputs, making physical costs and relation composition identical at full coverage.

VERA chronological has same-cost event-F1 AUC `{vera.same_cost_event_f1_auc_mean:.6f}`, full event F1 `{vera.full_event_f1_mean:.6f}`, and full GPU cost `{vera.full_gpu_seconds_mean:.3f}` seconds. The best deployable shared-operator label is `{best_label}` at `{best_auc:.6f}`; tied methods are `{ '|'.join(tied) }`. The fallback stage is appended identically after all 70 enumeration windows. This ordering result is diagnostic: VERA's claimed novelty is the variable-resolution relation-cover operator plan, not a new relevance ranker.

Native frozen AUCs remain: ARC `{float(native.loc[native.comparison == 'native_ARC', 'event_f1_auc'].iloc[0]):.6f}`, MAP/M1 `{float(native.loc[native.comparison == 'MAP_M1', 'event_f1_auc'].iloc[0]):.6f}`, CLIP retrieve-then-ground `{float(native.loc[native.comparison == 'CLIP_retrieve_then_ground', 'event_f1_auc'].iloc[0]):.6f}`, SUPG-adapted `{float(native.loc[native.comparison == 'SUPG_adapted', 'event_f1_auc'].iloc[0]):.6f}`, and ABae-adapted `{float(native.loc[native.comparison == 'ABae_adapted', 'event_f1_auc'].iloc[0]):.6f}`. These AUCs are not silently equated with the shared-operator AUC; both use the same six dense-equivalent budget points, but the physical query objects differ.

The evaluator-oracle order is explicitly nondeployable. Physical pilot gate: `{physical_decision['physical_gate']}`.
"""
    atomic_text(PACKAGE / "baselines/BASELINE_REPORT.md", report)
    print(json.dumps({
        "shared_operator_methods": int(aggregate.method.nunique()),
        "shared_operator_runs": int(len(per_seed)),
        "vera_same_cost_auc": float(vera.same_cost_event_f1_auc_mean),
        "best_deployable": best_label,
    }, indent=2))


if __name__ == "__main__":
    evaluate()
