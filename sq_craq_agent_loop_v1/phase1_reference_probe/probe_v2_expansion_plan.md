# probe_set_v2 Expansion Plan

Date: 2026-07-03

## Status

Design only. This document does not execute sampling, create media, create labels, modify `probe_set_v1`, or modify any probe manifest. No GPU, VLM, API, YOLO, or selector replay is required for this planning step.

## Goal

`probe_set_v1` has only 25 probes and the pre-annotation design estimate is about 1-6 positives. That scale is useful for case-level inspection but weak for comparing cheap-signal families. `probe_set_v2` should be a larger, independent candidate set designed to increase the number of labeled positives while preserving score-range diversity and avoiding any use of ground truth labels.

Recommended target size: 80 probes.

Acceptable smaller target if annotation budget is tight: 50-60 probes.

## Non-Negotiable Constraints

- Do not use `probe_set_v1` human labels, `6_event_reference` labels, expanded-reference labels, or any other ground truth to select rows.
- Do not select candidates because a human thinks they are likely positives.
- Do not tune thresholds, features, or selector logic from labels.
- Cheap-signal scores may be used only to stratify the candidate pool across score ranges.
- All sampling logic must be fixed before labels exist and logged with a random seed.

## Candidate Universe

Use existing no-new-compute cheap-signal interval candidates from:

- `outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv`

Eligibility rules for a future execution:

- Candidate must have valid `interval_id`, `t_start`, `t_end`, and score fields.
- Candidate duration should be clipped or represented as a reviewable 10s media window centered on the interval center, unless a later execution plan explicitly chooses a different fixed review duration.
- Candidate media must be exportable from existing local video sources.
- Candidate should not duplicate an existing `probe_set_v1` review window. A future executor should remove candidates whose proposed review window overlaps a `probe_set_v1` window by more than 50% of the shorter window.
- Candidate overlap within `probe_set_v2` should be controlled: after sorting a stratum by random key, accept a candidate only if its proposed review window overlaps already accepted `probe_set_v2` windows by no more than 50% of the shorter window.

## Stratification Rule

Build a design-only composite score from existing cheap-signal columns before any labels are read. One acceptable default is an equal-weight z-score average of:

- `cheap_fused_score`
- `primary_score`
- `active_score`
- `motion_energy_mean`
- `signal_disagreement`

If a future executor chooses different score columns because of missing fields, that choice must be documented before sampling and must not use labels.

Sampling rule for the recommended 80-probe design:

1. Compute the composite score for every eligible candidate.
2. Split candidates into 10 decile strata by composite score, from lowest to highest.
3. Within each decile, assign a deterministic pseudorandom key using a fixed seed, for example `probe_set_v2_seed=20260703`.
4. Sample 8 candidates per decile after applying the overlap-control rule.
5. If a decile has fewer than 8 eligible non-overlapping candidates, take all available candidates from that decile and redistribute the remainder evenly across adjacent deciles, preserving the fixed random key order.

Alternative 60-probe design:

- Sample 6 candidates per decile with the same rules.

Alternative 50-probe design:

- Sample 5 candidates per decile with the same rules.

This decile design deliberately includes low, middle, and high cheap-signal ranges. The strata are for coverage of score regimes, not for predicting which candidates are positives or inflating the positive rate by selecting only high-score rows.

## Expected Positive Count

This is a planning estimate only, not a validation result.

`probe_set_v1` was an equal-time grid with an estimated 1-6 positives in 25 probes. A larger stratified set should increase the number of positives mainly by increasing annotation volume and by ensuring representation from high-score strata, while still retaining middle and low score ranges.

Rough expected positive-count scale:

- 50 probes: about 3-10 positives
- 60 probes: about 4-12 positives
- 80 probes: about 5-16 positives

The range is intentionally wide. The purpose of `probe_set_v2` is to improve case coverage and power after annotation, not to guarantee a fixed positive rate.

## Relationship To probe_set_v1

`probe_set_v2` should be a parallel extension, not a replacement for `probe_set_v1`.

- `probe_set_v1` remains a frozen independent probe set and should keep its own reports.
- `probe_set_v2` should be reported separately at first.
- Combined reports may be added later only if the sampling rules, label schema, and evaluation plan are documented clearly and no labels were used to alter either set.
- The recommended default is to exclude overlapping `probe_set_v1` windows from `probe_set_v2` so the extension adds new case coverage rather than duplicating the first probe set.

## Annotation Workload Estimate

Assuming each probe is a 10s clip with a center frame and contact sheet:

- 50 probes: about 1.5-3 reviewer hours
- 60 probes: about 2-4 reviewer hours
- 80 probes: about 3-5 reviewer hours

The estimate includes opening media, assigning `label`, and writing concise `visible_evidence`. Hard or ambiguous cases may increase this time.

## Evaluation Planning Impact

Until `probe_set_v2` is executed and labeled, `probe_set_v1` should be treated as case-level evidence only. Stronger signal-comparison claims should wait for the expanded set or another larger frozen reference.

For `probe_set_v2`, the evaluation plan should be pre-registered before labels are read. It can include rank/hit readouts and, if enough positives are observed, AUC with percentile-bootstrap confidence intervals by probe.

## Queue Decision

This plan is ready for a future decision point. Do not execute sampling or media export in the current round.
