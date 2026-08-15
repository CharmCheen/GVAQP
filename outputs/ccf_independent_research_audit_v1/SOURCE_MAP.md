# GVAQP independent audit — source map

This file records which artifacts were treated as primary evidence for each
claim family, and where each claim was traced. It is a provenance index, not a
restatement of project conclusions.

## Precedence rules applied

Per `AGENTS.md`, claims were traced in this order:

1. frozen result tables, protocol hashes, completion manifests, gate decisions;
2. later adversarial / identifiability audits that narrow claim scope;
3. `PROJECT_STATE_OF_TRUTH.md` and the root ledgers (index only, not ground truth);
4. older narrative reports.

## Key source files (verified in this audit)

| Evidence | Path | What it establishes |
|---|---|---|
| K3 materializer | `src/garc_eval/accelerated_event_query/k3_unit_event_adapter.py` | Confirms `maximum_merge_gap_seconds=10.0` gap rule (C1), duration/unknown/parse semantics; events built only from model-relative `relevant` units |
| Event matching | `src/garc_eval/accelerated_event_query/matching.py` | Confirms one-to-one max-cardinality then tIoU; strict positive temporal overlap eligibility (`minimum_tiou=0.0`) |
| Model-relative reference | `src/garc_eval/accelerated_event_query/model_relative_event_relation.py` | Confirms reference is K3-grouped from full-grid model-relative unit labels |
| Sequential env | `src/rc_sem/sequential.py` | Confirms SCAN=release precomputed proxy rows; VERIFY=reveal cached label; abstract costs 0.1/1.0; `strict_k3_groups` adjacency grouping |
| Identifiability audit | `outputs/original_theory_identifiability_audit_v1/*` | Confirms candidate universe 1475/1475 precomputed; exposure recall 1.0; 108-state decomposition |
| Main alignment | `outputs/main_thesis_alignment_v1/*` | Proxy AUPRC 0.2584–0.3146; ranking gap 0.0951; exposure gap 0.0; monotonicity 0.48% |
| Materializer P0 v3 | `outputs/p0_materializer_validation_v3/*` | 54/54 valid controlled pairs; K3 better/equal/worse 40/14/0; median ΔF1 +0.1457 |
| Mechanism ablation | `outputs/p0_materializer_mechanism_ablation_v1/*` | gap-only C1 median +0.1377; duration/barrier/extras ≈ 0 |
| Geometry | `outputs/event_evidence_geometry_v1/*` | yield-only LOVO R2 0.006; +geometry 0.795; reference-aware 0.980; counterexample 1/3 videos |
| P1 shadow | `outputs/p1_shadow_vlm_direct_reference_v1/*` | 2/6 clusters positive; macro coverage +0.003193; geometry MAE gain 0.000665 |
| P2 novelty killer | `outputs/p2_query_policy_novelty_killer_v1/*` | generic relevance+coverage ties StaticProxyRank; semantic-state residual ABSENT |
| Controller / MAB | `outputs/public_state_predictability_cached_v3/SUMMARY.json`; `MAB_RESEARCH_DIRECTION_DECISION.md` | learned regret 0.009693 vs fixed 0.000885; 0/18 immediate positives; 1/7 continuation conversions |
| P1 readiness | `outputs/gvaqp_long_horizon_p1_p3_v1/*` | human label log 0 rows; automated grid complete; frozen analyzer ready |
| Reference circularity | `outputs/v10_multiseal_reference_v1/REFERENCE_CIRCULARITY_AUDIT.md` | K3-defined model-relative reference → reference-construction interaction risk |

## Claims not independently re-derived (relied on frozen artifacts)

Physical Guangzhou runtime results (deadline-safe B trace, one event at ~224 s)
were accepted from `MAB_RESEARCH_DIRECTION_DECISION.md` and its cited frozen
JSON traces with hashes, but were not re-executed on GPU. This audit did not
run any model inference or GPU workload.
