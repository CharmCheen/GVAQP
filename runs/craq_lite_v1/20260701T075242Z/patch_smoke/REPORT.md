# CRAQ-lite / CILS Inner Selector Evaluation V1

## Run Metadata

- Git commit: `04196b5c87b5f3d7551a761b6187cbe53ace4bb3`
- Main command: `python src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py --patch-smoke --run-dir runs/craq_lite_v1/20260701T075242Z/patch_smoke`
- Test command: `pytest -q src/garc_eval/tests/test_craq_lite_metrics.py`
- Syntax check command: `python -m py_compile src/garc_eval/metrics/craq_lite_metrics.py src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py`
- Environment: Python `3.10.20`, platform `Linux-5.15.0-60-generic-x86_64-with-glibc2.35`
- Run directory: `runs/craq_lite_v1/20260701T075242Z/patch_smoke`
- Grid mode: `patch-smoke`
- Exact rerun command: `python src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py --patch-smoke --run-dir runs/craq_lite_v1/20260701T075242Z/patch_smoke`

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
- `cils_craq_lite`: CRAQ-lite outer wrapper using clean v2 lattice and fixed CILS inner selector (`answer_quality_proxy_top + beta_bin_strata_lower`). Selector tau is set by `cils_taus`, NOT by `precision_target`.
- `lattice_oracle_upper_bound`: diagnostic oracle over the clean v2 candidate lattice.

## Metric Definitions

Metrics are implemented in `src/garc_eval/metrics/craq_lite_metrics.py` and tested in `src/garc_eval/tests/test_craq_lite_metrics.py`. Event recall hits a true interval event once if any returned interval reaches the IoU threshold. Precision uses existing clean v2 `answer_iou_0_3` interval labels. Duplicate rate is extra hit predictions per returned prediction. Duration inflation is returned duration divided by matched true-event duration, falling back to total true-event duration when no event is matched.

## Experiment Grid Actually Run

- Budgets: `[80, 160]`
- Precision targets (reporting only): `[0.8, 0.9]`
- CILS taus (selector threshold): `[0.5, 0.6, 0.7]`
- IoU thresholds: `[0.3, 0.5]`
- Seeds: `[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]`

## Results

