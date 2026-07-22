#!/usr/bin/env python3
"""Freeze H-SCAN1B before any new physical execution."""

from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "outputs/psvr_autonomous_research/stage_4_scan_component_ablation"
OUT = REPO / "outputs/psvr_autonomous_research/cycle_05_H_SCAN1B"


def write_once(path: Path, payload: dict) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text() != encoded:
        raise RuntimeError(f"refusing to change frozen artifact: {path}")
    if not path.exists():
        path.write_text(encoded)


def main() -> None:
    decision = json.loads((SOURCE / "AUDITED_DECISION.json").read_text())
    if decision.get("H_SCAN1A") != "ACCEPT_STRUCTURAL_SIGNAL":
        raise RuntimeError("H-SCAN1B requires H-SCAN1A structural acceptance")
    source_task = json.loads((SOURCE / "TASK_MANIFEST.json").read_text())
    source_deadline = json.loads((SOURCE / "DEADLINE_MANIFEST.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("raw_tie", "raw_factorial", "tables", "plots", "reports"):
        (OUT / name).mkdir(exist_ok=True)

    task = {
        "manifest_version": "H-SCAN1B_task_v1", "cycle": 5,
        "hypothesis_id": "H-SCAN1B", "revision": 0,
        "status": "FROZEN_BEFORE_PHYSICAL_EXECUTION",
        "scope": "ONE_DEVELOPMENT_VIDEO_QUERY__TIE_ROBUSTNESS_THEN_STRUCTURAL_FACTORIAL",
        "task": source_task["task"],
        "runtime_identity_hash": source_task["runtime_identity_hash"],
        "hardware": source_task["hardware"],
        "frozen_shared_system": source_task["frozen_shared_system"],
        "heldout_opened": False,
        "physical_budget": {"tie_gate": 9, "conditional_factorial": 24, "total_cap": 33},
        "forbidden": source_task["forbidden"],
    }
    deadlines = {
        "manifest_version": "H-SCAN1B_deadlines_v1",
        "deadlines_seconds": {
            "T_transition": source_deadline["deadlines_seconds"]["T_transition"],
            "T_high": source_deadline["deadlines_seconds"]["T_high"],
        },
        "tie_gate_uses": ["T_transition"], "factorial_uses": ["T_transition", "T_high"],
        "repeats": 3, "guard": source_task["frozen_shared_system"]["deadline_guard"],
    }
    prereg = {
        "hypothesis_id": "H-SCAN1B", "revision": 0,
        "status": "FROZEN_BEFORE_NEW_PHYSICAL_RUNS",
        "question": "Is the H-SCAN1A structural result robust to exact ties, and is one structural term sufficient?",
        "stage_5a_tie_gate": {
            "methods": {
                "TB0": "D2 structural priority; exact equal-priority cells ordered by ascending unit_id",
                "TB1": "D2 structural priority; only exact equal-priority cells ordered by descending unit_id",
                "TB2": "D2 structural priority; only exact equal-priority cells ordered by SHA256(seed,cell_id)",
            },
            "seed_TB2": 20260715, "equality": "bitwise-equal Python float value; no tolerance",
            "matrix": "TB0/TB1/TB2 x T_transition x 3 fresh physical repeats",
            "stable_effect": "positive F1 and AnytimeAUC in all three repeats",
            "decision_rules": {
                "STRONG": "TB0, TB1, and TB2 all have stable effect",
                "WEAK": "TB0 has stable effect and exactly one of TB1/TB2 has stable effect",
                "FAIL": "TB0 has stable effect and both TB1/TB2 lack stable effect",
                "ANOMALOUS": "TB0 lacks stable effect; do not interpret alternatives as robustness",
            },
            "gate": "Run factorial only for STRONG or WEAK. FAIL moves to H-TIE1; ANOMALOUS audits reproduction.",
        },
        "stage_5b_factorial": {
            "conditional_on": ["STRONG", "WEAK"],
            "methods": {
                "F00": "neither term: all eligible-cell priorities zero",
                "F10": "U only, U=unobserved_span_units/N",
                "F01": "L only, L=0.5*log2(unobserved_span_units+1)/log2(N+1)",
                "F11": "U+L, identical to H-SCAN1A D2",
            },
            "matrix": "F00/F10/F01/F11 x T_transition/T_high x 3 fresh physical repeats",
            "invariants": ["eligible cells", "midpoint hierarchy", "A0", "TB0", "normalization", "weights", "candidate selector", "guard", "K3", "physical operators"],
            "decision_rules": {
                "UL": "only F11 stably effective",
                "U": "F10 and F11 stably effective; F01 and F00 not",
                "L": "F01 and F11 stably effective; F10 and F00 not",
                "SIMPLE": "F10,F01,F11 stably effective and F00 not",
                "ZERO": "F00 stably effective, invalidating structural attribution",
                "NONE": "no structural arm stably effective",
            },
        },
        "identifiability_warning_frozen": {
            "fact": "For positive span, U and L are both strictly increasing functions of the same span.",
            "prediction": "With identical eligibility and TB0, F10 and F01 must induce exactly the same scan action sequence.",
            "constraint": "The factorial can establish sufficiency of a span-order term, but cannot identify duration/coverage versus hierarchy-debt semantics.",
            "component_identity_nonidentifiable": True,
        },
        "valid_run": ["physical oracle", "deadline_met", "cache_replay=false", "future_proxy_access=false", "visibility_violation=false", "durable snapshot"],
        "heldout_opened": False, "physical_cap": 33,
    }
    write_once(OUT / "TASK_MANIFEST.json", task)
    write_once(OUT / "DEADLINE_MANIFEST.json", deadlines)
    write_once(OUT / "PREREGISTRATION.json", prereg)
    commands = "#!/usr/bin/env bash\nPYTHONPATH=src pytest -q tests/psvr_runtime\nPYTHONPATH=src python scripts/verify_psvr_hscan1b.py\npython scripts/run_psvr_hscan1b.py tie\npython scripts/evaluate_psvr_hscan1b.py tie\npython scripts/run_psvr_hscan1b.py factorial\npython scripts/evaluate_psvr_hscan1b.py factorial\n"
    path = OUT / "commands.sh"
    if path.exists() and path.read_text() != commands:
        raise RuntimeError(f"refusing to change frozen artifact: {path}")
    if not path.exists():
        path.write_text(commands)
    print(OUT / "PREREGISTRATION.json")


if __name__ == "__main__":
    main()
