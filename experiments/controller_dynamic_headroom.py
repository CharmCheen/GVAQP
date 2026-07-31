"""Exploratory paired SCAN/VERIFY branch test on preserved cached domains.

This experiment is deliberately separate from the active Oracle V3 full-grid.
It uses the older frozen ARC replay inputs, abstract action costs, and a single
fixed continuation policy.  Consequently its output can establish cached
mechanism headroom only; it cannot establish physical deadline utility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from rc_sem.sequential import (
    LabelIsolatedSequentialEnv,
    SequentialAction,
    SequentialActionType,
    validate_public_state_no_evaluator_leakage,
)
from rc_sem.sequential_policies import (
    FixedCyclePolicy,
    can_scan_with_reserve,
    can_verify,
    next_scan_target,
)

import sequential_unknown_video_study as study


BEHAVIOR_METHODS = (
    "CURRENT_TWO_STAGE_RAW",
    "FIXED_SCAN1_VERIFY1",
    "FIXED_SCAN1_VERIFY3",
    "DYNAMIC_ADAPTIVE_K3_VALUE_V3",
)
BUDGETS = (20.0, 50.0, 100.0)
PRECISION_FLOOR = 0.8
MAX_STATES_PER_DOMAIN_BUDGET = 12


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def make_env(domain, budget: float):
    return LabelIsolatedSequentialEnv(
        unit_windows=domain.unit_windows,
        proxy_scores=domain.proxy_map,
        oracle_labels=domain.oracle_map,
        budget=budget,
        costs=study.COSTS,
    )


def forced_action(state, action_type: SequentialActionType) -> SequentialAction:
    if action_type is SequentialActionType.SCAN:
        target = next_scan_target(state)
        if target is None:
            raise RuntimeError("SCAN branch requested without a target")
        return SequentialAction(action_type, target, "forced_scan_fixed")
    if action_type is SequentialActionType.VERIFY:
        target = max(
            state.verifiable_unit_ids,
            key=lambda unit_id: (state.proxy_scores[unit_id], -unit_id),
        )
        return SequentialAction(action_type, target, "forced_verify_top1")
    raise ValueError("branch action must be SCAN or VERIFY")


def behavior_states(domain, profile, budget: float, arc_core):
    """Return naturally reachable, dual-legal states and their action prefixes."""

    found: dict[str, tuple[str, tuple[SequentialAction, ...], object]] = {}
    for method in BEHAVIOR_METHODS:
        env = make_env(domain, budget)
        policy = study.make_policy(method, study.COSTS, profile, 0, arc_core)
        prefix: list[SequentialAction] = []
        for _ in range(len(domain.units) + len(env.state.cells) + 1):
            state = env.state
            validate_public_state_no_evaluator_leakage(state)
            if can_scan_with_reserve(state, study.COSTS) and can_verify(state, study.COSTS):
                found.setdefault(state.canonical_hash(), (method, tuple(prefix), state))
            action = policy.choose(state)
            if action.action_type is SequentialActionType.STOP:
                break
            observation = env.step(action)
            policy.observe(state, observation, env.state)
            prefix.append(action)
        else:
            raise RuntimeError("behavior policy exceeded unique-action bound")

    rows = list(found.values())
    if len(rows) <= MAX_STATES_PER_DOMAIN_BUDGET:
        return rows
    indices = np.linspace(0, len(rows) - 1, MAX_STATES_PER_DOMAIN_BUDGET, dtype=int)
    return [rows[int(index)] for index in indices]


def rollout(domain, budget, prefix, first_action, bench, evaluator_hash, branch_id):
    """Replay a prefix, force one action, then use frozen fixed 1:1 continuation."""

    env = make_env(domain, budget)
    verify_rows: list[dict[str, object]] = []
    meta = study.evaluator_meta(domain, branch_id, 0, budget)
    predictions = study.predictions_from_verify_trace(domain, verify_rows, meta, bench)
    _, metrics = study.score_predictions(domain, predictions, meta, bench, evaluator_hash)
    recall_area = 0.0
    actions = [*prefix, first_action]
    continuation = FixedCyclePolicy(study.COSTS, verifies_per_scan=1)
    continuation_started = False

    for _ in range(len(domain.units) + len(env.state.cells) + 1):
        if actions:
            action = actions.pop(0)
        else:
            continuation_started = True
            action = continuation.choose(env.state)
        if action.action_type is SequentialActionType.STOP:
            break
        cost = env.action_cost(action)
        recall_area += cost * float(metrics["event_recall"])
        prior = env.state
        observation = env.step(action)
        if continuation_started:
            continuation.observe(prior, observation, env.state)
        if action.action_type is SequentialActionType.VERIFY:
            verify_rows.append(
                {
                    "verify_idx": len(verify_rows),
                    "unit_id": int(action.target_id),
                    "oracle_label_after_query": str(observation.revealed_label),
                }
            )
            predictions = study.predictions_from_verify_trace(domain, verify_rows, meta, bench)
            _, metrics = study.score_predictions(domain, predictions, meta, bench, evaluator_hash)
    else:
        raise RuntimeError("branch rollout exceeded unique-action bound")

    final = env.state
    recall_area += final.remaining * float(metrics["event_recall"])
    anytime_recall = recall_area / budget
    precision = float(metrics["event_precision"])
    precision_ok = len(predictions) == 0 or precision >= PRECISION_FLOOR
    base_utility = 0.5 * float(metrics["event_recall"]) + 0.5 * anytime_recall
    q_value = base_utility if precision_ok else base_utility - 1.0
    return {
        "q": q_value,
        "terminal_event_recall": float(metrics["event_recall"]),
        "terminal_event_precision": precision,
        "terminal_event_f1": float(metrics["event_f1"]),
        "anytime_event_recall_auc": anytime_recall,
        "terminal_distinct_event_count": int(len(predictions)),
        "precision_constraint_satisfied": precision_ok,
        "spent": final.spent,
        "deadline_overrun": final.spent > budget + 1e-12,
    }


def execute(arc_root: Path, output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite {output}")
    benchmark_path = arc_root / (
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/"
        "clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py"
    )
    evaluator_hash = study.sha256_file(benchmark_path)
    if evaluator_hash != study.EXPECTED_EVALUATOR_HASH:
        raise RuntimeError("evaluator hash changed")
    bench = study.load_module("controller_headroom_benchmark", benchmark_path)
    sys.path.insert(0, str(arc_root / "src"))
    from garc_eval.arc_cached_replay import core as arc_core

    domains, manifest = study.load_domains(arc_root)
    profiles = {
        name: study.fit_profile([other for key, other in domains.items() if key != name], study.COSTS)
        for name in domains
    }
    output.mkdir(parents=True)
    branch_path = output / "STATE_ACTION_BRANCHES.jsonl"
    records = []
    with branch_path.open("w", encoding="utf-8") as handle:
        for domain_name, domain in sorted(domains.items()):
            for budget in BUDGETS:
                for behavior, prefix, state in behavior_states(
                    domain, profiles[domain_name], budget, arc_core
                ):
                    scan = rollout(
                        domain,
                        budget,
                        prefix,
                        forced_action(state, SequentialActionType.SCAN),
                        bench,
                        evaluator_hash,
                        "BRANCH_SCAN_FIXED",
                    )
                    verify = rollout(
                        domain,
                        budget,
                        prefix,
                        forced_action(state, SequentialActionType.VERIFY),
                        bench,
                        evaluator_hash,
                        "BRANCH_VERIFY_TOP1",
                    )
                    delta = scan["q"] - verify["q"]
                    classification = (
                        "SCAN_BETTER"
                        if delta > 1e-12
                        else "VERIFY_BETTER"
                        if delta < -1e-12
                        else "EFFECTIVELY_TIED"
                    )
                    frontier_scores = [state.proxy_scores[uid] for uid in state.verifiable_unit_ids]
                    record = {
                        "schema_version": "CACHED_CONTROLLER_BRANCH_V1",
                        "classification": "cached_abstract_cost_replay_not_physical",
                        "domain": domain.name,
                        "video_id": domain.video_id,
                        "behavior_policy": behavior,
                        "budget": budget,
                        "elapsed": state.spent,
                        "remaining": state.remaining,
                        "state_hash": state.canonical_hash(),
                        "scanned_fraction": state.scanned_fraction,
                        "frontier_size": len(state.verifiable_unit_ids),
                        "frontier_top_score": max(frontier_scores),
                        "frontier_mean_score": float(np.mean(frontier_scores)),
                        "committed_event_count": len(state.event_groups),
                        "scan_count": state.scan_count,
                        "verify_count": state.verify_count,
                        "legal_actions": ["SCAN_FIXED", "VERIFY_TOP1", "STOP"],
                        "continuation_policy": "FIXED_SCAN1_VERIFY1",
                        "scan_branch": scan,
                        "verify_branch": verify,
                        "delta_q": delta,
                        "best_action": classification,
                        "rollout_repetitions": 1,
                        "observed_replay_noise": 0.0,
                    }
                    handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
                    records.append(record)

    frame = pd.DataFrame(
        {
            "domain": row["domain"],
            "video_id": row["video_id"],
            "classification": row["best_action"],
            "delta_q": row["delta_q"],
        }
        for row in records
    )
    counts = frame.classification.value_counts().to_dict()
    non_tie = int((frame.classification != "EFFECTIVELY_TIED").sum())
    source_switch = frame.groupby("video_id").classification.apply(
        lambda values: {"SCAN_BETTER", "VERIFY_BETTER"}.issubset(set(values))
    )
    gate = {
        "non_tie_fraction": non_tie / len(frame),
        "scan_better_fraction": counts.get("SCAN_BETTER", 0) / len(frame),
        "verify_better_fraction": counts.get("VERIFY_BETTER", 0) / len(frame),
        "source_videos_with_both_directions": int(source_switch.sum()),
        "deadline_overrun_count": sum(
            row["scan_branch"]["deadline_overrun"] + row["verify_branch"]["deadline_overrun"]
            for row in records
        ),
    }
    gate["cached_headroom_gate_pass"] = bool(
        gate["non_tie_fraction"] >= 0.25
        and gate["scan_better_fraction"] >= 0.10
        and gate["verify_better_fraction"] >= 0.10
        and gate["source_videos_with_both_directions"] >= 2
        and gate["deadline_overrun_count"] == 0
    )
    summary = {
        "schema_version": "CACHED_CONTROLLER_HEADROOM_SUMMARY_V1",
        "classification": "cached_abstract_cost_replay_not_physical_or_confirmatory",
        "record_count": len(records),
        "class_counts": counts,
        "gate": gate,
        "q_definition": "0.5*terminal_event_recall + 0.5*anytime_event_recall_auc; subtract 1 if nonempty output violates precision>=0.8",
        "tie_tolerance": 1e-12,
        "costs": {
            "scan": study.COSTS.scan_cost,
            "verify": study.COSTS.verify_cost,
            "unit": "abstract cached-replay cost, not seconds",
        },
        "evaluator_sha256": evaluator_hash,
        "frozen_input_manifest_sha256": canonical_hash(manifest),
        "limitations": [
            "only two independent source videos across three cached domains",
            "costs are abstract and no physical deadline is exercised",
            "one deterministic continuation policy and one rollout per branch",
            "older cached oracle/query/reference, not the active Oracle V3 full-grid",
        ],
    }
    (output / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execute(args.arc_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
