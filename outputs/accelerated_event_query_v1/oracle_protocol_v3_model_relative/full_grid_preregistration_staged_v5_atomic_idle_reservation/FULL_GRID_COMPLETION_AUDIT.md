# Full-Grid Preregistration Completion Audit

Audit state: `COMPLETE_REVIEWED_AWAITING_EXPLICIT_COMPUTE_APPROVAL`

- Exact units: 1,475; frame occurrences: 30,932; duplicate/missing units: 0/0.
- Tail units: DALI 12, HANGZHOU 2, WUHAN 6 frames; real processor-only audit PASS.
- Workers: V3_FULL_GRID_DALI: 567 calls on (2,6); V3_FULL_GRID_HANGZHOU: 561 calls on (3,5); V3_FULL_GRID_WUHAN: 347 calls on (1,7); disjoint union PASS; activation mode
  `staged_pair_authentication` with `V3_FULL_GRID_DALI` first.
- Cost: 18.835258 A100 GPU-hours expected; 56.0 fresh-run envelope; three loads; zero reload/retry within the fresh execution.
- Immediate prior failed run: 473 completed/476 attempted, no formal publication or label reuse;
  conservative usage upper bound 6.697182 A100 GPU-hours.
- Prior plus fresh envelope: 62.697182 < 64 authorized A100 GPU-hours.
- Coverage: global and per-video determined fraction >= 0.99; parse failure release tolerance 0.
- Global fail-stop, cost shield, no-resume, partial nonpublication, K3 determinism,
  diagnostic independence, and evaluator/runtime separation are implemented and tested.
- Tests: 158 passed, 0 failed.
- Complete 1,475-record mock dry-run: DRY_RUN_FINALIZER_PASS_NOT_ORACLE; formal publication false.
- Independent review: `GO_TO_REQUEST_FULL_GRID_APPROVAL`.
- Execution seal SHA-256: `8f1884ac84609aab86e726c5c2caf2c4c2739329fed89f7f0db8e5af1b9ac184`.
- Review bundle SHA-256: `eb5e2e64a20c7a0e0aa69a173fd1e9bd21c06e55a4f696475dcf1de1a4e48d21`.
- No compute approval artifact exists; no formal full-grid raw output or reference exists.
- V3 preflight and V2 frozen evidence were not modified or rerun.

Strongest conclusion: the exact full-grid protocol is ready to request compute
approval. It is not executed, does not establish representative adequacy, and
authorizes no downstream experiment.
