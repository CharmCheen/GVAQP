#!/usr/bin/env python3
"""Independent mechanical verification of the frozen DASR evidence package."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
EXPECTED_HASHES = {
    PACKAGE / "config" / "frozen_protocol.json": "4eea29f266f35be771ee430bb04221babe32c48adffc7bd7dd4a64e3ac7fd42a",
    PACKAGE / "config" / "frozen_continuation_v2.json": "f62800ece1edee2751afa646efe8d8d344dd8a04de3b1392c9845d0aa15e1daa",
    PACKAGE / "config" / "frozen_continuation_v3.json": "5fad1ac9b59430d9d19363c66c55001d33b5da9fc1c56552081d611336ee61ef",
    PACKAGE / "config" / "frozen_next_candidate_v4.json": "8da4c56f651839120a7975dbc3bbbf209fb76db746c8f3993189cd32da17cff2",
    PACKAGE / "config" / "frozen_external_confirmation_v5.json": "edecabf4a10346a7629ff90a7b5a94b0635ad3464c622594f371dc8d2234ab79",
}


def sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_order(values: np.ndarray) -> list[int]:
    ids = np.arange(len(values))
    return np.lexsort((ids, -values)).astype(int).tolist()


def nms_order(scores: np.ndarray, radius: int = 10) -> list[int]:
    base = stable_order(scores)
    first = []
    for unit_id in base:
        if all(abs(unit_id - chosen) > radius for chosen in first):
            first.append(unit_id)
    used = set(first)
    return first + [unit_id for unit_id in base if unit_id not in used]


def strata(scores: np.ndarray, budget: int) -> list[int]:
    n_units = len(scores)
    n_cells = min(n_units, max(budget, int(round(1.5 * budget))))
    winners = []
    for cell in range(n_cells):
        lo = n_units * cell // n_cells
        hi = n_units * (cell + 1) // n_cells
        winners.append(max(range(lo, hi), key=lambda unit_id: (scores[unit_id], -unit_id)))
    return sorted(winners, key=lambda unit_id: (-scores[unit_id], unit_id))[:budget]


def exact_fill(primary: list[int], secondary: list[int], budget: int) -> list[int]:
    output = []
    seen = set()
    for source in (primary, secondary):
        for unit_id in source:
            if unit_id in seen:
                continue
            output.append(unit_id)
            seen.add(unit_id)
            if len(output) == budget:
                return output
    raise RuntimeError("fill exhausted")


def dasr(scores: np.ndarray, budget: int) -> list[int]:
    n_units = len(scores)
    nms = nms_order(scores, 10)
    coverage = strata(scores, budget)
    alpha = n_units / (n_units + 8.0 * budget)
    quota = int(round(alpha * budget))
    return exact_fill(nms[:quota], coverage + nms, budget)


def pstr(proxy_scores: np.ndarray, budget: int, overhead: float) -> list[int]:
    n_units = len(proxy_scores)
    n_cells = min(n_units, budget + int(math.floor(overhead * budget)))
    winners = []
    for cell in range(n_cells):
        lo = n_units * cell // n_cells
        hi = n_units * (cell + 1) // n_cells
        winners.append(
            max(range(lo, hi), key=lambda unit_id: (proxy_scores[unit_id], -unit_id))
        )
    return sorted(winners, key=lambda unit_id: (-proxy_scores[unit_id], unit_id))[:budget]


def normalized_auc(budgets: list[int], values: list[float]) -> float:
    return float(np.trapezoid(values, budgets) / (budgets[-1] - budgets[0]))


def verify_auc_files(root: Path, checks: list[dict]) -> None:
    per_run = pd.read_csv(root / "per_budget_runs.csv")
    recorded = pd.read_csv(root / "event_f1_auc.csv")
    for (method, variant), group in per_run.groupby(["method", "method_variant"]):
        curve = group.groupby("budget").event_f1.mean().sort_index()
        budgets = curve.index.astype(int).tolist()
        if len(budgets) < 2:
            continue
        computed = normalized_auc(budgets, curve.to_numpy(float).tolist())
        row = recorded[
            (recorded.method == method) & (recorded.method_variant == variant)
        ]
        if len(row) != 1 or not math.isclose(
            computed, float(row.event_f1_auc.iloc[0]), rel_tol=0, abs_tol=1e-12
        ):
            raise AssertionError(f"AUC mismatch at {root}: {method}/{variant}")
    checks.append({"check": f"auc_recompute:{root.name}", "status": "PASS"})


def main() -> None:
    checks = []
    for path, expected in EXPECTED_HASHES.items():
        actual = sha256(path)
        if actual != expected:
            raise AssertionError(f"frozen hash mismatch: {path}: {actual}")
    checks.append({"check": "frozen_protocol_hashes", "status": "PASS"})

    v3 = json.loads((PACKAGE / "config" / "frozen_continuation_v3.json").read_text())
    for spec in v3["confirmatory_intervals"]:
        if sha256(REPO / spec["units_and_oracle"]) != spec["units_and_oracle_sha256"]:
            raise AssertionError(f"input hash mismatch: {spec['name']} grid")
        if sha256(REPO / spec["reference"]) != spec["reference_sha256"]:
            raise AssertionError(f"input hash mismatch: {spec['name']} reference")
    checks.append({"check": "confirmatory_input_hashes", "status": "PASS"})

    inference_specs = [
        (
            PACKAGE / "outputs" / "heldout" / "clip_inference",
            EXPECTED_HASHES[PACKAGE / "config" / "frozen_protocol.json"],
            120,
        ),
        (
            PACKAGE / "outputs" / "confirmatory" / "clip_inference",
            EXPECTED_HASHES[PACKAGE / "config" / "frozen_continuation_v2.json"],
            157,
        ),
        (
            PACKAGE
            / "outputs"
            / "final_confirmation"
            / "realcartest_1630_2000"
            / "clip_inference",
            EXPECTED_HASHES[PACKAGE / "config" / "frozen_continuation_v3.json"],
            37,
        ),
        (
            PACKAGE
            / "outputs"
            / "final_confirmation"
            / "realcartest_3200_3830"
            / "clip_inference",
            EXPECTED_HASHES[PACKAGE / "config" / "frozen_continuation_v3.json"],
            63,
        ),
    ]
    for root, protocol_hash, unit_count in inference_specs:
        complete = json.loads((root / "INFERENCE_COMPLETE.json").read_text())
        if complete["status"] != "COMPLETE":
            raise AssertionError(f"incomplete inference: {root}")
        if complete["frozen_protocol_sha256"] != protocol_hash:
            raise AssertionError(f"inference protocol mismatch: {root}")
        if complete["physical_exact_oracle_vlm_calls"] != 0:
            raise AssertionError(f"nonzero physical oracle calls: {root}")
        if complete["forbidden_label_or_reference_inputs_opened"]:
            raise AssertionError(f"label/reference input opened by scorer: {root}")
        scores = pd.read_csv(root / "clip_scores.csv")
        if len(scores) != unit_count or scores.unit_id.astype(int).tolist() != list(
            range(unit_count)
        ):
            raise AssertionError(f"score population mismatch: {root}")
    checks.append({"check": "label_blind_inference_ledgers", "status": "PASS"})

    final_root = PACKAGE / "outputs" / "final_confirmation"
    interval_budgets = {
        "realcartest_1630_2000": [5, 10, 20],
        "realcartest_3200_3830": [5, 10, 20, 50],
    }
    for name, budgets in interval_budgets.items():
        root = final_root / name
        scores = (
            pd.read_csv(root / "clip_inference" / "clip_scores.csv")
            .sort_values("unit_id")
            .score.to_numpy(float)
        )
        selections = pd.read_csv(root / "primary_selections.csv")
        for (method, seed, budget), group in selections.groupby(
            ["method", "seed", "budget"]
        ):
            units = group.sort_values("selection_rank").unit_id.astype(int).tolist()
            if len(units) != int(budget) or len(set(units)) != int(budget):
                raise AssertionError(
                    f"non-exact selection: {name}/{method}/s{seed}/B{budget}"
                )
        expected_by_method = {
            "clip_topk": {budget: stable_order(scores)[:budget] for budget in budgets},
            "temporal_nms_h10": {
                budget: nms_order(scores, 10)[:budget] for budget in budgets
            },
            "stratified_m1.5": {budget: strata(scores, budget) for budget in budgets},
            "dasr": {budget: dasr(scores, budget) for budget in budgets},
        }
        for method, expected_by_budget in expected_by_method.items():
            for budget, expected in expected_by_budget.items():
                actual = (
                    selections[
                        (selections.method == method)
                        & (selections.seed == 0)
                        & (selections.budget == budget)
                    ]
                    .sort_values("selection_rank")
                    .unit_id.astype(int)
                    .tolist()
                )
                if actual != expected:
                    raise AssertionError(f"selector mismatch: {name}/{method}/B{budget}")
        per_run = pd.read_csv(root / "per_budget_runs.csv")
        primary = per_run[
            per_run.method.isin(
                ["dasr", "clip_topk", "temporal_nms_h10", "stratified_m1.5", "arc_shared_k3"]
            )
        ]
        if not np.allclose(
            primary.exact_oracle_calls.to_numpy(float), primary.budget.to_numpy(float)
        ):
            raise AssertionError(f"exact-call metric mismatch: {name}")
        verify_auc_files(root, checks)
    checks.append({"check": "independent_selector_recompute", "status": "PASS"})
    checks.append({"check": "exact_call_fairness", "status": "PASS"})

    # ARC sensitivity: every threshold in the frozen sweep must reproduce the
    # same shared-K3 curve on both final intervals.
    for name, budgets in interval_budgets.items():
        root = final_root / name
        baseline = (
            pd.read_csv(root / "per_budget_summary.csv")
            .query("method == 'arc_shared_k3'")
            .sort_values("budget")
            .event_f1_mean.to_numpy(float)
        )
        for threshold in [0.1, 0.2, 0.3, 0.5]:
            sensitivity = (
                pd.read_csv(root / f"arc_sensitivity_th{threshold:.1f}_summary.csv")
                .sort_values("budget")
                .event_f1_mean.to_numpy(float)
            )
            if not np.allclose(baseline, sensitivity, atol=1e-12, rtol=0):
                raise AssertionError(f"ARC threshold sensitivity mismatch: {name}/{threshold}")
    checks.append({"check": "arc_threshold_0.1_to_0.5_sensitivity", "status": "PASS"})

    decision_path = final_root / "FINAL_CONFIRMATION_DECISION.json"
    decision = json.loads(decision_path.read_text())
    sparse_auc = pd.read_csv(final_root / "realcartest_1630_2000" / "event_f1_auc.csv")
    rich_auc = pd.read_csv(final_root / "realcartest_3200_3830" / "event_f1_auc.csv")

    def value(frame: pd.DataFrame, method: str) -> float:
        return float(frame.loc[frame.method == method, "event_f1_auc"].iloc[0])

    sparse_dasr = value(sparse_auc, "dasr")
    sparse_arc = value(sparse_auc, "arc_shared_k3")
    rich_dasr = value(rich_auc, "dasr")
    rich_arc = value(rich_auc, "arc_shared_k3")
    rich_clip = value(rich_auc, "clip_topk")
    rich_nms = value(rich_auc, "temporal_nms_h10")
    recomputed_pass = (
        rich_dasr > rich_arc
        and rich_dasr > rich_clip
        and rich_dasr > rich_nms
        and sparse_dasr >= sparse_arc
        and (rich_dasr + sparse_dasr) / 2 > (rich_arc + sparse_arc) / 2
    )
    if decision["decision"] != "CONFIRMED_GO" or not recomputed_pass:
        raise AssertionError("final decision does not follow frozen rule")
    checks.append({"check": "final_decision_recompute", "status": "PASS"})

    # Post-hoc ARC seed audit: verify stored seed-level summaries and confirm
    # that seeds 0--4 reproduce the sealed gate's per-seed AUCs.
    seed_root = final_root / "posthoc_arc_seed_audit"
    seed_summary = json.loads((seed_root / "SUMMARY.json").read_text())
    if seed_summary["audit_status"] != "COMPLETE":
        raise AssertionError("ARC seed audit is incomplete")
    for interval in seed_summary["intervals"]:
        name = interval["dataset"]
        seed_auc = pd.read_csv(seed_root / f"{name}_per_seed_auc.csv").sort_values("seed")
        values = seed_auc.event_f1_auc.to_numpy(float)
        if len(values) != int(interval["seed_count"]):
            raise AssertionError(f"ARC seed count mismatch: {name}")
        recorded_stats = {
            "arc_seed_auc_mean": float(values.mean()),
            "arc_seed_auc_std_population": float(values.std(ddof=0)),
            "arc_seed_auc_min": float(values.min()),
            "arc_seed_auc_median": float(np.median(values)),
            "arc_seed_auc_max": float(values.max()),
        }
        for key, actual in recorded_stats.items():
            if not math.isclose(actual, float(interval[key]), rel_tol=0, abs_tol=1e-12):
                raise AssertionError(f"ARC seed summary mismatch: {name}/{key}")
        gate = pd.read_csv(final_root / name / "per_budget_runs.csv")
        gate = gate[gate.method == "arc_shared_k3"]
        budgets = interval_budgets[name]
        for seed in range(5):
            curve = gate[gate.seed == seed].sort_values("budget")
            gate_auc = normalized_auc(
                budgets, curve.event_f1.to_numpy(float).tolist()
            )
            audit_auc = float(seed_auc.loc[seed_auc.seed == seed, "event_f1_auc"].iloc[0])
            if not math.isclose(gate_auc, audit_auc, rel_tol=0, abs_tol=1e-12):
                raise AssertionError(f"ARC sealed-seed replay mismatch: {name}/s{seed}")
    checks.append({"check": "posthoc_arc_1000_seed_summary", "status": "PASS"})

    # PSTR is exploratory, but its mechanical claims and nested-domain audit
    # are independently recomputed here from the public proxy inputs.
    pstr_root = PACKAGE / "outputs" / "pstr_exploration"
    pstr_selections = pd.read_csv(pstr_root / "selections.csv")
    pstr_runs = pd.read_csv(pstr_root / "per_budget_runs.csv")
    pstr_grid = pd.read_csv(pstr_root / "parameter_grid_auc.csv")
    proxy_sources = {
        "heldout": REPO / "outputs" / "real_video_protocol_pilot_v1" / "frame_scores_adapter_ready.csv",
        "confirmatory": final_root.parent / "confirmatory" / "adapter_inputs" / "frame_scores_adapter_ready.csv",
        "realcartest_1630_2000": final_root / "realcartest_1630_2000" / "adapter_inputs" / "frame_scores_adapter_ready.csv",
        "realcartest_3200_3830": final_root / "realcartest_3200_3830" / "adapter_inputs" / "frame_scores_adapter_ready.csv",
    }
    for (name, overhead, budget), group in pstr_selections.groupby(
        ["dataset", "overhead", "budget"]
    ):
        source = pd.read_csv(proxy_sources[name]).sort_values("frame_idx")
        scores = source.proxy_score.to_numpy(float)
        expected = pstr(scores, int(budget), float(overhead))
        actual = group.sort_values("selection_rank").unit_id.astype(int).tolist()
        if actual != expected or len(set(actual)) != int(budget):
            raise AssertionError(f"PSTR selector mismatch: {name}/{overhead}/B{budget}")
    if not np.allclose(
        pstr_runs.exact_oracle_calls.to_numpy(float), pstr_runs.budget.to_numpy(float)
    ):
        raise AssertionError("PSTR exact-call mismatch")
    for (name, overhead), group in pstr_runs.groupby(["dataset", "method"]):
        curve = group.sort_values("budget")
        computed = normalized_auc(
            curve.budget.astype(int).tolist(), curve.event_f1.to_numpy(float).tolist()
        )
        numeric_overhead = float(str(overhead).removeprefix("pstr_overhead_"))
        recorded = pstr_grid[
            (pstr_grid.dataset == name)
            & np.isclose(pstr_grid.overhead.astype(float), numeric_overhead)
        ]
        if len(recorded) != 1 or not math.isclose(
            computed, float(recorded.event_f1_auc.iloc[0]), rel_tol=0, abs_tol=1e-12
        ):
            raise AssertionError(f"PSTR AUC mismatch: {name}/{overhead}")
    loo = pd.read_csv(pstr_root / "leave_one_domain_out.csv")
    domain_names = sorted(pstr_grid.dataset.unique().tolist())
    for _, row in loo.iterrows():
        heldout_name = str(row.heldout_domain)
        training = pstr_grid[pstr_grid.dataset != heldout_name]
        means = training.groupby("overhead").event_f1_auc.mean()
        best = float(means.max())
        selected = min(value for value, score in means.items() if np.isclose(score, best))
        test_auc = float(
            pstr_grid[
                (pstr_grid.dataset == heldout_name)
                & np.isclose(pstr_grid.overhead.astype(float), selected)
            ].event_f1_auc.iloc[0]
        )
        if not math.isclose(float(row.selected_overhead), selected, abs_tol=1e-12):
            raise AssertionError(f"PSTR LOO selection mismatch: {heldout_name}")
        if not math.isclose(float(row.test_pstr_event_f1_auc), test_auc, abs_tol=1e-12):
            raise AssertionError(f"PSTR LOO AUC mismatch: {heldout_name}")
    checks.append({"check": "pstr_selector_auc_and_loo_recompute", "status": "PASS"})

    # Superseding five-domain PSTR exploration, including dataset3 and
    # machine-readable public-proxy curves.
    pstr_v2_root = PACKAGE / "outputs" / "pstr_exploration_v2"
    pstr_v2_selections = pd.read_csv(pstr_v2_root / "selections.csv")
    pstr_v2_runs = pd.read_csv(pstr_v2_root / "per_budget_runs.csv")
    pstr_v2_grid = pd.read_csv(pstr_v2_root / "parameter_grid_auc.csv")
    dataset3_proxy = pd.read_csv(G_STRICT_PROXY := (
        REPO
        / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
        / "agent_run"
        / "clean_baseline_benchmark_v2_strict"
        / "frozen_inputs"
        / "public_proxy.csv"
    ))
    dataset3_proxy = (
        dataset3_proxy[dataset3_proxy.proxy_name == "score_fusion_yolo_motion"]
        .sort_values("unit_id")
        .proxy_score_normalized.to_numpy(float)
    )
    pstr_v2_proxy = {
        "dataset3_development": dataset3_proxy,
        "realcartest_2000_3200": pd.read_csv(proxy_sources["heldout"])
        .sort_values("frame_idx")
        .proxy_score.to_numpy(float),
        "confirmatory": pd.read_csv(proxy_sources["confirmatory"])
        .sort_values("frame_idx")
        .proxy_score.to_numpy(float),
        "realcartest_1630_2000": pd.read_csv(proxy_sources["realcartest_1630_2000"])
        .sort_values("frame_idx")
        .proxy_score.to_numpy(float),
        "realcartest_3200_3830": pd.read_csv(proxy_sources["realcartest_3200_3830"])
        .sort_values("frame_idx")
        .proxy_score.to_numpy(float),
    }
    for (domain, overhead, budget), group in pstr_v2_selections.groupby(
        ["domain", "overhead", "budget"]
    ):
        expected = pstr(pstr_v2_proxy[domain], int(budget), float(overhead))
        actual = group.sort_values("selection_rank").unit_id.astype(int).tolist()
        if actual != expected or len(actual) != int(budget):
            raise AssertionError(f"PSTR v2 selector mismatch: {domain}/{overhead}/B{budget}")
    if not np.allclose(
        pstr_v2_runs.exact_oracle_calls.to_numpy(float), pstr_v2_runs.budget.to_numpy(float)
    ):
        raise AssertionError("PSTR v2 exact-call mismatch")
    for (domain, method), group in pstr_v2_runs.groupby(["domain", "method"]):
        curve = group.sort_values("budget")
        computed = normalized_auc(
            curve.budget.astype(int).tolist(), curve.event_f1.to_numpy(float).tolist()
        )
        numeric_overhead = float(str(method).removeprefix("pstr_overhead_"))
        recorded = pstr_v2_grid[
            (pstr_v2_grid.domain == domain)
            & np.isclose(pstr_v2_grid.overhead.astype(float), numeric_overhead)
        ]
        if len(recorded) != 1 or not math.isclose(
            computed, float(recorded.event_f1_auc.iloc[0]), rel_tol=0, abs_tol=1e-12
        ):
            raise AssertionError(f"PSTR v2 AUC mismatch: {domain}/{method}")
    loo_v2 = pd.read_csv(pstr_v2_root / "leave_one_domain_out.csv")
    for _, row in loo_v2.iterrows():
        heldout = str(row.heldout_domain)
        means = pstr_v2_grid[pstr_v2_grid.domain != heldout].groupby("overhead").event_f1_auc.mean()
        best = float(means.max())
        selected = min(value for value, score in means.items() if np.isclose(score, best))
        test_auc = float(
            pstr_v2_grid[
                (pstr_v2_grid.domain == heldout)
                & np.isclose(pstr_v2_grid.overhead.astype(float), selected)
            ].event_f1_auc.iloc[0]
        )
        if not math.isclose(float(row.selected_overhead), selected, abs_tol=1e-12):
            raise AssertionError(f"PSTR v2 LOO selection mismatch: {heldout}")
        if not math.isclose(float(row.test_pstr_event_f1_auc), test_auc, abs_tol=1e-12):
            raise AssertionError(f"PSTR v2 LOO AUC mismatch: {heldout}")
    baseline_v2 = pd.read_csv(pstr_v2_root / "baseline_per_budget_runs.csv")
    proxy_curves = baseline_v2[baseline_v2.method == "proxy_topk"]
    if set(proxy_curves.domain) != set(pstr_v2_proxy):
        raise AssertionError("PSTR v2 does not preserve every pure-proxy curve")
    if not np.allclose(
        proxy_curves.exact_oracle_calls.to_numpy(float), proxy_curves.budget.to_numpy(float)
    ):
        raise AssertionError("PSTR v2 proxy curve exact-call mismatch")
    v5 = json.loads((PACKAGE / "config" / "frozen_external_confirmation_v5.json").read_text())
    v5_hashes = {
        PACKAGE / "scripts" / "run_pstr_exploration_v2.py": v5["development_evidence"]["runner_sha256"],
        pstr_v2_root / "DECISION.json": v5["development_evidence"]["decision_sha256"],
        pstr_v2_root / "leave_one_domain_out.csv": v5["development_evidence"]["leave_one_domain_out_sha256"],
        pstr_v2_root / "selected_candidate_auc.csv": v5["development_evidence"]["selected_candidate_auc_sha256"],
        pstr_v2_root / "baseline_auc.csv": v5["development_evidence"]["baseline_auc_sha256"],
        pstr_v2_root / "baseline_per_budget_runs.csv": v5["development_evidence"]["baseline_per_budget_runs_sha256"],
        PACKAGE / "scripts" / "seal_pstr_selections.py": v5["candidate"]["label_blind_selector_sha256"],
        PACKAGE / "scripts" / "seal_dpp_baseline.py": v5["comparators"]["dpp"]["selector_sha256"],
        REPO / "refe_repos" / "adapter" / "arc_baseline" / "run.py": v5["comparators"]["arc_shared_k3"]["adapter_sha256"],
        REPO / "refe_repos" / "adapter" / "supg_baseline" / "run.py": v5["comparators"]["supg"]["adapter_sha256"],
        G_STRICT_PROXY: "7edd7fc87f849ce9f32bb26edc368aaf986952100c3f2184cd95cef015c33815",
        REPO / "scripts" / "roadclip_code" / "roadclip_budget_v2" / "01_filter_road_segments.py": v5["external_public_proxy"]["road_segment_filter_script_sha256"],
        REPO / "scripts" / "roadclip_code" / "roadclip_budget_v2" / "02_make_road_clips.py": v5["external_public_proxy"]["clip_script_sha256"],
        REPO / "scripts" / "roadclip_code" / "roadclip_budget_v2" / "03_run_proxy_scoring.py": v5["external_public_proxy"]["proxy_script_sha256"],
        REPO / "scripts" / "roadclip_code" / "roadclip_budget_v2" / "common.py": v5["external_public_proxy"]["common_script_sha256"],
        REPO / "scripts" / "roadclip_code" / "roadclip_budget_v2" / "config.yaml": v5["external_public_proxy"]["config_sha256"],
        REPO / "models" / "yolo" / "yolov8n.pt": v5["external_public_proxy"]["yolo_model_sha256"],
        REPO / "Audited_Event_Hypothesis_AQP_Design_Pack_v1" / "agent_run" / "clean_baseline_benchmark_v2_strict" / "scripts" / "benchmark_lib.py": v5["shared_evaluation"]["materializer_and_evaluator_implementation_sha256"],
        PACKAGE / "scripts" / "run_frozen_gate.py": v5["comparators"]["mmr_and_facility"]["implementation_sha256"],
        PACKAGE / "scripts" / "score_heldout_clip.py": v5["comparators"]["clip_topk"]["scorer_sha256"],
    }
    for path, expected in v5_hashes.items():
        if sha256(path) != expected:
            raise AssertionError(f"PSTR v5 bound artifact hash mismatch: {path}")
    checks.append({"check": "pstr_v2_five_domain_and_v5_contract", "status": "PASS"})

    cheap_path = (
        REPO
        / "src"
        / "garc_eval"
        / "outputs"
        / "clean_interval_aqp_full_reference_v2_clean_no_leak"
        / "cheap_signals_per_unit.csv"
    )
    atom_path = REPO / "outputs" / "exsample_aware_replay" / "atomic_grid_10s.csv"
    adapter_path = REPO / "outputs" / "real_video_protocol_pilot_v1" / "frame_scores_adapter_ready.csv"
    if sha256(cheap_path) != "5a58a80010fd3f1eaee2ae88011ce48c5f50e4265320c42444ed93524c12a1ff":
        raise AssertionError("PSTR fused-proxy source hash mismatch")
    if sha256(atom_path) != "bd0e6ee8eac9e44a8987d5e6df7b4fd4d5adbccdeb8bf132cf91f21cbd5a6afc":
        raise AssertionError("PSTR atomic-grid proxy hash mismatch")
    if sha256(adapter_path) != "6ca8c9eebc8b5808abd933879cca3890bda799128ac9e0911ebfc988591d66bf":
        raise AssertionError("PSTR heldout-adapter proxy hash mismatch")
    cheap = pd.read_csv(cheap_path)
    cheap["bin"] = np.floor(cheap.t_start.astype(float) / 10.0).astype(int)
    recomputed_fused = cheap.groupby("bin").cheap_fused_score.max().sort_index().to_numpy(float)
    atom = pd.read_csv(atom_path).sort_values("t_start")
    adapter = pd.read_csv(adapter_path).sort_values("frame_idx")
    if not np.allclose(recomputed_fused, atom.prior_score_max.to_numpy(float), atol=0, rtol=0):
        raise AssertionError("PSTR fused proxy does not reconstruct atomic grid")
    if not np.allclose(
        atom.prior_score_max.to_numpy(float), adapter.proxy_score.to_numpy(float), atol=0, rtol=0
    ):
        raise AssertionError("PSTR heldout adapter differs from atomic-grid proxy")

    roadclip_path = REPO / "experiments" / "roadclip_budget_v2" / "roadclip_budget_v2" / "proxy_scores.csv"
    if sha256(roadclip_path) != "573af538d39c2e8ad7cdc6c461f50104acd8f6b4829210064a507120286c18f8":
        raise AssertionError("PSTR RoadCLIP proxy source hash mismatch")
    roadclip = pd.read_csv(roadclip_path)
    grid_specs = [
        ("realcartest_0_1570", 0.0, "5fe80a5b4b8d0c02f0d41a301cd78af186b5ba696b2fd63eebcc43b8015fc0f7"),
        ("realcartest_1630_2000", 1630.0, "2fd09a701ad7db199536a9e202411fb4f00c095b7c5d4eee4397820c58fc61cb"),
        ("realcartest_3200_3830", 3200.0, "1dfacb84a43f06235e7c501c7b6eef8afa8379871ca0abe534a66084890add1f"),
    ]
    for name, offset, expected_hash in grid_specs:
        grid_path = REPO / "outputs" / "late_aqp_frozen_cross_segment_v1" / f"grid_{name}.csv"
        if sha256(grid_path) != expected_hash:
            raise AssertionError(f"PSTR RoadCLIP-derived grid hash mismatch: {name}")
        grid = pd.read_csv(grid_path)
        recomputed = []
        for _, unit in grid.iterrows():
            start = offset + float(unit.t_start)
            end = offset + float(unit.t_end)
            overlap = roadclip[
                (roadclip.start_time.astype(float) < end)
                & (roadclip.end_time.astype(float) > start)
            ]
            recomputed.append(float(overlap.score_count.max()) if len(overlap) else 0.0)
        if not np.allclose(
            np.asarray(recomputed), grid.prior_score_max.to_numpy(float), atol=0, rtol=0
        ):
            raise AssertionError(f"PSTR RoadCLIP proxy reconstruction mismatch: {name}")
    checks.append({"check": "pstr_public_proxy_provenance", "status": "PASS"})

    manifest_path = PACKAGE / "FINAL_OUTPUT_MANIFEST.csv"
    manifest = pd.read_csv(manifest_path)
    for _, row in manifest.iterrows():
        path = PACKAGE / str(row.path)
        if not path.is_file():
            raise AssertionError(f"manifest path missing: {path}")
        if path.stat().st_size != int(row.size_bytes) or sha256(path) != row.sha256:
            raise AssertionError(f"manifest mismatch: {path}")
    checks.append({"check": "final_output_manifest", "status": "PASS"})

    result = {
        "status": "PASS",
        "checks": checks,
        "frozen_protocol_sha256": EXPECTED_HASHES[
            PACKAGE / "config" / "frozen_continuation_v3.json"
        ],
        "next_candidate_protocol_sha256": EXPECTED_HASHES[
            PACKAGE / "config" / "frozen_external_confirmation_v5.json"
        ],
        "physical_exact_oracle_vlm_calls": 0,
    }
    output = PACKAGE / "outputs" / "VERIFICATION.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
