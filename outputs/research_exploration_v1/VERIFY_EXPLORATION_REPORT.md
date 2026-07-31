# VERIFY exploration report

Decision: **REVISE** (paired quality/cost signal exists; escalation utility is
not established).

The physical Hangzhou probe observed mean inference time 8.281 s for 8B on one
A100 and 24.726 s for the 32B-FP8 checkpoint dequantized across two A100s.
Inputs and tensor shapes matched; both models parsed 4/4 calls and repeated one
clip byte-identically. Across three unique clips, labels agreed on two. The
one 32B-only positive was judged unsupported by a qualitative contact-sheet
audit. This establishes a roughly 2.99x clip-latency difference and real model
disagreement, not a trustworthy escalation target.

The V3 full-grid fail-stopped at 136/1,475 and cannot release the shared event
reference. No current data support all-8B, all-32B, random escalation, confidence,
unknown-only, disagreement-predictor, event-level predictor, or hindsight
policies after the same V3 K3. Event-F1 gap, 32B call reduction, GPU-second
reduction, unsupported-positive rate, and representative latency quantiles are
unknown. The GO thresholds therefore cannot be evaluated.

Minimum conclusion-changing experiment after a newly sealed V3 release: form a preregistered
paired pilot across all three videos with identical V3 query/context/input
hashes, oversampling V3 32B positives/unknowns plus low-proxy audit samples;
obtain an independent human audit subset; then compare all-8B, all-32B and
unknown-only escalation through shared K3. Do not train a router before this
teacher/semantic audit passes.
