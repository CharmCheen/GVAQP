#!/usr/bin/env python3
"""Budget simulation for roadclip_budget_v2 conservative pseudo-GT."""

from __future__ import annotations

import argparse
import math
import random
from collections import defaultdict
from pathlib import Path

from common import DEFAULT_CONFIG, clamp01, ensure_output_dir, load_config, read_csv, to_float, validate_base_paths, write_blocked, write_csv


METHODS = [
    "random",
    "uniform_time",
    "top_count",
    "top_naive",
    "top_kinematic",
    "ensemble_count_naive",
    "ensemble_all_proxy",
    "temporal_nms_count",
    "temporal_nms_naive",
    "temporal_nms_ensemble",
    "uniform_expansion",
    "proxy_then_expansion_count",
    "proxy_then_expansion_naive",
    "proxy_then_expansion_ensemble",
]
SWEEP_METHODS = [
    "temporal_nms_count",
    "temporal_nms_naive",
    "temporal_nms_ensemble",
    "uniform_expansion",
    "proxy_then_expansion_count",
    "proxy_then_expansion_naive",
    "proxy_then_expansion_ensemble",
]


def normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def load_eval(output_dir: Path) -> list[dict]:
    proxy_path = output_dir / "proxy_scores.csv"
    label_path = output_dir / "vlm_labels_conservative.csv"
    if not proxy_path.is_file() or not label_path.is_file():
        path = write_blocked(output_dir, "BLOCKED_budget_missing_inputs.md", "BLOCKED: Budget Missing Inputs", ["Need proxy_scores.csv and vlm_labels_conservative.csv."])
        print(f"blocked_report={path}")
        return []
    proxies = {r["clip_id"]: r for r in read_csv(proxy_path)}
    labels = {r["clip_id"]: r for r in read_csv(label_path)}
    rows = []
    ids = [cid for cid in proxies if cid in labels]
    count_norm = dict(zip(ids, normalize([to_float(proxies[cid]["score_count"]) for cid in ids])))
    naive_norm = dict(zip(ids, normalize([to_float(proxies[cid]["score_naive"]) for cid in ids])))
    kin_norm = dict(zip(ids, normalize([to_float(proxies[cid]["score_kinematic"]) for cid in ids])))
    for cid in ids:
        p, l = proxies[cid], labels[cid]
        label = 1 if l.get("conservative_positive") == "yes" else 0
        row = {
            **p,
            "vlm_label": label,
            "score_count": to_float(p["score_count"]),
            "score_naive": to_float(p["score_naive"]),
            "score_kinematic": to_float(p["score_kinematic"]),
            "score_count_norm": count_norm[cid],
            "score_naive_norm": naive_norm[cid],
            "score_kinematic_norm": kin_norm[cid],
        }
        row["ensemble_count_naive_score"] = row["score_count_norm"] + row["score_naive_norm"]
        row["ensemble_all_proxy_score"] = row["score_count_norm"] + row["score_naive_norm"] + row["score_kinematic_norm"]
        rows.append(row)
    rows.sort(key=lambda r: (r["video_id"], to_float(r["start_time"])))
    return rows


def positive_events(rows: list[dict], merge_gap: float) -> list[dict]:
    positives = [r for r in rows if int(r["vlm_label"]) == 1]
    events = []
    for r in positives:
        st, en = to_float(r["start_time"]), to_float(r["end_time"])
        if not events or r["video_id"] != events[-1]["video_id"] or st - events[-1]["last_start"] > merge_gap:
            events.append({"video_id": r["video_id"], "start": st, "end": en, "last_start": st, "clip_ids": [r["clip_id"]]})
        else:
            events[-1]["end"] = max(events[-1]["end"], en)
            events[-1]["last_start"] = st
            events[-1]["clip_ids"].append(r["clip_id"])
    return events


def top_by(rows: list[dict], score: str, budget: int) -> list[str]:
    return [r["clip_id"] for r in sorted(rows, key=lambda r: (-float(r[score]), r["video_id"], to_float(r["start_time"])))[:budget]]


def uniform_time(rows: list[dict], budget: int) -> list[str]:
    if budget >= len(rows):
        return [r["clip_id"] for r in rows]
    if budget <= 1:
        return [rows[0]["clip_id"]]
    return [rows[int(round(i * (len(rows) - 1) / (budget - 1)))]["clip_id"] for i in range(budget)]


