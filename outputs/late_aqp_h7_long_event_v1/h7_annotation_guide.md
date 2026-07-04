# H7 Exhaustive Annotation Guide

## Query predicate
Visible Ego-Path Conflict (VEPC): see task spec for full definition.

## Label values
- `positive`: the bin contains at least one visible ego-path conflict.
- `negative`: the bin clearly contains no VEPC.
- `uncertain`: visibility/trajectory is ambiguous; do not guess.

## Event boundary rules
- Event start = first frame where a participant meets VEPC conditions.
- Event end = earliest of:
  - participant fully leaves ego-path;
  - ego evades and danger is resolved;
  - stable safe spacing > 2s.

## event_fraction_in_bin
- If a positive event partially occupies the bin, estimate the fraction (0–1).
- If the whole bin is positive, use 1.0.
- If unknown, leave empty.

## Point-anchor vs long-interval
- point_anchor: event duration < 1s.
- long_interval: event duration >= 1s.
- Record the event type in `notes`.

## Quality control
1. Before full annotation, randomly sample 5% of bins and have two independent annotators label them.
2. Compute Cohen's kappa or simple agreement.
3. If agreement < 0.7, stop and refine the guide/definition; do not proceed to full annotation.
4. After full annotation, a second reviewer spot-checks 5% of positive and 5% of negative bins.

## Usage restrictions
- This annotation package is **only** for H7 calibration evaluation.
- It must **not** be used to tune prior thresholds, E0 size, repair rules, or selector parameters.
- window_suspected_leakage may be used for H1/H2 qualitative evidence only; it must **not** be merged into H7 calibration error.

## Reviewer
- Fill `reviewer` with initials.
- Use `notes` for any ambiguous cases or definition questions.
