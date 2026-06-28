#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from diagnostic_common import (
    DIAG_DIR,
    MANDATED_POWER_SENTENCE,
    append_progress,
    ensure_dirs,
    read_phase0_csv,
    read_phase0_text,
    write_manifest,
)


def main() -> None:
    ensure_dirs()
    write_manifest()
    units = read_phase0_csv("data_audit/phase0_units.csv")
    events = read_phase0_csv("data_audit/phase0_pseudo_events.csv")
    b1 = read_phase0_csv("tables/block_audit_no_repair_results.csv")
    report = read_phase0_text("reports/PHASE0_REPORT.md")

    total_events = int(len(events))
    sentence_present = MANDATED_POWER_SENTENCE in report
    constraint_violation = bool(total_events < 30 and not sentence_present)

    full = pd.DataFrame(
        [
            {
                "scope": "full_dataset",
                "total_units": int(len(units)),
                "total_oracle_positive_units": int(units["oracle_label"].astype(bool).sum()),
                "total_pseudo_events": total_events,
                "pseudo_events_in_certification_sample": pd.NA,
                "blocks_sampled": pd.NA,
                "blocks_with_at_least_one_event_in_sample": pd.NA,
                "exact_blocks_with_event_available": False,
                "note": "Full-dataset pseudo-event count is available from phase0_pseudo_events.csv.",
            }
        ]
    )
    cert = b1.copy()
    cert["pseudo_events_in_certification_sample"] = cert["Y_sample_sum_O"]
    cert["blocks_with_at_least_one_event_in_sample"] = pd.NA
    cert["exact_blocks_with_event_available"] = False
    cert["note"] = (
        "Phase 0 persisted trial-level Y_sample_sum_O but did not persist per-block sampled rows, "
        "so exact blocks_with_at_least_one_event_in_sample cannot be audited from the produced CSVs."
    )
    cert_cols = [
        "mode",
        "trial",
        "gamma",
        "delta",
        "theta",
        "block_size_seconds",
        "population_blocks",
        "sampled_blocks",
        "pseudo_events_in_certification_sample",
        "blocks_with_at_least_one_event_in_sample",
        "exact_blocks_with_event_available",
        "note",
    ]
    cert[cert_cols].to_csv(DIAG_DIR / "tables/certification_sample_accounting_by_trial.csv", index=False)

    cert_summary = (
        cert.groupby(["theta", "block_size_seconds", "gamma", "delta"], as_index=False)
        .agg(
            trials=("trial", "count"),
            population_blocks=("population_blocks", "mean"),
            blocks_sampled=("sampled_blocks", "mean"),
            pseudo_events_in_certification_sample_mean=("pseudo_events_in_certification_sample", "mean"),
            pseudo_events_in_certification_sample_min=("pseudo_events_in_certification_sample", "min"),
            pseudo_events_in_certification_sample_median=("pseudo_events_in_certification_sample", "median"),
            pseudo_events_in_certification_sample_max=("pseudo_events_in_certification_sample", "max"),
        )
        .sort_values(["theta", "block_size_seconds", "gamma", "delta"])
    )
    cert_summary["blocks_with_at_least_one_event_in_sample"] = pd.NA
    cert_summary["exact_blocks_with_event_available"] = False

    full.to_csv(DIAG_DIR / "tables/sample_size_full_dataset.csv", index=False)
    cert_summary.to_csv(DIAG_DIR / "tables/sample_size_certification_summary.csv", index=False)
    sentence = pd.DataFrame(
        [
            {
                "mandated_sentence": MANDATED_POWER_SENTENCE,
                "sentence_present_in_phase0_report": sentence_present,
                "total_pseudo_events": total_events,
                "constraint_violation": constraint_violation,
                "violation_reason": "Phase0 total pseudo-events < 30 and mandated caveat sentence is absent." if constraint_violation else "",
            }
        ]
    )
    sentence.to_csv(DIAG_DIR / "tables/phase0_report_sentence_check.csv", index=False)
    append_progress(
        "sample-size accounting",
        "python scripts/d10_sample_size_accounting.py",
        f"total_events={total_events}; sentence_present={sentence_present}; constraint_violation={constraint_violation}",
        next_action="run bound decomposition",
    )


if __name__ == "__main__":
    main()
