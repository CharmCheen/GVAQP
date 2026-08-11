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
| Adequate fallible 32B operational oracle for the new query | exact 32/32 V2 records, metrics, independent grounding, finalizer | Contradicted: 31/32 parse, systematic three-video contradictions, 2/4 unsupported positives |
| Full 1,475-unit model-relative oracle and raw provenance | expanded user authorization; six preserved rejected preregistration seals; current continuous-clock/tail-input revision | Authorized in principle but not executed; no formal raw output exists |
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
| One user-authorized targeted-pilot decision | `TARGETED_PILOT_DECISION_V2.json` | Established: `REVISE_ORACLE_PROTOCOL` |
| One terminal decision for the full research objective | downstream gates cannot be evaluated after H1 failure | Not yet justified; do not misstate the targeted decision as full-system evidence |

## Decision-critical path

1. Preserve V2 at `REVISE_ORACLE_PROTOCOL`; V3 does not repair or overwrite its
   impossible boundary, cross-video contradictions, or unsupported positives.
2. Complete and independently review the prospective V3 model-relative
   full-grid package. The current blockers are continuous GPU-residency cost
   accounting and explicit tail-unit model visibility, not user authorization.
3. Execute 1,475 calls only under an exact reviewed seal and idle/exclusive GPU
   profile; partial outputs remain non-reference evidence.
4. Only an authenticated complete V3 run may release K3 reference events and
   open the SCAN ceiling/cost/replay/headroom gates. No downstream result exists
   yet.

The V2 rejection remains historical evidence. V3 intentionally narrows the
authority boundary to a model-relative unit label with K3-owned event timing;
this is a prospective construct, not a claim of human-driving semantic
accuracy or representative adequacy. The full research objective remains
incomplete until physical full-grid and downstream gates are evaluated.
