#!/usr/bin/env python3
"""Five-domain post-hoc and leave-one-domain-out PSTR evaluation.

This supersedes, but does not overwrite, the four-domain v4 exploration.
Every domain and label was open before this analysis; results are not
prospective confirmation.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent


def import_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V4 = import_script("pstr_v4_historical", PACKAGE / "scripts" / "run_pstr_exploration.py")
F = V4.F
G = V4.G
C = V4.C


def load_domains() -> list[dict]:
    frozen = json.loads(G.FROZEN.read_text(encoding="utf-8"))
    development = G.load_development(frozen)
    public_proxy_path = G.STRICT / "frozen_inputs" / "public_proxy.csv"
    public_proxy = pd.read_csv(public_proxy_path)
    public_proxy = public_proxy[
        public_proxy.proxy_name == "score_fusion_yolo_motion"
    ].sort_values("unit_id")
    if public_proxy.unit_id.astype(int).tolist() != list(range(len(development["units"]))):
        raise AssertionError("dataset3 ARC public proxy does not align by unit ID")
    development["proxy_scores"] = public_proxy.proxy_score_normalized.to_numpy(float)
    domains = [
        {
            "data": development,
            "domain": "dataset3_development",
            "video": "long_video_dataset3",
            "proxy_family": "score_fusion_yolo_motion_normalized",
            "budgets": [5, 10, 20, 50, 80, 100],
            "source_root": PACKAGE / "outputs" / "development",
        }
    ]
    for data, budgets, source_root in V4.load_domains():
        if data["name"] == "heldout":
            domain = "realcartest_2000_3200"
            proxy_family = "clean_no_leak_cheap_fused_score"
        else:
            domain = data["name"]
            proxy_family = "roadclip_score_count"
        domains.append(
            {
                "data": data,
                "domain": domain,
                "video": "realcartest",
                "proxy_family": proxy_family,
                "budgets": budgets,
                "source_root": source_root,
            }
        )
    return domains


def evaluate_selection(data: dict, selection: list[int], budget: int, method: str, evaluator: str) -> dict:
    row, _, _, _ = G.evaluate_selection(
        data, method, "posthoc_open_domain_exploration_v2", 0, budget, selection, evaluator
    )
    return row


def auc(rows: pd.DataFrame, budgets: list[int]) -> float:
    curve = rows.groupby("budget").event_f1.mean().reindex(budgets)
    return float(
        np.trapezoid(curve.to_numpy(float), np.asarray(budgets, dtype=float))
        / (budgets[-1] - budgets[0])
    )


def main() -> None:
    output = PACKAGE / "outputs" / "pstr_exploration_v2"
    output.mkdir(parents=True, exist_ok=True)
    evaluator_hash = G.sha256_file(G.STRICT / "scripts" / "benchmark_lib.py")
    overheads = [0.0, 0.25, 0.5, 1.0, 2.0]
    domains = load_domains()
    grid_rows = []
    run_rows = []
    selection_rows = []
    baseline_rows = []
    baseline_run_rows = []

    for spec in domains:
        data = spec["data"]
        budgets = spec["budgets"]
        proxy = np.asarray(data["proxy_scores"], dtype=float)
        for overhead in overheads:
            rows = []
            for budget in budgets:
                selected = V4.pstr_selection(proxy, budget, overhead)
                row = evaluate_selection(
                    data, selected, budget, f"pstr_overhead_{overhead:g}", evaluator_hash
                )
                row.update(
                    {
                        "domain": spec["domain"],
                        "video_id_audit": spec["video"],
                        "proxy_family": spec["proxy_family"],
                    }
                )
                rows.append(row)
                for rank, unit_id in enumerate(selected, 1):
                    selection_rows.append(
                        {
                            "domain": spec["domain"],
                            "video_id": spec["video"],
                            "proxy_family": spec["proxy_family"],
                            "overhead": overhead,
                            "budget": budget,
                            "selection_rank": rank,
                            "unit_id": unit_id,
                            "proxy_score": proxy[unit_id],
                            "oracle_label_after_query": data["labels"][unit_id],
                        }
                    )
            frame = pd.DataFrame(rows)
            run_rows.extend(frame.to_dict("records"))
            grid_rows.append(
                {
                    "domain": spec["domain"],
                    "video_id": spec["video"],
                    "proxy_family": spec["proxy_family"],
                    "overhead": overhead,
                    "event_f1_auc": auc(frame, budgets),
                    "budgets": "|".join(map(str, budgets)),
                }
            )

        recorded = pd.read_csv(spec["source_root"] / "event_f1_auc.csv")
        arc_auc = float(
            recorded.loc[recorded.method == "arc_shared_k3", "event_f1_auc"].iloc[0]
        )
        orders = {
            "proxy_topk": G.stable_order(proxy),
            "clip_topk": G.stable_order(data["scores"]),
            "temporal_nms_h10": G.temporal_nms_ranking(data["scores"], 10),
        }
        for method, order in orders.items():
            rows = pd.DataFrame(
                [
                    evaluate_selection(data, order[:budget], budget, method, evaluator_hash)
                    for budget in budgets
                ]
            )
            rows["domain"] = spec["domain"]
            rows["video_id_audit"] = spec["video"]
            rows["proxy_family"] = spec["proxy_family"]
            baseline_run_rows.extend(rows.to_dict("records"))
            baseline_rows.append(
                {
                    "domain": spec["domain"],
                    "video_id": spec["video"],
                    "method": method,
                    "event_f1_auc": auc(rows, budgets),
                }
            )
        dasr_rows = pd.DataFrame(
            [
                evaluate_selection(
                    data, F.dasr_selection(data["scores"], budget)[0], budget, "dasr", evaluator_hash
                )
                for budget in budgets
            ]
        )
        dasr_rows["domain"] = spec["domain"]
        dasr_rows["video_id_audit"] = spec["video"]
        dasr_rows["proxy_family"] = spec["proxy_family"]
        baseline_run_rows.extend(dasr_rows.to_dict("records"))
        baseline_rows.extend(
            [
                {
                    "domain": spec["domain"],
                    "video_id": spec["video"],
                    "method": "dasr",
                    "event_f1_auc": auc(dasr_rows, budgets),
                },
                {
                    "domain": spec["domain"],
                    "video_id": spec["video"],
                    "method": "arc_shared_k3_five_seed_mean",
                    "event_f1_auc": arc_auc,
                },
            ]
        )

    grid = pd.DataFrame(grid_rows)
    domain_names = grid.domain.drop_duplicates().tolist()
    loo_rows = []
    for heldout in domain_names:
        means = grid[grid.domain != heldout].groupby("overhead").event_f1_auc.mean()
        best = float(means.max())
        selected = float(min(value for value, score in means.items() if np.isclose(score, best)))
        test_auc = float(
            grid[(grid.domain == heldout) & np.isclose(grid.overhead, selected)].event_f1_auc.iloc[0]
        )
        arc_auc = next(
            row["event_f1_auc"]
            for row in baseline_rows
            if row["domain"] == heldout and row["method"] == "arc_shared_k3_five_seed_mean"
        )
        loo_rows.append(
            {
                "heldout_domain": heldout,
                "training_domains": "|".join(name for name in domain_names if name != heldout),
                "selected_overhead": selected,
                "training_macro_event_f1_auc": best,
                "test_pstr_event_f1_auc": test_auc,
                "test_arc_shared_k3_event_f1_auc": arc_auc,
                "test_delta_pstr_minus_arc": test_auc - arc_auc,
                "direction": "WIN" if test_auc > arc_auc else "TIE" if np.isclose(test_auc, arc_auc) else "LOSS",
            }
        )

    pooled = grid.groupby("overhead").event_f1_auc.mean()
    pooled_best = float(pooled.max())
    selected_overhead = float(
        min(value for value, score in pooled.items() if np.isclose(score, pooled_best))
    )
    selected = grid[np.isclose(grid.overhead, selected_overhead)].copy()
    selected["role"] = "posthoc_all_open_domains_candidate"

    grid.to_csv(output / "parameter_grid_auc.csv", index=False)
    pd.DataFrame(run_rows).to_csv(output / "per_budget_runs.csv", index=False)
    pd.DataFrame(selection_rows).to_csv(output / "selections.csv", index=False)
    pd.DataFrame(baseline_rows).to_csv(output / "baseline_auc.csv", index=False)
    pd.DataFrame(baseline_run_rows).to_csv(output / "baseline_per_budget_runs.csv", index=False)
    pd.DataFrame(loo_rows).to_csv(output / "leave_one_domain_out.csv", index=False)
    selected.to_csv(output / "selected_candidate_auc.csv", index=False)
    decision = {
        "status": "EXPLORATORY_CANDIDATE_NOT_EXTERNALLY_CONFIRMED",
        "method": "Proxy-Stratified Temporal Retrieval (PSTR-5:4)",
        "domain_count": len(domain_names),
        "video_count": len({spec["video"] for spec in domains}),
        "selected_overhead_after_all_domains_opened": selected_overhead,
        "pooled_domain_macro_event_f1_auc": pooled_best,
        "leave_one_domain_out_strict_wins_over_shared_arc": sum(
            row["direction"] == "WIN" for row in loo_rows
        ),
        "leave_one_domain_out_ties_with_shared_arc": sum(
            row["direction"] == "TIE" for row in loo_rows
        ),
        "leave_one_domain_out_losses_to_shared_arc": sum(
            row["direction"] == "LOSS" for row in loo_rows
        ),
        "physical_exact_oracle_vlm_calls": 0,
        "claim_limit": (
            "All five domains and labels were open before this analysis. Four domains share "
            "realcartest; domain-level LOO is not independent cross-video confirmation."
        ),
    }
    (output / "DECISION.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(decision, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
