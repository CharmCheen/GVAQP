# Accelerated Event Query Next Decision

Current loop decision: `REVISE_ORACLE_PROTOCOL` (not a terminal research decision).

Independent review showed that the V1 preflight could produce a false pass and did not present reviewers and Qwen with identical frames. It is preserved as rejected before execution. The highest-value next action is to finish and independently audit V2's authenticated physical runner and analyzer before requesting any oracle compute.

The adversarial comparison is now frozen before any new-query oracle output: a contradiction candidate requires both identical 2 fps calls to return `relevant` at high confidence while the blinded review is medium/high `not_relevant`. One candidate requires independent adjudication and prevents an automatic pass; at least two candidates across two videos fail the visual gate. A review label of `unknown` is never treated as negative.

If the preflight passes, run the full 1,475-unit operational oracle with retained raw outputs and then compute operational reference events and the YOLO+K3 event-recall ceiling before any controller learning. If it fails, do not spend the full oracle budget; record `INSUFFICIENT_EVIDENCE` or revise the oracle protocol without looking at controller outcomes.

The revised targeted pilot has 32 calls, including two extra cross-replica anchor calls, and is estimated at 0.44 A100 GPU-hours before overhead. Even a V2 pass will authorize only the design and separate approval of a larger reproducible content-blind audit—not the full 1,475-unit oracle. The full run remains both scientifically and computationally unauthorized.
