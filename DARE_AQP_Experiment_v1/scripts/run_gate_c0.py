#!/usr/bin/env python3
"""Run the exact hierarchical block-oracle feasibility ceiling."""

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
sys.path.insert(0, str(PACKAGE / "src"))

from dare_aqp.interval_ceiling import (  # noqa: E402
    any_binary_full,
    count_guided,
    count_root_any_best_first,
    trace_cost,
)
from dare_aqp.audit import zero_hit_minimum_sample  # noqa: E402


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("cannot write empty result table")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_population(config):
    paths = {key: REPO / value for key, value in config["inputs"].items()}
    units = read_csv(paths["units"])
    events = read_csv(paths["events"])
    proxy_rows = read_csv(paths["public_proxy"])
    unit_ids = [int(row["unit_id"]) for row in units]
    if unit_ids != list(range(len(units))):
        raise ValueError("C0 requires contiguous unit IDs")
    proxy = [0.0] * len(units)
    for row in proxy_rows:
        proxy[int(row["frame_idx"])] = float(row["proxy_score"])
    anchors = set()
    unit_to_events = {}
    for event in events:
        anchor_time = float(event["canonical_anchor_time"])
        matches = [
            int(unit["unit_id"])
            for unit in units
            if float(unit["start_time"]) <= anchor_time < float(unit["end_time"])
        ]
        if len(matches) != 1 or matches[0] in anchors:
            raise ValueError("canonical anchors are not unique at unit resolution")
        anchors.add(matches[0])
        for value in event["source_unit_ids"].split("|"):
            unit_to_events.setdefault(int(value), set()).add(event["reference_event_id"])
    selected_rows = read_csv(paths["current_selected"]) + read_csv(paths["baseline_selected"])
    return paths, len(units), anchors, proxy, unit_to_events, selected_rows


def build_traces(population_size, anchors, proxy, targets):
    traces = []
    full_queries, full_found = any_binary_full(population_size, anchors)
    traces.append(("any_binary_full", 1.0, False, full_queries, full_found))
    for target in targets:
        queries, found = count_guided(population_size, anchors, proxy, target)
        traces.append(("count_guided", target, True, queries, found))
        queries, found = count_root_any_best_first(
            population_size, anchors, proxy, target, oracle_priority=False
        )
        traces.append(("count_root_proxy_any", target, True, queries, found))
        queries, found = count_root_any_best_first(
            population_size, anchors, proxy, target, oracle_priority=True
        )
        traces.append(("count_root_oracle_any_ceiling", target, True, queries, found))
    return traces


def evaluate(config, population_size, anchors, traces):
    dense_cost = float(population_size)
    rows = []
    for method, target, has_count, queries, found in traces:
        multipliers = config["count_cost_multipliers"] if has_count else [1.0]
        for multiplier in multipliers:
            for alpha in config["fixed_fraction_grid"]:
                cost = trace_cost(
                    queries,
                    alpha,
                    count_multiplier=multiplier,
                    certify_count=len(found),
                    certify_cost=config["certify_event_cost"],
                )
                rows.append({
                    "method": method,
                    "target_recall": target,
                    "achieved_recall": len(found) / len(anchors),
                    "events_localized": len(found),
                    "query_calls": len(queries),
                    "any_calls": sum(q.operator == "ANY_EVENT" for q in queries),
                    "count_calls": sum(q.operator == "COUNT_EVENTS" for q in queries),
                    "sum_queried_unit_lengths": sum(q.length for q in queries),
                    "fixed_fraction": alpha,
                    "count_cost_multiplier": multiplier,
                    "total_cost": cost,
                    "dense_complete_audit_cost": dense_cost,
                    "cost_ratio": cost / dense_cost,
                    "below_70pct_dense": int(cost / dense_cost < config["go_cost_ratio"]),
                    "evaluator_informed_priority": int("oracle" in method),
                })
    return rows


