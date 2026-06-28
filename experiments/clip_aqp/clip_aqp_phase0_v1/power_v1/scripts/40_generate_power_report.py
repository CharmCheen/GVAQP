#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from power_common import POWER_DIR, markdown_table, append_progress, ensure_dirs


def decide(summary: pd.DataFrame, comparison: pd.DataFrame) -> str:
    certified = summary[summary["mode"] == "certified_srs"].copy()
    gvr_ok = bool((certified["GVR"] <= 0.10).all())
    reasonable = certified[certified["target_event_count"] <= 500]
    if not reasonable.empty and bool((reasonable["fraction_vacuous"] < 0.5).any()) and gvr_ok:
        return "POWER_DECISION: EXPAND_BENCHMARK_TO_N_EVENTS"
    high = certified[certified["target_event_count"].isin([1000, 2000])]
    boot_gap_high = comparison[comparison["target_event_count"].isin([1000, 2000])]["bootstrap_minus_certified_lcb"].mean()
    if not high.empty and bool((high["fraction_vacuous"] > 0.8).all()) and boot_gap_high > 0.10:
        return "POWER_DECISION: METHOD_BOUND_TOO_LOOSE"
    return "POWER_DECISION: INCONCLUSIVE_NEEDS_REAL_EVENT_BOUNDARIES"


def main() -> None:
    ensure_dirs()
    params = pd.read_csv(POWER_DIR / "tables/empirical_params.csv")
    validation = pd.read_csv(POWER_DIR / "tables/input_validation.csv")
    summary = pd.read_csv(POWER_DIR / "tables/power_scaling_summary.csv")
    comparison = pd.read_csv(POWER_DIR / "tables/mode_comparison.csv")
    decision = decide(summary, comparison)
    certified = summary[summary["mode"] == "certified_srs"].copy()
    strat = comparison[["target_event_count", "stratified_minus_certified_lcb"]].copy()
    boot = comparison[["target_event_count", "bootstrap_minus_certified_lcb"]].copy()
    useful = certified[certified["fraction_vacuous"] < 0.5]
    first_nonvacuous = "not reached"
    if not useful.empty:
        first_nonvacuous = str(int(useful.sort_values("target_event_count").iloc[0]["target_event_count"]))
    certified_key = certified[certified["target_event_count"].isin([100, 200, 500, 1000])][
        ["target_event_count", "LCB_recall_median", "fraction_vacuous", "tightness_mean", "GVR"]
    ].copy()
    report = "\n".join(
        [
            "# Phase 0.6 Power/Scaling Report",
            "",
            "This simulation uses repaired Phase 0 outputs only. It does not run VLM, download data, train models, build a perception stack, modify `repair_v1`, or fabricate event boundaries.",
            "",
            "## Input Validation",
            "",
            markdown_table(validation),
            "",
            "## Empirical Block Model",
            "",
            markdown_table(params),
            "",
            "The reference model uses the repaired rows at theta=0.3, block_size=10s, gamma=0.8, delta=0.1 because that was the least conservative repaired condition and is the most favorable read for whether scaling alone helps.",
            "",
            "## Power Scaling Summary",
            "",
            markdown_table(summary),
            "",
            "## Mode Comparison",
            "",
            markdown_table(comparison),
            "",
            "Mode C (`bootstrap_diagnostic`) is practical diagnostic only. It is not a certified proof and must not be described as a valid recall certificate.",
            "",
            "## Answers",
            "",
            f"- Is current UNDERPOWERED likely caused by only 29 pseudo-events? Certified mode becomes non-vacuous around target event count `{first_nonvacuous}` under the synthetic pseudo-event assumptions, so event count is a major contributor if that value is finite. The result remains pseudo-event based.",
            "- Around how many events are needed before LCB_recall becomes non-vacuous? See `tables/power_scaling_summary.csv`; the first certified event count with fraction_vacuous < 0.5 is reported above.",
            "- Does repaired certified bound become useful at 100 / 200 / 500 / 1000 events? Certified-mode details:",
            "",
            markdown_table(certified_key),
            "",
            f"- Does stratification materially improve tightness? Median stratified-minus-certified LCB ranges from `{strat['stratified_minus_certified_lcb'].min():.3f}` to `{strat['stratified_minus_certified_lcb'].max():.3f}`; this is source/video stratification because no candidate/proxy region field exists in `block_audit_rows_v2.csv`.",
            f"- Is practical bootstrap much tighter than certified mode? Bootstrap-minus-certified median LCB ranges from `{boot['bootstrap_minus_certified_lcb'].min():.3f}` to `{boot['bootstrap_minus_certified_lcb'].max():.3f}`, but bootstrap is diagnostic only.",
            "- Should the next step be expanding benchmark, changing bound, or collecting clean event boundaries? The safest next action is to collect/construct clean event boundaries or expand the benchmark only as a pseudo-event stress test; do not treat this as human-ground-truth certificate evidence.",
            "",
            "## Limitations",
            "",
            "- Synthetic populations are bootstrapped from repaired sampled block rows, not new real videos.",
            "- Event boundaries remain pseudo-events; this can dominate the conclusion.",
            "- Stratified mode uses `video_id` because candidate/proxy region fields are not available in the repaired block rows.",
            "- Bootstrap mode is not certified proof.",
            "",
            decision,
            "",
        ]
    )
    (POWER_DIR / "reports/POWER_REPORT.md").write_text(report, encoding="utf-8")
    pd.DataFrame([{"power_decision": decision}]).to_csv(POWER_DIR / "tables/power_decision.csv", index=False)
    append_progress(
        "generate power report",
        "python scripts/40_generate_power_report.py",
        f"wrote POWER_REPORT.md with {decision}",
    )


if __name__ == "__main__":
    main()
