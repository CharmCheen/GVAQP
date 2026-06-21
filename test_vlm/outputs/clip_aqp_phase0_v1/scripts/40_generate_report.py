#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import pandas as pd

from phase0_common import OUT_DIR, append_progress, ensure_dirs, markdown_table


def read_csv(name: str) -> pd.DataFrame:
    path = OUT_DIR / name
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def summarize_bool_rate(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return 0.0
    return float(df[col].astype(bool).mean())


def main() -> None:
    ensure_dirs()
    inventory = read_csv("data_audit/existing_data_inventory.csv")
    units = read_csv("data_audit/phase0_units.csv")
    events = read_csv("data_audit/phase0_pseudo_events.csv")
    supg = read_csv("tables/supg_stitch_results.csv")
    supg_summary = read_csv("tables/supg_stitch_summary.csv")
    b1 = read_csv("tables/block_audit_no_repair_results.csv")
    b2 = read_csv("tables/block_audit_repair_fresh_cert_results.csv")
    stability = read_csv("tables/oracle_stability.csv")

    has_clean_boundaries = bool((not units.empty) and units["has_event_boundary"].astype(bool).any())
    supg_fails = bool((not supg_summary.empty) and (supg_summary["GVR"] > supg_summary["delta"]).any())
    b1_conservative = bool((not b1.empty) and (b1["coverage"].mean() >= 0.90))
    b1_nonvacuous = bool((not b1.empty) and (b1["LCB_recall_O"].fillna(0).mean() > 0.05))
    b1_cost_below_full = bool((not b1.empty) and (b1["cost_to_certificate"].mean() < b1["population_blocks"].mean()))
    oracle_ok = bool((not stability.empty) and not (stability["stability_classification"] == "unstable").any())
    total_cert_events = int(b1["Y_sample_sum_O"].sum()) if not b1.empty and "Y_sample_sum_O" in b1.columns else 0

    if supg_fails and b1_conservative and b1_nonvacuous and b1_cost_below_full and oracle_ok and has_clean_boundaries:
        decision = "GO"
    elif supg_fails and b1_conservative and b1_nonvacuous and b1_cost_below_full and oracle_ok and not has_clean_boundaries:
        decision = "PARTIAL_GO_NEED_CLEAN_EVENT_BOUNDARIES"
    else:
        decision = "NO_GO"

    b2_status = "not run"
    if not b2.empty:
        if "stage_status" in b2.columns:
            b2_status = str(b2["stage_status"].iloc[0])
        else:
            b2_status = f"ran {len(b2)} fresh-certification trials; coverage={summarize_bool_rate(b2, 'coverage'):.3f}"

    lines = [
        "# Phase 0 Report: Clip-level AQP Guarantee Feasibility",
        "",
        "## 1. Goal",
        "",
        "Validate whether clip-level approximate selection with recall certificates is viable under strict sample-splitting and oracle-relative reporting constraints. This Phase 0 run uses existing local data only, does not train models, does not run large-scale VLM inference, and does not download datasets.",
        "",
        "## 2. Existing Data Inventory",
        "",
        f"- audited files: {len(inventory)}",
        f"- clean event-boundary files detected in strict audit: {int(inventory['has_event_boundary'].sum()) if not inventory.empty and 'has_event_boundary' in inventory.columns else 0}",
        "- selected local unit source: `test_vlm/focused_validation_outputs/04_temporal_concentration/positive_timeline.csv`",
        "- selected oracle label source: existing conservative VLM pseudo-oracle labels folded into the focused validation timeline",
        "- score source: `proxy_score` derived from existing `score_count`; no fallback-score aggregate is used.",
        "",
        "## 3. Unified Phase0 Table",
        "",
        f"- units: {len(units)}",
        f"- oracle-positive units: {int(units['oracle_label'].sum()) if not units.empty else 0}",
        f"- pseudo-events: {len(events)}",
        f"- has clean event boundaries: {has_clean_boundaries}",
        "",
        "Because clean event boundaries are absent in the unit table, pseudo-events are formed by merging adjacent oracle-positive units. All event recall and certificate quantities below are oracle-relative and pseudo-event based.",
        "",
        "## 4. Experiment A: SUPG/window-level + Stitch",
        "",
        "Window-level thresholding was calibrated on sampled records, applied to all units, stitched into returned intervals, and evaluated against pseudo-events.",
        "",
        markdown_table(supg_summary[["gamma", "delta", "theta", "trials", "GVR", "mean_window_recall", "mean_clip_event_recall", "mean_selected_fraction"]] if not supg_summary.empty else supg_summary),
        "",
        f"Result: SUPG/window-level + stitch {'has' if supg_fails else 'does not have'} clip-level GVR above delta in at least one configured condition.",
        "",
        "## 5. Experiment B1: No-repair Block/Event Audit",
        "",
        "Returned clips were fixed before certification samples were drawn. Certificate computation rejected any non-certification, design, or repair rows. Event ownership used midpoint-to-block assignment; padding and provenance fields are persisted in the output CSV.",
        "",
        markdown_table(
            b1.groupby(["block_size_seconds", "gamma", "delta"], as_index=False).agg(
                trials=("trial", "count"),
                mean_true_recall=("true_oracle_recall", "mean"),
                mean_LCB_recall_O=("LCB_recall_O", "mean"),
                coverage=("coverage", "mean"),
                GVR=("GVR", "mean"),
                mean_tightness=("tightness", "mean"),
                mean_cost=("cost_to_certificate", "mean"),
            )
            if not b1.empty
            else b1
        ),
        "",
        f"Result: no-repair audit coverage={summarize_bool_rate(b1, 'coverage'):.3f}; mean LCB={float(b1['LCB_recall_O'].mean()) if not b1.empty else 0:.3f}; cost below full block scan={b1_cost_below_full}.",
        "",
        "## 6. Experiment B2: Repair + Fresh Certification",
        "",
        f"Status: {b2_status}. Diagnostic and certification samples are kept disjoint when the stage runs; final certificate rows carry `sample_split=certification`, `used_for_design=false`, and `used_for_repair=false`.",
        "",
        "## 7. Experiment C: Oracle Stability",
        "",
        "Configured stability thresholds were written to `config/oracle_stability_thresholds.json` and are reported side by side with measured values.",
        "",
        markdown_table(stability[["label_source_pair", "num_comparable_clips", "agreement_rate", "flip_rate", "abstain_rate", "stable_min_agreement_rate", "stable_max_flip_rate", "stability_classification"]] if not stability.empty else stability),
        "",
        "Current oracle labels are not stable enough for human-truth guarantee; only oracle-relative certification is currently defensible." if not oracle_ok else "The available repeated-label checks support oracle-relative analysis but do not establish human-truth guarantees.",
        "",
        "## 8. Findings",
        "",
        "- Existing local data can support a Phase 0 pseudo-event smoke validation, but it does not contain clean human-adjudicated event boundaries.",
        f"- SUPG/window-level stitching failure observed: {supg_fails}.",
        f"- No-repair block audit conservative coverage observed: {b1_conservative}.",
        f"- No-repair LCB non-vacuous by the configured mean-LCB check: {b1_nonvacuous}.",
        f"- Mean certification cost below full block scan: {b1_cost_below_full}.",
    ]
    if total_cert_events < 30:
        lines.append('Sample size insufficient for robust GVR estimation; results indicate direction only and must not be treated as sufficient evidence for GO/NO_GO.')
    lines += [
        "",
        "## 9. Limitations",
        "",
        "- Event boundaries are pseudo-derived from adjacent oracle-positive windows; they are not clean oracle-localized or human-adjudicated boundaries.",
        "- The oracle is a VLM-defined pseudo-oracle and may be prompt/model sensitive.",
        "- The candidate generator is intentionally simple and existing-score based; Phase 0 does not optimize proxy design.",
        "- Confidence bounds are finite-population approximations for feasibility validation, not a final G-ARC theorem.",
        "",
        "## 10. Next Action",
        "",
        "Acquire or construct a small clean event-boundary set before making a GO/NO-GO claim about real clip-level event guarantees. Candidate datasets to audit without immediate download are DoTA, DADA-2000/LOTVS-DADA, and Nexar dashcam collision prediction.",
        "",
        "## 11. Final Decision",
        "",
        f"FINAL_DECISION: {decision}",
    ]
    report = "\n".join(lines) + "\n"
    (OUT_DIR / "reports/PHASE0_REPORT.md").write_text(report, encoding="utf-8")

    if not has_clean_boundaries:
        (OUT_DIR / "reports/EXTERNAL_DATA_NEEDED.md").write_text(
            "\n".join(
                [
                    "# External Data Needed",
                    "",
                    "Existing Phase 0 local data lacks clean event_start/event_end boundaries. Do not download large datasets without approval.",
                    "",
                    "Recommended acquisition audit targets:",
                    "",
                    "- DoTA",
                    "- DADA-2000 / LOTVS-DADA",
                    "- Nexar Dashcam Collision Prediction",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    append_progress("final report", "python scripts/40_generate_report.py", f"wrote PHASE0_REPORT.md with decision {decision}")


if __name__ == "__main__":
    main()
