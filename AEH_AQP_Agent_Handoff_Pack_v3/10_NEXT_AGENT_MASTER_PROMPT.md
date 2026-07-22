# Master Prompt for the Next Codex

Copy the block below into the next Codex session.

---

Continue the AEH-AQP project by executing **Frozen S2 Public Event-Cell Representation Repair Gate v1 only**.

Project root:

```text
/qiuyeqing/llama_prl/G-ARC
```

Handoff pack expected on server:

```text
/qiuyeqing/llama_prl/G-ARC/AEH_AQP_Agent_Handoff_Pack_v3
```

Read in order:

```text
README.md
00_AGENT_START_HERE.md
02_EVIDENCE_AND_DECISION_LEDGER.md
04_MECHANISM_GATE_FINAL_AND_ROUTING.md
05_AGENT_EXECUTION_CONTRACT.md
06_EVALUATION_AND_GATES.md
15_NEXT_EXPERIMENT_SPEC.md
09_DELIVERABLES_AND_HANDOFF_SCHEMA.md
```

Then reproduce the authoritative facts from:

```text
Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict
Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/hypothesis_construction_repair_v1
Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/candidate_outcome_calibration_gate_v1
Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/algorithmic_mechanism_viability_gate_v1
```

Frozen governing results:

```text
strict benchmark = cbbv2_514c0d360fd5b2a4b5fe
reference events = 26
best native AUC = 0.389659
MAP/M1 AUC = 0.388056
H1 AUC = 0.314990
mechanism settings = 149/149
mechanism decision = IDEAL_SIGNAL_ONLY
S1 P1-P0 = +0.025434
S2 frozen H1 P1-P0 = -0.003978 in all 15 cells
REAL_CHEAP_PRIMITIVE_ENGINEERING_JUSTIFIED = false
```

## Goal

Test exactly once whether a deterministic, planner-public event-cell representation of the existing frozen H1 candidate universe can make P1 event saturation transfer to S2.

This is a representation test, not feature engineering and not a candidate recall experiment.

## Output directory

```text
/qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/public_event_cell_representation_gate_v1
```

## Hard constraints

1. Do not modify any prior benchmark or experiment directory.
2. Physical VLM calls = 0.
3. Baseline reruns = 0.
4. Do not run P2 exploration or P3 counterfactual policies.
5. Do not add YOLO, tracking, embeddings, ego-motion or any new cheap primitive.
6. Do not add/remove candidate actions or change oracle observations.
7. Do not use event references, dense labels, matches or future outcomes to construct R1.
8. Do not tune a threshold/grid after evaluator execution.
9. Use the exact frozen S2 cells, budgets, seeds, materializer and evaluator.
10. Freeze R1 source/config/hash before any evaluator-aware run.
11. If required public fields are unavailable, decide `EXPERIMENT_BLOCKED`; do not invent a substitute.

## Required methods

```text
R0-P0  frozen H1 representation + positive-probability policy
R0-P1  frozen H1 representation + exact frozen saturation policy
R1-P0  public event-cell representation + same P0
R1-P1  public event-cell representation + same P1
```

R1 must preserve the frozen action universe. Construct cells deterministically from planner-public source intervals and types:

1. high-proxy islands are seed cells;
2. audit/uncovered windows never become event cells; retain them in a stable audit-owner namespace that is not affected by event-cell saturation;
3. process orphan-local-peak candidates chronologically;
4. attach an orphan to an overlapping seed cell, or to the temporally nearest seed cell only when the public interval distance is at most one frozen unit and the resulting cell span is at most the audited K3 core cap;
5. otherwise create a standalone orphan cell;
6. tie-break by interval distance, earlier seed start, then stable seed ID;
7. do not transitively merge two seed cells through an orphan;
8. retain every original legal action and its original score; only its owner cell changes.

Before evaluation, audit the actual H1/S2 schema. If a term above cannot be mapped exactly to existing public fields, stop with `EXPERIMENT_BLOCKED` rather than altering the rule.

Use the exact frozen P0/P1 implementation from `mechanism_gate_v1`. Do not recalibrate it.

## Required diagnostics

- cell count and source composition;
- candidate/action universe identity hashes R0 versus R1;
- oracle observation identity;
- event-cell sizes and spans;
- within-cell redundant-query rate;
- unique cells queried by budget;
- P1 saturation trigger/applied/output-change counts;
- event coverage and event-F1 at each frozen budget;
- normalized event-F1 AUC;
- paired R1 `(P1-P0)` by S2 cell and budget;
- R1 versus R0 decomposition to distinguish representation gain from saturation gain;
- bootstrap CI only if its resampling unit is defensible; otherwise report exact paired cells without pretending independence.

## Primary decision

Use exactly one:

### `PUBLIC_EVENT_CELL_SATURATION_GO`

Only if R1 P1−P0 AUC is positive, low-budget B=5/10/20 aggregate is positive, the effect is not one-cell dominated, and the valid paired CI lower bound is above zero when a valid CI can be formed.

### `PLANNER_ROUTE_REJECTED`

Use if R1 P1−P0 is non-positive, unstable, or lacks low-budget benefit. This permanently stops BCM/saturation/exploration/counterfactual planner work.

### `EXPERIMENT_BLOCKED`

Use for missing public schema, irreproducible frozen S2 inputs, leakage risk or incomplete evaluation.

`R1-P0` may be reported as a secondary representation finding but cannot convert a non-positive P1−P0 into saturation GO.

## Deliverables

Create the standard package required by `09_DELIVERABLES_AND_HANDOFF_SCHEMA.md`, including primitive per-cell/per-budget CSVs, representation lineage, frozen R1 config, source/input hashes, completion audit, independent adversarial review and file manifest.

The final report must write the exact next-task prompt:

- if GO: minimal event-cell saturation validation on multiple videos;
- if rejected: Barrier-Constrained Event Partition/Materialization operator design and fixed-trace gate;
- if blocked: only the concrete unblock task.

Stop after sealing this gate. Do not implement the next operator or multi-video experiment in this task.

---
