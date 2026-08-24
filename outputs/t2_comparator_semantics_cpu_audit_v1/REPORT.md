# T2 Comparator and Policy-Semantics CPU Audit

## Verdict

`CURRENT_DATB_RETIRED_DEPLOYABLE_EXSAMPLE_SUPERIORITY_NOT_ESTABLISHED`

This is a read-only diagnostic over the six consumed T2 workloads. It is not a
new algorithm comparison and cannot authorize policy tuning.

## Fixed ExSample configurations

- chunk 3: DATB-minus-fixed-ExSample mean AUC -0.010108
- chunk 6: DATB-minus-fixed-ExSample mean AUC +0.005561
- chunk 12: DATB-minus-fixed-ExSample mean AUC -0.010999

- Per-row oracle-envelope DATB delta: -0.040842
- Oracle bonus over best global fixed chunk: +0.029843
- Oracle bonus fraction of the reported absolute gap: 0.731
- Leave-one-workload-out DATB delta: +0.000117

## Query observability diagnostic

- DATB identical action traces across the two queries: 3/3
- Fixed-chunk-6 ExSample identical traces: 0/3

The DATB result is consistent with the audited adapter: every scanned cell
exposes a candidate, candidate participant IDs are empty, and VERIFY outcomes do
not alter DATB's future value calculation. Human labels cannot repair this
policy-state degeneracy.

## Claim boundary

- Current DATB robust superiority is not supported and the branch remains retired.
- Failure to beat a per-row oracle envelope does not establish that one deployable
  fixed ExSample configuration consistently dominates DATB.
- These consumed workloads cannot be reused to select a new policy.
