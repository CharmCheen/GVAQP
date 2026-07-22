# Reviewer attacks

| Attack | Best response from evidence | Remaining weakness |
|---|---|---|
| "This is just a longer prompt/clip." | Novelty is claimed for the relation-cover plan, alternative physical edges, and ownership semantics; prompt novelty is explicitly excluded. | The pilot uses a fixed 50-second cover, so variable-resolution benefit is simulator-only. |
| "This is ARC with postprocessing." | ARC's native output and state are unit/clip selections; VERA edges return set-valued relations and form an exact cover. | ARC+the same operator must be compared; the shared-output baseline does so. |
| "This is SUPG on windows." | SUPG record selection does not express variable-cardinality fragment composition or dense/enumeration cover choice. | Statistical quality guarantees here are model-based, not SUPG-style empirical guarantees. |
| "Cost is call-count theater." | Gate uses synchronized generation seconds and same-GPU dense calibration; cold/warm/frame/token/memory costs are separate. | Dense total cost is estimated from 20 uniform calls rather than rerunning all 347 on the A100. |
| "The simulator was optimistic." | Correlated p05 failures were reported before execution. | Confirmed: it omitted the processor's default-metadata resampling error mode. |
| "Reference leaked into the plan." | The sample matrix is uniform/chronological and declares no reference access; hashes freeze it before calls. | The same strict pseudo-oracle is used for evaluation and was produced by the same model family. |
| "One video proves nothing." | No generalization claim is made. | Multi-video human-truth validation remains mandatory. |
| "Fallback hides misses." | A valid empty enumeration never triggers fallback. Fallback triggers only abstain/parser/resource failure. | Systematic valid omissions remain undetected—which is intentional falsification pressure. |

Decision under attack: `PHYSICAL_PILOT_NO_GO`. Strongest competing explanation for physical failure: the metadata-free processor consumed far fewer frames than simulated. That explanation does not turn the frozen result positive.
