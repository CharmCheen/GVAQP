# Probe Set v1 Runtime Read-Only Eval Final Report

Date: 2026-07-03

## Scope

This is a read-only overlap audit of the frozen `query_runtime_v1` output against `probe_set_v1`. It does not tune thresholds, score columns, NMS gaps, budgets, repair decisions, or selector choices.

All metrics in this report are labeled `probe_set_v1_vlm_oracle_reference`; these are VLM oracle judgments, not human ground truth.

## Results

- Runtime intervals: `40`.
- Probe windows: `25`; positives `probe_set_v1_vlm_oracle_reference`: `7`.
- Covered probe windows: `5`.
- Covered positive probe windows: `2`.
- Covered negative probe windows: `3`.
- Covered-probe precision `probe_set_v1_vlm_oracle_reference`: 0.400.
- Positive probe-window recall `probe_set_v1_vlm_oracle_reference`: 0.286.

## Interpretation

The runtime output overlaps only part of the independent probe grid, so this is a weak compatibility signal, not a promotion criterion. The selector configuration remains the pre-registered `query_runtime_v1` setting.

## Sanity Checks

| Check | Status | Details |
|---|---|---|
| probe_labels_not_used_for_selector_config | PASS | Runtime output was generated in outputs/query_runtime_v1 before this read-only audit. |
| all_probe_rows_mark_do_not_use_for_tuning | PASS | Checked probe_set_manifest.csv do_not_use_for_tuning column. |
| probe_labels_parse_ok | PASS | Parsed 25 labels for 25 probes. |
| time_axis_scope_warning | WARN | Probe media uses fallback_dataset3_with_reference_absolute_offset; overlap is a compatibility audit, not a tuning or full-video evaluation. |

## Files

- `tables/probe_overlap_matches.csv`
- `tables/probe_readonly_summary.csv`
- `tables/sanity_checks.csv`
- `figures/runtime_vs_probe_windows.svg`

FINAL_DECISION: WEAK GO
