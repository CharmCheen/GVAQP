# Failure modes

| Failure | Detection | Frozen response | Claim impact |
|---|---|---|---|
| Brief event falls between frames | Physical FN against evaluator | Count as miss; no prompt tuning | May kill mechanism |
| Long-window context overload | Missing or conflated events | Count exact output; preserve raw response | May kill mechanism |
| Hallucinated event | Unmatched parsed event | False positive | Lowers F1 |
| Duplicate across overlaps | Same event in adjacent fragments | Deterministic owner/reconcile | Component ablation |
| Boundary truncation | Report touches input boundary | Mark truncated; owner fragment retained conservatively | Boundary metric limitation |
| Parser failure/abstain | Schema validation | Dense fallback if call cap permits | Fully charged |
| OOM/runtime failure | Exception and GPU ledger | Preserve attempt, execute registered fallback | Fully charged; may make run incomplete |
| Cost model error | Measured versus predicted runtime | Use measured result for gate | Can reject optimizer |
| Reference leakage | Source/config audit | Fail experiment | `RESEARCH_BLOCKED` |
| Single-video overclaim | Claim audit | Scope to oracle-relative development evidence | Prevent top-tier-ready decision |

