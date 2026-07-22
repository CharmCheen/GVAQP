
# Authority and terminology freeze

Status: `FROZEN_RESULT_BLIND`. Generated 2026-07-19T16:28:52+00:00. No toy comparison, physical call, GPU extraction, or held-out-real-data access was performed.

## Authority order and observed state

The user-supplied D1--D4 freeze specification governs this package. It is interpreted with the repository contracts, registries, ledgers, failure catalog, two-video NO_GO report, Stage-A model report, H-DS1 deadline artifacts, and frozen unit manifest. Their SHA-256 values are recorded in the freeze manifest.

Observed evidence: the rule-based two-video route is `NO_GO`; FIFO is the current simple baseline; M0 is exploratory and not deployable; the temporal refiner shows no clear gain; H-DS1 is empirical development safety, not WCET; no toy rollout evidence exists. Derived decision: only design/preregistration is authorized. Working hypothesis: ideal symmetric rollout may improve a proper base policy under restrictive exact-model conditions. Unresolved: a full pre-action SCAN obligation bound.

## Frozen terms

- **Candidate Witness**: runtime-visible proxy evidence tied immutably to one VERIFY opportunity. It is not an oracle label or event.
- **Event Hypothesis**: a frontier group containing one or more witnesses believed to concern one event opportunity; grouping can under-merge or over-merge.
- **Committed Event**: an event interval durably and atomically materialized into the append-only output snapshot after CONFIRM.
- **Event-Hypothesis Frontier**: current hypotheses and their witness states, not committed output.
- **VERIFY**: physical semantic Oracle plus parser only.
- **CONFIRM**: VERIFY, PARSE, MATERIALIZE, ATOMIC durable COMMIT, then frontier update as one decision-level action.
- **Scan State** replaces “coverage”; **Ratio-PSVR baseline** replaces “ratio-index”; **Committed Event** replaces “confirmed result”.

The three entities are not one-to-one: many witnesses may represent one event; under-merge may create several hypotheses for one event; over-merge may put several events in one hypothesis; a positive witness may duplicate an existing committed event or fail materialization; and one hypothesis may yield no committed event.

`H-PROG1` is superseded as the method direction by `H-ROLLOUT1` but remains a baseline. “M0 candidate value” means an optional confirm-outcome estimator only, never a rollout world model or a dependency of H-ROLLOUT1A.

SAFE_HARBOR means stop starting work and return the last complete durable snapshot. It never flushes dirty state.
