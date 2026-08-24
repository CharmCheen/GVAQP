#!/usr/bin/env python3
"""CPU-only timing and alias preflight for the frozen H2 design."""
from __future__ import annotations

import csv
import json
import math
import random
import shutil
import statistics
import sys
import time
from itertools import combinations, product
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from garc.datb_sv import DatbSVConfig, DatbSVReplayRunner, bisection_order


SEEDS = (1729, 3253, 4999, 7919, 104729)
POLICIES = ("datb_sv", "sequential", "uniform_stride", "largest_gap", "random")
COST_RATIOS = (1, 3, 10, 30)
TIGHTNESS = (0.2, 0.4, 0.6)
LEVEL_LABELS = {
    "A": ("sparse", "medium", "dense"),
    "B": ("one_mode", "three_modes", "six_modes"),
    "C": ("short", "medium", "long"),
    "D": ("none", "false_negative", "false_positive"),
    "F": ("20pct", "40pct", "60pct"),
}


def frozen_design() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    design_id = 0
    for ratio in COST_RATIOS:
        for a, b, c, d in product(range(3), repeat=4):
            f = (a + b + c + d) % 3
            design_id += 1
            rows.append({
                "design_id": f"H2-{design_id:03d}",
                "A_density_code": a,
                "A_density": LEVEL_LABELS["A"][a],
                "B_temporal_modes_code": b,
                "B_temporal_modes": LEVEL_LABELS["B"][b],
                "C_event_duration_code": c,
                "C_event_duration": LEVEL_LABELS["C"][c],
                "D_proxy_noise_code": d,
                "D_proxy_noise": LEVEL_LABELS["D"][d],
                "E_verify_scan_cost_ratio": ratio,
                "F_deadline_tightness_code": f,
                "F_deadline_tightness": TIGHTNESS[f],
                "generator_relation": "F=(A+B+C+D) mod 3",
            })
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def largest_gap_order(n: int) -> tuple[int, ...]:
    remaining = set(range(n))
    chosen: list[int] = []
    while remaining:
        if not chosen:
            pick = (n - 1) // 2
        else:
            pick = max(remaining, key=lambda x: (min(abs(x - y) for y in chosen), -x))
        chosen.append(pick)
        remaining.remove(pick)
    return tuple(chosen)


def policy_order(name: str, n: int, seed: int) -> tuple[int, ...]:
    if name == "datb_sv":
        return bisection_order(n)
    if name == "sequential":
        return tuple(range(n))
    if name == "uniform_stride":
        step = 37
        while math.gcd(step, n) != 1:
            step += 2
        return tuple((i * step) % n for i in range(n))
    if name == "largest_gap":
        return largest_gap_order(n)
    if name == "random":
        values = list(range(n))
        random.Random(seed).shuffle(values)
        return tuple(values)
    raise ValueError(name)


def synthetic_workload(row: dict[str, object], seed: int, n: int = 96):
    rng = random.Random(seed + 1000 * int(row["A_density_code"]) + 100 * int(row["D_proxy_noise_code"]))
    density_target = (6, 24, 60)[int(row["A_density_code"])]
    mode_count = (1, 3, 6)[int(row["B_temporal_modes_code"])]
    width = (1, 3, 7)[int(row["C_event_duration_code"])]
    centers = [round((i + 1) * (n - 1) / (mode_count + 1)) for i in range(mode_count)]
    positive_units: set[int] = set()
    radius = width // 2
    for center in centers:
        positive_units.update(range(max(0, center - radius), min(n, center + radius + 1)))
    candidates = [i for i in range(n) if i in positive_units]
    while len(candidates) < density_target:
        candidates.append(rng.randrange(n))
        candidates = sorted(set(candidates))
    positive_units = set(candidates[:density_target])

    noise = int(row["D_proxy_noise_code"])
    units = []
    outcomes = {}
    for unit_id in range(n):
        truly_positive = unit_id in positive_units
        visible = True
        if noise == 1 and truly_positive and unit_id % 5 == 0:
            visible = False
        score = 0.9 if truly_positive else 0.1
        if noise == 2 and not truly_positive and unit_id % 4 == 0:
            score = 0.8
        raw_candidates = []
        if visible:
            raw_candidates.append({"candidate_id": f"candidate-{unit_id}", "score": score})
        units.append({
            "unit_id": unit_id,
            "start_sec": float(unit_id * 10),
            "end_sec": float((unit_id + 1) * 10),
            "scan_cost_sec": 1.0,
            "candidates": raw_candidates,
        })
        event_id = min(range(mode_count), key=lambda i: abs(unit_id - centers[i]))
        outcomes[unit_id] = {
            "completed": True,
            "positive": truly_positive,
            "distinct_utility_ids": [f"event-{event_id}"] if truly_positive else [],
            "actual_cost_sec": float(row["E_verify_scan_cost_ratio"]),
        }
    exhaustive_cost = n * (1.0 + float(row["E_verify_scan_cost_ratio"]))
    deadline = exhaustive_cost * float(row["F_deadline_tightness"])
    return units, outcomes, deadline


