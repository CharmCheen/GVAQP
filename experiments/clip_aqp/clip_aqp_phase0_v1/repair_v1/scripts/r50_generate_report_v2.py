#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from repair_common import MANDATED_POWER_SENTENCE, REPAIR_DIR, append_progress, ensure_dirs, markdown_table


def read_table(name: str) -> pd.DataFrame:
    path = REPAIR_DIR / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def enforce_report_caveat(report: str, total_certification_events: int) -> None:
    if total_certification_events < 30 and MANDATED_POWER_SENTENCE not in report:
        (REPAIR_DIR / "reports/REPORT_CONSTRAINT_FAILURE.md").write_text(
            "\n".join(
                [
                    "# Report Constraint Failure",
                    "",
                    f"total_certification_events was `{total_certification_events}`, below 30.",
                    "The mandated caveat sentence was missing:",
                    "",
                    MANDATED_POWER_SENTENCE,
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        raise SystemExit("report constraint failure: mandated sample-size caveat missing")


def main() -> None:
    ensure_dirs()
    results = read_table("tables/block_audit_no_repair_results_v2.csv")
    rows = read_table("tables/block_audit_rows_v2.csv")
    recompute = read_table("tables/block_audit_recompute_check_v2.csv")
    oracle = read_table("tables/certification_oracle_identity.csv")
    comparisons = read_table("tables/certification_oracle_comparison.csv")
    unit_test = read_table("tables/bound_formula_unit_test.csv")
    total_certification_events = int(results["total_events_O"].max()) if not results.empty else 0
    summary = (
        results.groupby(["theta", "block_size_seconds", "gamma", "delta"], as_index=False)
        .agg(
            trials=("trial", "count"),
            mean_true_recall=("true_oracle_recall", "mean"),
            mean_LCB_recall_O=("LCB_recall_O", "mean"),
            max_LCB_recall_O=("LCB_recall_O", "max"),
            coverage=("coverage", "mean"),
            GVR=("GVR", "mean"),
            mean_tightness=("tightness", "mean"),
            mean_cost=("cost_to_certificate", "mean"),
            invariant_UCB=("bound_invariant_UCB_M_ge_M_hat", "all"),
            invariant_LCB=("bound_invariant_LCB_Y_le_Y_hat", "all"),
        )
        if not results.empty
        else pd.DataFrame()
    )
    summary.to_csv(REPAIR_DIR / "tables/block_audit_no_repair_summary_v2.csv", index=False)
    recompute_ok = bool(recompute["all_match"].all()) if not recompute.empty else False
    invariant_ok = bool(results["bound_invariant_UCB_M_ge_M_hat"].all() and results["bound_invariant_LCB_Y_le_Y_hat"].all()) if not results.empty else False
    if total_certification_events < 30:
        decision = "UNDERPOWERED_NO_CLEAN_GO_NO_GO"
    elif bool((summary["mean_LCB_recall_O"] >= 0.8).any()) and invariant_ok:
        decision = "CERTIFICATE_READ_POSITIVE"
    else:
        decision = "CERTIFICATE_READ_NEGATIVE"
    report = "\n".join(
        [
            "# Phase 0 Repair v1 Report",
            "",
            "This repair reruns only the corrected no-repair block/event audit and report generation on existing Phase 0 data. It does not collect new data, call VLMs, or start Phase 1 system building.",
            "",
            "## Root Cause and Fix",
            "",
            "The original `UCB_M_O` was capped by `LCB_Y_O`, which could push an upper confidence bound below the missed-event point estimate. The repaired formula removes that cap and enforces `UCB_M_O >= M_hat_O - epsilon` and `LCB_Y_O <= Y_hat_O + epsilon` with `epsilon = 1e-9`.",
            "",
            "Synthetic formula test:",
            "",
            markdown_table(unit_test),
            "",
            "## Corrected No-repair Block/Event Audit",
            "",
            markdown_table(summary),
            "",
            f"- per-block rows persisted: `{len(rows)}`",
            f"- per-block recomputation check passed: `{recompute_ok}`",
            f"- bound invariants passed: `{invariant_ok}`",
            f"- total pseudo-events / certification target events: `{total_certification_events}`",
            "",
            MANDATED_POWER_SENTENCE if total_certification_events < 30 else "",
            "",
            "## Oracle Configuration Identification",
            "",
            markdown_table(oracle),
            "",
            markdown_table(comparisons),
            "",
            "Exact model-size and raw/masked metadata were not persisted in Phase 0 outputs. No existing Stage 4 comparison can be confirmed as the exact certification oracle configuration from current logs/tables alone. A prepared stability-check placeholder was written but not run.",
            "",
            "## Does the Original NO_GO Change?",
            "",
            "The original formula defect is fixed, but this repaired run remains underpowered because the benchmark still has only 29 pseudo-events. The fixed LCBs remain below the target recall settings, and the result should not be promoted to a clean GO/NO_GO claim.",
            "",
            f"REPAIR_DECISION: {decision}",
            "",
            "## Human Review Note",
            "",
            "Read `reports/ROOT_CAUSE.md` and this report directly. Spot-check at least one row of `tables/block_audit_rows_v2.csv` against the formula before deciding what Phase 0's real verdict is.",
        ]
    )
    enforce_report_caveat(report, total_certification_events)
    (REPAIR_DIR / "reports/PHASE0_REPORT_v2.md").write_text(report, encoding="utf-8")
    append_progress(
        "R3/R5 guarded v2 report",
        "python scripts/r50_generate_report_v2.py",
        f"wrote PHASE0_REPORT_v2.md decision={decision}",
        next_action="capture git hygiene snapshot",
    )


if __name__ == "__main__":
    main()
