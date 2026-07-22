# Gate B result

**Decision: `NO_GO` for the preregistered 80% pseudo-event recall certificate gate.**

## Observed evidence

- Population: 347 units and 26 distinct frozen canonical anchors.
- Repetitions: 500 seeds per policy/budget; delta=0.05.
- Minimum empirical coverage across all fixed stages: 0.9380.
- Lowest-cost public stage certifying 80% recall in >=90% of seeds: `proxy_top` with discovery budget 5, audit n=310, median total logical cost 315.0 (0.908 of dense complete audit).
- Lowest-cost evaluator-only oracle-anchor ceiling: discovery budget 29, 26 events found before audit, audit n=110, median total cost 165.0 (0.476 of dense complete audit).
- First idealized ceiling budget crossing the cost gate: B=24 after finding 24/26 events; B=23 remains NO_GO.

## Interpretation

The result tests audit identifiability under the strict pseudo-event contract. It does not validate real-event certification, semantic search, sequential stopping, or cross-video generalization.

Weak discovery is now a working explanation, not an established cause. The evaluator-only oracle-anchor ceiling only proves that perfect event-first ordering creates an idealized feasible region; it does not show that a real semantic signal can approach it. Compare proxy-top with uniform and the ceiling before deciding whether Gate A is justified.

## Decision and next action

The public Gate B result is NO_GO. The evaluator-only ceiling establishes only an idealized feasible region and makes attainable search quality the next decision-critical uncertainty. The next justified experiment is Gate A: test frozen, externally pretrained all-unit semantic signals without tuning on strict labels. Reject or revise DARE-AQP if those signals cannot materially close the public-to-ceiling discovery gap.

See `stage_decisions.csv`, `fixed_stage_summary.csv`, and `raw_trials.csv` for authoritative values.
