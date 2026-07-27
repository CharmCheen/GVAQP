#!/usr/bin/env python3
"""Freeze hashes and requirement-level evidence for the SCAN headroom audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/scan_optimization_headroom_audit_v1"
BENCH = ROOT / "benchmarks/partial_scan_pilot_v1"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def main() -> None:
    replay = pd.read_csv(OUT / "replay_run_summary.csv")
    checkpoints = pd.read_csv(OUT / "replay_budget_checkpoints.csv")
    physical = pd.read_csv(OUT / "physical_run_summary.csv")
    physical_trace = pd.read_csv(OUT / "physical_exposure_trace.csv")
    policy_audit = json.loads((OUT / "trusted_policy_code_audit.json").read_text())
    lineage = json.loads((OUT / "physical_policy_lineage_audit.json").read_text())
    temporal = json.loads(
        (OUT / "temporal_correlation_audit/temporal_refinement_decision.json").read_text()
    )
    refinement = json.loads(
        (OUT / "fixed_refinement_baselines/refinement_decision.json").read_text()
    )
    random = replay[replay.policy_id.eq("RANDOM_WITHOUT_REPLACEMENT")]
    requirements = {
        "trusted_policy_protocol_frozen": (OUT / "TRUSTED_POLICY_EXPERIMENT_PROTOCOL.md").is_file(),
        "trusted_policy_static_audit_pass": policy_audit["status"] == "PASS",
        "replay_run_count_110": len(replay) == 110,
        "random_50_seeds_per_video": random.groupby("video_id").seed.nunique().eq(50).all(),
        "eight_budget_checkpoints": checkpoints.budget_fraction.nunique() == 8,
        "offset0_exposure_denominator_263": replay.groupby("video_id").offset0_exposable_event_count.first().sum() == 263,
        "all_reference_denominator_268": replay.groupby("video_id").all_reference_event_count.first().sum() == 268,
        "visible_subset_checkpoint_equivalence": (checkpoints.fast_vs_exact_current_delta == 0).all(),
        "physical_run_count_32": len(physical) == 32,
        "physical_completed_prefix_count_1478": len(physical_trace) == 1478,
        "physical_visible_subset_equivalence": (physical_trace.fast_vs_exact_ever_delta == 0).all(),
        "physical_policy_lineage_pass": lineage["status"] == "PASS" and lineage["action_mismatch_count"] == 0,
        "temporal_audit_complete": temporal["status"] == "PASS",
        "fixed_refinement_gate_executed": temporal["FIXED_REFINEMENT_GATE"] == "PASS",
        "guarded_marginal_gate_respected": refinement["GUARDED_MARGINAL_SCAN_GATE"] == "STOP",
        "adversarial_review_present": (OUT / "ADVERSARIAL_INTERPRETATION_AUDIT.md").is_file(),
        "final_synthesis_present": (OUT / "FINAL_RESEARCH_SYNTHESIS_ZH.md").is_file(),
    }
    inputs = [
        BENCH / "immutable/timeline_units.csv",
        BENCH / "immutable/reference_events.csv",
        BENCH / "derived/candidate_event_map.parquet",
        BENCH / "derived/cost_calibration/conservative_cost_model.json",
    ]
    sources = [
        ROOT / "src/garc_eval/scan_headroom/trusted_policies.py",
        ROOT / "scripts/run_scan_optimization_headroom_audit.py",
        ROOT / "scripts/run_scan_temporal_refinement_audit.py",
        ROOT / "scripts/run_scan_fixed_refinement_baselines.py",
        ROOT / "scripts/audit_scan_physical_policy_lineage.py",
    ]
    critical_outputs = [
        OUT / "headroom_decision.json",
        OUT / "physical_evidence_manifest.json",
        OUT / "physical_policy_lineage_audit.json",
        OUT / "temporal_correlation_audit/temporal_refinement_decision.json",
        OUT / "fixed_refinement_baselines/refinement_decision.json",
        OUT / "FINAL_RESEARCH_SYNTHESIS_ZH.md",
        OUT / "ADVERSARIAL_INTERPRETATION_AUDIT.md",
    ]
    payload = {
        "status": "PASS" if all(requirements.values()) else "FAIL",
        "requirements": {key: bool(value) for key, value in requirements.items()},
        "input_hashes": {str(path.relative_to(ROOT)): digest(path) for path in inputs},
        "source_hashes": {str(path.relative_to(ROOT)): digest(path) for path in sources},
        "critical_output_hashes": {
            str(path.relative_to(ROOT)): digest(path) for path in critical_outputs
        },
        "scope": "TWO_VIDEO_TRUSTED_POLICY_MECHANISM_AUDIT",
        "formal_generalization_claim": False,
    }
    write_json(OUT / "AUDIT_MANIFEST.json", payload)
    print(json.dumps({"status": payload["status"], "requirements": payload["requirements"]}, indent=2))


if __name__ == "__main__":
    main()