def temporal_nms(rows: list[dict], score: str, budget: int, gap: float) -> list[str]:
    selected = []
    for r in sorted(rows, key=lambda x: -float(x[score])):
        st = to_float(r["start_time"])
        if all(r["video_id"] != s["video_id"] or abs(st - to_float(s["start_time"])) > gap for s in selected):
            selected.append(r)
            if len(selected) >= budget:
                break
    if len(selected) < budget:
        for r in sorted(rows, key=lambda x: -float(x[score])):
            if r not in selected:
                selected.append(r)
                if len(selected) >= budget:
                    break
    return [r["clip_id"] for r in selected[:budget]]


def expansion(rows: list[dict], anchors: list[str], budget: int, radius: int, anchor_fraction: float) -> list[str]:
    by_video = defaultdict(list)
    pos = {}
    for r in rows:
        by_video[r["video_id"]].append(r)
    for video_rows in by_video.values():
        video_rows.sort(key=lambda r: to_float(r["start_time"]))
        for i, r in enumerate(video_rows):
            pos[r["clip_id"]] = (video_rows, i)
    selected = []
    anchor_budget = max(1, min(budget, int(math.ceil(budget * anchor_fraction))))
    for cid in anchors[:anchor_budget]:
        if cid not in selected:
            selected.append(cid)
        if len(selected) >= budget:
            return selected[:budget]
        video_rows, idx = pos[cid]
        for d in range(1, radius + 1):
            for j in [idx - d, idx + d]:
                if 0 <= j < len(video_rows):
                    nid = video_rows[j]["clip_id"]
                    if nid not in selected:
                        selected.append(nid)
                        if len(selected) >= budget:
                            return selected[:budget]
    for cid in anchors:
        if cid not in selected:
            selected.append(cid)
            if len(selected) >= budget:
                break
    return selected[:budget]


def select(rows: list[dict], method: str, budget: int, seed: int, gap: float, radius: int, anchor_fraction: float) -> list[str]:
    if method == "random":
        rng = random.Random(seed)
        ids = [r["clip_id"] for r in rows]
        rng.shuffle(ids)
        return ids[:budget]
    if method == "uniform_time":
        return uniform_time(rows, budget)
    score_map = {
        "top_count": "score_count",
        "top_naive": "score_naive",
        "top_kinematic": "score_kinematic",
        "ensemble_count_naive": "ensemble_count_naive_score",
        "ensemble_all_proxy": "ensemble_all_proxy_score",
        "temporal_nms_count": "score_count",
        "temporal_nms_naive": "score_naive",
        "temporal_nms_ensemble": "ensemble_count_naive_score",
        "proxy_then_expansion_count": "score_count",
        "proxy_then_expansion_naive": "score_naive",
        "proxy_then_expansion_ensemble": "ensemble_count_naive_score",
    }
    if method == "uniform_expansion":
        return expansion(rows, uniform_time(rows, budget), budget, radius, anchor_fraction)
    score = score_map[method]
    if method.startswith("temporal_nms"):
        return temporal_nms(rows, score, budget, gap)
    if method.startswith("proxy_then_expansion"):
        return expansion(rows, top_by(rows, score, len(rows)), budget, radius, anchor_fraction)
    return top_by(rows, score, budget)


def evaluate_selection(rows: list[dict], selected: list[str], events: list[dict]) -> dict:
    selected_set = set(selected)
    positives = {r["clip_id"] for r in rows if int(r["vlm_label"]) == 1}
    tp = len(selected_set & positives)
    recall = tp / len(positives) if positives else 0.0
    precision = tp / len(selected_set) if selected_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    hit = sum(1 for e in events if selected_set & set(e["clip_ids"]))
    event_recall = hit / len(events) if events else 0.0
    return {"recall": recall, "precision": precision, "f1": f1, "positives_found": tp, "event_recall": event_recall, "num_events": len(events), "num_events_hit": hit}


def mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
    return mean, std


