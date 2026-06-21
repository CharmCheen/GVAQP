#!/usr/bin/env python3
"""VLM-as-oracle acceleration benchmark for expanded roadclip_budget_v2."""

from __future__ import annotations

import argparse
import math
import random
from collections import defaultdict
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, load_config, read_csv, to_float, validate_base_paths, write_blocked, write_csv


METHODS = [
    "random",
    "uniform_time",
    "top_count",
    "top_naive",
    "temporal_nms_count",
    "proxy_then_expansion_count",
    "adaptive_count_nms_expand",
    "top_learned_logreg",
    "top_learned_rf",
]


def normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def load_rows(output_dir: Path) -> list[dict]:
    proxy_path = output_dir / "proxy_scores.csv"
    label_path = output_dir / "vlm_labels_conservative.csv"
    if not proxy_path.is_file() or not label_path.is_file():
        path = write_blocked(
            output_dir,
            "BLOCKED_vlm_oracle_missing_inputs.md",
            "BLOCKED: VLM Oracle Benchmark Missing Inputs",
            ["Need proxy_scores.csv and vlm_labels_conservative.csv in the expanded output directory."],
        )
        print(f"blocked_report={path}")
        return []
    proxies = {r["clip_id"]: r for r in read_csv(proxy_path)}
    labels = {r["clip_id"]: r for r in read_csv(label_path)}
    ids = [cid for cid in proxies if cid in labels]
    count_norm = dict(zip(ids, normalize([to_float(proxies[cid].get("score_count")) for cid in ids])))
    naive_norm = dict(zip(ids, normalize([to_float(proxies[cid].get("score_naive")) for cid in ids])))
    kin_norm = dict(zip(ids, normalize([to_float(proxies[cid].get("score_kinematic")) for cid in ids])))
    rows = []
    for cid in ids:
        p, l = proxies[cid], labels[cid]
        row = dict(p)
        row["vlm_label"] = 1 if (l.get("conservative_positive") or "").strip().lower() == "yes" else 0
        row["event_type"] = l.get("event_type", "")
        row["negative_reason"] = l.get("negative_reason", "")
        row["score_count"] = to_float(p.get("score_count"))
        row["score_naive"] = to_float(p.get("score_naive"))
        row["score_kinematic"] = to_float(p.get("score_kinematic"))
        row["score_count_norm"] = count_norm[cid]
        row["score_naive_norm"] = naive_norm[cid]
        row["score_kinematic_norm"] = kin_norm[cid]
        row["ensemble_count_naive_score"] = row["score_count_norm"] + row["score_naive_norm"]
        row["ensemble_all_proxy_score"] = row["score_count_norm"] + row["score_naive_norm"] + row["score_kinematic_norm"]
        rows.append(row)
    rows.sort(key=lambda r: (r["video_id"], r["segment_id"], to_float(r["start_time"])))
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


def by_video_positions(rows: list[dict]) -> dict[str, tuple[list[dict], int]]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["video_id"]].append(row)
    out = {}
    for video_rows in grouped.values():
        video_rows.sort(key=lambda r: to_float(r["start_time"]))
        for idx, row in enumerate(video_rows):
            out[row["clip_id"]] = (video_rows, idx)
    return out


def top_order(rows: list[dict], score: str) -> list[str]:
    return [r["clip_id"] for r in sorted(rows, key=lambda r: (-float(r.get(score, 0.0)), r["video_id"], to_float(r["start_time"])))]


def uniform_order(rows: list[dict]) -> list[str]:
    if not rows:
        return []
    if len(rows) == 1:
        return [rows[0]["clip_id"]]
    return [rows[int(round(i * (len(rows) - 1) / (len(rows) - 1)))]["clip_id"] for i in range(len(rows))]


def temporal_nms_order(rows: list[dict], score: str, gap: float) -> list[str]:
    selected = []
    selected_ids = set()
    for r in sorted(rows, key=lambda x: -float(x.get(score, 0.0))):
        st = to_float(r["start_time"])
        if all(r["video_id"] != s["video_id"] or abs(st - to_float(s["start_time"])) > gap for s in selected):
            selected.append(r)
            selected_ids.add(r["clip_id"])
    for r in sorted(rows, key=lambda x: -float(x.get(score, 0.0))):
        if r["clip_id"] not in selected_ids:
            selected.append(r)
            selected_ids.add(r["clip_id"])
    return [r["clip_id"] for r in selected]


