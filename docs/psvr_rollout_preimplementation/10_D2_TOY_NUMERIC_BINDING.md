# D2-T — exact toy numerical binding

The frozen H-ROLLOUT1A parameter universe has finite duration support. For a
mode change, the complete-action switch cost is at most 0.25 seconds.

For SCAN, `ratio <= 5`, `activity <= 2`, and `v <= 0.8`. Therefore nominal
SCAN is at most `5*5*(0.75+0.5*2/2)=31.25`, core duration is at most 56.25,
and complete SCAN duration is at most 56.5 seconds.

For CONFIRM, the nominal duration has supremum 7.5 seconds and `v <= 0.8`.
Core duration is therefore at most 13.5 and complete CONFIRM duration at most
13.75 seconds. The standard confirm reserve is 13.75 seconds.

Admission uses the exact per-action support function and productive SCAN
requires `B_SCAN(x,r)+13.75 <= remaining`. No observed maximum, empirical p95,
or physical timing is used. This binding makes no physical safety claim.

The mathematical binding is complete. End-to-end simulator validation is not:
the frozen generator is not uniquely executable for reasons documented in
the implementation specification and independent review.

