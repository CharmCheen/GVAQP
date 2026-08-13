#!/usr/bin/env python3
"""Create terminal project documents only after the frozen P1 gate is FAIL.

This script deliberately has no P2/P3 implementation path.  It is a fail-closed
archival step for the long-horizon task's legitimate P1 NO-GO endpoint.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1"
DECISION = OUT / "P1_DECISION.json"
REPORT = OUT / "P1_FINAL_REPORT.md"
FAILURE = OUT / "P1_FAILURE_ANALYSIS.md"
DIRECTION = OUT / "PROJECT_DIRECTION_AFTER_P1.md"
STATE = OUT / "RESEARCH_STATE.json"
TARGETS = (OUT / "FINAL_RESEARCH_DECISION.md", OUT / "PAPER_CLAIM_BOUNDARY.md", OUT / "NEXT_RESEARCH_ACTION.md")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    if any(path.exists() for path in TARGETS):
        raise RuntimeError("terminal P1 NO-GO documents already exist; refusing overwrite")
    for path in (DECISION, REPORT, FAILURE, DIRECTION, STATE):
        if not path.exists():
            raise RuntimeError(f"required P1 FAIL artifact unavailable: {path}")
    p1 = json.loads(DECISION.read_text())
    if p1.get("decision") != "FAIL":
        raise RuntimeError("P1 is not FAIL; terminal NO-GO finalization is prohibited")
    criteria = p1["criteria"]
    state = json.loads(STATE.read_text())
    mainline = "TWO_STAGE_PROBLEM_ONLY"
    final = f"""# Final GVAQP research decision

## Mainline decision

`PROJECT_MAINLINE_DECISION = {mainline}`

The preregistered independent P1 gate returned `FAIL`. Therefore
`EVENT_EVIDENCE_POLICY = NO_GO`; P2 novelty baselines, P3 event-aware policy
development, P4 true-SCAN work, and P5 controller development were not run.

## Evidence basis

- P1 decision: `FAIL`, from the frozen analysis protocol and adjudicated human temporal-event reference.
- The required two natural proxy families and the complete semantic-oracle table were used by P1; their result is captured in [P1_FINAL_REPORT.md](P1_FINAL_REPORT.md).
- Key P1 gate values: `{json.dumps(criteria, sort_keys=True)}`.

## Recommendations

- P4 true-SCAN: `NO`.
- P5/controller: `NO`.
- Do not develop a geometry-aware selector, MAB, RL policy, or SCAN/VERIFY controller under this research branch.
"""
    boundary = """# Paper claim boundary

## Strongest supported claim

GVAQP establishes a carefully provenance-tracked two-stage temporal
materialization problem and reports a qualified, model-relative association
between public evidence geometry and C1 reconstruction quality.

## Claims not supported

The P1 independent-human gate did not establish that equal-yield temporal
evidence geometry consistently improves independent event recovery across the
prespecified clusters and natural proxy families. Accordingly, the work must not
claim that a geometry-aware semantic query policy is effective, necessary, or
superior to generic temporal coverage.

## Reviewer risk

The principal risk is over-interpreting prior cached, K3/model-relative geometry
associations as human-validated algorithmic evidence. P1 FAIL is the explicit
boundary against that interpretation.
"""
    next_action = """# Next research action

No additional query-policy algorithm development is justified by this branch.
The single next action is to package the two-stage materialization/provenance
artifacts and the independent P1 negative result as a bounded empirical finding,
without P2/P3/P4/P5 claims.
"""
    TARGETS[0].write_text(final)
    TARGETS[1].write_text(boundary)
    TARGETS[2].write_text(next_action)
    state.update({
        "current_phase": "P1 terminal NO-GO",
        "phase_status": "COMPLETE",
        "current_gate": "P1 independent geometry replication: FAIL/NO-GO",
        "failed_hypotheses": list(state.get("failed_hypotheses", [])) + ["Independent event-evidence geometry replication did not pass the preregistered P1 gate"],
        "user_input_required": "None; P1 FAIL terminates the event-evidence policy branch.",
        "next_entrypoint": "Read FINAL_RESEARCH_DECISION.md; do not execute P2/P3/P4/P5 for this branch.",
        "terminal_artifact_hashes": {path.name: sha(path) for path in TARGETS},
    })
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "COMPLETE_P1_NO_GO", "project_mainline_decision": mainline}, sort_keys=True))


if __name__ == "__main__":
    main()