def proxy_expansion_selection(rows: list[dict], budget: int, score: str, radius: int, anchor_fraction: float) -> list[str]:
    positions = by_video_positions(rows)
    anchors = top_order(rows, score)
    selected = []
    anchor_budget = max(1, min(budget, int(math.ceil(budget * anchor_fraction))))
    for cid in anchors[:anchor_budget]:
        if cid not in selected:
            selected.append(cid)
        if len(selected) >= budget:
            return selected[:budget]
        video_rows, idx = positions[cid]
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


def adaptive_count_nms_expand(rows: list[dict], budget: int, gap: float, radius: int, anchor_fraction: float) -> list[str]:
    """Two-stage simulation: count+NMS anchors, expand locally only after a positive anchor."""
    positions = by_video_positions(rows)
    labels = {r["clip_id"]: int(r["vlm_label"]) for r in rows}
    anchor_budget = max(1, min(budget, int(math.ceil(budget * anchor_fraction))))
    anchor_queue = temporal_nms_order(rows, "score_count", gap)
    fallback = top_order(rows, "score_count")
    selected = []
    selected_set = set()
    anchors_used = 0

    def add(cid: str) -> bool:
        if cid in selected_set:
            return False
        selected.append(cid)
        selected_set.add(cid)
        return len(selected) >= budget

    for anchor in anchor_queue:
        if anchors_used >= anchor_budget or len(selected) >= budget:
            break
        if add(anchor):
            break
        anchors_used += 1
        if labels.get(anchor, 0) == 1:
            video_rows, idx = positions[anchor]
            for d in range(1, radius + 1):
                for j in [idx - d, idx + d]:
                    if 0 <= j < len(video_rows) and add(video_rows[j]["clip_id"]):
                        break
                if len(selected) >= budget:
                    break
    for cid in fallback:
        if len(selected) >= budget:
            break
        add(cid)
    return selected[:budget]


def select(rows: list[dict], method: str, budget: int, cfg: dict, seed: int = 0) -> list[str]:
    bcfg = cfg.get("budget") or {}
    gap = float(bcfg.get("temporal_nms_gap_sec", 4.0))
    radius = int(bcfg.get("expansion_radius", 2))
    anchor_fraction = float(bcfg.get("anchor_fraction", 0.25))
    adaptive_anchor_fraction = float(bcfg.get("adaptive_anchor_fraction", 0.5))
    if method == "random":
        ids = [r["clip_id"] for r in rows]
        rng = random.Random(seed)
        rng.shuffle(ids)
        return ids[:budget]
    if method == "uniform_time":
        return uniform_order(rows)[:budget]
    if method == "top_count":
        return top_order(rows, "score_count")[:budget]
    if method == "top_naive":
        return top_order(rows, "score_naive")[:budget]
    if method == "temporal_nms_count":
        return temporal_nms_order(rows, "score_count", gap)[:budget]
    if method == "proxy_then_expansion_count":
        return proxy_expansion_selection(rows, budget, "score_count", radius, anchor_fraction)
    if method == "adaptive_count_nms_expand":
        return adaptive_count_nms_expand(rows, budget, gap, radius, adaptive_anchor_fraction)
    if method == "top_learned_logreg":
        return top_order(rows, "score_learned_logreg")[:budget]
    if method == "top_learned_rf":
        return top_order(rows, "score_learned_rf")[:budget]
    raise ValueError(f"unknown method: {method}")


def evaluate(rows: list[dict], selected: list[str], events: list[dict]) -> dict:
    selected_set = set(selected)
    positives = {r["clip_id"] for r in rows if int(r["vlm_label"]) == 1}
    tp = len(selected_set & positives)
    recall = tp / len(positives) if positives else 0.0
    precision = tp / len(selected_set) if selected_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    hit = sum(1 for event in events if selected_set & set(event["clip_ids"]))
    event_recall = hit / len(events) if events else 0.0
    return {
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "positives_found": tp,
        "event_recall": event_recall,
        "num_events": len(events),
        "num_events_hit": hit,
    }


def mean_std(vals: list[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    mean = sum(vals) / len(vals)
    return mean, math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))


