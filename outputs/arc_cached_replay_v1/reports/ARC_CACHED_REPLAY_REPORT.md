# ARC cached-replay baseline report

## Result and identity

`ARC-CACHED-REPLAY-v1` is fully executed on the selected frozen logical-call benchmark: 90 ARC runs and 90 current-method runs completed. This is an **algorithmic cached replay**. It is not a faithful native ARC reproduction and it is not a measured physical hard-deadline result.

The strongest supported descriptive conclusion is that ARC has lower macro F1 at every frozen budget; the comparison below records the exact differences. Scientific interpretation is weak because the benchmark contains only two independent source videos, the labels were already open before the adaptation, and two realcartest slices share a source video. Seeds were averaged within tasks and slices were averaged within source video before the two videos were treated as independent (`n=2`); inferential power is explicitly insufficient.

## Frozen inputs selected and why

The selected identity is the BSEC `native_arc_vs_pstr_v1` frozen replay, frozen 2026-07-13, with domains `dataset3_development, realcartest_0_1570, realcartest_2000_3200`, budgets `[5, 10, 20, 50, 80, 100]`, and seeds `[0, 1, 2, 3, 4]`. It was selected before inspecting new ARC outcomes because it is the discovered frozen artifact explicitly tied to the mandated historical ARC/PSTR runner and it supplies the same proxy, unit, frozen oracle, reference, logical-call budgets, sealed current-method selections, shared K3, and evaluator for both arms. A newer physical deadline benchmark was not substituted because cached ARC has no measured runtime with which to share its deadline grid.

Exact paths and SHA-256 values are in `DATA_PROVENANCE.json`. The benchmark manifest SHA-256 is `9d1b2a7201a2087e685899b8171805edadde38720d85da385d8059652e56f821`. Worktree and read-only-source copies of every selected frozen input matched.

Prompt/parser provenance is complete for `dataset3_development` (prompt `12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33`, parser `9a7413407d52df0484c0a338f0a12ae6b57553bdfa16753d7542f60977b558cb`) but is not recoverable from the frozen BSEC realcartest label tables for the two realcartest slices. Those slices retain source/reference hashes but not a prompt/parser hash. This is a genuine provenance limitation, not silently imputed metadata.

## ARC mapping and deviations

- One immutable frozen unit is one ARC record; the selected input tables define the unit timeline. Most records are 10 seconds. `dataset3_development` contains a preserved overlapping 5-second terminal unit (unit 346), which is disclosed rather than changed.
- Each proxy probability is mapped exactly to `[1-p, p]`; the fixed historical threshold is 0.4.
- Temporal clustering is the historical sequential SciPy Jensen-Shannon distance change-point rule with threshold 0.001. Frozen cluster assignments were recomputed and matched exactly.
- Native ARC `tau=1`; strict `k3_bridge_safe` (`g_max=1`, `d_core_max=40`, `d_seg_max=60`) alone materializes comparable events.
- ARC cluster propagation changes scheduling state and native candidate diagnostics only. Comparable predictions use only explicitly queried frozen-oracle-positive units.
- Indeterminate outcomes are charged, remain unknown, and are neither coerced nor propagated. The chosen frozen labels happen to contain only positive/negative outcomes.
- The selector cannot receive references, current-method selections, or a label array. The oracle accessor reveals only a selected unique unit.
- The result differs from native ARC in record semantics, proxy feature construction, categorical cached oracle, K3 endpoint, and absence of a physical shared clock. Native candidate intervals/confidence are stored separately and are not claimed to carry ARC's native guarantee.

The surviving historical helper hashes match the frozen manifest for pruning, refinement, and tools. The ignored instrumented ARC entry point used by the prior run (manifest SHA `53e920...`) is absent; the surviving `try_or_no` entry point hashes differently. Synthetic parity therefore compares against the surviving historical control loop with the NumPy-2 compatibility repair, while the missing exact entry point remains unresolved.

## Existing code reused and changes made

Reused without modification: historical ARC candidate, entropy, uncertainty, propagation, and boundary helpers under `try_or_no/arc_source/arc`; sealed PSTR selections; and the frozen `benchmark_lib.py` K3/evaluator (SHA `0a7a8ad4a13cc4404b0cfe7dfb1aef8958197267e22ff1df545ac4dbbf744610`).

