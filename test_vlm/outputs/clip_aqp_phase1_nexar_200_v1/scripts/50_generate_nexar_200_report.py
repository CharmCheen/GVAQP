#!/usr/bin/env python3
"""Generate the Nexar-200 derived-boundary benchmark report."""

from __future__ import annotations

import json
from pathlib import Path

from nexar_200_common import OUT, append_progress, read_csv, write_csv


def table_md(rows: list[dict], max_rows: int | None = None) -> str:
    if not rows:
        return "_No rows._"
    rows = rows[:max_rows] if max_rows else rows
    cols = list(rows[0].keys())
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in cols) + " |")
    return "\n".join(lines)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def metric(rows: list[dict], name: str, default=""):
    for row in rows:
        if row.get("metric") == name:
            return row.get("value", default)
    return default


def pick_reference(block_summary: list[dict]) -> dict:
    for row in block_summary:
        if (
            str(row.get("theta")) == "0.3"
            and str(row.get("gamma")) == "0.8"
            and str(row.get("delta")) == "0.1"
            and str(row.get("block_size_seconds")) == "10"
            and str(row.get("sample_fraction")) == "0.35"
        ):
            return row
    return block_summary[0] if block_summary else {}


def decide(event_stats: list[dict], block_summary: list[dict]) -> str:
    usable_events = int(float(metric(event_stats, "usable_casq_events", 0) or 0))
    if usable_events < 200:
        return "NEED_METADATA_ACCESS"
    ref = pick_reference(block_summary)
    if not ref:
        return "METHOD_STILL_TOO_VACUOUS"
    fraction_vacuous = float(ref.get("fraction_vacuous", 1.0))
    cert_success = float(ref.get("certificate_success_rate", 0.0))
    gvr = float(ref.get("GVR", 1.0))
    delta = float(ref.get("delta", 0.1))
    if fraction_vacuous > 0.5 or cert_success == 0.0:
        return "METHOD_STILL_TOO_VACUOUS"
    if gvr <= delta:
        return "GOOD_FOR_DERIVED_BOUNDARY_BASELINE_ONLY"
    return "NEED_ORIGINAL_BOUNDARY_DATASET"


