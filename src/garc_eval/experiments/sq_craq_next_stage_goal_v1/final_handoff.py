from __future__ import annotations

import pandas as pd

from common_io import OUT, ROOT, md_table, write_text


def read_text(path):
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main() -> None:
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    (OUT / "data_manifest").mkdir(parents=True, exist_ok=True)
    (OUT / "config").mkdir(parents=True, exist_ok=True)
    cils_report = OUT / "cils_vs_topk_value_add_audit_v1/FINAL_REPORT.md"
    env_report = OUT / "audited_interval_envelope_mvp_v1/FINAL_REPORT.md"
    ref_report = OUT / "true_interval_reference_expansion_v1/FINAL_REPORT.md"
    dojo_report = OUT / "drivingdojo_signal_probe_v1/FINAL_REPORT.md"
    cils_core = "No"
    envelope_main = "Yes, diagnostic mainline"
    decision = pd.DataFrame(
        [
            {
                "Question": "Does CILS add value over top-k?",
                "Evidence": "cils_vs_topk matched comparisons and synthetic prior show neutral/no stable value-add.",
                "Verdict": "CILS optional only",
                "Next action": "Do not use CILS as core claim.",
            },
            {
                "Question": "Can outside audit detect miss risk?",
                "Evidence": "audited envelope replay records outside positives and CANNOT_CERTIFY cases.",
                "Verdict": "Diagnostic yes, formal no",
                "Next action": "Develop audited_interval_envelope_mvp_v2 after reference expansion.",
            },
            {
                "Question": "Is current reference enough?",
                "Evidence": "six interval_eval events, fourteen point-anchor events.",
                "Verdict": "No",
                "Next action": "Execute true interval reference expansion.",
            },
            {
                "Question": "Should DrivingDojo be used now?",
                "Evidence": "scaffold only; no downloads or heavy model runs.",
                "Verdict": "Only as signal-probe corpus",
                "Next action": "Use small authorized sample only.",
            },
        ]
    )
    write_text(
        OUT / "FINAL_HANDOFF.md",
        f"""# SQ-CRAQ Next Stage Handoff V1

## Overall Verdict

- CILS retained as core algorithm: **{cils_core}**.
- CILS downgraded to optional selector / ablation: **Yes**.
- Audited interval envelope should become mainline: **{envelope_main}**.
- Reference expansion blocks formal claims: **Yes**.
- DrivingDojo role: answer-compatible cheap-signal probe corpus, not final AQP benchmark.

## Key Paths

- CILS value-add report: `{cils_report.relative_to(ROOT)}`
- CILS comparison CSV: `src/garc_eval/outputs/sq_craq_next_stage_goal_v1/cils_vs_topk_value_add_audit_v1/matched_value_add_comparison.csv`
- Envelope report: `{env_report.relative_to(ROOT)}`
- Envelope comparison CSV: `src/garc_eval/outputs/sq_craq_next_stage_goal_v1/audited_interval_envelope_mvp_v1/envelope_baseline_comparison.csv`
- Reference expansion report: `{ref_report.relative_to(ROOT)}`
- Review queue CSV: `src/garc_eval/outputs/sq_craq_next_stage_goal_v1/true_interval_reference_expansion_v1/true_interval_review_queue.csv`
- DrivingDojo report: `{dojo_report.relative_to(ROOT)}`

## Decision Table

{md_table(decision, 10)}

## Recommended Next Task

**true_interval_reference_expansion execution**.

Rationale: CILS value-add is neutral/negative and audited-envelope replay remains diagnostic under a six-event interval reference. Expanding the true interval reference is the bottleneck for stronger SQ-CRAQ claims.

## No Overclaim Statement

All current conclusions remain diagnostic. The true interval event reference is too small. Synthetic label-informed signals cannot represent real non-leak cheap-signal performance. A formal guarantee has not been established. If CILS has no value-add, it should not be used as the core algorithm claim.
""",
    )
    write_text(
        OUT / "logs/progress.md",
        """# Progress

- Generated cils_vs_topk_value_add_audit_v1.
- Generated audited_interval_envelope_mvp_v1.
- Generated true_interval_reference_expansion_v1.
- Generated drivingdojo_signal_probe_v1.
- Generated FINAL_HANDOFF.md.
""",
    )
    write_text(
        OUT / "config/experiment_config.md",
        """# SQ-CRAQ Next Stage Config

No model inference, downloads, or existing-output rewrites. All replay outputs are DIAGNOSTIC_ONLY.
""",
    )


if __name__ == "__main__":
    main()
