# Frozen Input Audit

The v3 pack manifest validated in full before implementation. Frozen facts are independently reproduced in `frozen_fact_reproduction.csv`.

R1 construction consumes only the public unit intervals, H1 source semantics and IDs, and audit-cell unit IDs. It does not receive the event reference, oracle observations, dense labels, event matches, event IDs, future outcomes, or evaluator result tables. The builder signature and frozen input list make that boundary structural rather than relying on a promise not to inspect columns.

The source inventory is 55 high-proxy seeds, 32 orphan-local-peak sources, and 25 stable audit/uncovered cells. Units are 10 seconds; the authoritative K3 core cap is 40 seconds. R1 and its lineage were written and hashed in `config/INPUT_MANIFEST.csv` before formal evaluator execution.
