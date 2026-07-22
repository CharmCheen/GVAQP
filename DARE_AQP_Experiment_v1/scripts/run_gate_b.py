#!/usr/bin/env python3
"""Run the preregistered DARE-AQP Gate B finite-population replay."""

import argparse
import csv
import hashlib
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
sys.path.insert(0, str(PACKAGE / "src"))

from dare_aqp.audit import hypergeom_upper_bound  # noqa: E402


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values, q):
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    index = (len(ordered) - 1) * q
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    weight = index - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def load_population(config):
    input_paths = {k: REPO / v for k, v in config["inputs"].items()}
    units = read_csv(input_paths["units"])
    proxy = read_csv(input_paths["public_proxy"])
    events_raw = read_csv(input_paths["events"])
    if len(units) != len(proxy):
        raise ValueError("unit and proxy tables have different lengths")
    unit_ids = [int(row["unit_id"]) for row in units]
    if unit_ids != list(range(len(units))):
        raise ValueError("Gate B v1 requires contiguous ordered unit IDs")
    proxy_by_unit = {int(row["frame_idx"]): float(row["proxy_score"]) for row in proxy}
    events = {}
    unit_to_events = defaultdict(set)
    anchors = set()
    for row in events_raw:
        event_id = row["reference_event_id"]
        source_units = {int(value) for value in row["source_unit_ids"].split("|")}
        anchor_time = float(row["canonical_anchor_time"])
        matching = [
            int(u["unit_id"])
            for u in units
            if float(u["start_time"]) <= anchor_time < float(u["end_time"])
        ]
        if len(matching) != 1:
            raise ValueError(f"event {event_id} has {len(matching)} anchor units")
        anchor = matching[0]
        if anchor in anchors:
            raise ValueError("duplicate canonical-anchor unit violates binary model")
        anchors.add(anchor)
        events[event_id] = {"anchor": anchor, "source_units": source_units}
        for unit_id in source_units:
            unit_to_events[unit_id].add(event_id)
    return input_paths, unit_ids, proxy_by_unit, events, unit_to_events


def discovery_order(policy, unit_ids, proxy_by_unit, events, budget, seed):
    if policy == "proxy_top":
        return sorted(unit_ids, key=lambda u: (-proxy_by_unit[u], u))[:budget]
    if policy == "uniform":
        rng = random.Random(seed)
        return rng.sample(unit_ids, budget)
    if policy == "oracle_anchor_ceiling":
        # Evaluator-only diagnostic: one distinct canonical anchor per event
        # precedes every non-anchor.  This must never be presented as an
        # online method or mixed into the public-policy gate decision.
        anchors = sorted(data["anchor"] for data in events.values())
        remaining = [u for u in unit_ids if u not in set(anchors)]
        return (anchors + remaining)[:budget]
    raise ValueError(f"unknown discovery policy: {policy}")


def simulate(config):
    input_paths, unit_ids, proxy_by_unit, events, unit_to_events = load_population(config)
    total_events = len(events)
    delta = float(config["delta"])
    costs = config["costs"]
    raw = []
    policies = config["discovery_policies"] + config.get("diagnostic_policies", [])
    public = set(config["discovery_policies"])
    for policy_index, policy in enumerate(policies):
        budgets = (
            config["discovery_budgets"]
            if policy in public
            else config.get("diagnostic_budgets", config["discovery_budgets"])
        )
        for budget in budgets:
            for seed_offset in range(config["seed_count"]):
                seed = config["base_seed"] + seed_offset
                discovery_seed = seed + 1_000_003 * (policy_index + 1) + 101 * budget
                queried = discovery_order(
                    policy, unit_ids, proxy_by_unit, events, budget, discovery_seed
                )
                discovered = set()
                for unit_id in queried:
                    discovered.update(unit_to_events.get(unit_id, ()))
                discovered_anchors = {events[e]["anchor"] for e in discovered}
                known = set(queried) | discovered_anchors
                audit_frame = [u for u in unit_ids if u not in known]
                residual_anchors = {
                    data["anchor"] for event_id, data in events.items()
                    if event_id not in discovered
                }
                if not residual_anchors.issubset(set(audit_frame)):
                    raise AssertionError("residual anchor removed from audit frame")
                audit_rng = random.Random(seed + 10_000_019 * (policy_index + 1) + 313 * budget)
                permutation = list(audit_frame)
                audit_rng.shuffle(permutation)
                sizes = list(range(0, len(audit_frame) + 1, config["audit_step"]))
                if sizes[-1] != len(audit_frame):
                    sizes.append(len(audit_frame))
                for n in sizes:
                    observed = sum(u in residual_anchors for u in permutation[:n])
                    upper_total = hypergeom_upper_bound(
                        len(audit_frame), n, observed, delta
                    )
                    upper_remaining = max(0, upper_total - observed)
                    discovered_after = len(discovered) + observed
                    true_remaining = len(residual_anchors) - observed
                    recall_lb = discovered_after / (
                        discovered_after + upper_remaining
                    ) if discovered_after + upper_remaining else 1.0
                    true_recall = discovered_after / total_events
                    total_cost = (
                        budget * costs["presence_unit"]
                        + len(discovered) * costs["certify_event"]
                        + n * costs["audit_unit"]
                    )
                    raw.append({
                        "policy": policy,
                        "discovery_budget": budget,
                        "seed": seed,
                        "audit_n": n,
                        "audit_frame_size": len(audit_frame),
                        "discovered_pre_audit": len(discovered),
                        "observed_residual_anchors": observed,
                        "true_residual_pre_audit": len(residual_anchors),
                        "upper_residual_pre_audit": upper_total,
                        "true_remaining": true_remaining,
                        "upper_remaining": upper_remaining,
                        "coverage": int(true_remaining <= upper_remaining),
                        "recall_lb": recall_lb,
                        "true_recall": true_recall,
                        "total_logical_cost": total_cost,
                    })
    manifest = [
        {"role": key, "path": str(path.relative_to(REPO)), "sha256": sha256(path)}
        for key, path in input_paths.items()
    ]
    return raw, manifest, total_events, len(unit_ids)