def add_learned_scores(rows: list[dict], output_dir: Path) -> tuple[list[dict], str]:
    feature_cols = [
        "score_count",
        "score_naive",
        "score_kinematic",
        "mean_vehicle_count",
        "max_vehicle_count",
        "max_area_growth",
        "max_center_motion",
        "max_ego_path_overlap",
        "max_predicted_entry",
        "max_lateral_toward_ego_path",
        "max_temporal_persistence",
        "track_count",
        "stable_track_count",
    ]
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import GroupKFold
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except Exception as exc:
        for row in rows:
            row["score_learned_logreg"] = row["score_count"]
            row["score_learned_rf"] = row["score_count"]
        return rows, f"sklearn unavailable, learned scores fell back to score_count: {exc}"

    x = np.array([[to_float(row.get(col)) for col in feature_cols] for row in rows], dtype=float)
    y = np.array([int(row["vlm_label"]) for row in rows], dtype=int)
    groups = np.array([row["segment_id"] for row in rows])
    unique_groups = sorted(set(groups))
    if len(set(y)) < 2 or len(unique_groups) < 2:
        for row in rows:
            row["score_learned_logreg"] = row["score_count"]
            row["score_learned_rf"] = row["score_count"]
        return rows, "not enough class or segment diversity; learned scores fell back to score_count"

    n_splits = min(5, len(unique_groups))
    logreg_scores = np.zeros(len(rows), dtype=float)
    rf_scores = np.zeros(len(rows), dtype=float)
    gkf = GroupKFold(n_splits=n_splits)
    completed = 0
    for train_idx, test_idx in gkf.split(x, y, groups):
        if len(set(y[train_idx])) < 2:
            logreg_scores[test_idx] = float(y[train_idx].mean()) if len(train_idx) else 0.0
            rf_scores[test_idx] = logreg_scores[test_idx]
            continue
        logreg = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced"))
        rf = RandomForestClassifier(n_estimators=200, min_samples_leaf=3, class_weight="balanced", random_state=17)
        logreg.fit(x[train_idx], y[train_idx])
        rf.fit(x[train_idx], y[train_idx])
        logreg_scores[test_idx] = logreg.predict_proba(x[test_idx])[:, 1]
        rf_scores[test_idx] = rf.predict_proba(x[test_idx])[:, 1]
        completed += 1
    for row, lr, rf in zip(rows, logreg_scores, rf_scores):
        row["score_learned_logreg"] = float(lr)
        row["score_learned_rf"] = float(rf)
    fields = list(rows[0].keys())
    write_csv(output_dir / "proxy_scores_with_learned.csv", rows, fields)
    return rows, f"segment-level GroupKFold learned proxy completed: folds={completed}/{n_splits}, features={len(feature_cols)}"


def run_budget(rows: list[dict], cfg: dict, events: list[dict]) -> tuple[list[dict], list[dict]]:
    ratios = [float(x) for x in (cfg.get("budget") or {}).get("budget_ratios", [0.05, 0.1, 0.2])]
    seeds = int((cfg.get("budget") or {}).get("random_seeds", 20))
    raw = []
    for ratio in ratios:
        budget = max(1, math.ceil(len(rows) * ratio))
        for method in METHODS:
            method_seeds = range(seeds) if method == "random" else [0]
            for seed in method_seeds:
                selected = select(rows, method, budget, cfg, seed)
                raw.append({"method": method, "budget_ratio": ratio, "budget": budget, "seed": seed, **evaluate(rows, selected, events)})
    grouped = defaultdict(list)
    for row in raw:
        grouped[(row["method"], row["budget_ratio"], row["budget"])].append(row)
    agg = []
    positives = sum(int(row["vlm_label"]) for row in rows)
    for (method, ratio, budget), vals in sorted(grouped.items()):
        rec_m, rec_s = mean_std([v["recall"] for v in vals])
        pre_m, pre_s = mean_std([v["precision"] for v in vals])
        f1_m, f1_s = mean_std([v["f1"] for v in vals])
        ev_m, ev_s = mean_std([v["event_recall"] for v in vals])
        agg.append(
            {
                "method": method,
                "budget_ratio": ratio,
                "budget": budget,
                "recall_mean": rec_m,
                "recall_std": rec_s,
                "precision_mean": pre_m,
                "precision_std": pre_s,
                "f1_mean": f1_m,
                "f1_std": f1_s,
                "event_recall": ev_m,
                "event_recall_std": ev_s,
                "num_events": len(events),
                "num_events_hit": sum(v["num_events_hit"] for v in vals) / len(vals),
                "total_positives": positives,
                "calls_saved_fraction": 1.0 - budget / len(rows),
            }
        )
    return raw, agg


