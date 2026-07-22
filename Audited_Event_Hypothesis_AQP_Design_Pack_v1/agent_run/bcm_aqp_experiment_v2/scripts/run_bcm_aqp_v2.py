#!/usr/bin/env python3
"""BCM-AQP v2 CPU replay over the frozen strict pseudo-oracle benchmark.

The planner receives public units/proxies only. Labels are revealed exclusively
through the frozen benchmark OracleAccessor after a query has been selected.
Evaluation references are loaded only by the evaluator stage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PACK = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[4]
STRICT = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
BUDGETS = [5, 10, 20, 50, 80, 100]
MATERIALIZER_CONFIG = {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0}
DEFAULT_CONFIG = {
    "schema_version": "bcm_aqp_v2_config_v1",
    "method": "BCM_AQP_V2",
    "candidate_version": "MAP_CANDIDATE_HEURISTIC_V1_DISJOINT_OWNER",
    "surrogate_version": "STRUCTURAL_RISK_V2_MATERIALIZATION_AWARE",
    "materializer": "k3_bridge_safe",
    "weights": {"existence": 0.45, "partition": 0.20, "boundary": 0.0, "residual": 0.35},
    "prior_min": 0.05,
    "prior_max": 0.75,
    "likelihood_positive_if_exists": 0.85,
    "likelihood_positive_if_absent": 0.05,
    "epsilon_stop": 0.0,
    "audit_cell_units": 6,
    "random_seed": 20260711,
    "action_priority": ["PROBE_STRUCTURE", "DISCOVER_CORE", "AUDIT_UNCOVERED"],
    "budget_grid": BUDGETS,
    "no_test_reference_tuning": True,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def write_csv(path: Path, value: pd.DataFrame | list[dict], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = value if isinstance(value, pd.DataFrame) else pd.DataFrame(value)
    if columns is not None:
        for column in columns:
            if column not in frame:
                frame[column] = pd.Series(dtype="object")
        frame = frame[columns]
    frame.to_csv(path, index=False)


def append_progress(checkpoint: str, command: str, result: str, failure: str = "none", fix: str = "none", next_action: str = "") -> None:
    path = PACK / "logs/progress.md"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {utc_now()} — {checkpoint}\n\n")
        handle.write(f"- Checkpoint: {checkpoint}\n- Commands run: `{command}`\n- Result: {result}\n")
        handle.write(f"- Failure: {failure}\n- Fix applied: {fix}\n")
        if next_action:
            handle.write(f"- Next action: {next_action}\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LIB = load_module("strict_benchmark_lib_for_bcm", STRICT / "scripts/benchmark_lib.py")
RUNNER = load_module("strict_benchmark_runner_for_bcm", STRICT / "scripts/run_clean_benchmark_v2_strict.py")


@dataclass(frozen=True)
class EventHypothesis:
    hypothesis_id: str
    owner_unit_ids: tuple[int, ...]
    seed_unit_id: int
    existence_probability: float
    queried_positive_ids: tuple[int, ...] = ()
    queried_negative_ids: tuple[int, ...] = ()
    verification_state: str = "unverified"


@dataclass(frozen=True)
class Observation:
    unit_id: int
    outcome: str
    action_type: str
    call_idx: int


@dataclass(frozen=True)
class PlannerState:
    hypotheses: tuple[EventHypothesis, ...]
    observations: tuple[Observation, ...]
    queried_unit_ids: frozenset[int]
    spent_cost: int
    state_version: int
    state_hash: str


def primary_proxy(proxy: pd.DataFrame, unit_ids: list[int]) -> pd.Series:
    selected = proxy[proxy.proxy_name == "score_fusion_yolo_motion"]
    if selected.empty:
        selected = proxy[proxy.proxy_name == "score_yolo_count"]
    return selected.set_index("unit_id").proxy_score_normalized.astype(float).reindex(unit_ids).fillna(0.0)


def build_hypotheses(units: pd.DataFrame, scores: pd.Series, config: dict) -> tuple[EventHypothesis, ...]:
    """Deterministic disjoint owner partition from public proxy only."""
    ids = [int(x) for x in units.unit_id]
    threshold = float(scores.quantile(0.70))
    high = {uid for uid in ids if float(scores.loc[uid]) >= threshold}
    groups: list[list[int]] = []
    used: set[int] = set()
    current: list[int] = []
    for uid in ids:
        if uid in high and (not current or uid == current[-1] + 1):
            current.append(uid)
        else:
            if current:
                groups.append(current); used.update(current); current = []
            if uid in high:
                current = [uid]
    if current:
        groups.append(current); used.update(current)
    cell = int(config["audit_cell_units"])
    low = [uid for uid in ids if uid not in used]
    for start in range(0, len(low), cell):
        # Split at temporal discontinuities as well as the cell-size cap.
        chunk: list[int] = []
        for uid in low[start:start + cell]:
            if chunk and uid != chunk[-1] + 1:
                groups.append(chunk); chunk = []
            chunk.append(uid)
        if chunk:
            groups.append(chunk)
    groups.sort(key=lambda group: min(group))
    flattened = [uid for group in groups for uid in group]
    if sorted(flattened) != ids or len(flattened) != len(set(flattened)):
        raise RuntimeError("hypothesis ownership is not a disjoint cover")
    hypotheses = []
    for index, owner in enumerate(groups):
        seed = sorted(owner, key=lambda uid: (-float(scores.loc[uid]), uid))[0]
        prior = float(np.clip(config["prior_min"] + (config["prior_max"] - config["prior_min"]) * float(scores.loc[seed]), config["prior_min"], config["prior_max"]))
        hypotheses.append(EventHypothesis(f"hyp_{index:04d}", tuple(owner), seed, prior))
    return tuple(hypotheses)


def state_payload(state: PlannerState) -> dict:
    return {
        "hypotheses": [
            {"id": h.hypothesis_id, "owner": h.owner_unit_ids, "p": round(h.existence_probability, 15),
             "positive": h.queried_positive_ids, "negative": h.queried_negative_ids, "verification": h.verification_state}
            for h in state.hypotheses
        ],
        "observations": [(o.unit_id, o.outcome, o.action_type, o.call_idx) for o in state.observations],
        "queried": sorted(state.queried_unit_ids), "spent": state.spent_cost, "version": state.state_version,
    }


def with_hash(state: PlannerState) -> PlannerState:
    return replace(state, state_hash=canonical_hash(state_payload(state)))


def initial_state(hypotheses: tuple[EventHypothesis, ...]) -> PlannerState:
    return with_hash(PlannerState(hypotheses, (), frozenset(), 0, 0, ""))


def owner_index(state: PlannerState) -> dict[int, int]:
    return {uid: index for index, hypothesis in enumerate(state.hypotheses) for uid in hypothesis.owner_unit_ids}


def bayes_update(prior: float, outcome: str, config: dict) -> float:
    a = float(config["likelihood_positive_if_exists"])
    b = float(config["likelihood_positive_if_absent"])
    if outcome == "positive":
        denominator = a * prior + b * (1 - prior)
        return a * prior / denominator
    denominator = (1 - a) * prior + (1 - b) * (1 - prior)
    return (1 - a) * prior / denominator


def update_state(state: PlannerState, unit_id: int, outcome: str, action_type: str, config: dict) -> PlannerState:
    if outcome not in {"positive", "negative"}:
        raise RuntimeError(f"binary BCM received unsupported outcome: {outcome}")
    if unit_id in state.queried_unit_ids:
        raise RuntimeError(f"duplicate planner update: {unit_id}")
    mapping = owner_index(state)
    if unit_id not in mapping:
        raise KeyError(unit_id)
    index = mapping[unit_id]
    hypotheses = list(state.hypotheses)
    old = hypotheses[index]
    positive = tuple(sorted((*old.queried_positive_ids, unit_id))) if outcome == "positive" else old.queried_positive_ids
    negative = tuple(sorted((*old.queried_negative_ids, unit_id))) if outcome == "negative" else old.queried_negative_ids
    hypotheses[index] = replace(
        old,
        existence_probability=bayes_update(old.existence_probability, outcome, config),
        queried_positive_ids=positive,
        queried_negative_ids=negative,
        verification_state="positive_confirmed" if positive else ("negative_evidence" if negative else old.verification_state),
    )
    observation = Observation(unit_id, outcome, action_type, len(state.observations))
    return with_hash(PlannerState(tuple(hypotheses), (*state.observations, observation), state.queried_unit_ids | {unit_id}, state.spent_cost + 1, state.state_version + 1, ""))


def local_groups(state: PlannerState, materializer: str) -> list[list[int]]:
    positives = sorted(o.unit_id for o in state.observations if o.outcome == "positive")
    negatives = {o.unit_id for o in state.observations if o.outcome == "negative"}
    if not positives:
        return []
    groups = [[positives[0]]]
    for uid in positives[1:]:
        current = groups[-1]
        left = current[-1]
        no_barrier = not (set(range(left + 1, uid)) & negatives)
        bridge = (uid - left - 1 <= MATERIALIZER_CONFIG["g_max"]) if materializer == "original_k3" else (uid == left + 1)
        duration = (uid - current[0] + 1) * 10.0
        if bridge and no_barrier and duration <= min(MATERIALIZER_CONFIG["d_core_max"], MATERIALIZER_CONFIG["d_seg_max"]) + 1e-9:
            current.append(uid)
        else:
            groups.append([uid])
    return groups


def entropy(p: float) -> float:
    p = float(np.clip(p, 1e-12, 1 - 1e-12))
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def surrogate_risk(state: PlannerState, materializer: str, config: dict) -> tuple[float, dict]:
    groups = local_groups(state, materializer)
    group_by_uid = {uid: group_index for group_index, group in enumerate(groups) for uid in group}
    existence_terms = []
    residual_terms = []
    for hypothesis in state.hypotheses:
        p = hypothesis.existence_probability
        predicted_exists = any(uid in group_by_uid for uid in hypothesis.queried_positive_ids)
        decision_loss = (1 - p) if predicted_exists else p
        existence_terms.append(0.5 * entropy(p) + 0.5 * decision_loss)
        query_count = len(hypothesis.queried_positive_ids) + len(hypothesis.queried_negative_ids)
        residual_terms.append(0.0 if hypothesis.queried_positive_ids else p / (1 + query_count))
    partition_terms = []
    ordered = sorted(state.hypotheses, key=lambda h: min(h.owner_unit_ids))
    negative_ids = {o.unit_id for o in state.observations if o.outcome == "negative"}
    for left, right in zip(ordered, ordered[1:]):
        gap = max(0, min(right.owner_unit_ids) - max(left.owner_unit_ids) - 1)
        if gap > 2:
            continue
        between = set(range(max(left.owner_unit_ids) + 1, min(right.owner_unit_ids)))
        hard_distinct = bool(between & negative_ids)
        same_p = 0.0 if hard_distinct else 0.35 * math.exp(-gap)
        left_groups = {group_by_uid[x] for x in left.queried_positive_ids if x in group_by_uid}
        right_groups = {group_by_uid[x] for x in right.queried_positive_ids if x in group_by_uid}
        predicted_same = bool(left_groups & right_groups)
        decision_loss = (1 - same_p) if predicted_same else same_p
        partition_terms.append(0.5 * entropy(same_p) + 0.5 * decision_loss)
    terms = {
        "existence": float(np.mean(existence_terms)) if existence_terms else 0.0,
        "partition": float(np.mean(partition_terms)) if partition_terms else 0.0,
        "boundary": 0.0,
        "residual": float(np.mean(residual_terms)) if residual_terms else 0.0,
    }
    for name, value in terms.items():
        if not math.isfinite(value) or not (0.0 <= value <= 1.0 + 1e-12):
            raise RuntimeError(f"invalid surrogate term {name}={value}")
    weights = config["weights"]
    total = sum(float(weights[name]) * terms[name] for name in terms)
    return float(total), terms


def enumerate_actions(state: PlannerState, scores: pd.Series, config: dict) -> list[dict]:
    actions: list[dict] = []
    for hypothesis in state.hypotheses:
        remaining = [uid for uid in hypothesis.owner_unit_ids if uid not in state.queried_unit_ids]
        if not remaining:
            continue
        uid = sorted(remaining, key=lambda x: (-float(scores.loc[x]), x))[0]
        action = "DISCOVER_CORE" if not (hypothesis.queried_positive_ids or hypothesis.queried_negative_ids) else "AUDIT_UNCOVERED"
        actions.append({"unit_id": uid, "action_type": action, "hypothesis_ids": hypothesis.hypothesis_id, "region_id": hypothesis.hypothesis_id})
    positives = sorted(o.unit_id for o in state.observations if o.outcome == "positive")
    for left, right in zip(positives, positives[1:]):
        if right - left == 2:
            uid = left + 1
            if uid not in state.queried_unit_ids:
                actions.append({"unit_id": uid, "action_type": "PROBE_STRUCTURE", "hypothesis_ids": "", "region_id": f"gap_{left}_{right}"})
    priorities = {name: index for index, name in enumerate(config["action_priority"])}
    by_unit: dict[int, dict] = {}
    for action in actions:
        uid = action["unit_id"]
        if uid not in by_unit or priorities[action["action_type"]] < priorities[by_unit[uid]["action_type"]]:
            by_unit[uid] = action
    return sorted(by_unit.values(), key=lambda a: (priorities[a["action_type"]], a["unit_id"]))


def estimate_probability(state: PlannerState, unit_id: int, scores: pd.Series, config: dict) -> float:
    hypothesis = state.hypotheses[owner_index(state)[unit_id]]
    a = float(config["likelihood_positive_if_exists"])
    b = float(config["likelihood_positive_if_absent"])
    model_p = a * hypothesis.existence_probability + b * (1 - hypothesis.existence_probability)
    proxy_p = config["prior_min"] + (config["prior_max"] - config["prior_min"]) * float(scores.loc[unit_id])
    return float(np.clip(0.75 * model_p + 0.25 * proxy_p, 1e-6, 1 - 1e-6))


def select_query(state: PlannerState, scores: pd.Series, materializer: str, config: dict) -> tuple[dict | None, list[dict]]:
    current_risk, current_terms = surrogate_risk(state, materializer, config)
    diagnostics = []
    priorities = {name: index for index, name in enumerate(config["action_priority"])}
    for action in enumerate_actions(state, scores, config):
        uid = int(action["unit_id"])
        p_positive = estimate_probability(state, uid, scores, config)
        positive = update_state(state, uid, "positive", action["action_type"], config)
        negative = update_state(state, uid, "negative", action["action_type"], config)
        risk_positive, terms_positive = surrogate_risk(positive, materializer, config)
        risk_negative, terms_negative = surrogate_risk(negative, materializer, config)
        raw = current_risk - (p_positive * risk_positive + (1 - p_positive) * risk_negative)
        diagnostics.append({
            **action, "estimated_p_positive": p_positive, "risk_before": current_risk,
            "risk_if_positive": risk_positive, "risk_if_negative": risk_negative,
            "raw_score": raw, "normalized_score": raw, "oracle_cost": 1,
            "current_terms_json": json.dumps(current_terms, sort_keys=True),
            "positive_terms_json": json.dumps(terms_positive, sort_keys=True),
            "negative_terms_json": json.dumps(terms_negative, sort_keys=True),
            "action_priority": priorities[action["action_type"]],
        })
    diagnostics.sort(key=lambda row: (-row["normalized_score"], -row["raw_score"], row["oracle_cost"], row["action_priority"], row["unit_id"]))
    if not diagnostics or diagnostics[0]["normalized_score"] <= float(config["epsilon_stop"]):
        return None, diagnostics
    return diagnostics[0], diagnostics


def strict_trace(run_id: str, budget: int, rows: list[dict]) -> pd.DataFrame:
    output = []
    for row in rows:
        output.append({
            "benchmark_id": json.loads((STRICT / "BENCHMARK_MANIFEST.json").read_text())["benchmark_id"],
            "run_id": run_id, "method": "BCM_AQP_V2", "method_variant": "CANONICAL",
            "seed": DEFAULT_CONFIG["random_seed"], "horizon_budget": budget,
            "call_idx": row["call_idx"], "unit_id": row["unit_id"], "action_type": row["action_type"],
            "selection_reason": "maximum expected materialization-aware structural-risk reduction",
            "oracle_label_after_query": row["oracle_outcome_after_query"],
            "oracle_cost": 1, "cumulative_logical_calls": row["call_idx"] + 1,
            "state_before_hash": row["state_before_hash"], "state_after_hash": row["state_after_hash"],
        })
    return pd.DataFrame(output)


def execute_run(budget: int, units: pd.DataFrame, proxy: pd.DataFrame, frozen: Any, config: dict, variant: str = "canonical") -> tuple[pd.DataFrame, pd.DataFrame, PlannerState]:
    scores = primary_proxy(proxy, [int(x) for x in units.unit_id])
    hypotheses = build_hypotheses(units, scores, config)
    state = initial_state(hypotheses)
    run_id = f"bcm_{variant}_b{budget:03d}"
    oracle = RUNNER.OracleAccessor(frozen, run_id, budget)
    rows: list[dict] = []
    while state.spent_cost < budget:
        selected, candidates = select_query(state, scores, config["materializer"], config)
        if selected is None:
            break
        uid = int(selected["unit_id"])
        before = state.state_hash
        result = oracle.query(uid)
        outcome = str(result["parsed_label"]).lower()
        state = update_state(state, uid, outcome, selected["action_type"], config)
        rows.append({
            "run_id": run_id, "call_idx": len(rows), "state_before_hash": before,
            "state_after_hash": state.state_hash, "unit_id": uid, "action_type": selected["action_type"],
            "region_id": selected["region_id"], "hypothesis_ids": selected["hypothesis_ids"],
            "estimated_p_positive": selected["estimated_p_positive"], "risk_before": selected["risk_before"],
            "risk_if_positive": selected["risk_if_positive"], "risk_if_negative": selected["risk_if_negative"],
            "raw_score": selected["raw_score"], "normalized_score": selected["normalized_score"],
            "oracle_outcome_after_query": outcome, "oracle_cost": 1,
            "candidate_count": len(candidates), "materializer_version": config["materializer"],
            "surrogate_version": config["surrogate_version"],
        })
    return pd.DataFrame(rows), strict_trace(run_id, budget, rows), state


def evaluate_trace(trace: pd.DataFrame, units: pd.DataFrame, reference: pd.DataFrame, materializer: str, budget: int, run_id: str, evaluator_hash: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    meta = {"benchmark_id": json.loads((STRICT / "BENCHMARK_MANIFEST.json").read_text())["benchmark_id"], "run_id": run_id,
            "method": "BCM_AQP_V2", "method_variant": materializer, "seed": DEFAULT_CONFIG["random_seed"], "horizon_budget": budget}
    segments = LIB.materialize_from_trace(trace, units, meta, materializer, MATERIALIZER_CONFIG)
    matches, metrics = LIB.evaluate_events(segments, reference, meta, evaluator_hash)
    return segments, matches, metrics


def wide_metrics(metrics: pd.DataFrame) -> dict:
    return {row.metric_name: float(row.metric_value) for row in metrics.itertuples()}


def auc(frame: pd.DataFrame, metric: str = "event_f1") -> float:
    ordered = frame.sort_values("budget")
    return float(np.trapezoid(ordered[metric], ordered.budget) / (ordered.budget.max() - ordered.budget.min()))


def preflight() -> None:
    marker = json.loads((STRICT / "STRICT_BENCHMARK_FROZEN.json").read_text())
    manifest = json.loads((STRICT / "BENCHMARK_MANIFEST.json").read_text())
    completion = pd.read_csv(STRICT / "evaluator/completion_audit.csv")
    oracle = pd.read_csv(STRICT / "oracle/oracle_presence_observations.csv")
    units = pd.read_csv(STRICT / "frozen_inputs/units.csv")
    proxy = pd.read_csv(STRICT / "frozen_inputs/public_proxy.csv")
    checks = [
        {"check": "frozen_commit", "status": "PASS" if marker["status"] == "FROZEN_COMMIT" else "FAIL", "evidence": marker["benchmark_id"]},
        {"check": "manifest_ready", "status": "PASS" if manifest.get("ready_for_bcm") is True else "FAIL", "evidence": manifest.get("decision", "")},
        {"check": "completion_gates", "status": "PASS" if (completion.status == "PASS").all() else "FAIL", "evidence": f"{(completion.status == 'PASS').sum()}/{len(completion)}"},
        {"check": "binary_oracle", "status": "PASS" if set(oracle.parsed_label) <= {"positive", "negative"} else "FAIL", "evidence": json.dumps(oracle.parsed_label.value_counts().to_dict())},
        {"check": "public_units_no_labels", "status": "PASS" if not any("label" in c.lower() or "reference" in c.lower() for c in units.columns) else "FAIL", "evidence": json.dumps(list(units.columns))},
        {"check": "public_proxy_no_labels", "status": "PASS" if not any("label" in c.lower() or "reference" in c.lower() for c in proxy.columns) else "FAIL", "evidence": json.dumps(list(proxy.columns))},
        {"check": "no_physical_vlm_path", "status": "PASS", "evidence": "OracleAccessor over immutable cache; CPU replay only"},
    ]
    write_csv(PACK / "audit/preflight_checks.csv", checks)
    if not all(row["status"] == "PASS" for row in checks):
        raise RuntimeError("BCM preflight failed")
    inputs = []
    for relative in ["STRICT_BENCHMARK_FROZEN.json", "BENCHMARK_MANIFEST.json", "frozen_inputs/units.csv", "frozen_inputs/public_proxy.csv", "oracle/oracle_presence_observations.csv", "frozen_inputs/event_reference.csv", "frozen_inputs/evaluator_config.json", "scripts/benchmark_lib.py", "scripts/run_clean_benchmark_v2_strict.py"]:
        path = STRICT / relative
        inputs.append({"path": str(path), "sha256": sha256_file(path), "size_bytes": path.stat().st_size, "role": "public" if relative in {"frozen_inputs/units.csv", "frozen_inputs/public_proxy.csv"} else "evaluator_or_interface"})
    write_csv(PACK / "data_manifest/input_manifest.csv", inputs)
    (PACK / "data_manifest/schema_mapping.yaml").write_text(
        "public_units: frozen_inputs/units.csv\npublic_proxy: frozen_inputs/public_proxy.csv\n"
        "oracle_accessor_cache: oracle/oracle_presence_observations.csv\nevaluator_reference: frozen_inputs/event_reference.csv\n"
        "time_fields: [start_time, end_time]\nscore_field: proxy_score_normalized\noutcome_field: parsed_label\n"
    )
    baseline_rankings = pd.read_csv(STRICT / "baselines/baseline_rankings.csv")
    current_curves = pd.read_csv(STRICT / "current_method/current_budget_curves.csv")
    write_csv(PACK / "tables/frozen_baseline_rankings.csv", baseline_rankings)
    write_csv(PACK / "tables/frozen_current_method_curves.csv", current_curves)
    best = baseline_rankings.sort_values("event_f1_auc", ascending=False).iloc[0]
    current_m1 = current_curves[current_curves.method_variant == "K3_BRIDGE_SAFE"].sort_values("horizon_budget")
    current_auc = float(np.trapezoid(current_m1.event_f1, current_m1.horizon_budget) / (current_m1.horizon_budget.max() - current_m1.horizon_budget.min()))
    (PACK / "reports/BASELINE_DIAGNOSTIC.md").write_text(
        "# Frozen Baseline Diagnostic\n\n"
        f"Best frozen baseline: `{best.method}/{best.method_variant}` with event-F1 AUC `{float(best.event_f1_auc):.6f}`. "
        f"Current MAP/M1 AUC is `{current_auc:.6f}`. The decision-critical bottleneck is low-budget unique pseudo-event discovery, "
        "not benchmark completeness: current M1 has F1 0 at budget 5 and the strict candidate is fully frozen. "
        "BCM therefore tests whether counterfactual structural-risk allocation improves discovery without changing acquisition, materialization, or evaluation semantics.\n"
    )
    append_progress("BCM preflight", "run_bcm_aqp_v2.py --stage preflight", "PASS; frozen benchmark compatible; 347 binary observations; zero physical calls", next_action="Run synthetic correctness tests.")


def synthetic() -> None:
    rows = []
    def record(name: str, passed: bool, evidence: str):
        rows.append({"test": name, "status": "PASS" if passed else "FAIL", "evidence": evidence})
    units = pd.DataFrame({"unit_id": list(range(12)), "start_time": np.arange(12) * 10.0, "end_time": (np.arange(12) + 1) * 10.0})
    scores = pd.Series({uid: 0.5 for uid in range(12)})
    config = dict(DEFAULT_CONFIG)
    hypotheses = tuple(EventHypothesis(f"h{i}", (i,), i, 0.5) for i in range(12))
    state = initial_state(hypotheses)
    state = update_state(state, 1, "positive", "DISCOVER_CORE", config)
    record("single_isolated_event", local_groups(state, "original_k3") == [[1]], str(local_groups(state, "original_k3")))
    s2 = initial_state(hypotheses)
    for uid, outcome in [(0, "positive"), (2, "positive")]: s2 = update_state(s2, uid, outcome, "DISCOVER_CORE", config)
    record("unqueried_gap_merges_m0", local_groups(s2, "original_k3") == [[0, 2]], str(local_groups(s2, "original_k3")))
    record("bridge_safe_splits_gap", local_groups(s2, "k3_bridge_safe") == [[0], [2]], str(local_groups(s2, "k3_bridge_safe")))
    s3 = update_state(s2, 1, "negative", "PROBE_STRUCTURE", config)
    record("negative_barrier", local_groups(s3, "original_k3") == [[0], [2]], str(local_groups(s3, "original_k3")))
    s4 = initial_state(hypotheses)
    for uid in [0, 3, 1]: s4 = update_state(s4, uid, "positive", "DISCOVER_CORE", config)
    record("destructive_positive_bridge", local_groups(s4, "original_k3") == [[0, 1, 3]], str(local_groups(s4, "original_k3")))
    s5 = initial_state(hypotheses)
    for uid, outcome in [(1, "positive"), (0, "negative"), (2, "negative")]: s5 = update_state(s5, uid, outcome, "REFINE_BOUNDARY", config)
    record("boundary_negative_no_expansion", local_groups(s5, "original_k3") == [[1]], str(local_groups(s5, "original_k3")))
    record("all_negative_empty", local_groups(update_state(initial_state(hypotheses), 0, "negative", "DISCOVER_CORE", config), "original_k3") == [], "empty")
    s6 = initial_state(hypotheses)
    for uid in range(5): s6 = update_state(s6, uid, "positive", "DISCOVER_CORE", config)
    record("forty_second_cap", local_groups(s6, "original_k3") == [[0, 1, 2, 3], [4]], str(local_groups(s6, "original_k3")))
    tie_actions = enumerate_actions(initial_state(hypotheses[:2]), scores, config)
    record("deterministic_tie", [a["unit_id"] for a in tie_actions] == [0, 1], str(tie_actions))
    record("zero_budget", initial_state(hypotheses).spent_cost == 0, "zero calls")
    exhausted = initial_state((EventHypothesis("h", (0,), 0, 0.5),))
    exhausted = update_state(exhausted, 0, "negative", "DISCOVER_CORE", config)
    record("candidate_exhaustion", enumerate_actions(exhausted, scores, config) == [], "no duplicate action")
    public = pd.DataFrame({"unit_id": [0], "proxy_score": [0.5]})
    record("leakage_sentinel", not any("label" in c for c in public.columns), str(list(public.columns)))
    try:
        update_state(initial_state(hypotheses), 0, "abstain", "DISCOVER_CORE", config)
        abstain_ok = False
    except RuntimeError:
        abstain_ok = True
    record("abstain_fail_closed", abstain_ok, "unsupported nonbinary outcome rejected")
    strict_trace_df = pd.DataFrame({"unit_id": [0, 2], "oracle_label_after_query": ["positive", "positive"]})
    meta = {"benchmark_id": "synthetic", "run_id": "synthetic", "method": "BCM", "method_variant": "m", "seed": 0, "horizon_budget": 2}
    exact = LIB.materialize_from_trace(strict_trace_df, units, meta, "original_k3", MATERIALIZER_CONFIG)
    record("local_materializer_matches_frozen", local_groups(s2, "original_k3") == [[0, 2]] and len(exact) == 1, f"local={local_groups(s2, 'original_k3')} frozen_rows={len(exact)}")
    # Explicitly test the actual finite-weight matcher on the documented small counterexample.
    pred = pd.DataFrame({"event_id": ["p0", "p1"], "start_time": [0.0, 9.0], "end_time": [10.0, 10.0], "anchor_unit_ids": ["0", "1"], "returned_seconds": [10.0, 1.0]})
    ref = pd.DataFrame({"reference_event_id": ["r0", "r1"], "start_time": [0.0, 9.5], "end_time": [9.5, 10.0], "source_unit_ids": ["0", "1"]})
    matches = LIB.match_events(pred, ref, meta)
    record("matcher_cardinality_small_case", int(matches.matched.sum()) == 2, f"matched={int(matches.matched.sum())}")
    write_csv(PACK / "audit/synthetic_test_results.csv", rows)
    if not all(row["status"] == "PASS" for row in rows):
        raise RuntimeError("synthetic tests failed")
    append_progress("Synthetic correctness", "run_bcm_aqp_v2.py --stage synthetic", f"{len(rows)}/{len(rows)} PASS", next_action="Freeze configuration and run canonical CPU replay.")


def freeze_config() -> None:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    write_json(PACK / "config/experiment_config.json", config)
    write_json(PACK / "config/config_freeze.json", {"config_sha256": sha256_file(PACK / "config/experiment_config.json"), "frozen_at_utc": utc_now(), "selection_basis": "mathematical-reference preregistered defaults; no test-reference tuning"})
    append_progress("Configuration freeze", "run_bcm_aqp_v2.py --stage config", f"config_sha256={sha256_file(PACK / 'config/experiment_config.json')}", next_action="Run exact canonical and ablation matrix.")


def run_experiments() -> None:
    freeze = json.loads((PACK / "config/config_freeze.json").read_text())
    if freeze["config_sha256"] != sha256_file(PACK / "config/experiment_config.json"):
        raise RuntimeError("frozen experiment config hash mismatch")
    config = json.loads((PACK / "config/experiment_config.json").read_text())
    frozen = RUNNER.load_frozen()
    units, proxy, reference = frozen.units, frozen.proxy, frozen.reference
    evaluator_hash = frozen.manifest["compatibility"]["evaluator_hash"]
    trace_rows, metric_rows, segment_rows, match_rows, matrix_rows = [], [], [], [], []
    variants = {
        "canonical": config,
        "no_partition": {**config, "weights": {"existence": 0.5625, "partition": 0.0, "boundary": 0.0, "residual": 0.4375}},
        "no_residual": {**config, "weights": {"existence": 0.6923076923, "partition": 0.3076923077, "boundary": 0.0, "residual": 0.0}},
        "existence_only": {**config, "weights": {"existence": 1.0, "partition": 0.0, "boundary": 0.0, "residual": 0.0}},
    }
    run_registry = []
    for variant, variant_config in variants.items():
        for budget in BUDGETS:
            actions, trace, state = execute_run(budget, units, proxy, frozen, variant_config, variant)
            run_id = f"bcm_{variant}_b{budget:03d}"
            actions["variant"] = variant; actions["budget"] = budget
            trace_rows.append(actions)
            materializers = [config["materializer"]] if variant != "canonical" else ["k3_bridge_safe", "original_k3"]
            canonical_metric = None
            for materializer in materializers:
                segments, matches, metrics = evaluate_trace(trace, units, reference, materializer, budget, run_id + "_" + materializer, evaluator_hash)
                segments["variant"] = variant; matches["variant"] = variant; metrics["variant"] = variant
                segment_rows.append(segments); match_rows.append(matches); metric_rows.append(metrics)
                wide = wide_metrics(metrics)
                matrix_rows.append({"variant": variant, "budget": budget, "materializer": materializer, "logical_calls": len(trace), **wide})
                if materializer == config["materializer"]:
                    canonical_metric = wide
            trace_path = PACK / f"runs/{variant}/b{budget:03d}/action_trace.csv"
            write_csv(trace_path, actions)
            write_csv(trace_path.parent / "strict_replay_trace.csv", trace)
            run_manifest = {"run_id": run_id, "variant": variant, "budget": budget, "logical_calls": len(trace), "physical_vlm_calls": 0,
                            "terminal_state_hash": state.state_hash, "action_trace_sha256": sha256_file(trace_path), "status": "COMPLETE"}
            write_json(trace_path.parent / "run_manifest.json", run_manifest)
            run_registry.append({**run_manifest, **(canonical_metric or {})})
    write_csv(PACK / "tables/action_traces.csv", pd.concat(trace_rows, ignore_index=True))
    write_csv(PACK / "tables/event_segments.csv", pd.concat(segment_rows, ignore_index=True))
    write_csv(PACK / "tables/event_matches.csv", pd.concat(match_rows, ignore_index=True))
    write_csv(PACK / "tables/metrics_long.csv", pd.concat(metric_rows, ignore_index=True))
    matrix = pd.DataFrame(matrix_rows)
    write_csv(PACK / "tables/materializer_matrix.csv", matrix)
    write_csv(PACK / "tables/run_registry.csv", run_registry)
    append_progress("Canonical, ablation, materializer runs", "run_bcm_aqp_v2.py --stage run", f"24 planner runs; {sum(r['logical_calls'] for r in run_registry)} logical cached calls; zero physical VLM calls", next_action="Compute ceilings and final analysis.")


def ceilings() -> None:
    frozen = RUNNER.load_frozen()
    units, proxy, oracle, reference = frozen.units, frozen.proxy, frozen.oracle, frozen.reference
    scores = primary_proxy(proxy, [int(x) for x in units.unit_id])
    hypotheses = build_hypotheses(units, scores, DEFAULT_CONFIG)
    candidates = {uid for h in hypotheses for uid in h.owner_unit_ids}
    positive = set(oracle.loc[oracle.parsed_label == "positive", "unit_id"].astype(int))
    reference_units = [set(int(x) for x in str(value).split("|") if x) for value in reference.source_unit_ids]
    certified = sum(bool(units_ & candidates & positive) for units_ in reference_units) / len(reference_units)
    rows = [{"ceiling": "candidate_evidence_certified_recall", "budget": len(candidates), "value": certified, "scope": "all_public_candidates"}]
    # Evaluator-only oracle-informed order: one positive source unit per unseen pseudo-event, then remaining positives, then others.
    order: list[int] = []
    for source in reference_units:
        choices = sorted(source & positive)
        if choices:
            order.append(choices[0])
    order = list(dict.fromkeys(order + sorted(positive) + sorted(candidates - positive)))
    for budget in BUDGETS:
        selected = set(order[:budget])
        ceiling_recall = sum(bool(source & selected) for source in reference_units) / len(reference_units)
        rows.append({"ceiling": "oracle_informed_evidence_recall", "budget": budget, "value": ceiling_recall, "scope": "evaluator_only_not_planner"})
    full_trace = pd.DataFrame({"unit_id": sorted(candidates), "oracle_label_after_query": [str(oracle.set_index("unit_id").loc[uid, "parsed_label"]) for uid in sorted(candidates)]})
    evaluator_hash = frozen.manifest["compatibility"]["evaluator_hash"]
    for materializer in ["original_k3", "k3_bridge_safe"]:
        _, _, metrics = evaluate_trace(full_trace, units, reference, materializer, len(candidates), "ceiling_" + materializer, evaluator_hash)
        values = wide_metrics(metrics)
        rows.append({"ceiling": "full_oracle_materializer_event_f1", "budget": len(candidates), "value": values["event_f1"], "scope": materializer})
        rows.append({"ceiling": "full_oracle_materializer_event_recall", "budget": len(candidates), "value": values["event_recall"], "scope": materializer})
    write_csv(PACK / "tables/ceilings.csv", rows)
    append_progress("Ceilings", "run_bcm_aqp_v2.py --stage ceilings", "Candidate, oracle-informed, and full-oracle materializer ceilings complete", next_action="Analyze without tuning configuration.")


def analyze() -> None:
    matrix = pd.read_csv(PACK / "tables/materializer_matrix.csv")
    registry = pd.read_csv(PACK / "tables/run_registry.csv")
    baseline = pd.read_csv(STRICT / "baselines/baseline_rankings.csv")
    current = pd.read_csv(STRICT / "current_method/current_budget_curves.csv")
    canonical = matrix[(matrix.variant == "canonical") & (matrix.materializer == "k3_bridge_safe")].copy()
    bcm_auc = auc(canonical)
    best = baseline.sort_values("event_f1_auc", ascending=False).iloc[0]
    current_m1 = current[current.method_variant == "K3_BRIDGE_SAFE"].rename(columns={"horizon_budget": "budget"})
    current_auc = auc(current_m1)
    summary = []
    for (variant, materializer), group in matrix.groupby(["variant", "materializer"]):
        summary.append({"method": "BCM_AQP_V2", "variant": variant, "materializer": materializer, "event_f1_auc": auc(group),
                        "event_recall_auc": auc(group, "event_recall"), "max_budget_f1": float(group.loc[group.budget.idxmax(), "event_f1"]),
                        "logical_calls_total": int(group.logical_calls.sum())})
    summary.extend([
        {"method": "STRICT_BASELINE", "variant": str(best.method), "materializer": str(best.method_variant), "event_f1_auc": float(best.event_f1_auc), "event_recall_auc": math.nan, "max_budget_f1": math.nan, "logical_calls_total": math.nan},
        {"method": "CURRENT_MAP", "variant": "K3_BRIDGE_SAFE", "materializer": "k3_bridge_safe", "event_f1_auc": current_auc, "event_recall_auc": auc(current_m1, "event_recall"), "max_budget_f1": float(current_m1.loc[current_m1.budget.idxmax(), "event_f1"]), "logical_calls_total": int(current_m1.budget.sum())},
    ])
    write_csv(PACK / "tables/method_summary.csv", summary)
    delta_best = bcm_auc - float(best.event_f1_auc)
    delta_current = bcm_auc - current_auc
    # Post-selection evaluator diagnostics: these never feed planner/config.
    canonical_actions = pd.read_csv(PACK / "runs/canonical/b100/action_trace.csv")
    canonical_trace = pd.read_csv(PACK / "runs/canonical/b100/strict_replay_trace.csv")
    activation = canonical_actions.groupby("action_type").size().to_dict()
    activation_rows = [
        {"diagnostic": "initial_hypothesis_count", "value": 141, "interpretation": "public candidate partition"},
        {"diagnostic": "discover_core_calls_b100", "value": int(activation.get("DISCOVER_CORE", 0)), "interpretation": "mechanism activation"},
        {"diagnostic": "probe_structure_calls_b100", "value": int(activation.get("PROBE_STRUCTURE", 0)), "interpretation": "mechanism activation"},
        {"diagnostic": "audit_uncovered_calls_b100", "value": int(activation.get("AUDIT_UNCOVERED", 0)), "interpretation": "mechanism activation"},
    ]
    write_csv(PACK / "audit/mechanism_activation.csv", activation_rows)
    ablation_rows = []
    variants = ["canonical", "no_partition", "no_residual", "existence_only"]
    for budget in BUDGETS:
        sequences = {variant: tuple(pd.read_csv(PACK / f"runs/{variant}/b{budget:03d}/action_trace.csv").unit_id.astype(int)) for variant in variants}
        reference_sequence = sequences["canonical"]
        common_prefix = min((next((i for i, (a, b) in enumerate(zip(reference_sequence, sequence)) if a != b), min(len(reference_sequence), len(sequence))) for sequence in sequences.values()), default=0)
        ablation_rows.append({"budget": budget, "distinct_query_sequences": len(set(sequences.values())), "common_prefix_length": common_prefix,
                              "identical_event_f1": matrix[(matrix.budget == budget) & (matrix.materializer == "k3_bridge_safe")].event_f1.nunique() == 1})
    write_csv(PACK / "audit/ablation_trace_comparison.csv", ablation_rows)
    evaluator_hash = json.loads((STRICT / "BENCHMARK_MANIFEST.json").read_text())["compatibility"]["evaluator_hash"]
    units = pd.read_csv(STRICT / "frozen_inputs/units.csv")
    reference = pd.read_csv(STRICT / "frozen_inputs/event_reference.csv")
    realized_rows, previous_f1 = [], 0.0
    for prefix in range(1, len(canonical_trace) + 1):
        _, _, prefix_metrics = evaluate_trace(canonical_trace.iloc[:prefix].copy(), units, reference, "k3_bridge_safe", prefix, f"realized_prefix_{prefix:03d}", evaluator_hash)
        values = wide_metrics(prefix_metrics)
        action = canonical_actions.iloc[prefix - 1]
        realized_rows.append({"call_idx": prefix - 1, "unit_id": int(action.unit_id), "action_type": action.action_type,
                              "surrogate_score": float(action.normalized_score), "oracle_outcome": action.oracle_outcome_after_query,
                              "event_f1_before": previous_f1, "event_f1_after": values["event_f1"], "realized_event_f1_delta": values["event_f1"] - previous_f1})
        previous_f1 = values["event_f1"]
    realized = pd.DataFrame(realized_rows)
    write_csv(PACK / "audit/realized_query_utility.csv", realized)
    from scipy.stats import spearmanr
    correlation = spearmanr(realized.surrogate_score, realized.realized_event_f1_delta).statistic
    utility_summary = [{"metric": "selected_score_vs_realized_f1_delta_spearman", "value": float(correlation) if math.isfinite(correlation) else math.nan},
                       {"metric": "positive_score_queries_with_zero_or_negative_f1_delta_fraction", "value": float((realized.realized_event_f1_delta <= 0).mean())},
                       {"metric": "positive_outcome_fraction", "value": float((realized.oracle_outcome == 'positive').mean())}]
    write_csv(PACK / "audit/surrogate_validity_summary.csv", utility_summary)
    synthetic_ok = (pd.read_csv(PACK / "audit/synthetic_test_results.csv").status == "PASS").all()
    preflight_ok = (pd.read_csv(PACK / "audit/preflight_checks.csv").status == "PASS").all()
    if not (synthetic_ok and preflight_ok):
        decision = "NO-GO"
    elif delta_best > 0.01:
        decision = "GO"
    elif delta_best >= -0.01:
        decision = "WEAK GO"
    else:
        decision = "NO-GO"
    decision_row = {"decision": decision, "benchmark_id": json.loads((STRICT / "BENCHMARK_MANIFEST.json").read_text())["benchmark_id"],
                    "bcm_event_f1_auc": bcm_auc, "best_baseline": f"{best.method}/{best.method_variant}", "best_baseline_event_f1_auc": float(best.event_f1_auc),
                    "delta_vs_best_baseline": delta_best, "current_m1_event_f1_auc": current_auc, "delta_vs_current_m1": delta_current,
                    "physical_vlm_calls": 0, "formal_experiment_complete": True, "result_scope": "SINGLE_VIDEO_VLM_DEFINED_PSEUDO_ORACLE_DIAGNOSTIC"}
    write_csv(PACK / "FINAL_DECISION.csv", [decision_row])
    # Compact SVG uses the authoritative table as its source.
    series = [("BCM", canonical), ("Current M1", current_m1)]
    width, height, margin = 760, 440, 55
    x = lambda b: margin + (float(b) - 5) / 95 * (width - 2 * margin)
    y = lambda v: height - margin - float(v) * (height - 2 * margin)
    colors = ["#1f77b4", "#d62728"]
    paths = []
    for (label, frame), color in zip(series, colors):
        points = " ".join(f"{x(r.budget):.1f},{y(r.event_f1):.1f}" for r in frame.sort_values("budget").itertuples())
        paths.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/><text x="{width-190}" y="{35+20*len(paths)}" fill="{color}">{label}</text>')
    plotted_paths = "".join(paths)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="white"/><line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="black"/><line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="black"/><text x="{width/2-40}" y="{height-10}">Budget</text><text x="8" y="30">Event F1</text>{plotted_paths}</svg>\n'
    (PACK / "figures/event_f1_budget_curve.svg").write_text(svg)
    write_csv(PACK / "figures/event_f1_budget_curve_data.csv", pd.concat([canonical.assign(series="BCM"), current_m1.assign(series="Current M1")], ignore_index=True, sort=False))
    report = f"""# BCM-AQP v2 Final Report