class TimedCommit:
    def __init__(self, delegate):
        self.delegate = delegate
        self.io_sec = 0.0

    @property
    def rows(self):
        return self.delegate.rows

    def append(self, *args, **kwargs):
        start = time.perf_counter()
        try:
            return self.delegate.append(*args, **kwargs)
        finally:
            self.io_sec += time.perf_counter() - start

    def finalize(self, *args, **kwargs):
        start = time.perf_counter()
        try:
            return self.delegate.finalize(*args, **kwargs)
        finally:
            self.io_sec += time.perf_counter() - start


def anytime_auc(trace: list[dict[str, object]], deadline: float) -> float:
    if deadline <= 0:
        return 0.0
    last_t = 0.0
    last_u = 0.0
    area = 0.0
    for row in trace:
        complete = min(float(row.get("complete_sec", last_t)), deadline)
        area += max(0.0, complete - last_t) * last_u
        last_t = complete
        last_u = float(row.get("cumulative_utility", last_u))
        if complete >= deadline:
            break
    area += max(0.0, deadline - last_t) * last_u
    return area / deadline


def run_timing(rows: list[dict[str, object]], out: Path) -> tuple[list[dict[str, object]], dict[str, float]]:
    run_root = out / "runs"
    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True)
    records: list[dict[str, object]] = []
    batch_start = time.perf_counter()
    for point in rows[:10]:
        for policy in POLICIES:
            for seed in SEEDS:
                units, outcomes, deadline = synthetic_workload(point, seed)
                call_dir = run_root / str(point["design_id"]) / policy / str(seed)
                call_dir.mkdir(parents=True)
                call_start = time.perf_counter()
                config = DatbSVConfig(
                    deadline_sec=deadline,
                    scan_cost_upper_sec=1.0,
                    verify_cost_upper_sec=float(point["E_verify_scan_cost_ratio"]),
                    commit_reserve_sec=0.0,
                    frontier_capacity=10,
                )
                execution_start = time.perf_counter()
                runner = DatbSVReplayRunner(
                    units,
                    outcomes,
                    config,
                    commit_path=call_dir / "durable_result.json",
                    oracle_metadata={"source": "synthetic_h2_preflight"},
                )
                runner.order = policy_order(policy, len(units), seed)
                timed_commit = TimedCommit(runner.commit)
                runner.commit = timed_commit
                summary = runner.run()
                execution_sec = time.perf_counter() - execution_start

                post_start = time.perf_counter()
                metrics = {
                    "anytime_distinct_event_auc": anytime_auc(runner.trace, deadline),
                    "distinct_utility_count": summary["distinct_utility_count"],
                    "durable_actions": summary["durable_actions"],
                }
                (call_dir / "trace.json").write_text(
                    json.dumps(runner.trace, sort_keys=True) + "\n", encoding="utf-8"
                )
                (call_dir / "summary.json").write_text(
                    json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8"
                )
                (call_dir / "metrics.json").write_text(
                    json.dumps(metrics, sort_keys=True) + "\n", encoding="utf-8"
                )
                postprocess_sec = time.perf_counter() - post_start
                total_sec = time.perf_counter() - call_start
                records.append({
                    "design_id": point["design_id"],
                    "policy": policy,
                    "seed": seed,
                    "execution_and_commit_sec": execution_sec,
                    "durable_commit_io_sec": timed_commit.io_sec,
                    "postprocess_log_serialize_aggregate_sec": postprocess_sec,
                    "total_call_sec": total_sec,
                    **metrics,
                })
    calls_path = out / "preflight_calls.csv"
    write_csv(calls_path, records)
    batch_total = time.perf_counter() - batch_start
    total_calls = sum(float(r["total_call_sec"]) for r in records)
    commit_io = sum(float(r["durable_commit_io_sec"]) for r in records)
    post = sum(float(r["postprocess_log_serialize_aggregate_sec"]) for r in records)
    execution = sum(float(r["execution_and_commit_sec"]) for r in records)
    measured_core = max(0.0, execution - commit_io)
    measured_io = commit_io + post
    residual = max(0.0, batch_total - measured_core - measured_io)
    stats = {
        "call_count": len(records),
        "median_call_sec": statistics.median(float(r["total_call_sec"]) for r in records),
        "max_call_sec": max(float(r["total_call_sec"]) for r in records),
        "batch_total_sec": batch_total,
        "sum_call_sec": total_calls,
        "core_compute_sec": measured_core,
        "durable_commit_io_sec": commit_io,
        "postprocess_io_aggregate_sec": post,
        "batch_setup_and_final_aggregation_residual_sec": residual,
        "core_fraction": measured_core / batch_total,
        "io_log_aggregate_fraction": (batch_total - measured_core) / batch_total,
    }
    stats["n_max_from_median"] = math.floor((8 * 3600) / (stats["median_call_sec"] * 25 * 4))
    return records, stats


