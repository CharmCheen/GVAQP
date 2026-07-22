# COUNT threshold derivation

Synthetic COUNT errors were mapped to conservative priority inversions between
the frozen perfect count-guided trace (85 calls) and safe ANY best-first trace
(201 calls). Because COUNT_PRIORITY_ONLY never prunes, recall is invariant.
Many descriptive error cells improve ordering under optimistic constant cost,
but no existing C0 artifact freezes a separate meaningful COUNT-over-ANY margin,
and the interpolation is not a proof of real priority behavior.

Consequently `COUNT_NOT_REQUIRED_FOR_GO=true`. COUNT has no formal gating
threshold; exact accuracy, MAE, undercount, multi-event undercount and UNKNOWN
remain mandatory reported diagnostics. COUNT conservation is evaluator-only.
