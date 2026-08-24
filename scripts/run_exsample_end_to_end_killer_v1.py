"""CPU-only DATB versus ExSample-EndToEnd-Adapted killer comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

from garc.causal_frontier import (
    CausalFrontierReplay,
    ConstantCostModel,
    DatbSVPolicy,
    ExSampleEndToEndPolicy,
)
import run_h2_synthetic_mechanism_v1 as v1
import run_h2_synthetic_mechanism_v3 as v3


SCHEMA_VERSION = "EXSAMPLE_END_TO_END_ADAPTED_KILLER_V1"
CHUNK_COUNTS = (3, 6, 12)


def full_design() -> list[dict]:
    rows = []
    workload_id = 0
    for a in range(3):
        for b in range(3):
            for c in range(3):
                for d in range(3):
                    for e, ratio in enumerate(v1.COST_RATIOS):
                        for f in range(3):
                            rows.append(
                                {
                                    "workload_id": workload_id,
                                    "design_id": workload_id,
                                    "A_density": a,
                                    "B_temporal_modes": b,
                                    "C_event_duration": c,
                                    "D_proxy_noise": d,
                                    "E_cost_ratio": e,
                                    "verify_scan_cost_ratio": ratio,
                                    "F_deadline": f,
                                }
                            )
                        workload_id += 1
    if len(rows) != 972:
        raise AssertionError("full killer design must have 972 workload-deadline rows")
    return rows


def run_policy(row: dict, seed: int, policy) -> dict:
    cells, oracle, reference_count = v1.generate_workload(row, seed)
    ratio = float(row["verify_scan_cost_ratio"])
    deadline = (
        v1.N_CELLS
        * (1.0 + ratio)
        * v1.DEADLINE_FRACTIONS[int(row["F_deadline"])]
    )
    engine = CausalFrontierReplay(
        cells,
        oracle,
        ConstantCostModel(1.0, ratio),
        deadline,
        reference_count,
    )
    result = engine.run(policy)
    return {
        **row,
        "base_seed": seed,
        "policy": policy.name,
        "chunk_count": "",
        "normalized_anytime_event_auc": result.normalized_anytime_event_auc,
        "terminal_event_recall": result.terminal_event_recall,
        "committed_events": len(result.committed_events),
        "scan_actions": sum(entry.action == "SCAN" and entry.status == "COMPLETED" for entry in result.trace),
        "verify_actions": sum(entry.action == "VERIFY" and entry.status == "COMPLETED" for entry in result.trace),
    }


def execute(output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)
    design = full_design()
    v1.write_csv(output / "frozen_full_deadline_design.csv", design)
    raw_rows = []
    pair_rows = []
    for row in design:
        for seed in v3.HOLDOUT_SEEDS:
            datb = run_policy(row, seed, DatbSVPolicy())
            raw_rows.append(datb)
            exsample_rows = []
            for chunks in CHUNK_COUNTS:
                policy_seed = v1.stable_seed(int(row["workload_id"]), seed) ^ chunks
                result = run_policy(
                    row,
                    seed,
                    ExSampleEndToEndPolicy(policy_seed, chunk_count=chunks),
                )
                result["chunk_count"] = chunks
                raw_rows.append(result)
                exsample_rows.append(result)
            envelope = max(
                exsample_rows,
                key=lambda item: (
                    item["normalized_anytime_event_auc"],
                    item["terminal_event_recall"],
                    -item["chunk_count"],
                ),
            )
            datb_auc = float(datb["normalized_anytime_event_auc"])
            exsample_auc = float(envelope["normalized_anytime_event_auc"])
            pair_rows.append(
                {
                    **row,
                    "base_seed": seed,
                    "datb_auc": datb_auc,
                    "exsample_envelope_auc": exsample_auc,
                    "exsample_selected_chunk_count": envelope["chunk_count"],
                    "delta_auc": datb_auc - exsample_auc,
                    "relative_delta_auc": (datb_auc - exsample_auc) / max(exsample_auc, 0.01),
                    "datb_events": datb["committed_events"],
                    "exsample_events": envelope["committed_events"],
                    "delta_events": int(datb["committed_events"])
                    - int(envelope["committed_events"]),
                }
            )

    grouped: dict[tuple[int, int], list[dict]] = {}
    for row in pair_rows:
        grouped.setdefault((int(row["workload_id"]), int(row["base_seed"])), []).append(row)
    adjacent_rows = []
    for (workload_id, seed), rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda item: int(item["F_deadline"]))
        deltas = [int(row["delta_events"]) for row in ordered]
        adjacent_pass = bool(
            (deltas[0] >= 1 and deltas[1] >= 1)
            or (deltas[1] >= 1 and deltas[2] >= 1)
        )
        adjacent_rows.append(
            {
                "workload_id": workload_id,
                "base_seed": seed,
                "delta_events_deadline_20": deltas[0],
                "delta_events_deadline_40": deltas[1],
                "delta_events_deadline_60": deltas[2],
                "adjacent_deadline_extra_event_pass": adjacent_pass,
            }
        )

    relative = [float(row["relative_delta_auc"]) for row in pair_rows]
    absolute = [float(row["delta_auc"]) for row in pair_rows]
    cost30 = [
        float(row["delta_auc"])
        for row in pair_rows
        if float(row["verify_scan_cost_ratio"]) == 30.0
    ]
    median_relative = float(statistics.median(relative))
    adjacent_fraction = statistics.fmean(
        bool(row["adjacent_deadline_extra_event_pass"]) for row in adjacent_rows
    )
    mean_cost30 = float(statistics.fmean(cost30))
    passed = bool(
        median_relative >= 0.05
        and adjacent_fraction > 0.5
        and mean_cost30 >= 0.0
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "classification": "synthetic_killer_test_not_original_exsample_reproduction",
        "design_rows": len(design),
        "seeds": list(v3.HOLDOUT_SEEDS),
        "chunk_count_envelope": list(CHUNK_COUNTS),
        "total_policy_replays": len(raw_rows),
        "paired_rows": len(pair_rows),
        "independent_synthetic_workload_seed_groups": len(adjacent_rows),
        "mean_absolute_auc_delta": float(statistics.fmean(absolute)),
        "median_absolute_auc_delta": float(statistics.median(absolute)),
        "median_relative_auc_delta": median_relative,
        "positive_equal_negative_rows": {
            "positive": sum(value > 1e-12 for value in absolute),
            "equal": sum(abs(value) <= 1e-12 for value in absolute),
            "negative": sum(value < -1e-12 for value in absolute),
        },
        "adjacent_deadline_extra_event_fraction": adjacent_fraction,
        "mean_auc_delta_at_cost_ratio_30": mean_cost30,
        "synthetic_exsample_killer_pass": passed,
        "paper_claim_status": "BLOCKED_NATURAL_CORPUS_C3_HUMAN_MEC",
    }
    v1.write_csv(output / "raw_policy_results.csv", raw_rows)
    v1.write_csv(output / "paired_datb_exsample_envelope.csv", pair_rows)
    v1.write_csv(output / "adjacent_deadline_sesoi.csv", adjacent_rows)
    (output / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    verdict = "PASS" if passed else "FAIL"
    report = f"""# ExSample-EndToEnd-Adapted Killer Result\n\n## Verdict\n\n`{verdict}_SYNTHETIC_EXSAMPLE_KILLER`\n\n- Total policy replays: {summary['total_policy_replays']}\n- Mean absolute AUC delta: {summary['mean_absolute_auc_delta']:.6f}\n- Median relative AUC delta: {summary['median_relative_auc_delta']:.2%}\n- Positive/equal/negative rows: {summary['positive_equal_negative_rows']['positive']}/{summary['positive_equal_negative_rows']['equal']}/{summary['positive_equal_negative_rows']['negative']}\n- Adjacent-deadline extra-event fraction: {summary['adjacent_deadline_extra_event_fraction']:.2%}\n- Mean AUC delta at cost ratio 30: {summary['mean_auc_delta_at_cost_ratio_30']:.6f}\n\n## Boundary\n\nThis is an event-query adaptation of ExSample, not a reproduction of its original GPU system. `{summary['paper_claim_status']}`\n"""
    (output / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execute(args.output.resolve())


if __name__ == "__main__":
    main()
