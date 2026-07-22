#!/usr/bin/env python3
"""Run the frozen DASR gate on two disjoint, prospectively CLIP-scored intervals."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
PROTOCOL = PACKAGE / "config" / "frozen_continuation_v3.json"
EXPECTED_PROTOCOL_SHA256 = "5fad1ac9b59430d9d19363c66c55001d33b5da9fc1c56552081d611336ee61ef"


def import_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G = import_script("bsec_gate_v1", PACKAGE / "scripts" / "run_frozen_gate.py")
C = import_script("bsec_gate_v2", PACKAGE / "scripts" / "run_continuation_gate.py")


def stratum_winners(scores: np.ndarray, budget: int, multiplier: float = 1.5) -> list[int]:
    n_units = len(scores)
    n_cells = min(n_units, max(budget, int(round(multiplier * budget))))
    candidates = []
    for cell in range(n_cells):
        lo = n_units * cell // n_cells
        hi = n_units * (cell + 1) // n_cells
        if hi <= lo:
            continue
        candidates.append(max(range(lo, hi), key=lambda unit_id: (scores[unit_id], -unit_id)))
    return sorted(candidates, key=lambda unit_id: (-scores[unit_id], unit_id))[:budget]


def exact_fill(primary: list[int], secondary: list[int], budget: int) -> list[int]:
    output = []
    seen = set()
    for source in (primary, secondary):
        for unit_id in source:
            if unit_id in seen:
                continue
            output.append(unit_id)
            seen.add(unit_id)
            if len(output) == budget:
                return output
    raise RuntimeError("selection fill exhausted")


def dasr_selection(scores: np.ndarray, budget: int) -> tuple[list[int], dict]:
    n_units = len(scores)
    nms = G.temporal_nms_ranking(scores, radius=10)
    strata = stratum_winners(scores, budget, multiplier=1.5)
    alpha = n_units / (n_units + 8.0 * budget)
    exploitation = int(round(alpha * budget))
    selection = exact_fill(nms[:exploitation], strata + nms, budget)
    return selection, {
        "population": n_units,
        "budget": budget,
        "alpha": alpha,
        "nms_quota": exploitation,
        "stratum_cells": min(n_units, max(budget, int(round(1.5 * budget)))),
    }


def reference_from_grid(
    name: str, grid: pd.DataFrame, events: pd.DataFrame
) -> pd.DataFrame:
    rows = []
    for _, event in events.iterrows():
        source = grid.loc[grid.event_id.astype(str) == str(event.event_id), "bin_idx"].astype(int)
        rows.append(
            {
                "benchmark_id": f"final_{name}",
                "video_id": "realcartest",
                "reference_event_id": str(event.event_id),
                "start_time": float(event.t_start),
                "core_start_time": float(event.t_start),
                "core_end_time": float(event.t_end),
                "end_time": float(event.t_end),
                "canonical_anchor_time": float(event.t_start),
                "source_unit_ids": "|".join(map(str, source.tolist())),
                "event_type": str(event.event_type),
                "reference_type": "VLM_DEFINED_PSEUDO_ORACLE",
                "reference_version": "late_aqp_frozen_cross_segment_v1",
                "adjudication_status": "not_human_adjudicated",
            }
        )
    return pd.DataFrame(rows)


def load_interval(spec: dict, root: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    grid_path = REPO / spec["units_and_oracle"]
    reference_path = REPO / spec["reference"]
    if G.sha256_file(grid_path) != spec["units_and_oracle_sha256"]:
        raise RuntimeError(f"grid changed: {spec['name']}")
    if G.sha256_file(reference_path) != spec["reference_sha256"]:
        raise RuntimeError(f"reference changed: {spec['name']}")
    grid = pd.read_csv(grid_path)
    events = pd.read_csv(reference_path)
    if len(grid) != spec["unit_count"] or len(events) != spec["event_count"]:
        raise RuntimeError(f"population mismatch: {spec['name']}")
    if grid.bin_idx.astype(int).tolist() != list(range(len(grid))):
        raise RuntimeError(f"noncontiguous unit IDs: {spec['name']}")
    units = pd.DataFrame(
        {
            "benchmark_id": f"final_{spec['name']}",
            "video_id": "realcartest",
            "unit_id": grid.bin_idx.astype(int),
            "frame_idx": grid.bin_idx.astype(int),
            "start_time": grid.t_start.astype(float),
            "end_time": grid.t_end.astype(float),
        }
    )
    labels = {
        int(row.bin_idx): ("positive" if bool(row.is_positive) else "negative")
        for _, row in grid.iterrows()
    }
    inference = root / spec["name"] / "clip_inference"
    complete = json.loads((inference / "INFERENCE_COMPLETE.json").read_text(encoding="utf-8"))
    if complete["frozen_protocol_sha256"] != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"wrong scorer protocol: {spec['name']}")
    scores = pd.read_csv(inference / "clip_scores.csv").sort_values("unit_id").score.to_numpy(float)
    if len(scores) != len(grid):
        raise RuntimeError(f"score coverage mismatch: {spec['name']}")
    data = {
        "name": spec["name"],
        "benchmark_id": f"final_{spec['name']}",
        "units": units,
        "reference": reference_from_grid(spec["name"], grid, events),
        "labels": labels,
        "scores": scores,
        "proxy_scores": grid.prior_score_max.to_numpy(float),
    }
    return data, grid, events


def evaluate_method(
    data: dict,
    method: str,
    selections: dict[int, list[int]],
    budgets: list[int],
    evaluator_hash: str,
) -> list[dict]:
    rows = []
    for budget in budgets:
        row, _, _, _ = G.evaluate_selection(
            data,
            method,
            "frozen_continuation_v3",
            0,
            budget,
            selections[budget],
            evaluator_hash,
        )
        rows.append(row)
    return rows


def interval_gate(
    spec: dict, data: dict, grid: pd.DataFrame, events: pd.DataFrame, root: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    budgets = [int(value) for value in spec["budgets"]]
    evaluator_hash = G.sha256_file(G.STRICT / "scripts" / "benchmark_lib.py")
    output = root / spec["name"]
    frame_path, reference_path = C.write_adapter_inputs(grid, events, output)
    arc_paths = C.run_arc_adapter(frame_path, reference_path, budgets, output)
    scores = data["scores"]
    clip = G.stable_order(scores)
    nms = G.temporal_nms_ranking(scores, radius=10)
    dasr = {}
    strata = {}
    diagnostics = []
    for budget in budgets:
        dasr[budget], diag = dasr_selection(scores, budget)
        strata[budget] = stratum_winners(scores, budget, multiplier=1.5)
        diagnostics.append({"dataset": spec["name"], **diag})
    rows = []
    rows.extend(evaluate_method(data, "dasr", dasr, budgets, evaluator_hash))
    rows.extend(
        evaluate_method(data, "clip_topk", {b: clip[:b] for b in budgets}, budgets, evaluator_hash)
    )
    rows.extend(
        evaluate_method(
            data, "temporal_nms_h10", {b: nms[:b] for b in budgets}, budgets, evaluator_hash
        )
    )
    rows.extend(evaluate_method(data, "stratified_m1.5", strata, budgets, evaluator_hash))
    shared_arc, native_arc = C.evaluate_arc_curves(
        data, arc_paths, budgets, evaluator_hash
    )
    rows.extend(shared_arc)
    rows.extend(native_arc)
    rows.extend(C.add_random_and_oracle(data, budgets, evaluator_hash))
    per_run = pd.DataFrame(rows)
    summary, auc = G.summarize(per_run, budgets)
    per_run.to_csv(output / "per_budget_runs.csv", index=False)
    summary.to_csv(output / "per_budget_summary.csv", index=False)
    auc.to_csv(output / "event_f1_auc.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(output / "dasr_budget_diagnostics.csv", index=False)
    selection_rows = []
    primary_selections = {
        "dasr": dasr,
        "clip_topk": {budget: clip[:budget] for budget in budgets},
        "temporal_nms_h10": {budget: nms[:budget] for budget in budgets},
        "stratified_m1.5": strata,
    }
    for method, selections in primary_selections.items():
        for budget, selection in selections.items():
            for rank, unit_id in enumerate(selection, 1):
                selection_rows.append(
                    {
                        "dataset": spec["name"],
                        "method": method,
                        "seed": 0,
                        "budget": budget,
                        "selection_rank": rank,
                        "unit_id": unit_id,
                        "clip_score": scores[unit_id],
                        "oracle_label_after_query": data["labels"][unit_id],
                    }
                )
    proxy_order = G.stable_order(data["proxy_scores"])
    for (seed, budget), run_dir in sorted(arc_paths.items()):
        log = pd.read_csv(run_dir / "oracle_log.csv")
        selection = log.sort_values("call_idx").unit_id.astype(int).tolist()
        seen = set(selection)
        selection.extend(unit_id for unit_id in proxy_order if unit_id not in seen)
        for rank, unit_id in enumerate(selection[:budget], 1):
            selection_rows.append(
                {
                    "dataset": spec["name"],
                    "method": "arc_shared_k3",
                    "seed": seed,
                    "budget": budget,
                    "selection_rank": rank,
                    "unit_id": unit_id,
                    "clip_score": scores[unit_id],
                    "oracle_label_after_query": data["labels"][unit_id],
                }
            )
    pd.DataFrame(selection_rows).to_csv(output / "primary_selections.csv", index=False)
    return per_run, summary, auc, pd.DataFrame(diagnostics)


def fitting_replay(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    old = json.loads(G.FROZEN.read_text(encoding="utf-8"))
    datasets = [G.load_development(old), G.load_heldout(old)]
    confirm_config = json.loads(C.PROTOCOL.read_text(encoding="utf-8"))
    confirm, _, _ = C.load_confirmatory(
        confirm_config, PACKAGE / "outputs" / "confirmatory"
    )
    datasets.append(confirm)
    budgets = [5, 10, 20, 50, 80, 100]
    evaluator_hash = G.sha256_file(G.STRICT / "scripts" / "benchmark_lib.py")
    rows = []
    for data in datasets:
        scores = data["scores"]
        clip = G.stable_order(scores)
        nms = G.temporal_nms_ranking(scores, radius=10)
        method_selections = {
            "dasr": {b: dasr_selection(scores, b)[0] for b in budgets},
            "clip_topk": {b: clip[:b] for b in budgets},
            "temporal_nms_h10": {b: nms[:b] for b in budgets},
            "stratified_m1.5": {b: stratum_winners(scores, b, 1.5) for b in budgets},
        }
        for method, selections in method_selections.items():
            rows.extend(evaluate_method(data, method, selections, budgets, evaluator_hash))
    per_run = pd.DataFrame(rows)
    summary, auc = G.summarize(per_run, budgets)
    summary.to_csv(root / "fitting_replay_summary.csv", index=False)
    auc.to_csv(root / "fitting_replay_auc.csv", index=False)
    return summary, auc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=PACKAGE / "outputs" / "final_confirmation"
    )
    args = parser.parse_args()
    if G.sha256_file(PROTOCOL) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("final protocol changed after freeze")
    config = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}
    all_runs = []
    for spec in config["confirmatory_intervals"]:
        data, grid, events = load_interval(spec, args.output)
        per_run, summary, auc, diagnostics = interval_gate(
            spec, data, grid, events, args.output
        )
        results[spec["name"]] = {"per_run": per_run, "summary": summary, "auc": auc}
        all_runs.append(per_run)
    fitting_replay(args.output)

    def auc_value(interval: str, method: str) -> float:
        frame = results[interval]["auc"]
        row = frame[frame.method == method]
        if len(row) != 1:
            raise RuntimeError(f"missing AUC: {interval}/{method}")
        return float(row.event_f1_auc.iloc[0])

    sparse = "realcartest_1630_2000"
    rich = "realcartest_3200_3830"
    sparse_dasr = auc_value(sparse, "dasr")
    sparse_arc = auc_value(sparse, "arc_shared_k3")
    rich_dasr = auc_value(rich, "dasr")
    rich_arc = auc_value(rich, "arc_shared_k3")
    rich_clip = auc_value(rich, "clip_topk")
    rich_nms = auc_value(rich, "temporal_nms_h10")
    event_rich_pass = rich_dasr > rich_arc and rich_dasr > rich_clip and rich_dasr > rich_nms
    sparse_pass = sparse_dasr >= sparse_arc
    macro_dasr = (sparse_dasr + rich_dasr) / 2.0
    macro_arc = (sparse_arc + rich_arc) / 2.0
    macro_pass = macro_dasr > macro_arc
    primary = pd.concat(all_runs, ignore_index=True)
    primary = primary[
        primary.method.isin(
            ["dasr", "clip_topk", "temporal_nms_h10", "stratified_m1.5", "arc_shared_k3"]
        )
    ]
    fairness = bool(
        np.allclose(
            primary.exact_oracle_calls.to_numpy(float), primary.budget.to_numpy(float)
        )
    )
    passed = event_rich_pass and sparse_pass and macro_pass and fairness
    decision = {
        "frozen_protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "event_rich_interval": {
            "name": rich,
            "dasr_event_f1_auc": rich_dasr,
            "arc_shared_k3_event_f1_auc": rich_arc,
            "clip_event_f1_auc": rich_clip,
            "temporal_nms_event_f1_auc": rich_nms,
            "pass": event_rich_pass,
        },
        "sparse_interval": {
            "name": sparse,
            "dasr_event_f1_auc": sparse_dasr,
            "arc_shared_k3_event_f1_auc": sparse_arc,
            "directional_pass": sparse_pass,
        },
        "macro_dasr_event_f1_auc": macro_dasr,
        "macro_arc_shared_k3_event_f1_auc": macro_arc,
        "macro_pass": macro_pass,
        "exact_call_fairness_pass": fairness,
        "decision": "CONFIRMED_GO" if passed else "NO_GO_CONTINUE_SEARCH",
        "physical_exact_oracle_vlm_calls": 0,
        "claim_limit": config["claim_limit"],
    }
    (args.output / "FINAL_CONFIRMATION_DECISION.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    C.manifest(PACKAGE).to_csv(PACKAGE / "FINAL_OUTPUT_MANIFEST.csv", index=False)
    print(json.dumps(decision, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
