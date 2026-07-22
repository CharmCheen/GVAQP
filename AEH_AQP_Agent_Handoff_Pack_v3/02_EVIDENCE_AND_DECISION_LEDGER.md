# Evidence and Decision Ledger

## E0 — Strict benchmark v2

**ID:** `cbbv2_514c0d360fd5b2a4b5fe`  
**Status:** frozen, independently audited, compatible and ready for downstream replay.  
**Oracle:** self-contained VLM-defined pseudo-oracle.  
**Reference events:** 26.  
**Scope:** one video; oracle-relative; not human-GT or cross-video.

Authoritative path:

```text
Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/
clean_baseline_benchmark_v2_strict
```

Results:

| Method | Event-F1 AUC |
|---|---:|
| Best native baseline | 0.389659 |
| MAP/M1 | 0.388056 |
| Difference | -0.001603 |

Interpretation: current method is competitive but not superior. The strict benchmark is infrastructure/evidence, not itself an algorithmic novelty.

## E1 — BCM-AQP v2

Path: `agent_run/bcm_aqp_experiment_v2`  
Decision: `NO-GO`.  
AUC: `0.294270`.

Failure mechanism:

- 141 initial hypotheses;
- first 100 actions all `DISCOVER_CORE`;
- structure/audit actions never selected;
- candidate construction/state initialization dominated the planner.

This rejects the implemented BCM candidate construction, not all counterfactual probing in principle.

## E2 — Hypothesis Construction Repair v1

Path: `agent_run/hypothesis_construction_repair_v1`  
Decision: `HYPOTHESIS_REPAIR_WEAK_GO`.

- H0: 141 hypotheses = 55 high-proxy islands + 86 low/uncovered windows incorrectly treated as hypotheses.
- H1: 87 hypotheses = 55 islands + 32 deterministic orphan-peak cells.
- H0 AUC `0.294270`; H1–H4 AUC `0.314990`.
- H2 saturation, H3 exploration and H4 triggered structure had zero independent gain.
- All formal B=100 runs still selected only core actions.
- H1 helped only at higher budgets and remained below MAP/M1 and ARC.

Decision: freeze the source-semantics correction as a useful implementation repair; do not portray it as a recovered planner.

## E3 — Candidate and Outcome Calibration Gate v1

Path: `agent_run/candidate_outcome_calibration_gate_v1`  
Decision: `CHEAP_CANDIDATE_CONSTRUCTION_REQUIRED`.

Candidate evidence:

| Quantity | Result |
|---|---:|
| H1 core event coverage | 12/26 = 0.461538 |
| Full legal-universe coverage | 20/26 = 0.769231 |
| Events absent from legal universe | 6/26 |
| H1 top-5 coverage | 0 |
| H1 top-10 coverage | 0.038462 |
| H1 top-20 coverage | 0.076923 |

Oracle-informed reorder:

| Budget | Event-F1 |
|---:|---:|
| 5 | 0.322581 |
| 10 | 0.555556 |
| 20 | 0.666667 |
| AUC | 0.664458 |

Public signal:

| Target | AUROC | AP |
|---|---:|---:|
| Positive | 0.546143 | 0.142250 |
| New event | 0.502504 | 0.115319 |
| Fixed blocked-CV F2 | 0.548282 | — |

Interpretation: the action space has large evaluator-only headroom, but current public features neither cover all events nor rank useful actions reliably. Oracle reorder is a ceiling, not a runnable algorithm.

## E4 — Algorithmic Mechanism Viability Gate v1

Path: `agent_run/algorithmic_mechanism_viability_gate_v1`  
Decision: `IDEAL_SIGNAL_ONLY`.  
Completion: 149/149 settings, 141,750 policy runs.  
Physical VLM calls: 0.  
Final execution: one A100-host CPU path; no incomplete A800 policy result was mixed.

Checkpoint forensics found 0/149 complete-valid A800 settings: 121 incomplete and 28 not started. All 149 were recomputed with atomic checkpoints.

Primary effects:

- Suite A saturation P1−P0: `+0.093699`.
- Suite C robustness: saturation `+0.022001`, exploration `−0.138092`, counterfactual `+0.000460`.
- Suite D: saturation `+0.016258`, exploration `−0.092787`, counterfactual `+0.002482`.
- N=1000: saturation `+0.008548`, 95% CI `[+0.005851,+0.011245]`; exploration `−0.101653`; counterfactual `+0.000292` with CI crossing zero.
- S1 event-aligned: saturation `+0.025434`, exploration `−0.127773`, counterfactual `−0.000030`.
- S2 frozen H1: saturation `−0.003978` in every one of 15 cells; exploration `+0.008843`; counterfactual `+0.000927`.
- Moderate signal: saturation `+0.046874`, exploration `−0.111195`, counterfactual `+0.001368`.
- `IMPLEMENTATION_CALIBRATION_GAP=false`.

The initial saturation-only interpretation was rejected by independent review because the gains require oracle/event-aligned hypotheses. `REAL_CHEAP_PRIMITIVE_ENGINEERING_JUSTIFIED=false`.

Scientific consequence:

- stop P2 exploration and P3 counterfactual work;
- do not start real cheap-primitive engineering;
- allow one frozen public representation-transfer gate;
- if saturation remains non-positive on repaired S2, close the planner route and retain EventRelation + BB-EM/operator work only.

## Superseded decisions

- Historical v1/v2 caches and failed v2 attempts must not be mixed with strict v2.
- The “full C6 multi-rule contribution” is not supported; only queried-negative barrier showed independent contribution.
- Proxy valley, duplicate suppression and selected expansion are not part of the main algorithm without new evidence.
- Full actor graph, calibrated VOI and statistical certificate are unvalidated targets.
