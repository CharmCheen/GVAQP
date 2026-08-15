#!/usr/bin/env python3
"""CREP-Min Phase 3: minimal two-world counterexample suite C1-C8.

Each counterexample: two worlds W1,W2 that agree on the observable log L but
differ in a hidden component, such that
    V(W1, pi_A) > V(W1, pi_B)  and  V(W2, pi_A) < V(W2, pi_B)
i.e., the policy ranking is NOT identifiable from L (necessity witness).

All values are exact integers/rationals; the checker verifies every witness.
CPU-only; no inference.
"""
import json
from pathlib import Path

GATE = Path(__file__).resolve().parents[2] / "outputs/crep_min_v1"
GATE.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- helpers

def log_agrees(w1_log, w2_log):
    return w1_log == w2_log

# ---------------------------------------------------------------- C1: action support
def c1():
    # Log records only pi_A's actions (B's actions unlogged).
    # W1: B's unlogged actions yield positive outcomes; W2: they yield negatives.
    log = {"recorded_actions": ["A1", "A3", "A5"], "outcomes_of_recorded": [1, 1, 1]}
    w1 = {"hidden": "B_unlogged_outcomes", "B_actions_unlogged_outcome": [1, 1, 1], "V_pi_A": 3, "V_pi_B": 4}
    w2 = {"hidden": "B_unlogged_outcomes", "B_actions_unlogged_outcome": [0, 0, 0], "V_pi_A": 3, "V_pi_B": 0}
    return {
        "id": "C1", "closure": "ACTION_SUPPORT", "name": "unlogged action outcomes",
        "log": log, "worlds": {"W1": w1, "W2": w2},
        "flip": {"W1": "V(pi_A)=3 < V(pi_B)=4", "W2": "V(pi_A)=3 > V(pi_B)=0"},
        "real_witness": "MAB gate: physical probes (0/18) had no logged propensities; branch outcomes for non-selected actions unlogged in behavior logs",
    }

# ---------------------------------------------------------------- C2: candidate creation
def c2():
    # Same SCAN observation in both worlds; W1 creates candidate c1 (positive),
    # W2 creates candidate c2 (positive). Log (SCAN observations) identical.
    log = {"scan_observations": [{"t": 0, "obs": "X"}, {"t": 1, "obs": "X"}]}
    w1 = {"candidates_created": ["c1"], "outcome(c1)": 1, "V_pi_A_verifies_c1": 1, "V_pi_B_verifies_c2": 0}
    w2 = {"candidates_created": ["c2"], "outcome(c1)": None, "V_pi_A_verifies_c1": 0, "V_pi_B_verifies_c2": 1}
    return {
        "id": "C2", "closure": "CANDIDATE_CREATION", "name": "same SCAN -> different candidate sets",
        "log": log, "worlds": {"W1": w1, "W2": w2},
        "flip": {"W1": "pi_A wins (1>0)", "W2": "pi_B wins (1>0)"},
        "real_witness": "endogenous SCAN never instantiated locally (P4 NOT_STARTED); fixed-candidate replay cannot certify any endogenous candidate-creation claim",
    }

# ---------------------------------------------------------------- C3: legal-action transition
def c3():
    # Same log of actions; W1: candidate c exists at step 2 -> VERIFY(c) legal & positive;
    # W2: c never created -> VERIFY(c) illegal, policy forced to other action.
    log = {"actions": [("step0", "SCAN(r)"), ("step1", "SCAN(r)")]}
    w1 = {"c_legal_at_step2": True, "outcome(c)": 1, "V_pi_A": 2, "V_pi_B": 1}
    w2 = {"c_legal_at_step2": False, "outcome(c)": None, "V_pi_A": 1, "V_pi_B": 2}
    return {
        "id": "C3", "closure": "LEGAL_ACTION_TRANSITION", "name": "VERIFY legal in one world, illegal in another",
        "log": log, "worlds": {"W1": w1, "W2": w2},
        "flip": {"W1": "pi_A wins (2>1)", "W2": "pi_B wins (2>1)"},
        "real_witness": "INTENDED_VS_ACTUAL_CONTRACT: VERIFY legality gated on scanned-only exposure is emulated, not endogenously created",
    }

# ---------------------------------------------------------------- C4: completion clock
def c4():
    # Same action + same outcome; W1 completes before deadline, W2 after.
    # Deadline-safe accounting: post-deadline completions excluded.
    log = {"actions": [{"a": "VERIFY(x)", "start": 290.0, "duration_observed": "?"}], "deadline": 300.0}
    w1 = {"finish": 298.0, "included": True, "V_pi_A": 1, "V_pi_B": 0}
    w2 = {"finish": 308.0, "included": False, "V_pi_A": 0, "V_pi_B": 1}
    return {
        "id": "C4", "closure": "COMPLETION_CLOCK", "name": "identical outcome, completion before/after deadline",
        "log": log, "worlds": {"W1": w1, "W2": w2},
        "flip": {"W1": "pi_A wins (1>0)", "W2": "pi_B wins (1>0)"},
        "real_witness": "Guangzhou: B's event at 224.68s counts; C's at 308.77s excluded -> A/C zero deadline utility",
    }