New code adds a causal ARC state machine and frozen-oracle boundary, a CPU-only experiment/evaluation runner, and targeted contract tests. The only compatibility repair is in the wrapper: NumPy 2 no longer implicitly converts one-element arrays in historical confidence calculation, so the wrapper scalarizes them explicitly while preserving the old computation. Vendored ARC files, frozen inputs, references, prompts/parsers, and evaluator rules were not edited.

## Results

### Macro across source videos (seeds and within-video slices averaged first)

| method | budget | event_precision | event_recall | event_f1 | tiou_03 | tiou_05 | verified_positive_units | logical_oracle_calls | returned_event_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ARC-CACHED-REPLAY-v1 | 5 | 0.250 | 0.013 | 0.024 | 0.000 | 0.000 | 0.250 | 3.900 | 0.250 |
| ARC-CACHED-REPLAY-v1 | 10 | 0.350 | 0.024 | 0.044 | 0.005 | 0.000 | 0.500 | 7.650 | 0.500 |
| ARC-CACHED-REPLAY-v1 | 20 | 0.540 | 0.073 | 0.122 | 0.018 | 0.003 | 1.700 | 15.150 | 1.600 |
| ARC-CACHED-REPLAY-v1 | 50 | 0.727 | 0.184 | 0.268 | 0.049 | 0.026 | 5.500 | 37.650 | 4.300 |
| ARC-CACHED-REPLAY-v1 | 80 | 0.726 | 0.297 | 0.385 | 0.087 | 0.067 | 9.200 | 60.150 | 7.000 |
| ARC-CACHED-REPLAY-v1 | 100 | 0.730 | 0.361 | 0.442 | 0.098 | 0.088 | 11.200 | 74.250 | 8.450 |
| PSTR-5:4-FROZEN | 5 | 0.500 | 0.062 | 0.111 | 0.025 | 0.013 | 1.250 | 5.000 | 1.250 |
| PSTR-5:4-FROZEN | 10 | 0.500 | 0.087 | 0.149 | 0.038 | 0.013 | 1.750 | 10.000 | 1.750 |
| PSTR-5:4-FROZEN | 20 | 1.000 | 0.277 | 0.418 | 0.038 | 0.013 | 6.000 | 20.000 | 6.000 |
| PSTR-5:4-FROZEN | 50 | 0.806 | 0.415 | 0.515 | 0.087 | 0.050 | 12.250 | 50.000 | 11.500 |
| PSTR-5:4-FROZEN | 80 | 0.813 | 0.599 | 0.671 | 0.157 | 0.082 | 19.000 | 80.000 | 16.500 |
| PSTR-5:4-FROZEN | 100 | 0.887 | 0.662 | 0.728 | 0.194 | 0.144 | 23.750 | 100.000 | 16.500 |

### Paired macro F1 differences

| budget | arc_event_f1 | current_event_f1 | delta_arc_minus_current_event_f1 | f1_outcome |
| --- | --- | --- | --- | --- |
| 5 | 0.024 | 0.111 | -0.087 | ARC loses |
| 10 | 0.044 | 0.149 | -0.104 | ARC loses |
| 20 | 0.122 | 0.418 | -0.297 | ARC loses |
| 50 | 0.268 | 0.515 | -0.247 | ARC loses |
| 80 | 0.385 | 0.671 | -0.286 | ARC loses |
| 100 | 0.442 | 0.728 | -0.286 | ARC loses |

### Normalized AUC across the frozen budget grid

| method | event_f1_auc | event_precision_auc | event_recall_auc | tiou_03_auc | tiou_05_auc |
| --- | --- | --- | --- | --- | --- |
| ARC-CACHED-REPLAY-v1 | 0.262 | 0.645 | 0.192 | 0.053 | 0.036 |
| PSTR-5:4-FROZEN | 0.518 | 0.825 | 0.425 | 0.101 | 0.056 |

### Per source-video/query task