def main() -> int:
    metadata_status = read_json(OUT / "tables" / "nexar_200_metadata_status.json")
    manifest = read_csv(OUT / "manifests" / "nexar_200_manifest.csv") if (OUT / "manifests" / "nexar_200_manifest.csv").exists() else []
    event_stats = read_csv(OUT / "tables" / "nexar_200_event_stats.csv") if (OUT / "tables" / "nexar_200_event_stats.csv").exists() else []
    unit_stats = read_csv(OUT / "tables" / "nexar_200_unit_stats.csv") if (OUT / "tables" / "nexar_200_unit_stats.csv").exists() else []
    validation = read_csv(OUT / "tables" / "nexar_200_schema_validation.csv") if (OUT / "tables" / "nexar_200_schema_validation.csv").exists() else []
    supg_summary = read_csv(OUT / "tables" / "nexar_200_supg_stitch_summary.csv") if (OUT / "tables" / "nexar_200_supg_stitch_summary.csv").exists() else []
    block_summary = read_csv(OUT / "tables" / "nexar_200_block_audit_summary.csv") if (OUT / "tables" / "nexar_200_block_audit_summary.csv").exists() else []
    sanity = read_csv(OUT / "tables" / "nexar_200_sanity_checks.csv") if (OUT / "tables" / "nexar_200_sanity_checks.csv").exists() else []
    ref = pick_reference(block_summary)
    final_decision = decide(event_stats, block_summary)
    write_csv(OUT / "tables" / "nexar_200_final_decision.csv", [{"decision": final_decision}], ["decision"])

    all_boundaries_derived = "derived_from_alert_time_to_event_moment" in str(metric(event_stats, "boundary_source_distribution", ""))
    ref_lcb = float(ref.get("LCB_recall_median", 0.0) or 0.0) if ref else 0.0
    ref_vacuous = float(ref.get("fraction_vacuous", 1.0) or 1.0) if ref else 1.0
    ref_gvr = float(ref.get("GVR", 0.0) or 0.0) if ref else 0.0
    ref_true = float(ref.get("true_derived_recall", 0.0) or 0.0) if ref else 0.0
    ref_cert = float(ref.get("certificate_success_rate", 0.0) or 0.0) if ref else 0.0

    lines = [
        "# Nexar-200 Derived-Boundary CASQ Benchmark Report",
        "",
        "## 1. Goal",
        "",
        "Build a metadata-only Nexar benchmark with about 200 positive derived-boundary events and 200 normal videos, then rerun Phase 0-style SUPG stitch and no-repair block/event audit validation. No VLM, training, perception stack, full dataset download, or original-boundary fabrication is used.",
        "",
        "## 2. Dataset and Metadata Source",
        "",
        f"- Positive metadata: `{metadata_status.get('positive_metadata_path', '')}`",
        f"- Negative metadata: `{metadata_status.get('negative_metadata_path', '')}`",
        f"- Positive metadata rows: `{metadata_status.get('positive_metadata_rows', '')}`",
        f"- Negative metadata rows: `{metadata_status.get('negative_metadata_rows', '')}`",
        f"- Selected positive rows: `{metadata_status.get('selected_positive_rows', '')}`",
        f"- Selected normal rows: `{metadata_status.get('selected_normal_rows', '')}`",
        f"- Videos downloaded: `{metadata_status.get('videos_downloaded', False)}`",
        "",
        "## 3. Boundary Derivation Rule",
        "",
        "For positives with `time_of_alert` and `time_of_event`, CASQ uses:",
        "",
        "`event_start = time_of_alert`",
        "",
        "`event_end = time_of_event`",
        "",
        "`boundary_source = derived_from_alert_time_to_event_moment`",
        "",
        "`boundary_confidence = medium`",
        "",
        "These are derived precursor intervals, not original human event_start/event_end annotations.",
        "",
        "## 4. CASQ Event Conversion",
        "",
        table_md(event_stats),
        "",
        "## 5. CASQ Unit Construction",
        "",
        "Units are fixed 5s, 10s, and 15s intervals. Tail fragments shorter than the configured unit length are dropped.",
        "",
        table_md(unit_stats),
        "",
        "## 6. Schema Validation",
        "",
        table_md(validation),
        "",
        "Sanity checks:",
        "",
        table_md(sanity),
        "",
        "## 7. SUPG/window-level + Stitch Result",
        "",
        "The SUPG-style run uses metadata-only hash-random 5s unit selection, independent of labels and event intervals. Because many Nexar alert-to-event intervals are much shorter than 5s, overlap does not imply high IoU recall.",
        "",
        table_md([row for row in supg_summary if row.get("gamma") == "0.8" and row.get("theta") == "0.3"], max_rows=8),
        "",
        "## 8. Block/Event Audit Result",
        "",
        "The no-repair block/event audit freezes a metadata-only hash candidate set before certification sampling. It uses only certification samples and does not use diagnostic or repair reuse.",
        "",
        "Reference condition for comparison: theta=0.3, gamma=0.8, delta=0.1, 10s blocks, sample_fraction=0.35.",
        "",
        table_md([ref] if ref else []),
        "",
        "## 9. Comparison to Phase 0.6 Power Simulation",
        "",
        f"- Did Nexar-200 behave like the power simulation predicted? Partly. It reached 200 derived events, but the metadata-only hash candidate set has true derived recall `{ref_true:.4f}`, which is not the same operating point as the Phase 0.6 reference recall around 0.31.",
        f"- Is LCB_recall non-vacuous at around 200 events? Reference median LCB is `{ref_lcb:.4f}` with fraction vacuous `{ref_vacuous:.4f}`.",
        f"- Does GVR remain <= delta? Reference GVR is `{ref_gvr:.4f}` against delta `{ref.get('delta', '')}`; this is mostly because certificates do not succeed when LCB is far below gamma.",
        f"- Is the bound still too conservative for gamma=0.8/0.9? Yes. Reference certificate success rate is `{ref_cert:.4f}`.",
        "- Does this justify expanding to 500 events? Not as a main claim. It can be useful as a derived-boundary baseline, but the current metadata-only candidate and short derived intervals still make certification weak.",
        f"- Are derived boundaries too weak for main-paper claims? {'Yes' if all_boundaries_derived else 'Mixed'}; they are not original human intervals.",
        "",
        "## 10. Limitations",
        "",
        "- Boundaries are derived from alert/event timestamps, not original human interval annotations.",
        "- Videos were not downloaded, so no visual/perception proxy is available.",
        "- The candidate generator is a metadata-only hash/random baseline and should not be interpreted as a deployed retrieval method.",
        "- The block audit validates the certificate machinery over derived boundaries; it does not establish human-truth driving-event recall.",
        "- GVR can be zero when certificate success is also zero, so GVR alone is not evidence of usefulness.",
        "",
        "## 11. Recommendation",
        "",
        "Use Nexar-200 as a derived-boundary baseline and certificate plumbing benchmark only. For main research claims, prioritize original interval annotations or human-adjudicated CASQ boundaries. Expanding to 500 derived events is reasonable only after adding a non-label perception or metadata proxy that raises true derived recall without using event labels.",
        "",
        f"NEXAR_200_DECISION: {final_decision}",
    ]
    report_path = OUT / "reports" / "NEXAR_200_DERIVED_BENCHMARK_REPORT.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    append_progress("generate_report", "python scripts/50_generate_nexar_200_report.py", f"decision={final_decision}", "review completion evidence")
    print(f"Wrote {report_path} with decision {final_decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
