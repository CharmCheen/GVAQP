# P1 frozen-component parity audit

`PASS` — P1's C1 gap-only interval construction was compared against the authoritative `generic_events(..., "C1_gap_limited")` implementation on all 54 P0 video × selector × budget traces. Every interval list matched exactly.

The P1 analysis uses the repository's authoritative `MatchConfig(minimum_tiou=0.0, boundary_tolerance_sec=0.0)`, `match_events`, and `summarize_matches` functions for its secondary C1-versus-human EventF1/recall endpoint. This audit does not validate the human reference; it validates that P1 has not changed the frozen materializer or evaluator.
