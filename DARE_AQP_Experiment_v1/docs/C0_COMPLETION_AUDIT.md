# Gate C0 completion audit

## Requirement-to-evidence matrix

| Requirement | Evidence | Status |
|---|---|---|
| Exact `ANY_EVENT` / `COUNT_EVENTS` interval operators | `src/dare_aqp/interval_ceiling.py`; exhaustive small-N recovery tests | Complete as cached ceiling |
| Dense, uniform, ARC/MAP, binary, best-first, count-guided, oracle comparisons | `unit_order_comparators.csv`, `break_even.csv`, `query_traces.csv` | Complete; unit orders are contextual, not C0 decision-bearing |
| Constant and affine duration/frame cost models | `cost_curves.csv`; normalized `c(L;alpha)` contract | Complete as parametric sweep |
| Actual VLM cost curve | No block calls made; host has no GPU | Missing, explicitly unresolved |
| Unit-audit lower-bound explanation | `UNIT_AUDIT_LOWER_BOUND.md`, exact numerical table and tests | Complete for registered SRSWOR design |
| Independent consequential-claim review | `INDEPENDENT_REVIEW_C0.md` | Complete |
| Gate A frozen semantic signals | Model commits/prompt/sampling/fusion frozen; label-blind runner and exact Gate-B-linked evaluator preflighted; embeddings absent | Infrastructure complete, inference pending compute decision |

## Verified decision

`CONDITIONAL_C0_ONLY` is proven by current artifacts.  A real multi-resolution
algorithm is not proven: exact interval operators require fixed-cost fraction
strictly above 0.919267 in the primary cell, and accuracy is unmeasured.

## Routing

No broad VLM experiment or full Gate C is authorized by C0.  The next external
work is either the once-frozen Gate A or a small block-operator measurement;
both require an explicit compute/model execution decision.
