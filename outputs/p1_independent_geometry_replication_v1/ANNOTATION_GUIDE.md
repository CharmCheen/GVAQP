# Frozen P1-B independent annotation guide — version 1.1

Watch each full raw video and annotate maximal semantic temporal events under the frozen query. You may seek and replay freely. The interface and annotators must never access proxy/detection/flow scores, candidate units, VERIFY outcomes, trace/policy identities, C0/C1/K3 events, pseudo-reference, geometry, matched pairs, EventF1, or model predictions.

For every event record start/end seconds, boundary ambiguity, semantic ambiguity, and an optional note. Events may overlap when they are independently actionable semantic occurrences. Do not merge or split by elapsed gap length. Submit an explicit empty event list for a no-event case.

ANNOTATOR_A and ANNOTATOR_B each complete all six cases independently using stable distinct IDs. Neither may inspect or discuss the other's event locations until both submissions are complete. Saves are append-only revisions; the latest revision is used only after completeness validation. Adjudication starts only after both complete exports pass validation and remains blinded to all algorithmic artifacts.

Agreement is computed before adjudication using one-to-one maximum-IoU matching at IoU thresholds 0.1, 0.3, and 0.5, plus raw best-overlap tIoU, boundary disagreement, unmatched counts, and ambiguity rates. Difficult cases are never deleted.