def run_methods(rows: list[dict], cfg: dict) -> tuple[list[dict], list[dict]]:
    bcfg = cfg.get("budget") or {}
    ratios = [float(x) for x in bcfg.get("budget_ratios", [0.05, 0.1, 0.2])]
    seeds = int(bcfg.get("random_seeds", 20))
    gap = float(bcfg.get("temporal_nms_gap_sec", 4))
    radius = int(bcfg.get("expansion_radius", 2))
    anchor_fraction = float(bcfg.get("anchor_fraction", 0.25))
    events = positive_events(rows, float(bcfg.get("event_merge_gap_sec", 4)))
    raw = []
    for ratio in ratios:
        budget = max(1, math.ceil(len(rows) * ratio))
        for method in METHODS:
            method_seeds = range(seeds) if method == "random" else [0]
            for seed in method_seeds:
                selected = select(rows, method, budget, seed, gap, radius, anchor_fraction)
                metrics = evaluate_selection(rows, selected, events)
                raw.append({"method": method, "budget_ratio": ratio, "budget": budget, "seed": seed, **metrics})
    agg = []
    groups = defaultdict(list)
    for r in raw:
        groups[(r["method"], r["budget_ratio"], r["budget"])].append(r)
    for (method, ratio, budget), vals in groups.items():
        rec_m, rec_s = mean_std([v["recall"] for v in vals])
        prec_m, prec_s = mean_std([v["precision"] for v in vals])
        f1_m, f1_s = mean_std([v["f1"] for v in vals])
        ev_m, ev_s = mean_std([v["event_recall"] for v in vals])
        agg.append(
            {
                "method": method,
                "budget_ratio": ratio,
                "budget": budget,
                "recall_mean": rec_m,
                "recall_std": rec_s,
                "precision_mean": prec_m,
                "precision_std": prec_s,
                "f1_mean": f1_m,
                "f1_std": f1_s,
                "event_recall": ev_m,
                "event_recall_std": ev_s,
                "num_events": len(events),
                "num_events_hit": sum(v["num_events_hit"] for v in vals) / len(vals),
                "total_positives": sum(int(r["vlm_label"]) for r in rows),
                "calls_saved_fraction": 1.0 - budget / len(rows),
            }
        )
    return raw, agg


def run_sweep(rows: list[dict], cfg: dict) -> list[dict]:
    bcfg = cfg.get("budget") or {}
    sweep_cfg = bcfg.get("policy_sweep") or {}
    events = positive_events(rows, float(bcfg.get("event_merge_gap_sec", 4)))
    rows_out = []
    for ratio in [float(x) for x in bcfg.get("budget_ratios", [])]:
        budget = max(1, math.ceil(len(rows) * ratio))
        for method in SWEEP_METHODS:
            if method.startswith("temporal_nms"):
                for gap in sweep_cfg.get("temporal_nms_gap_sec", [0, 2, 4, 6, 8]):
                    selected = select(rows, method, budget, 0, float(gap), 0, 0.25)
                    rows_out.append({"method": method, "budget_ratio": ratio, "budget": budget, "temporal_nms_gap_sec": gap, "expansion_radius": "", "anchor_fraction": "", **evaluate_selection(rows, selected, events)})
            else:
                for radius in sweep_cfg.get("expansion_radius", [1, 2, 3]):
                    for anchor_fraction in sweep_cfg.get("anchor_fraction", [0.25, 0.5, 0.75]):
                        selected = select(rows, method, budget, 0, 0.0, int(radius), float(anchor_fraction))
                        rows_out.append({"method": method, "budget_ratio": ratio, "budget": budget, "temporal_nms_gap_sec": "", "expansion_radius": radius, "anchor_fraction": anchor_fraction, **evaluate_selection(rows, selected, events)})
    return rows_out


def best_low(agg: list[dict], metric: str) -> tuple[str, float]:
    low = [r for r in agg if float(r["budget_ratio"]) in {0.05, 0.10, 0.15, 0.20}]
    by = defaultdict(list)
    for r in low:
        by[r["method"]].append(float(r[metric]))
    best = sorted(((k, sum(v) / len(v)) for k, v in by.items()), key=lambda x: x[1], reverse=True)
    return best[0] if best else ("none", 0.0)


