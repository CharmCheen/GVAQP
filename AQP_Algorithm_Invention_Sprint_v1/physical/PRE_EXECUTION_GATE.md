# VERA physical pre-execution gate

Decision: `PHYSICAL_PILOT_JUSTIFIED`.

All inference-affecting state was frozen before any new call. The frozen plan has 70 chronological `EVENT_ENUMERATE` calls and 20 uniformly spaced, reference-independent dense hardware-calibration calls. The remaining 110-call reserve is only for preregistered dense fallback. Every started attempt counts, retries are forbidden, and the hard cap is 200.

Primary success requires all three inequalities on the untouched strict event reference: event recall >= 0.80, event F1 >= 0.80, and selected-operator synchronized GPU seconds / estimated 347-unit dense GPU seconds < 0.70. Reference rows are absent from prompt construction, sampling, ordering, parsing, fallback triggering, and runtime state.

Freeze checks:

- prompt and parser hashes: PASS
- 70-core exact timeline cover: PASS
- sample matrix constructed without event reference: PASS
- strict model manifest matches local checkpoint: PASS
- current assigned GPU recorded: PASS (`NVIDIA A100-SXM4-80GB`, `GPU-2ca52ddc-874d-913c-c345-5fa08fa92817`)
- base calls <= 200 and fallback reserve explicit: PASS (90 + 110)
- strict evaluator and reference hashed but evaluator-only: PASS
- no prior physical attempt in this sprint: PASS

The strongest unresolved risk is correlated omission inside long inputs. A parser-valid empty result does not trigger fallback, so the pilot can directly falsify the physical enumeration mechanism.
