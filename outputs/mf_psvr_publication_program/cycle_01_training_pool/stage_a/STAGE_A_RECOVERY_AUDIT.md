# STAGE_A_RECOVERY_AUDIT.md

## Recovery performed
- Date (UTC): see STAGE_A_RECOVERY_STATE.json
- Method: read-only durable-state audit, no oracle calls, no GPU work.

## Phase 1 — Active processes
- `pgrep -af "run_mf_psvr_stage_a_oracle|mf_psvr|oracle"`: only the grep wrapper itself; **no Stage-A runner process**.
- `nvidia-smi --query-compute-apps`: empty; **no GPU compute apps**.
- Conclusion: no active runner to audit or resume. Safe to recover from durable checkpoint.

## Phase 2 — Workspace audit
- `git status`: working tree has many untracked/scaffolding changes unrelated to Stage A; core Stage-A files are tracked and unmodified at the working-tree level.
- Three target files compile cleanly (py_compile) and the focused test suite passes (9 passed).
- `freeze-spec` ran successfully and is idempotent (`execution_spec_hash` stable, self-hash valid, pre-inference audit copy preserved at `oracle/PREINFERENCE_AUDIT_MANIFEST.json`).
- `preflight` reports `WAITING_FOR_FULL_POOL_CANDIDATES_AND_SELECTION`.

### Stage-A artifact inventory (actual on disk)
| Artifact | Exists | Notes |
|---|---|---|
| STAGE_A_ORACLE_EXECUTION_SPEC.json | YES | written by freeze-spec |
| PREINFERENCE_AUDIT_MANIFEST.json | YES | preserved copy |
| STAGE_A_FROZEN_SAMPLE.csv | NO | upstream dependency missing |
| STAGE_A_QUERY_OPPORTUNITIES.csv | NO | upstream dependency missing |
| STAGE_A_FREEZE_MANIFEST.json | NO | upstream dependency missing |
| INPUT_IDENTITIES.jsonl | NO | prepare() not run |
| ORACLE_BUILD_CONFIG.json | NO | prepare() not run |
| PREPARATION_COMPLETE.json | NO | prepare() not run |
| MODEL_CONTENT_VALIDATION.json | NO | prepare() not run |
| RESOLVED_INFERENCE_RUNTIME.json | NO | infer() not run |
| ATTEMPT_EVENT_LOG.jsonl | NO | infer() not run |
| STAGE_A_ORACLE_STATE.json | NO | prepare() not run |
| STAGE_A_ORACLE_COMPLETE.json | NO | finalize() not run |
| STAGE_A_SUPPORT_GATE_REPORT.json | NO | finalize() not run |
| STAGE_A_K3_EVENT_GROUPS.csv | NO | finalize() not run |
| STAGE_A_PHYSICAL_COST.json | NO | finalize() not run |
| ORACLE_CALL_MANIFEST.csv | YES | header only (0 data rows) |
| ORACLE_LABEL_MANIFEST.csv | YES | header only (0 data rows) |

### Upstream dependency audit (the actual blocker)
- `CANDIDATE_STATE.status = PREFLIGHT_PASS_GPU_NOT_RUN`
- `completed_provider_videos = 0`, `physical_y8_frames = 0`, `query_unit_rows = 0`
- `candidates/UNIT_MANIFEST.csv` exists (2654 units) but `candidates/UNIT_SCORES.csv` is **MISSING** (expected 5308 rows).
- The candidate extraction runner `run_mf_psvr_training_pool_candidates.py extract --confirm-gpu` has never produced `UNIT_SCORES.csv`.
- `freeze_mf_psvr_stage_a_sample.py` requires `CANDIDATE_STATE.status == COMPLETE`, 603 completed videos, and 5308 unit-score rows. None are satisfied.

## Phase 3 — Stage-A classification (derived from artifacts, not transcript)
- `STAGE_A_STATE = NOT_PREPARED_ZERO_CALLS`
- But more precisely: **blocked upstream by incomplete full-pool candidate extraction**. The Stage-A code path itself is intact (compiles + 9 tests pass). The interrupted "code patch" was in fact already complete and green.

## Phase 4 — Code-patch status
- The previously reported additions (STAGE_A_PHYSICAL_COST.json generation, model-load accounting, preparation/model-hash/frame-decode/oracle-gen/parse/K3/finalization cost fields, focused tests) are present in the source and verified:
  - `py_compile` of all three files: OK
  - `pytest tests/psvr_runtime/test_mf_stage_a_oracle.py`: 9 passed
- No code repair was required to reach a compilable/test-green state. The patch was never "incomplete" — it was simply never exercised because no physical calls had run.

## Phase 5/6 — No oracle work performed
- 0 physical oracle attempts started.
- 0 raw outputs, 0 parsed outputs.
- No uncertain started calls, nothing to reconcile, nothing to retry.
- Cannot finalize: requires 96 durable accepted calls, which require the upstream freeze + prepare + infer.

## Next highest-information action
The decision-critical uncertainty is whether the full-pool Y8 extraction (603 videos, 5308 score rows) can complete. This is the true research bottleneck, not the Stage-A oracle plumbing. It requires explicit GPU/oracle authority (it is a charged GPU pipeline). Before that is authorized, no Stage-A physical oracle call — including the 96 frozen calls — is permissible, because the frozen sample cannot be selected until `UNIT_SCORES.csv` exists and `CANDIDATE_STATE.status == COMPLETE`.