def write_reports(output_dir: Path, rows: list[dict], agg: list[dict], sweep: list[dict]) -> None:
    events = positive_events(rows, 4.0)
    positives = sum(int(r["vlm_label"]) for r in rows)
    avg_run = positives / len(events) if events else 0.0
    clip_m, clip_v = best_low(agg, "recall_mean")
    event_m, event_v = best_low(agg, "event_recall")
    random_clip = sum(float(r["recall_mean"]) for r in agg if r["method"] == "random" and float(r["budget_ratio"]) in {0.05, 0.10, 0.15, 0.20}) / 4
    random_event = sum(float(r["event_recall"]) for r in agg if r["method"] == "random" and float(r["budget_ratio"]) in {0.05, 0.10, 0.15, 0.20}) / 4
    lines = [
        "# Roadclip Budget Report",
        "",
        f"- clips: {len(rows)}",
        f"- conservative positives: {positives} / {len(rows)} = {positives / len(rows) if rows else 0:.3f}",
        f"- positive events: {len(events)}",
        f"- average positive run length: {avg_run:.3f}",
        f"- low-budget best clip recall: `{clip_m}` = {clip_v:.3f}; random = {random_clip:.3f}",
        f"- low-budget best event recall: `{event_m}` = {event_v:.3f}; random = {random_event:.3f}",
        "",
        "## Results",
        "",
        "| method | budget | recall | precision | F1 | event_recall | events_hit |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(agg, key=lambda x: (float(x["budget_ratio"]), x["method"])):
        lines.append(f"| {r['method']} | {r['budget_ratio']:.2f} | {r['recall_mean']:.3f} | {r['precision_mean']:.3f} | {r['f1_mean']:.3f} | {r['event_recall']:.3f} | {r['num_events_hit']:.2f}/{r['num_events']} |")
    (output_dir / "budget_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    key = [r for r in sweep if float(r["budget_ratio"]) in {0.10, 0.20, 0.30}]
    lines = ["# Budget Policy Sweep Report", "", "| budget | best clip policy | recall | best event policy | event_recall |", "|---:|---|---:|---|---:|"]
    for ratio in [0.10, 0.20, 0.30]:
        sub = [r for r in key if abs(float(r["budget_ratio"]) - ratio) < 1e-9]
        if not sub:
            continue
        bc = max(sub, key=lambda r: float(r["recall"]))
        be = max(sub, key=lambda r: float(r["event_recall"]))
        lines.append(f"| {ratio:.2f} | {bc['method']} | {bc['recall']:.3f} | {be['method']} | {be['event_recall']:.3f} |")
    (output_dir / "budget_policy_sweep_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_curve(output_dir: Path, agg: list[dict]) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    methods = ["random", "top_count", "top_naive", "ensemble_count_naive", "temporal_nms_count", "temporal_nms_naive", "proxy_then_expansion_count", "top_kinematic"]
    fig, ax = plt.subplots(figsize=(9, 5))
    for method in methods:
        sub = sorted([r for r in agg if r["method"] == method], key=lambda r: r["budget_ratio"])
        if sub:
            ax.plot([r["budget_ratio"] for r in sub], [r["recall_mean"] for r in sub], marker="o", label=method)
    ax.set_xlabel("Budget ratio")
    ax.set_ylabel("Clip recall")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "budget_curve.png", dpi=160)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run budget simulation.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    rows = load_eval(output_dir)
    if not rows:
        return
    raw, agg = run_methods(rows, cfg)
    sweep = run_sweep(rows, cfg)
    write_csv(output_dir / "budget_curve_raw.csv", raw, ["method", "budget_ratio", "budget", "seed", "recall", "precision", "f1", "positives_found", "event_recall", "num_events", "num_events_hit"])
    write_csv(output_dir / "budget_curve.csv", agg, ["method", "budget_ratio", "budget", "recall_mean", "recall_std", "precision_mean", "precision_std", "f1_mean", "f1_std", "event_recall", "event_recall_std", "num_events", "num_events_hit", "total_positives", "calls_saved_fraction"])
    write_csv(output_dir / "budget_policy_sweep.csv", sweep, ["method", "budget_ratio", "budget", "temporal_nms_gap_sec", "expansion_radius", "anchor_fraction", "recall", "precision", "f1", "positives_found", "event_recall", "num_events", "num_events_hit"])
    write_reports(output_dir, rows, agg, sweep)
    plot_curve(output_dir, agg)
    print(f"budget_curve={output_dir / 'budget_curve.csv'}")
    print(f"budget_report={output_dir / 'budget_report.md'}")
    print(f"budget_policy_sweep={output_dir / 'budget_policy_sweep.csv'}")


if __name__ == "__main__":
    main()