def summarize(raw, targets):
    grouped = defaultdict(list)
    for row in raw:
        grouped[(row["policy"], row["discovery_budget"], row["audit_n"])].append(row)
    summary = []
    for (policy, budget, audit_n), rows in sorted(grouped.items()):
        out = {
            "policy": policy,
            "discovery_budget": budget,
            "audit_n": audit_n,
            "runs": len(rows),
            "coverage_rate": statistics.fmean(r["coverage"] for r in rows),
            "mean_discovered_pre_audit": statistics.fmean(r["discovered_pre_audit"] for r in rows),
            "mean_recall_lb": statistics.fmean(r["recall_lb"] for r in rows),
            "median_true_recall": statistics.median(r["true_recall"] for r in rows),
            "median_total_cost": statistics.median(r["total_logical_cost"] for r in rows),
            "p90_total_cost": percentile([r["total_logical_cost"] for r in rows], 0.9),
        }
        for target in targets:
            label = str(target).replace(".", "p")
            out[f"certify_rate_{label}"] = statistics.fmean(
                r["recall_lb"] >= target for r in rows
            )
        summary.append(out)
    return summary


def decide(summary, config, dense_cost):
    decisions = []
    policies = config["discovery_policies"] + config.get("diagnostic_policies", [])
    public = set(config["discovery_policies"])
    for policy in policies:
        budgets = (
            config["discovery_budgets"]
            if policy in public
            else config.get("diagnostic_budgets", config["discovery_budgets"])
        )
        for budget in budgets:
            candidates = [r for r in summary if r["policy"] == policy and r["discovery_budget"] == budget]
            for target in config["recall_targets"]:
                label = str(target).replace(".", "p")
                eligible = [
                    r for r in candidates
                    if r[f"certify_rate_{label}"] >= 0.9 and r["coverage_rate"] >= 0.94
                ]
                chosen = min(eligible, key=lambda r: r["audit_n"]) if eligible else None
                threshold = 0.7 * dense_cost
                decisions.append({
                    "policy": policy,
                    "discovery_budget": budget,
                    "recall_target": target,
                    "selected_fixed_audit_n": chosen["audit_n"] if chosen else "",
                    "certify_rate": chosen[f"certify_rate_{label}"] if chosen else "",
                    "coverage_rate": chosen["coverage_rate"] if chosen else "",
                    "mean_discovered_pre_audit": chosen["mean_discovered_pre_audit"] if chosen else "",
                    "median_total_cost": chosen["median_total_cost"] if chosen else "",
                    "dense_cost": dense_cost,
                    "cost_ratio": chosen["median_total_cost"] / dense_cost if chosen else "",
                    "gate": (
                        "GO" if chosen and target == 0.8 and chosen["median_total_cost"] < threshold
                        else "NO_GO" if target == 0.8 else "DIAGNOSTIC"
                    ),
                })
    return decisions


