# AEH-AQP Agent Handoff Pack v3

**Freeze date:** 2026-07-11  
**Purpose:** let a new Codex/agent continue the research without relying on chat history.  
**Project root on server:** `/qiuyeqing/llama_prl/G-ARC`

This is a handoff and governance pack, not a claim that the final AEH-AQP algorithm has been validated.

## Read order

1. `00_AGENT_START_HERE.md` — 5-minute takeover context.
2. `01_RESEARCH_NORTH_STAR.md` — research question, intended contribution, non-claims.
3. `02_EVIDENCE_AND_DECISION_LEDGER.md` — frozen benchmark and all experiment outcomes.
4. `03_SYSTEM_AND_ALGORITHM_SPEC.md` — current system, target system, operator boundaries.
5. `04_MECHANISM_GATE_FINAL_AND_ROUTING.md` — sealed mechanism result and route change.
6. `05_AGENT_EXECUTION_CONTRACT.md` — leakage, provenance, mutation, reporting and stop rules.
7. `06_EVALUATION_AND_GATES.md` — metrics, comparisons and GO/NO-GO logic.
8. `07_PAPER_POSITIONING.md` — paper story, novelty boundary and required baselines.
9. `08_SERVER_ARTIFACT_MAP.md` — authoritative paths and reading priority.
10. `09_DELIVERABLES_AND_HANDOFF_SCHEMA.md` — required output tree and schemas.
11. `10_NEXT_AGENT_MASTER_PROMPT.md` — copy/paste prompt for the one-shot S2 representation gate.
12. `11_RISKS_AND_OPEN_QUESTIONS.md` — unresolved scientific and operational risks.
13. `12_DOCUMENT_GOVERNANCE.md` — which documents govern when sources disagree.
14. `13_RESEARCH_ROADMAP.md` — operator-centered research sequence toward a paper.
15. `14_MECHANISM_GATE_FINAL_EVIDENCE.md` — complete 149-setting result snapshot.
16. `15_NEXT_EXPERIMENT_SPEC.md` — frozen S2 public event-cell experiment specification.
17. `16_INSTALL_ON_SERVER.md` — target path and installation/verification commands.

Machine-readable state is in `PROJECT_STATE.json`. Templates are under `templates/`.
Packaging provenance and its remote-verification limitation are in `SOURCE_PROVENANCE.md`.
Changes from the previous pack are summarized in `V3_CHANGELOG.md`.

## Authority order

When documents disagree, use this order:

1. immutable source code and hashed artifacts from the strict benchmark or completed experiment;
2. independent audit and completion audit attached to that artifact;
3. `02_EVIDENCE_AND_DECISION_LEDGER.md` in this pack;
4. `PROJECT_STATE.json` in this pack;
5. the sealed reports under `algorithmic_mechanism_viability_gate_v1`;
6. `references/BCM_AQP_MATHEMATICAL_REFERENCE_v2.md` as theory/reference, not empirical truth;
7. legacy design pack as historical design intent.

Never let an older design document override a later negative result.

## Present status in one sentence

Strict benchmark v2 is frozen; MAP/M1 is essentially tied with the best baseline; BCM/H1 remain below baseline; the controlled mechanism gate concluded `IDEAL_SIGNAL_ONLY`; exploration and counterfactual planning are stopped; one frozen public event-cell representation gate remains before the project commits fully to the EventRelation + barrier-constrained materialization operator route.
