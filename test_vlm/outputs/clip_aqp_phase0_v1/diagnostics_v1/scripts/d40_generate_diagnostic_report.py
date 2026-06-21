#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from diagnostic_common import DIAG_DIR, append_progress, ensure_dirs, git_status_for, markdown_table


def read_diag(rel: str) -> pd.DataFrame:
    path = DIAG_DIR / rel
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def main() -> None:
    ensure_dirs()
    full = read_diag("tables/sample_size_full_dataset.csv")
    cert = read_diag("tables/sample_size_certification_summary.csv")
    sentence = read_diag("tables/phase0_report_sentence_check.csv")
    bsum = read_diag("tables/bound_decomposition_summary.csv")
    power = read_diag("tables/bound_power_curve.csv")
    bclass = read_diag("tables/bound_classification.csv")
    odetail = read_diag("tables/oracle_stability_detail.csv")
    oclass = read_diag("tables/oracle_stability_classification.csv")
    git_status = git_status_for(["AGENTS.md", "docs/clip_aqp/CASQ_CODEX_BRIEF_V11.md"])
    agents_modified = "AGENTS.md" in git_status

    stage_b_class = str(bclass["stage_b_classification"].iloc[0]) if not bclass.empty else "INCONCLUSIVE_NEEDS_CODE_REVIEW"
    actual_oracle_unstable = bool(oclass["actual_oracle_contract_unstable"].iloc[0]) if not oclass.empty else False
    if stage_b_class == "BOUND_LOOKS_STRUCTURALLY_TOO_LOOSE" or actual_oracle_unstable:
        revised = "CONFIRMED_NO_GO"
    elif stage_b_class == "BOUND_LOOKS_SOUND_BUT_UNDERPOWERED" and not actual_oracle_unstable:
        revised = "UNDERPOWERED_NEEDS_LARGER_BENCHMARK"
    else:
        revised = "INCONCLUSIVE_NEEDS_CODE_REVIEW"

    lines = [
        "# Phase 0 NO_GO Diagnostic Report",
        "",
        "This diagnostic stage re-analyzes existing Phase 0 outputs only. It does not build new systems, collect new data, or call any VLM.",
        "",
    ]
    if agents_modified:
        lines += [
            "## Human Review Flag",
            "",
            "`git status` shows `AGENTS.md` is modified. Per instruction, this diagnostic does not investigate or revert it.",
            "",
            "```text",
            git_status,
            "```",
            "",
        ]
    lines += [
        "## 1. Sample-size accounting (Stage A)",
        "",
        markdown_table(full),
        "",
        "Certification-sample summary by configured condition:",
        "",
        markdown_table(cert),
        "",
        "Phase 0 mandated caveat sentence check:",
        "",
        markdown_table(sentence),
        "",
        "Diagnostic finding: the full dataset has 29 pseudo-events, below the 30-event bar. The Phase 0 report did not contain the exact mandated caveat sentence, so this is a reporting constraint violation. Exact `blocks_with_at_least_one_event_in_sample` cannot be audited from the produced CSVs because Phase 0 persisted trial-level aggregates rather than per-block sampled rows.",
        "",
        "## 2. Bound decomposition and power curve (Stage B)",
        "",
        "Aggregate decomposition:",
        "",
        markdown_table(
            bsum[
                [
                    "theta",
                    "block_size_seconds",
                    "delta",
                    "sampled_blocks",
                    "point_estimate_recall_mean",
                    "LCB_recall_O_mean",
                    "M_concentration_term_median",
                    "Y_concentration_term_median",
                    "has_negative_UCB_M_margin",
                    "point_minus_LCB_gap_mean",
                    "true_oracle_recall",
                ]
            ]
            if not bsum.empty
            else bsum
        ),
        "",
        "Power curve using the same bound construction and observed aggregate variance structure:",
        "",
        markdown_table(power),
        "",
        "Stage B classification:",
        "",
        markdown_table(bclass),
        "",
        "Interpretation: Stage B is not clean enough to accept as a statistical power finding. The decomposition found negative `UCB_M_O - M_hat` margins, meaning the reported UCB for missed events can be lower than the uncorrected point estimate. That is inconsistent with the documented upper-bound interpretation and should be reviewed before using the LCB to diagnose method viability. Separately, the fixed returned clips have low point recall, so high LCB targets would remain impossible unless candidate recall improves.",
        "",
        "## 3. Oracle stability detail (Stage C)",
        "",
        markdown_table(odetail),
        "",
        markdown_table(oclass),
        "",
        "The unstable comparison is `32b_raw_vs_masked`; the ambiguous comparison is `8b_raw_vs_masked`. These are raw-vs-masked comparison checks and are not shown by the Phase 0 stability table to be the exact conservative VLM pseudo-oracle table used for `Y_i^O/M_i^O` in B1. They do not directly invalidate the already computed Stage B arithmetic, but they remain a warning for any future oracle/prompt change. This is consistent with the prior prompt-sensitivity finding that 32B L2/L3 behavior was non-monotonic under different prompt wording.",
        "",
        "## 4. Revised classification",
        "",
        f"`{revised}`",
        "",
        "Reason: Stage B surfaces a bound-construction inconsistency rather than a clean statistical power result. Stage C does not prove that the exact certification oracle contract is unstable, but it does flag nearby oracle sensitivity.",
        "",
        "## 5. Recommended next action",
        "",
        "Do not accept the original NO_GO as final evidence that the whole G-ClipAQP direction is impossible. First review the Stage B bound implementation/formula and require per-block certification-sample outputs so the sample design can be audited exactly. Also treat the current pseudo-event benchmark as under the 30-event reporting threshold.",
        "",
        "Before deciding whether to scale up the benchmark, change the oracle, or abandon the certificate construction, manually read Stage B's power-curve table and Stage C's per-comparison numbers directly rather than relying on the revised classification label alone.",
        "",
    ]
    (DIAG_DIR / "reports/DIAGNOSTIC_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    pd.DataFrame([{"revised_classification": revised, "stage_b_classification": stage_b_class, "actual_oracle_contract_unstable": actual_oracle_unstable}]).to_csv(
        DIAG_DIR / "tables/revised_classification.csv", index=False
    )
    append_progress(
        "diagnostic report",
        "python scripts/d40_generate_diagnostic_report.py",
        f"wrote DIAGNOSTIC_REPORT.md revised_classification={revised}",
    )


if __name__ == "__main__":
    main()
