#!/usr/bin/env python3
"""Diagnose Ours budget allocation at low budgets (B=10,20) vs B=40."""

import csv
import os
from collections import defaultdict
from statistics import mean, stdev

OUTDIR = os.path.dirname(os.path.abspath(__file__))
SRCDIR = os.path.join(OUTDIR, "..", "late_aqp_frozen_cross_segment_v1")


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fmt(x, d=3):
    return f"{x:.{d}f}"


def main():
    metrics = read_csv(os.path.join(SRCDIR, "cross_segment_metrics.csv"))
    budgets = [10, 20, 40]
    method = "Frozen-LATE-AQP-v1"

    # raw rows per (budget, segment, trial)
    rows = [r for r in metrics if r["method"] == method and int(r["budget"]) in budgets]

    # aggregate per segment per budget: mean ratios across trials
    seg_budget = defaultdict(lambda: defaultdict(list))
    for r in rows:
        b = int(r["budget"])
        seg = r["segment_id"]
        seg_budget[(seg, b)]["audit"].append(int(r["audit_calls"]) / b)
        seg_budget[(seg, b)]["discovery"].append(int(r["discovery_calls"]) / b)
        seg_budget[(seg, b)]["repair"].append(int(r["repair_calls"]) / b)

    # macro average per budget across segments (mean of segment means)
    macro = {b: {"audit": [], "discovery": [], "repair": []} for b in budgets}
    for (seg, b), vals in seg_budget.items():
        for k in ("audit", "discovery", "repair"):
            macro[b][k].append(mean(vals[k]))

    # overall average across all trials/segments
    overall = {b: {"audit": [], "discovery": [], "repair": []} for b in budgets}
    for r in rows:
        b = int(r["budget"])
        overall[b]["audit"].append(int(r["audit_calls"]) / b)
        overall[b]["discovery"].append(int(r["discovery_calls"]) / b)
        overall[b]["repair"].append(int(r["repair_calls"]) / b)

    # hypothetical reallocation: if B=10/20 audit ratio is reduced to B=40 overall level
    b40_audit_ratio = mean(overall[40]["audit"])
    hypothetical = {}
    for b in [10, 20]:
        total_budget = sum(int(r["budget"]) for r in rows if int(r["budget"]) == b)
        actual_audit = sum(int(r["audit_calls"]) for r in rows if int(r["budget"]) == b)
        target_audit = total_budget * b40_audit_ratio
        extra = actual_audit - target_audit
        hypothetical[b] = {
            "total_budget": total_budget,
            "actual_audit": actual_audit,
            "target_audit": target_audit,
            "extra_calls": extra,
        }

    # write markdown
    md = "# Budget Allocation Diagnosis — Ours (Frozen-LATE-AQP-v1)\n\n"
    md += "This report diagnoses how Ours spends its oracle budget at low budgets (B=10, B=20) compared to B=40.\n\n"
    md += "All numbers are proportions of the nominal budget (audit_calls / budget, etc.).\n"
    md += "Source: `outputs/late_aqp_frozen_cross_segment_v1/cross_segment_metrics.csv`.\n\n"

    md += "## Overall average allocation per budget\n\n"
    md += "| Budget | Audit ratio | Discovery ratio | Repair ratio |\n"
    md += "|--------|-------------|-----------------|--------------|\n"
    for b in budgets:
        md += f"| {b} | {fmt(mean(overall[b]['audit']))} | {fmt(mean(overall[b]['discovery']))} | {fmt(mean(overall[b]['repair']))} |\n"

    md += "\n## Macro-averaged allocation per budget (average across segments)\n\n"
    md += "| Budget | Audit ratio | Discovery ratio | Repair ratio |\n"
    md += "|--------|-------------|-----------------|--------------|\n"
    for b in budgets:
        md += f"| {b} | {fmt(mean(macro[b]['audit']))} | {fmt(mean(macro[b]['discovery']))} | {fmt(mean(macro[b]['repair']))} |\n"

    md += "\n## Per-segment allocation at B=10, B=20, B=40\n\n"
    segments = sorted({seg for (seg, b) in seg_budget.keys()})
    for seg in segments:
        md += f"### {seg}\n\n"
        md += "| Budget | Audit | Discovery | Repair | N trials |\n"
        md += "|--------|-------|-----------|--------|----------|\n"
        for b in budgets:
            key = (seg, b)
            if key not in seg_budget:
                continue
            vals = seg_budget[key]
            md += f"| {b} | {fmt(mean(vals['audit']))} ± {fmt(stdev(vals['audit']) if len(vals['audit'])>1 else 0.0)} | {fmt(mean(vals['discovery']))} ± {fmt(stdev(vals['discovery']) if len(vals['discovery'])>1 else 0.0)} | {fmt(mean(vals['repair']))} ± {fmt(stdev(vals['repair']) if len(vals['repair'])>1 else 0.0)} | {len(vals['audit'])} |\n"
        md += "\n"

    md += "## Hypothetical reallocation: lower audit ratio to B=40 level\n\n"
    md += f"B=40 overall audit ratio = {fmt(b40_audit_ratio)}.\n\n"
    md += "| Budget | Total budget (across segments/trials) | Actual audit calls | Target audit calls (B=40 ratio) | Freed calls for discovery+repair |\n"
    md += "|--------|----------------------------------------|--------------------|----------------------------------|-----------------------------------|\n"
    for b in [10, 20]:
        h = hypothetical[b]
        md += f"| {b} | {h['total_budget']} | {h['actual_audit']} | {fmt(h['target_audit'])} | {fmt(h['extra_calls'])} |\n"

    md += "\n## Diagnosis conclusions\n\n"
    b10_audit = mean(overall[10]["audit"])
    b20_audit = mean(overall[20]["audit"])
    b40_audit = mean(overall[40]["audit"])
    md += f"- B=10 audit ratio = {fmt(b10_audit)}, B=20 audit ratio = {fmt(b20_audit)}, B=40 audit ratio = {fmt(b40_audit)}.\n"

    if b10_audit > b40_audit and b20_audit > b40_audit:
        md += "- **Audit share at B=10 and B=20 is higher than at B=40.**\n"
    else:
        md += "- Audit share at B=10/20 is not consistently higher than at B=40.\n"

    md += f"- If audit ratio at B=10/20 were reduced to the B=40 level ({fmt(b40_audit)}), the freed calls would be approximately:\n"
    for b in [10, 20]:
        md += f"  - B={b}: {fmt(hypothetical[b]['extra_calls'])} calls across all segments/trials, or about {fmt(hypothetical[b]['extra_calls']/5)} calls per segment on average.\n"

    # Interpretation
    md += "\n### Budget-allocation vs cold-start assessment\n\n"
    # Compute discovery+repair counts at low budgets
    b10_disc_rep = mean(overall[10]["discovery"]) + mean(overall[10]["repair"])
    b20_disc_rep = mean(overall[20]["discovery"]) + mean(overall[20]["repair"])
    b40_disc_rep = mean(overall[40]["discovery"]) + mean(overall[40]["repair"])
    md += f"- At B=10, discovery+repair combined gets {fmt(b10_disc_rep)} of the budget; at B=20, {fmt(b20_disc_rep)}; at B=40, {fmt(b40_disc_rep)}.\n"

    if b10_audit > b40_audit and b20_audit > b40_audit:
        md += "- The dominant pattern is that audit consumes a larger share of the small budget, leaving less room for discovery and repair.\n"
        md += "- **Judgment: this supports a budget-allocation problem.** A low-budget audit floor that caps the audit share should free enough calls for discovery+repair and improve recall.\n"
    else:
        md += "- Audit share is not the main driver; the low-budget failure is more consistent with a cold-start problem (discovery ledger cannot seed enough positives early).\n"
        md += "- **Judgment: this supports a cold-start mechanism problem.** A fallback that lets discovery run before/without audit-gated repair is more appropriate.\n"

    md += "\n### Recommended candidate family\n\n"
    if b10_audit > b40_audit and b20_audit > b40_audit:
        md += "Prioritize `V4_low_budget_floor_a` / `V4_low_budget_floor_b`: enforce an upper bound on audit share that shrinks with budget.\n"
    else:
        md += "Prioritize `V4_cold_start_fallback`: at low budgets, allow discovery to skip audit-gated repair and run discovery-first.\n"

    out_path = os.path.join(OUTDIR, "budget_allocation_diagnosis.md")
    with open(out_path, "w") as f:
        f.write(md)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
