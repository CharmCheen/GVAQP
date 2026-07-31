# Post-SCAN chain completeness audit

Audit date: 2026-07-27

Frozen source: `/qiuyeqing/llama_prl/G-ARC` at `5047241b0561b911b9a519b18e8e7591c0074e70`

Audited core baseline: `20dabb57a2bf6b6d1766c9b951acfaa5fe4c9b92`

## Conclusion

`SCAN_ONLY_BEFORE = false`: the baseline already contained a Frontier, R4 controller, CONFIRM adapter, runner, and CLI. However, `POST_SCAN_CHAIN_COMPLETE_BEFORE = false`. Direct code and test inspection found that frozen candidate generation was folded into permissive manifest conversion, CONFIRM parsing and failure behavior were incomplete, post-result event materialization was not an explicit runtime boundary, durable state was mutated before persistence and had no final STOP snapshot, and the causal q90 estimator did not match the frozen linear-quantile/global-fallback behavior. The previous curation success statement therefore overstated completeness.

After the repairs recorded below, the runnable replay/dry-run chain is:

```text
AnytimeLargestGap SCAN
-> frozen candidate generation
-> Frontier admission/deduplication/retention
-> deadline admission + fixed 25:75 realized-wall-clock choice
-> frozen CONFIRM adapter
-> result parsing
-> replay event materialization
-> candidate/event deduplication
-> fsync + atomic-replace durable commit
-> STOP/final durable result
```

The core contains no Oracle client. The physical K3 materializer remains in the frozen source; replay inputs contain its frozen event IDs, and the curated materialization boundary validates/canonicalizes those IDs without making a new Oracle call.

## Itemized runtime audit

Every source entry below refers to source commit `5047241b0561b911b9a519b18e8e7591c0074e70`. “Covered” means executable tests, not documentation presence.