def contrast3(levels: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "L": np.choose(levels, (-1.0, 0.0, 1.0)) / math.sqrt(2.0),
        "Q": np.choose(levels, (1.0, -2.0, 1.0)) / math.sqrt(6.0),
    }


def helmert(levels: np.ndarray, count: int) -> dict[str, np.ndarray]:
    values: dict[str, np.ndarray] = {}
    for j in range(count - 1):
        vector = np.zeros(count)
        vector[:j + 1] = 1.0
        vector[j + 1] = -(j + 1)
        vector /= np.linalg.norm(vector)
        values[f"H{j + 1}"] = vector[levels]
    return values


def corr_abs(x: np.ndarray, y: np.ndarray) -> float:
    denom = float(np.linalg.norm(x) * np.linalg.norm(y))
    return 0.0 if denom == 0 else abs(float(np.dot(x, y))) / denom


def alias_checks(design: list[dict[str, object]], out: Path):
    core = design[:81]
    factors = "ABCDF"
    codes = {f: np.array([int(row[next(k for k in row if k.startswith(f + "_"))]) for row in core]) for f in factors}
    contrasts = {f: contrast3(codes[f]) for f in factors}
    mains = {f"{f}_{c}": v for f in factors for c, v in contrasts[f].items()}
    interactions: dict[str, np.ndarray] = {}
    for left, right in combinations(factors, 2):
        for lc, lv in contrasts[left].items():
            for rc, rv in contrasts[right].items():
                interactions[f"{left}_{lc}:{right}_{rc}"] = lv * rv
    alias_rows = []
    for main_name, main_values in mains.items():
        nearest_name, nearest_corr = max(
            ((name, corr_abs(main_values, values)) for name, values in interactions.items()),
            key=lambda item: item[1],
        )
        alias_rows.append({
            "main_effect_component": main_name,
            "nearest_two_factor_component": nearest_name,
            "absolute_correlation": nearest_corr,
            "aliased_at_1e-12": nearest_corr > 1e-12,
        })
    write_csv(out / "alias_main_vs_two_factor.csv", alias_rows)

    expanded = []
    for row in design:
        for policy_code, policy in enumerate(POLICIES):
            expanded.append((row, policy_code, policy))
    arrays = {
        "A": np.array([int(row["A_density_code"]) for row, _, _ in expanded]),
        "B": np.array([int(row["B_temporal_modes_code"]) for row, _, _ in expanded]),
        "C": np.array([int(row["C_event_duration_code"]) for row, _, _ in expanded]),
        "D": np.array([int(row["D_proxy_noise_code"]) for row, _, _ in expanded]),
        "F": np.array([int(row["F_deadline_tightness_code"]) for row, _, _ in expanded]),
        "E": np.array([COST_RATIOS.index(int(row["E_verify_scan_cost_ratio"])) for row, _, _ in expanded]),
        "P": np.array([policy_code for _, policy_code, _ in expanded]),
    }
    expanded_contrasts = {f: contrast3(arrays[f]) for f in "ABCDF"}
    expanded_contrasts["E"] = helmert(arrays["E"], 4)
    expanded_contrasts["P"] = helmert(arrays["P"], 5)
    expanded_mains = {
        f"{factor}_{component}": values
        for factor, parts in expanded_contrasts.items()
        for component, values in parts.items()
    }
    all_two_factor: dict[str, np.ndarray] = {}
    for left, right in combinations("ABCDFEP", 2):
        for lc, lv in expanded_contrasts[left].items():
            for rc, rv in expanded_contrasts[right].items():
                all_two_factor[f"{left}_{lc}:{right}_{rc}"] = lv * rv
    targets: dict[str, dict[str, np.ndarray]] = {}
    for factor in ("A", "B", "E", "F"):
        group = {}
        for pc, pv in expanded_contrasts["P"].items():
            for fc, fv in expanded_contrasts[factor].items():
                # Match the canonical factor order used by all_two_factor so
                # the target columns are removed before testing against the
                # remaining two-factor interaction space.
                group[f"{factor}_{fc}:P_{pc}"] = fv * pv
        targets[f"policy_by_{factor}"] = group
    target_rows = []
    for target_name, target_columns in targets.items():
        other_target_columns = {
            name: values
            for group_name, group in targets.items()
            if group_name != target_name
            for name, values in group.items()
        }
        remaining_two_factor = {
            name: values
            for name, values in all_two_factor.items()
            if name not in target_columns and name not in other_target_columns
        }
        for comparison, pool in (
            ("all_main_effects", expanded_mains),
            ("other_named_policy_interactions", other_target_columns),
            ("remaining_two_factor_interactions", remaining_two_factor),
        ):
            maximum = 0.0
            nearest = "NONE"
            for target_values in target_columns.values():
                for name, values in pool.items():
                    value = corr_abs(target_values, values)
                    if value > maximum:
                        maximum, nearest = value, name
            target_rows.append({
                "target_interaction": target_name,
                "comparison_set": comparison,
                "nearest_component": nearest,
                "max_absolute_correlation": maximum,
                "aliased_at_1e-12": maximum > 1e-12,
            })
    write_csv(out / "alias_target_policy_interactions.csv", target_rows)
    return alias_rows, target_rows


