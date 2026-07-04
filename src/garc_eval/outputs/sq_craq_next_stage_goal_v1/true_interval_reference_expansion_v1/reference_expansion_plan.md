# Reference Expansion Plan

- Current interval events: `6`.
- Target: at least 20 true interval events for a minimal reference gate; preferably 30 for more stable diagnostics.
- Review queue rows: `208`.
- Priority: existing interval events for consistency, top p_answer/high-score candidates, outside-audit high-risk proxies, and hard false positives.
- After review, write corrected rows back as a new independent reference table; do not overwrite `reference_events.csv`.
