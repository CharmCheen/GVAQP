# Limited-Oracle Retrieval Frontier against Full-VLM Evaluation Reference

This directory evaluates B6 / B7 / B6-core / B7-core / LATE-AQP-core under a strict limited-oracle replay, where the algorithm may consume at most B oracle calls and the full-VLM reference `O_full` is used only for final evaluation.

## Key principle

- **Runtime**: methods request units/intervals through an `oracle_adapter`. Each request consumes one oracle call.
- **Evaluation**: after the method returns, the evaluator compares returned segments against `O_full`.
- `O_full` labels, event IDs, and event intervals are **not** available to the method during selection.

## Files

- `commands.sh` — reproduction command.
- `input_manifest.csv` — inputs consumed.
- `full_vlm_reference_discovery_report.md` — available full-VLM evaluation references.
- `oracle_replay_isolation_audit.md` — label-isolation audit (strict_replay vs posthoc_eval).
- `oracle_adapter_spec.md` — runtime oracle adapter specification.
- `method_inventory.md` — methods and their oracle usage.
- `budget_grid.md` — per-segment budget grid and ratios.
- `limited_oracle_frontier_raw.csv` — raw per-seed results.
- `precision_recall_frontier.csv` — aggregated precision-recall frontier.
- `b90_90_by_segment.csv` — per-segment B_90/90.
- `budget_ratio_summary.csv` — budget-ratio summary.
- `method_comparison_macro_micro.csv` — macro/micro comparison.
- `failure_taxonomy.csv` — failure taxonomy for non-reaching cases.
- `oracle_usage_report.md` — oracle call composition and guard overhead.
- `FINAL_REPORT.md` — answers to the 12 required questions.

## Methodological notes

- No new GPU/VLM/API calls were made.
- No new labels were generated.
- The full-VLM reference already exists in `center10_vlm_oracle_events.csv` (non-dev segments) and `reference_events.csv` (dev segment).
- B6/B7 use per-bin `event_id` internally for their adaptive chunk counting; this is flagged as a label-leakage risk and their results are classified as `posthoc_eval`.
- LATE-AQP-core selection uses only per-bin labels (positive/negative) and prior scores, so it is classified as `strict_replay`.
