# V7 Runtime Abort Audit

Status: `VERIFIED_INFRASTRUCTURE_FAILURE; NOT A SEMANTIC RESULT`

The frozen V7 full-grid launcher authenticated all three sealed GPU pairs and
started all three workers. `WUHAN` completed its fixed schedule and exited
zero. The DALI and HANGZHOU worker/supervisor processes subsequently ceased to
exist while `DALI_u0485` and `HANGZHOU_u0553` remained durably reserved without
terminal records. At the final authoritative state snapshot, 1,385 of 1,475
units were completed and 90 were not terminally accounted for.

The frozen finalizer was run after process loss and emitted
`FULL_GRID_ABORTED_RUNTIME`:

- execution root: `outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative/full_grid_execution_staged_v7_review_corrections`
- V7 execution seal: `a564cb5b0e24d7c143e7f5430298f61b1f31f6781edfb5b6a5701d2e53605819`
- final-decision payload SHA-256: `4b0d6ae41dc8795c0c781e9c0e5b75b2b33b5a71f0d5b45493a7ce2917ff94fe`
- finalizer metrics payload SHA-256: `12605b868d770fccd2f9e9cda1f4022c21d17e386f985956a1e6c849b8cc21df`

This run is not a reference release and its raw model outputs are not used by
reference construction, selector construction, K0/K3 comparison, or metric
analysis. The conclusion follows the V7 sealed failure policy: there is no
in-approval resume, retry, output reuse, or partial publication. A future
execution, if lawful under compute authorization, must be a fresh complete
execution under a new pre-execution seal while preserving the V7 artifacts as
immutable failure evidence.
