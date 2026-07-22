# Gate A harness completion audit

| Requirement | Authoritative evidence | Status |
|---|---|---|
| Four frozen methods | `config/gate_a_frozen.json` pins CLIP/X-CLIP commits, prompt, sampling, fusion | Complete |
| All 347 units remain rankable | score validator requires exact unit set; dry run reports 347 | Complete |
| No strict-label inference leakage | inference runner reads video, units, proxy only; independent review | Complete statically |
| Frozen metadata and method completeness | evaluator `--final` exact-set/metadata validation and test | Complete |
| Stable audit randomness | per-signal seed namespaces frozen in config | Complete |
| Top-k unique event/anchor coverage | evaluator and proxy preflight outputs | Complete |
| Full-video and blocked AUROC/AP | descriptive full-video plus five-block macro metrics | Complete; not cross-video evidence |
| Original Gate B linkage | exact bound, 500 seeds, fixed stages, same cost semantics; proxy reproduces 318/347 at B=24 | Complete |
| Cold/warm/hardware costs | runner records partial cold runtime; warm/amortized and rigorous GPU ledger unresolved | Incomplete |
| Image/video/fusion scores | model weights absent; no GPU on host; no inference executed | Incomplete |
| Final unit-ranking decision | requires eligible four-signal `--final` run | Incomplete |

The harness is ready for a bounded first GPU smoke and then one frozen run.
It is not evidence that either semantic signal works, nor that logical-oracle
GO would imply end-to-end acceleration.

Three consecutive execution audits found no GPU and no cached CLIP/X-CLIP
weights.  Final execution is therefore externally blocked until a GPU is
provided or CPU download/inference is explicitly authorized.
