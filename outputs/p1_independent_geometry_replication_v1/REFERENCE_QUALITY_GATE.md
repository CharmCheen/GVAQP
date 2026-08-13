# Frozen human-reference quality gate — P1-B v1.2

Agreement uses one-to-one maximum-IoU matching and reports IoU>0 plus sensitivities at 0.1, 0.3, and 0.5, event existence, count differences, unmatched fraction, median matched tIoU, start/end disagreement, and boundary/semantic ambiguity.

`HUMAN_REFERENCE_QUALITY=INSUFFICIENT` if any holds: (A) event existence differs in at least 3/6 cases; (B) event-count difference exceeds `max(2, 50% of larger count)` in at least 3/6 cases; (C) global one-to-one matched-event fraction at IoU>0 is below 0.50; (D) blinded semantic review documents systematic different query interpretation in multiple cases. Otherwise it is `ADJUDICATION_ELIGIBLE`.

IoU 0.3/0.5 are boundary diagnostics and do not mechanically fail the reference. Failure prohibits adjudication and requires protocol review plus full six-case reannotation; difficult cases cannot be deleted.
