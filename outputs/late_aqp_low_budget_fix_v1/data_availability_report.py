#!/usr/bin/env python3
"""Report available O_ref label coverage and identify usable unseen intervals."""

import csv
import os
from pathlib import Path

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUTDIR = ROOT / "outputs" / "late_aqp_low_budget_fix_v1"

# Primary whole-video oracle labels.
CENTER10_PATH = ROOT / "experiments" / "v13" / "v13_8_full_oracle" / "tables" / "center10_vlm_oracle_events.csv"

# All reference files found.
REF_FILES = [
    ROOT / "src" / "garc_eval" / "outputs" / "clean_interval_aqp_full_reference_v2_clean_no_leak" / "reference_events.csv",
    ROOT / "src" / "garc_eval" / "outputs" / "clean_interval_aqp_full_reference_v2_label_aligned" / "reference_events.csv",
    ROOT / "src" / "garc_eval" / "outputs" / "clean_interval_aqp_full_reference_v1" / "reference_events.csv",
]

# Intervals already used in any prior experiment round.
USED_INTERVALS = [
    ("realcartest", 2000.0, 3200.0, "dev (cross-segment validation)"),
    ("realcartest", 0.0, 1570.0, "unseen high (cross-segment validation)"),
    ("realcartest", 1630.0, 2000.0, "unseen low (cross-segment validation)"),
    ("realcartest", 3200.0, 3830.0, "unseen medium (cross-segment validation)"),
]


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fmt_time(t):
    return f"{t:.1f}"


def count_pos_bins(start, end, events, bin_size=10.0):
    n_bins = int((end - start) / bin_size)
    pos_bins = 0
    long_events = []
    point_events = []
    for i in range(n_bins):
        bs = start + i * bin_size
        be = bs + bin_size
        has_pos = False
        for ev in events:
            est = float(ev["event_start"])
            eed = float(ev["event_end"])
            if est < be and eed > bs:
                has_pos = True
                break
        if has_pos:
            pos_bins += 1
    # event-level counts for interval
    covered = [ev for ev in events if float(ev["event_start"]) < end and float(ev["event_end"]) > start]
    for ev in covered:
        dur = float(ev["event_end"]) - float(ev["event_start"])
        if dur >= 1.0:
            long_events.append(ev["event_id"])
        else:
            point_events.append(ev["event_id"])
    density = pos_bins / n_bins if n_bins > 0 else 0.0
    return n_bins, pos_bins, density, long_events, point_events


