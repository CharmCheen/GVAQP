# CRAQ-lite / CILS Inner Selector Evaluation V1

## Run Metadata

- Git commit: `04196b5c87b5f3d7551a761b6187cbe53ace4bb3`
- Main command: `python src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py --smoke --run-dir runs/craq_lite_v1/20260701T074755Z`
- Test command: `pytest -q src/garc_eval/tests/test_craq_lite_metrics.py`
- Syntax check command: `python -m py_compile src/garc_eval/metrics/craq_lite_metrics.py src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py`
- Environment: Python `3.10.20`, platform `Linux-5.15.0-60-generic-x86_64-with-glibc2.35`
- Run directory: `runs/craq_lite_v1/20260701T074755Z`
- Grid mode: `smoke-scale`
- Exact rerun command: `python src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py --smoke --run-dir runs/craq_lite_v1/20260701T074755Z`

## Repository Structure

See `repo_inventory.md`.

## Reference Audit

See `reference_audit.csv` and `reference_audit_summary.md`.

- True interval events: `6`
- Reference gate passed: **no**
- Conclusion status: **diagnostic only**

## Method Descriptions

- `fixed_window_topk`: clean v2 fixed-window candidates ranked by cheap active score with temporal NMS.
- `threshold_merge`: clean v2 threshold-merge candidates ranked by cheap active score with temporal NMS.
- `arc_style_prune_refine`: closest clean v2 ARC-style proxy using signal-peak, threshold-merge, and boundary-refined proposals ranked by fixed answer-quality proxy.
- `oracle_confirmed_only`: top active-score candidates directly filtered by existing oracle replay labels; conservative lower-bound baseline.
- `audited_proposal_repair`: starts from ARC-style candidates, audits candidate-external 2s locations with fixed seed, repairs positives by local nearest clean lattice intervals, and counts audit calls in `oracle_budget_trace.csv`.
- `cils_craq_lite`: CRAQ-lite outer wrapper using clean v2 lattice and fixed CILS inner selector (`answer_quality_proxy_top + beta_bin_strata_lower`).
- `lattice_oracle_upper_bound`: diagnostic oracle over the clean v2 candidate lattice.

## Metric Definitions

Metrics are implemented in `src/garc_eval/metrics/craq_lite_metrics.py` and tested in `src/garc_eval/tests/test_craq_lite_metrics.py`. Event recall hits a true interval event once if any returned interval reaches the IoU threshold. Precision uses existing clean v2 `answer_iou_0_3` interval labels. Duplicate rate is extra hit predictions per returned prediction. Duration inflation is returned duration divided by matched true-event duration, falling back to total true-event duration when no event is matched.

## Experiment Grid Actually Run

- Budgets: `[20, 40, 80]`
- Precision targets: `[0.8, 0.9]`
- IoU thresholds: `[0.3, 0.5]`
- Seeds: `[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]`

## Results

| method | budget | precision_target | iou_threshold | mean_event_recall | std_event_recall | mean_precision | mean_expected_precision | mean_returned_interval_count | mean_duration_inflation | mean_duplicate_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lattice_oracle_upper_bound | 20 | 0.8 | 0.3 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 20 | 0.8 | 0.5 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 20 | 0.9 | 0.3 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 20 | 0.9 | 0.5 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 40 | 0.8 | 0.3 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 40 | 0.8 | 0.5 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 40 | 0.9 | 0.3 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 40 | 0.9 | 0.5 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 80 | 0.8 | 0.3 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 80 | 0.8 | 0.5 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 80 | 0.9 | 0.3 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 80 | 0.9 | 0.5 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| oracle_confirmed_only | 40 | 0.8 | 0.3 | 0.166667 | 0 | 1 | nan | 2 | 1.49533 | 0.5 |
| oracle_confirmed_only | 40 | 0.8 | 0.5 | 0.166667 | 0 | 1 | nan | 2 | 1.49533 | 0 |
| oracle_confirmed_only | 40 | 0.9 | 0.3 | 0.166667 | 0 | 1 | nan | 2 | 1.49533 | 0.5 |
| oracle_confirmed_only | 40 | 0.9 | 0.5 | 0.166667 | 0 | 1 | nan | 2 | 1.49533 | 0 |
| oracle_confirmed_only | 80 | 0.8 | 0.3 | 0.166667 | 0 | 1 | nan | 8 | 9.15888 | 0.875 |
| oracle_confirmed_only | 80 | 0.8 | 0.5 | 0.166667 | 0 | 1 | nan | 8 | 9.15888 | 0.25 |
| oracle_confirmed_only | 80 | 0.9 | 0.3 | 0.166667 | 0 | 1 | nan | 8 | 9.15888 | 0.875 |
| oracle_confirmed_only | 80 | 0.9 | 0.5 | 0.166667 | 0 | 1 | nan | 8 | 9.15888 | 0.25 |
| arc_style_prune_refine | 20 | 0.8 | 0.3 | 0 | 0 | 0 | nan | 1 | 0.257649 | 0 |
| arc_style_prune_refine | 20 | 0.8 | 0.5 | 0 | 0 | 0 | nan | 1 | 0.257649 | 0 |
| arc_style_prune_refine | 20 | 0.9 | 0.3 | 0 | 0 | 0 | nan | 1 | 0.257649 | 0 |
| arc_style_prune_refine | 20 | 0.9 | 0.5 | 0 | 0 | 0 | nan | 1 | 0.257649 | 0 |
| arc_style_prune_refine | 40 | 0.8 | 0.3 | 0 | 0 | 0 | nan | 1 | 0.257649 | 0 |

## Plots

- `plots/budget_vs_duration_inflation.png`
- `plots/budget_vs_recall_precision_0_8.png`
- `plots/budget_vs_recall_precision_0_9.png`
- `plots/proposal_recall_by_method.png`
- `plots/upper_bound_vs_actual_recall.png`

## Gate Outcomes

- Gate 1 reference gate: **FAIL**. `6` true interval events; conclusions are diagnostic only when this is below 20.
- Gate 2 proposal gate: **PASS**. Lattice oracle upper bound IoU@0.3 max = `1.000`.
- Gate 3 selector gate: **FAIL**. Best CILS recall at precision >= 0.8 = `0.000`; best audited repair recall at precision >= 0.8 = `0.000`.

## Preferred Interpretation

Current result **does not support** the claim:

> "CILS as a CRAQ-lite inner selector improves event recall under a precision constraint, compared with audited proposal repair, without materially increasing returned duration."

Evidence:
- Best CILS recall: `0.000`.
- Best audited proposal repair recall: `0.000`.
- Reference size: `6` true interval events, so this run is **diagnostic only**.

Bottleneck diagnosis:
- Reference size is the dominant validity bottleneck when true interval events < 20.
- Candidate coverage is not the primary bottleneck if lattice upper bound remains high.
- Selector/calibration still has weak recall at high precision targets in this small reference.

## Limitations

- Uses VLM-defined pseudo-oracle labels, not human truth.
- Audited proposal repair is a fixed diagnostic wrapper over existing labels, not a tuned production algorithm.
- No strong event-level guarantee is claimed.

## Next Recommended Action

Build or acquire a larger true-interval reference (>=20 interval events) and rerun this exact wrapper before making any CILS-vs-repair claim.
