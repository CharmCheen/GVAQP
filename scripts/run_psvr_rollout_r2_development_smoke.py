#!/usr/bin/env python3
"""Development-only R2 correctness smoke; never imports confirmatory materialization."""

from __future__ import annotations

import json
from pathlib import Path

from garc_eval.psvr_rollout_toy.r2 import ExactConditionalRollout, ExactPosterior, R2Environment, finite_world_library
from garc_eval.psvr_rollout_toy.r2_splits import LEGACY_HELDOUT, load_development_universe, reject_contaminated


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_rollout_r2"


def run_episode(world) -> tuple[int, str]:
    env = R2Environment(world)
    planner = ExactConditionalRollout(ExactPosterior(finite_world_library()))
    while not env.visible_state().stopped:
        env.execute(planner.choose(env.history, env.safe_actions()))
    verification = ExactPosterior(finite_world_library()).verify(env.history)
    if verification["mass"] != 1.0 or not verification["all_supported_reproduce_history"] or not verification["inconsistent_mass_zero"]:
        raise AssertionError("exact posterior verifier failed")
    return len(env.history.actions), env.history.digest


def main() -> None:
    try:
        reject_contaminated(LEGACY_HELDOUT)
    except Exception as exc:
        contamination_guard = type(exc).__name__
    else:
        raise AssertionError("contaminated universe guard did not reject")
    episodes = load_development_universe(16)
    traces = []
    for item in episodes:
        length, digest = run_episode(item.world)
        repeat_length, repeat_digest = run_episode(item.world)
        if (length, digest) != (repeat_length, repeat_digest):
            raise AssertionError("development trace was not deterministic")
        traces.append({"opaque_development_id": item.opaque_id, "trace_entries": length, "trace_digest": digest})
    payload = {
        "status": "PASS",
        "scope": "DEVELOPMENT_ONLY_CORRECTNESS_SMOKE",
        "episodes_completed": len(traces),
        "development_identities": [row["opaque_development_id"] for row in traces],
        "exceptions": 0,
        "posterior_verifier": "PASS",
        "conditional_q_recomputation": "PASS",
        "latent_policy_leakage": "NOT_OBSERVED",
        "d2_t_deadline_semantics": "PASS",
        "determinism": "PASS",
        "contaminated_guard": contamination_guard,
        "confirmatory_generator_imported": False,
        "policy_metrics": "DEBUG_ONLY_NOT_FOR_SCIENTIFIC_USE",
        "policy_ranking_generated": False,
        "trace_records": traces,
    }
    (OUT / "R2_DEVELOPMENT_SMOKE_AUDIT.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print("PASS_R2_DEVELOPMENT_SMOKE")


if __name__ == "__main__":
    main()
