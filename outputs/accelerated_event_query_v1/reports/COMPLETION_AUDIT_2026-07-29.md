# Accelerated Event Query V1 — Completion Audit

Audit conclusion: `INCOMPLETE`; terminal success or failure is not yet justified.

This audit checks the original 24-section research specification against current direct artifacts. Passing implementation tests proves only the mechanisms they cover; it does not substitute for the required three-video physical experiments.

| Requirement | Current evidence | Status |
|---|---|---|
| Frozen query, event-level objective, precision 0.80 with 0.70/0.90 sensitivity, hard deadline order | `docs/ACCELERATED_EVENT_QUERY_CONTRACT_V1.md`, frozen V2 config | Established contract; no outcome |
| Event return schema with distinct probable/verified evidence | `types.py`, `incremental_k3.py`, focused tests | Implemented and unit-tested; not exercised on real new-query results |
| One-to-one event matching and duplicate treatment | `matching.py`, matching tests | Implemented and unit-tested |
| Incremental K3 after actions and post-deadline immutability | `incremental_k3.py`, K3/deadline tests | Kernel tested; full SCAN/VERIFY loop absent |
| Causal public state and future-information rejection | `state.py`, causality tests | Schema/guard tested; replay/controller not built |
| Frozen three real videos and 1,475-unit grid | video manifests and freeze audit | Established |
| Adequate fallible 32B operational oracle for the new query | reviewed V2 preflight seal; physical raw/attempt count 0/32 | Decision-critical evidence missing; explicit user approval required |
| Full 1,475-unit operational oracle and raw provenance | no authorized full-run design or outputs | Missing |
| K3 operational reference events parquet | `operational_reference_events/STATUS.md` | Missing; gated by oracle evidence |
| Frozen YOLO/proxy execution and candidate join | `scan_candidates/STATUS.md` | Missing |
| Candidate coverage and `SCAN_EVENT_RECALL_CEILING` on all videos | no real new-query references/candidates | Missing |
| Observed complete-path SCAN and VERIFY costs | `cost_calibration/STATUS.md` | Missing |
| Held-out safety bounds with zero overruns/incomplete admissions/post-deadline commits | no formal cost validation | Missing |
| Label-hiding replay with incremental EventRelation updates | `replay_environment/STATUS.md` | Missing |
| Deterministic `VERIFY_EVENT_CALIBRATION_TARGET` and `VERIFY_TOP1` ablation in replay | contract only; no replay implementation | Missing |
| Natural-state generation and forced-action branch values | `conditioned_values/STATUS.md` | Missing |
| Cross-video SCAN-better/VERIFY-better and safe-oracle headroom gates | `oracle_headroom/STATUS.md` | Missing |
| Required fixed, two-stage, myopic, R4, macro, and oracle baselines | no V1 baseline results | Missing |
| Public-state long-horizon advantage model, only if headroom passes | `state_models/STATUS.md` | Correctly deferred |
| Shielded controller and leave-one-video-out closed loop | `closed_loop/STATUS.md` | Correctly deferred |
| Event-query curves, deadline recall/precision/AUC, timing and K3 diagnostics | `figures/STATUS.md` | Missing |
| Required ablation matrix | `ablations/STATUS.md` | Correctly deferred |
| Twelve explicit final-report answers | report records all as open | Missing |
| One terminal decision from the frozen set | current nonterminal decision is `REVISE_ORACLE_PROTOCOL` | Missing |

## Decision-critical path

1. Obtain explicit user approval or rejection for only the independently reviewed 32-call V2 pilot.
2. If approved, execute exactly the 10/11/11 shards and apply the frozen analyzer plus independent claim-grounding finalizer.
3. If the pilot passes, design and separately approve a content-blind representative oracle audit; a targeted pass does not authorize the full grid.
4. Only adequate representative oracle evidence permits full operational references, the YOLO/K3 ceiling, observed safety costs, replay, and headroom in that order.
5. Learned-controller and ablation work remains conditional on the dynamic-headroom gate.

The observation that would revise this path immediately is a preflight numeric, reproducibility, sensitivity, semantic, or grounding failure; that would stop expansion and route to oracle-protocol revision or `INSUFFICIENT_EVIDENCE` rather than downstream controller work.
