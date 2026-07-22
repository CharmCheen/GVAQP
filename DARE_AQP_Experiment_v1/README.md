# DARE-AQP Experiment v1

This is an isolated, reproducible research package for the proposed
**Discovery–Audit Residual Event AQP (DARE-AQP)** route.  It does not claim
that DARE-AQP has already been validated.

The first experiment deliberately targets the decision-critical bottleneck:
can an independent probability audit certify residual pseudo-events without
approaching a dense scan?  The package therefore implements **Gate B before
Gate A/C**.  A sophisticated discovery planner is not justified if the
certificate itself has no useful cost regime.

## What is implemented

- a versioned pseudo-event `Presence / Certify / Audit` contract;
- an exact fixed-stage, one-sided hypergeometric upper confidence bound for
  residual canonical anchors;
- discovery/audit sample separation;
- all-unit proxy-top and uniform discovery controls;
- 500-seed coverage and cost simulation on the frozen 347-unit / 26-event
  strict benchmark;
- machine-readable raw results, summaries, input hashes, and research state;
- unit tests for the statistical bound and leakage-relevant invariants.

The statistical unit in v1 is a **single 10-second canonical-anchor unit**.
This makes the residual variable binary and permits exact finite-population
inference.  It is a strict pseudo-event audit, not a human-event guarantee.

## Run

From the repository root:

```bash
python DARE_AQP_Experiment_v1/scripts/run_gate_b.py
python -m unittest discover -s DARE_AQP_Experiment_v1/tests -v
```

Outputs are written below `DARE_AQP_Experiment_v1/outputs/gate_b/`.

## Read in this order

1. `RESEARCH_STATE.md` — current evidence, hypotheses, decision and next action.
2. `docs/ORACLE_CONTRACT.md` — what the pilot can and cannot identify.
3. `docs/GATE_B_PROTOCOL.md` — preregistered estimands and gates.
4. `outputs/gate_b/REPORT.md` — generated result and interpretation.
5. `docs/ROADMAP_AND_GATES.md` — P0–P4 status and the falsifiable Gate A route.
6. `docs/GATE_A_FROZEN_PROTOCOL.md` — one-shot unit-ranking falsification test.
7. `outputs/gate_c0/REPORT.md` — hierarchical interval-operator ceiling.
8. `docs/GATE_C0_PROTOCOL.md` — registered methods, costs, and routing gate.
9. `docs/C0_COMPLETION_AUDIT.md` — requirement-by-requirement evidence audit.
10. `outputs/gate_a_preflight/REPORT.md` — current-proxy evaluator preflight.
11. `docs/GATE_A_HARNESS_COMPLETION_AUDIT.md` — completed versus compute-pending Gate A requirements.

## Scope boundary

Gate A is now sealed: exact frozen CLIP/X-CLIP inference completed for all 347
units on an A100 and the result is `UNIT_ORACLE_DARE_ACCELERATION_NO_GO` (best
public linked cost 311/347). Gate C0 remains an exact cached conditional
ceiling; full Gate C is unjustified without a separately authorized measured
operator pilot. K3-safe stays frozen.
