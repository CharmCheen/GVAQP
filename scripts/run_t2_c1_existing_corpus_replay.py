"""C1 descriptive replay on six cached VLM-relative video-query workloads."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics

from garc.causal_frontier import (
    Candidate,
    CausalFrontierReplay,
    ConstantCostModel,
    DatbSVPolicy,
    EventRelation,
    ExSampleEndToEndPolicy,
    LargestGapPolicy,
    MappingOracle,
    RandomTemporalPolicy,
    ScanCell,
    SequentialPolicy,
    UniformStridePolicy,
)
import run_h2_synthetic_mechanism_v1 as h2v1
import run_h2_synthetic_mechanism_v3 as h2v3


SCHEMA_VERSION = "T2_C1_EXISTING_CORPUS_REPLAY_V1"
VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
COST_RATIOS = (1.0, 3.0, 10.0, 30.0)
DEADLINE_FRACTIONS = (0.20, 0.40, 0.60)
EXSAMPLE_CHUNKS = (3, 6, 12)


def load_proxy(root: Path) -> dict[str, list[dict]]:
    output = {}
    for video in VIDEOS:
        path = root / video / "raw_unit_detections.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows.sort(key=lambda item: (float(item["start_sec"]), item["unit_id"]))
        output[video] = rows
    return output


def load_outcomes(path: Path) -> dict[tuple[str, str], list[dict]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["video_id"], row["query_id"]), []).append(row)
    for values in grouped.values():
        values.sort(key=lambda item: (float(item["start_time"]), item["unit_id"]))
    return grouped


def build_workload(proxy_rows: list[dict], outcome_rows: list[dict]):
    outcomes = {row["unit_id"]: row for row in outcome_rows}
    if {row["unit_id"] for row in proxy_rows} != set(outcomes):
        raise RuntimeError("proxy and semantic unit sets do not align")

    event_for_unit: dict[str, str] = {}
    event_count = 0
    previous_end = None
    previous_relevant = False
    for row in outcome_rows:
        relevant = row["label"] == "relevant"
        start = float(row["start_time"])
        if relevant and not (
            previous_relevant
            and previous_end is not None
            and abs(start - previous_end) <= 1e-9
        ):
            event_count += 1
        if relevant:
            event_for_unit[row["unit_id"]] = f"model-event-{event_count:04d}"
        previous_relevant = relevant
        previous_end = float(row["end_time"])
    if event_count <= 0:
        raise RuntimeError("workload has no cached relevant event")

    cells = []
    results = {}
    failures = set()
    for proxy in proxy_rows:
        unit_id = proxy["unit_id"]
        outcome = outcomes[unit_id]
        start = float(proxy["start_sec"])
        end = float(proxy["end_sec"])
        score = 0.5 * min(int(proxy["det_count"]), 20) / 20.0 + 0.5 * float(proxy["max_conf"])
        candidate_id = f"candidate:{unit_id}"
        candidate = Candidate(candidate_id, unit_id, start, end, score)
        cells.append(ScanCell(unit_id, start, end, (candidate,)))
        events = ()
        if outcome["label"] == "relevant":
            model_event = event_for_unit[unit_id]
            events = (
                EventRelation(
                    f"relation:{unit_id}",
                    start,
                    end,
                    (model_event,),
                ),
            )
        elif outcome["label"] in {"unknown", "parse_failure"}:
            failures.update({candidate_id, f"fallback:{unit_id}"})
        elif outcome["label"] != "not_relevant":
            raise RuntimeError(f"unknown cached label: {outcome['label']}")
        results[candidate_id] = events
        results[f"fallback:{unit_id}"] = events
    return cells, MappingOracle(results, frozenset(failures)), event_count, len(failures) // 2


def select_fixed_windows(proxy_rows: list[dict], outcome_rows: list[dict]):
    partial = [
        row
        for row in proxy_rows
        if abs((float(row["end_sec"]) - float(row["start_sec"])) - 10.0) > 1e-9
    ]
    if len(partial) != 1 or partial[0]["unit_id"] != proxy_rows[-1]["unit_id"]:
        raise RuntimeError("expected exactly one trailing partial unit per video")
    excluded_id = partial[0]["unit_id"]
    fixed_proxy = [row for row in proxy_rows if row["unit_id"] != excluded_id]
    fixed_outcomes = [row for row in outcome_rows if row["unit_id"] != excluded_id]
    excluded_outcomes = [row for row in outcome_rows if row["unit_id"] == excluded_id]
    if len(excluded_outcomes) != 1:
        raise RuntimeError("trailing partial unit does not have exactly one query outcome")
    return fixed_proxy, fixed_outcomes, excluded_id, excluded_outcomes[0]["label"]


def run_policy(cells, oracle, event_count, ratio, fraction, policy):
    deadline = len(cells) * (1.0 + ratio) * fraction
    result = CausalFrontierReplay(
        cells,
        oracle,
        ConstantCostModel(1.0, ratio),
        deadline,
        event_count,
    ).run(policy)
    return {
        "policy": policy.name,
        "normalized_anytime_event_auc": result.normalized_anytime_event_auc,
        "terminal_event_recall": result.terminal_event_recall,
        "committed_events": len(result.committed_events),
        "oracle_failures": sum(entry.oracle_status == "FAILURE" for entry in result.trace),
        "scan_actions": sum(entry.action == "SCAN" and entry.status == "COMPLETED" for entry in result.trace),
        "verify_actions": sum(entry.action == "VERIFY" and entry.status == "COMPLETED" for entry in result.trace),
    }


def execute(proxy_root: Path, outcomes_path: Path, output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)
    proxies = load_proxy(proxy_root)
    outcomes = load_outcomes(outcomes_path)
    expected_workloads = {(video, query) for video in VIDEOS for query in sorted({key[1] for key in outcomes})}
    if set(outcomes) != expected_workloads or len(expected_workloads) != 6:
        raise RuntimeError("expected exactly three videos by two queries")

    raw_rows = []
    pair_rows = []
    workload_metadata = []
    for video, query in sorted(outcomes):
        fixed_proxy, fixed_outcomes, excluded_id, excluded_label = select_fixed_windows(
            proxies[video], outcomes[(video, query)]
        )
        cells, oracle, event_count, cached_failures = build_workload(
            fixed_proxy, fixed_outcomes
        )
        workload_id = f"{video}::{query}"
        workload_metadata.append(
            {
                "workload_id": workload_id,
                "video_id": video,
                "query_id": query,
                "units": len(cells),
                "model_relative_events": event_count,
                "cached_failure_units": cached_failures,
                "excluded_trailing_partial_unit": excluded_id,
                "excluded_trailing_partial_label": excluded_label,
            }
        )
        for ratio in COST_RATIOS:
            for deadline_level, fraction in enumerate(DEADLINE_FRACTIONS):
                for seed in h2v3.HOLDOUT_SEEDS:
                    common = {
                        "workload_id": workload_id,
                        "video_id": video,
                        "query_id": query,
                        "cost_tier": "C1_SIMULATED",
                        "verify_scan_cost_ratio": ratio,
                        "deadline_level": deadline_level,
                        "deadline_fraction": fraction,
                        "base_seed": seed,
                    }
                    policies = (
                        SequentialPolicy(),
                        UniformStridePolicy(stride=5),
                        RandomTemporalPolicy(h2v1.stable_seed(deadline_level, seed)),
                        LargestGapPolicy(),
                        DatbSVPolicy(),
                    )
                    results_by_policy = {}
                    for policy in policies:
                        result = run_policy(cells, oracle, event_count, ratio, fraction, policy)
                        row = {**common, "chunk_count": "", **result}
                        raw_rows.append(row)
                        results_by_policy[policy.name] = row
                    exsample_rows = []
                    for chunks in EXSAMPLE_CHUNKS:
                        policy_seed = h2v1.stable_seed(chunks + deadline_level, seed)
                        result = run_policy(
                            cells,
                            oracle,
                            event_count,
                            ratio,
                            fraction,
                            ExSampleEndToEndPolicy(policy_seed, chunk_count=chunks),
                        )
                        row = {**common, "chunk_count": chunks, **result}
                        raw_rows.append(row)
                        exsample_rows.append(row)
                    envelope = max(
                        exsample_rows,
                        key=lambda item: (
                            item["normalized_anytime_event_auc"],
                            item["terminal_event_recall"],
                            -int(item["chunk_count"]),
                        ),
                    )
                    datb = results_by_policy["datb_sv"]
                    largest = results_by_policy["largest_gap"]
                    pair_rows.append(
                        {
                            **common,
                            "datb_auc": datb["normalized_anytime_event_auc"],
                            "largest_gap_auc": largest["normalized_anytime_event_auc"],
                            "exsample_envelope_auc": envelope["normalized_anytime_event_auc"],
                            "exsample_selected_chunk_count": envelope["chunk_count"],
                            "delta_datb_exsample_auc": datb["normalized_anytime_event_auc"] - envelope["normalized_anytime_event_auc"],
                            "delta_datb_largest_gap_auc": datb["normalized_anytime_event_auc"] - largest["normalized_anytime_event_auc"],
                            "delta_datb_exsample_events": datb["committed_events"] - envelope["committed_events"],
                        }
                    )

    deltas = [float(row["delta_datb_exsample_auc"]) for row in pair_rows]
    workload_rows = []
    for metadata in workload_metadata:
        selected = [row for row in pair_rows if row["workload_id"] == metadata["workload_id"]]
        workload_rows.append(
            {
                **metadata,
                "mean_datb_exsample_auc_delta": statistics.fmean(float(row["delta_datb_exsample_auc"]) for row in selected),
                "mean_datb_largest_gap_auc_delta": statistics.fmean(float(row["delta_datb_largest_gap_auc"]) for row in selected),
                "fraction_datb_exsample_positive": statistics.fmean(float(row["delta_datb_exsample_auc"]) > 1e-12 for row in selected),
            }
        )
    label_counts = {}
    for rows in outcomes.values():
        for row in rows:
            label_counts[row["label"]] = label_counts.get(row["label"], 0) + 1
    summary = {
        "schema_version": SCHEMA_VERSION,
        "classification": "C1_simulated_model_relative_descriptive_only",
        "videos": len(VIDEOS),
        "queries": 2,
        "video_query_workloads": 6,
        "raw_semantic_rows": sum(len(rows) for rows in outcomes.values()),
        "proxy_units": sum(len(rows) for rows in proxies.values()),
        "label_counts": label_counts,
        "total_policy_replays": len(raw_rows),
        "paired_rows": len(pair_rows),
        "mean_datb_exsample_auc_delta": statistics.fmean(deltas),
        "median_datb_exsample_auc_delta": statistics.median(deltas),
        "positive_equal_negative_pairs": {
            "positive": sum(value > 1e-12 for value in deltas),
            "equal": sum(abs(value) <= 1e-12 for value in deltas),
            "negative": sum(value < -1e-12 for value in deltas),
        },
        "workloads_datb_mean_positive": sum(float(row["mean_datb_exsample_auc_delta"]) > 0 for row in workload_rows),
        "claim_status": "DESCRIPTIVE_ONLY_LOW_INDEPENDENT_SAMPLE_SUPPORT_NO_HUMAN_EVENTS_NO_C3",
        "workload_results": workload_rows,
    }
    h2v1.write_csv(output / "workload_metadata.csv", workload_metadata)
    h2v1.write_csv(output / "raw_policy_results.csv", raw_rows)
    h2v1.write_csv(output / "paired_results.csv", pair_rows)
    h2v1.write_csv(output / "workload_results.csv", workload_rows)
    (output / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = f"""# T2-C1 Existing-Corpus Descriptive Replay\n\n## Verdict\n\n`C1_DESCRIPTIVE_ONLY`\n\n- Workloads: 6 video-query cells from 3 videos and 2 queries\n- Policy replays: {summary['total_policy_replays']}\n- Mean DATB-minus-ExSample AUC: {summary['mean_datb_exsample_auc_delta']:.6f}\n- Median DATB-minus-ExSample AUC: {summary['median_datb_exsample_auc_delta']:.6f}\n- Positive/equal/negative paired rows: {summary['positive_equal_negative_pairs']['positive']}/{summary['positive_equal_negative_pairs']['equal']}/{summary['positive_equal_negative_pairs']['negative']}\n- Workloads with positive mean delta: {summary['workloads_datb_mean_positive']}/6\n- Cached labels: {json.dumps(label_counts, sort_keys=True)}\n\n## Claim boundary\n\n`{summary['claim_status']}`\n\nEvery unit had a precomputed query-agnostic proxy candidate. Events are contiguous runs of cached VLM-relative positives, not independent human events.\n"""
    (output / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy-root", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execute(args.proxy_root.resolve(), args.outcomes.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