| domain | method | budget | event_f1 | event_precision | event_recall | verified_positive_units | logical_oracle_calls |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dataset3_development | ARC-CACHED-REPLAY-v1 | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 5.000 |
| dataset3_development | ARC-CACHED-REPLAY-v1 | 10 | 0.015 | 0.200 | 0.008 | 0.200 | 10.000 |
| dataset3_development | ARC-CACHED-REPLAY-v1 | 20 | 0.058 | 0.600 | 0.031 | 0.800 | 20.000 |
| dataset3_development | ARC-CACHED-REPLAY-v1 | 50 | 0.218 | 1.000 | 0.123 | 3.400 | 50.000 |
| dataset3_development | ARC-CACHED-REPLAY-v1 | 80 | 0.364 | 1.000 | 0.223 | 6.600 | 80.000 |
| dataset3_development | ARC-CACHED-REPLAY-v1 | 100 | 0.434 | 1.000 | 0.277 | 8.200 | 100.000 |
| realcartest_0_1570 | ARC-CACHED-REPLAY-v1 | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.600 |
| realcartest_0_1570 | ARC-CACHED-REPLAY-v1 | 10 | 0.000 | 0.000 | 0.000 | 0.000 | 0.600 |
| realcartest_0_1570 | ARC-CACHED-REPLAY-v1 | 20 | 0.000 | 0.000 | 0.000 | 0.000 | 0.600 |
| realcartest_0_1570 | ARC-CACHED-REPLAY-v1 | 50 | 0.000 | 0.000 | 0.000 | 0.000 | 0.600 |
| realcartest_0_1570 | ARC-CACHED-REPLAY-v1 | 80 | 0.000 | 0.000 | 0.000 | 0.000 | 0.600 |
| realcartest_0_1570 | ARC-CACHED-REPLAY-v1 | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.600 |
| realcartest_2000_3200 | ARC-CACHED-REPLAY-v1 | 5 | 0.095 | 1.000 | 0.050 | 1.000 | 5.000 |
| realcartest_2000_3200 | ARC-CACHED-REPLAY-v1 | 10 | 0.147 | 1.000 | 0.080 | 1.600 | 10.000 |
| realcartest_2000_3200 | ARC-CACHED-REPLAY-v1 | 20 | 0.370 | 0.960 | 0.230 | 5.200 | 20.000 |
| realcartest_2000_3200 | ARC-CACHED-REPLAY-v1 | 50 | 0.635 | 0.907 | 0.490 | 15.200 | 50.000 |
| realcartest_2000_3200 | ARC-CACHED-REPLAY-v1 | 80 | 0.811 | 0.905 | 0.740 | 23.600 | 80.000 |
| realcartest_2000_3200 | ARC-CACHED-REPLAY-v1 | 100 | 0.902 | 0.921 | 0.890 | 28.400 | 96.400 |
| dataset3_development | PSTR-5:4-FROZEN | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 5.000 |
| dataset3_development | PSTR-5:4-FROZEN | 10 | 0.000 | 0.000 | 0.000 | 0.000 | 10.000 |
| dataset3_development | PSTR-5:4-FROZEN | 20 | 0.267 | 1.000 | 0.154 | 4.000 | 20.000 |
| dataset3_development | PSTR-5:4-FROZEN | 50 | 0.364 | 0.857 | 0.231 | 7.000 | 50.000 |
| dataset3_development | PSTR-5:4-FROZEN | 80 | 0.564 | 0.846 | 0.423 | 13.000 | 80.000 |
| dataset3_development | PSTR-5:4-FROZEN | 100 | 0.579 | 0.917 | 0.423 | 15.000 | 100.000 |
| realcartest_0_1570 | PSTR-5:4-FROZEN | 5 | 0.182 | 1.000 | 0.100 | 2.000 | 5.000 |
| realcartest_0_1570 | PSTR-5:4-FROZEN | 10 | 0.261 | 1.000 | 0.150 | 3.000 | 10.000 |
| realcartest_0_1570 | PSTR-5:4-FROZEN | 20 | 0.519 | 1.000 | 0.350 | 7.000 | 20.000 |
| realcartest_0_1570 | PSTR-5:4-FROZEN | 50 | 0.684 | 0.722 | 0.650 | 19.000 | 50.000 |
| realcartest_0_1570 | PSTR-5:4-FROZEN | 80 | 0.683 | 0.667 | 0.700 | 26.000 | 80.000 |
| realcartest_0_1570 | PSTR-5:4-FROZEN | 100 | 0.780 | 0.762 | 0.800 | 33.000 | 100.000 |
| realcartest_2000_3200 | PSTR-5:4-FROZEN | 5 | 0.261 | 1.000 | 0.150 | 3.000 | 5.000 |
| realcartest_2000_3200 | PSTR-5:4-FROZEN | 10 | 0.333 | 1.000 | 0.200 | 4.000 | 10.000 |
| realcartest_2000_3200 | PSTR-5:4-FROZEN | 20 | 0.621 | 1.000 | 0.450 | 9.000 | 20.000 |
| realcartest_2000_3200 | PSTR-5:4-FROZEN | 50 | 0.647 | 0.786 | 0.550 | 16.000 | 50.000 |
| realcartest_2000_3200 | PSTR-5:4-FROZEN | 80 | 0.872 | 0.895 | 0.850 | 24.000 | 80.000 |
| realcartest_2000_3200 | PSTR-5:4-FROZEN | 100 | 0.976 | 0.952 | 1.000 | 32.000 | 100.000 |

