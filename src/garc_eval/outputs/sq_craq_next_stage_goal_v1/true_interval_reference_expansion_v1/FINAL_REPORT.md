# True Interval Reference Expansion V1

## Answers

1. Current reference is insufficient because it has only `6` true interval events and `14` point-anchor events.
2. Expand to at least 20 true interval events; 30 is preferable for diagnostics.
3. Priority review candidates: existing interval events, top p_answer/high-score candidates, hard false positives, and outside-audit high-risk intervals.
4. Existing point-anchor events should be excluded from interval-IoU main evaluation.
5. Human review should produce a new independent corrected reference table consumed by later SQ-CRAQ replay; do not overwrite existing artifacts.

Review queue: `208` rows. No human labels were fabricated.
