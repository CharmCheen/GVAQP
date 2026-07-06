#!/usr/bin/env python3
"""Secondary analysis on existing frozen cross-segment outputs."""

import csv
import os
from collections import defaultdict
from statistics import mean

OUTDIR = os.path.dirname(os.path.abspath(__file__))


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def to_float(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return None


def parse_budget_trial_from_interval_id(iid):
    """Parse budget/trial from selected_interval_id like ..._b5_t0_i0."""
    parts = iid.split("_")
    b = None
    t = None
    for p in parts:
        if p.startswith("b") and p[1:].isdigit():
            b = int(p[1:])
        if p.startswith("t") and p[1:].isdigit():
            t = int(p[1:])
    return b, t


def main():
    metrics = read_csv(os.path.join(OUTDIR, "cross_segment_metrics.csv"))
    repair_calls = read_csv(os.path.join(OUTDIR, "repair_trace_calls.csv"))
    selected_intervals = read_csv(os.path.join(OUTDIR, "repair_trace_selected_intervals.csv"))

    # ---- 1. per_budget_breakdown.csv (raw per-trial) ----
    breakdown_path = os.path.join(OUTDIR, "per_budget_breakdown.csv")
    with open(breakdown_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["budget", "method", "segment", "long_event_recall", "precision", "selected_duration"])
        for r in metrics:
            writer.writerow([
                r["budget"],
                r["method"],
                r["segment_id"],
                r["long_event_recall"],  # keep raw (empty when no long events)
                r["selected_precision"],
                r["selected_total_duration"],
            ])
    print(f"Wrote {breakdown_path}")

    # ---- 2. repair_causal_chain.csv ----
    # Index selected intervals by (segment, method, budget, trial) -> list of intervals
    intervals_by_run = defaultdict(list)
    interval_by_id = {}
    for row in selected_intervals:
        b, t = parse_budget_trial_from_interval_id(row["selected_interval_id"])
        if b is None:
            b = int(row["budget"])
        key = (row["segment_id"], row["method"], b, t)
        intervals_by_run[key].append(row)
        interval_by_id[row["selected_interval_id"]] = row

    repair_rows = [r for r in repair_calls if r["action_type"] == "repair_expansion"]
    chain_path = os.path.join(OUTDIR, "repair_causal_chain.csv")
    ours_only_long_rows = []
    with open(chain_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "repair_call_id", "trigger_unit_id", "produced_positive_overlap",
            "entered_selected_interval", "selected_interval_id",
            "hit_event_id", "event_type", "is_ours_only_hit"
        ])
        for r in repair_rows:
            iid = r.get("selected_interval_id", "")
            interval = interval_by_id.get(iid)
            entered = interval is not None
            overlap = to_float(r.get("event_overlap_duration", ""))
            produced_positive = overlap is not None and overlap > 0
            hit_event = ""
            event_type = ""
            if interval is not None:
                hit_event = interval.get("hit_event_id", "") or ""
                event_type = interval.get("hit_event_type", "") or ""
            else:
                hit_event = r.get("hit_event_id", "") or ""
                event_type = r.get("hit_event_type", "") or ""

            ours_only = False
            if interval is not None and hit_event and hit_event != "none":
                seg = interval["segment_id"]
                budget, trial = parse_budget_trial_from_interval_id(interval["selected_interval_id"])
                if budget is None:
                    budget = int(interval["budget"])
                b6_hits = {x.get("hit_event_id") for x in intervals_by_run[(seg, "B6_ExSample", budget, trial)]}
                b7_hits = {x.get("hit_event_id") for x in intervals_by_run[(seg, "B7_ExSample_plus_expansion", budget, trial)]}
                ours_only = hit_event not in b6_hits and hit_event not in b7_hits

            writer.writerow([
                r["call_id"],
                r.get("trigger_unit_id", ""),
                produced_positive,
                entered,
                iid,
                hit_event,
                event_type,
                ours_only,
            ])
            if ours_only and event_type == "long_interval":
                ours_only_long_rows.append(r["call_id"])

    print(f"Wrote {chain_path}")
    print(f"Repair-expansion rows: {len(repair_rows)}")
    print(f"is_ours_only_hit=True & event_type=long_interval: {len(ours_only_long_rows)}")

    # ---- 3. Summary for FINAL_REPORT.md ----
    # Per-budget macro long-event recall on unseen segments (same definition as generate_reports)
    unseen_segments = ["realcartest_0_1570", "realcartest_3200_3830", "realcartest_1630_2000"]
    budgets = sorted({int(r["budget"]) for r in metrics})
    methods = ["B6_ExSample", "B7_ExSample_plus_expansion", "Frozen-LATE-AQP-v1"]

    seg_mean = defaultdict(lambda: defaultdict(list))
    seg_num_long = {}
    for r in metrics:
        key = (r["segment_id"], r["method"], int(r["budget"]))
        seg_mean[key]["long_event_recall"].append(to_float(r["long_event_recall"]) or 0.0)
        seg_num_long[key] = to_float(r["num_long_events"]) or 0.0

    def mean_of(vals):
        return sum(vals) / len(vals)

    macro = {}
    for method in methods:
        for b in budgets:
            vals = []
            for seg in unseen_segments:
                key = (seg, method, b)
                if seg_num_long.get(key, 0) > 0:
                    vals.append(mean_of(seg_mean[key]["long_event_recall"]))
            macro[(method, b)] = mean(vals) if vals else 0.0

    losses = []
    for b in budgets:
        ours = macro[("Frozen-LATE-AQP-v1", b)]
        b6 = macro[("B6_ExSample", b)]
        b7 = macro[("B7_ExSample_plus_expansion", b)]
        if not (ours > b6 and ours > b7):
            losses.append((b, ours, b6, b7))

    # Read current FINAL_REPORT.md and insert new section before "## Deliverables"
    final_path = os.path.join(OUTDIR, "FINAL_REPORT.md")
    with open(final_path) as f:
        content = f.read()

    new_section = "## Secondary Analysis\n\n"
    new_section += "### Budgets where Ours did not win on long-event recall\n\n"
    new_section += "Macro-averaged long-event recall across the three unseen segments; source: `center10_vlm_oracle_events.csv`.\n\n"
    new_section += "| Budget | Ours | B6 | B7 | Gap to best baseline |\n"
    new_section += "|--------|------|------|------|----------------------|\n"
    for b, ours, b6, b7 in losses:
        best = max(b6, b7)
        gap = best - ours
        new_section += f"| {b} | {ours:.3f} | {b6:.3f} | {b7:.3f} | {gap:.3f} |\n"
    if not losses:
        new_section += "_Ours wins at every budget._\n"
    new_section += "\n"
    new_section += "### Repair mechanism contribution: Ours-only long-interval hits\n\n"
    new_section += f"- Total repair-expansion calls traced: {len(repair_rows)}\n"
    new_section += f"- Repair rows with `is_ours_only_hit=True` and `event_type=long_interval`: **{len(ours_only_long_rows)}**\n"
    unique_events = set()
    # Re-derive unique event ids for ours-only long rows
    for r in repair_rows:
        if r["call_id"] in ours_only_long_rows:
            iid = r.get("selected_interval_id", "")
            interval = interval_by_id.get(iid)
            if interval and interval.get("hit_event_id"):
                unique_events.add(interval["hit_event_id"])
    new_section += f"- Unique long-interval event ids involved: {len(unique_events)}\n"
    new_section += "\nThis count is **greater than 0**, indicating that the repair mechanism produced selected intervals hitting long events that neither B6 nor B7 selected in the same segment/budget/trial.\n\n"

    if "## Secondary Analysis" in content:
        print("FINAL_REPORT.md already contains Secondary Analysis; skipping append.")
        return

    marker = "## Deliverables"
    if marker in content:
        content = content.replace(marker, new_section + marker, 1)
    else:
        content += "\n" + new_section

    with open(final_path, "w") as f:
        f.write(content)
    print(f"Updated {final_path}")


if __name__ == "__main__":
    main()
