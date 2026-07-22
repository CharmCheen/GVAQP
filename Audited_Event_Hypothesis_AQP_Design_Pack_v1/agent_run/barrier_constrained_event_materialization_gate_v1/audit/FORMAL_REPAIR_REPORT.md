# Formal Non-Crossing Repair Report

Independent review found a high-severity universal-constraint counterexample: frozen unit 345 is `[3450.00,3460.00)` and unit 346 is `[3457.93,3462.93)`. The original engine admitted `((345,), (346,))`, producing overlapping events while the invariant check passed.

The repair rejects a cut before anchor `i>0` whenever `end(p[i-1]) > start(p[i])`. The invariant checker and EventRelation emitter enforce the same interval condition. The existing strict-ID-interior negative-barrier semantics is unchanged and is now explicit in the formal model.

Verification:

- the real-unit counterexample now has only `((345,346),)` as a legal partition;
- 13/13 tests pass, including the new overlapping-interval assertion;
- `FORMAL_REPAIR_EQUIVALENCE.csv` has 738 unique expected runs and 738 passes;
- no frozen trace contains both units 345 and 346 as positive anchors;
- legal-partition counts and selected ceiling/public partitions are identical for all 738 runs;
- maximum ceiling F1 difference is `1.1102230246251565e-16`;
- maximum public F1 difference is `8.326672684688674e-17`.

Conclusion: the universal legality defect is corrected; the realized frozen legal spaces and the primary decision metrics are unchanged.
