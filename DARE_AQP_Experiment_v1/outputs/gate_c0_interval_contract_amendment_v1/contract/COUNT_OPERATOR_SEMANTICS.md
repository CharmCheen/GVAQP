# COUNT operator semantics v2

COUNT is advisory and may order positive/UNKNOWN intervals or estimate work. It
cannot prune, infer a sibling count by conservation, establish the recall
denominator, or override safe ANY. COUNT=0 with effective ANY POSITIVE/UNKNOWN
follows ANY. Invalid/abstaining COUNT becomes `UNKNOWN_COUNT`.

Two variants are frozen:

- `COUNT_PRIORITY_ONLY`: formal-safe; ordering only, recall equals safe ANY.
- `COUNT_CONSERVATION_EXPERIMENTAL`: evaluator-only diagnostic, ineligible for
  formal GO because any undercount can erase a sibling without proof.

`COUNT_NOT_REQUIRED_FOR_GO=true`. The amendment therefore freezes no gating
COUNT accuracy threshold. COUNT metrics remain mandatory diagnostics, but a
later formal GO can only be `ANY_HIERARCHICAL_GO` under this contract.
