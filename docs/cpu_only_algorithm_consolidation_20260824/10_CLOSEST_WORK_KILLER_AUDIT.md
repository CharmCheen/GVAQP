# Closest-Work Killer Audit

## Verdict

`DIRECT_NOVELTY_FAIL_CONDITIONAL_OPERATOR_GAP`

## Claims already covered

| Claim family | Closest work | Consequence |
|---|---|---|
| Action-level video query and boundary localization | ZEUS, SIGMOD 2022 | GVAQP cannot claim the first event/action video query system. |
| Dynamic temporal input configuration | ZEUS | RL or adaptive segment length/resolution/sampling is not novelty. |
| Feedback-driven adaptive video sampling | ExSample, ICDE 2022 | A new temporal sampling heuristic alone is insufficient. |
| Language-driven segment localization and trajectory association | LAVA, 2025 preprint | Natural-language predicates, MAB localization, and tracks are covered components. |
| Open compositional video queries | VOCAL-UDF, SIGMOD 2025 | Open semantic UDF construction and compositional event querying are not novelty. |
| Generic semantic cost/quality benchmarking | SemBench, VLDB 2026 | Cost-quality evaluation alone is not a systems contribution. |

## Conditional remaining gap

The defensible gap is narrower:

> In an anytime video query where cheap temporal processing causally reveals a
> candidate frontier and expensive semantic verification is a separate operator,
> how should a query plan interleave SCAN and VERIFY to maximize distinct committed
> event utility under a deadline?

This is a conditional gap, not established novelty. It survives only if one shared
execution contract shows that operator interleaving changes outcomes beyond
temporal ordering, proxy ranking, and existing adaptive sampling.

## Killer baselines

1. `ExSample-EndToEnd`: adaptive sampling plus the same VERIFY, materializer,
   fallback, cost model, and deadline.
2. `ZEUS-style configuration policy`: dynamic segment configuration under the same
   fixed query ontology where executable compatibility permits.
3. `LargestGap`: isolates temporal dispersion from operator allocation.
4. `ProxyGreedy`: isolates ranking from temporal exposure.
5. `Sequential`, `UniformStride`, and `RandomTemporal`.
6. Offline oracle upper bound under the same action and cost semantics.

## Kill conditions

- If DATB-SV is action-trace equivalent to LargestGap, the mechanism claim fails.
- If ExSample-EndToEnd matches or beats DATB-SV under common cost and oracle, the
  algorithmic contribution fails.
- If benefit disappears under C3 cost, the deadline-safe systems claim fails.
- If gains depend on one video or query family, generalization fails.
- If human MEC invalidates VLM-relative event utility, the user-utility claim fails.

## Primary sources checked

- ZEUS: https://www.microsoft.com/en-us/research/publication/zeus-efficiently-localizing-actions-in-videos-using-reinforcement-learning/
- ExSample: https://arxiv.org/abs/2005.09141
- LAVA: https://arxiv.org/abs/2507.19821
- VOCAL-UDF: https://arxiv.org/abs/2408.02243
- SemBench: https://sembench.github.io/SemBench/

