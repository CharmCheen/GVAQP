# ARC baseline readiness audit

## Conclusion

The requested cached baseline, `ARC-CACHED-REPLAY-v1`, is implemented, validated, and fully executed. The physical baseline named in the earlier Stage-1 task, `ARC-UNIT-INSPIRED-PHYS-v1`, is **not ready for a physical smoke run**: commit `97d3412a9` did not add an ARC/SMDP/runtime implementation, and no ARC physical runner currently binds the causal selector to complete online proxy generation, the frozen physical oracle, shared monotonic deadline admission, and durable snapshots.

This distinction is consequential. The completed result is an algorithmic cached replay, not a native ARC reproduction and not physical hard-deadline evidence.

## Repository and commit findings

- Applicable `AGENTS.md` files in the writable worktree and read-only source repository were read first; they are identical.
- Worktree branch at audit time: `arc-phys-baseline`; HEAD: `dc5c507605f603f01d2a7f07e5b492ad0ca06280`.
- The only initial worktree status entry was the user-owned untracked `CODEX_TASK_ARC_BASELINE.md`; it was not edited.
- Commit `97d3412a9` is an ancestor of HEAD and is also referenced by `arc-test`.
- Despite its subject, “Implement ARC baseline adaptation,” the commit adds no ARC, SMDP, physical-runtime, or ARC-test file. Its 92-file patch is primarily a safety-reference pilot plus unrelated research artifacts. There is therefore no commit-introduced ARC implementation to complete.
- No matching intended implementation was recoverable from dangling Git objects.
- The read-only repository `/root/charm/GVAQP` has no tracked diff after this work. Its seven pre-existing untracked full-grid preregistration directories remain untouched.

## Inspected implementation map

| Area | Inspected evidence | Finding |
| --- | --- | --- |
| ARC literature and adaptation contract | `ARC_FULLTEXT_AUDIT.md`, `BASELINE_ADAPTATION_SPEC.md` | The benchmark can support only a unit-level adaptation; no current row may be called faithful ARC. |
| Historical ARC | `try_or_no/arc_source/arc/{arc.py,pruning_phase.py,refinement_phase.py,tools.py,sampling_tools.py,score_tools.py}` | Candidate, clustering, entropy, uncertainty, progressive sampling, propagation, and confidence logic survives. Historical confidence needs a NumPy-2 scalar compatibility wrapper. |
| Prior ARC/PSTR replay | `BSEC_AQP_Development_Gate_v1/scripts/run_native_arc_vs_pstr.py` and `outputs/native_arc_vs_pstr/` | Supplies frozen configuration, call budgets, seeds, inputs, clusters, sealed PSTR order, shared K3/evaluator, and historical outputs. The script points to ignored ARC sources no longer present. |
| Frozen input universe | BSEC `frozen_inputs/`, `sealed_pstr/`, `arc_clusters/`, and `manifest.json`; matching files in `/root/charm/GVAQP` | Three tasks, two independent source videos, 624 units, budgets 5/10/20/50/80/100, seeds 0–4. All selected file hashes match both repositories and the manifest. |
| Current physical runtime | `scripts/run_psvr_two_video_physical.py`; `src/garc_eval/psvr_runtime/{runner,deadline_guard,physical_oracle,two_video_physical_oracle,sandbox}.py` | Existing PSVR code implements monotonic accounting, tail-aware admission, isolated oracle access, K3, serialization, fsync, and atomic replacement. It is not wired to ARC. |
| SMDP/controller | `src/garc_eval/scan_confirm_controller/smdp_*.py` and `tests/test_smdp_*.py` | Existing state/action/budget/causality logic passes its CPU regression tests, but commit `97d3412a9` added no ARC policy integration. |
| K3/evaluator | `clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py`, accelerated K3/state tests, existing experiment outputs | `k3_bridge_safe` uses queried-positive anchors only and the frozen evaluator uses overlap-any one-to-one Hungarian matching. The exact same implementation is reused for both replay methods. |
| New cached adapter | `src/garc_eval/arc_cached_replay/{core.py,experiment.py}` and `scripts/run_arc_cached_replay.py` | Causal, one-query-at-a-time ARC replay with scheduling-only propagation, strict K3 output, frozen current-method pairing, full artifact persistence, aggregation, and reporting. |

## Physical-contract requirement matrix