def marginal_tables(design: list[dict[str, object]], out: Path) -> list[dict[str, object]]:
    core = design[:81]
    rows = []
    for f in range(3):
        selected = [row for row in core if int(row["F_deadline_tightness_code"]) == f]
        rows.append({"F_level": f, "factor": "ROW_COUNT", "level_0": len(selected), "level_1": "", "level_2": ""})
        for factor, key in (
            ("A_density", "A_density_code"),
            ("B_temporal_modes", "B_temporal_modes_code"),
            ("C_event_duration", "C_event_duration_code"),
            ("D_proxy_noise", "D_proxy_noise_code"),
        ):
            counts = [sum(int(row[key]) == level for row in selected) for level in range(3)]
            rows.append({"F_level": f, "factor": factor, "level_0": counts[0], "level_1": counts[1], "level_2": counts[2]})
    write_csv(out / "f_marginal_counts.csv", rows)
    return rows


def main() -> None:
    design_path = ROOT / "docs/cpu_only_algorithm_consolidation_20260824/frozen_h2_design_matrix_v1.csv"
    out = ROOT / "outputs/h2_design_preflight_v1"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    design = frozen_design()
    write_csv(design_path, design)
    alias_rows, target_rows = alias_checks(design, out)
    marginal_rows = marginal_tables(design, out)
    _, timing = run_timing(design, out)
    summary = {
        "status": "CPU_PREFLIGHT_COMPLETE",
        "design_points": len(design),
        "core_design_points": 81,
        "seeds": list(SEEDS),
        "policies": list(POLICIES),
        "timing": timing,
        "max_main_vs_two_factor_abs_correlation": max(float(r["absolute_correlation"]) for r in alias_rows),
        "max_target_policy_interaction_abs_correlation": max(float(r["max_absolute_correlation"]) for r in target_rows),
        "main_vs_two_factor_clean": not any(bool(r["aliased_at_1e-12"]) for r in alias_rows),
        "target_policy_interactions_clean": not any(bool(r["aliased_at_1e-12"]) for r in target_rows),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("\nF_MARGINAL_COUNTS")
    for row in marginal_rows:
        print(row)
    print("\nMAIN_VS_TWO_FACTOR_ALIAS")
    for row in alias_rows:
        print(row)
    print("\nTARGET_POLICY_INTERACTION_ALIAS")
    for row in target_rows:
        print(row)


if __name__ == "__main__":
    main()
