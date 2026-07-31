# YOLO-guided region scheduling

- Original hypothesis: low-rate YOLO-visible signals could rank regions well enough to improve SCAN allocation.
- Scope: two design videos; frozen pseudo-reference; no validation/test videos.
- Main metrics: preview cost caps H002 0.052925 and H003 0.070582; both preregistered static Gates rejected.
- Result/failure mechanism: ranking signal existed, but selective high-rate detection and directional motion were not robust or cost-effective on both videos.
- Failed Gate: static observability; scheduler and new physical validation were prohibited afterward.
- Current disposition: excluded; safe geometric coverage is the replacement.
- Source: `outputs/scan_innovation_agentic_loop_v1/reports/FINAL_ALGORITHM_DECISION.md` and `INDEPENDENT_FINAL_AUDIT.json`, commit `5047241b0561b911b9a519b18e8e7591c0074e70`.
