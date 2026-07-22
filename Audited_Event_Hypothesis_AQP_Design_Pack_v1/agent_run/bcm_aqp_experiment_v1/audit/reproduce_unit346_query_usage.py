#!/usr/bin/env python3
"""Reproduce the read-only unit-346 frozen-trace usage summary."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[4]
TARGET = Path(__file__).resolve().parent / "unit346_query_usage.csv"
BENCHMARK = REPO / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1"


def summarize(category: str, frame: pd.DataFrame, notes: str) -> dict:
    runs = frame[["run_id", "method", "method_variant", "seed", "horizon_budget"]].drop_duplicates()
    hits = frame[frame["unit_id"].astype(int) == 346]
    hit_runs = hits[["run_id", "method", "method_variant", "seed", "horizon_budget"]].drop_duplicates()
    if hits.empty:
        earliest_budget = earliest_idx = earliest_number = ""
        unique_seeds = 0
    else:
        earliest_budget = int(hits["horizon_budget"].min())
        earliest_idx = int(hits.loc[hits["horizon_budget"] == earliest_budget, "call_idx"].min())
        earliest_number = earliest_idx + 1
        unique_seeds = int(hits["seed"].nunique())
    return {
        "category": category,
        "total_run_instances": len(runs),
        "querying_run_instances": len(hit_runs),
        "unique_querying_seeds": unique_seeds,
        "earliest_budget": earliest_budget,
        "earliest_call_idx_0based": earliest_idx,
        "earliest_call_number_1based": earliest_number,
        "notes": notes,
    }


def main() -> None:
    current = pd.read_csv(BENCHMARK / "current_method/current_action_traces.csv")
    baseline = pd.read_csv(BENCHMARK / "baselines/baseline_action_traces.csv")
    controlled = baseline[baseline["run_id"].str.startswith("controlled_track_")]
    rows = [
        summarize("current_M0", current[current.method == "M0_MAP_anchor_only"], "M0_MAP_anchor_only/CURRENT_ORIGINAL"),
        summarize("current_M1", current[current.method == "M1_MAP_anchor_only"], "M1_MAP_anchor_only/K3_BRIDGE_SAFE"),
        summarize("native_ARC", baseline[baseline.method == "B5_ARC_native"], "B5_ARC_native/arc_refinement_th0.4_native"),
        summarize("controlled_ARC", baseline[baseline.method == "B3_ARC_adapted"], "B3_ARC_adapted/arc_refinement_th0.4_controlled"),
        summarize("SUPG_all", baseline[baseline.method == "B4_SUPG_adapted"], "all native and controlled all-selected/confirmed-only variants"),
        summarize("SUPG_native", baseline[(baseline.method == "B4_SUPG_adapted") & baseline.method_variant.str.contains("native")], "native all-selected and confirmed-only variants"),
        summarize("SUPG_controlled", baseline[(baseline.method == "B4_SUPG_adapted") & baseline.method_variant.str.contains("controlled")], "controlled all-selected and confirmed-only variants"),
        summarize("ABae_all", baseline[baseline.method == "B6_ABae_adapted_diagnostic"], "native plus controlled duplicates of acquisition results"),
        summarize("ABae_native", baseline[(baseline.method == "B6_ABae_adapted_diagnostic") & baseline.method_variant.str.contains("native")], "abae_stratified_native"),
        summarize("ABae_controlled", baseline[(baseline.method == "B6_ABae_adapted_diagnostic") & baseline.method_variant.str.contains("controlled")], "abae_stratified_controlled"),
        summarize("random_all", baseline[baseline.method == "B0_uniform_random"], "native plus controlled materializations of each random acquisition order"),
        summarize("random_native", baseline[(baseline.method == "B0_uniform_random") & baseline.method_variant.str.contains("native")], "random_native_confirmed"),
        summarize("random_controlled", baseline[(baseline.method == "B0_uniform_random") & baseline.method_variant.str.contains("controlled")], "random_controlled_bridge_safe"),
        summarize("all_controlled_trace_runs", controlled, "67 random + 13 ARC + 3 ABae; every one has a materializer replay row"),
    ]
    with TARGET.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {TARGET} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
