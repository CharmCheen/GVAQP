# Full-Grid Seal V2 Dry-Run Failure

Seal SHA-256:
`f986ddc488e364baa04d4c5400f3394b42e5c3f8e9f3d209dfc3e50e97c041cb`

Decision: `REVISE_FULL_GRID_PREREGISTRATION`

Observed evidence:

- 120 tests passed.
- All 1,475 units and 30,932 frames independently redecoded and reprocessed;
  every frozen tensor identity matched with no model load or inference.
- Nine hard fault injections passed, including abrupt worker death.
- `partial_nonpublication` returned false because the revised analyzer correctly
  maps a missing supervisor audit to `FULL_GRID_ABORTED_RUNTIME`, while the old
  dry-run assertion still required exactly `INSUFFICIENT_EVIDENCE`.
- No formal reference was published; the safety outcome itself was correct.

Revision: update the dry-run assertion to require the frozen higher-priority
runtime-abort decision plus absence of a formal release pointer. Analyzer,
finalizer, authentication gates, inputs, tensor identities, and decision
priority are unchanged. Rebuild and reseal because dry-run source is bound.
