# Document Governance

## Why this file exists

The project contains plans, mathematical proposals, code audits, failed attempts and frozen experiments. They do not have equal authority. An agent must resolve disagreements by evidence type and time, not by document length or confidence of wording.

## Document classes

| Class | Examples | Authority | Permitted use |
|---|---|---|---|
| Frozen benchmark | strict v2 manifest, source hashes, completion audit | Highest for benchmark facts | execution and evaluation |
| Completed experiment | final decision, primitive traces, independent review | Highest for that mechanism/result | claim updates and next gate |
| Current handoff | this pack | Current synthesis | routing and context |
| Mathematical reference | BCM mathematical reference | Normative/candidate theory | implementation constraints, counterexamples |
| Legacy design | original 17-document pack | Historical intent | terminology and long-term architecture |
| Chat/prompt | prior session text | Lowest unless sealed into artifact | clues only |

## Conflict-resolution rules

1. Later frozen evidence supersedes an earlier design prediction.
2. Source plus trace supersedes prose describing the source.
3. Independent recomputation supersedes copied aggregate values.
4. A negative experiment narrows claims even if the theory remains plausible.
5. A ceiling may motivate work but cannot upgrade an online method’s status.
6. A single-video result cannot supersede a requirement for cross-video evidence.
7. A server copy with a later hash may supersede this pack’s reference copy only after its provenance and change are documented.

## Required reading by task type

### Coding agent

- `03_SYSTEM_AND_ALGORITHM_SPEC.md`
- `05_AGENT_EXECUTION_CONTRACT.md`
- strict source/manifests
- relevant theory/code audit

### Experiment agent

- `02_EVIDENCE_AND_DECISION_LEDGER.md`
- `04_MECHANISM_GATE_FINAL_AND_ROUTING.md`
- `06_EVALUATION_AND_GATES.md`
- `09_DELIVERABLES_AND_HANDOFF_SCHEMA.md`

### Theory agent

- `01_RESEARCH_NORTH_STAR.md`
- mathematical reference
- completed counterexamples/failure decompositions

### Paper agent

- `01_RESEARCH_NORTH_STAR.md`
- `02_EVIDENCE_AND_DECISION_LEDGER.md`
- `06_EVALUATION_AND_GATES.md`
- `07_PAPER_POSITIONING.md`
- all latest primary-source papers

### Audit/red-team agent

- execution contract;
- exact expected matrix;
- primitive artifacts and source;
- final report only after independent recomputation.

## Updating this pack

After the S2 representation gate finishes, create v4 rather than silently editing this frozen package. The update must:

- record the sealed S2 decision;
- add exact metrics and action-activation evidence;
- select one next route;
- update the master prompt;
- regenerate the manifest and ZIP;
- preserve this v3 package for lineage.
