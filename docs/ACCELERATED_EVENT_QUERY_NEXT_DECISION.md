# Accelerated Event Query Next Decision

Current loop decision: `CONTINUE` (not a terminal research decision).

The highest-value next experiment is a preregistered, cross-video 32B oracle stability and parse-validity preflight on a small fixed sample spanning old-oracle positive/negative and boundary/disputed strata. Repeat every selected clip with identical 2 fps inputs, and run six frozen 4 fps sensitivity calls at the highest-risk locations. Pass only if parsing is complete, repeated labels/boundaries are stable, no high-confidence 2 fps/4 fps polarity flip occurs, and an adversarial visual review does not reveal systematic unsupported response claims.

If the preflight passes, run the full 1,475-unit operational oracle with retained raw outputs and then compute operational reference events and the YOLO+K3 event-recall ceiling before any controller learning. If it fails, do not spend the full oracle budget; record `INSUFFICIENT_EVIDENCE` or revise the oracle protocol without looking at controller outcomes.

The 30-call preflight is estimated at 741.8 sequential inference-seconds, or an idealized 247.3 seconds with three independent two-GPU replicas, excluding load/decode/preprocess. The full pass is estimated from direct prior measurements at roughly 10.1 sequential inference-hours, or an idealized 3.4 hours with three replicas. Launching either physical oracle workload is intentionally deferred pending the repository's required approval for substantial compute/oracle expenditure.