| # | Requirement | Cached replay state | Physical readiness |
| --- | --- | --- | --- |
| 1 | Benchmark 10-second units are ARC records | Satisfied on the immutable selected grid. Two realcartest slices are entirely 10 seconds; dataset3 preserves 346 ten-second units plus one overlapping 5-second terminal exception. | Partial: the physical runner still needs to bind the frozen online UnitTable and explicitly handle the terminal exception. |
| 2 | Map calibrated `p_i(q)` to `[1-p_i(q), p_i(q)]` | Satisfied exactly in `ARCSelector`. | Missing online calibrated-proxy binding. |
| 3 | Complete online proxy pass before refinement | Cached replay validates and loads a complete frozen proxy table before ARC starts. | Missing: no ARC physical runner performs and charges the complete online pass. |
| 4 | Fixed Jensen-Shannon temporal clustering | Satisfied; recomputed historical sequential SciPy Jensen-Shannon-distance assignments match all frozen cluster files. | Algorithm ready; common-clock physical integration missing. |
| 5 | Native `tau=1`; K3 owns bridging | Satisfied; frozen `tau=1` and unchanged `k3_bridge_safe` are used. | K3 runtime exists but is not wired to a physical ARC controller. |
| 6 | Propagation changes scheduling/diagnostics only | Satisfied; 108 scheduling propagations occurred and none entered comparable EventRelation anchors. | Selector behavior ready; physical integration missing. |
| 7 | Only physically verified positives anchor events | Cached analogue satisfied: only explicitly queried frozen-oracle positives anchor K3. | Missing physical execution; cached labels are not newly physically verified. |
| 8 | Indeterminate results are charged, unknown, and unpropagated | Satisfied by the causal selector/oracle contract and parameterized tests for unknown, timeout, parse failure, ambiguous, abstain, and unusable. Selected frozen inputs contain only determinate outcomes. | Physical budget/action trace binding remains missing. |
| 9 | All work shares one monotonic wall-clock deadline | Not claimed by cached replay. | Missing for ARC. Existing PSVR primitives demonstrate the needed mechanism but do not execute ARC proxy/clustering/selection. |
| 10 | Reserve complete action plus durable commit before VERIFY | Not applicable to logical-call cached replay. | Missing ARC admission integration. Existing `TailAwareDeadlineGuard` and durable snapshot code are reusable. |
| 11 | Separate native candidates from confirmed EventRelation | Satisfied: `native_candidate_diagnostics/` is separate from `predictions/`. | Output design ready; physical persistence integration missing. |
| 12 | Do not claim native ARC confidence guarantee | Satisfied in code, manifests, and reports. | Ready as a reporting rule. |

## Exact changes

- Added `src/garc_eval/arc_cached_replay/core.py`:
  - exact probability mapping and frozen ARC configuration;
  - historical sequential Jensen-Shannon clustering;
  - causal selection/observation state machine;
  - selection-authorized, deduplicating frozen-oracle accessor;
  - explicit unknown/parse/timeout semantics;
  - separation of scheduling propagation from explicitly observed labels;
  - finite empty-candidate confidence handling;
  - NumPy-2 scalarization compatibility repair around unmodified historical confidence semantics.
- Added `src/garc_eval/arc_cached_replay/experiment.py` and `scripts/run_arc_cached_replay.py`:
  - hash-bound input selection and worktree/read-only-copy checks;
  - full 180-run ARC/current comparison;
  - strict shared K3 and frozen evaluator execution;
  - ordered trace, prediction, match, native diagnostic, metric, curve, AUC, paired, manifest, provenance, validation, and report artifacts;
  - seed-within-task and slice-within-video aggregation before treating two source videos as independent.
- Added `tests/arc_cached_replay/test_arc_cached_replay.py` with 15 focused contract tests.
- Created the complete result tree at `outputs/arc_cached_replay_v1/`.
- No vendored ARC file, frozen input, oracle label, reference, prompt/parser, evaluator rule, original-repository file, CUDA setting, or process was changed.

## Commands and results

Material inspection commands included:

```text
git status --short --branch
git show --stat --oneline --decorate 97d3412a9
git show --format=fuller --find-renames 97d3412a9
sha256sum try_or_no/arc_source/arc/arc.py try_or_no/arc_source/arc/pruning_phase.py try_or_no/arc_source/arc/refinement_phase.py try_or_no/arc_source/arc/tools.py
```

Validation and execution commands:

```text
pytest -q tests/arc_cached_replay/test_arc_cached_replay.py
# Collection error: garc_eval was not importable without PYTHONPATH=src.

PYTHONPATH=src pytest -q tests/arc_cached_replay/test_arc_cached_replay.py
# Intermediate result: 6 failed, 9 passed; exposed NumPy-2 scalar conversion and immutable terminal-grid assumptions.

PYTHONPATH=src pytest -q tests/arc_cached_replay/test_arc_cached_replay.py
# Final focused result: 15 passed in 0.89 s.

PYTHONPATH=src python scripts/run_arc_cached_replay.py
# Completed 180/180 runs; no stdout errors.

PYTHONPATH=src pytest -q tests/arc_cached_replay/test_arc_cached_replay.py tests/test_smdp_action_legality.py tests/test_smdp_budget_accounting.py tests/test_smdp_controller_fallback.py tests/test_smdp_determinism.py tests/test_smdp_oracle.py tests/test_smdp_state_causality.py tests/psvr_runtime/test_deadline_guard.py tests/psvr_runtime/test_runner_boundaries.py tests/accelerated_event_query/test_post_deadline_event_immutability.py tests/partial_scan_v2/test_run_recovery.py tests/partial_scan_v2/test_runtime_accounting.py
# 74 passed in 51.13 s.

PYTHONPATH=src python -m compileall -q src/garc_eval/arc_cached_replay scripts/run_arc_cached_replay.py
# Passed with no output.

git diff --check
# Passed with no output.

PYTHONPATH=src python scripts/validate_arc_cached_replay_outputs.py
# Recomputed 180 persisted rows and checked 640 artifact hashes with zero failures.
```

An independent post-run script reloaded all 180 persisted predictions, recomputed the required frozen-evaluator metrics, checked every trace for duplicate units, and checked every prediction anchor against explicitly queried positives: 180 rows recomputed, zero failures. Its first attempt correctly exposed stale staging prefixes in `per_run_metrics.csv`; the publisher and persisted paths were repaired, and the complete audit then passed.

No formatter, linter, or static type checker was available (`ruff`, `mypy`, `black`, and `flake8` were absent). These checks were not run and are not described as passed. No test was skipped in the reported focused or 74-test commands.

## Remaining uncertainties and limitations

- The exact ignored, instrumented ARC entry point recorded by the historical manifest (`53e920...`) is absent. The surviving `arc.py` differs, although pruning/refinement/tools hashes match exactly. Parity is therefore with the surviving historical control loop plus the semantics-preserving NumPy-2 repair.
- The two frozen realcartest derivatives do not retain prompt/parser hashes. Dataset3 does retain bound prompt/parser/model hashes upstream.
- The selected evidence is post hoc and open-label, uses VLM-defined pseudo-oracle references, has only two independent source videos, and has two slices from one of those videos. Statistical power and generalization are insufficient.
- ARC often terminates below the nominal budget under its frozen confidence rule, especially on `realcartest_0_1570`. Exact filling was not enabled because the frozen configuration forbids it.
- No proxy, decode, model, VERIFY, serialization, fsync, or deadline latency was measured in cached replay.
- A physical ARC runner, online calibrated unit probability source, ARC-specific tail profiles, and end-to-end durable commit integration remain absent.

## Physical smoke decision

Physical smoke is **not technically authorized**. There is no valid executable smoke command today: `scripts/run_arc_unit_inspired_physical.py` does not exist, and using the PSVR runner under an ARC name would violate the information, proxy-pass, and deadline contracts.

The interface that must exist before approval can be requested is provisionally:

```text
PYTHONPATH=src python scripts/run_arc_unit_inspired_physical.py \
  --config <frozen-physical-arc-config.json> \
  --task <source-video-query-task-id> \
  --deadline-name T_transition \
  --seed 0 \
  --smoke
```

This is deliberately marked non-executable, not a next command to run. Its expected inputs would be the frozen UnitTable, Q1/Q2 prompt/parser/model identities, source video and immutable opportunity mapping, independently calibrated unit probability configuration, fixed ARC/K3 configuration, frozen deadline, and task-matched latency profiles. Expected outputs would include the complete online proxy trace, cluster assignments, ARC native diagnostics, unique VERIFY trace, oracle-confirmed EventRelation snapshots, admission decisions, monotonic stage timings, serialization/fsync/atomic-replace timings, failure state, and hashes.

Estimated GPU/model actions for one eventual smoke are: load and warm the frozen online proxy components; decode and scan the complete source video; compute all calibrated unit probabilities before ARC refinement; initialize/synchronize the frozen oracle session; run only admitted Qwen VERIFY calls selected by ARC; synchronize each charged GPU action; then perform CPU K3 and durable snapshot commits. Whether an 8B refiner is part of the calibrated probability path is unresolved and must be frozen before a physical command is valid. None of these actions was performed in this task.