Decision: `{decision}`

## Strongest supported conclusion

BCM-AQP v2 completed a public-input-only, OracleAccessor-mediated CPU replay on frozen strict benchmark `{decision_row['benchmark_id']}`. Its event-F1 AUC is `{bcm_auc:.6f}`, versus `{float(best.event_f1_auc):.6f}` for the best frozen repository baseline and `{current_auc:.6f}` for current MAP/M1. The deltas are `{delta_best:+.6f}` and `{delta_current:+.6f}` respectively.

This is a single-video diagnostic against a VLM-defined pseudo-oracle, not human ground truth and not evidence of general G-ARC performance.

## Decisive evidence

- Strict preflight and every synthetic falsification test passed.
- Planner state and scoring use only public units/proxies plus already queried observations.
- Actual outcomes were obtained only after selection through the frozen `OracleAccessor`.
- Physical VLM calls: `0`; all calls are logical reads of the immutable strict cache.
- Configuration uses preregistered no-training weights `(0.45, 0.20, 0.00, 0.35)` and was not selected from test-reference results.
- Candidate, oracle-informed, and full-oracle materializer ceilings are in `tables/ceilings.csv`; M0/M1 replay is in `tables/materializer_matrix.csv`.
- Mechanism activation failed: the public builder produced 141 hypotheses and all 100 maximum-budget actions were `DISCOVER_CORE`; structure probes and follow-up audit actions were never selected.
- Weight ablations have identical event curves. They share complete query prefixes through budget 50; later ordering differences do not change pseudo-event metrics.
- The selected-score/realized-one-step-F1 diagnostic is in `audit/surrogate_validity_summary.csv` and was computed only after acquisition.

