# Core/Halo Attribution Analysis for LATE-AQP

This directory contains offline attribution diagnostics for the Core/Halo precision-constrained release introduced in `outputs/late_aqp_core_halo_frontier/`.

## Key questions

1. Is the Core/Halo gain specific to LATE-AQP, or is it a generic post-processing gain that also helps B6/B7?
2. On the hardest segment (`realcartest_0_1570`), is the remaining recall gap caused by an over-conservative release or by upstream discovery misses?
3. How efficient are boundary guards, and is their budget overhead acceptable?

## Files

- `commands.sh` — command used to generate all outputs.
- `input_manifest.csv` — list of inputs consumed.
- `b6_b7_core_diagnostic_results.csv` — B6/B7/B6-core/B7-core/LATE-AQP-core raw per-seed results.
- `core_halo_attribution_summary.md` — B_90/90 comparison and answers to diagnostic questions 1-4.
- `hardest_segment_miss_analysis.csv` / `hardest_segment_casebook.md` — per-event miss reasons for `realcartest_0_1570`.
- `guard_efficiency_report.md` — guard call statistics.
- `core_halo_tradeoff.csv` — release-variant tradeoff curves.
- `final_recommendation.md` — single primary conclusion (A-E) with supporting evidence.

## Methodological notes

- No GPU/VLM/oracle calls were used.
- No changes were made to discovery, repair, prior signals, or the 90/90 threshold.
- B6-core and B7-core apply the same boundary-guard rule as LATE-AQP-core, with guard calls counted inside the same total budget.
