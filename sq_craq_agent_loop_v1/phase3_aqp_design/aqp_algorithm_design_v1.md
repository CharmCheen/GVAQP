# AQP Algorithm Design v1

## Scope

This document puts the certificate/guarantee line aside and describes only the
algorithmic AQP object: given a video-derived candidate universe and a budget
`B`, return a constrained set of intervals.

The current implemented loop is:

1. Build or load an interval lattice.
2. Compute cheap selector scores for each candidate interval.
3. Select a budgeted return set with overlap control.
4. Evaluate returned intervals against an explicit reference source.

## Converged Design

### Candidate Layer

The design has converged from a single change-point proposal set to an interval
lattice:

- fixed windows;
- dense multiscale windows;
- signal peak multiscale windows;
- threshold-merge intervals;
- low-density blind-spot proposals;
- boundary-refined expansions.

The implemented artifact used by the Phase 3 smoke is:

- `outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv`

This is a candidate lattice plus cheap features. It is not a learned model and
does not require a new detector run.

### Selector Layer

The selector is the part that maps each interval to an ordering score. The
current AQP v1 selector family is deliberately simple:

- `uniform_random`: budget baseline;
- `existing_signal`: existing cheap signal baseline;
- `track_interaction`: track-level interaction feature composite;
- `inside_outside`: inside/outside contrast feature composite;
- `simple_fused`: unweighted mean of the three deterministic selector scores.

The selector layer is not allowed to use `probe_set_v1` labels for feature
choice, threshold choice, or score direction.

### Budget And Return-Set Layer

The minimal implemented return-set optimizer is greedy ranked selection with
overlap control:

- sort candidates by fixed selector score;
- scan in rank order;
- reject candidates that exceed interval IoU overlap with already selected
  intervals;
- reject duplicate `overlap_group_id` candidates only when the field contains
  more than one usable group;
- stop after budget `B`.

This is the first executable AQP budget loop. It is not yet the full weighted
interval scheduling design. The next stronger version should replace greedy NMS
with an explicit objective such as:

`maximize sum(score_i * x_i) subject to count <= B, overlap constraints, duration constraints`

### Oracle Layer

The current oracle role is reference construction and spot evaluation, not
online policy learning. For `probe_set_v1`, the current reference source is
`probe_set_v1_vlm_oracle_reference` produced by local Qwen3-VL-32B.

The broader five-action oracle interface remains design-only:

- relevance;
- boundary;
- split-merge;
- blind-spot;
- pairwise comparison.

It has not yet been integrated into the selector/budget loop.

## Engineering State After This Step

Implemented:

- interval lattice artifacts exist from previous clean interval AQP runs;
- cheap signal v2 feature table exists;
- VLM-oracle labels exist for `probe_set_v1`;
- signal-level probe diagnostic exists;
- Phase 3 minimal selector/budget smoke script exists:
  `scripts/phase3/run_minimal_selector_smoke.py`.

Expected Phase 3 outputs:

- `outputs/agent_loop_v1/phase3_selector_smoke_v1/selector_budget_summary.csv`
- `outputs/agent_loop_v1/phase3_selector_smoke_v1/selector_budget_metrics_by_seed.csv`
- `outputs/agent_loop_v1/phase3_selector_smoke_v1/selected_intervals.csv`
- `outputs/agent_loop_v1/phase3_selector_smoke_v1/event_coverage.csv`
- `outputs/agent_loop_v1/phase3_selector_smoke_v1/phase3_selector_smoke_report.md`

Actual Phase 3 smoke outcome:

- the loop executed and produced budgeted returned interval sets;
- `overlap_group_id` was a single global value in the current feature table, so
  the implementation disabled group capping and used time-IoU NMS only;
- at B=40, `uniform_random` averaged 0.153 event_recall_iou_0_3 across 50 seeds;
- at B=40, the best deterministic cheap-signal selector reached 0.050
  event_recall_iou_0_3;
- the current fixed selector definitions therefore did not turn signal-level
  diagnostics into better budgeted return-set coverage.

## Still Design-Only

The following are not yet completed AQP implementation pieces:

- event_shape_signal feature generation;
- VOI-driven multi-action oracle scheduling;
- exact weighted interval scheduling optimizer;
- repair actions for boundary/split/merge;
- full Phase 4 interval envelope comparison;
- full Phase 5 end-to-end replay on a larger independent reference;
- formal claim that any selector is ready to replace the baseline.
- selector/return-set redesign after the negative Phase 3 smoke.

## Interpretation Rules

The Phase 3 selector smoke answers only:

> Can the current AQP loop produce budgeted interval return sets from existing
> cheap signals, and what do those returned sets cover under the current
> reference source?

It does not answer:

- whether a selector is statistically superior;
- whether probe_set_v1 proves generalization;
- whether the certificate/guarantee line is satisfied;
- whether a production selector should replace the current baseline.
