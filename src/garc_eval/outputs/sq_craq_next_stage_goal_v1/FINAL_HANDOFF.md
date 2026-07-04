# SQ-CRAQ Next Stage Handoff V1

## Overall Verdict

- CILS retained as core algorithm: **No**.
- CILS downgraded to optional selector / ablation: **Yes**.
- Audited interval envelope should become mainline: **Yes, diagnostic mainline**.
- Reference expansion blocks formal claims: **Yes**.
- DrivingDojo role: answer-compatible cheap-signal probe corpus, not final AQP benchmark.

## Key Paths

- CILS value-add report: `src/garc_eval/outputs/sq_craq_next_stage_goal_v1/cils_vs_topk_value_add_audit_v1/FINAL_REPORT.md`
- CILS comparison CSV: `src/garc_eval/outputs/sq_craq_next_stage_goal_v1/cils_vs_topk_value_add_audit_v1/matched_value_add_comparison.csv`
- Envelope report: `src/garc_eval/outputs/sq_craq_next_stage_goal_v1/audited_interval_envelope_mvp_v1/FINAL_REPORT.md`
- Envelope comparison CSV: `src/garc_eval/outputs/sq_craq_next_stage_goal_v1/audited_interval_envelope_mvp_v1/envelope_baseline_comparison.csv`
- Reference expansion report: `src/garc_eval/outputs/sq_craq_next_stage_goal_v1/true_interval_reference_expansion_v1/FINAL_REPORT.md`
- Review queue CSV: `src/garc_eval/outputs/sq_craq_next_stage_goal_v1/true_interval_reference_expansion_v1/true_interval_review_queue.csv`
- DrivingDojo report: `src/garc_eval/outputs/sq_craq_next_stage_goal_v1/drivingdojo_signal_probe_v1/FINAL_REPORT.md`

## Decision Table

| Question | Evidence | Verdict | Next action |
| --- | --- | --- | --- |
| Does CILS add value over top-k? | cils_vs_topk matched comparisons and synthetic prior show neutral/no stable value-add. | CILS optional only | Do not use CILS as core claim. |
| Can outside audit detect miss risk? | audited envelope replay records outside positives and CANNOT_CERTIFY cases. | Diagnostic yes, formal no | Develop audited_interval_envelope_mvp_v2 after reference expansion. |
| Is current reference enough? | six interval_eval events, fourteen point-anchor events. | No | Execute true interval reference expansion. |
| Should DrivingDojo be used now? | scaffold only; no downloads or heavy model runs. | Only as signal-probe corpus | Use small authorized sample only. |

## Recommended Next Task

**true_interval_reference_expansion execution**.

Rationale: CILS value-add is neutral/negative and audited-envelope replay remains diagnostic under a six-event interval reference. Expanding the true interval reference is the bottleneck for stronger SQ-CRAQ claims.

## No Overclaim Statement

All current conclusions remain diagnostic. The true interval event reference is too small. Synthetic label-informed signals cannot represent real non-leak cheap-signal performance. A formal guarantee has not been established. If CILS has no value-add, it should not be used as the core algorithm claim.
