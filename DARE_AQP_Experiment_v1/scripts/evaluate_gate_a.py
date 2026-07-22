#!/usr/bin/env python3
"""Evaluate frozen all-unit scores and feed each ranking into Gate B."""

import argparse
import csv
import hashlib
import json
import math
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


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("empty output")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_population(config):
    paths = {key: REPO / value for key, value in config["inputs"].items()}
    units = read_csv(paths["units"])
    events_raw = read_csv(paths["events"])
    unit_ids = [int(row["unit_id"]) for row in units]
    if unit_ids != list(range(len(units))):
        raise ValueError("Gate A requires contiguous unit IDs")
    events = {}
    unit_to_events = defaultdict(set)
    for row in events_raw:
        source = {int(value) for value in row["source_unit_ids"].split("|")}
        anchor_time = float(row["canonical_anchor_time"])
        matches = [
            int(unit["unit_id"]) for unit in units
            if float(unit["start_time"]) <= anchor_time < float(unit["end_time"])
        ]
        if len(matches) != 1:
            raise ValueError("non-unique anchor mapping")
        event_id = row["reference_event_id"]
        events[event_id] = {"anchor": matches[0], "source": source}
        for unit_id in source:
            unit_to_events[unit_id].add(event_id)
    anchors = [value["anchor"] for value in events.values()]
    if len(anchors) != len(set(anchors)):
        raise ValueError("duplicate anchor units")
    return paths, unit_ids, events, unit_to_events


def load_scores(score_path, config, unit_ids, final_mode=False):
    if score_path is None:
        proxy_path = REPO / config["inputs"]["public_proxy"]
        rows = [
            {
                "signal_id": "current_proxy",
                "unit_id": row["frame_idx"],
                "score": row["proxy_score"],
                "model_id": "strict_public_proxy",
                "model_revision": sha256(proxy_path),
                "prompt_id": "not_applicable",
            }
            for row in read_csv(proxy_path)
        ]
        source = proxy_path
    else:
        rows = read_csv(score_path)
        source = score_path
    required = {"signal_id", "unit_id", "score", "model_id", "model_revision", "prompt_id"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"score file missing columns: {sorted(required)}")
    scores = defaultdict(dict)
    metadata = {}
    for row in rows:
        signal = row["signal_id"]
        unit = int(row["unit_id"])
        score = float(row["score"])
        if not math.isfinite(score) or unit in scores[signal]:
            raise ValueError("non-finite score or duplicate signal/unit")
        scores[signal][unit] = score
        row_metadata = (row["model_id"], row["model_revision"], row["prompt_id"])
        if signal in metadata and metadata[signal] != row_metadata:
            raise ValueError(f"inconsistent metadata within signal {signal}")
        metadata[signal] = row_metadata
    expected = set(unit_ids)
    for signal, mapping in scores.items():
        if set(mapping) != expected:
            raise ValueError(f"signal {signal} does not cover all units")
    if final_mode:
        frozen = config["methods"]
        if set(scores) != set(frozen):
            raise ValueError(
                f"final mode requires exactly {sorted(frozen)}, got {sorted(scores)}"
            )
        for signal, method in frozen.items():
            expected_metadata = (
                method["model_id"], method["revision"], method["prompt_id"]
            )
            if metadata[signal] != expected_metadata:
                raise ValueError(
                    f"signal {signal} metadata {metadata[signal]} != frozen {expected_metadata}"
                )
    return source, scores, metadata


def average_precision(labels, scores, unit_ids):
    positives = sum(labels.values())
    if positives == 0:
        return float("nan")
    order = sorted(unit_ids, key=lambda unit: (-scores[unit], unit))
    found = 0
    total = 0.0
    for rank, unit in enumerate(order, 1):
        if labels[unit]:
            found += 1
            total += found / rank
    return total / positives


def auroc(labels, scores, unit_ids):
    positive = [unit for unit in unit_ids if labels[unit]]
    negative = [unit for unit in unit_ids if not labels[unit]]
    wins = 0.0
    for pos in positive:
        for neg in negative:
            wins += scores[pos] > scores[neg]
            wins += 0.5 * (scores[pos] == scores[neg])
    return wins / (len(positive) * len(negative))


