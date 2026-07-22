# Adversarial candidate review

## Gate decision

`ALGORITHM_CANDIDATE_SELECTED`: VERA only.

## Rubric audit

Scores were frozen before headroom execution. VERA passes all eight selection
conditions conditionally: it is not ARC plus postprocessing, not SUPG on
renamed fixed records, changes the physical operator and optimizer state, has
an analytic 70-call ideal headroom bound, is not falsified by the unit-ranking
or Boolean-pruning gates, supports a bounded full-timeline pilot, applies
unchanged to multiple videos, and admits an exact discretized DP plus ownership
properties.

## Strongest attacks on VERA

1. **“It is only longer clips.”** This attack wins unless the DP actually
   chooses among operator/granularity/fallback edges and relation ownership is
   required to compose set-valued outputs. A fixed 60-second prompt is a
   baseline, not the algorithm.
2. **“It is retrieve-then-ground.”** VERA does not require retrieval and must
   enumerate every owned core; a retrieved-window variant is only an ablation.
3. **“It is LOTUS/PLOP on video.”** Typed operators and cost DP are known. The
   narrower claimed novelty is temporal relation-cover planning with
   variable-cardinality output and overlap ownership. Related work may still
   invalidate this claim; wording remains provisional.
4. **“Risk profiles leak the strict reference.”** The online/physical plan is
   uniform and frozen without event locations. Evaluator-derived profiles are
   ceilings/sensitivity analysis only and cannot configure the pilot.
5. **“Set-valued output is an easier oracle.”** Correct: the mechanism changes
   the physical operator. Its cost and accuracy must be charged and measured;
   no comparison may count one enumeration call as equal merely by fiat.
6. **“Short events are invisible.”** The strict reference has many 0.7-second
   events. Fixed 2 fps has no phase-independent guarantee. This is the leading
   physical kill mechanism.
7. **“The theorem is trivial shortest path.”** Global optimality is useful but
   not a top-tier theorem by itself. A paper claim requires physical gains and
   multi-video evidence; theory alone is insufficient.

## Rejected candidates

BOLT is mostly batching and fails the explicit novelty exclusion. WAVE has a
credible workload systems question but no non-arbitrary workload or bounded
pilot under current assets. Selecting either would optimize for ease rather
than the requested end state.

## Revision trigger

Reject VERA immediately if realistic headroom requires perfect enumeration or
per-window cost below an implausible value, or if the frozen physical pilot
misses the 0.80 quality gate / 0.70 dense-cost gate. Do not respond with a
prompt, overlap or window-length sweep on the strict reference.

