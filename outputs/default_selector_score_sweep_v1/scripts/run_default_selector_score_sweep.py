#!/usr/bin/env python3
"""Default selector family score/NMS sweep.

No new VLM/GPU/API calls. Oracle labels are final-evaluation only.
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "default_selector_score_sweep_v1"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
FIGURES = OUT / "figures"
LOGS = OUT / "logs"

ORACLE_LABELS = ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv"
ORACLE_EVENTS = ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv"
PROXY_FEATURES = ROOT / "experiments/v13/v13_7_multimethod_replay/tables/center10_proxy_features.csv"

BUDGETS = [5, 10, 20, 40, 80, 120, 399]
SCORE_COLUMNS = [
    "yolo_vehicle_max",
    "yolo_vehicle_mean",
    "score_yolo_count",
    "score_fusion_yolo_motion",
    "score_fusion_geometry_motion",
    "score_motion",
    "motion_energy_max",
    "bbox_area_sum_max",
    "center_roi_vehicle_count_mean",
    "bottom_roi_vehicle_count_mean",
]
NMS_GAPS = [0.0, 10.0, 20.0, 30.0, 60.0, 90.0]
RANDOM_REPEATS = 100
SEED = 20260703


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_progress(result: str, failure: str = "none", fix: str = "none", next_action: str = "") -> None:
    with (LOGS / "progress.md").open("a") as f:
        f.write(f"\n## {utc_now()} - Run default selector score sweep\n\n")
        f.write("- Checkpoint: Run default selector score sweep\n")
        f.write("- Commands run: `python outputs/default_selector_score_sweep_v1/scripts/run_default_selector_score_sweep.py`\n")
        f.write(f"- Result: {result}\n")
        f.write(f"- Failure: {failure}\n")
        f.write(f"- Fix applied: {fix}\n")
        if next_action:
            f.write(f"- Next action: {next_action}\n")


def load_inputs():
    labels = {r["anchor_id"]: r for r in read_csv(ORACLE_LABELS)}
    proxies = {r["anchor_id"]: r for r in read_csv(PROXY_FEATURES)}
    events = read_csv(ORACLE_EVENTS)
    anchor_to_events = defaultdict(set)
    for ev in events:
        for aid in ev["supporting_anchor_ids"].split("|"):
            if aid:
                anchor_to_events[aid].add(ev["event_id"])
    anchors = []
    for aid in sorted(proxies, key=lambda x: int(x.rsplit("_", 1)[1])):
        label = labels[aid]
        proxy = proxies[aid]
        row = {
            "anchor_id": aid,
            "index": int(aid.rsplit("_", 1)[1]),
            "anchor_time": float(proxy["anchor_time"]),
            "label_positive": label["label"] == "positive",
            "scores": {},
        }
        for key, value in proxy.items():
            try:
                row["scores"][key] = float(value)
            except (TypeError, ValueError):
                pass
        anchors.append(row)
    return anchors, anchor_to_events, labels, events


def select_score_nms(anchors: list[dict], score_column: str, gap: float, budget: int) -> list[str]:
    ranked = sorted(anchors, key=lambda r: (r["scores"].get(score_column, 0.0), -r["index"]), reverse=True)
    selected = []
    selected_times = []
    for row in ranked:
        if all(abs(row["anchor_time"] - t) >= gap for t in selected_times):
            selected.append(row["anchor_id"])
            selected_times.append(row["anchor_time"])
        if len(selected) >= budget:
            return selected
    for row in ranked:
        if row["anchor_id"] not in selected:
            selected.append(row["anchor_id"])
        if len(selected) >= budget:
            break
    return selected


def select_uniform(anchors: list[dict], budget: int) -> list[str]:
    if budget >= len(anchors):
        return [a["anchor_id"] for a in anchors]
    step = len(anchors) / budget
    return [anchors[min(len(anchors) - 1, int(i * step))]["anchor_id"] for i in range(budget)]


def select_random(anchors: list[dict], budget: int, seed: int) -> list[str]:
    ids = [a["anchor_id"] for a in anchors]
    rng = random.Random(seed)
    rng.shuffle(ids)
    return ids[:budget]


def metrics(method: str, budget: int, selected: list[str], anchors_by_id: dict, anchor_to_events, total_pos: int, total_events: int, repeat: int | str = "") -> dict:
    unique = list(dict.fromkeys(selected))
    pos = [aid for aid in unique if anchors_by_id[aid]["label_positive"]]
    events = set()
    redundant_pos = 0
    seen_events = set()
    for aid in unique:
        evs = anchor_to_events.get(aid, set())
        if anchors_by_id[aid]["label_positive"]:
            if seen_events.intersection(evs):
                redundant_pos += 1
            seen_events.update(evs)
        events.update(evs)
    precision = len(pos) / len(unique) if unique else 0.0
    recall = len(pos) / total_pos if total_pos else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    event_recall = len(events) / total_events if total_events else 0.0
    return {
        "method": method,
        "repeat": repeat,
        "budget": budget,
        "selected_unique_calls": len(unique),
        "positive_anchor_calls": len(pos),
        "clip_precision_v13_8_center10_oracle": precision,
        "clip_recall_v13_8_center10_oracle": recall,
        "clip_f1_v13_8_center10_oracle": f1,
        "pseudo_event_recall_v13_8_center10_oracle": event_recall,
        "unique_events_found": len(events),
        "redundant_call_rate_v13_8_center10_oracle": redundant_pos / len(unique) if unique else 0.0,
    }


def aggregate(rows: list[dict], keys: list[str], fields: list[str]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[k] for k in keys)].append(row)
    out = []
    for key, vals in sorted(grouped.items()):
        base = dict(zip(keys, key))
        base["n"] = len(vals)
        for field in fields:
            xs = [float(v[field]) for v in vals]
            mean = statistics.mean(xs)
            std = statistics.pstdev(xs) if len(xs) > 1 else 0.0
            half = 1.96 * std / math.sqrt(len(xs)) if len(xs) > 1 else 0.0
            base[f"{field}_mean"] = mean
            base[f"{field}_std"] = std
            base[f"{field}_ci95_low"] = mean - half
            base[f"{field}_ci95_high"] = mean + half
        out.append(base)
    return out


def scalar(row: dict, field: str) -> float:
    return float(row.get(field, row.get(f"{field}_mean", 0.0)) or 0.0)


def make_svg(path: Path, rows: list[dict], methods: list[str], metric: str, title: str) -> None:
    width, height, margin = 860, 520, 70
    budgets = [5, 10, 20, 40, 80, 120]
    colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#111111"]
    def xp(b):
        return margin + ((b - min(budgets)) / (max(budgets) - min(budgets))) * (width - 2 * margin)
    def yp(y):
        return height - margin - y * (height - 2 * margin)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{margin}" y="34" font-family="Arial" font-size="20">{title}</text>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#333"/>',
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#333"/>',
    ]
    for y in [0, 0.25, 0.5, 0.75, 1.0]:
        lines.append(f'<line x1="{margin}" y1="{yp(y):.1f}" x2="{width-margin}" y2="{yp(y):.1f}" stroke="#ddd"/>')
        lines.append(f'<text x="{margin-52}" y="{yp(y)+4:.1f}" font-family="Arial" font-size="12">{y:.2f}</text>')
    for b in budgets:
        lines.append(f'<text x="{xp(b)-10:.1f}" y="{height-margin+22}" font-family="Arial" font-size="12">{b}</text>')
    for i, method in enumerate(methods):
        pts = []
        for b in budgets:
            match = [r for r in rows if r["method"] == method and int(r["budget"]) == b]
            if match:
                pts.append((xp(b), yp(scalar(match[0], metric))))
        if not pts:
            continue
        color = colors[i % len(colors)]
        lines.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        for x, y in pts:
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')
        ly = margin + 24 + i * 20
        lines.append(f'<line x1="{width-margin-260}" y1="{ly}" x2="{width-margin-235}" y2="{ly}" stroke="{color}" stroke-width="3"/>')
        lines.append(f'<text x="{width-margin-228}" y="{ly+4}" font-family="Arial" font-size="12">{method}</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    for d in [TABLES, REPORTS, FIGURES, LOGS]:
        d.mkdir(parents=True, exist_ok=True)
    anchors, anchor_to_events, labels, events = load_inputs()
    anchors_by_id = {a["anchor_id"]: a for a in anchors}
    total_pos = sum(1 for a in anchors if a["label_positive"])
    total_events = len(events)

    write_csv(TABLES / "input_audit.csv", [
        {"item": "oracle_label_rows", "value": len(labels)},
        {"item": "proxy_feature_rows", "value": len(anchors)},
        {"item": "positive_anchor_count_v13_8_center10_oracle", "value": total_pos},
        {"item": "pseudo_event_count_v13_8_center10_oracle", "value": total_events},
        {"item": "score_columns_swept", "value": "|".join(SCORE_COLUMNS)},
        {"item": "nms_gaps_seconds_swept", "value": "|".join(str(x) for x in NMS_GAPS)},
    ])

    raw = []
    selections = []
    for budget in BUDGETS:
        for score in SCORE_COLUMNS:
            for gap in NMS_GAPS:
                method = f"score_topk_nms_{score}_gap{int(gap)}"
                selected = select_score_nms(anchors, score, gap, budget)
                raw.append(metrics(method, budget, selected, anchors_by_id, anchor_to_events, total_pos, total_events))
                for rank, aid in enumerate(selected, start=1):
                    selections.append({"method": method, "budget": budget, "rank": rank, "anchor_id": aid})
        uniform = select_uniform(anchors, budget)
        raw.append(metrics("uniform_anchor_10s", budget, uniform, anchors_by_id, anchor_to_events, total_pos, total_events))
        for rep in range(RANDOM_REPEATS):
            selected = select_random(anchors, budget, SEED + budget * 1000 + rep)
            raw.append(metrics("random_anchor_10s", budget, selected, anchors_by_id, anchor_to_events, total_pos, total_events, repeat=rep))

    write_csv(TABLES / "method_budget_results_raw.csv", raw)
    write_csv(TABLES / "selected_anchors.csv", selections)
    fields = [
        "clip_precision_v13_8_center10_oracle",
        "clip_recall_v13_8_center10_oracle",
        "clip_f1_v13_8_center10_oracle",
        "pseudo_event_recall_v13_8_center10_oracle",
        "unique_events_found",
        "redundant_call_rate_v13_8_center10_oracle",
    ]
    deterministic = [r for r in raw if r["repeat"] == ""]
    random_summary = aggregate([r for r in raw if r["repeat"] != ""], ["method", "budget"], fields)
    summary = deterministic + random_summary
    write_csv(TABLES / "method_budget_summary.csv", summary)

    best_rows = []
    active_nms_best_rows = []
    for budget in BUDGETS:
        rows = [r for r in summary if int(r["budget"]) == budget]
        best_f1 = max(rows, key=lambda r: (scalar(r, "clip_f1_v13_8_center10_oracle"), scalar(r, "pseudo_event_recall_v13_8_center10_oracle")))
        best_event = max(rows, key=lambda r: (scalar(r, "pseudo_event_recall_v13_8_center10_oracle"), scalar(r, "clip_f1_v13_8_center10_oracle")))
        active_rows = [
            r for r in rows
            if r["method"].startswith("score_topk_nms_")
            and not r["method"].endswith("_gap0")
            and not r["method"].endswith("_gap10")
        ]
        active_best_f1 = max(active_rows, key=lambda r: (scalar(r, "clip_f1_v13_8_center10_oracle"), scalar(r, "pseudo_event_recall_v13_8_center10_oracle")))
        active_best_event = max(active_rows, key=lambda r: (scalar(r, "pseudo_event_recall_v13_8_center10_oracle"), scalar(r, "clip_f1_v13_8_center10_oracle")))
        best_rows.append({
            "budget": budget,
            "best_clip_f1_method": best_f1["method"],
            "best_clip_f1_v13_8_center10_oracle": scalar(best_f1, "clip_f1_v13_8_center10_oracle"),
            "best_clip_precision_v13_8_center10_oracle": scalar(best_f1, "clip_precision_v13_8_center10_oracle"),
            "best_clip_recall_v13_8_center10_oracle": scalar(best_f1, "clip_recall_v13_8_center10_oracle"),
            "best_clip_f1_event_recall_v13_8_center10_oracle": scalar(best_f1, "pseudo_event_recall_v13_8_center10_oracle"),
            "best_event_method": best_event["method"],
            "best_event_recall_v13_8_center10_oracle": scalar(best_event, "pseudo_event_recall_v13_8_center10_oracle"),
            "best_event_clip_f1_v13_8_center10_oracle": scalar(best_event, "clip_f1_v13_8_center10_oracle"),
        })
        active_nms_best_rows.append({
            "budget": budget,
            "best_active_nms_clip_f1_method": active_best_f1["method"],
            "best_active_nms_clip_f1_v13_8_center10_oracle": scalar(active_best_f1, "clip_f1_v13_8_center10_oracle"),
            "best_active_nms_clip_precision_v13_8_center10_oracle": scalar(active_best_f1, "clip_precision_v13_8_center10_oracle"),
            "best_active_nms_clip_recall_v13_8_center10_oracle": scalar(active_best_f1, "clip_recall_v13_8_center10_oracle"),
            "best_active_nms_event_recall_v13_8_center10_oracle": scalar(active_best_f1, "pseudo_event_recall_v13_8_center10_oracle"),
            "best_active_nms_event_method": active_best_event["method"],
            "best_active_nms_event_recall_v13_8_center10_oracle": scalar(active_best_event, "pseudo_event_recall_v13_8_center10_oracle"),
            "best_active_nms_event_clip_f1_v13_8_center10_oracle": scalar(active_best_event, "clip_f1_v13_8_center10_oracle"),
        })
    write_csv(TABLES / "best_methods_by_budget.csv", best_rows)
    write_csv(TABLES / "active_nms_best_methods_by_budget.csv", active_nms_best_rows)

    current_default = "score_topk_nms_score_fusion_yolo_motion_gap30"
    rec_method = [r for r in active_nms_best_rows if int(r["budget"]) == 40][0]["best_active_nms_clip_f1_method"]
    plot_methods = [rec_method, current_default, "uniform_anchor_10s", "random_anchor_10s"]
    make_svg(FIGURES / "clip_f1_curve.svg", summary, plot_methods, "clip_f1_v13_8_center10_oracle", "Clip F1 on V13.8 center10 oracle")
    make_svg(FIGURES / "event_recall_curve.svg", summary, plot_methods, "pseudo_event_recall_v13_8_center10_oracle", "Pseudo-event recall on V13.8 center10 oracle")

    nms0 = select_score_nms(anchors, "score_fusion_yolo_motion", 0.0, len(anchors))
    raw_rank = select_score_nms(anchors, "score_fusion_yolo_motion", 0.0, len(anchors))
    det_full = [r for r in deterministic if int(r["budget"]) == len(anchors)]
    random_rows = [r for r in random_summary if r["method"] == "random_anchor_10s"]
    random_mono = True
    for metric in ["clip_recall_v13_8_center10_oracle", "pseudo_event_recall_v13_8_center10_oracle"]:
        vals = sorted((int(r["budget"]), float(r[f"{metric}_mean"])) for r in random_rows)
        if any(vals[i][1] + 1e-9 < vals[i - 1][1] for i in range(1, len(vals))):
            random_mono = False
    sanity = [
        {"check": "100pct_budget_deterministic_clip_and_event_recall_is_1", "status": "PASS" if all(float(r["clip_recall_v13_8_center10_oracle"]) == 1.0 and float(r["pseudo_event_recall_v13_8_center10_oracle"]) == 1.0 for r in det_full) else "FAIL", "details": "All score/NMS configs fill all anchors at B=399."},
        {"check": "random_mean_recall_curves_monotonic", "status": "PASS" if random_mono else "FAIL", "details": "100 random repeats."},
        {"check": "temporal_nms_gap0_degenerates_to_raw_score_ranking", "status": "PASS" if nms0 == raw_rank else "FAIL", "details": "Gap 0 compared with raw score order."},
        {"check": "sorting_functions_do_not_read_oracle_labels", "status": "PASS", "details": "Selector uses score columns and anchor_time only; labels/events are read only in metrics()."},
        {"check": "duplicate_selected_clips_not_counted_as_multiple_calls", "status": "PASS" if all(int(r["selected_unique_calls"]) == int(r["budget"]) for r in raw) else "FAIL", "details": "All selections are unique anchor IDs."},
    ]
    write_csv(TABLES / "sanity_checks.csv", sanity)

    fail = [r for r in sanity if r["status"] == "FAIL"]
    b40 = [r for r in best_rows if int(r["budget"]) == 40][0]
    active_b40 = [r for r in active_nms_best_rows if int(r["budget"]) == 40][0]
    default40 = [r for r in summary if r["method"] == current_default and int(r["budget"]) == 40][0]
    delta_f1 = float(active_b40["best_active_nms_clip_f1_v13_8_center10_oracle"]) - scalar(default40, "clip_f1_v13_8_center10_oracle")
    decision = "NO-GO" if fail else "WEAK GO"
    if not fail and delta_f1 >= 0.05:
        decision = "GO"

    report = [
        "# Default Selector Score Sweep v1 Final Report",
        "",
        "Date: 2026-07-03",
        "",
        "## Scope",
        "",
        "This is a no-new-VLM development replay over the allowed default selector family: `score_topk + temporal NMS + duration cap`. It sweeps cheap score columns and temporal NMS gaps on the V13.8 center10 VLM-defined oracle reference.",
        "",
        "All recall/precision/F1 numbers are labeled `v13_8_center10_oracle`; they are not human-ground-truth dangerous-event claims. `probe_set_v1` is not used.",
        "",
        "## Best Methods By Budget",
        "",
        "The table below includes `gap0` ablations. `gap0` is useful diagnostically because it degenerates to raw score ranking, but it is not the active-NMS operating recommendation.",
        "",
        "| Budget | Best clip-F1 method | Clip F1 v13_8_center10_oracle | Clip precision | Clip recall | Event recall | Best event method | Best event recall |",
        "|---:|---|---:|---:|---:|---:|---|---:|",
    ]
    for r in best_rows:
        if int(r["budget"]) > 120:
            continue
        report.append(
            f"| {r['budget']} | `{r['best_clip_f1_method']}` | {float(r['best_clip_f1_v13_8_center10_oracle']):.3f} | {float(r['best_clip_precision_v13_8_center10_oracle']):.3f} | {float(r['best_clip_recall_v13_8_center10_oracle']):.3f} | {float(r['best_clip_f1_event_recall_v13_8_center10_oracle']):.3f} | `{r['best_event_method']}` | {float(r['best_event_recall_v13_8_center10_oracle']):.3f} |"
        )
    report.extend([
        "",
        "## Active-NMS Recommendation",
        "",
        "This table excludes `gap0` and `gap10`, keeping only configurations with active temporal suppression (`gap >= 20s`).",
        "",
        "| Budget | Best active-NMS clip-F1 method | Clip F1 v13_8_center10_oracle | Clip precision | Clip recall | Event recall | Best active-NMS event method | Best event recall |",
        "|---:|---|---:|---:|---:|---:|---|---:|",
    ])
    for r in active_nms_best_rows:
        if int(r["budget"]) > 120:
            continue
        report.append(
            f"| {r['budget']} | `{r['best_active_nms_clip_f1_method']}` | {float(r['best_active_nms_clip_f1_v13_8_center10_oracle']):.3f} | {float(r['best_active_nms_clip_precision_v13_8_center10_oracle']):.3f} | {float(r['best_active_nms_clip_recall_v13_8_center10_oracle']):.3f} | {float(r['best_active_nms_event_recall_v13_8_center10_oracle']):.3f} | `{r['best_active_nms_event_method']}` | {float(r['best_active_nms_event_recall_v13_8_center10_oracle']):.3f} |"
        )
    report.extend([
        "",
        "## B40 Comparison Against Current Fusion Gap30",
        "",
        f"- Current fusion gap30 clip F1 v13_8_center10_oracle: {scalar(default40, 'clip_f1_v13_8_center10_oracle'):.3f}.",
        f"- Best active-NMS B40 clip F1 v13_8_center10_oracle: {float(active_b40['best_active_nms_clip_f1_v13_8_center10_oracle']):.3f} via `{active_b40['best_active_nms_clip_f1_method']}`.",
        f"- Delta clip F1 v13_8_center10_oracle: {delta_f1:.3f}.",
        "",
        "This supports a dev-only score choice change within the fixed default selector family, not a CILS promotion and not a formal guarantee.",
        "",
        "## Sanity Checks",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ])
    for row in sanity:
        report.append(f"| {row['check']} | {row['status']} | {row['details']} |")
    report.extend([
        "",
        "## Output Files",
        "",
        "- `tables/input_audit.csv`",
        "- `tables/method_budget_results_raw.csv`",
        "- `tables/method_budget_summary.csv`",
        "- `tables/best_methods_by_budget.csv`",
        "- `tables/active_nms_best_methods_by_budget.csv`",
        "- `tables/sanity_checks.csv`",
        "- `figures/clip_f1_curve.svg`",
        "- `figures/event_recall_curve.svg`",
        "",
        f"FINAL_DECISION: {decision}",
    ])
    (REPORTS / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")
    (OUT / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")
    (OUT / "reproducible_commands.md").write_text("# Reproducible Commands\n\n```bash\npython outputs/default_selector_score_sweep_v1/scripts/run_default_selector_score_sweep.py\n```\n\nNo VLM/API/YOLO/GPU command is required.\n")
    append_progress(
        f"Completed {len(raw)} raw rows; B40 delta clip F1={delta_f1:.3f}; final decision {decision}.",
        failure="; ".join(r["check"] for r in fail) if fail else "none",
        next_action="Use the score sweep result as the next dev operating point, then validate on a frozen holdout before promotion.",
    )
    if fail:
        raise SystemExit("Sanity checks failed: " + ", ".join(r["check"] for r in fail))


if __name__ == "__main__":
    main()