| method | budget | precision_target | cils_tau | iou_threshold | mean_event_recall | std_event_recall | mean_precision | mean_expected_precision | mean_returned_interval_count | mean_duration_inflation | mean_duplicate_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lattice_oracle_upper_bound | 80 | 0.8 | nan | 0.3 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 80 | 0.8 | nan | 0.5 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 80 | 0.9 | nan | 0.3 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 80 | 0.9 | nan | 0.5 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 160 | 0.8 | nan | 0.3 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 160 | 0.8 | nan | 0.5 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 160 | 0.9 | nan | 0.3 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| lattice_oracle_upper_bound | 160 | 0.9 | nan | 0.5 | 1 | 0 | 1 | nan | 6 | 0.901771 | 0 |
| audited_proposal_repair | 80 | 0.8 | nan | 0.3 | 1 | 0 | 0.175305 | nan | 40.5 | 5.17713 | 0.0271341 |
| audited_proposal_repair | 80 | 0.9 | nan | 0.3 | 1 | 0 | 0.175305 | nan | 40.5 | 5.17713 | 0.0271341 |
| audited_proposal_repair | 160 | 0.8 | nan | 0.3 | 1 | 0 | 0.0875 | nan | 80 | 9.50081 | 0.0125 |
| audited_proposal_repair | 160 | 0.9 | nan | 0.3 | 1 | 0 | 0.0875 | nan | 80 | 9.50081 | 0.0125 |
| audited_proposal_repair | 80 | 0.8 | nan | 0.5 | 0.683333 | 0.0512989 | 0.175305 | nan | 40.5 | 6.79956 | 0 |
| audited_proposal_repair | 80 | 0.9 | nan | 0.5 | 0.683333 | 0.0512989 | 0.175305 | nan | 40.5 | 6.79956 | 0 |
| audited_proposal_repair | 160 | 0.8 | nan | 0.5 | 0.666667 | 0 | 0.0875 | nan | 80 | 12.7155 | 0 |
| audited_proposal_repair | 160 | 0.9 | nan | 0.5 | 0.666667 | 0 | 0.0875 | nan | 80 | 12.7155 | 0 |
| cils_craq_lite | 80 | 0.8 | 0.5 | 0.3 | 0.5 | 0 | 0.2 | 0.518742 | 20 | 4.99307 | 0.05 |
| cils_craq_lite | 80 | 0.9 | 0.5 | 0.3 | 0.5 | 0 | 0.2 | 0.518742 | 20 | 4.99307 | 0.05 |
| cils_craq_lite | 80 | 0.8 | 0.6 | 0.3 | 0.5 | 0 | 0.16 | 0.626952 | 25 | 4.93759 | 0.04 |
| cils_craq_lite | 80 | 0.9 | 0.6 | 0.3 | 0.5 | 0 | 0.16 | 0.626952 | 25 | 4.93759 | 0.04 |
| oracle_confirmed_only | 160 | 0.8 | nan | 0.3 | 0.333333 | 0 | 1 | nan | 17 | 4.91857 | 0.882353 |
| oracle_confirmed_only | 160 | 0.9 | nan | 0.3 | 0.333333 | 0 | 1 | nan | 17 | 4.91857 | 0.882353 |
| cils_craq_lite | 80 | 0.8 | 0.5 | 0.5 | 0.333333 | 0 | 0.2 | 0.518742 | 20 | 16.8224 | 0 |
| cils_craq_lite | 80 | 0.9 | 0.5 | 0.5 | 0.333333 | 0 | 0.2 | 0.518742 | 20 | 16.8224 | 0 |
| cils_craq_lite | 80 | 0.8 | 0.6 | 0.5 | 0.333333 | 0 | 0.16 | 0.626952 | 25 | 16.6355 | 0 |


### CILS by tau (IoU@0.3)

| cils_tau | mean_returned_interval_count | mean_event_recall | mean_precision | empty_return_rate |
| --- | --- | --- | --- | --- |
| 0.5 | 10 | 0.25 | 0.2 | 0.5 |
| 0.6 | 12.5 | 0.25 | 0.16 | 0.5 |
| 0.7 | 0 | 0 | nan | 1 |


## Patch-Smoke Diagnostic Q&A

- Was precision_target fully decoupled from cils_tau? **YES**. `cils_select` receives `tau` from the `cils_taus` axis; `precision_target` is only a reporting/filter label.
- What cils_tau values actually ran? `[0.5, 0.6, 0.7]`
- Was the single overlap_group_id issue fixed? **YES**. NMS and `cils_select` no longer skip by `overlap_group_id`; selection uses IoU > 0.3 only.
- Can CILS now return more than one interval when candidates permit it? **YES** (max mean returned count = `25.00`).
- Does CILS at tau=0.5/0.6 reproduce non-empty behavior? **YES** (tau=0.5 nonempty: True, tau=0.6 nonempty: True).
- Does any CILS setting achieve observed precision >= 0.8 with nonzero recall? **NO** (best recall = `0.000`).
- Does any CILS setting achieve observed precision >= 0.9 with nonzero recall? **NO** (best recall = `0.000`).
- Does audited_proposal_repair still return zero recall after the group-id/NMS fix? **YES (still zero at precision>=0.8)** (best repair recall @ precision>=0.8 = `0.000`; repair recall ignoring precision = `1.000`).
- Is the selector gate still failed, passed, or inconclusive? **INCONCLUSIVE (reference gate failed, diagnostic only)**.

### Prediction counts

- `predictions_cils_craq_lite.csv` rows: `1800`

## Plots



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
