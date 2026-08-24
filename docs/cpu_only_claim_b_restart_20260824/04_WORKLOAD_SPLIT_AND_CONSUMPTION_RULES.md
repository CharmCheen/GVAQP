# Workload separation and consumption rules

## Consumed

The DALI, HANGZHOU, and WUHAN two-query T2 cells in
`outputs/t2_c1_existing_corpus_replay_v1_retry2` are consumed for algorithm and
comparator selection. They cannot be a development, validation, or test set for
a successor policy.

## CPU synthetic fixtures

Synthetic fixtures test only semantics: empty/single/multiple candidate
creation, permissions, query conditioning, local materialization, deadline
behavior, and parity. They must not be reported as natural headroom.

## Any future empirical split

Before new sensing, freeze disjoint development, selection, and held-out test
videos or environments. Policy/hyperparameter choice uses development only;
gates are selected on validation; the held-out test is opened once. Query
families, costs, seeds, exclusions, and failure handling must be preregistered.

No near-duplicate queries or policies may be added after outcomes to create
heterogeneity or positive headroom.
