# Full-Grid Preregistration Completion Audit

Audit state: `COMPLETE_REVIEWED_AWAITING_EXPLICIT_COMPUTE_APPROVAL`

- Exact units: 1,475; frame occurrences: 30,932; duplicate/missing units: 0/0.
- Tail units: DALI 12, HANGZHOU 2, WUHAN 6 frames; real processor-only audit PASS.
- Workers: V3_FULL_GRID_DALI: 567 calls on (2,6); V3_FULL_GRID_HANGZHOU: 561 calls on (3,5); V3_FULL_GRID_WUHAN: 347 calls on (1,7); disjoint union PASS; activation mode
  `staged_pair_authentication` with `V3_FULL_GRID_DALI` first.
- Cost: 16.097123 A100 GPU-hours expected; 29.0 fresh-run envelope; three loads; zero reload/retry within the fresh execution.
- Prior failed run: 136 completed/137 attempted, no formal publication or label reuse;
  conservative usage upper bound 1.444388 A100 GPU-hours.
- Prior plus fresh envelope: 30.444388 < 64 authorized A100 GPU-hours.
- Coverage: global and per-video determined fraction >= 0.99; parse failure release tolerance 0.
- Global fail-stop, cost shield, no-resume, partial nonpublication, K3 determinism,
  diagnostic independence, and evaluator/runtime separation are implemented and tested.
- Tests: 153 passed, 0 failed.
- Complete 1,475-record mock dry-run: DRY_RUN_FINALIZER_PASS_NOT_ORACLE; formal publication false.
- Independent review: `GO_TO_REQUEST_FULL_GRID_APPROVAL`.
- Execution seal SHA-256: `2189d821eba4b0e0022da4f0a1113e51ed2128351def12c4e310ffd36569c9ee`.
- Review bundle SHA-256: `f69eb4c7bef9aef89653875909d2003c92b009ba6c0e6e6cedbcbc80771e7983`.
- No compute approval artifact exists; no formal full-grid raw output or reference exists.
- V3 preflight and V2 frozen evidence were not modified or rerun.

Strongest conclusion: the exact full-grid protocol is ready to request compute
approval. It is not executed, does not establish representative adequacy, and
authorizes no downstream experiment.
