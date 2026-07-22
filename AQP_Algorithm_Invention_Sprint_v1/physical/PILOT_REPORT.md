# VERA physical pilot report

Physical gate: `FAIL`.

The run started 105 new Qwen3-VL calls: 20 reference-independent dense hardware calibrations, 70 full-timeline enumeration calls, and 15 preregistered dense fallback calls. The 200-call cap was respected.

## Primary frozen endpoints

| Metric | Result | Frozen threshold | Pass |
|---|---:|---:|---|
| Event precision | 0.083333 | diagnostic | — |
| Event recall | 0.038462 | >= 0.80 | False |
| Event F1 | 0.052632 | >= 0.80 | False |
| Selected GPU seconds | 1566.323 | diagnostic | — |
| Estimated dense GPU seconds on this GPU | 6499.602 | denominator | — |
| GPU-cost ratio | 0.240987 | < 0.70 | True |

The cost denominator is 347 times the median synchronized generation wall time of the 20 uniformly spaced dense calibration calls. Calibration quality agreement with the pre-existing strict outputs, checked only after inference, is 1.000.

## Interpretation

This is single-video, VLM-pseudo-oracle-relative development evidence. A valid empty enumeration does not trigger fallback, so misses are not hidden by the fallback policy. Single-owner reconciliation performs no heuristic cross-window merge; oversplitting remains visible to the frozen evaluator. The cost-normalized event-F1 AUC on the predeclared dense-equivalent budget grid is 0.005540.
