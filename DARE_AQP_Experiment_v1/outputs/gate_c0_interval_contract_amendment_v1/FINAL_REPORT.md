# Physical Interval Oracle Contract Amendment v1

## Decision

**`CONTRACT_INFEASIBLE_UNDER_160_CALLS`.** Physical VLM calls remain **0**.

The governing targets are recovered: event recall at least 0.8 and total cost
strictly below 0.7 of the 347-call dense audit. No governing event-F1 target is
present.

## Derived ANY feasibility boundary

Synthetic error injection over the frozen hierarchy evaluated independent,
multi-event adversarial and boundary-adversarial false-negative placement. At
the optimistic constant-cost cell, only sensitivity 1.00, specificity at least
0.99, UNKNOWN rate 0 and zero false negatives pass every placement. Worst cost
ratio is 0.675072 at specificity 0.99. At alpha=0.95 there is no passing ANY
cell, even at perfect accuracy.

The thresholds are frozen at that conservative boundary. They are deliberately
not chosen for attainability.

## COUNT and safety policy

COUNT is `COUNT_PRIORITY_ONLY`: it may order work but cannot prune or infer a
sibling count. `COUNT_CONSERVATION_EXPERIMENTAL` is evaluator-only. COUNT is not
required for formal GO and therefore has no gating accuracy threshold. Every
abstain, invalid parse, contradiction, incomplete target, truncation, timeout or
failure is charged and maps to safe UNKNOWN fallback. Only a valid, complete,
high-confidence negative can prune.

## Why 160 calls are insufficient

With zero failures, 96 independent intervals yield a one-sided 95% exact lower
bound of 0.969276; 148 yield 0.979962. A 0.99 bound requires 299 independent
trials. A 1.00 lower bound is impossible for any finite sample. The proposed
matrix contains at most 64 independent positives and 32 independent negatives;
matched operator calls and repeats do not increase semantic sample size.

The versioned contract is sealed for provenance, but it records
`sample_size_feasible=false`; the physical gate must not run under the current
160-call authorization.

## Next action

Redesign the validation population/budget—potentially multiple frozen videos or
a substantially larger independently sampled interval set—without lowering the
accuracy, recall or cost thresholds. This requires new authorization and must
precede prompt/sample freezing.
