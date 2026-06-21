#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from repair_common import PHASE0_DIR, PROJECT_ROOT, REPAIR_DIR, append_progress, ensure_dirs, load_units


def infer_from_sources() -> dict:
    units = load_units()
    oracle_sources = sorted(units["oracle_source"].dropna().astype(str).unique())
    inventory = PHASE0_DIR / "reports/DATA_AUDIT.md"
    phase0_report = PHASE0_DIR / "reports/PHASE0_REPORT.md"
    text = ""
    for path in [inventory, phase0_report]:
        if path.exists():
            text += "\n" + path.read_text(encoding="utf-8", errors="replace")
    likely_files = [
        PROJECT_ROOT / "test_vlm/focused_validation_outputs/04_temporal_concentration/positive_timeline.csv",
        PROJECT_ROOT / "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv",
    ]
    source_files = [str(path) for path in likely_files if path.exists()]
    config = {
        "oracle_source_values_in_phase0_units": ";".join(oracle_sources),
        "certification_oracle_label_table": source_files[-1] if source_files else "",
        "model_size": "not_recorded_in_phase0_units",
        "raw_or_masked": "not_recorded_in_phase0_units",
        "prompt_variant": "conservative_vlm_pseudo_oracle",
        "inference_from_existing_logs": "Phase0 units record only conservative_vlm_pseudo_oracle; exact model size and raw/masked setting are not persisted in Phase0 outputs.",
    }
    if "vlm_oracle_expanded" in text:
        config["certification_oracle_label_table"] = str(PROJECT_ROOT / "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv")
    return config


def main() -> None:
    ensure_dirs()
    config = infer_from_sources()
    stability = pd.read_csv(PHASE0_DIR / "tables/oracle_stability.csv")
    rows = []
    for _, row in stability.iterrows():
        comparison = str(row["label_source_pair"])
        match = False
        implication = "No direct match: Phase 0 did not persist enough oracle metadata to map this comparison to the exact Y_i^O/M_i^O oracle."
        rows.append(
            {
                "comparison_name": comparison,
                "stability_classification": row["stability_classification"],
                "agreement_rate": row["agreement_rate"],
                "flip_rate": row["flip_rate"],
                "matches_certification_oracle": match,
                "implication": implication,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(REPAIR_DIR / "tables/certification_oracle_comparison.csv", index=False)
    pd.DataFrame([config]).to_csv(REPAIR_DIR / "tables/certification_oracle_identity.csv", index=False)
    script = REPAIR_DIR / "scripts/prepared_exact_oracle_stability_check.py"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                '"""Prepared only; do not run without explicit approval.',
                "",
                "This placeholder documents that Phase 0 did not persist model-size/raw-masked",
                "metadata for the exact conservative_vlm_pseudo_oracle table. A valid exact",
                "stability check would need explicit approval and a concrete oracle contract.",
                '"""',
                "",
                "raise SystemExit('Prepared only. Do not run without explicit approval and exact oracle metadata.')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (REPAIR_DIR / "reports/CERTIFICATION_ORACLE_IDENTITY.md").write_text(
        "\n".join(
            [
                "# Certification Oracle Identity",
                "",
                f"- oracle_source in phase0_units: `{config['oracle_source_values_in_phase0_units']}`",
                f"- likely label table: `{config['certification_oracle_label_table']}`",
                "- model size: `not_recorded_in_phase0_units`",
                "- raw/masked setting: `not_recorded_in_phase0_units`",
                "- prompt variant: `conservative_vlm_pseudo_oracle`",
                "",
                "No existing Stage 4 comparison can be confirmed as the exact certification oracle configuration from Phase 0 outputs alone. The repair pass therefore prepares but does not run `scripts/prepared_exact_oracle_stability_check.py`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    append_progress(
        "R4 identify certification oracle",
        "python scripts/r40_identify_certification_oracle.py",
        "exact model/raw-masked metadata not persisted; prepared stability script without running it",
        next_action="generate guarded v2 report",
    )


if __name__ == "__main__":
    main()
