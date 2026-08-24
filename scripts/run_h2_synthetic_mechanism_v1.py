"""Frozen CPU-only H2 synthetic mechanism screen.

This experiment tests whether temporal sparsity and multimodality change the
value of scan/verify coupling under a shared causal executor. Synthetic results
are mechanism diagnostics, never scientific evidence about natural prevalence.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import statistics
from typing import Callable

from garc.causal_frontier import (
    Candidate,
    CausalFrontierReplay,
    ConstantCostModel,
    DatbSVPolicy,
    EventRelation,
    LargestGapPolicy,
    MappingOracle,
    RandomTemporalPolicy,
    ScanCell,
    SequentialPolicy,
    UniformStridePolicy,
)


SCHEMA_VERSION = "H2_SYNTHETIC_MECHANISM_V1"
BASE_SEEDS = (1729, 3253, 4999, 7919, 104729)
COST_RATIOS = (1.0, 3.0, 10.0, 30.0)
DENSITY_EVENTS = (4, 12, 28)
TEMPORAL_MODES = (1, 2, 4)
EVENT_DURATION_CELLS = (1, 3, 6)
PROXY_NOISE_SIGMA = (0.08, 0.20, 0.35)
DEADLINE_FRACTIONS = (0.20, 0.40, 0.60)
N_CELLS = 60
CELL_SECONDS = 10.0
POLICY_NAMES = (
    "sequential",
    "uniform_stride",
    "random_temporal",
    "largest_gap",
    "datb_sv",
)


def frozen_design() -> list[dict[str, int | float]]:
    rows: list[dict[str, int | float]] = []
    design_id = 0
    for a in range(3):
        for b in range(3):
            for c in range(3):
                for d in range(3):
                    f = (a + b + c + d) % 3
                    for e, ratio in enumerate(COST_RATIOS):
                        rows.append(
                            {
                                "design_id": design_id,
                                "A_density": a,
                                "B_temporal_modes": b,
                                "C_event_duration": c,
                                "D_proxy_noise": d,
                                "E_cost_ratio": e,
                                "verify_scan_cost_ratio": ratio,
                                "F_deadline": f,
                            }
                        )
                        design_id += 1
    if len(rows) != 324:
        raise AssertionError("frozen H2 design must contain 324 points")
    return rows


def stable_seed(design_id: int, base_seed: int) -> int:
    payload = f"{SCHEMA_VERSION}:{design_id}:{base_seed}".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def generate_workload(row: dict[str, int | float], base_seed: int):
    rng = random.Random(stable_seed(int(row["design_id"]), base_seed))
    event_count = DENSITY_EVENTS[int(row["A_density"])]
    mode_count = TEMPORAL_MODES[int(row["B_temporal_modes"])]
    duration = EVENT_DURATION_CELLS[int(row["C_event_duration"])]
    noise = PROXY_NOISE_SIGMA[int(row["D_proxy_noise"])]

    mode_centers = [
        (index + 0.5) * N_CELLS / mode_count for index in range(mode_count)
    ]
    event_ranges: list[tuple[int, int, str]] = []
    spread = max(1.0, N_CELLS / (mode_count * 8.0))
    for event_index in range(event_count):
        center = mode_centers[event_index % mode_count]
        sampled_center = int(round(rng.gauss(center, spread)))
        start = max(0, min(N_CELLS - duration, sampled_center - duration // 2))
        event_ranges.append((start, start + duration, f"track-{event_index:03d}"))

    cells: list[ScanCell] = []
    oracle_results: dict[str, tuple[EventRelation, ...]] = {}
    for cell_index in range(N_CELLS):
        cell_id = f"cell-{cell_index:03d}"
        start_s = cell_index * CELL_SECONDS
        end_s = start_s + CELL_SECONDS
        active = [event for event in event_ranges if event[0] <= cell_index < event[1]]
        latent_positive = bool(active)
        score_mean = 0.80 if latent_positive else 0.20
        score = min(1.0, max(0.0, rng.gauss(score_mean, noise)))
        relations = tuple(
            EventRelation(
                relation_id=f"relation:{track_id}:{cell_index:03d}",
                start_s=start_s,
                end_s=end_s,
                participant_track_ids=(track_id,),
            )
            for _, _, track_id in active
        )
        candidates: tuple[Candidate, ...] = ()
        if score >= 0.5:
            candidate_id = f"candidate:{cell_index:03d}"
            candidates = (
                Candidate(
                    candidate_id=candidate_id,
                    cell_id=cell_id,
                    start_s=start_s,
                    end_s=end_s,
                    score=score,
                ),
            )
            oracle_results[candidate_id] = relations
        oracle_results[f"fallback:{cell_id}"] = relations
        cells.append(ScanCell(cell_id, start_s, end_s, candidates))
    return cells, MappingOracle(oracle_results), event_count


def policy_factories(seed: int) -> dict[str, Callable[[], object]]:
    return {
        "sequential": SequentialPolicy,
        "uniform_stride": lambda: UniformStridePolicy(stride=5),
        "random_temporal": lambda: RandomTemporalPolicy(seed),
        "largest_gap": LargestGapPolicy,
        "datb_sv": lambda: DatbSVPolicy(verify_score_threshold=0.5),
    }


def run_one(row: dict[str, int | float], base_seed: int, policy_name: str) -> dict:
    cells, oracle, reference_count = generate_workload(row, base_seed)
    ratio = float(row["verify_scan_cost_ratio"])
    exhaustive_cost = N_CELLS * (1.0 + ratio)
    deadline = exhaustive_cost * DEADLINE_FRACTIONS[int(row["F_deadline"])]
    engine = CausalFrontierReplay(
        cells,
        oracle,
        ConstantCostModel(scan_cost_s=1.0, verify_cost_s=ratio),
        deadline_s=deadline,
        reference_event_count=reference_count,
    )
    policy = policy_factories(stable_seed(int(row["design_id"]), base_seed))[policy_name]()
    result = engine.run(policy)
    return {
        **row,
        "base_seed": base_seed,
        "policy": policy_name,
        "deadline_s": deadline,
        "normalized_anytime_event_auc": result.normalized_anytime_event_auc,
        "terminal_event_recall": result.terminal_event_recall,
        "committed_events": len(result.committed_events),
        "elapsed_s": result.elapsed_s,
        "scan_actions": sum(entry.action == "SCAN" and entry.status == "COMPLETED" for entry in result.trace),
        "verify_actions": sum(entry.action == "VERIFY" and entry.status == "COMPLETED" for entry in result.trace),
    }


def mean(values) -> float:
    return float(statistics.fmean(values))


def analyse(seed_rows: list[dict]) -> tuple[list[dict], dict]:
    grouped: dict[tuple[int, str], list[dict]] = {}
    for row in seed_rows:
        grouped.setdefault((int(row["design_id"]), str(row["policy"])), []).append(row)
    point_rows = []
    for (_, policy), rows in sorted(grouped.items()):
        first = rows[0]
        point_rows.append(
            {
                **{key: first[key] for key in frozen_design()[0]},
                "policy": policy,
                "mean_auc": mean(row["normalized_anytime_event_auc"] for row in rows),
                "median_auc": float(statistics.median(row["normalized_anytime_event_auc"] for row in rows)),
                "mean_terminal_recall": mean(row["terminal_event_recall"] for row in rows),
            }
        )

    by_run = {
        (int(row["design_id"]), int(row["base_seed"]), str(row["policy"])): row
        for row in seed_rows
    }
    deltas = []
    for design in frozen_design():
        for seed in BASE_SEEDS:
            datb = by_run[(int(design["design_id"]), seed, "datb_sv")]
            sequential = by_run[(int(design["design_id"]), seed, "sequential")]
            largest = by_run[(int(design["design_id"]), seed, "largest_gap")]
            deltas.append(
                {
                    **design,
                    "base_seed": seed,
                    "delta_datb_vs_sequential": datb["normalized_anytime_event_auc"]
                    - sequential["normalized_anytime_event_auc"],
                    "delta_datb_vs_largest_gap": datb["normalized_anytime_event_auc"]
                    - largest["normalized_anytime_event_auc"],
                }
            )

    def regime(rows, a, b):
        return [
            row["delta_datb_vs_sequential"]
            for row in rows
            if int(row["A_density"]) == a and int(row["B_temporal_modes"]) == b
        ]

    sparse_multi = mean(regime(deltas, 0, 2))
    dense_uni = mean(regime(deltas, 2, 0))
    interaction_contrast = sparse_multi - dense_uni

    cost_directions = {}
    for ratio in COST_RATIOS:
        subset = [row for row in deltas if float(row["verify_scan_cost_ratio"]) == ratio]
        contrast = mean(regime(subset, 0, 2)) - mean(regime(subset, 2, 0))
        cost_directions[str(int(ratio))] = contrast
    noise_directions = {}
    deadline_directions = {}
    for level in range(3):
        subset_noise = [row for row in deltas if int(row["D_proxy_noise"]) == level]
        noise_directions[str(level)] = mean(regime(subset_noise, 0, 2)) - mean(regime(subset_noise, 2, 0))
        subset_deadline = [row for row in deltas if int(row["F_deadline"]) == level]
        deadline_directions[str(level)] = mean(regime(subset_deadline, 0, 2)) - mean(regime(subset_deadline, 2, 0))

    direction_costs = sum(value > 0 for value in cost_directions.values())
    direction_noise = sum(value > 0 for value in noise_directions.values())
    direction_deadline = sum(value > 0 for value in deadline_directions.values())
    screen_pass = bool(
        interaction_contrast >= 0.05
        and direction_costs >= 3
        and direction_noise >= 2
        and direction_deadline >= 2
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "scientific_classification": "synthetic_mechanism_screen_not_natural_evidence",
        "design_points": 324,
        "policies": list(POLICY_NAMES),
        "seeds": list(BASE_SEEDS),
        "total_replays": len(seed_rows),
        "sparse_multimodal_mean_delta_vs_sequential": sparse_multi,
        "dense_unimodal_mean_delta_vs_sequential": dense_uni,
        "interaction_contrast": interaction_contrast,
        "cost_ratio_contrasts": cost_directions,
        "proxy_noise_contrasts": noise_directions,
        "deadline_contrasts": deadline_directions,
        "positive_cost_ratio_directions": direction_costs,
        "positive_noise_directions": direction_noise,
        "positive_deadline_directions": direction_deadline,
        "frozen_synthetic_h2_screen_pass": screen_pass,
        "claim_gate_status": "BLOCKED_MISSING_EXSAMPLE_END_TO_END_AND_NATURAL_CORPUS",
        "interpretation_rule": "Synthetic PASS supports implementation of T2; it cannot support a paper effect claim.",
    }
    return point_rows, {"summary": summary, "deltas": deltas}


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty table: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def execute(output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)
    design = frozen_design()
    write_csv(output / "frozen_design_matrix.csv", design)
    seed_rows = []
    for row in design:
        for seed in BASE_SEEDS:
            for policy in POLICY_NAMES:
                seed_rows.append(run_one(row, seed, policy))
    point_rows, analysis = analyse(seed_rows)
    write_csv(output / "seed_level_results.csv", seed_rows)
    write_csv(output / "design_policy_results.csv", point_rows)
    write_csv(output / "h2_paired_deltas.csv", analysis["deltas"])
    summary = analysis["summary"]
    (output / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    verdict = "PASS" if summary["frozen_synthetic_h2_screen_pass"] else "FAIL"
    report = f"""# H2 Synthetic Mechanism Screen\n\n## Verdict\n\n`{verdict}_SYNTHETIC_MECHANISM_SCREEN_ONLY`\n\n## Frozen result\n\n- Replays: {summary['total_replays']}\n- Sparse + multimodal DATB-minus-Sequential AUC: {summary['sparse_multimodal_mean_delta_vs_sequential']:.6f}\n- Dense + unimodal DATB-minus-Sequential AUC: {summary['dense_unimodal_mean_delta_vs_sequential']:.6f}\n- Preregistered interaction contrast: {summary['interaction_contrast']:.6f}\n- Positive cost-ratio directions: {summary['positive_cost_ratio_directions']}/4\n- Positive proxy-noise directions: {summary['positive_noise_directions']}/3\n- Positive deadline directions: {summary['positive_deadline_directions']}/3\n\n## Claim boundary\n\n`{summary['claim_gate_status']}`\n\nThis synthetic result is a mechanism and pipeline diagnostic. It is not evidence of natural workload prevalence, real C3 cost benefit, or superiority over ExSample-EndToEnd.\n"""
    (output / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execute(args.output.resolve())


if __name__ == "__main__":
    main()