def target_costs(rows: list[dict], cfg: dict, events: list[dict]) -> list[dict]:
    targets = [float(x) for x in (cfg.get("budget") or {}).get("target_recalls", [0.5, 0.6, 0.7, 0.8])]
    seeds = int((cfg.get("budget") or {}).get("random_seeds", 20))
    out = []
    n = len(rows)
    for method in METHODS:
        method_seeds = range(seeds) if method == "random" else [0]
        per_seed = []
        for seed in method_seeds:
            first_hit = {("clip", t): None for t in targets} | {("event", t): None for t in targets}
            for budget in range(1, n + 1):
                metrics = evaluate(rows, select(rows, method, budget, cfg, seed), events)
                for target in targets:
                    if first_hit[("clip", target)] is None and metrics["recall"] >= target:
                        first_hit[("clip", target)] = budget
                    if first_hit[("event", target)] is None and metrics["event_recall"] >= target:
                        first_hit[("event", target)] = budget
                if all(v is not None for v in first_hit.values()):
                    break
            per_seed.append(first_hit)
        for kind in ["clip", "event"]:
            for target in targets:
                calls = [d[(kind, target)] or n for d in per_seed]
                mean_calls, std_calls = mean_std([float(c) for c in calls])
                out.append(
                    {
                        "method": method,
                        "target_type": kind,
                        "target_recall": target,
                        "mean_calls": mean_calls,
                        "std_calls": std_calls,
                        "budget_ratio": mean_calls / n if n else 0.0,
                        "calls_saved": n - mean_calls,
                        "calls_saved_fraction": 1.0 - mean_calls / n if n else 0.0,
                    }
                )
    return out


def low_budget_best(agg: list[dict], metric: str) -> tuple[str, float]:
    low = [r for r in agg if float(r["budget_ratio"]) in {0.05, 0.10, 0.15, 0.20}]
    by_method = defaultdict(list)
    for row in low:
        by_method[row["method"]].append(float(row[metric]))
    ranked = sorted(((m, sum(v) / len(v)) for m, v in by_method.items()), key=lambda x: x[1], reverse=True)
    return ranked[0] if ranked else ("none", 0.0)


def write_plot(output_dir: Path, agg: list[dict]) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    for method in METHODS:
        sub = sorted([r for r in agg if r["method"] == method], key=lambda r: r["budget_ratio"])
        if sub:
            ax.plot([r["budget_ratio"] for r in sub], [r["recall_mean"] for r in sub], marker="o", label=method)
    ax.set_xlabel("VLM budget ratio")
    ax.set_ylabel("Clip recall vs full VLM scan")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "vlm_oracle_budget_curve.png", dpi=160)


