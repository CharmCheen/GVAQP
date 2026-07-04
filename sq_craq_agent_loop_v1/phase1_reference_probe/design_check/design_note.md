# Probe Set v1 Pre-Annotation Design Check

Date: 2026-07-03

## Scope

This document is a pre-annotation design check for `probe_set_v1`. It does not contain probe labels and does not report frozen-evaluation metrics. No GPU, VLM, API, YOLO, selector replay, threshold tuning, or manifest regeneration was run.

Hard boundary: the design estimates below may be used only to shape the annotation form and to pre-register the frozen-evaluation reporting plan after human labels exist. They must not be used to choose which probes to annotate, select features, choose thresholds, train models, alter candidate generation, or change the selector.

## Input Sheet Check

Input: `outputs/probe_set_v1/probe_set_review_sheet.csv`

- Rows: 25
- Unique `probe_id`: 25
- Required locator fields present: `probe_id`, `clip_path`, `center_frame_path`, `sheet_path`
- Required locator fields non-empty for all rows: yes
- Existing human-label fields in source sheet: present but empty

Decision: field coverage is sufficient. The human label template was created by extending this existing review sheet rather than regenerating a parallel probe locator table.

Output template: `outputs/probe_set_v1/probe_set_human_labels_template.csv`

## Design-Only Cheap-Signal Score Pass

Inputs used for this design estimate:

- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/cheap_signals_per_unit.csv`
- `outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv`
- `outputs/cheap_signal_v2/probe_feature_coverage_audit.csv`
- `outputs/cheap_signal_v2/signal_upgrade_within_bin_metrics.csv` only for the previously recorded six-event diagnostic prevalence, not for probe labels

Feature coverage over the 25 probes:

- Full current cheap-signal coverage: 20 probes
- No current cheap-signal coverage: 5 probes
- Covered probe seconds: 200.0
- Total probe seconds: 250.0

The table below is a design-only ranking summary over covered probes. It is not a prediction label and is not included in the annotation template.

| probe_id | coverage_status | design_rank | design_composite_score | cheap_fused_score_weighted_mean | primary_signal_score_weighted_mean | interval_active_score_max |
| --- | --- | --- | --- | --- | --- | --- |
| probe_set_v1_0015 | full | 1.000 | 1.370 | 0.368 | 0.627 | 1.000 |
| probe_set_v1_0001 | full | 2.000 | 0.873 | 0.258 | 0.121 | 1.000 |
| probe_set_v1_0018 | full | 3.000 | 0.851 | 0.378 | 0.445 | 1.000 |
| probe_set_v1_0013 | full | 4.000 | 0.762 | 0.262 | 0.234 | 1.000 |
| probe_set_v1_0016 | full | 5.000 | 0.372 | 0.179 | 0.185 | 1.000 |
| probe_set_v1_0014 | full | 6.000 | 0.313 | 0.238 | 0.349 | 1.000 |
| probe_set_v1_0012 | full | 7.000 | 0.253 | 0.279 | 0.562 | 1.000 |
| probe_set_v1_0010 | full | 8.000 | 0.154 | 0.204 | 0.201 | 1.000 |
| probe_set_v1_0020 | full | 9.000 | 0.122 | 0.175 | 0.155 | 1.000 |
| probe_set_v1_0003 | full | 10.000 | 0.115 | 0.257 | 0.198 | 1.000 |

## Expected Positive Count Design Estimate

This is a rough design estimate, not a validation result.

Two intentionally simple anchors were used:

- Exposure anchor: six reference events over the current 1200s cheap-signal feature window, scaled to 200s of feature-covered probe time, gives about 1.00 expected positives.
- Liberal signal-enriched anchor: the existing six-event top-bin diagnostic prevalence is 16/87 = 0.184; applying that to all 25 time-grid probes gives about 4.60 positives. This is an upper-style design anchor because `probe_set_v1` is an independent time grid, not a top-bin-selected set.

Pre-registered design estimate for the 25-probe annotation set: **about 1-6 positive probes**.

All 25 probes must still be manually annotated. No probe may be skipped because of feature coverage, score, rank, or expected label.

## Frozen-Evaluation Reporting Rule

The pre-annotation positive-count estimate is only about 1-6 positives among 25 probes. Under this regime, `precision@5` and `precision@10` can both be capped by the theoretical maximum `min(k, n_positive) / k`. For example, if only one true positive exists, the maximum possible `precision@5` is 0.20 and the maximum possible `precision@10` is 0.10 even for a perfect ranking. This makes precision@k weak for comparing signals in `probe_set_v1`.

Therefore, `precision@5`, `precision@10`, and `precision@20` are downgraded to reference-only auxiliary columns. They must not be used as the main basis for claims that one signal is better than another on `probe_set_v1`.

The primary frozen-evaluation readouts for `probe_set_v1` should be case-level ranking evidence:

- `rank_of_each_positive`: for every probe manually labeled as `true_interval` or `point_anchor`, report its rank from 1 to 25 under each signal score.
- `hit@5`: for each positive probe and each signal, report whether that positive probe falls in the top 5.
- `hit@10`: for each positive probe and each signal, report whether that positive probe falls in the top 10.
- If the final positive count is at least 5, additionally report Mann-Whitney AUC with a clear warning that the 95% confidence interval will be wide at this sample size and that AUC is only a rough reference.
- If the final positive count is below 3, do not compute AUC; report only `rank_of_each_positive` and `hit@5` / `hit@10`.

If the final positive count is 3-4, `rank_of_each_positive` and `hit@5` / `hit@10` remain the pre-registered primary readouts; AUC is not a required result and should not be used as a main conclusion.

`probe_set_v1` at its current scale can provide case-level evidence about which situations each signal catches or misses. It is not powered to support statistical conclusions such as "signal X is significantly better than signal Y." Any final report making a signal-comparison claim must first check whether the `probe_set_v2` expansion plan has been executed and whether the expanded labels support that claim.

Future frozen evaluation must report point estimates and 95% percentile-bootstrap confidence intervals for all reported metrics. This design note itself intentionally reports no frozen-evaluation metric.

## VLM Oracle Reference Update

Date: 2026-07-03

The `probe_set_v1` reference source was switched from pending human labels to local Qwen3-VL-32B oracle labels. The output file is:

`outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`

Reference-source label: `probe_set_v1_vlm_oracle_reference`.

These labels are VLM oracle judgments, not human ground truth. Downstream reports must not call metrics from this file "true recall" or "ground truth recall"; use wording such as "relative to VLM oracle judgment."

Observed VLM oracle label counts:

- `true_interval`: 6
- `point_anchor`: 1
- `negative`: 18
- `uncertain`: 0
- Parse status: 25/25 `ok`
- Oracle-positive definition for probe evaluation: `true_interval` + `point_anchor` = 7/25

Metric-selection update from actual VLM oracle positives:

- `rank_of_each_positive` remains the primary case-level readout.
- `hit@5` and `hit@10` remain primary case-level readouts.
- `precision@5` and `precision@10` may be reported as auxiliary aggregate summaries, with point estimate and 95% percentile-bootstrap CI if reported. They should not be used alone for signal-superiority claims.
- `precision@20` remains reference-only because the theoretical maximum is `min(20, 7) / 20 = 0.35`, so it is strongly capped by the number of oracle positives.
- Mann-Whitney AUC may be reported as a rough reference because the VLM oracle positive count is at least 5, but its 95% bootstrap CI should be expected to be wide at 7 positives and 18 negatives.
- If human spotcheck later reveals material disagreement with the VLM labels, this section must be revisited before frozen evaluation.

## Frozen Boundary

The current `probe_set_v1` frozen reference is `outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`, with source label `probe_set_v1_vlm_oracle_reference`. It is evaluation-only and must not be used for tuning, threshold selection, feature choice, model training, selector changes, repair decisions, or candidate generation.

The human spotcheck file `outputs/probe_set_v1/vlm_human_agreement_spotcheck.csv` is for auditing VLM agreement. It should not be used to tune the selector or rewrite probe candidates.
