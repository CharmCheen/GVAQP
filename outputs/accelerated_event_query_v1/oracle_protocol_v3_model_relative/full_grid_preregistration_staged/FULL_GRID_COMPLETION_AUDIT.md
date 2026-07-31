# Full-Grid Preregistration Completion Audit

Audit state: `COMPLETE_REVIEWED_AWAITING_EXPLICIT_COMPUTE_APPROVAL`

- Exact units: 1,475; frame occurrences: 30,932; duplicate/missing units: 0/0.
- Tail units: DALI 12, HANGZHOU 2, WUHAN 6 frames; real processor-only audit PASS.
- Workers: V3_FULL_GRID_DALI: 567 calls on (2,6); V3_FULL_GRID_HANGZHOU: 561 calls on (3,5); V3_FULL_GRID_WUHAN: 347 calls on (1,7); disjoint union PASS; activation mode
  `staged_pair_authentication` with `V3_FULL_GRID_DALI` first.
- Cost: 16.097123 A100 GPU-hours expected; 19.4 envelope; three loads; zero reload/retry.
- Coverage: global and per-video determined fraction >= 0.99; parse failure release tolerance 0.
- Global fail-stop, cost shield, no-resume, partial nonpublication, K3 determinism,
  diagnostic independence, and evaluator/runtime separation are implemented and tested.
- Tests: 150 passed, 0 failed.
- Complete 1,475-record mock dry-run: DRY_RUN_FINALIZER_PASS_NOT_ORACLE; formal publication false.
- Independent review: `GO_TO_REQUEST_FULL_GRID_APPROVAL`.
- Execution seal SHA-256: `5136aaddfc5e7daee691c9faaab323f3159db6d52a469fade45fce6719847134`.
- Review bundle SHA-256: `06be559735038406dd736dc3e508e9f80a0b097febe0cd81aa6459b0c43465cc`.
- No compute approval artifact exists; no formal full-grid raw output or reference exists.
- V3 preflight and V2 frozen evidence were not modified or rerun.

Strongest conclusion: the exact full-grid protocol is ready to request compute
approval. It is not executed, does not establish representative adequacy, and
authorizes no downstream experiment.
