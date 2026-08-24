"""Versioned H2 rerun after repairing DATB/LargestGap implementation identity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import run_h2_synthetic_mechanism_v1 as v1


SCHEMA_VERSION = "H2_SYNTHETIC_MECHANISM_V2_VALUE_RATE"


def execute(output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)
    design = v1.frozen_design()
    v1.write_csv(output / "frozen_design_matrix.csv", design)
    seed_rows = []
    for row in design:
        for seed in v1.BASE_SEEDS:
            for policy in v1.POLICY_NAMES:
                seed_rows.append(v1.run_one(row, seed, policy))
    point_rows, analysis = v1.analyse(seed_rows)
    deltas = analysis["deltas"]
    nonidentity_rows = sum(
        abs(float(row["delta_datb_vs_largest_gap"])) > 1e-12 for row in deltas
    )
    nonidentity_fraction = nonidentity_rows / len(deltas)
    nonidentity_pass = nonidentity_fraction >= 0.05
    summary = dict(analysis["summary"])
    summary.update(
        {
            "schema_version": SCHEMA_VERSION,
            "supersedes_v1": False,
            "v1_status": "FAIL_SYNTHETIC_MECHANISM_SCREEN_ONLY",
            "method_change": "DATB deterministic causal value-rate planner",
            "datb_largest_gap_nonidentity_rows": nonidentity_rows,
            "datb_largest_gap_nonidentity_fraction": nonidentity_fraction,
            "datb_largest_gap_nonidentity_pass": nonidentity_pass,
            "frozen_synthetic_h2_v2_pass": bool(
                summary["frozen_synthetic_h2_screen_pass"] and nonidentity_pass
            ),
            "claim_gate_status": "BLOCKED_MISSING_EXSAMPLE_END_TO_END_AND_NATURAL_CORPUS",
        }
    )
    v1.write_csv(output / "seed_level_results.csv", seed_rows)
    v1.write_csv(output / "design_policy_results.csv", point_rows)
    v1.write_csv(output / "h2_paired_deltas.csv", deltas)
    (output / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    verdict = "PASS" if summary["frozen_synthetic_h2_v2_pass"] else "FAIL"
    report = f"""# H2 V2 Synthetic Mechanism Screen\n\n## Verdict\n\n`{verdict}_SYNTHETIC_MECHANISM_V2_ONLY`\n\n## Frozen result\n\n- Replays: {summary['total_replays']}\n- DATB/LargestGap nonidentity: {summary['datb_largest_gap_nonidentity_rows']}/{len(deltas)} ({summary['datb_largest_gap_nonidentity_fraction']:.2%})\n- Sparse + multimodal DATB-minus-Sequential AUC: {summary['sparse_multimodal_mean_delta_vs_sequential']:.6f}\n- Dense + unimodal DATB-minus-Sequential AUC: {summary['dense_unimodal_mean_delta_vs_sequential']:.6f}\n- Interaction contrast: {summary['interaction_contrast']:.6f}\n- Positive cost-ratio directions: {summary['positive_cost_ratio_directions']}/4\n- Positive proxy-noise directions: {summary['positive_noise_directions']}/3\n- Positive deadline directions: {summary['positive_deadline_directions']}/3\n\n## Claim boundary\n\n`{summary['claim_gate_status']}`\n\nV1 remains a frozen failure. V2 qualifies only the repaired mechanism and cannot support a natural-corpus paper claim.\n"""
    (output / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execute(args.output.resolve())


if __name__ == "__main__":
    main()
