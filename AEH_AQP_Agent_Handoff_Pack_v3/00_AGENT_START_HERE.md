# Start Here

## Mission

Determine whether a database-style, budgeted event-set query processor can beat strong long-video search baselines by using event-aware query state, bounded materialization and independent audit—not merely by adding engineering heuristics.

The intended query plan is:

```text
EVENT_SEARCH
  → EVENT_VERIFY
  → EVENT_MATERIALIZE
  → EVENT_AUDIT
  → EventRelation
```

The immediate job is **not** to implement the full actor graph or resume the completed mechanism gate. Run exactly one frozen public event-cell representation test on S2, then either retain a minimal saturation mechanism or close the planner route.

## Frozen facts

- Strict benchmark: `cbbv2_514c0d360fd5b2a4b5fe`.
- Reference events: 26.
- Best native baseline event-F1 AUC: `0.389659`.
- Current MAP/M1 AUC: `0.388056`.
- Initial BCM AUC: `0.294270`; decision `NO-GO` for that implementation.
- H1 source repair AUC: `0.314990`; decision `HYPOTHESIS_REPAIR_WEAK_GO`.
- Oracle-informed action reorder ceiling AUC: `0.664458`, but public blocked-CV AUROC is only `0.548282` and the legal universe misses `6/26` events.
- Therefore planner headroom exists, but current public candidate features cannot realize it.
- The 149-setting controlled mechanism gate is complete: `IDEAL_SIGNAL_ONLY`.
- Saturation works with oracle/event-aligned hypotheses but does not transfer to frozen H1.
- Exploration is harmful overall; counterfactual materialization is negligible.
- `REAL_CHEAP_PRIMITIVE_ENGINEERING_JUSTIFIED=false`.

## Next experiment

Run `public_event_cell_representation_gate_v1` as specified in `15_NEXT_EXPERIMENT_SPEC.md`.

It uses the frozen H1/S2 universe and existing observations. It changes only the public structural representation of existing candidates; it adds no cheap features, candidates, oracle calls or evaluator information.

## First actions

1. Reproduce the sealed mechanism-gate decision from server artifacts.
2. Read `15_NEXT_EXPERIMENT_SPEC.md` and freeze one R1 construction before evaluation.
3. Run R0/R1 × P0/P1 only on the exact frozen S2 matrix.
4. Seal the result and issue either `PUBLIC_EVENT_CELL_SATURATION_GO`, `PLANNER_ROUTE_REJECTED`, or `EXPERIMENT_BLOCKED`.
5. Write the next operator-task prompt; do not implement the operator in the same task.

## Hard prohibitions

- Do not expose evaluator reference or dense oracle labels to an online planner.
- Do not tune on the strict test video after seeing evaluator outcomes.
- Do not call the VLM unless a future task explicitly authorizes it.
- Do not rerun the strict benchmark or baselines merely to obtain a favorable score.
- Do not call a single-video result a cross-video or human-GT result.
- Do not claim a certificate without a unique canonical anchor, independent audit sampling and empirical coverage validation.
- Do not claim “event graph” or “coarse-to-fine search” alone as novelty.
- Do not run P2 exploration or P3 counterfactual materialization again.
- Do not add a representation grid after seeing results; this is a one-shot falsification gate.
