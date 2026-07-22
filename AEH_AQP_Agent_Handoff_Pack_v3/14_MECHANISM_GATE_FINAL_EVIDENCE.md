# Mechanism Gate Final Evidence

## Completion and provenance

- Final decision: `IDEAL_SIGNAL_ONLY`.
- Settings: 149/149.
- Synthetic policy runs: 133,650.
- Semi-synthetic policy runs: 8,100.
- Total: 141,750.
- Physical VLM calls: 0.
- Old A800 checkpoint: 0 complete-valid, 121 incomplete, 28 not started.
- Final results: recomputed on one A100-host CPU path with atomic checkpoints.
- Full A800/A100 policy equivalence was unavailable because A800 traces were absent; no A800 result was mixed.

## Effects

| Suite | Saturation P1−P0 | Exploration P2−P1 | Counterfactual P3−P2 |
|---|---:|---:|---:|
| A | +0.093699 | — | — |
| B | — | — | +0.007910* |
| C | +0.022001 | −0.138092 | +0.000460 |
| D | +0.016258 | −0.092787 | +0.002482 |
| N=1000 | +0.008548 | −0.101653 | +0.000292 |
| S1 event-aligned | +0.025434 | −0.127773 | −0.000030 |
| S2 frozen H1 | −0.003978 | +0.008843 | +0.000927 |
| Moderate signal | +0.046874 | −0.111195 | +0.001368 |

`*` Suite B cannot support the intended barrier-frequency causal claim because `merge_ambiguity` is unused and nominal levels are identical.

N=1000 saturation 95% CI: `[+0.005851,+0.011245]`. Counterfactual CI crosses zero.

## Decision logic

The controlled saturation mechanism exists, but it depends on oracle/event-aligned hypotheses. It fails on frozen public H1 in every S2 cell. Therefore it does not justify real feature engineering or an online algorithm claim.

The one remaining falsification test asks whether a deterministic reownership of the same H1 actions into public event cells can transfer saturation without new information.

