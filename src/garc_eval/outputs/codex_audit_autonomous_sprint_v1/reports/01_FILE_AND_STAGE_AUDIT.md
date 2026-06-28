# 01 File And Stage Audit

## Verdict

GLM produced a real output tree at `garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1`, but the user-specified `autonomous_sprint_v1` path is a naming drift. The most trustworthy artifacts are the full parsed oracle CSV, per-anchor JSON files, proxy feature table, cluster/temporal CSVs, and `budget_replay_results.csv`.

## Stage Completion

- Stage 1 boundary smoke: executed, 31 table rows. Scheme C was incomplete due to timeout; final decision relies mainly on Schemes A/B.
- Stage 2 full center10 oracle: executed as 297 new per-anchor JSON files plus 50 reused P1 rows, merged into 347 anchors.
- Stage 3 proxy-oracle analysis: executed from existing labels/features.
- Stage 4 temporal/cluster analysis: executed, but final report text has a singleton/multi-cluster inconsistency.
- Stage 5 budget replay: executed as `budget_replay_results.csv` with 10 methods x 8 budgets. `method_by_budget_summary.csv` was not generated.
- Stage 6 algorithm exploration: design-only. DCA was proposed, not replay-validated.
- Stage 7 related work matrix: generated.
- Stage 8 dataset2 role: generated from P0 scout, no new VLM.
- Stage 9 paper-style report: generated.

## Unsupported Or Risky Completion Claims

- DCA is marked as main algorithm in state/design files, but no DCA method appears in `budget_replay_results.csv`.
- `cluster_aware_selection` is an oracle-informed upper bound, not a deployable method.
- Audit/certificate is not implemented; it appears only as next action/design language.
- Final report says 18 singleton / 9 multi-anchor clusters; recomputation gives 21 / 6.
- Stage 3 proxy AUROC numbers are materially wrong: GLM reports score-fusion around 0.624 and `object_count_mean` around 0.052, but tie-aware recomputation gives 0.550 and 0.627.
- `method_by_budget_summary.csv` is named in the user task but absent.

## Most Credible Output Files

See `tables/key_file_index.csv`. Highest-confidence files: full oracle parsed CSV, 297 new raw JSONs, P1 parsed CSV, proxy features, temporal/cluster CSVs, budget replay CSV, stage scripts, and logs/failure log.
