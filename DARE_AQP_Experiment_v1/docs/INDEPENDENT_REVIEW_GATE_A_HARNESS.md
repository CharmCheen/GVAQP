# Independent adversarial review: Gate A harness

Review date: 2026-07-11.  No model was downloaded or executed, and the reviewer
made no file changes.

## Confirmed before repair

- inference does not read the event reference;
- rank fusion is built before evaluator labels are joined;
- current-proxy preflight is byte-reproducible and matches original Gate B
  seed, audit-frame, cost, and hypergeometric semantics;
- preflight was explicitly described as non-final.

## Findings and resolutions

1. **Final eligibility was not enforced (high).**  Arbitrary partial signals
   could receive a final-looking decision, metadata were unchecked, and RNG
   namespaces depended on supplied signal ordering.  Resolution: preflight is
   now always `PREFLIGHT_ONLY`; `--final` requires exactly the four frozen
   signals and exact model/revision/prompt metadata; seed namespaces are fixed
   in config per signal.
2. **Only full-video AUROC/AP were implemented (high for generalization
   language).**  Resolution: those metrics are renamed evaluator-only
   descriptive metrics, and five frozen contiguous-block macro AUROC/AP values
   are added.  No cross-video generalization claim is made.
3. **Runtime cannot support end-to-end acceleration (high).**  Logical Gate B
   excludes semantic-index cost, warm-query cost is not fully measured, and GPU
   wall timing is not a complete hardware cost ledger.  Resolution: reports
   now separate logical-oracle results from `end-to-end NOT_ESTABLISHED`.
   A final paper claim still requires a repaired measured runtime ledger.
4. **Proxy was position-bound (medium).**  Resolution: inference now joins the
   proxy by `frame_idx` and validates exact frozen-unit coverage.

## Remaining execution risk

The CLIP/X-CLIP runner is dry-run and static-check tested only.  Its first real
GPU execution must be treated as a software smoke test before the frozen full
run; any API repair may preserve model/prompt/sampling semantics but cannot be
chosen using evaluator labels.