def blocked_metrics(labels, scores, unit_ids, block_count):
    values = []
    for block in range(block_count):
        lo = len(unit_ids) * block // block_count
        hi = len(unit_ids) * (block + 1) // block_count
        block_units = unit_ids[lo:hi]
        positives = sum(labels[unit] for unit in block_units)
        if positives and positives < len(block_units):
            values.append((
                auroc(labels, scores, block_units),
                average_precision(labels, scores, block_units),
            ))
    if not values:
        return float("nan"), float("nan"), 0
    return (
        statistics.fmean(value[0] for value in values),
        statistics.fmean(value[1] for value in values),
        len(values),
    )


def ranking_metrics(scores_by_signal, unit_ids, events, unit_to_events, top_k, block_count):
    anchor_set = {value["anchor"] for value in events.values()}
    presence_set = set(unit_to_events)
    anchor_labels = {unit: unit in anchor_set for unit in unit_ids}
    presence_labels = {unit: unit in presence_set for unit in unit_ids}
    rows = []
    for signal, scores in sorted(scores_by_signal.items()):
        order = sorted(unit_ids, key=lambda unit: (-scores[unit], unit))
        anchor_block_auc, anchor_block_ap, anchor_blocks = blocked_metrics(
            anchor_labels, scores, unit_ids, block_count
        )
        presence_block_auc, presence_block_ap, presence_blocks = blocked_metrics(
            presence_labels, scores, unit_ids, block_count
        )
        base = {
            "signal_id": signal,
            "full_video_anchor_auroc_descriptive": auroc(anchor_labels, scores, unit_ids),
            "full_video_anchor_ap_descriptive": average_precision(anchor_labels, scores, unit_ids),
            "full_video_presence_auroc_descriptive": auroc(presence_labels, scores, unit_ids),
            "full_video_presence_ap_descriptive": average_precision(presence_labels, scores, unit_ids),
            "blocked_anchor_auroc_macro": anchor_block_auc,
            "blocked_anchor_ap_macro": anchor_block_ap,
            "blocked_anchor_valid_blocks": anchor_blocks,
            "blocked_presence_auroc_macro": presence_block_auc,
            "blocked_presence_ap_macro": presence_block_ap,
            "blocked_presence_valid_blocks": presence_blocks,
        }
        for k in top_k:
            selected = order[:k]
            found = set()
            for unit in selected:
                found.update(unit_to_events.get(unit, ()))
            base[f"top_{k}_distinct_events"] = len(found)
            base[f"top_{k}_event_recall"] = len(found) / len(events)
            base[f"top_{k}_anchor_coverage"] = sum(unit in anchor_set for unit in selected) / len(events)
        rows.append(base)
    return rows


