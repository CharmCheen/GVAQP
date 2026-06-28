#!/usr/bin/env python3
"""Write final old-strict vs conservative budget allocation report."""

import argparse
import csv
from collections import Counter
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, fail, load_config, validate_base_paths


def read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        fail(f"required CSV not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def truthy(value) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1"}


def risk_rank(value) -> int:
    return {"l0": 0, "0": 0, "l1": 1, "1": 1, "l2": 2, "2": 2, "l3": 3, "3": 3}.get(
        str(value).strip().lower(), -1
    )


def stats(labels: list[dict]) -> dict:
    old_pos = [
        row for row in labels
        if truthy(row.get("old_vlm_affected_ego", "")) and risk_rank(row.get("old_vlm_risk_level", "")) >= 2
    ]
    cons_pos = [row for row in labels if str(row.get("label_conservative_positive", "")).strip() == "1"]
    return {
        "n": len(labels),
        "old_pos": len(old_pos),
        "old_rate": len(old_pos) / len(labels) if labels else 0.0,
        "cons_pos": len(cons_pos),
        "cons_rate": len(cons_pos) / len(labels) if labels else 0.0,
        "downgraded": len([row for row in old_pos if str(row.get("label_conservative_positive", "")).strip() != "1"]),
        "negative_reasons": Counter(row.get("negative_reason", "") for row in labels if str(row.get("label_conservative_positive", "")) != "1"),
        "events": Counter(row.get("event_type", "") for row in labels),
    }


def best_low_budget(rows: list[dict], variant: str, metric_level: str) -> tuple[str, float, float]:
    vals = {}
    for row in rows:
        if row["label_variant"] != variant or row["metric_level"] != metric_level or float(row["budget_ratio"]) > 0.20:
            continue
        vals.setdefault(row["method"], []).append(float(row["recall_mean"]))
    means = {method: sum(values) / len(values) for method, values in vals.items()}
    if not means:
        return "NA", 0.0, 0.0
    best = max(means, key=means.get)
    return best, means[best], means.get("random", 0.0)


def avg_method(rows: list[dict], variant: str, metric_level: str, method_prefix: str | None = None, method: str | None = None) -> float:
    vals = []
    for row in rows:
        if row["label_variant"] != variant or row["metric_level"] != metric_level:
            continue
        if method is not None and row["method"] != method:
            continue
        if method_prefix is not None and not row["method"].startswith(method_prefix):
            continue
        vals.append(float(row["recall_mean"]))
    return sum(vals) / len(vals) if vals else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Write conservative final report.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    labels_path = output_dir / "vlm_labels_conservative_exact_102.csv"
    curve_path = output_dir / "budget_curve_conservative_exact_102.csv"
    sweep_path = output_dir / "budget_policy_sweep_conservative_exact_102.csv"
    report_path = output_dir / "conservative_budget_final_report.md"

    labels = read_csv(labels_path)
    curve = read_csv(curve_path)
    sweep = read_csv(sweep_path)
    s = stats(labels)
    old_clip, old_clip_val, old_random_clip = best_low_budget(curve, "old_strict", "clip")
    old_event, old_event_val, old_random_event = best_low_budget(curve, "old_strict", "event")
    cons_clip, cons_clip_val, cons_random_clip = best_low_budget(curve, "conservative", "clip")
    cons_event, cons_event_val, cons_random_event = best_low_budget(curve, "conservative", "event")
    cons_nms_event = avg_method(curve, "conservative", "event", method_prefix="temporal_nms")
    cons_top_count = avg_method(curve, "conservative", "clip", method="top_count")
    cons_top_naive = avg_method(curve, "conservative", "clip", method="top_naive")
    cons_ensemble = avg_method(curve, "conservative", "clip", method="ensemble_count_naive")
    cons_kin_clip = avg_method(curve, "conservative", "clip", method="top_kinematic")
    cons_kin_event = avg_method(curve, "conservative", "event", method="top_kinematic")

    lines = [
        "# Conservative 102-Clip Pseudo-GT Budget Allocation Final Report",
        "",
        "This report treats the full conservative Qwen3-VL-32B scan as pseudo-GT. It is not human ground truth.",
        "",
        "## Label Shift",
        "",
        f"- clips: {s['n']}",
        f"- old strict positives: {s['old_pos']} / {s['n']} = {s['old_rate']:.3f}",
        f"- conservative positives: {s['cons_pos']} / {s['n']} = {s['cons_rate']:.3f}",
        f"- old strict positives downgraded by conservative prompt: {s['downgraded']}",
        "",
        "## Conservative Negative Reasons",
        "",
        "| negative_reason | count |",
        "|---|---:|",
    ]
    for reason, count in s["negative_reasons"].most_common():
        lines.append(f"| {reason or 'none'} | {count} |")
    lines.extend(["", "## Conservative Event Type Distribution", "", "| event_type | count |", "|---|---:|"])
    for event, count in s["events"].most_common():
        lines.append(f"| {event or 'none'} | {count} |")
    lines.extend(
        [
            "",
            "## Low-Budget Results",
            "",
            "| variant | best clip recall method | clip recall | random clip recall | best event recall method | event recall | random event recall |",
            "|---|---|---:|---:|---|---:|---:|",
            f"| old_strict | {old_clip} | {old_clip_val:.3f} | {old_random_clip:.3f} | {old_event} | {old_event_val:.3f} | {old_random_event:.3f} |",
            f"| conservative | {cons_clip} | {cons_clip_val:.3f} | {cons_random_clip:.3f} | {cons_event} | {cons_event_val:.3f} | {cons_random_event:.3f} |",
            "",
            "## Policy Interpretation",
            "",
            f"- conservative temporal-NMS average event recall across budgets/methods: {cons_nms_event:.3f}",
            f"- conservative top_count/top_naive/ensemble_count_naive average clip recall: {cons_top_count:.3f}/{cons_top_naive:.3f}/{cons_ensemble:.3f}",
            f"- conservative top_kinematic average clip/event recall: {cons_kin_clip:.3f}/{cons_kin_event:.3f}",
        ]
    )
    if cons_clip != cons_event:
        lines.append("- Clip-level and event-level conclusions diverge under conservative pseudo-GT; temporal-aware allocation remains useful.")
    else:
        lines.append("- Clip-level and event-level winners align under conservative pseudo-GT; temporal-aware allocation evidence is weaker.")
    if s["cons_rate"] > 0.50:
        lines.append("- Conservative prompt is still too broad for rare-risk retrieval.")
    elif 0.10 <= s["cons_rate"] <= 0.30:
        lines.append("- Conservative prompt produces a useful rare-ish predicate range for budget allocation.")
    else:
        lines.append("- Conservative prompt is outside the 10%-30% target range; inspect examples before treating it as final.")
    lines.append("- Do not resume kinematic-v0 tuning as the main path; prioritize proxy anchors, temporal diversity, and conservative predicate validation.")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"final_report={report_path}")


if __name__ == "__main__":
    main()
