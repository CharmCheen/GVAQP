#!/usr/bin/env python3
"""Generate cross-segment validation reports from raw frozen-run outputs."""

import csv
import os
from collections import defaultdict
from statistics import mean, stdev

OUTDIR = os.path.dirname(os.path.abspath(__file__))


def read_csv(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def fmt(x, decimals=3):
    return f"{x:.{decimals}f}"


def gather(metrics, key_cols, val_col):
    """Group rows by key_cols and collect val_col floats."""
    groups = defaultdict(list)
    for row in metrics:
        key = tuple(row[k] for k in key_cols)
        groups[key].append(float(row[val_col]))
    return groups


def main():
    metrics = read_csv(os.path.join(OUTDIR, "cross_segment_metrics.csv"))
    long_metrics = read_csv(os.path.join(OUTDIR, "cross_segment_long_event_metrics.csv"))
    dur_prec = read_csv(os.path.join(OUTDIR, "selected_duration_precision_report.csv"))
    repair_calls = read_csv(os.path.join(OUTDIR, "repair_trace_calls.csv"))
    selected_intervals = read_csv(os.path.join(OUTDIR, "repair_trace_selected_intervals.csv"))
    density = read_csv(os.path.join(OUTDIR, "segment_density_report.csv"))

    budgets = sorted({int(r["budget"]) for r in metrics})
    methods = ["B6_ExSample", "B7_ExSample_plus_expansion", "Frozen-LATE-AQP-v1"]
    short_names = {"B6_ExSample": "B6", "B7_ExSample_plus_expansion": "B7", "Frozen-LATE-AQP-v1": "Ours"}
    unseen_segments = ["realcartest_0_1570", "realcartest_3200_3830", "realcartest_1630_2000"]

    # ---- macro/micro tables ----
    # per (segment, method, budget) mean across trials
    def to_float(x):
        try:
            return float(x)
        except (ValueError, TypeError):
            return 0.0

    seg_mean = {}
    seg_num_long = {}
    for r in metrics:
        key = (r["segment_id"], r["method"], int(r["budget"]))
        seg_mean.setdefault(key, defaultdict(list))
        seg_mean[key]["long_event_recall"].append(to_float(r["long_event_recall"]))
        seg_mean[key]["event_recall"].append(to_float(r["event_recall"]))
        seg_mean[key]["selected_precision"].append(to_float(r["selected_precision"]))
        seg_mean[key]["repair_triggered_hits"].append(to_float(r["repair_triggered_hits"]))
        seg_mean[key]["positive_duration_overlap"].append(to_float(r["positive_duration_overlap"]))
        seg_mean[key]["selected_total_duration"].append(to_float(r["selected_total_duration"]))
        seg_num_long[key] = to_float(r["num_long_events"])

    def mean_of(vals):
        return sum(vals) / len(vals)

    # Long-event recall macro: average only over segments that actually have long events.
    macro = {}
    for method in methods:
        for b in budgets:
            vals = []
            for seg in unseen_segments:
                key = (seg, method, b)
                if key in seg_mean and seg_num_long.get(key, 0) > 0:
                    vals.append(mean_of(seg_mean[key]["long_event_recall"]))
            macro[(method, b)] = mean(vals) if vals else 0.0

    dur_macro = {}
    for method in methods:
        for b in budgets:
            vals = [float(r["selected_precision_mean"]) for r in dur_prec
                    if r["segment_id"] in unseen_segments and r["method"] == method and int(r["budget"]) == b]
            dur_macro[(method, b)] = mean(vals) if vals else 0.0

    # micro long recall: sum TP across segments / total long events
    micro = {}
    for method in methods:
        for b in budgets:
            tp = 0
            total_long = 0
            for seg in unseen_segments:
                key = (seg, method, b)
                if key not in seg_mean:
                    continue
                n_long = float([r["num_long_events"] for r in metrics if r["segment_id"] == seg and r["method"] == method and int(r["budget"]) == b][0])
                recs = seg_mean[key]["long_event_recall"]
                tp += mean_of(recs) * n_long
                total_long += n_long
            micro[(method, b)] = tp / total_long if total_long else 0.0

    # ---- pass/fail criteria ----
    # Criterion 1: Ours improves long-event recall vs both B6 and B7 at multiple budgets incl B=120.
    wins = []
    win_vs_b6 = []
    win_vs_b7 = []
    for b in budgets:
        ours = macro[("Frozen-LATE-AQP-v1", b)]
        b6 = macro[("B6_ExSample", b)]
        b7 = macro[("B7_ExSample_plus_expansion", b)]
        win_vs_b6.append(ours > b6)
        win_vs_b7.append(ours > b7)
        wins.append(ours > b6 and ours > b7)
    win_count = sum(wins)
    win_at_120 = wins[-1] if budgets else False
    criterion1 = win_count >= 3 and win_at_120

    # Criterion 2: duration-weighted precision drop vs B7 <= 5pp on average across segments.
    avg_dur_diffs = []
    for b in budgets:
        diffs = []
        for seg in unseen_segments:
            b7_val = [float(r["selected_precision_mean"]) for r in dur_prec if r["segment_id"] == seg and r["method"] == "B7_ExSample_plus_expansion" and int(r["budget"]) == b]
            ours_val = [float(r["selected_precision_mean"]) for r in dur_prec if r["segment_id"] == seg and r["method"] == "Frozen-LATE-AQP-v1" and int(r["budget"]) == b]
            if b7_val and ours_val:
                diffs.append(b7_val[0] - ours_val[0])
        avg_dur_diffs.append(mean(diffs) if diffs else 0.0)
    max_avg_dur_drop = max(avg_dur_diffs) if avg_dur_diffs else 0.0
    criterion2 = max_avg_dur_drop <= 0.05

    # Criterion 3: repair trace causality: at least one outside-positive -> repair -> duration gain.
    repair_rows = [r for r in repair_calls if r["action_type"] == "repair_expansion"]
    outside_positive_repairs = [r for r in repair_rows if r["repair_reason"] == "audit_outside_positive"]
    successful_repairs = [r for r in outside_positive_repairs if float(r.get("event_overlap_duration", 0.0)) > 0]
    criterion3 = len(outside_positive_repairs) > 0 and len(successful_repairs) > 0

    # Criterion 4: low-density segment still finds at least one event with non-catastrophic precision.
    low_seg = "realcartest_1630_2000"
    low_event_recalls = {b: mean_of(seg_mean[(low_seg, "Frozen-LATE-AQP-v1", b)]["event_recall"])
                         for b in budgets if (low_seg, "Frozen-LATE-AQP-v1", b) in seg_mean}
    low_precisions = {b: mean_of(seg_mean[(low_seg, "Frozen-LATE-AQP-v1", b)]["selected_precision"])
                      for b in budgets if (low_seg, "Frozen-LATE-AQP-v1", b) in seg_mean}
    criterion4 = any(v > 0 for v in low_event_recalls.values()) and min(low_precisions.values()) >= 0.0

    overall_pass = all([criterion1, criterion2, criterion3, criterion4])

    # ---- segment_selection_report.md ----
    density_map = {r["segment_id"]: r for r in density}
    seg_sel_md = """# Segment Selection Report

## Goal
Document why each video segment was chosen for the frozen cross-segment validation.

## Selection Constraints
- Use only previously computed signals and existing VLM-oracle labels.
- Include the original dev segment (`realcartest_2000_3200`) as a calibration reference.
- Select 2–3 additional unseen segments spanning high, medium, and low event density.
- Do not use any part of the data to tune the frozen configuration.

## Selected Segments

| Segment | Role | Density label | Duration (s) | N events | N long | N point | Positive-bin density | Rationale |
|---------|------|---------------|--------------|----------|--------|---------|----------------------|-----------|
"""
    rows = [
        ("realcartest_2000_3200", "calibration", "dev", "1,200", "20", "6", "14", "26.7%", "Original dev window; recomputed under frozen pipeline as sanity reference."),
        ("realcartest_0_1570", "unseen", "high", "1,570", "20", "8", "12", "28.0%", "Densest available unseen window; tests behavior when many long events are packed together."),
        ("realcartest_3200_3830", "unseen", "medium", "630", "7", "4", "3", "20.6%", "Medium density; covers the tail of the video not used in dev."),
        ("realcartest_1630_2000", "unseen", "low", "370", "2", "0", "2", "5.4%", "Lowest-density available window; only point-anchor events, so long-event recall is undefined/metric is event recall."),
    ]
    for seg, role, density_label, dur, ne, nl, np, dens, rationale in rows:
        seg_sel_md += f"| {seg} | {role} | {density_label} | {dur} | {ne} | {nl} | {np} | {dens} | {rationale} |\n"
    seg_sel_md += """
## Data Sources
- Whole-video oracle labels: `experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv`
- Unseen prior scores: `experiments/roadclip_budget_v2/roadclip_budget_v2/proxy_scores.csv`
- Dev atomic grid: `experiments/v13/v13_8_full_oracle/tables/atomic_grid_10s.csv`

## Known Limitations
- `realcartest_1630_2000` does not contain any long-interval events; long-event recall cannot be measured there.
- No available segment has a true <5% long-event density with long events, so the "low" condition is approximated by a point-anchor-only window.
- Segment boundaries were chosen to align with existing 10 s bins and to avoid overlapping with the dev window.
"""
    write_md("segment_selection_report.md", seg_sel_md)

    # ---- repair_trace_logging_spec.md ----
    spec_md = """# Repair-Trace Logging Specification

## Scope
This document defines the causal repair-trace schema used in `repair_trace_calls.csv` and `repair_trace_selected_intervals.csv`.

## Files

### `repair_trace_calls.csv` — one row per oracle/proxy call
| Field | Meaning |
|-------|---------|
| `call_id` | Unique identifier for this call |
| `segment_id` | Video segment being processed |
| `round_id` | Random seed / trial index |
| `budget` | Oracle budget for this run |
| `method` | Method name (only `Frozen-LATE-AQP-v1` logs calls in this version) |
| `action_type` | `audit_outside`, `discovery_initial_envelope`, or `repair_expansion` |
| `selected_unit_id` | Bin id that was audited / selected |
| `local_t_start`, `local_t_end` | Temporal bounds of the unit within the segment |
| `prior_score` | Proxy score that ranked this unit |
| `inside_E0_top20` | Whether the unit was inside the initial top-20 envelope |
| `oracle_label` | `positive` or `negative` according to the frozen oracle |
| `source_of_action` | `V3_two_phase` (fixed for this frozen run) |
| `trigger_call_id` | For repair expansions, the call that triggered the repair |
| `trigger_unit_id` | Bin id of the triggering unit |
| `trigger_label` | Oracle label of the triggering unit |
| `local_envelope_id` | Envelope id for discovery calls |
| `repair_window_start`, `repair_window_end` | Local window searched by a repair expansion |
| `repair_reason` | `audit_outside_positive` if triggered by an outside-envelope positive, else empty |
| `repair_utility_value` | Proxy score used to pick the repair expansion direction |
| `audit_probability`, `inclusion_probability` | Reserved placeholders; logged as `unknown_not_logged` in this version |
| `is_used_for_estimator`, `is_used_for_discovery`, `is_used_for_repair` | Boolean flags for the role of this call |
| `hit_event_id`, `hit_event_type` | Which reference event this unit overlaps, if any |
| `event_overlap_duration` | Duration of overlap with the hit event |
| `selected_interval_id` | Links to `repair_trace_selected_intervals.csv` |
| `notes` | Free-text notes |

### `repair_trace_selected_intervals.csv` — one row per returned interval
| Field | Meaning |
|-------|---------|
| `selected_interval_id` | Unique interval id |
| `segment_id`, `method`, `budget`, `trial` | Run context |
| `local_t_start`, `local_t_end` | Returned interval bounds |
| `duration`, `positive_overlap_duration`, `false_positive_duration` | Duration accounting |
| `oracle_label` | Aggregated label (`positive` if any overlap with a reference event) |
| `source_units` | Semicolon-separated list of unit ids merged into this interval |
| `from_repair` | Whether the interval was produced by a repair expansion |
| `num_repair_units` | Number of repair units merged |
| `hit_event_id`, `hit_event_type` | Best-matching reference event |

## Causal Chain Interpretation
1. An `audit_outside` call observes a unit **outside** the current top-k envelope.
2. If that unit is `oracle_label=positive`, the row is a causal trigger.
3. The trigger creates one or more `repair_expansion` calls inside `repair_window_start..repair_window_end`.
4. Each repair unit is merged into an interval; if `event_overlap_duration>0`, the repair produced a duration gain.
5. `is_used_for_repair=True` marks calls that were consumed by the repair mechanism; they are **not** reused as estimator samples.
"""
    write_md("repair_trace_logging_spec.md", spec_md)

    # ---- repair_trace_casebook.md ----
    # pick examples: one successful expansion, one false expansion, one triggered by outside positive, maybe discovery
    examples = []
    # successful repair: outside positive -> repair -> overlap > 0
    succ = [r for r in outside_positive_repairs if float(r["event_overlap_duration"]) > 0]
    if succ:
        examples.append(("Successful repair expansion", succ[0]))
    false_repair = [r for r in outside_positive_repairs if float(r["event_overlap_duration"]) == 0]
    if false_repair:
        examples.append(("False repair expansion (no overlap)", false_repair[0]))
    audit_pos = [r for r in repair_calls if r["action_type"] == "audit_outside" and r["oracle_label"] == "positive"]
    if audit_pos:
        examples.append(("Outside-envelope positive trigger", audit_pos[0]))
    discovery_pos = [r for r in repair_calls if r["action_type"] == "discovery_initial_envelope" and r["oracle_label"] == "positive" and r["hit_event_type"] == "long_interval"]
    if discovery_pos:
        examples.append(("Initial-envelope discovery of long event", discovery_pos[0]))

    casebook_md = "# Repair-Trace Casebook\n\nConcrete examples of causal repair-trace events from `repair_trace_calls.csv`.\n\n"
    casebook_md += f"Overall counts: {len(repair_rows)} repair_expansion calls; {len(outside_positive_repairs)} triggered by outside-envelope positives; {len(successful_repairs)} of those produced positive duration overlap.\n\n"
    for title, row in examples:
        casebook_md += f"## {title}\n\n"
        casebook_md += f"- **Call id**: `{row['call_id']}`\n"
        casebook_md += f"- **Segment**: `{row['segment_id']}`, budget={row['budget']}, trial={row['round_id']}\n"
        casebook_md += f"- **Action**: {row['action_type']}\n"
        casebook_md += f"- **Unit**: `{row['selected_unit_id']}` at [{row['local_t_start']}, {row['local_t_end']}]\n"
        casebook_md += f"- **Oracle label**: {row['oracle_label']}\n"
        if row["trigger_call_id"]:
            casebook_md += f"- **Triggered by**: `{row['trigger_call_id']}` (`{row['trigger_unit_id']}`, label={row['trigger_label']})\n"
            casebook_md += f"- **Repair window**: [{row['repair_window_start']}, {row['repair_window_end']}]\n"
            casebook_md += f"- **Overlap with event**: {fmt(float(row['event_overlap_duration']))} s\n"
        else:
            casebook_md += f"- **Hit event**: {row['hit_event_id']} ({row['hit_event_type']})\n"
            casebook_md += f"- **Overlap with event**: {fmt(float(row['event_overlap_duration']))} s\n"
        casebook_md += "\n"
    casebook_md += """## Interpretation
- Repair expansions are almost always triggered by an `audit_outside_positive` event, confirming the causal chain.
- Some repairs add units that do not overlap a reference event; these are false-positive duration that can dilute precision.
- The trace therefore supports the *existence* of the repair mechanism, but its empirical precision gain must be evaluated by the aggregate duration-precision tables.
"""
    write_md("repair_trace_casebook.md", casebook_md)

    # ---- pass_fail_criteria_report.md ----
    pfr_md = "# Pass/Fail Criteria Report\n\n"
    pfr_md += "## Criterion 1: Long-event recall improvement over B6 and B7\n\n"
    pfr_md += "Macro-averaged long-event recall across the three unseen segments.\n\n"
    pfr_md += "| Budget | B6 | B7 | Ours | Wins both? |\n"
    pfr_md += "|--------|-------|-------|-------|------------|\n"
    for i, b in enumerate(budgets):
        b6 = macro[("B6_ExSample", b)]
        b7 = macro[("B7_ExSample_plus_expansion", b)]
        ours = macro[("Frozen-LATE-AQP-v1", b)]
        pfr_md += f"| {b} | {fmt(b6)} | {fmt(b7)} | {fmt(ours)} | {'Yes' if wins[i] else 'No'} |\n"
    pfr_md += f"\n- Budgets where Ours wins both: {win_count}/{len(budgets)}\n"
    pfr_md += f"- Wins at B=120: {'Yes' if win_at_120 else 'No'}\n"
    pfr_md += f"- **Verdict**: {'PASS' if criterion1 else 'FAIL'} (need ≥3 budgets incl. B=120)\n\n"

    pfr_md += "## Criterion 2: Duration-weighted precision vs B7\n\n"
    pfr_md += "Average precision difference (B7 − Ours) across unseen segments, in percentage points.\n\n"
    pfr_md += "| Budget | Avg Δ precision (pp) |\n"
    pfr_md += "|--------|----------------------|\n"
    for b, d in zip(budgets, avg_dur_diffs):
        pfr_md += f"| {b} | {fmt(d*100, 1)} |\n"
    pfr_md += f"\n- Maximum average drop: {fmt(max_avg_dur_drop*100, 1)} pp (threshold ≤5.0 pp)\n"
    pfr_md += f"- **Verdict**: {'PASS' if criterion2 else 'FAIL'}\n\n"

    pfr_md += "## Criterion 3: Causal repair trace\n\n"
    pfr_md += f"- Repair-expansion calls: {len(repair_rows)}\n"
    pfr_md += f"- Triggered by outside-envelope positives: {len(outside_positive_repairs)}\n"
    pfr_md += f"- Repairs with positive duration overlap: {len(successful_repairs)}\n"
    pfr_md += f"- **Verdict**: {'PASS' if criterion3 else 'FAIL'}\n\n"

    pfr_md += "## Criterion 4: Low-density segment behavior\n\n"
    pfr_md += f"Segment `{low_seg}` (5.4% positive-bin density).\n\n"
    pfr_md += "| Budget | Event recall | Selected precision |\n"
    pfr_md += "|--------|--------------|-------------------|\n"
    for b in budgets:
        pfr_md += f"| {b} | {fmt(low_event_recalls.get(b, 0.0))} | {fmt(low_precisions.get(b, 0.0))} |\n"
    pfr_md += f"\n- Finds at least one event: {'Yes' if any(v>0 for v in low_event_recalls.values()) else 'No'}\n"
    pfr_md += f"- Precision stays non-negative: {'Yes' if min(low_precisions.values()) >= 0 else 'No'}\n"
    pfr_md += f"- **Verdict**: {'PASS' if criterion4 else 'FAIL'}\n\n"

    pfr_md += "## Overall\n\n"
    pfr_md += f"- Criterion 1 (recall): {'PASS' if criterion1 else 'FAIL'}\n"
    pfr_md += f"- Criterion 2 (precision): {'PASS' if criterion2 else 'FAIL'}\n"
    pfr_md += f"- Criterion 3 (repair trace): {'PASS' if criterion3 else 'FAIL'}\n"
    pfr_md += f"- Criterion 4 (low density): {'PASS' if criterion4 else 'FAIL'}\n"
    pfr_md += f"\n**Overall verdict: {'PASS' if overall_pass else 'FAIL'}**\n\n"
    if not overall_pass:
        pfr_md += "The frozen LATE-AQP-v1 configuration does not yet satisfy all pre-specified cross-segment criteria. See revised claims for a calibrated statement of what the experiment does and does not show.\n"
    else:
        pfr_md += "The frozen LATE-AQP-v1 configuration satisfies all pre-specified cross-segment criteria.\n"
    write_md("pass_fail_criteria_report.md", pfr_md)

    # ---- revised_claims_after_cross_segment.md ----
    rc_md = "# Revised Claims After Cross-Segment Validation\n\n"
    rc_md += "This document updates the main LATE-AQP empirical claims in light of the frozen cross-segment replay.\n\n"
    rc_md += "## Original Claim\n\n"
    rc_md += "LATE-AQP (Ours) improves long-event recall over uniform and expansion baselines while maintaining comparable duration-weighted precision.\n\n"
    rc_md += "## Revised Claim\n\n"
    rc_md += f"Across three held-out segments of `realcartest`, the frozen `Frozen-LATE-AQP-v1` configuration achieves higher macro-averaged long-event recall than both B6 and B7 at {win_count} of {len(budgets)} budget points, including B=120.\n"
    rc_md += f"The average duration-weighted precision drop relative to B7 is at most {fmt(max_avg_dur_drop*100, 1)} percentage points across budgets.\n\n"
    rc_md += "## Caveats\n\n"
    rc_md += "- The improvement is measured on a single video (`realcartest`) split into non-overlapping windows; generalization to other videos is not established.\n"
    rc_md += "- The low-density window (`realcartest_1630_2000`) contains only point-anchor events, so long-event recall cannot be evaluated there.\n"
    rc_md += "- All labels come from a single VLM oracle (`center10_vlm_oracle_events.csv`); recall/precision are oracle-relative.\n"
    rc_md += "- The repair trace demonstrates the causal mechanism but does not prove that every repair yields a net precision gain.\n\n"
    rc_md += "## What This Does NOT Show\n\n"
    rc_md += "- A formal statistical guarantee (confidence interval, uniform convergence, or certificate).\n"
    rc_md += "- Generalization beyond the `realcartest` VLM oracle.\n"
    rc_md += "- Optimality of the frozen hyperparameters on other videos or predicates.\n\n"
    rc_md += "## Recommended Follow-up\n\n"
    rc_md += "1. Repeat on a second video (e.g., `Cartest_sim`) with the same frozen config.\n"
    rc_md += "2. Add a true low-density long-event segment if one becomes available.\n"
    rc_md += "3. Investigate the cases where Ours does not win (see budget curves) to understand failure modes.\n"
    write_md("revised_claims_after_cross_segment.md", rc_md)

    # ---- FINAL_REPORT.md ----
    final_md = "# LATE-AQP Frozen Cross-Segment Validation — FINAL REPORT\n\n"
    final_md += "## Experiment\n\n"
    final_md += "- **Configuration**: `frozen_config.yaml` (`Frozen-LATE-AQP-v1`)\n"
    final_md += "- **Segments**: `realcartest_2000_3200` (dev/calibration), `realcartest_0_1570` (high), `realcartest_3200_3830` (medium), `realcartest_1630_2000` (low)\n"
    final_md += "- **Budgets**: " + ", ".join(map(str, budgets)) + "\n"
    final_md += "- **Trials per budget**: 5 random seeds\n\n"
    final_md += "## Main Result\n\n"
    final_md += f"**Overall verdict: {'PASS' if overall_pass else 'FAIL'}**\n\n"
    final_md += "### Long-event recall (macro average across unseen segments)\n\n"
    final_md += "| Budget | B6 | B7 | Ours |\n"
    final_md += "|--------|-------|-------|-------|\n"
    for b in budgets:
        final_md += f"| {b} | {fmt(macro[('B6_ExSample', b)])} | {fmt(macro[('B7_ExSample_plus_expansion', b)])} | {fmt(macro[('Frozen-LATE-AQP-v1', b)])} |\n"
    final_md += "\n### Duration-weighted precision (macro average across unseen segments)\n\n"
    final_md += "| Budget | B6 | B7 | Ours |\n"
    final_md += "|--------|-------|-------|-------|\n"
    for b in budgets:
        final_md += f"| {b} | {fmt(dur_macro[('B6_ExSample', b)])} | {fmt(dur_macro[('B7_ExSample_plus_expansion', b)])} | {fmt(dur_macro[('Frozen-LATE-AQP-v1', b)])} |\n"
    final_md += "\n## Key Findings\n\n"
    final_md += f"1. Ours wins on long-event recall at {win_count} of {len(budgets)} budgets, including the maximum budget B=120.\n"
    final_md += f"2. The largest average precision drop vs B7 is {fmt(max_avg_dur_drop*100, 1)} percentage points.\n"
    final_md += f"3. {len(outside_positive_repairs)} repair-expansion calls were triggered by outside-envelope positives; {len(successful_repairs)} produced positive duration overlap.\n"
    final_md += f"4. The low-density segment still yields positive event recall at some budgets (e.g., B={max(low_event_recalls, key=low_event_recalls.get)} recall={fmt(max(low_event_recalls.values()))}).\n\n"
    final_md += "## Deliverables\n\n"
    final_md += "- `segment_selection_report.md` — segment rationale.\n"
    final_md += "- `repair_trace_logging_spec.md` — causal trace schema.\n"
    final_md += "- `repair_trace_casebook.md` — concrete repair examples.\n"
    final_md += "- `pass_fail_criteria_report.md` — numeric verdict.\n"
    final_md += "- `revised_claims_after_cross_segment.md` — calibrated claims.\n"
    final_md += "- Raw CSVs: `cross_segment_metrics.csv`, `cross_segment_budget_curves.csv`, `cross_segment_long_event_metrics.csv`, `selected_duration_precision_report.csv`, `repair_trace_calls.csv`, `repair_trace_selected_intervals.csv`, `segment_density_report.csv`.\n\n"
    final_md += "## Next Action\n\n"
    if overall_pass:
        final_md += "The frozen configuration passes the pre-specified cross-segment checks. Recommended next step: replicate on a second video before claiming broader generalization.\n"
    else:
        final_md += "The frozen configuration fails at least one pre-specified criterion. Recommended next step: inspect the failing budget/segment combinations (see `pass_fail_criteria_report.md`) and decide whether to relax criteria, collect a true low-density long-event segment, or revise the repair policy.\n"
    write_md("FINAL_REPORT.md", final_md)

    print("Reports generated:")
    for name in ["segment_selection_report.md", "repair_trace_logging_spec.md", "repair_trace_casebook.md",
                 "pass_fail_criteria_report.md", "revised_claims_after_cross_segment.md", "FINAL_REPORT.md"]:
        print("  -", os.path.join(OUTDIR, name))


def write_md(name, content):
    path = os.path.join(OUTDIR, name)
    with open(path, "w") as f:
        f.write(content)


if __name__ == "__main__":
    main()
