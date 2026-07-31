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
entry points. Formal evaluator directories are owned by frozen evaluator UID 0
with mode `0700`; files use `0600`. Every later controller/replay process must
run as UID/GID 65534 with zero effective capabilities and with the evaluator
execution root absent from its container mount namespace. A real fork/setuid
test must prove that a guessed absolute evaluator sentinel path raises
`PermissionError`. Import-root nonoverlap alone is explicitly insufficient.

Tests also require hidden-label permutation invariance, rejection of
forged/future results, rejection of direct lookup, path-root non-overlap, and
same-host different-UID guessed-path denial. No replay or controller is run in
this preregistration stage.
