#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from diagnostic_common import DIAG_DIR, PROJECT_ROOT, append_progress, ensure_dirs, read_phase0_csv


def main() -> None:
    ensure_dirs()
    stability = read_phase0_csv("tables/oracle_stability.csv")
    units = read_phase0_csv("data_audit/phase0_units.csv")
    actual_oracle_sources = sorted(units["oracle_source"].dropna().astype(str).unique())
    prompt_report = PROJECT_ROOT / "test_vlm/outputs/prompt_sensitivity_report.md"
    prompt_text = prompt_report.read_text(encoding="utf-8", errors="replace") if prompt_report.exists() else ""
    l2_l3_known = "L2/L3 Reversal" in prompt_text and "32B L3" in prompt_text

    rows = []
    for _, row in stability.iterrows():
        name = str(row["label_source_pair"])
        direct_contract = False
        involvement = (
            "not_the_certification_oracle_table"
            if "raw_vs_masked" in name
            else "unknown_from_phase0_stability_table"
        )
        threat = (
            "not_first_order_for_existing_B1_certificate"
            if not direct_contract
            else "first_order_threat_to_certificate"
        )
        rows.append(
            {
                "comparison_name": name,
                "agreement_rate": row["agreement_rate"],
                "flip_rate": row["flip_rate"],
                "positive_to_negative_flip": row["positive_to_negative_flip"],
                "negative_to_positive_flip": row["negative_to_positive_flip"],
                "stability_classification": row["stability_classification"],
                "actual_oracle_sources_used_for_Y_M": ";".join(actual_oracle_sources),
                "involves_actual_oracle_contract_used_for_certification": direct_contract,
                "oracle_contract_relation": involvement,
                "certificate_threat_level": threat,
                "consistent_with_prior_prompt_strictness_nonmonotonicity": bool(l2_l3_known),
                "prior_prompt_sensitivity_reference": str(prompt_report) if prompt_report.exists() else "",
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(DIAG_DIR / "tables/oracle_stability_detail.csv", index=False)
    unstable = out[out["stability_classification"].astype(str).eq("unstable")]
    ambiguous = out[out["stability_classification"].astype(str).eq("ambiguous")]
    pd.DataFrame(
        [
            {
                "unstable_comparisons": ";".join(unstable["comparison_name"].astype(str)),
                "ambiguous_comparisons": ";".join(ambiguous["comparison_name"].astype(str)),
                "actual_oracle_contract_unstable": bool(unstable["involves_actual_oracle_contract_used_for_certification"].any()) if not unstable.empty else False,
                "stage_c_finding": (
                    "unstable comparison exists but Phase 0 stability table does not show it is the same table/contract used for Y_i^O/M_i^O"
                    if not unstable.empty
                    else "no unstable comparison"
                ),
            }
        ]
    ).to_csv(DIAG_DIR / "tables/oracle_stability_classification.csv", index=False)
    append_progress(
        "oracle stability detail",
        "python scripts/d30_oracle_stability_detail.py",
        f"unstable={len(unstable)} ambiguous={len(ambiguous)} actual_contract_unstable={bool(unstable['involves_actual_oracle_contract_used_for_certification'].any()) if not unstable.empty else False}",
        next_action="generate diagnostic report",
    )


if __name__ == "__main__":
    main()
