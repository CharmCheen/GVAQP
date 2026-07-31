# Full-Grid Label-Hiding Audit

Status: `FROZEN_INTERFACE_IMPLEMENTED_TEST_REQUIRED`

Three layers are separate:

1. `EvaluatorOnlyLabelStore` owns exhaustive full-grid labels and requires an
   opaque evaluator capability. Its controller lookup method fails closed.
2. Runtime VERIFY results are produced causally by the selected runtime action
   and signed with Ed25519. The public runtime history receives only the public
   verification key and completed signed results; it cannot mint results or
   request arbitrary full-grid unit IDs.
3. Public controller state contains public observations plus already completed
   signed VERIFY history only. SCAN, runtime K3, and action selection receive no
   evaluator path, object, event ID, future label, or boundary.

The evaluator reference and runtime K3 use different constructors and process
entry points. Evaluator releases are permissioned `0600`, stored outside runtime
import roots, and accessible downstream only through a validated release commit.
Tests require hidden-label permutation invariance with public observations and
revealed history fixed, rejection of forged/future results, rejection of direct
controller lookup, and path-root non-overlap. No replay or controller is run in
this preregistration stage.