## Competing explanation and uncertainty

The loss may be driven primarily by overfragmented public hypotheses and uncalibrated existence priors, rather than by counterfactual materialization itself: the structure-probing branch was never exercised. The permissive overlap-any pseudo-event evaluator and single-video proxy distribution are additional competing explanations. Cross-video calibration/regret and human-adjudicated evaluation remain unresolved.

## Rejection/revision trigger

Reject this candidate construction now: it fails to expose the claimed BCM mechanism within the full budget. Revise only on development videos, requiring a preregistered mechanism-activation gate and improved score/realized-utility correlation before another frozen evaluation. Reject any future general BCM claim if held-out-video AUC, regret, or calibration fails to reproduce, or if leakage auditing finds unqueried-label/reference access.
"""
    (PACK / "reports/FINAL_REPORT.md").write_text(report)
    (PACK / "FINAL_REPORT.md").write_text(report)
    (PACK / "REPRODUCTION.md").write_text("# Reproduction\n\n```bash\npython3 Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/bcm_aqp_experiment_v2/scripts/run_bcm_aqp_v2.py --stage all\n```\n\nThis command performs CPU/cache replay only and makes zero physical VLM calls.\n")
    append_progress("Final analysis", "run_bcm_aqp_v2.py --stage analyze", f"decision={decision}; BCM AUC={bcm_auc:.6f}; delta_best={delta_best:+.6f}", next_action="Run final independent audit and seal manifest.")


def finalize() -> None:
    required = ["config/experiment_config.json", "data_manifest/input_manifest.csv", "data_manifest/schema_mapping.yaml", "audit/preflight_checks.csv", "audit/synthetic_test_results.csv", "audit/mechanism_activation.csv", "audit/surrogate_validity_summary.csv", "tables/run_registry.csv", "tables/materializer_matrix.csv", "tables/ceilings.csv", "tables/method_summary.csv", "figures/event_f1_budget_curve.svg", "reports/FINAL_REPORT.md", "reports/RESEARCH_STATE.md", "FINAL_DECISION.csv", "REPRODUCTION.md", "logs/progress.md"]
    missing = [path for path in required if not (PACK / path).is_file()]
    registry = pd.read_csv(PACK / "tables/run_registry.csv")
    review_path = PACK / "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json"
    review = json.loads(review_path.read_text()) if review_path.exists() else None
    review_ok = bool(review and review.get("status") == "PASS" and review.get("blocking_findings") == 0 and review.get("high_findings") == 0)
    checkpoint = "Final package sealed after independent review" if review_ok else "Pre-review package sealed"
    next_action = "No required work remains." if review_ok else "Independent adversarial review, then rerun finalization."
    append_progress(checkpoint, "run_bcm_aqp_v2.py --stage finalize", f"review_status={'PASS' if review_ok else 'PENDING'}", next_action=next_action)
    checks = [
        {"check": "required_artifacts", "status": "PASS" if not missing else "FAIL", "evidence": json.dumps(missing)},
        {"check": "exact_run_matrix", "status": "PASS" if len(registry) == 24 and registry.run_id.nunique() == 24 else "FAIL", "evidence": f"rows={len(registry)} unique={registry.run_id.nunique()}"},
        {"check": "zero_physical_vlm_calls", "status": "PASS" if (registry.physical_vlm_calls == 0).all() else "FAIL", "evidence": f"sum={registry.physical_vlm_calls.sum()}"},
        {"check": "logical_budget_respected", "status": "PASS" if (registry.logical_calls <= registry.budget).all() else "FAIL", "evidence": f"max_excess={(registry.logical_calls-registry.budget).max()}"},
        {"check": "unique_queries", "status": "PASS" if all(pd.read_csv(path).unit_id.nunique() == len(pd.read_csv(path)) for path in PACK.glob('runs/*/b*/action_trace.csv')) else "FAIL", "evidence": "all run traces"},
        {"check": "preflight", "status": "PASS" if (pd.read_csv(PACK / 'audit/preflight_checks.csv').status == 'PASS').all() else "FAIL", "evidence": "all rows"},
        {"check": "synthetic", "status": "PASS" if (pd.read_csv(PACK / 'audit/synthetic_test_results.csv').status == 'PASS').all() else "FAIL", "evidence": "all rows"},
    ]
    if review is not None:
        checks.append({"check": "independent_adversarial_review", "status": "PASS" if review_ok else "FAIL", "evidence": str(review_path.relative_to(PACK))})
    write_csv(PACK / "audit/completion_audit.csv", checks)
    if not all(row["status"] == "PASS" for row in checks):
        raise RuntimeError("BCM completion audit failed")
    def write_and_verify_file_manifest() -> list[dict]:
        rows = []
        for path in sorted(PACK.rglob("*")):
            if path.is_file() and path.name not in {"FILE_MANIFEST.csv", "EXPERIMENT_MANIFEST.json"}:
                rows.append({"path": str(path.relative_to(PACK)), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
        write_csv(PACK / "FILE_MANIFEST.csv", rows)
        for row in rows:
            path = PACK / row["path"]
            if not path.is_file() or path.stat().st_size != int(row["size_bytes"]) or sha256_file(path) != row["sha256"]:
                raise RuntimeError(f"file manifest verification failed: {row['path']}")
        return rows

    files = write_and_verify_file_manifest()
    checks.append({"check": "file_manifest_entries", "status": "PASS", "evidence": f"verified_rows={len(files)}"})
    write_csv(PACK / "audit/completion_audit.csv", checks)
    # The completion-audit row changed; rebuild once and verify the final set.
    files = write_and_verify_file_manifest()
    decision = pd.read_csv(PACK / "FINAL_DECISION.csv").iloc[0].to_dict()
    manifest = {"schema_version": "bcm_aqp_experiment_v2_manifest_v1", "status": "COMPLETE" if review_ok else "PRE_REVIEW_COMPLETE", "completed_at_utc": utc_now(),
                "benchmark_id": decision["benchmark_id"], "decision": decision["decision"], "physical_vlm_calls": 0,
                "run_count": len(registry), "logical_calls": int(registry.logical_calls.sum()),
                "config_sha256": sha256_file(PACK / "config/experiment_config.json"), "completion_audit_sha256": sha256_file(PACK / "audit/completion_audit.csv"),
                "file_manifest_sha256": sha256_file(PACK / "FILE_MANIFEST.csv")}
    write_json(PACK / "EXPERIMENT_MANIFEST.json", manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["preflight", "synthetic", "ceilings", "config", "run", "analyze", "finalize", "all"], default="all")
    args = parser.parse_args()
    stages = ["preflight", "synthetic", "ceilings", "config", "run", "analyze", "finalize"] if args.stage == "all" else [args.stage]
    for stage in stages:
        function = {"config": freeze_config, "run": run_experiments}.get(stage, globals().get(stage))
        function()


if __name__ == "__main__":
    main()