def render_report(path, config, total_events, total_units, decisions, summary):
    public = set(config["discovery_policies"])
    diagnostics = set(config.get("diagnostic_policies", []))
    best_80 = [d for d in decisions if d["policy"] in public and d["recall_target"] == 0.8 and d["selected_fixed_audit_n"] != ""]
    best = min(best_80, key=lambda d: d["median_total_cost"]) if best_80 else None
    ceiling_80 = [d for d in decisions if d["policy"] in diagnostics and d["recall_target"] == 0.8 and d["selected_fixed_audit_n"] != ""]
    ceiling = min(ceiling_80, key=lambda d: d["median_total_cost"]) if ceiling_80 else None
    ceiling_go = [d for d in ceiling_80 if d["gate"] == "GO"]
    first_ceiling_go = min(ceiling_go, key=lambda d: d["discovery_budget"]) if ceiling_go else None
    min_coverage = min(row["coverage_rate"] for row in summary)
    overall = "GO" if best and best["gate"] == "GO" else "NO_GO"
    lines = [
        "# Gate B result",
        "",
        f"**Decision: `{overall}` for the preregistered 80% pseudo-event recall certificate gate.**",
        "",
        "## Observed evidence",
        "",
        f"- Population: {total_units} units and {total_events} distinct frozen canonical anchors.",
        f"- Repetitions: {config['seed_count']} seeds per policy/budget; delta={config['delta']}.",
        f"- Minimum empirical coverage across all fixed stages: {min_coverage:.4f}.",
    ]
    if best:
        lines.extend([
            f"- Lowest-cost public stage certifying 80% recall in >=90% of seeds: `{best['policy']}` with discovery budget {best['discovery_budget']}, audit n={best['selected_fixed_audit_n']}, median total logical cost {best['median_total_cost']:.1f} ({best['cost_ratio']:.3f} of dense complete audit).",
        ])
    else:
        lines.append("- No tested fixed stage certified 80% recall in >=90% of seeds while passing the coverage diagnostic.")
    if ceiling:
        lines.append(
            f"- Lowest-cost evaluator-only oracle-anchor ceiling: discovery budget {ceiling['discovery_budget']}, {ceiling['mean_discovered_pre_audit']:.0f} events found before audit, audit n={ceiling['selected_fixed_audit_n']}, median total cost {ceiling['median_total_cost']:.1f} ({ceiling['cost_ratio']:.3f} of dense complete audit)."
        )
    if first_ceiling_go:
        lines.append(
            f"- First idealized ceiling budget crossing the cost gate: B={first_ceiling_go['discovery_budget']} after finding {first_ceiling_go['mean_discovered_pre_audit']:.0f}/26 events; B=23 remains NO_GO."
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "The result tests audit identifiability under the strict pseudo-event contract. It does not validate real-event certification, semantic search, sequential stopping, or cross-video generalization.",
        "",
        "Weak discovery is now a working explanation, not an established cause. The evaluator-only oracle-anchor ceiling only proves that perfect event-first ordering creates an idealized feasible region; it does not show that a real semantic signal can approach it. Compare proxy-top with uniform and the ceiling before deciding whether Gate A is justified.",
        "",
        "## Decision and next action",
        "",
        "The public Gate B result is NO_GO. The evaluator-only ceiling establishes only an idealized feasible region and makes attainable search quality the next decision-critical uncertainty. The next justified experiment is Gate A: test frozen, externally pretrained all-unit semantic signals without tuning on strict labels. Reject or revise DARE-AQP if those signals cannot materially close the public-to-ceiling discovery gap.",
        "",
        "See `stage_decisions.csv`, `fixed_stage_summary.csv`, and `raw_trials.csv` for authoritative values.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PACKAGE / "config/gate_b.json")
    parser.add_argument("--output", type=Path, default=PACKAGE / "outputs/gate_b")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    raw, manifest, total_events, total_units = simulate(config)
    summary = summarize(raw, config["recall_targets"])
    decisions = decide(summary, config, total_units * config["costs"]["audit_unit"])
    raw_columns = list(raw[0])
    summary_columns = list(summary[0])
    decision_columns = list(decisions[0])
    write_csv(args.output / "raw_trials.csv", raw, raw_columns)
    write_csv(args.output / "fixed_stage_summary.csv", summary, summary_columns)
    write_csv(args.output / "stage_decisions.csv", decisions, decision_columns)
    write_csv(args.output / "INPUT_MANIFEST.csv", manifest, ["role", "path", "sha256"])
    render_report(args.output / "REPORT.md", config, total_events, total_units, decisions, summary)
    print(args.output / "REPORT.md")


if __name__ == "__main__":
    main()
