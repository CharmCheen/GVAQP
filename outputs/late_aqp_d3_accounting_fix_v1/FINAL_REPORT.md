# FINAL REPORT — D3 Chunk-Bandit Accounting Fix

## 1. Is the accounting bug fixed?

**Yes.** `duplicate_query_after_audit_repair_count` is 0 across 12 dry-run trials. Discovery no longer re-queries audit/repair bins.

## 2. Did duplicate calls drop significantly?

- Original D3-core mean duplicates per trial: 11.21
- Fixed D3-core mean duplicates per trial: 0.51
- Reduction: 95.4%

## 3-5. Performance comparisons

| question | answer | evidence |
|---|---|---|
| fixed vs original D3-core | better on 1/6 segments | B_90/90 comparison |
| fixed vs D3-norepair | better on 1/6 segments | B_90/90 comparison |
| fixed vs B7-core | better on 0/6 segments | B_90/90 comparison |

## 6. Does repair have positive marginal value after fix?

**Neutral.** D3-core-fixed is better on some segments but not a majority; repair is not consistently additive.

## Budget diversion after fix

Across 84 logged trials, there were 146 repair calls and **0** budget-diverting repair calls (diversion rate 0.0%).

After the accounting fix, repair calls no longer preempt higher-theta chunks. The remaining performance gap vs D3-norepair is therefore not caused by budget diversion, but by the fact that repair consumes budget that could otherwise go to global bandit exploration.

## 7-8. Should we stop the performance route?

Even after fixing accounting, repair is not additive and B7-core remains best. Consider pivoting to audit/estimator contributions.

## 9. Re-interpretation of previous event-diverse discovery conclusions

The previous conclusion that 'D3-core repair is net-negative' was contaminated by the queried-state accounting bug. After fixing the bug, the comparison between D3-core-fixed and D3-norepair is the valid one for assessing repair. Previous rankings of D0/D1/D2 are unaffected because they do not use the D3 chunk-bandit discovery function.

## Final recommendation

**B. Continue with D3-norepair / chunk-bandit core, repair not consistently useful.**