def run_gate_b(scores_by_signal, unit_ids, events, unit_to_events, config):
    gate = config["gate_b"]
    total_events = len(events)
    dense_cost = len(unit_ids) * gate["audit_unit_cost"]
    summary_rows = []
    for signal, scores in sorted(scores_by_signal.items()):
        if signal not in config["methods"]:
            raise ValueError(f"unknown signal {signal}; no frozen seed namespace")
        signal_namespace = int(config["methods"][signal]["seed_namespace"])
        order = sorted(unit_ids, key=lambda unit: (-scores[unit], unit))
        for budget in config["top_k"]:
            selected = order[:budget]
            discovered = set()
            for unit in selected:
                discovered.update(unit_to_events.get(unit, ()))
            discovered_anchors = {events[event]["anchor"] for event in discovered}
            frame = [unit for unit in unit_ids if unit not in set(selected) | discovered_anchors]
            residual = {
                value["anchor"] for event, value in events.items() if event not in discovered
            }
            sizes = list(range(0, len(frame) + 1, gate["audit_step"]))
            if sizes[-1] != len(frame):
                sizes.append(len(frame))
            trials = defaultdict(list)
            for offset in range(gate["seed_count"]):
                seed = gate["base_seed"] + offset + 10_000_019 * (signal_namespace + 1) + 313 * budget
                permutation = list(frame)
                random.Random(seed).shuffle(permutation)
                for audit_n in sizes:
                    observed = sum(unit in residual for unit in permutation[:audit_n])
                    upper = hypergeom_upper_bound(
                        len(frame), audit_n, observed, gate["delta"]
                    )
                    upper_remaining = upper - observed
                    found_after = len(discovered) + observed
                    recall_lb = found_after / (found_after + upper_remaining)
                    cost = (
                        budget * gate["presence_unit_cost"]
                        + len(discovered) * gate["certify_event_cost"]
                        + audit_n * gate["audit_unit_cost"]
                    )
                    trials[audit_n].append((
                        int(len(residual) - observed <= upper_remaining),
                        int(recall_lb >= gate["recall_target"]),
                        cost,
                    ))
            candidates = []
            for audit_n, values in sorted(trials.items()):
                coverage = statistics.fmean(value[0] for value in values)
                certify_rate = statistics.fmean(value[1] for value in values)
                median_cost = statistics.median(value[2] for value in values)
                if (
                    coverage >= gate["coverage_diagnostic_required"]
                    and certify_rate >= gate["certify_rate_required"]
                ):
                    candidates.append((audit_n, coverage, certify_rate, median_cost))
            chosen = min(candidates) if candidates else None
            median_cost = chosen[3] if chosen else float("inf")
            summary_rows.append({
                "signal_id": signal,
                "discovery_budget": budget,
                "events_discovered_pre_audit": len(discovered),
                "selected_fixed_audit_n": chosen[0] if chosen else "",
                "coverage_rate": chosen[1] if chosen else "",
                "certify_rate": chosen[2] if chosen else "",
                "median_total_cost": "" if chosen is None else median_cost,
                "dense_complete_audit_cost": dense_cost,
                "cost_ratio": "" if chosen is None else median_cost / dense_cost,
                "gate": "GO" if chosen and median_cost / dense_cost < gate["go_cost_ratio"] else "NO_GO",
            })
    return summary_rows


def render_report(path, score_source, metrics, gate_rows, final_mode):
    go = [row for row in gate_rows if row["gate"] == "GO"]
    logical_result = "GATE_A_LOGICAL_ORACLE_GO" if go else "UNIT_ORACLE_DARE_ACCELERATION_NO_GO"
    decision = logical_result if final_mode else "PREFLIGHT_ONLY"
    lines = [
        "# Gate A frozen-score evaluation",
        "",
        f"**Decision status: `{decision}`.**",
        "",
        f"Score source: `{score_source}`.",
        "",
        f"Logical-oracle result over supplied signals: `{logical_result}`.",
        "",
        "End-to-end acceleration is `NOT_ESTABLISHED`: semantic-index and warm-query runtime are reported separately and are not denominated in logical oracle calls.",
        "",
        "Final mode is eligible only after exact four-signal metadata validation. Preflight mode cannot issue a final Gate A decision.",
        "",
        "See `ranking_metrics.csv` and `gate_b_link.csv` for authoritative values.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PACKAGE / "config/gate_a_frozen.json")
    parser.add_argument("--scores", type=Path)
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--output", type=Path, default=PACKAGE / "outputs/gate_a_preflight")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    paths, unit_ids, events, unit_to_events = load_population(config)
    if args.final and args.scores is None:
        raise ValueError("--final requires an explicit four-signal score file")
    score_source, scores, metadata = load_scores(
        args.scores, config, unit_ids, final_mode=args.final
    )
    metrics = ranking_metrics(
        scores, unit_ids, events, unit_to_events,
        config["top_k"], config["temporal_block_count"],
    )
    gate_rows = run_gate_b(scores, unit_ids, events, unit_to_events, config)
    write_csv(args.output / "ranking_metrics.csv", metrics)
    write_csv(args.output / "gate_b_link.csv", gate_rows)
    manifest = [
        {"role": key, "path": str(path.relative_to(REPO)), "sha256": sha256(path)}
        for key, path in paths.items()
    ]
    manifest.append({
        "role": "scores",
        "path": str(score_source),
        "sha256": sha256(score_source),
    })
    write_csv(args.output / "INPUT_MANIFEST.csv", manifest)
    render_report(
        args.output / "REPORT.md", score_source, metrics, gate_rows, args.final
    )
    print(args.output / "REPORT.md")


if __name__ == "__main__":
    main()