def write_report(output_dir: Path, rows: list[dict], agg: list[dict], costs: list[dict], learned_note: str, cfg: dict) -> None:
    events = positive_events(rows, float((cfg.get("budget") or {}).get("event_merge_gap_sec", 4.0)))
    positives = sum(int(row["vlm_label"]) for row in rows)
    avg_run = positives / len(events) if events else 0.0
    best_clip_method, best_clip_value = low_budget_best(agg, "recall_mean")
    best_event_method, best_event_value = low_budget_best(agg, "event_recall")
    random_clip = [r for r in agg if r["method"] == "random" and float(r["budget_ratio"]) in {0.05, 0.10, 0.15, 0.20}]
    random_event = [r for r in agg if r["method"] == "random" and float(r["budget_ratio"]) in {0.05, 0.10, 0.15, 0.20}]
    random_clip_avg = sum(float(r["recall_mean"]) for r in random_clip) / len(random_clip) if random_clip else 0.0
    random_event_avg = sum(float(r["event_recall"]) for r in random_event) / len(random_event) if random_event else 0.0
    cost_focus = [c for c in costs if c["target_recall"] in {0.5, 0.6, 0.7, 0.8} and c["target_type"] in {"clip", "event"}]
    best_80_event = sorted([c for c in cost_focus if c["target_type"] == "event" and abs(c["target_recall"] - 0.8) < 1e-9], key=lambda c: c["mean_calls"])
    lines = [
        "# Final VLM-as-Oracle Acceleration Report",
        "",
        "Evaluation target: approximating the full conservative Qwen3-VL scan. These labels are VLM pseudo-oracle labels, not human ground truth.",
        "",
        "## Dataset",
        "",
        f"- clips: {len(rows)}",
        f"- conservative VLM positives: {positives} / {len(rows)} = {positives / len(rows) if rows else 0:.3f}",
        f"- positive events: {len(events)}",
        f"- average positive run length: {avg_run:.3f}",
        f"- event_merge_gap_sec: {(cfg.get('budget') or {}).get('event_merge_gap_sec', 4.0)}",
        "",
        "## Learned Proxy",
        "",
        f"- {learned_note}",
        "- Learned scores use segment-level GroupKFold out-of-fold predictions, so clips from the same segment do not appear in both train and test folds.",
        "",
        "## Low-Budget Results",
        "",
        f"- best 5%-20% clip recall method: `{best_clip_method}` = {best_clip_value:.3f}",
        f"- random 5%-20% clip recall: {random_clip_avg:.3f}",
        f"- best clip uplift over random: {(best_clip_value / random_clip_avg) if random_clip_avg else 0.0:.2f}x",
        f"- best 5%-20% event recall method: `{best_event_method}` = {best_event_value:.3f}",
        f"- random 5%-20% event recall: {random_event_avg:.3f}",
        f"- best event uplift over random: {(best_event_value / random_event_avg) if random_event_avg else 0.0:.2f}x",
        "",
        "## Budget Curve",
        "",
        "| method | budget | recall | precision | F1 | event_recall | calls_saved |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(agg, key=lambda r: (float(r["budget_ratio"]), r["method"])):
        lines.append(
            f"| {row['method']} | {row['budget_ratio']:.2f} | {row['recall_mean']:.3f} | {row['precision_mean']:.3f} | {row['f1_mean']:.3f} | {row['event_recall']:.3f} | {row['calls_saved_fraction']:.3f} |"
        )
    lines += [
        "",
        "## Target-Recall Cost Saving",
        "",
        "| method | target_type | target_recall | mean_calls | budget_ratio | calls_saved_fraction |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in sorted(cost_focus, key=lambda r: (r["target_type"], r["target_recall"], r["mean_calls"], r["method"])):
        lines.append(
            f"| {row['method']} | {row['target_type']} | {row['target_recall']:.2f} | {row['mean_calls']:.1f} | {row['budget_ratio']:.3f} | {row['calls_saved_fraction']:.3f} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- `top_count` tests pure proxy ranking.",
        "- `temporal_nms_count` tests proxy ranking with time diversity.",
        "- `proxy_then_expansion_count` tests dense local recovery around proxy anchors.",
        "- `adaptive_count_nms_expand` first calls count+NMS anchors, then spends local expansion calls only after an anchor is VLM-positive.",
        "- Learned proxy results are feasibility checks using existing proxy/track features, not a separate anomaly model.",
    ]
    if best_80_event:
        b = best_80_event[0]
        lines.append(f"- cheapest 0.80 event recall method: `{b['method']}` with {b['mean_calls']:.1f}/{len(rows)} calls, saving {b['calls_saved_fraction']:.3f}.")
    lines += [
        "",
        "## Decision",
        "",
        "- This benchmark supports or rejects acceleration only relative to the full conservative VLM scan.",
        "- It does not prove true traffic-risk accuracy without human GT.",
        "- If a method substantially beats random in target-recall cost, it is a candidate budget allocation strategy for larger VLM-as-oracle experiments.",
    ]
    (output_dir / "final_vlm_oracle_acceleration_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    rows = load_rows(output_dir)
    if not rows:
        return
    rows, learned_note = add_learned_scores(rows, output_dir)
    events = positive_events(rows, float((cfg.get("budget") or {}).get("event_merge_gap_sec", 4.0)))
    raw, agg = run_budget(rows, cfg, events)
    costs = target_costs(rows, cfg, events)
    write_csv(output_dir / "vlm_oracle_budget_curve_raw.csv", raw, ["method", "budget_ratio", "budget", "seed", "recall", "precision", "f1", "positives_found", "event_recall", "num_events", "num_events_hit"])
    write_csv(output_dir / "vlm_oracle_budget_curve.csv", agg, ["method", "budget_ratio", "budget", "recall_mean", "recall_std", "precision_mean", "precision_std", "f1_mean", "f1_std", "event_recall", "event_recall_std", "num_events", "num_events_hit", "total_positives", "calls_saved_fraction"])
    write_csv(output_dir / "target_recall_cost_saving.csv", costs, ["method", "target_type", "target_recall", "mean_calls", "std_calls", "budget_ratio", "calls_saved", "calls_saved_fraction"])
    write_plot(output_dir, agg)
    write_report(output_dir, rows, agg, costs, learned_note, cfg)
    print(f"budget_curve={output_dir / 'vlm_oracle_budget_curve.csv'}")
    print(f"target_cost={output_dir / 'target_recall_cost_saving.csv'}")
    print(f"final_report={output_dir / 'final_vlm_oracle_acceleration_report.md'}")


if __name__ == "__main__":
    main()
