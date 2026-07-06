# FINAL DIAGNOSIS — Why Repair Is Net-Negative on Chunk-Bandit Discovery

## 1. Is D3-norepair-core-chunk120 the same method as B6-core?

**No.** They differ in singleton counting (event_id vs bin-level positive). D3-norepair achieves slightly higher event_recall (+0.026) and uses more discovery calls, so it is an independently verified strong strict-replay configuration.

## 2. Main cause of repair's negative effect: budget diversion or accounting error?

**Both, but the accounting error dominates.**

- Budget diversion: 25/38 repair calls picked a chunk with lower theta than the best available alternative.
- Accounting error: 981 discovery calls in D3-core re-queried bins already queried by audit/repair, because `discovery_d3_chunk_bandit` ignores the `queried` argument. This wastes real oracle budget and corrupts the bandit posterior.

## 3. Is this a fixable bug or a mechanism design problem?

**It is a fixable bug.** The chunk-bandit discovery function should (a) initialize its state from `queried`, including audit/repair bins, and (b) never re-select a bin in `queried`. Once fixed, the marginal value of repair should be re-evaluated before concluding that the repair mechanism is net-negative.

## 4. What does this mean for the 'performance route vs mechanism paper' decision?

This diagnosis **weakens the evidence for stopping the performance route**. The previous conclusion that 'repair is net-negative' was partly based on a known accounting bug. The honest next step is to fix the bug and re-run, rather than pivoting to a mechanism-comparison paper on the basis of a contaminated comparison.
