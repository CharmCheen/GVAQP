# Decision Ledger

## Cycle 00 — 2026-07-29 — OBSERVE / CONTRACT FREEZE

- Decision: `CONTINUE`; run oracle-adequacy preflight before a full 1,475-unit oracle pass.
- Decisive evidence: the old complete Dali/Wuhan oracle uses different query semantics; the prior 32B Hangzhou probe includes a qualitatively unsupported positive; direct prior 32B latency implies a full pass is substantial.
- Rejected action: reuse old Q1/Q2 labels as the new operational reference. Reason: semantic mismatch would change the frozen objective.
- Rejected action: train a controller from existing binary-SMDP pilot rows. Reason: only four formally ineligible rows exist, with no VERIFY-better states and unsafe latency support.
- Preserved failure evidence: binary-SMDP `INSUFFICIENT_EVIDENCE`, V0 imputed costs, overrun counts, 32B disagreement, parse/unknown policies, and all historical result directories remain unchanged.
- Next highest-value action: materialize and verify the frozen grid, then preregister the smallest cross-video 32B stability sample.
- Revision trigger: if H1 fails, stop the full oracle launch and revise/declare insufficient evidence; if H1 passes, run the full oracle and test H2 before controller work.
