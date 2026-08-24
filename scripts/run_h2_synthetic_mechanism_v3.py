"""Comparator-orthogonalized H2 holdout screen with deterministic new seeds."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics

import run_h2_synthetic_mechanism_v1 as v1


SCHEMA_VERSION = "H2_SYNTHETIC_MECHANISM_V3_ORTHOGONAL_HOLDOUT"
HOLDOUT_SEEDS = tuple(
    int.from_bytes(
        hashlib.sha256(f"H2_V3_HOLDOUT:{index}".encode("ascii")).digest()[:8],
        "big",
    )
    for index in range(5)
)


def mean(values) -> float:
    return float(statistics.fmean(values))


def regime(rows: list[dict], a: int, b: int, key: str) -> list[float]:
    return [
        float(row[key])
        for row in rows
        if int(row["A_density"]) == a and int(row["B_temporal_modes"]) == b
    ]


def contrast(rows: list[dict], key: str) -> float:
    return mean(regime(rows, 0, 2, key)) - mean(regime(rows, 2, 0, key))


def execute(output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)
    design = v1.frozen_design()
    v1.write_csv(output / "frozen_design_matrix.csv", design)
    seed_rows = []
    for row in design:
        for seed in HOLDOUT_SEEDS:
            for policy in v1.POLICY_NAMES:
                seed_rows.append(v1.run_one(row, seed, policy))

    original_seeds = v1.BASE_SEEDS
    v1.BASE_SEEDS = HOLDOUT_SEEDS
    try:
        point_rows, analysis = v1.analyse(seed_rows)
    finally:
        v1.BASE_SEEDS = original_seeds
    deltas = analysis["deltas"]
    coupling_key = "delta_datb_vs_largest_gap"
    sequential_key = "delta_datb_vs_sequential"
    coupling_values = [float(row[coupling_key]) for row in deltas]
    coupling_contrast = contrast(deltas, coupling_key)
    composite_contrast = contrast(deltas, sequential_key)

    cost_contrasts = {}
    for ratio in v1.COST_RATIOS:
        subset = [
            row
            for row in deltas
            if float(row["verify_scan_cost_ratio"]) == ratio
        ]
        cost_contrasts[str(int(ratio))] = contrast(subset, coupling_key)
    noise_contrasts = {}
    deadline_contrasts = {}
    for level in range(3):
        noise_contrasts[str(level)] = contrast(
            [row for row in deltas if int(row["D_proxy_noise"]) == level],
            coupling_key,
        )
        deadline_contrasts[str(level)] = contrast(
            [row for row in deltas if int(row["F_deadline"]) == level],
            coupling_key,
        )

    nonidentity_rows = sum(abs(value) > 1e-12 for value in coupling_values)
    nonidentity_fraction = nonidentity_rows / len(coupling_values)
    direction_costs = sum(value > 0 for value in cost_contrasts.values())
    direction_noise = sum(value > 0 for value in noise_contrasts.values())
    direction_deadline = sum(value > 0 for value in deadline_contrasts.values())
    passed = bool(
        coupling_contrast >= 0.05
        and direction_costs >= 3
        and direction_noise >= 2
        and direction_deadline >= 2
        and nonidentity_fraction >= 0.05
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "scientific_classification": "synthetic_holdout_mechanism_screen_not_natural_evidence",
        "supersedes_v1_or_v2": False,
        "v1_status": "FAIL_SYNTHETIC_MECHANISM_SCREEN_ONLY",
        "v2_status": "FAIL_SYNTHETIC_MECHANISM_V2_ONLY",
        "design_points": len(design),
        "seeds": list(HOLDOUT_SEEDS),
        "policies": list(v1.POLICY_NAMES),
        "total_replays": len(seed_rows),
        "primary_estimand": "DATB_minus_LargestGap_sparse_multimodal_minus_dense_unimodal",
        "coupling_interaction_contrast": coupling_contrast,
        "composite_datb_sequential_interaction_contrast": composite_contrast,
        "mean_datb_minus_largest_gap_auc": mean(coupling_values),
        "median_datb_minus_largest_gap_auc": float(statistics.median(coupling_values)),
        "datb_largest_gap_positive_rows": sum(value > 1e-12 for value in coupling_values),
        "datb_largest_gap_equal_rows": sum(abs(value) <= 1e-12 for value in coupling_values),
        "datb_largest_gap_negative_rows": sum(value < -1e-12 for value in coupling_values),
        "datb_largest_gap_nonidentity_fraction": nonidentity_fraction,
        "cost_ratio_coupling_contrasts": cost_contrasts,
        "proxy_noise_coupling_contrasts": noise_contrasts,
        "deadline_coupling_contrasts": deadline_contrasts,
        "positive_cost_ratio_directions": direction_costs,
        "positive_noise_directions": direction_noise,
        "positive_deadline_directions": direction_deadline,
        "frozen_synthetic_h2_v3_pass": passed,
        "claim_gate_status": "BLOCKED_MISSING_EXSAMPLE_END_TO_END_AND_NATURAL_CORPUS",
    }
    v1.write_csv(output / "seed_level_results.csv", seed_rows)
    v1.write_csv(output / "design_policy_results.csv", point_rows)
    v1.write_csv(output / "h2_paired_deltas.csv", deltas)
    (output / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    verdict = "PASS" if passed else "FAIL"
    report = f"""# H2 V3 Comparator-Orthogonalized Holdout\n\n## Verdict\n\n`{verdict}_SYNTHETIC_COUPLING_MECHANISM_ONLY`\n\n## Frozen holdout result\n\n- Replays: {summary['total_replays']}\n- Holdout seeds: {', '.join(str(seed) for seed in HOLDOUT_SEEDS)}\n- Mean DATB-minus-LargestGap AUC: {summary['mean_datb_minus_largest_gap_auc']:.6f}\n- Median DATB-minus-LargestGap AUC: {summary['median_datb_minus_largest_gap_auc']:.6f}\n- Positive/equal/negative rows: {summary['datb_largest_gap_positive_rows']}/{summary['datb_largest_gap_equal_rows']}/{summary['datb_largest_gap_negative_rows']}\n- Coupling interaction contrast: {summary['coupling_interaction_contrast']:.6f}\n- Composite DATB-minus-Sequential contrast: {summary['composite_datb_sequential_interaction_contrast']:.6f}\n- Positive cost/noise/deadline directions: {summary['positive_cost_ratio_directions']}/4, {summary['positive_noise_directions']}/3, {summary['positive_deadline_directions']}/3\n\n## Claim boundary\n\n`{summary['claim_gate_status']}`\n\nThis holdout can qualify or retire the synthetic coupling mechanism only.\n"""
    (output / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execute(args.output.resolve())


if __name__ == "__main__":
    main()
