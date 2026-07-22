# K3 Path Audit

## Actual Path

Stage 1A and 1B dynamically import `scripts/stage0_7_minimal_operator_compression.py` and call `construct_k_segments(..., "K3_gap_duration_negative_barrier")`. Stage 0.7 loops over each explicit variant and writes variant-specific files; no result cache is read. The variant argument is consumed by the `KRULES` lookup. Config YAML files are records written from hard-coded Python constants, not runtime config inputs.

## Aggregate Rule Evidence

Counts below aggregate 211 fixed-log replay runs over budgets 5, 10, 20, 50, 80, 100. Eligibility follows K3's actual short-circuit order.

| Rule | Eligible | Trigger | State change | Changed replay output | Interpretation |
|---|---:|---:|---:|---:|---|
| positive-anchor merge | 2009 | 718 | 718 | 211 nonempty runs | independently active |
| gap limit (`G_max=1`) | 2009 | 957 | 957 | 161 | independently active |
| core duration (`40s`) | 1052 | 106 | 106 | 79 | independently active after gap passes |
| queried-negative barrier | 946 | 228 | 228 | 75 | independently active, but semantically untyped |
| intermediate-positive bridge merge | 2009 | 12 | 12 | 12 action prefixes | destructive merge is reachable and observed |
| K4 boundary expansion | 3004 | 1372 | 1372 | 106 | active only outside K3 |
| segment duration (`60s`) | 1372 | 0 | 0 | 0 | unreachable in K3; reachable check in K4 but never rejects these logs |
| C6 proxy valley | 2009 | 708 raw condition hits | 0 independent | 0 | condition overlaps earlier blockers; no C3→C4 output effect |
| duplicate suppression | 0 | 0 | 0 | 0 | no eligible duplicate pairs |
| conflict resolution | 0 | 0 | 0 | 0 | no implementation branch |

Per-budget evidence is in `k3_path_audit.csv`.

## Required Questions

1. A new middle positive can destructively merge two existing events. This happened in 12 ordered-log prefixes (B20:1, B50:2, B80:5, B100:4).
2. `D_seg_max=60s` has no K3 execution path because K3 sets `selected_expand=False`; K3 returns the core interval directly. It is checked only in K4/C6 expansion.
3. Negative barriers are built from every queried `oracle_label==0`, regardless of core/support/PLACE_BARRIER origin. The log schema has no relation semantics.
4. K3/K4/C6 variants are passed to the execution function and generate separate files.
5. No shared cache alias was found. K3/K4/C6 segment hashes differ.
6. Python consumes the parameters, but YAML is output-only. Editing YAML alone cannot change execution.
7. The evaluator can hide output differences: K3, K4 and C6 have identical aggregate overlap-any metrics in Stage 0.7, while K4 differs from K3 in 106 run outputs and C6 differs from K3 in 204 output hashes in the prior audit.

## Freeze Decision

K3 is reproducible enough to retain as a **legacy fixed-log comparator**. It is not safe to freeze as the latent-event materializer baseline: ordinary binary negatives are hard must-not-links, typed relation evidence is unavailable, `D_seg_max` is dead in K3, destructive positive bridges occur, and the current evaluator masks output changes.