| item | target repository path | source repository path | source commit | runtime status | test coverage |
|---|---|---|---|---|---|
| `SCAN_IMPLEMENTATION` | `src/garc/scan/policy.py` | `src/garc_eval/scan_headroom/trusted_policies.py`; `src/garc_eval/scan_scheduler/config.py` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Present; `ANYTIME_LARGEST_GAP`, deterministic causal public-state selection | `tests/test_safe_coverage.py`, including exhaustive frozen-reference parity |
| `CANDIDATE_GENERATION` | `src/garc/controller/candidate.py`; called by `src/garc/controller/runner.py` | `scripts/run_psvr_two_video_physical.py::causal_unit_candidates`; `src/garc_eval/mf_psvr/candidate_identity.py::bind_track_witness`; `src/garc_eval/scan_confirm_controller/runner.py::_visible_candidates` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Restored; first-visible top-track binding, immutable witness, stable creation metadata, accumulated visible-prefix emission | `tests/test_post_scan_chain_parity.py` top/tie binding, prefix re-emission, disappearance rejection |
| `FRONTIER_ADMISSION` | `src/garc/controller/frontier.py` | `src/garc_eval/scan_confirm_controller/frontier_adapter.py` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Present and wired after every SCAN | `tests/test_frontier_contract.py` sequential differential batches |
| `FRONTIER_DEDUPLICATION` | `src/garc/controller/frontier.py` | `src/garc_eval/scan_confirm_controller/frontier_adapter.py` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Present; identity is `unit_id`; queried/discarded units cannot re-enter | `tests/test_frontier_contract.py`; duplicate-cluster end-to-end test in `tests/test_post_scan_chain_parity.py` |
| `FRONTIER_RETENTION` | `src/garc/controller/frontier.py` | `src/garc_eval/scan_confirm_controller/frontier_adapter.py` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Present; capacity and frozen order `(-score, unit_id, track_id, candidate_id)` | 24 input-order permutations plus sequential cap/drop parity in `tests/test_frontier_contract.py` |
| `CONFIRM_SELECTION` | `src/garc/controller/frontier.py::best`; `src/garc/controller/runner.py::_confirm` | `src/garc_eval/scan_confirm_controller/frontier_adapter.py`; `src/garc_eval/scan_confirm_controller/runner.py::step` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Present; always the first retained frozen-order row | 24 selection permutations and sequential source-reference parity |
| `CONFIRM_ADAPTER` | `src/garc/confirm/adapter.py` | `src/garc_eval/scan_confirm_controller/runner.py::step`; `src/garc_eval/psvr_runtime/runner.py` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Restored as injected replay/physical boundary; no embedded Oracle; backend failures are non-committing | adapter parity and end-to-end backend-failure tests in `tests/test_post_scan_chain_parity.py` |
| `RESULT_PARSING` | `src/garc/confirm/adapter.py::parse_confirm_result` | `outputs/scan_confirm_decision_v1/audits/action_outcome_audit.json`; `src/garc_eval/scan_confirm_controller/runner.py::step` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Restored explicit validation of completion, status, cost, label, and raw utility IDs | positive/negative parsing parity and failure paths in `tests/test_post_scan_chain_parity.py` |
| `MATERIALIZATION` | `src/garc/confirm/materialize.py` | `src/garc_eval/psvr_runtime/runner.py::materialize_and_commit`; `Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py::materialize_from_trace` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Restored explicit request and post-result boundaries. Replay consumes already-frozen K3 event IDs, enforces negative semantics, and canonicalizes identity | materialization frozen-reference parity; pre-request and post-result failure tests |
| `EVENT_OR_CLUSTER_DEDUPLICATION` | `src/garc/controller/candidate.py`; `src/garc/controller/frontier.py`; `src/garc/controller/runner.py` | `src/garc_eval/mf_psvr/candidate_identity.py`; `src/garc_eval/scan_confirm_controller/frontier_adapter.py`; `src/garc_eval/scan_confirm_controller/runner.py` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Present at unit, Frontier, per-result event, and cross-action event levels | duplicate candidate tracks and duplicate event IDs count once in `tests/test_post_scan_chain_parity.py` |
| `DURABLE_COMMIT` | `src/garc/confirm/commit.py`; called by `src/garc/controller/runner.py` | `src/garc_eval/psvr_runtime/runner.py::durable_json`; `src/garc_eval/psvr_runtime/runner.py::materialize_and_commit` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Restored transactional snapshot, file fsync, atomic replace, directory fsync, completed-action-only append, and final STOP/failure snapshot | exact final-snapshot parity, write-failure rollback, runner and CLI durable-result tests |
| `DEADLINE_ADMISSION` | `src/garc/controller/deadline.py`; `src/garc/controller/fixed_ratio.py` | `src/garc_eval/scan_confirm_controller/fixed_ratio.py`; `src/garc_eval/scan_confirm_controller/cost.py` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Restored exact finite/nonnegative fit and linear q90 with measured global fallback, then causal observations | 20 valid-domain admission comparisons, invalid-domain check, five quantiles and fallback/observed parity |
| `FIXED_RATIO_CONTROLLER` | `src/garc/controller/fixed_ratio.py`; config validation in `scripts/run_fixed_ratio_controller.py` | `src/garc_eval/scan_confirm_controller/fixed_ratio.py` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Present; 0.25/0.75 is accumulated completed actual wall-clock, never action count | 1,296 differential states plus explicit empty/nonempty, ratio-deficit, sole-fit and neither-fit cases |
| `END_TO_END_RUNNER` | `src/garc/controller/runner.py`; `scripts/run_fixed_ratio_controller.py` | `src/garc_eval/scan_confirm_controller/runner.py`; `src/garc_eval/psvr_runtime/runner.py` | `5047241b0561b911b9a519b18e8e7591c0074e70` | Complete for replay/dry-run; final result is durable; CLI rejects non-frozen config and modes that could imply a new Oracle | runner integration, failure atomicity, overrun/deadline, dedup, and CLI smoke tests |

## Import graph and CLI evidence

The runtime import path is `scripts/run_fixed_ratio_controller.py -> garc.controller.runner -> garc.scan + garc.controller.{candidate,deadline,fixed_ratio,frontier,state} + garc.confirm.{adapter,materialize,commit}`. No runtime file imports `/qiuyeqing/llama_prl/G-ARC`, `garc_eval`, an Oracle client, Myopic-VPS, Ratio-Anchored, Bandit, SMDP, RL, or YOLO scheduling code.

The required CLI shape is exercised by `tests/test_cli_smoke.py` using `mode: replay`; it writes both `summary.json` and a `durable_result.json` whose status is `FINAL` and whose final result equals the summary. `dry-run` and `replay` are the only accepted modes.

## Differential result

Within the enumerated frozen valid domains:

- Frontier admission parity: 100% of tested updates.
- Frontier candidate selection parity: 100% across 24 permutations and all sequential states.
- Fixed-ratio action parity: 100% across 1,296 states.
- Deadline admission parity: 100% across 20 valid cost/budget pairs; q90/fallback parity also passes.
- Materialization parity: 100% across tested positive, duplicate-ID, and negative outcomes.
- Durable-result parity: 100% across tested completed, final STOP, failure, and write-rollback cases.

These are implementation parity claims over checked cases, not claims of physical hard-deadline safety, Oracle correctness, semantic completeness, or cross-video generalization. The main remaining alternative explanation is that replay event IDs conceal physical K3 or Oracle failures; a physical adapter can reject that hypothesis only with separately authorized, measured physical trials.
