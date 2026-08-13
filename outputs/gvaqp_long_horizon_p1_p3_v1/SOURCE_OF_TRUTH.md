# P1 source of truth

## Verified facts

- The released matrix has three independent videos (DALI, HANGZHOU, WUHAN), one frozen semantic query (`Q_DRIVER_RESPONSE_V1`), a one-candidate-per-10-second-unit interface, and six fixed query budgets. The release contains one natural Proxy A: a prospective YOLOv8n object/motion score.
- The model-relative geometry audit replays 378 cached C1 cells. Yield-only LOVO macro R² is 0.006; adding public/online geometry is 0.795; reference-aware diagnostic is 0.980. It is explicitly model-relative and uses the C1-shaped reference; `EVENT_EVIDENCE_GEOMETRY = PARTIAL`, `ROBUST_EVENT_POLICY_OPPORTUNITY = WEAK`.
- The strongest public matched-trace signal reported there is `number_of_temporal_regions_touched`, but the top equal-yield counterexamples with C1 F1 difference >=0.15 occur in only 1/3 videos. That evidence is not an independent replication.
- P0 establishes only a cached, model-relative C1 gap-limited materialization effect. The stated main limitation is the K3-defined reference relation. The prior human-continuity package is a blinded pairwise continuity test with no completed human labels; it is not a P1 event reference.
- The current alignment audit explicitly documents that no reproducible second natural proxy shares this candidate universe and that current evidence does not establish human semantic correctness or learned-controller benefit.

## Current hypotheses

- H1: At equal verified-positive count, broader online-visible evidence geometry improves recovery of independent temporal events.
- H0: The apparent geometry signal primarily reflects C1's fixed gap rule and/or the model-relative reference; yield or generic temporal coverage accounts for recovery once independently measured.
- H2: If H1 is real, it should survive a natural proxy-family change and directly improve human event coverage/touch endpoints, not merely C1 EventF1.

## Known confounds

- Current event outcomes and reference are model-relative and K3-grouped, so they cannot be P1's primary endpoint.
- Only three video-query clusters and a single natural proxy family are currently released; this cannot meet the required 6-cluster / 2-proxy P1 pass gate.
- Existing ranking/exposure variants are synthetic and cannot substitute for a second natural proxy.
- Positive-cluster features with a 10-second threshold are too close to C1 and are excluded from P1 primary geometry claims.

## Frozen components

The exact freeze is in [P1_PROTOCOL.json](P1_PROTOCOL.json). Candidate/unit semantics, C1's 10-second gap rule, current EventRelation evaluator, and query-budget semantics are frozen. P1 may not retune these components or train a selector.

## Authoritative inputs reviewed

- `outputs/event_evidence_geometry_v1/{FINAL_GEOMETRY_REPORT.md,ANALYSIS_PROTOCOL.json,TRACE_GEOMETRY_FEATURES.csv}`
- `outputs/main_thesis_alignment_v1/{FINAL_ALIGNMENT_REPORT.md,MAIN_THESIS_DECISION.md,AUDIT_PROTOCOL.json}`
- `outputs/p0_materializer_validation_v3/{FINAL_RESEARCH_REPORT.md,MAINLINE_DECISION.md,EXPERIMENT_PROTOCOL.json,event_metrics.csv}`
- `outputs/p0_materializer_mechanism_ablation_v1/{MECHANISM_PROTOCOL.json,mechanism_summary.csv}`
- `outputs/research_contribution_convergence_v1/{PAPER_MAINLINE_DECISION.md,CONTRIBUTION_SCORECARD.csv}`
- `outputs/v10_multiseal_reference_v1/{REFERENCE_MANIFEST.json,MULTI_SEAL_RELEASE_DECISION.md,FINAL_UNIT_REFERENCE.parquet,K3_MODEL_RELATIVE_EVENT_RELATION.parquet}`
