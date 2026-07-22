# Paper Positioning and Novelty Boundary

## Recommended title-level framing

**Budgeted Multi-Event Semantic Query Processing over Long Video**

Avoid making “event graph” or “coarse-to-fine search” the title contribution. Recent work already makes long-video grounding a search problem and uses structured search-and-aggregate or hierarchical knowledge graphs.

## Novelty intersection

The still-open intersection is:

```text
multi-event discovery
+ explicit heterogeneous oracle budget
+ event-level deduplication and boundary recovery
+ cost-aware typed action selection
+ independent residual audit
+ proposal-coverage and missed-event accounting
```

## Closest recent threats and opportunities

### ExtremeWhenBench

Supports the empirical diagnosis that search/proposal quality can dominate long-video performance. It motivates strong frame/clip retrieval and retrieve-then-ground baselines, and separate search-miss reporting.

### CoMET-Bench / CoMET-Agent

The main novelty threat: conditional multi-event grounding, counting, negative queries and search-and-aggregate already exist. Differentiate via strict oracle budget, database execution semantics, event materialization/partition, independent audit and cost-quality planning.

### Hierarchical video knowledge-graph retrieval

Shows that event/KG representation is not enough. A hypothesis node must be a query-time uncertain state with legal actions, provenance and materialization consequences.

### Query-centric AQP for expensive AI predicates

Strengthens the database framing. Use it to explain why record-level sampling/proxy filtering does not directly control event-set recall under temporal dependence and duplicate records.

### Cost-based semantic-operator placement

Motivates cost/selectivity models for typed event actions. The sealed mechanism gate did not support counterfactual planning, so do not implement a complex optimizer. Apply cost modeling first to the retained event materialization operator.

### AUTOPILOT VQA

Useful for a structured driving-event oracle schema—actor, context, incident, impact and avoidability—but VQA accuracy is not an event retrieval baseline.

## Related-work links, snapshot 2026-07-11

- AUTOPILOT VQA: https://arxiv.org/abs/2607.08745
- ExtremeWhenBench: https://arxiv.org/abs/2606.12300
- CoMET-Bench/Agent: https://arxiv.org/abs/2606.15320
- Hierarchical KG retrieval: https://arxiv.org/abs/2606.01933
- Query-centric AQP: https://arxiv.org/abs/2607.00254
- PLOP, cost-based semantic-operator placement: https://arxiv.org/abs/2604.09944

Verify titles, versions and results from primary sources again before paper submission.

## Venue view

For VLDB/SIGMOD-style review, emphasize query semantics, physical operators, optimizer state, budget/cost model, audit and reproducibility. For SIGIR-style review, emphasize multi-event retrieval, ranking under budget, negative queries and retrieval effectiveness. A single-video engineering improvement is unlikely to clear either bar.

## Paper routes

### Route A — Strong algorithm paper

Requires mechanism GO, operational public features, multiple videos, modern baselines and an audit component.

### Route B — Event materialization/query semantics paper

If planner fails, establish EventRelation semantics and selector-agnostic BB-EM across selectors/videos with merge/split and cost analysis.

### Route C — Systems/benchmark paper

Only if the strict execution protocol, datasets, oracle provenance and evaluation suite are expanded beyond one video and released as a reusable benchmark.
