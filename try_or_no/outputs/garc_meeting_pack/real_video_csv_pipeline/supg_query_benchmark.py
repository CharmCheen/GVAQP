#!/usr/bin/env python3
"""
supg_query_benchmark.py

Use the real SUPG framework (refe_repos/supg) to measure query-time cost
on the real video CSV. Compares brute-force oracle scan vs SUPG selectors.

Usage:
    python supg_query_benchmark.py \
        --csv-path outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg_k5.csv \
        --oracle-fps 44.9 \
        --nb-trials 50
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Add SUPG to path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "refe_repos" / "supg"))

from supg.datasource.csv_source import load_csv_source
from supg.selector.base_selector import ApproxQuery
from supg.selector.recall_selector import RecallSelector
from supg.selector.importance_precision import ImportancePrecisionSelector
from supg.selector.naive_recall import NaiveRecallSelector
from supg.selector.naive_precision import NaivePrecisionSelector
from supg.sampler.naive_sampler import NaiveSampler
from supg.sampler.imp_sampler import ImportanceSampler


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--csv-path", required=True, help="SUPG-format CSV (id, label, proxy_score)")
    p.add_argument("--oracle-fps", type=float, default=44.9, help="Oracle inference fps")
    p.add_argument("--nb-trials", type=int, default=50, help="Number of SUPG trials")
    p.add_argument("--budget-ratios", default="0.05,0.10,0.20", help="Budget as fraction of N")
    return p.parse_args()


def time_selector(selector, source, nb_trials):
    """Run selector nb_trials times, return (avg_time_per_trial, results)."""
    times = []
    results = []
    for _ in range(nb_trials):
        t0 = time.perf_counter()
        selected = selector.select()
        elapsed = time.perf_counter() - t0
        times.append(elapsed)

        labels = source.lookup(selected)
        n_pos = int(np.sum(labels))
        results.append({
            "n_selected": len(selected),
            "n_positive": n_pos,
            "precision": n_pos / len(selected) if len(selected) > 0 else 0,
        })

    return np.mean(times), np.std(times), results


def main():
    args = parse_args()

    # Load SUPG data source
    print(f"Loading CSV: {args.csv_path}")
    source = load_csv_source(args.csv_path)
    n = len(source.df_sorted)
    n_pos = int(source.df_sorted["label"].sum())
    pos_rate = n_pos / n
    print(f"  N = {n}, positive = {n_pos} ({pos_rate:.2%})")
    print()

    budget_ratios = [float(x) for x in args.budget_ratios.split(",")]

    # --- Baseline: brute-force oracle on all frames ---
    oracle_time_full = n / args.oracle_fps
    print(f"=== Brute-force baseline (oracle on all {n} frames) ===")
    print(f"  Oracle fps: {args.oracle_fps}")
    print(f"  Full oracle time: {oracle_time_full:.2f}s")
    print()

    # --- SUPG selectors ---
    configs = [
        {
            "name": "RecallSelector (sqrt importance)",
            "qtype": "rt",
            "selector_cls": RecallSelector,
            "sampler_cls": ImportanceSampler,
            "kwargs": {"sample_mode": "sqrt"},
        },
        {
            "name": "RecallSelector (uniform)",
            "qtype": "rt",
            "selector_cls": RecallSelector,
            "sampler_cls": NaiveSampler,
            "kwargs": {"sample_mode": "uniform"},
        },
        {
            "name": "PrecisionSelector (importance)",
            "qtype": "pt",
            "selector_cls": ImportancePrecisionSelector,
            "sampler_cls": ImportanceSampler,
            "kwargs": {"start_samp": 50, "step_size": 50},
        },
        {
            "name": "NaiveRecallSelector",
            "qtype": "rt",
            "selector_cls": NaiveRecallSelector,
            "sampler_cls": NaiveSampler,
            "kwargs": {},
        },
        {
            "name": "NaivePrecisionSelector",
            "qtype": "pt",
            "selector_cls": NaivePrecisionSelector,
            "sampler_cls": NaiveSampler,
            "kwargs": {},
        },
    ]

    all_results = []

    for ratio in budget_ratios:
        budget = max(10, int(n * ratio))
        print(f"{'='*70}")
        print(f"Budget ratio = {ratio:.0%}, budget = {budget}")
        print(f"{'='*70}")

        for cfg in configs:
            # Create query
            if cfg["qtype"] == "rt":
                query = ApproxQuery(qtype="rt", min_recall=0.9, delta=0.01, budget=budget)
            else:
                query = ApproxQuery(qtype="pt", min_precision=0.5, delta=0.01, budget=budget)

            # Create sampler
            sampler = cfg["sampler_cls"]()

            # Create selector
            try:
                selector = cfg["selector_cls"](query, source, sampler, **cfg["kwargs"])
            except Exception as e:
                print(f"  [{cfg['name']}] SKIP (init error: {e})")
                continue

            # Benchmark
            try:
                avg_time, std_time, results = time_selector(selector, source, args.nb_trials)
            except Exception as e:
                print(f"  [{cfg['name']}] SKIP (runtime error: {e})")
                continue

            avg_selected = np.mean([r["n_selected"] for r in results])
            avg_positive = np.mean([r["n_positive"] for r in results])
            avg_precision = np.mean([r["precision"] for r in results])

            # Oracle cost for selected frames
            oracle_cost_selected = avg_selected / args.oracle_fps
            # Total query time = selector time + oracle cost on selected
            total_query_time = avg_time + oracle_cost_selected
            speedup = oracle_time_full / total_query_time if total_query_time > 0 else float("inf")

            print(f"  [{cfg['name']}]")
            print(f"    selector time:   {avg_time*1000:.2f}ms ± {std_time*1000:.2f}ms")
            print(f"    selected frames: {avg_selected:.0f} / {n}")
            print(f"    oracle calls:    {avg_selected:.0f} (vs {n} brute-force)")
            print(f"    oracle cost:     {oracle_cost_selected:.2f}s")
            print(f"    total query:     {total_query_time:.2f}s")
            print(f"    speedup:         {speedup:.1f}×")
            print(f"    avg precision:   {avg_precision:.4f}")
            print()

            all_results.append({
                "budget_ratio": ratio,
                "budget": budget,
                "selector": cfg["name"],
                "qtype": cfg["qtype"],
                "selector_time_ms": avg_time * 1000,
                "avg_selected": avg_selected,
                "oracle_cost_s": oracle_cost_selected,
                "total_query_s": total_query_time,
                "speedup": speedup,
                "avg_precision": avg_precision,
            })

    # --- Summary table ---
    print()
    print("=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)
    print(f"{'ratio':>6s} {'selector':<35s} {'sel_ms':>8s} {'selected':>8s} {'oracle_s':>9s} {'total_s':>8s} {'speedup':>8s} {'prec':>6s}")
    print("-" * 80)
    for r in all_results:
        print(f"{r['budget_ratio']:>5.0%} {r['selector']:<35s} {r['selector_time_ms']:>7.1f}ms {r['avg_selected']:>8.0f} {r['oracle_cost_s']:>8.2f}s {r['total_query_s']:>7.2f}s {r['speedup']:>7.1f}× {r['avg_precision']:>5.3f}")

    print()
    print(f"Brute-force baseline: {oracle_time_full:.2f}s (oracle on all {n} frames)")

    # Return for report generation
    return all_results, oracle_time_full, n, n_pos, pos_rate


if __name__ == "__main__":
    main()
