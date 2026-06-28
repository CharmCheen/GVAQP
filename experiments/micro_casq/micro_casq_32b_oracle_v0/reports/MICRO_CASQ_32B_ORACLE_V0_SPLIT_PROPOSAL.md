# Micro-CASQ 32B-Oracle v0 Split Proposal

Generated: `2026-06-22T15:17:03Z`

Splits are proposed for future oracle-relative candidate feasibility and certificate experiments. Excluded rows are kept out of candidate tuning, heldout evaluation, and the reserved certification pool. Event boundaries must not be used to generate future candidates.

| split_label | oracle_category | count |
| --- | --- | --- |
| candidate_dev | oracle_negative | 13 |
| candidate_dev | oracle_positive | 13 |
| excluded_or_needs_sanity_check | excluded_or_needs_sanity_check | 79 |
| heldout_eval | oracle_negative | 20 |
| heldout_eval | oracle_positive | 7 |
| reserved_certification_pool | oracle_negative | 18 |
| reserved_certification_pool | oracle_positive | 3 |

The reserved certification pool must not be used for candidate tuning. If eligible positives are sparse, this benchmark is useful for candidate signal testing but underpowered for final certificate claims.
