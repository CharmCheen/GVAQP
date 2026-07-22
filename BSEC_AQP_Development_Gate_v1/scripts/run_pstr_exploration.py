#!/usr/bin/env python3
"""Exploratory nested-domain evaluation of proxy-stratified retrieval.

All four realcartest domains were already open before this script existed.
Consequently these outputs are development and leave-one-domain-out evidence,
not a new confirmation test.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


PACKAGE = Path(__file__).resolve().parents[1]


def import_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


F = import_script("dasr_final_for_pstr", PACKAGE / "scripts" / "run_final_confirmation_gate.py")
G = F.G
C = F.C


def pstr_selection(proxy_scores: np.ndarray, budget: int, overhead: float) -> list[int]:
    """Select B best proxy representatives from B+floor(overhead*B) time cells."""
    n_units = len(proxy_scores)
    if not 0 < budget <= n_units:
        raise ValueError(f"invalid budget {budget} for population {n_units}")
    n_cells = min(n_units, budget + int(math.floor(overhead * budget)))
    winners = []
    for cell in range(n_cells):
        lo = n_units * cell // n_cells
        hi = n_units * (cell + 1) // n_cells
        winners.append(
            max(range(lo, hi), key=lambda unit_id: (proxy_scores[unit_id], -unit_id))
        )
    ranked = sorted(winners, key=lambda unit_id: (-proxy_scores[unit_id], unit_id))
    if len(ranked) < budget:
        raise AssertionError("PSTR produced fewer cell winners than the budget")
    return ranked[:budget]


def load_domains() -> list[tuple[dict, list[int], Path]]:
    old = json.loads(G.FROZEN.read_text(encoding="utf-8"))
    heldout = G.load_heldout(old)
    continuation = json.loads(C.PROTOCOL.read_text(encoding="utf-8"))
    confirmatory, _, _ = C.load_confirmatory(
        continuation, PACKAGE / "outputs" / "confirmatory"
    )
    domains = [
        (heldout, [5, 10, 20, 50, 80, 100], PACKAGE / "outputs" / "heldout"),
        (
            confirmatory,
            [5, 10, 20, 50, 80, 100],
            PACKAGE / "outputs" / "confirmatory",
        ),
    ]
    v3 = json.loads(F.PROTOCOL.read_text(encoding="utf-8"))
    for spec in v3["confirmatory_intervals"]:
        data, _, _ = F.load_interval(spec, PACKAGE / "outputs" / "final_confirmation")
        domains.append(
            (
                data,
                [int(value) for value in spec["budgets"]],
                PACKAGE / "outputs" / "final_confirmation" / spec["name"],
            )
        )
    for data, _, _ in domains:
        if "proxy_scores" not in data:
            raise AssertionError(f"domain lacks the ARC public proxy: {data['name']}")
    return domains


def normalized_auc(rows: pd.DataFrame, budgets: list[int]) -> float:
    curve = rows.groupby("budget").event_f1.mean().reindex(budgets)
    return float(
        np.trapezoid(curve.to_numpy(float), np.asarray(budgets, dtype=float))
        / (budgets[-1] - budgets[0])
    )


def main() -> None:
    output = PACKAGE / "outputs" / "pstr_exploration"
    output.mkdir(parents=True, exist_ok=True)
    evaluator_hash = G.sha256_file(G.STRICT / "scripts" / "benchmark_lib.py")
    domains = load_domains()
    overheads = [0.0, 0.25, 0.5, 1.0, 2.0]
    grid_rows = []
    curve_rows = []
    selection_rows = []

    for data, budgets, source_root in domains:
        proxy_scores = np.asarray(data["proxy_scores"], dtype=float)
        for overhead in overheads:
            rows = []
            method = f"pstr_overhead_{overhead:g}"
            for budget in budgets:
                selection = pstr_selection(proxy_scores, budget, overhead)
                row, _, _, _ = G.evaluate_selection(
                    data,
                    method,
                    "posthoc_open_domain_exploration",
                    0,
                    budget,
                    selection,
                    evaluator_hash,
                )
                rows.append(row)
                for rank, unit_id in enumerate(selection, 1):
                    selection_rows.append(
                        {
                            "dataset": data["name"],
                            "overhead": overhead,
                            "budget": budget,
                            "selection_rank": rank,
                            "unit_id": unit_id,
                            "proxy_score": proxy_scores[unit_id],
                            "oracle_label_after_query": data["labels"][unit_id],
                        }
                    )
            frame = pd.DataFrame(rows)
            curve_rows.extend(frame.to_dict("records"))
            grid_rows.append(
                {
                    "dataset": data["name"],
                    "overhead": overhead,
                    "cell_rule": "B+floor(overhead*B)",
                    "event_f1_auc": normalized_auc(frame, budgets),
                    "budgets": "|".join(map(str, budgets)),
                }
            )

    grid = pd.DataFrame(grid_rows)
    domains_order = [data["name"] for data, _, _ in domains]
    loo_rows = []
    for heldout_name in domains_order:
        training = grid[grid.dataset != heldout_name]
        means = training.groupby("overhead").event_f1_auc.mean()
        best_mean = float(means.max())
        selected_overhead = float(
            min(value for value, score in means.items() if np.isclose(score, best_mean))
        )
        test_auc = float(
            grid[
                (grid.dataset == heldout_name) & (grid.overhead == selected_overhead)
            ].event_f1_auc.iloc[0]
        )
        source_root = next(root for data, _, root in domains if data["name"] == heldout_name)
        recorded = pd.read_csv(source_root / "event_f1_auc.csv")
        arc_auc = float(
            recorded.loc[recorded.method == "arc_shared_k3", "event_f1_auc"].iloc[0]
        )
        loo_rows.append(
            {
                "heldout_domain": heldout_name,
                "training_domains": "|".join(name for name in domains_order if name != heldout_name),
                "selected_overhead": selected_overhead,
                "training_macro_event_f1_auc": best_mean,
                "test_pstr_event_f1_auc": test_auc,
                "test_arc_shared_k3_event_f1_auc": arc_auc,
                "test_delta_pstr_minus_arc": test_auc - arc_auc,
                "direction": "WIN" if test_auc > arc_auc else "TIE" if np.isclose(test_auc, arc_auc) else "LOSS",
            }
        )

    pooled = grid.groupby("overhead").event_f1_auc.mean()
    pooled_best = float(pooled.max())
    selected = float(min(value for value, score in pooled.items() if np.isclose(score, pooled_best)))
    candidate = grid[grid.overhead == selected].copy()
    candidate["role"] = "posthoc_all_open_domains_candidate"
    candidate["exact_oracle_calls"] = candidate.budgets.map(
        lambda text: "|".join(text.split("|"))
    )

    grid.to_csv(output / "parameter_grid_auc.csv", index=False)
    pd.DataFrame(curve_rows).to_csv(output / "per_budget_runs.csv", index=False)
    pd.DataFrame(selection_rows).to_csv(output / "selections.csv", index=False)
    pd.DataFrame(loo_rows).to_csv(output / "leave_one_domain_out.csv", index=False)
    candidate.to_csv(output / "selected_candidate_auc.csv", index=False)
    decision = {
        "status": "EXPLORATORY_CANDIDATE_NOT_EXTERNALLY_CONFIRMED",
        "method": "Proxy-Stratified Temporal Retrieval (PSTR-5:4)",
        "selection_rule": (
            "For budget B, split the timeline into min(n, B+floor(B/4)) equal contiguous "
            "cells, take each cell's highest public-proxy unit, rank winners by proxy, and select B."
        ),
        "selected_overhead_after_all_domains_opened": selected,
        "pooled_macro_event_f1_auc": pooled_best,
        "leave_one_domain_out_strict_wins": int(
            sum(row["direction"] == "WIN" for row in loo_rows)
        ),
        "leave_one_domain_out_ties": int(
            sum(row["direction"] == "TIE" for row in loo_rows)
        ),
        "leave_one_domain_out_losses": int(
            sum(row["direction"] == "LOSS" for row in loo_rows)
        ),
        "physical_exact_oracle_vlm_calls": 0,
        "claim_limit": (
            "All domains and labels were open before PSTR was proposed. Leave-one-domain-out "
            "replay reduces same-domain parameter bias but is not prospective confirmation."
        ),
    }
    (output / "DECISION.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(decision, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