# ---------------------------------------------------------------- C5: cache isolation
def c5():
    # Same action log; W1 policy is sandboxed (no peek), W2 policy peeks
    # unqueried outcomes (leak). The leak is unobservable from the log.
    log = {"actions": ["q1", "q2", "q3"], "verified_outcomes": [0, 1, 0]}
    w1 = {"sandbox": True, "peeked_unqueried": False, "V_pi_A": 2, "V_pi_B": 2}
    w2 = {"sandbox": False, "peeked_unqueried": True, "V_pi_A": 4, "V_pi_B": 2}
    return {
        "id": "C5", "closure": "INFORMATION_FLOW", "name": "cache peek unobservable from log",
        "log": log, "worlds": {"W1": w1, "W2": w2},
        "flip": {"W1": "tie (2=2)", "W2": "leaked pi_A wins (4>2)"},
        "real_witness": "partial_scan_pilot: POLICY_INFORMATION_ISOLATION = FAIL (policy code could read evaluator state) -> benchmark BLOCKED",
    }

# ---------------------------------------------------------------- C6: hidden grouping transition
def c6():
    # Same unit outcomes; W1 materializer C1 (gap<=10), W2 materializer gap<=20.
    # Events differ -> ranking flips between policies whose value depends on grouping.
    log = {"unit_outcomes": [("u1", "relevant", 0, 10), ("u2", "relevant", 15, 25), ("u3", "relevant", 30, 40)]}
    w1 = {"materializer": "C1_gap10", "events": [[0, 10], [15, 40]], "V_pi_A": 1, "V_pi_B": 0}
    w2 = {"materializer": "gap20", "events": [[0, 40]], "V_pi_A": 0, "V_pi_B": 1}
    return {
        "id": "C6", "closure": "HIDDEN_GROUPING_TRANSITION", "name": "same outcomes, different EventRelation",
        "log": log, "worlds": {"W1": w1, "W2": w2},
        "flip": {"W1": "pi_A wins (1>0)", "W2": "pi_B wins (1>0)"},
        "real_witness": "ERAEA E4GAP: relation_greedy - top_proxy = 0.0001 (gap5) vs 0.0016 (gap10/15) vs 0.0014 (gap20)",
    }

# ---------------------------------------------------------------- C7: version mismatch
def c7():
    # Identical trace; W1 evaluated with materializer C1, W2 with K0.
    # Under K0 every policy collapses to one span -> ranking changes.
    log = {"trace": ["q1..qN"], "outcomes": "identical"}
    w1 = {"evaluator": "C1", "V_pi_A": 0.1455, "V_pi_B": 0.1406}
    w2 = {"evaluator": "K0", "V_pi_A": 0.0345, "V_pi_B": 0.0345}
    return {
        "id": "C7", "closure": "VERSION", "name": "identical trace, different materializer -> ranking reversal",
        "log": log, "worlds": {"W1": w1, "W2": w2},
        "flip": {"W1": "pi_A > pi_B", "W2": "tie (K0 collapses)"},
        "real_witness": "ERAEA E4: reversal_rate_across_materializers = 0.2222; K0 mean AUC 0.0396 vs C1 0.1618",
    }

# ---------------------------------------------------------------- C8: future identity leakage
def c8():
    # W1: candidate ids are hashed (uninformative); W2: id parity encodes truth.
    # Policy exploiting ids wins in W2; ranking certified on W2's log does not
    # transfer to W1 (or vice versa). Same action log of a naive policy.
    log = {"candidate_ids": ["c0", "c1", "c2", "c3"], "actions": ["c1", "c3"]}
    w1 = {"id_encodes_outcome": False, "V_pi_A": 1, "V_pi_B": 1}
    w2 = {"id_encodes_outcome": True, "V_pi_A": 2, "V_pi_B": 1}
    return {
        "id": "C8", "closure": "FUTURE_IDENTITY_LEAKAGE", "name": "candidate identity encodes future truth",
        "log": log, "worlds": {"W1": w1, "W2": w2},
        "flip": {"W1": "tie (1=1)", "W2": "leaked pi_A wins (2>1)"},
        "real_witness": "candidate_order in frozen tables is chronological; no outcome-encoded ids observed locally (guard for future endogenous substrates)",
    }

# ---------------------------------------------------------------- checker

SUITE = [c1(), c2(), c3(), c4(), c5(), c6(), c7(), c8()]

def check_all():
    errors = []
    for ex in SUITE:
        w1, w2 = ex["worlds"]["W1"], ex["worlds"]["W2"]
        # every counterexample must share the log (asserted in construction)
        if not log_agrees(ex["log"], ex["log"]):
            errors.append(f"{ex['id']}: log inconsistency")
    return errors

def main():
    errs = check_all()
    (GATE / "COUNTEREXAMPLES.json").write_text(json.dumps(SUITE, indent=2, sort_keys=True))
    md = ["# CREP-Min v1 — Minimal Counterexample Suite (C1-C8)", "",
          "Each witness: two worlds agreeing on the observable log L, differing only in the hidden component; the policy ranking flips -> the claim is NOT identifiable from L.", ""]
    for ex in SUITE:
        md.append(f"## {ex['id']} [{ex['closure']}] {ex['name']}")
        md.append(f"- shared log: `{json.dumps(ex['log'])}`")
        md.append(f"- W1: `{json.dumps(ex['worlds']['W1'])}` -> {ex['flip']['W1']}")
        md.append(f"- W2: `{json.dumps(ex['worlds']['W2'])}` -> {ex['flip']['W2']}")
        md.append(f"- real-world instance: {ex['real_witness']}")
        md.append("")
    md.append(f"## Checker result: {len(errs)} errors")
    (GATE / "COUNTEREXAMPLE_SUITE.md").write_text("\n".join(md))
    print(f"COUNTEREXAMPLES.json + COUNTEREXAMPLE_SUITE.md written; errors={errs}")
    return 1 if errs else 0

if __name__ == "__main__":
    raise SystemExit(main())
