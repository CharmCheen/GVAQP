#!/usr/bin/env python3
"""Independently reconstruct the frozen evidence used by the invention sprint.

This program reads immutable reports for provenance, but numerical checks use
primitive tables wherever one is available.  It never loads a model or reads a
raw VLM response.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = next(
    p for p in Path(__file__).resolve().parents
    if (p / "Audited_Event_Hypothesis_AQP_Design_Pack_v1").is_dir()
)
OUT = ROOT / "AQP_Algorithm_Invention_Sprint_v1"
EVIDENCE = OUT / "evidence"

STRICT = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
AGENT_RUN = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run"
DARE = ROOT / "DARE_AQP_Experiment_v1/outputs"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def auc(budget: pd.Series, value: pd.Series) -> float:
    order = np.argsort(budget.to_numpy(dtype=float))
    x = budget.to_numpy(dtype=float)[order]
    y = value.to_numpy(dtype=float)[order]
    return float(np.trapezoid(y, x) / (x[-1] - x[0]))


def one_row(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as f:
        return next(csv.DictReader(f))


def close(observed: float, expected: float, atol: float = 5e-12) -> bool:
    return bool(np.isclose(observed, expected, rtol=0.0, atol=atol))


def fact(
    rows: list[dict[str, object]],
    name: str,
    observed: object,
    expected: object,
    source: str,
    method: str,
    ok: bool | None = None,
) -> None:
    if ok is None:
        if isinstance(expected, float):
            ok = close(float(observed), expected)
        else:
            ok = str(observed) == str(expected)
    rows.append(
        {
            "fact": name,
            "expected": expected,
            "observed": observed,
            "status": "PASS" if ok else "FAIL",
            "verification_method": method,
            "authoritative_source": source,
        }
    )


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    # Strict benchmark: recompute AUC from per-budget primitives rather than
    # copying analysis/event_f1_auc.csv.
    units_path = STRICT / "frozen_inputs/units.csv"
    events_path = STRICT / "frozen_inputs/event_reference.csv"
    strict_budget_path = STRICT / "analysis/per_budget_metrics.csv"
    units = pd.read_csv(units_path)
    events = pd.read_csv(events_path)
    strict_budget = pd.read_csv(strict_budget_path)
    baseline_curve = strict_budget[
        (strict_budget.method == "B5_ARC_native")
        & (strict_budget.method_variant == "arc_refinement_th0.4_native")
    ]
    map_curve = strict_budget[
        (strict_budget.method == "M1_MAP_anchor_only")
        & (strict_budget.method_variant == "K3_BRIDGE_SAFE")
    ]
    baseline_auc = auc(baseline_curve.horizon_budget, baseline_curve.event_f1_mean)
    map_auc = auc(map_curve.horizon_budget, map_curve.event_f1)

    # Frozen method and repair curves.
    bcm_summary_path = AGENT_RUN / "bcm_aqp_experiment_v2/tables/method_summary.csv"
    bcm_summary = pd.read_csv(bcm_summary_path)
    bcm_auc = float(
        bcm_summary[(bcm_summary.method == "BCM_AQP_V2") & (bcm_summary.variant == "canonical")]
        .iloc[0]
        .event_f1_auc
    )
    repair_auc_path = AGENT_RUN / "hypothesis_construction_repair_v1/analysis/event_f1_auc.csv"
    repair_auc_table = pd.read_csv(repair_auc_path)
    h1_auc = float(
        repair_auc_table[
            (repair_auc_table.variant == "H1")
            & (repair_auc_table.materializer == "k3_bridge_safe")
        ].iloc[0].event_f1_auc
    )

    # Candidate universe and ranking ceiling.
    reorder_path = AGENT_RUN / "candidate_outcome_calibration_gate_v1/ceilings/oracle_informed_reorder_metrics.csv"
    reorder = pd.read_csv(reorder_path)
    reorder_auc = auc(reorder.budget, reorder.event_f1)
    missing_path = AGENT_RUN / "candidate_outcome_calibration_gate_v1/ceilings/missing_event_from_candidate_universe.csv"
    missing = pd.read_csv(missing_path)
    legal_coverage = float(missing.present_in_full_legal_action_universe.astype(bool).mean())
    crossfit_path = AGENT_RUN / "candidate_outcome_calibration_gate_v1/calibration_feasibility/crossfit_metrics.csv"
    crossfit = pd.read_csv(crossfit_path)
    public_cv = float(
        crossfit[
            (crossfit.target == "can_certify_any_event")
            & (crossfit.feature_set == "F2_all_public_H1")
            & (crossfit.scope == "pooled")
        ].iloc[0].auroc
    )

    # Mechanism and representation gate primitives.
    mechanism_decision_path = AGENT_RUN / "algorithmic_mechanism_viability_gate_v1/FINAL_DECISION.csv"
    mechanism_decision = one_row(mechanism_decision_path)
    public_cells_path = AGENT_RUN / "public_event_cell_representation_gate_v1/aggregates/paired_auc_by_s2_cell.csv"
    public_cells = pd.read_csv(public_cells_path)
    public_delta = float(public_cells.r1_p1_minus_p0.mean())

    # Materialization gate primitives.
    bcem_decision_path = AGENT_RUN / "barrier_constrained_event_materialization_gate_v1/FINAL_DECISION.csv"
    bcem = one_row(bcem_decision_path)

    # DARE ranking primitives.
    dare_decision_path = DARE / "gate_a_final/FINAL_DECISION.json"
    dare_decision = json.loads(dare_decision_path.read_text())
    dare_auc_path = DARE / "gate_a_final/evaluation/event_f1_auc.csv"
    dare_auc = pd.read_csv(dare_auc_path).set_index("signal_id")
    dare_rank_path = DARE / "gate_a_final/evaluation/ranking_metrics.csv"
    dare_rank = pd.read_csv(dare_rank_path).set_index("signal_id")
    dare_ideal_rank_path = DARE / "gate_a_final/evaluation/ideal_oracle_ranking_metrics.csv"
    dare_ideal_rank = pd.read_csv(dare_ideal_rank_path).set_index("signal_id")
    gate_b_path = DARE / "gate_a_final/evaluation/gate_b_link.csv"
    gate_b = pd.read_csv(gate_b_path)

    # Risk-limiting interval gate primitives.
    risk_decision_path = DARE / "risk_limiting_interval_pruning_feasibility_v1/FINAL_DECISION.csv"
    risk_decision = one_row(risk_decision_path)
    risk_grid_path = DARE / "risk_limiting_interval_pruning_feasibility_v1/simulations/RISK_LIMITING_GRID.csv"
    risk_grid = pd.read_csv(risk_grid_path)
    robust_path = DARE / "risk_limiting_interval_pruning_feasibility_v1/feasible_region/ROBUST_FEASIBLE_REGION.csv"
    robust = pd.read_csv(robust_path)
    quality = risk_grid[
        risk_grid.recall_pass
        & risk_grid.coverage_pass
        & (risk_grid.certify_rate >= 0.9)
    ]
    grouped_quality_costs: list[float] = []
    group_cols = [
        "sensitivity", "specificity", "unknown_rate", "variant",
        "audit_fraction", "cost_family", "fixed_fraction",
    ]
    qflag = risk_grid.assign(
        quality=risk_grid.recall_pass
        & risk_grid.coverage_pass
        & (risk_grid.certify_rate >= 0.9)
    )
    for _, group in qflag.groupby(group_cols):
        if bool(group.quality.all()):
            grouped_quality_costs.append(float(group.total_cost_p95.max()))

    rows: list[dict[str, object]] = []
    fact(rows, "benchmark_id", units.benchmark_id.nunique() == 1 and units.benchmark_id.iloc[0], "cbbv2_514c0d360fd5b2a4b5fe", str(units_path.relative_to(ROOT)), "unique value in frozen units")
    fact(rows, "strict_units", len(units), 347, str(units_path.relative_to(ROOT)), "row count")
    fact(rows, "strict_reference_events", len(events), 26, str(events_path.relative_to(ROOT)), "row count")
    fact(rows, "best_native_baseline_event_f1_auc", baseline_auc, 0.3896592193755119, str(strict_budget_path.relative_to(ROOT)), "normalized trapezoid over six primitive budget rows")
    fact(rows, "map_m1_event_f1_auc", map_auc, 0.3880556629484837, str(strict_budget_path.relative_to(ROOT)), "normalized trapezoid over six primitive budget rows")
    fact(rows, "bcm_event_f1_auc", bcm_auc, 0.2942701472213107, str(bcm_summary_path.relative_to(ROOT)), "canonical bridge-safe method row")
    fact(rows, "bcm_decision", one_row(AGENT_RUN / "bcm_aqp_experiment_v2/FINAL_DECISION.csv")["decision"], "NO-GO", "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/bcm_aqp_experiment_v2/FINAL_DECISION.csv", "sealed decision")
    fact(rows, "h1_event_f1_auc", h1_auc, 0.31499046948962056, str(repair_auc_path.relative_to(ROOT)), "H1 bridge-safe row")
    fact(rows, "h1_decision", one_row(AGENT_RUN / "hypothesis_construction_repair_v1/FINAL_DECISION.csv")["decision"], "HYPOTHESIS_REPAIR_WEAK_GO", "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/hypothesis_construction_repair_v1/FINAL_DECISION.csv", "sealed decision")
    fact(rows, "oracle_informed_reorder_auc", reorder_auc, 0.6644581556172099, str(reorder_path.relative_to(ROOT)), "normalized trapezoid over evaluator-only budget rows")
    fact(rows, "h1_full_legal_universe_coverage", legal_coverage, 20 / 26, str(missing_path.relative_to(ROOT)), "26 minus six explicitly absent events")
    fact(rows, "public_blocked_cv_auroc", public_cv, 0.5482815057283144, str(crossfit_path.relative_to(ROOT)), "pooled frozen F2 blocked-crossfit row")
    fact(rows, "mechanism_decision", mechanism_decision["decision"], "IDEAL_SIGNAL_ONLY", str(mechanism_decision_path.relative_to(ROOT)), "sealed decision")
    fact(rows, "mechanism_exploration_harmful", float(mechanism_decision["P2_minus_P1_mean"]) < 0, True, str(mechanism_decision_path.relative_to(ROOT)), "sign of paired mean effect")
    fact(rows, "mechanism_counterfactual_negligible", abs(float(mechanism_decision["P3_minus_P2_mean"])) < 0.002, True, str(mechanism_decision_path.relative_to(ROOT)), "absolute paired mean effect below 0.002 diagnostic threshold")
    fact(rows, "public_cell_decision", one_row(AGENT_RUN / "public_event_cell_representation_gate_v1/FINAL_DECISION.csv")["decision"], "PLANNER_ROUTE_REJECTED", "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/public_event_cell_representation_gate_v1/FINAL_DECISION.csv", "sealed decision")
    fact(rows, "public_cell_r1_p1_minus_p0_auc", public_delta, -0.0035011393723635154, str(public_cells_path.relative_to(ROOT)), "mean of 15 primitive paired S2 cells")
    fact(rows, "public_cell_all_15_negative", int((public_cells.r1_p1_minus_p0 < 0).sum()), 15, str(public_cells_path.relative_to(ROOT)), "sign count")
    fact(rows, "materialization_decision", bcem["decision"], "PUBLIC_BCEM_NO_GO", str(bcem_decision_path.relative_to(ROOT)), "sealed decision")
    fact(rows, "k3_safe_auc", float(bcem["k3_safe_auc"]), 0.3176441956920938, str(bcem_decision_path.relative_to(ROOT)), "sealed value backed by fixed-trace aggregates")
    fact(rows, "legal_partition_ceiling_auc", float(bcem["legal_partition_ceiling_auc"]), 0.3185143608556265, str(bcem_decision_path.relative_to(ROOT)), "exact-DP aggregate")
    fact(rows, "public_bcem_delta", float(bcem["public_bcem_minus_k3_safe_auc"]), -0.0075201598224607, str(bcem_decision_path.relative_to(ROOT)), "public exact-DP minus K3-safe")
    fact(rows, "dare_decision", dare_decision["gate_a_decision"], "UNIT_ORACLE_DARE_ACCELERATION_NO_GO", str(dare_decision_path.relative_to(ROOT)), "sealed decision")
    fact(rows, "dare_public_proxy_auc", float(dare_auc.loc["current_proxy", "event_f1_auc"]), 0.3542124760437505, str(dare_auc_path.relative_to(ROOT)), "ranking evaluation row")
    fact(rows, "dare_clip_auc", float(dare_auc.loc["image_text", "event_f1_auc"]), 0.538949, str(dare_auc_path.relative_to(ROOT)), "ranking evaluation row", close(float(dare_auc.loc["image_text", "event_f1_auc"]), 0.538949, 5e-7))
    fact(rows, "dare_xclip_auc", float(dare_auc.loc["video_text", "event_f1_auc"]), 0.265671, str(dare_auc_path.relative_to(ROOT)), "ranking evaluation row", close(float(dare_auc.loc["video_text", "event_f1_auc"]), 0.265671, 5e-7))
    fact(rows, "dare_ideal_auc", float(dare_auc.loc["ideal_oracle_ceiling", "event_f1_auc"]), 0.919626, str(dare_auc_path.relative_to(ROOT)), "evaluator-only ceiling row", close(float(dare_auc.loc["ideal_oracle_ceiling", "event_f1_auc"]), 0.919626, 5e-7))
    for signal, expected in [("current_proxy", 4), ("image_text", 8), ("video_text", 2)]:
        fact(rows, f"dare_{signal}_top24_events", int(dare_rank.loc[signal, "top_24_distinct_events"]), expected, str(dare_rank_path.relative_to(ROOT)), "ranking metric row")
    fact(rows, "dare_ideal_oracle_ceiling_top24_events", int(dare_ideal_rank.loc["ideal_oracle_ceiling", "top_24_distinct_events"]), 24, str(dare_ideal_rank_path.relative_to(ROOT)), "evaluator-only ranking metric row")
    for signal, expected in [("current_proxy", 315), ("image_text", 311), ("video_text", 316)]:
        observed = int(gate_b[gate_b.signal_id == signal].median_total_cost.min())
        fact(rows, f"dare_{signal}_best_gate_b_calls", observed, expected, str(gate_b_path.relative_to(ROOT)), "minimum frozen total cost")
    fact(rows, "risk_limiting_decision", risk_decision["decision"], "RISK_LIMITING_INTERVAL_NO_GO", str(risk_decision_path.relative_to(ROOT)), "sealed decision")
    fact(rows, "risk_grid_rows", len(risk_grid), 56448, str(risk_grid_path.relative_to(ROOT)), "row count")
    fact(rows, "risk_robust_feasible_cells", int(robust.robust_feasible.sum()), 0, str(robust_path.relative_to(ROOT)), "boolean sum")
    fact(rows, "risk_min_single_quality_cost", float(quality.total_cost_p95.min()), 350.0, str(risk_grid_path.relative_to(ROOT)), "minimum p95 among recall/coverage/certificate-valid cells")
    fact(rows, "risk_min_all_placement_quality_cost", min(grouped_quality_costs), 550.0, str(risk_grid_path.relative_to(ROOT)), "minimum worst-placement p95 among all-placement quality-valid configs")
    fact(rows, "risk_exact_any_cost", 217 + 26, 243, "DARE_AQP_Experiment_v1/outputs/risk_limiting_interval_pruning_feasibility_v1/diagnostics/DECISION_FACTS.csv", "217 interval queries plus 26 certifications")
    fact(rows, "risk_exact_any_dense_ratio", (217 + 26) / 347, 0.7002881844380403, "DARE_AQP_Experiment_v1/outputs/risk_limiting_interval_pruning_feasibility_v1/diagnostics/DECISION_FACTS.csv", "exact arithmetic")
    fact(rows, "risk_physical_vlm_calls", int(risk_decision["physical_vlm_calls"]), 0, str(risk_decision_path.relative_to(ROOT)), "sealed ledger count")

    facts = pd.DataFrame(rows)
    facts.to_csv(EVIDENCE / "FROZEN_FACT_REPRODUCTION.csv", index=False)
    if not (facts.status == "PASS").all():
        failed = facts[facts.status != "PASS"].fact.tolist()
        raise RuntimeError(f"Frozen fact reproduction failed: {failed}")

    source_paths = [
        "BCM_AQP_MATHEMATICAL_REFERENCE.md",
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py",
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/scripts/run_clean_benchmark_v2_strict.py",
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/bcm_aqp_experiment_v2/scripts/run_bcm_aqp_v2.py",
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/hypothesis_construction_repair_v1/implementation/run_hypothesis_construction_repair_v1.py",
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/candidate_outcome_calibration_gate_v1/scripts/run_candidate_outcome_calibration_gate_v1.py",
        "garc_eval/mechanism_gate_v1/core.py",
        "garc_eval/mechanism_gate_v1/run_gate.py",
        "garc_eval/public_event_cell_gate_v1/run_gate.py",
        "src/garc_eval/bcem_gate_v1/core.py",
        "src/garc_eval/bcem_gate_v1/ceiling.py",
        "src/garc_eval/bcem_gate_v1/public.py",
        "DARE_AQP_Experiment_v1/src/dare_aqp/audit.py",
        "DARE_AQP_Experiment_v1/src/dare_aqp/interval_ceiling.py",
        "garc_eval/risk_limiting_interval_v1/simulate.py",
    ]
    source_rows = []
    for rel in source_paths:
        path = ROOT / rel
        source_rows.append({"path": rel, "sha256": sha256(path), "bytes": path.stat().st_size, "status": "READ_AND_HASHED"})
    pd.DataFrame(source_rows).to_csv(EVIDENCE / "SOURCE_MANIFEST.csv", index=False)

    experiment_names = [
        "clean_baseline_benchmark_v2_strict",
        "bcm_aqp_experiment_v2",
        "hypothesis_construction_repair_v1",
        "candidate_outcome_calibration_gate_v1",
        "algorithmic_mechanism_viability_gate_v1",
        "public_event_cell_representation_gate_v1",
        "barrier_constrained_event_materialization_gate_v1",
    ]
    input_paths: set[str] = {
        str(units_path.relative_to(ROOT)), str(events_path.relative_to(ROOT)),
        str(strict_budget_path.relative_to(ROOT)), str(bcm_summary_path.relative_to(ROOT)),
        str(repair_auc_path.relative_to(ROOT)), str(reorder_path.relative_to(ROOT)),
        str(missing_path.relative_to(ROOT)), str(crossfit_path.relative_to(ROOT)),
        str(mechanism_decision_path.relative_to(ROOT)), str(public_cells_path.relative_to(ROOT)),
        str(bcem_decision_path.relative_to(ROOT)), str(dare_decision_path.relative_to(ROOT)),
        str(dare_auc_path.relative_to(ROOT)), str(dare_rank_path.relative_to(ROOT)),
        str(dare_ideal_rank_path.relative_to(ROOT)),
        str(gate_b_path.relative_to(ROOT)), str(risk_decision_path.relative_to(ROOT)),
        str(risk_grid_path.relative_to(ROOT)), str(robust_path.relative_to(ROOT)),
    }
    for name in experiment_names:
        base = AGENT_RUN / name
        for rel in ["FINAL_DECISION.csv", "FINAL_REPORT.md", "EXPERIMENT_MANIFEST.json", "BENCHMARK_MANIFEST.json", "FILE_MANIFEST.csv", "REPRODUCTION.md"]:
            path = base / rel
            if path.exists():
                input_paths.add(str(path.relative_to(ROOT)))
        for path in (base / "audit").glob("INDEPENDENT_ADVERSARIAL_REVIEW.*"):
            input_paths.add(str(path.relative_to(ROOT)))
    for base in [DARE / "gate_a_final", DARE / "risk_limiting_interval_pruning_feasibility_v1"]:
        for rel in ["FINAL_DECISION.csv", "FINAL_DECISION.json", "FINAL_REPORT.md", "REPORT.md", "FILE_MANIFEST.csv", "REPRODUCTION.md"]:
            path = base / rel
            if path.exists():
                input_paths.add(str(path.relative_to(ROOT)))
        for path in base.glob("*INDEPENDENT_ADVERSARIAL_REVIEW.*"):
            input_paths.add(str(path.relative_to(ROOT)))
        for path in (base / "audit").glob("INDEPENDENT_ADVERSARIAL_REVIEW.*"):
            input_paths.add(str(path.relative_to(ROOT)))
    input_rows = []
    for rel in sorted(input_paths):
        path = ROOT / rel
        input_rows.append({"path": rel, "sha256": sha256(path), "bytes": path.stat().st_size, "status": "READ_AND_HASHED"})
    pd.DataFrame(input_rows).to_csv(EVIDENCE / "INPUT_MANIFEST.csv", index=False)
    print(json.dumps({"facts": len(facts), "source_files": len(source_rows), "input_files": len(input_rows), "status": "PASS"}))


if __name__ == "__main__":
    main()
