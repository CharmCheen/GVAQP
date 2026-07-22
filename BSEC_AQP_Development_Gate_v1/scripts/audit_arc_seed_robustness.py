#!/usr/bin/env python3
"""Post-hoc ARC seed audit for the two final DASR intervals.

This script does not alter the frozen gate or tune DASR.  It repeats the
specified ARC-refinement + proxy-order exact-fill comparator for a larger,
deterministic seed range and checks seeds 0--4 against the sealed gate logs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
FINAL_SCRIPT = PACKAGE / "scripts" / "run_final_confirmation_gate.py"
ARC_ADAPTER = REPO / "refe_repos" / "adapter" / "arc_baseline" / "run.py"


def import_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


F = import_script("dasr_final_gate", FINAL_SCRIPT)
A = import_script("arc_adapter_seed_audit", ARC_ADAPTER)
G = F.G


def arc_refinement_calls(frame: pd.DataFrame, budget: int, seed: int) -> list[int]:
    """Run the same ARC refinement primitive used by the adapter."""
    np.random.seed(seed)
    scores = A.normalize_scores(frame["proxy_score"].to_numpy(dtype=float))
    proxy = np.column_stack((1.0 - scores, scores))
    proxy_score = (scores >= 0.4).astype(int)
    tracker = A.OracleTracker(frame)
    clusters = A.cluster_array(frame, "each_frame", 8)
    initial_clips = A.binary_intervals(proxy_score == 1, min_len=1)
    if budget > 0 and len(initial_clips) > 0:
        with A.suppress_stdout(True):
            A.original_arc(
                proxy=proxy,
                oracle=A.AuditedOracleArray(tracker),
                proxy_score=proxy_score.copy(),
                oracle_score=A.AuditedOracleScore(tracker),
                B=budget + 1,
                op=">",
                constant=0,
                tau=1,
                confidence=0.9,
                IOUThreshold=0.5,
                clusters=clusters,
                startup_sampling_rate=0.002,
                tc_enabled=True,
                ps_enabled=True,
                lp_enabled=True,
            )
    return tracker.calls[:budget]


def validate_sealed_calls(name: str, budget: int, seed: int, calls: list[int]) -> None:
    path = (
        PACKAGE
        / "outputs"
        / "final_confirmation"
        / name
        / "arc_adapter_runs"
        / f"arc_refinement_th0.4_s{seed:03d}_b{budget}"
        / "oracle_log.csv"
    )
    sealed = pd.read_csv(path).sort_values("call_idx").unit_id.astype(int).tolist()
    if calls != sealed:
        raise AssertionError(
            f"in-process ARC replay differs from sealed adapter: {name}/s{seed}/b{budget}: "
            f"{calls} != {sealed}"
        )


def audit_interval(spec: dict, seed_count: int, output: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    name = spec["name"]
    budgets = [int(value) for value in spec["budgets"]]
    final_root = PACKAGE / "outputs" / "final_confirmation"
    data, grid, events = F.load_interval(spec, final_root)
    frame_path, _ = F.C.write_adapter_inputs(grid, events, final_root / name)
    frame = A.load_frame_csv_replay(str(frame_path))
    proxy_order = G.stable_order(data["proxy_scores"])
    evaluator_hash = G.sha256_file(G.STRICT / "scripts" / "benchmark_lib.py")
    rows = []
    for seed in range(seed_count):
        for budget in budgets:
            calls = arc_refinement_calls(frame, budget, seed)
            if seed < 5:
                validate_sealed_calls(name, budget, seed, calls)
            selection = F.exact_fill(calls, proxy_order, budget)
            row, _, _, _ = G.evaluate_selection(
                data,
                "arc_shared_k3_seed_audit",
                "threshold_0.4_refinement_plus_proxy_exact_fill",
                seed,
                budget,
                selection,
                evaluator_hash,
            )
            row["actual_arc_refinement_calls"] = len(calls)
            rows.append(row)

    per_budget = pd.DataFrame(rows)
    seed_auc_rows = []
    for seed, group in per_budget.groupby("seed"):
        curve = group.sort_values("budget")
        auc = float(
            np.trapezoid(curve.event_f1.to_numpy(float), curve.budget.to_numpy(float))
            / (budgets[-1] - budgets[0])
        )
        seed_auc_rows.append({"dataset": name, "seed": int(seed), "event_f1_auc": auc})
    seed_auc = pd.DataFrame(seed_auc_rows)

    recorded_auc = pd.read_csv(final_root / name / "event_f1_auc.csv")
    dasr_auc = float(recorded_auc.loc[recorded_auc.method == "dasr", "event_f1_auc"].iloc[0])
    proxy_rows = []
    for budget in budgets:
        row, _, _, _ = G.evaluate_selection(
            data,
            "proxy_topk",
            "prior_score_max",
            0,
            budget,
            proxy_order[:budget],
            evaluator_hash,
        )
        proxy_rows.append(row)
    proxy_frame = pd.DataFrame(proxy_rows).sort_values("budget")
    proxy_auc = float(
        np.trapezoid(
            proxy_frame.event_f1.to_numpy(float), proxy_frame.budget.to_numpy(float)
        )
        / (budgets[-1] - budgets[0])
    )
    auc_values = seed_auc.event_f1_auc.to_numpy(float)
    summary = {
        "dataset": name,
        "seed_range": [0, seed_count - 1],
        "seed_count": seed_count,
        "sealed_seed_replay_0_to_4": "PASS",
        "comparator": "threshold-0.4 ARC-refinement + proxy-order exact-fill, shared K3",
        "arc_seed_auc_mean": float(auc_values.mean()),
        "arc_seed_auc_std_population": float(auc_values.std(ddof=0)),
        "arc_seed_auc_min": float(auc_values.min()),
        "arc_seed_auc_median": float(np.median(auc_values)),
        "arc_seed_auc_max": float(auc_values.max()),
        "dasr_event_f1_auc": dasr_auc,
        "proxy_topk_event_f1_auc": proxy_auc,
        "fraction_arc_seeds_strictly_above_dasr": float(np.mean(auc_values > dasr_auc)),
        "fraction_arc_seeds_equal_dasr": float(np.mean(np.isclose(auc_values, dasr_auc))),
        "physical_exact_oracle_vlm_calls": 0,
        "status": "POST_HOC_DESCRIPTIVE_AUDIT_NOT_PART_OF_FROZEN_DECISION",
    }
    output.mkdir(parents=True, exist_ok=True)
    per_budget.to_csv(output / f"{name}_per_seed_budget.csv", index=False)
    seed_auc.to_csv(output / f"{name}_per_seed_auc.csv", index=False)
    proxy_frame.to_csv(output / f"{name}_proxy_topk_curve.csv", index=False)
    return per_budget, seed_auc, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-count", type=int, default=1000)
    parser.add_argument(
        "--output",
        type=Path,
        default=PACKAGE / "outputs" / "final_confirmation" / "posthoc_arc_seed_audit",
    )
    args = parser.parse_args()
    if args.seed_count < 5:
        raise ValueError("seed-count must be at least 5 to validate sealed seeds")
    config = json.loads(F.PROTOCOL.read_text(encoding="utf-8"))
    summaries = []
    for spec in config["confirmatory_intervals"]:
        _, _, summary = audit_interval(spec, args.seed_count, args.output)
        summaries.append(summary)
    decision = {
        "audit_status": "COMPLETE",
        "frozen_gate_decision_changed": False,
        "interpretation": (
            "This post-hoc audit estimates sensitivity to the ARC adapter's random seed. "
            "It cannot convert the previously labeled intervals into unseen confirmation data."
        ),
        "intervals": summaries,
    }
    (args.output / "SUMMARY.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(decision, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
