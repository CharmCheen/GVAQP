# Changed files

Implementation and tests:

- `scripts/run_psvr_two_video_physical.py`: added the preregistered observable stage controller path.
- `scripts/run_psvr_stage1_physical.py`: H-STAGE1 preregistration checks, matrix execution, and smoke gate.
- `scripts/evaluate_psvr_bottleneck.py`: normalized NumPy booleans before JSON serialization.
- `scripts/evaluate_psvr_stage1.py`: evaluator-only correctness, quality, lifecycle, and terminal decision.
- `tests/psvr_runtime/test_bottleneck_factorial.py`: observable-state controller correctness cases.

Research state and evidence:

- `outputs/psvr_bottleneck_research/`: Cycle 1–3 evidence, invalidation archives, final decision, reports, tables, and state.
- `outputs/psvr_two_video_loop/deadlines/profiles/` and `raw_profile/`: fresh same-topology 20-sample profile.
- `outputs/psvr_two_video_loop/deadlines/profile_archive_20260718T022600Z/`: expired profiles retained.
- `docs/PSVR_HYPOTHESIS_REGISTRY.md`, `docs/PSVR_DECISION_LEDGER.md`, and `docs/PSVR_FAILURE_CATALOG.md`.
- `outputs/psvr_autonomous_research/` persistent state, queue, method registry, index, current best, and claims.

No Stage 1–5, H-EXPOSE2, proxy, benchmark, reference, or held-out artifact was overwritten.
