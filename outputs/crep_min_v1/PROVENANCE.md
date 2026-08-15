# PROVENANCE.md — CREP-Min v1

Date: 2026-08-14. CPU-only macOS checkout. No GPU, no model inference, no
human labels read, no project state files modified.

## Inputs
- Frozen semantics: this package (OPERATIONAL_SEMANTICS.md/.json).
- Replay data: outputs from the two preceding CPU gates
  (mab_cpu_gate_v1/, eraea_cpu_novelty_gate_v1/) and the frozen manifests
  they consume (P2 TRACE_MANIFEST, qwen32 raw, raw_unit_detections,
  PROXY_REGIME_MANIFEST, RC_SEM manifest, Guangzhou physical artifacts).
- Engine fidelity anchor: 252/252 exact reproduction of P2 TRACE_MANIFEST
  EventF1/TP/FP/FN (scripts/mab_cpu_gate/validate_engine.py).

## Outputs (outputs/crep_min_v1/)
- OPERATIONAL_SEMANTICS.md — frozen state/action-transition contract
- REPLAY_CLOSURE.md — six closures A-F (+G,H derived)
- COUNTEREXAMPLES.json + COUNTEREXAMPLE_SUITE.md — C1-C8 two-world witnesses
- CLAIM_CERTIFICATES.csv — 8 ledger claims, certificate status per claim
- PARTIAL_INTERVALS.csv — 252 Q_DRIVER trace rows, interval width 0.0 (exact
  given recorded outcomes)
- PARTIAL_INTERVALS_UNIVERSE.csv — full-universe status: NOT_IDENTIFIABLE
  (missing FINAL_UNIT_REFERENCE.parquet, recorded sha256 4f732859...)
- CREP_GATE_METRICS.json — must-satisfy + paper-potential checks
- FINAL_DECISION.md — GO_CREP_PAPER_CANDIDATE
- REPRODUCE.sh

## Method notes
- Counterexample suite: constructive two-world witnesses with exact integer
  values; each world reproduces the shared log; flip inequalities are exact.
- Certificates: replay_status is assigned per claim by mapping the six
  closures against the artifacts each claim actually uses; version pins are
  the protocol hashes recorded in the earlier gates.
- Partial intervals: over the queried universe the outcome law is fully known
  (union labels), so the interval width is 0; over the unqueried universe the
  gap is a provenance gap (missing parquet), not an estimable interval.

## Limitations
- Reversal-rate witness (0.2222) is MODEL_RELATIVE; human external validity
  still blocked (0 labels).
- C2/C3 witnesses are abstract constructive cases, not empirical endogenous
  failures (none exist locally by construction).
- CLAIM_1/CLAIM_8 rest on single-domain / single-source evidence; their
  certificates are corpus-scoped.