def break_even(rows, config):
    groups = {}
    for row in rows:
        key = (row["method"], row["target_recall"], row["count_cost_multiplier"])
        groups.setdefault(key, []).append(row)
    output = []
    for (method, target, multiplier), values in sorted(groups.items()):
        passing = [row for row in values if row["below_70pct_dense"]]
        threshold = min((row["fixed_fraction"] for row in passing), default=None)
        constant = next(row for row in values if row["fixed_fraction"] == 1.0)
        linear = next(row for row in values if row["fixed_fraction"] == 0.0)
        limit = config["go_cost_ratio"] * float(constant["dense_complete_audit_cost"])
        constant_cost = float(constant["total_cost"])
        linear_cost = float(linear["total_cost"])
        if constant_cost >= limit or linear_cost == constant_cost:
            continuous = None
        else:
            continuous = max(0.0, (linear_cost - limit) / (linear_cost - constant_cost))
        output.append({
            "method": method,
            "target_recall": target,
            "count_cost_multiplier": multiplier,
            "events_localized": constant["events_localized"],
            "query_calls": constant["query_calls"],
            "sum_queried_unit_lengths": constant["sum_queried_unit_lengths"],
            "minimum_fixed_fraction_for_70pct_dense": "" if threshold is None else threshold,
            "continuous_fixed_fraction_threshold": "" if continuous is None else continuous,
            "constant_cost_ratio": constant["cost_ratio"],
            "linear_cost_ratio": linear["cost_ratio"],
            "evaluator_informed_priority": constant["evaluator_informed_priority"],
        })
    return output


def unit_order_comparators(selected_rows, unit_to_events, total_events):
    """Summarize frozen strict MAP, ARC and uniform acquisition traces."""
    allowed = {"M1_MAP_anchor_only", "B0_uniform_random", "B5_ARC_native"}
    runs = {}
    for row in selected_rows:
        if row["method"] not in allowed:
            continue
        key = (
            row["method"], row["method_variant"], int(row["horizon_budget"]),
            row["run_id"], int(row["seed"]),
        )
        runs.setdefault(key, []).append(row)
    grouped = {}
    for (method, variant, budget, run_id, seed), rows in runs.items():
        events = set()
        for row in sorted(rows, key=lambda value: int(value["call_idx"])):
            events.update(unit_to_events.get(int(row["unit_id"]), ()))
        key = (method, variant, budget)
        grouped.setdefault(key, []).append((len(events), len(rows)))
    output = []
    for (method, variant, budget), values in sorted(grouped.items()):
        event_counts = [value[0] for value in values]
        calls = [value[1] for value in values]
        output.append({
            "method": method,
            "method_variant": variant,
            "budget": budget,
            "runs": len(values),
            "mean_distinct_events": statistics.fmean(event_counts),
            "median_distinct_events": statistics.median(event_counts),
            "max_distinct_events": max(event_counts),
            "mean_discovery_recall": statistics.fmean(event_counts) / total_events,
            "mean_unit_calls": statistics.fmean(calls),
            "decision_bearing_for_c0": 0,
            "note": "frozen strict unit-order comparator; no root COUNT and no C0 cost gate effect",
        })
    return output