`verified_event_yield` in CSV outputs is the number of strict returned verified events divided by logical oracle calls; `verified_event_count` and `returned_event_count` are also retained as counts. All metrics were recomputed from the newly persisted prediction CSVs, not copied from prior aggregate tables.

## Validation and execution accounting

Expected runs: 180 total (3 tasks × 5 seeds × 6 budgets × 2 methods). Completed: 180. Validation status: `PASS_WITH_DISCLOSED_LIMITATIONS`. Detailed checks, including hash binding, causality, deduplication, propagation exclusion, run completeness, alignment, and cluster parity, are in `validation_checks.json`.

Final test results: the targeted ARC suite passed 15/15, and the broader ARC/SMDP/deadline/durability command passed 74/74. Python compilation and `git diff --check` also passed. Two intermediate development attempts failed and were retained in `command_log.txt`: one collection error from omitting `PYTHONPATH=src`, then 6 failures/9 passes that exposed the NumPy-2 and immutable terminal-grid issues. Both were repaired and rerun. Skipped tests: 0 in the reported commands. Formatter/linter/type checks were unavailable because `ruff`, `mypy`, `black`, and `flake8` were not installed; they were not counted as passed. An independent post-run audit recomputed all required metrics from 180 persisted prediction files and found zero discrepancies after repairing a publication-path prefix defect. No GPU/model/network/physical action was executed.

## Scientific interpretation and limitations

The observed comparison is descriptive and post hoc. `n=2` independent source videos is insufficient for statistical claims or generalization. Five ARC seeds are stochastic repetitions, not five videos; the deterministic current method is repeated only to preserve pairing. Budget checkpoints are repeated measures, not independent samples. Both realcartest tasks are slices from the same video. References are VLM-defined pseudo-oracles, not human-adjudicated truth. Realcartest prompt/parser identities are missing from the selected frozen derivative. The dataset3 terminal grid exception can affect unit adjacency at the tail. The exact previously instrumented ARC entry point is unavailable. There is no measured proxy, model, decode, VERIFY, serialization, fsync, or wall-clock cost here, so no physical-deadline conclusion is supported.

The main competing explanation for any method difference is not an intrinsic ARC/PSTR advantage but interaction among the adapted 10-second record universe, frozen proxy, early ARC confidence termination, shared K3, and open-label benchmark construction. Rejection/revision trigger: a provenance-complete multi-video benchmark with independent prompt/parser-bound oracle observations and a true shared physical clock materially reverses the paired source-video results.

## Commands and artifacts

Exact material commands and their outcomes are in `command_log.txt`. Required artifacts are rooted at `outputs/arc_cached_replay_v1/`: `RUN_MANIFEST.json`, `DATA_PROVENANCE.json`, `CONFIG.json`, `per_run_metrics.csv`, `selection_traces/`, `predictions/`, `event_matches/`, `macro_curve.csv`, `macro_auc.csv`, `paired_comparison.csv`, and `validation_checks.json`.
