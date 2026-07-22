# Invalidated Attempt 003 — H1 Score Isolation

- Independent-review finding: the initial repaired `risk()` moved the residual term from H0's per-hypothesis formula to a per-exploration-cell mean.
- Consequence: H1 was not a clean representation-only ablation; exploration received a new score pathway and activated immediately.
- Status: all prior H1–H4 formal results and the prior NO-GO decision are invalidated and retained only through this provenance note.
- Repair: restore H0's exact `p/(1+query_count)` per-hypothesis residual term; exploration cells contribute no hypothesis/residual mass. H3 may add mass only after a committed/simulated positive creates a hypothesis.
- Required action: rerun all 24 formal runs, all analyses, decision, independent review, and final seal.
