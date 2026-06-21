#!/usr/bin/env python3
"""Generate final acceleration report for roadclip_budget_v2."""

from __future__ import annotations

import argparse
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, load_config, read_csv, to_float, validate_base_paths


LOW_RATIOS = {0.05, 0.10, 0.15, 0.20}


def avg_by_method(rows: list[dict], metric: str) -> list[tuple[str, float]]:
    by = {}
    for r in rows:
        if float(r["budget_ratio"]) not in LOW_RATIOS:
            continue
        by.setdefault(r["method"], []).append(to_float(r[metric]))
    return sorted(((m, sum(v) / len(v)) for m, v in by.items() if v), key=lambda x: x[1], reverse=True)


def budget_to_event_recall(rows: list[dict], threshold: float = 0.8) -> tuple[str, float, float]:
    candidates = [r for r in rows if to_float(r["event_recall"]) >= threshold and r["method"] != "random"]
    if not candidates:
        return "none", 0.0, 0.0
    best = sorted(candidates, key=lambda r: (to_float(r["budget_ratio"]), -to_float(r["event_recall"])))[0]
    return best["method"], to_float(best["budget_ratio"]), to_float(best["calls_saved_fraction"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate final acceleration report.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    required = ["road_segments.csv", "clips.csv", "vlm_labels_conservative.csv", "budget_curve.csv", "budget_policy_sweep.csv"]
    missing = [name for name in required if not (output_dir / name).is_file()]
    if missing:
        status = "BLOCKED_VLM_OR_PROXY_FAILURE"
        lines = ["# Roadclip V2 Final Acceleration Report", "", f"STATUS: {status}", "", "Missing required outputs:", ""]
        lines.extend(f"- `{name}`" for name in missing)
        (output_dir / "final_acceleration_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"final_report={output_dir / 'final_acceleration_report.md'}")
        return

    segments = read_csv(output_dir / "road_segments.csv")
    clips = read_csv(output_dir / "clips.csv")
    labels = read_csv(output_dir / "vlm_labels_conservative.csv")
    curve = read_csv(output_dir / "budget_curve.csv")
    sweep = read_csv(output_dir / "budget_policy_sweep.csv")
    positives = [r for r in labels if r["conservative_positive"] == "yes"]
    num_events = int(float(curve[0]["num_events"])) if curve else 0
    positive_rate = len(positives) / len(labels) if labels else 0.0
    road_duration = sum(to_float(s["end_time"]) - to_float(s["start_time"]) for s in segments)
    avg_run = len(positives) / num_events if num_events else 0.0
    best_clip = avg_by_method(curve, "recall_mean")
    best_event = avg_by_method(curve, "event_recall")
    random_clip = dict(best_clip).get("random", 0.0)
    random_event = dict(best_event).get("random", 0.0)
    clip_method, clip_val = best_clip[0] if best_clip else ("none", 0.0)
    event_method, event_val = best_event[0] if best_event else ("none", 0.0)
    best_nonrandom_clip = next(((m, v) for m, v in best_clip if m != "random"), ("none", 0.0))
    best_nonrandom_event = next(((m, v) for m, v in best_event if m != "random"), ("none", 0.0))
    clip_gain = best_nonrandom_clip[1] / random_clip if random_clip > 0 else 999.0 if best_nonrandom_clip[1] > 0 else 0.0
    event_gain = best_nonrandom_event[1] / random_event if random_event > 0 else 999.0 if best_nonrandom_event[1] > 0 else 0.0
    reach_method, reach_budget, call_saving = budget_to_event_recall(curve, 0.8)

    data_insufficient = len(clips) < 100 or num_events < 3 or road_duration < 120
    proxy_failure = len(labels) < max(1, int(0.9 * len(clips)))
    pass_accel = (
        len(clips) >= 200
        and 0.05 <= positive_rate <= 0.40
        and num_events >= 5
        and (clip_gain >= 1.5 or event_gain >= 1.5)
        and not proxy_failure
    )
    if proxy_failure:
        status = "BLOCKED_VLM_OR_PROXY_FAILURE"
    elif data_insufficient:
        status = "BLOCKED_INSUFFICIENT_DATA"
    elif pass_accel:
        status = "PASS_PRELIMINARY_ACCELERATION"
    else:
        status = "FAIL_NO_ACCELERATION"

    lines = [
        "# Roadclip V2 Final Acceleration Report",
        "",
        f"STATUS: {status}",
        "",
        "These VLM labels are conservative Qwen3-VL pseudo-GT, not human ground truth.",
        "",
        "## Dataset",
        "",
        f"1. road-driving segments: {len(segments)}",
        f"2. valid road-driving duration sec: {road_duration:.1f}",
        f"3. clip pool size: {len(clips)}",
        f"4. conservative positive rate: {len(positives)} / {len(labels)} = {positive_rate:.3f}",
        f"5. positive events: {num_events}",
        f"6. average positive run length: {avg_run:.3f}",
        f"7. positive density sufficient: {'yes' if 0.05 <= positive_rate <= 0.40 and num_events >= 5 else 'no'}",
        f"8. better than old 102-clip smoke set: {'yes' if len(clips) > 102 and road_duration >= 120 else 'no'}",
        "",
        "## Low-Budget Acceleration",
        "",
        f"9. 5%-20% best clip recall method: `{clip_method}` = {clip_val:.3f}",
        f"10. 5%-20% best event recall method: `{event_method}` = {event_val:.3f}",
        f"11. random clip recall avg: {random_clip:.3f}; best non-random gain: {clip_gain:.2f}x by `{best_nonrandom_clip[0]}`",
        f"12. random event recall avg: {random_event:.3f}; best non-random gain: {event_gain:.2f}x by `{best_nonrandom_event[0]}`",
        f"13. budget needed to reach 0.8 event recall: `{reach_method}` at {reach_budget:.2f} budget; approximate VLM call saving {call_saving:.3f}",
        "",
        "## Method Interpretation",
        "",
        f"- top_count avg clip recall: {dict(best_clip).get('top_count', 0.0):.3f}",
        f"- top_naive avg clip recall: {dict(best_clip).get('top_naive', 0.0):.3f}",
        f"- ensemble_count_naive avg clip recall: {dict(best_clip).get('ensemble_count_naive', 0.0):.3f}",
        f"- top_kinematic avg clip recall: {dict(best_clip).get('top_kinematic', 0.0):.3f}",
        f"- temporal_nms_count avg event recall: {dict(best_event).get('temporal_nms_count', 0.0):.3f}",
        f"- temporal_nms_naive avg event recall: {dict(best_event).get('temporal_nms_naive', 0.0):.3f}",
        f"- proxy_then_expansion_count avg clip recall: {dict(best_clip).get('proxy_then_expansion_count', 0.0):.3f}",
        "",
        "## Policy Sweep Summary",
        "",
    ]
    for ratio in [0.10, 0.20, 0.30]:
        sub = [r for r in sweep if abs(to_float(r["budget_ratio"]) - ratio) < 1e-9]
        if sub:
            bc = max(sub, key=lambda r: to_float(r["recall"]))
            be = max(sub, key=lambda r: to_float(r["event_recall"]))
            lines.append(f"- {ratio:.2f} budget: best clip `{bc['method']}` recall={to_float(bc['recall']):.3f}; best event `{be['method']}` event_recall={to_float(be['event_recall']):.3f}")
    lines += ["", "## Decision", ""]
    if status == "PASS_PRELIMINARY_ACCELERATION":
        lines.append("- Current evidence supports preliminary semantic clip query acceleration under conservative VLM pseudo-GT.")
        lines.append("- Next step: expand to more videos and run human audit on the audit package.")
    elif status == "FAIL_NO_ACCELERATION":
        lines.append("- Data are sufficient, but non-random methods are close to random. Proxy correlation or temporal structure is too weak.")
    elif status == "BLOCKED_INSUFFICIENT_DATA":
        lines.append("- Data are insufficient for a defensible acceleration claim. Re-cut from more or better source videos.")
    else:
        lines.append("- Pipeline failure prevents a valid conclusion. Inspect blocked reports and missing outputs.")
    (output_dir / "final_acceleration_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"final_report={output_dir / 'final_acceleration_report.md'}")
    print(f"status={status}")


if __name__ == "__main__":
    main()