def render_report(path, config, population_size, anchors, break_even_rows, comparators):
    primary = next(
        row for row in break_even_rows
        if row["method"] == "count_guided"
        and float(row["target_recall"]) == 0.8
        and float(row["count_cost_multiplier"]) == 1.25
    )
    threshold = primary["minimum_fixed_fraction_for_70pct_dense"]
    continuous = primary["continuous_fixed_fraction_threshold"]
    strong_go = threshold != "" and float(threshold) <= config["max_required_fixed_fraction"]
    decision = "STRONG_C0_GO" if strong_go else "CONDITIONAL_C0_ONLY"
    unit_b100 = [row for row in comparators if row["budget"] == 100]
    unit_summary = ", ".join(
        f"{row['method']}={float(row['mean_distinct_events']):.1f}"
        for row in unit_b100
        if (
            row["method"] == "M1_MAP_anchor_only"
            or row["method"] == "B5_ARC_native"
            or row["method_variant"] == "random_controlled_bridge_safe"
        )
    )
    lines = [
        "# Gate C0 hierarchical block-oracle ceiling",
        "",
        f"**Decision: `{decision}`.**",
        "",
        "## Observed ceiling evidence",
        "",
        f"- Population: {population_size} units, {len(anchors)} canonical anchors.",
        f"- Primary exact count-guided plan (80% recall, COUNT cost x1.25): {primary['query_calls']} interval calls and {primary['events_localized']} certifications.",
        f"- Constant-cost ratio: {float(primary['constant_cost_ratio']):.3f} of dense complete audit.",
        f"- Linear-duration-cost ratio: {float(primary['linear_cost_ratio']):.3f} of dense complete audit.",
        f"- Minimum fixed-cost fraction on the registered 0.05 grid needed to beat 70% dense: {threshold}.",
        f"- Continuous break-even requires fixed-cost fraction strictly above {float(continuous):.6f}.",
        f"- Frozen unit-order distinct events at B=100 (strict traces): {unit_summary}.",
        "",
        "## Conclusion",
        "",
    ]
    if strong_go:
        lines.append(
            "The exact interval ceiling remains useful under a cost curve with a substantial duration-dependent component. A small measured block-oracle pilot is justified."
        )
    else:
        lines.append(
            "The ceiling is useful only when interval calls are dominated by fixed overhead. Do not launch a broad VLM experiment; first measure 10s/30s/60s/120s latency and accuracy on a small stratified operator-contract pilot."
        )
    lines.extend([
        "",
        "This result does not establish that a real block VLM is exact or has the required cost curve. `count_root_oracle_any_ceiling` is evaluator-informed and diagnostic only.",
        "",
        "Authoritative tables: `break_even.csv`, `cost_curves.csv`, `query_traces.csv`, `unit_order_comparators.csv`, and `unit_audit_zero_hit_lower_bound.csv`.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def lower_bound_table(population_size, total_events, targets, delta=0.05):
    rows = []
    for discovered in (5, 10, 20, 23, 24, total_events):
        remaining_frame = population_size - discovered
        for target in targets:
            allowed = int(discovered * (1.0 - target) / target + 1e-12)
            allowed = min(allowed, remaining_frame - 1)
            sample = zero_hit_minimum_sample(remaining_frame, allowed, delta)
            rows.append({
                "ideal_events_discovered": discovered,
                "recall_target": target,
                "remaining_anchor_frame": remaining_frame,
                "largest_allowed_residual_upper_bound": allowed,
                "minimum_zero_hit_audit_n": sample,
                "audit_fraction_of_remaining_frame": sample / remaining_frame,
                "note": "design threshold only; zero hits may be improbable when true residual exceeds allowed",
            })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PACKAGE / "config/gate_c0.json")
    parser.add_argument("--output", type=Path, default=PACKAGE / "outputs/gate_c0")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    paths, population_size, anchors, proxy, unit_to_events, selected_rows = load_population(config)
    traces = build_traces(population_size, anchors, proxy, config["recall_targets"])
    cost_rows = evaluate(config, population_size, anchors, traces)
    break_even_rows = break_even(cost_rows, config)
    comparators = unit_order_comparators(selected_rows, unit_to_events, len(anchors))
    trace_rows = []
    for method, target, _, queries, found in traces:
        for index, query in enumerate(queries):
            trace_rows.append({
                "method": method,
                "target_recall": target,
                "query_index": index,
                "operator": query.operator,
                "lo": query.lo,
                "hi": query.hi,
                "length_units": query.length,
                "events_localized_final": len(found),
            })
    manifest = [
        {"role": key, "path": str(path.relative_to(REPO)), "sha256": sha256(path)}
        for key, path in paths.items()
    ]
    write_csv(args.output / "cost_curves.csv", cost_rows)
    write_csv(args.output / "break_even.csv", break_even_rows)
    write_csv(args.output / "query_traces.csv", trace_rows)
    write_csv(
        args.output / "unit_order_comparators.csv",
        comparators,
    )
    write_csv(
        args.output / "unit_audit_zero_hit_lower_bound.csv",
        lower_bound_table(population_size, len(anchors), config["recall_targets"]),
    )
    write_csv(args.output / "INPUT_MANIFEST.csv", manifest)
    render_report(
        args.output / "REPORT.md", config, population_size, anchors,
        break_even_rows, comparators,
    )
    print(args.output / "REPORT.md")


if __name__ == "__main__":
    main()