def main():
    events = read_csv(CENTER10_PATH)
    events = [e for e in events if e.get("video_id") == "realcartest"]
    events_start = min(float(e["event_start"]) for e in events)
    events_end = max(float(e["event_end"]) for e in events)

    md = "# Data Availability Report\n\n"
    md += "## Search scope\n\n"
    md += "Searched for existing `reference_events.csv` / `full_reference_units.csv` / `*vlm_oracle_events.csv` files under the repository root.\n\n"

    md += "## Existing O_ref files\n\n"
    md += "| File | Video | Events | Time coverage | Notes |\n"
    md += "|------|-------|--------|---------------|-------|\n"
    md += f"| `{CENTER10_PATH.relative_to(ROOT)}` | realcartest | {len(events)} | {fmt_time(events_start)}–{fmt_time(events_end)} | Primary whole-video VLM-oracle labels |\n"
    for p in REF_FILES:
        rows = read_csv(p)
        vids = sorted({r.get("video_id", "") for r in rows})
        ts = [float(r["absolute_t_start"]) for r in rows if "absolute_t_start" in r]
        te = [float(r["absolute_t_end"]) for r in rows if "absolute_t_end" in r]
        md += f"| `{p.relative_to(ROOT)}` | {','.join(vids)} | {len(rows)} | {fmt_time(min(ts)) if ts else '-'}–{fmt_time(max(te)) if te else '-'} | Dev-segment reference |\n"

    md += "\n## Already-used intervals\n\n"
    md += "| Video | Start | End | Role |\n"
    md += "|-------|-------|-----|------|\n"
    for vid, s, e, role in USED_INTERVALS:
        md += f"| {vid} | {fmt_time(s)} | {fmt_time(e)} | {role} |\n"

    # Determine unused intervals within labeled range.
    labeled_start = events_start
    labeled_end = events_end
    used = sorted([(s, e) for vid, s, e, role in USED_INTERVALS if vid == "realcartest"])
    # merge used intervals
    merged = []
    for s, e in used:
        if not merged or s > merged[-1][1]:
            merged.append([s, e])
        else:
            merged[-1][1] = max(merged[-1][1], e)

    unused = []
    cur = labeled_start
    for s, e in merged:
        if s > cur:
            unused.append((cur, s))
        cur = max(cur, e)
    if cur < labeled_end:
        unused.append((cur, labeled_end))

    md += "\n## Unused intervals inside existing labels\n\n"
    md += "| Start | End | Duration | Positive-bin density | Long events | Point events | Usable for tuning? | Usable for final validation? | Notes |\n"
    md += "|-------|-----|----------|----------------------|-------------|--------------|--------------------|------------------------------|-------|\n"
    candidates = []
    for s, e in unused:
        n_bins, pos_bins, dens, long_ev, point_ev = count_pos_bins(s, e, events)
        duration = e - s
        # usable for tuning if sparse (<15%) and has long events; usable for final validation if >0 events and not used
        tune_ok = dens < 0.15 and len(long_ev) >= 1 and duration >= 100
        final_ok = duration >= 100 and len(long_ev) >= 1
        candidates.append({
            "start": s, "end": e, "duration": duration, "density": dens,
            "long": long_ev, "point": point_ev, "tune_ok": tune_ok, "final_ok": final_ok,
        })
        md += f"| {fmt_time(s)} | {fmt_time(e)} | {fmt_time(duration)} | {dens:.1%} | {len(long_ev)} | {len(point_ev)} | {'Yes' if tune_ok else 'No'} | {'Yes' if final_ok else 'No'} | Within realcartest labels |\n"

    # Beyond labeled range.
    md += "\n## Intervals outside existing labels\n\n"
    md += "| Video | Available labels | Notes |\n"
    md += "|-------|------------------|-------|\n"
    md += "| realcartest (after ~3920 s) | No | Center10 labels end near 3920 s; video continues but no O_ref exists. |\n"
    md += "| realcartest_5k | No | Video exists but no VEPC reference events found. |\n"
    md += "| test | No | Video exists but no VEPC reference events found. |\n"

    md += "\n## Conclusion\n\n"
    tune_candidates = [c for c in candidates if c["tune_ok"]]
    final_candidates = [c for c in candidates if c["final_ok"]]
    if tune_candidates and final_candidates:
        md += "Both tuning and final-validation intervals can be carved out of existing `center10_vlm_oracle_events.csv` labels. No new GPU/VLM labeling is required.\n\n"
        md += "Recommended tuning data:\n"
        for c in tune_candidates:
            md += f"- realcartest {fmt_time(c['start'])}–{fmt_time(c['end'])} (density {c['density']:.1%}, {len(c['long'])} long events)\n"
        md += "\nRecommended final-validation data (must be disjoint from tuning and all used intervals):\n"
        for c in final_candidates:
            md += f"- realcartest {fmt_time(c['start'])}–{fmt_time(c['end'])} (density {c['density']:.1%}, {len(c['long'])} long events)\n"
    else:
        md += "No usable interval inside existing labels satisfies the requirements for both tuning and final validation. **Step 3 (one-time labeling) is required.**\n\n"
        md += "Recommended labeling plan:\n"
        md += "- For tuning: choose a low-density interval within or beyond current labels, ideally <15% positive-bin density and containing long-interval events.\n"
        md += "- For final validation: choose a disjoint interval, preferably on a different video source, with non-overlapping time bounds.\n"
        md += "- Because no second labeled video exists, the final-validation interval will have to be a non-overlapping portion of `realcartest` unless new labels are generated for `realcartest_5k` or `test`.\n"

    out_path = OUTDIR / "data_availability_report.md"
    with open(out_path, "w") as f:
        f.write(md)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
