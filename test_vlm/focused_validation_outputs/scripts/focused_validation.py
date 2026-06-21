#!/usr/bin/env python3
"""Focused validation for the roadclip_budget_v2 VLM-as-oracle benchmark.

This script intentionally writes only under focused_validation_outputs/.
It does not modify existing benchmark inputs or previously generated outputs.
"""

from __future__ import annotations

import argparse
import math
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


METHODS = [
    "random",
    "top_count",
    "temporal_nms_count",
    "adaptive_count_nms_expand",
    "proxy_then_expansion_count",
    "top_learned_logreg",
    "top_learned_rf",
]
BUDGETS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
GAPS = [0, 3, 6, 10]
IOU_THRESHOLDS = [0.1, 0.3, 0.5]
REQUIRED_LABEL_COLS = {
    "clip_id",
    "segment_id",
    "start_time",
    "end_time",
    "conservative_positive",
}
REQUIRED_PROXY_COLS = {"clip_id", "score_count", "score_naive", "score_kinematic"}


def mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def as_positive(value) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "positive"}


def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def format_float(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def df_to_md(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty_"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if isinstance(val, float):
                vals.append(f"{val:.3f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def discover_inputs(search_roots: list[Path], explicit_output_dir: Path | None) -> dict:
    candidates = []
    csv_paths = []
    for root in search_roots:
        if root.exists():
            csv_paths.extend(root.rglob("*.csv"))
    for path in sorted(csv_paths):
        try:
            df = pd.read_csv(path, nrows=5)
        except Exception as exc:
            candidates.append({"path": str(path), "readable": False, "error": repr(exc), "columns": []})
            continue
        cols = set(df.columns)
        candidates.append(
            {
                "path": str(path),
                "readable": True,
                "rows_sampled": len(df),
                "columns": list(df.columns),
                "has_labels": REQUIRED_LABEL_COLS <= cols,
                "has_proxy": REQUIRED_PROXY_COLS <= cols,
                "has_budget_curve": {"method", "budget_ratio"} <= cols and ({"recall_mean", "event_recall"} & cols),
            }
        )

    preferred = explicit_output_dir
    if preferred is None:
        likely_dirs = []
        for row in candidates:
            if not row.get("readable"):
                continue
            path = Path(row["path"])
            if path.name == "vlm_labels_conservative.csv":
                try:
                    df = pd.read_csv(path)
                    if len(df) >= 1000 and REQUIRED_LABEL_COLS <= set(df.columns):
                        likely_dirs.append(path.parent)
                except Exception:
                    pass
        preferred = sorted(likely_dirs, key=lambda p: ("vlm_oracle_expanded" not in str(p), str(p)))[0] if likely_dirs else None
    if preferred is None:
        raise SystemExit("Could not auto-detect a 1000-clip VLM label directory; pass --input_dir.")

    files = {
        "input_dir": preferred,
        "labels": preferred / "vlm_labels_conservative.csv",
        "proxy": preferred / "proxy_scores.csv",
        "proxy_learned": preferred / "proxy_scores_with_learned.csv",
        "budget_curve": preferred / "vlm_oracle_budget_curve.csv",
        "target_recall": preferred / "target_recall_cost_saving.csv",
        "final_report": preferred / "final_vlm_oracle_acceleration_report.md",
    }
    return {"candidates": candidates, "files": files}


def write_inventory(out_dir: Path, discovery: dict, dfs: dict) -> None:
    files = discovery["files"]
    lines = ["# Input Inventory", ""]
    lines += ["## Selected Inputs", ""]
    for key, path in files.items():
        if key == "input_dir":
            lines.append(f"- {key}: `{path}`")
        else:
            lines.append(f"- {key}: `{path}` exists={path.exists()}")
    lines += ["", "## Detected Fields", ""]
    for name, df in dfs.items():
        lines.append(f"### {name}")
        lines.append(f"- rows: {len(df)}")
        lines.append(f"- columns: `{list(df.columns)}`")
        missing = []
        if name == "labels":
            missing = sorted(REQUIRED_LABEL_COLS - set(df.columns))
        if name in {"proxy", "proxy_learned"}:
            missing = sorted(REQUIRED_PROXY_COLS - set(df.columns))
        lines.append(f"- missing required fields: `{missing}`")
        lines.append("")
    lines += ["## Candidate Files", ""]
    for row in discovery["candidates"]:
        if row.get("readable") and (row.get("has_labels") or row.get("has_proxy") or row.get("has_budget_curve")):
            lines.append(f"- `{row['path']}`")
            lines.append(f"  - columns: `{row['columns']}`")
            lines.append(f"  - has_labels={row.get('has_labels')} has_proxy={row.get('has_proxy')} has_budget_curve={row.get('has_budget_curve')}")
    (out_dir / "00_input_inventory.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_dir / "00_input_inventory.md")


def load_joined(files: dict) -> tuple[pd.DataFrame, dict]:
    labels = read_csv(files["labels"])
    proxy_path = files["proxy_learned"] if files["proxy_learned"].exists() else files["proxy"]
    proxy = read_csv(proxy_path)
    missing_label = sorted(REQUIRED_LABEL_COLS - set(labels.columns))
    missing_proxy = sorted(REQUIRED_PROXY_COLS - set(proxy.columns))
    if missing_label:
        raise SystemExit(f"Label file missing required fields: {missing_label}")
    if missing_proxy:
        raise SystemExit(f"Proxy file missing required fields: {missing_proxy}")
    label_cols = [
        "clip_id",
        "segment_id",
        "start_time",
        "end_time",
        "clip_path",
        "conservative_positive",
        "risk_level",
        "affected_ego",
        "event_type",
        "negative_reason",
        "confidence",
        "evidence",
    ]
    label_cols = [c for c in label_cols if c in labels.columns]
    proxy_cols = [
        "clip_id",
        "video_id",
        "segment_id",
        "start_time",
        "end_time",
        "clip_path",
        "score_count",
        "score_naive",
        "score_kinematic",
        "score_learned_logreg",
        "score_learned_rf",
        "mean_vehicle_count",
        "max_vehicle_count",
        "track_count",
        "stable_track_count",
    ]
    proxy_cols = [c for c in proxy_cols if c in proxy.columns]
    rows = proxy[proxy_cols].merge(labels[label_cols], on="clip_id", how="inner", suffixes=("", "_label"))
    for col in ["segment_id", "start_time", "end_time", "clip_path"]:
        alt = f"{col}_label"
        if col not in rows.columns and alt in rows.columns:
            rows[col] = rows[alt]
        elif alt in rows.columns:
            rows[col] = rows[col].combine_first(rows[alt])
    if "video_id" not in rows.columns:
        rows["video_id"] = rows["segment_id"].astype(str).str.rsplit("_seg", n=1).str[0]
    for col in ["score_learned_logreg", "score_learned_rf"]:
        if col not in rows.columns:
            rows[col] = rows["score_count"]
    for col in ["risk_level", "affected_ego", "event_type", "negative_reason", "confidence", "evidence"]:
        if col not in rows.columns:
            rows[col] = ""
    rows["oracle_positive"] = rows["conservative_positive"].map(as_positive)
    rows["vlm_label"] = rows["oracle_positive"].astype(int)
    rows["start_time"] = rows["start_time"].map(safe_float)
    rows["end_time"] = rows["end_time"].map(safe_float)
    rows = rows.sort_values(["segment_id", "start_time", "end_time", "clip_id"]).reset_index(drop=True)
    return rows, {"labels": labels, "proxy": proxy}


def write_pseudo_oracle_definition(out_dir: Path, rows: pd.DataFrame) -> None:
    seg = rows.groupby("segment_id").agg(
        clips=("clip_id", "count"),
        positive_clips=("oracle_positive", "sum"),
    )
    seg["positive_rate"] = seg["positive_clips"] / seg["clips"]
    total = len(rows)
    pos = int(rows["oracle_positive"].sum())
    neg = total - pos
    lines = [
        "# Pseudo-oracle Definition",
        "",
        "The `full conservative VLM scan` is fixed as the pseudo-oracle target for this focused validation.",
        "",
        "- A clip is an oracle-positive fixed window iff `conservative_positive == yes/true/1`.",
        "- This definition is only for semantic clip query processing and budget allocation evaluation.",
        "- It is not human ground truth and must not be reported as true traffic-risk recall.",
        "- All recall and precision values in this validation are relative to the VLM pseudo-oracle.",
        "",
        "Metric names used in this validation:",
        "",
        "- `oracle_clip_recall`",
        "- `oracle_event_recall`",
        "- `oracle_event_precision`",
        "- `vlm_call_saving`",
        "- `budgeted_event_iou`",
        "",
        "## Statistics",
        "",
        f"- total clips: {total}",
        f"- positive clips: {pos}",
        f"- negative clips: {neg}",
        f"- positive rate: {pos / total:.3f}",
        f"- segment count: {rows['segment_id'].nunique()}",
        "",
        "## Positive Clips By Segment",
        "",
        "| segment_id | clips | positive_clips | positive_rate |",
        "|---|---:|---:|---:|",
    ]
    for sid, row in seg.sort_values("positive_clips", ascending=False).iterrows():
        lines.append(f"| {sid} | {int(row['clips'])} | {int(row['positive_clips'])} | {row['positive_rate']:.3f} |")
    (out_dir / "01_pseudo_oracle_definition.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_dir / "01_pseudo_oracle_definition.md")


def order_by_score(df: pd.DataFrame, score: str) -> list[str]:
    if score not in df.columns:
        return []
    return (
        df.assign(_score=df[score].map(safe_float))
        .sort_values(["_score", "segment_id", "start_time"], ascending=[False, True, True])["clip_id"]
        .tolist()
    )


def temporal_nms_order(df: pd.DataFrame, score: str, gap: float = 4.0) -> list[str]:
    selected = []
    selected_ids = set()
    for _, row in df.assign(_score=df[score].map(safe_float)).sort_values("_score", ascending=False).iterrows():
        st = row["start_time"]
        sid = row["segment_id"]
        if all(sid != s["segment_id"] or abs(st - s["start_time"]) > gap for s in selected):
            selected.append(row)
            selected_ids.add(row["clip_id"])
    for _, row in df.assign(_score=df[score].map(safe_float)).sort_values("_score", ascending=False).iterrows():
        if row["clip_id"] not in selected_ids:
            selected.append(row)
    return [r["clip_id"] for r in selected]


def proxy_expansion_selection(df: pd.DataFrame, budget: int, score: str, radius: int = 2, anchor_fraction: float = 0.25) -> list[str]:
    ordered = order_by_score(df, score)
    by_segment = {sid: g.sort_values("start_time").reset_index(drop=True) for sid, g in df.groupby("segment_id")}
    pos = {}
    for sid, g in by_segment.items():
        for idx, row in g.iterrows():
            pos[row["clip_id"]] = (sid, idx)
    selected = []
    selected_set = set()
    anchor_budget = max(1, min(budget, int(math.ceil(budget * anchor_fraction))))
    for cid in ordered[:anchor_budget]:
        if cid not in selected_set:
            selected.append(cid)
            selected_set.add(cid)
        if len(selected) >= budget:
            return selected[:budget]
        if cid not in pos:
            continue
        sid, idx = pos[cid]
        g = by_segment[sid]
        for d in range(1, radius + 1):
            for j in [idx - d, idx + d]:
                if 0 <= j < len(g):
                    nid = g.loc[j, "clip_id"]
                    if nid not in selected_set:
                        selected.append(nid)
                        selected_set.add(nid)
                        if len(selected) >= budget:
                            return selected[:budget]
    for cid in ordered:
        if cid not in selected_set:
            selected.append(cid)
            selected_set.add(cid)
            if len(selected) >= budget:
                break
    return selected[:budget]


def adaptive_count_nms_expand(df: pd.DataFrame, budget: int, gap: float = 4.0, radius: int = 2, anchor_fraction: float = 0.5) -> list[str]:
    anchor_queue = temporal_nms_order(df, "score_count", gap)
    fallback = order_by_score(df, "score_count")
    by_segment = {sid: g.sort_values("start_time").reset_index(drop=True) for sid, g in df.groupby("segment_id")}
    pos = {}
    labels = dict(zip(df["clip_id"], df["oracle_positive"]))
    for sid, g in by_segment.items():
        for idx, row in g.iterrows():
            pos[row["clip_id"]] = (sid, idx)
    selected = []
    selected_set = set()
    anchor_budget = max(1, min(budget, int(math.ceil(budget * anchor_fraction))))
    anchors_used = 0

    def add(cid: str) -> bool:
        if cid not in selected_set:
            selected.append(cid)
            selected_set.add(cid)
        return len(selected) >= budget

    for anchor in anchor_queue:
        if anchors_used >= anchor_budget or len(selected) >= budget:
            break
        if add(anchor):
            break
        anchors_used += 1
        if labels.get(anchor, False) and anchor in pos:
            sid, idx = pos[anchor]
            g = by_segment[sid]
            for d in range(1, radius + 1):
                for j in [idx - d, idx + d]:
                    if 0 <= j < len(g) and add(g.loc[j, "clip_id"]):
                        break
                if len(selected) >= budget:
                    break
    for cid in fallback:
        if len(selected) >= budget:
            break
        add(cid)
    return selected[:budget]


def select_policy(df: pd.DataFrame, policy: str, budget: int, seed: int = 0) -> list[str]:
    if policy == "random":
        ids = df["clip_id"].tolist()
        rng = random.Random(seed)
        rng.shuffle(ids)
        return ids[:budget]
    if policy == "top_count":
        return order_by_score(df, "score_count")[:budget]
    if policy == "temporal_nms_count":
        return temporal_nms_order(df, "score_count")[:budget]
    if policy == "adaptive_count_nms_expand":
        return adaptive_count_nms_expand(df, budget)[:budget]
    if policy == "proxy_then_expansion_count":
        return proxy_expansion_selection(df, budget, "score_count")[:budget]
    if policy == "top_learned_logreg":
        return order_by_score(df, "score_learned_logreg")[:budget]
    if policy == "top_learned_rf":
        return order_by_score(df, "score_learned_rf")[:budget]
    raise ValueError(policy)


def build_events(pos_df: pd.DataFrame, gap: float) -> pd.DataFrame:
    events = []
    eid = 0
    for sid, g in pos_df.sort_values(["segment_id", "start_time"]).groupby("segment_id"):
        current = None
        for _, row in g.iterrows():
            st, en = row["start_time"], row["end_time"]
            if current is None or st - current["event_end"] > gap:
                if current is not None:
                    events.append(current)
                current = {
                    "event_id": f"event_{eid:04d}",
                    "segment_id": sid,
                    "event_start": st,
                    "event_end": en,
                    "num_positive_windows": 1,
                    "positive_clip_ids": [row["clip_id"]],
                }
                eid += 1
            else:
                current["event_end"] = max(current["event_end"], en)
                current["num_positive_windows"] += 1
                current["positive_clip_ids"].append(row["clip_id"])
        if current is not None:
            events.append(current)
    for ev in events:
        ev["duration"] = ev["event_end"] - ev["event_start"]
        ev["positive_clip_ids"] = ";".join(ev["positive_clip_ids"])
    return pd.DataFrame(events, columns=["event_id", "segment_id", "event_start", "event_end", "duration", "num_positive_windows", "positive_clip_ids"])


def interval_iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / union if union > 0 else 0.0


def evaluate_events(oracle: pd.DataFrame, returned: pd.DataFrame, theta: float) -> dict:
    if oracle.empty:
        return {}
    pairs = []
    for oi, o in oracle.iterrows():
        for ri, r in returned[returned["segment_id"].eq(o["segment_id"])].iterrows():
            iou = interval_iou(o["event_start"], o["event_end"], r["event_start"], r["event_end"])
            if iou > 0:
                pairs.append((iou, oi, ri))
    pairs.sort(reverse=True)
    matched_o, matched_r, ious, start_err, end_err = set(), set(), [], [], []
    for iou, oi, ri in pairs:
        if iou < theta or oi in matched_o or ri in matched_r:
            continue
        matched_o.add(oi)
        matched_r.add(ri)
        o = oracle.loc[oi]
        r = returned.loc[ri]
        ious.append(iou)
        start_err.append(abs(r["event_start"] - o["event_start"]))
        end_err.append(abs(r["event_end"] - o["event_end"]))
    overmerge = 0
    for _, r in returned.iterrows():
        overlaps = 0
        for _, o in oracle[oracle["segment_id"].eq(r["segment_id"])].iterrows():
            if interval_iou(o["event_start"], o["event_end"], r["event_start"], r["event_end"]) >= theta:
                overlaps += 1
        if overlaps > 1:
            overmerge += 1
    matched = len(matched_o)
    return {
        "num_oracle_events": len(oracle),
        "num_returned_events": len(returned),
        "matched_oracle_events": matched,
        "oracle_event_recall": matched / len(oracle) if len(oracle) else 0.0,
        "oracle_event_precision": len(matched_r) / len(returned) if len(returned) else 0.0,
        "mean_event_iou": float(np.mean(ious)) if ious else 0.0,
        "median_event_iou": float(np.median(ious)) if ious else 0.0,
        "mean_start_error": float(np.mean(start_err)) if start_err else np.nan,
        "mean_end_error": float(np.mean(end_err)) if end_err else np.nan,
        "fragmentation_rate": len(returned) / matched if matched else np.nan,
        "overmerge_count": overmerge,
    }


def event_conversion(out_dir: Path, rows: pd.DataFrame) -> pd.DataFrame:
    ev_dir = mkdir(out_dir / "03_event_conversion")
    selected_cache = {}
    metrics = []
    for gap in GAPS:
        oracle = build_events(rows[rows["oracle_positive"]], gap)
        oracle.to_csv(ev_dir / f"oracle_events_gap{gap}.csv", index=False)
        for policy in METHODS:
            for budget_fraction in BUDGETS:
                budget = max(1, math.ceil(len(rows) * budget_fraction))
                selected = select_policy(rows, policy, budget, seed=0)
                selected_cache[(policy, budget_fraction)] = selected
                returned_pos = rows[rows["clip_id"].isin(selected) & rows["oracle_positive"]]
                returned = build_events(returned_pos, gap)
                returned.to_csv(ev_dir / f"returned_events_{policy}_budget{int(budget_fraction*100)}_gap{gap}.csv", index=False)
                for theta in IOU_THRESHOLDS:
                    row = evaluate_events(oracle, returned, theta)
                    row.update(
                        {
                            "policy": policy,
                            "budget": budget,
                            "budget_fraction": budget_fraction,
                            "gap_threshold_seconds": gap,
                            "iou_threshold": theta,
                            "vlm_calls": len(selected),
                            "vlm_call_saving": 1.0 - len(selected) / len(rows),
                        }
                    )
                    metrics.append(row)
    metrics_df = pd.DataFrame(metrics)
    metrics_df.to_csv(ev_dir / "event_level_metrics.csv", index=False)
    print(ev_dir / "event_level_metrics.csv")
    return metrics_df


def make_audit_package(out_dir: Path, rows: pd.DataFrame) -> pd.DataFrame:
    audit_dir = mkdir(out_dir / "02_audit_package")
    selected: dict[str, set[str]] = defaultdict(set)
    positives = rows[rows["oracle_positive"]].copy()
    negatives = rows[~rows["oracle_positive"]].copy()

    for _, r in positives.sort_values(["segment_id", "event_type", "score_count"], ascending=[True, True, False]).groupby("segment_id").head(2).iterrows():
        selected[r["clip_id"]].add("vlm_positive_diverse_segment")
    for event_type, g in positives.groupby("event_type"):
        for _, r in g.sort_values("score_count", ascending=False).head(2).iterrows():
            selected[r["clip_id"]].add(f"vlm_positive_event_type_{event_type}")
    for score in ["score_count", "score_naive", "score_kinematic"]:
        for _, r in positives.sort_values(score, ascending=False).head(3).iterrows():
            selected[r["clip_id"]].add(f"vlm_positive_high_{score}")
        for _, r in positives.sort_values(score, ascending=True).head(2).iterrows():
            selected[r["clip_id"]].add(f"vlm_positive_low_{score}")
    for _, r in positives[positives["risk_level"].astype(str).str.upper().eq("L3")].head(5).iterrows():
        selected[r["clip_id"]].add("vlm_positive_l3")

    # Hard negatives.
    for score in ["score_count", "score_naive", "score_kinematic"]:
        for _, r in negatives.sort_values(score, ascending=False).head(5).iterrows():
            selected[r["clip_id"]].add(f"hard_negative_high_{score}")
    for reason in ["dense_traffic_only", "normal_following", "adjacent_no_intrusion"]:
        g = negatives[negatives["negative_reason"].astype(str).eq(reason)]
        for _, r in g.sort_values("score_count", ascending=False).head(4).iterrows():
            selected[r["clip_id"]].add(f"hard_negative_{reason}")

    pos_by_seg = {sid: g.sort_values("start_time") for sid, g in positives.groupby("segment_id")}
    for sid, pos_g in pos_by_seg.items():
        neg_g = negatives[negatives["segment_id"].eq(sid)]
        for _, p in pos_g.head(6).iterrows():
            if neg_g.empty:
                continue
            idx = (neg_g["start_time"] - p["start_time"]).abs().sort_values().index[:1]
            for _, r in neg_g.loc[idx].iterrows():
                selected[r["clip_id"]].add("boundary_negative_near_positive")

    rng = random.Random(17)
    random_negs = negatives.sample(n=min(10, len(negatives)), random_state=17)
    for _, r in random_negs.iterrows():
        selected[r["clip_id"]].add("random_negative")

    # Trim to around 40 while preserving groups.
    pos_ids = [cid for cid in selected if rows.set_index("clip_id").loc[cid, "oracle_positive"]]
    neg_ids = [cid for cid in selected if not rows.set_index("clip_id").loc[cid, "oracle_positive"]]
    pos_ids = pos_ids[:18]
    neg_ids = neg_ids[:22]
    chosen_ids = pos_ids + neg_ids
    rng.shuffle(chosen_ids)
    selected_methods = {}
    for policy in METHODS:
        for budget_fraction in [0.10, 0.20]:
            for cid in select_policy(rows, policy, max(1, math.ceil(len(rows) * budget_fraction)), seed=0):
                selected_methods.setdefault(cid, set()).add(f"{policy}@{int(budget_fraction*100)}")

    manifest_rows = []
    for order, cid in enumerate(chosen_ids, 1):
        r = rows[rows["clip_id"].eq(cid)].iloc[0].to_dict()
        src = Path(str(r.get("clip_path", "")))
        local_name = src.name if src.name else f"{cid}.mp4"
        if src.exists():
            clips_dir = mkdir(audit_dir / "clips")
            dst = clips_dir / local_name
            if not dst.exists():
                shutil.copy2(src, dst)
        else:
            local_name = ""
        manifest_rows.append(
            {
                "review_order": order,
                "audit_group": ";".join(sorted(selected[cid])),
                "clip_id": cid,
                "segment_id": r.get("segment_id", ""),
                "start_time": r.get("start_time", ""),
                "end_time": r.get("end_time", ""),
                "clip_path": r.get("clip_path", ""),
                "local_clip_filename": f"clips/{local_name}" if local_name else "",
                "conservative_positive": r.get("conservative_positive", ""),
                "risk_level": r.get("risk_level", ""),
                "affected_ego": r.get("affected_ego", ""),
                "event_type": r.get("event_type", ""),
                "negative_reason": r.get("negative_reason", ""),
                "confidence": r.get("confidence", ""),
                "evidence": r.get("evidence", ""),
                "score_count": r.get("score_count", ""),
                "score_naive": r.get("score_naive", ""),
                "score_kinematic": r.get("score_kinematic", ""),
                "selected_by_methods": ";".join(sorted(selected_methods.get(cid, set()))),
                "human_label": "",
                "human_event_type": "",
                "human_reason": "",
                "human_confidence": "",
                "error_type": "",
            }
        )
    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(audit_dir / "priority_audit_clips.csv", index=False)
    readme = """# Priority Audit Clips

This is a sanity-check package for the VLM pseudo-oracle. It is not intended to create full human GT.

Fill:

human_label:
  yes
  possible
  no
  invalid

human_event_type:
  true_ego_conflict
  possible_ego_conflict
  dense_traffic_only
  normal_following
  roadside_static
  ambiguous
  invalid_or_osd

error_type:
  vlm_false_positive
  vlm_false_negative
  proxy_false_positive
  proxy_false_negative
  boundary_error
  ambiguous_definition
"""
    (audit_dir / "README.md").write_text(readme, encoding="utf-8")
    print(audit_dir / "priority_audit_clips.csv")
    return manifest


def plot_outputs(conc_dir: Path, rows: pd.DataFrame, seg_dist: pd.DataFrame, oracle_events: pd.DataFrame) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        (conc_dir / "PLOTS_SKIPPED.md").write_text(f"matplotlib unavailable: {exc}\n", encoding="utf-8")
        return
    timeline = rows.copy()
    timeline["y"] = pd.factorize(timeline["segment_id"])[0]
    plt.figure(figsize=(12, 4))
    plt.scatter(timeline["start_time"], timeline["y"], c=timeline["oracle_positive"].map({True: "red", False: "lightgray"}), s=8)
    plt.xlabel("start_time")
    plt.ylabel("segment")
    plt.tight_layout()
    plt.savefig(conc_dir / "positive_timeline.png", dpi=160)
    plt.close()

    positive_col = "positive_clips" if "positive_clips" in seg_dist.columns else "positive_count"
    seg_plot = seg_dist.sort_values(positive_col, ascending=False).head(30)
    plt.figure(figsize=(12, 5))
    plt.bar(seg_plot["segment_id"], seg_plot[positive_col])
    plt.xticks(rotation=80, ha="right")
    plt.ylabel("positive clips")
    plt.tight_layout()
    plt.savefig(conc_dir / "segment_positive_bar.png", dpi=160)
    plt.close()

    if not oracle_events.empty:
        plt.figure(figsize=(8, 4))
        plt.hist(oracle_events["duration"], bins=20)
        plt.xlabel("event duration sec")
        plt.ylabel("events")
        plt.tight_layout()
        plt.savefig(conc_dir / "event_length_hist.png", dpi=160)
        plt.close()

    plt.figure(figsize=(12, 4))
    colors = {"top_count": "blue", "top_learned_logreg": "green", "top_learned_rf": "purple"}
    for policy, color in colors.items():
        ids = set(select_policy(rows, policy, max(1, math.ceil(len(rows) * 0.20))))
        s = rows[rows["clip_id"].isin(ids)]
        plt.scatter(s["start_time"], pd.factorize(s["segment_id"])[0], s=8, alpha=0.6, label=policy, c=color)
    plt.legend()
    plt.xlabel("start_time")
    plt.ylabel("selected segment index")
    plt.tight_layout()
    plt.savefig(conc_dir / "selected_timeline_by_method.png", dpi=160)
    plt.close()


def temporal_concentration(out_dir: Path, rows: pd.DataFrame) -> dict:
    conc_dir = mkdir(out_dir / "04_temporal_concentration")
    seg = rows.groupby("segment_id").agg(
        clip_count=("clip_id", "count"),
        positive_count=("oracle_positive", "sum"),
        start_time_min=("start_time", "min"),
        end_time_max=("end_time", "max"),
    ).reset_index()
    seg["positive_rate"] = seg["positive_count"] / seg["clip_count"]
    seg.to_csv(conc_dir / "segment_positive_distribution.csv", index=False)

    selected_rows = []
    for policy in METHODS:
        if policy == "random":
            continue
        ids = set(select_policy(rows, policy, max(1, math.ceil(len(rows) * 0.20))))
        s = rows[rows["clip_id"].isin(ids)]
        by_seg = s.groupby("segment_id").agg(selected_clips=("clip_id", "count"), selected_positives=("oracle_positive", "sum")).reset_index()
        by_seg["policy"] = policy
        selected_rows.append(by_seg)
    selected_dist = pd.concat(selected_rows, ignore_index=True) if selected_rows else pd.DataFrame()
    selected_dist.to_csv(conc_dir / "method_selected_segment_distribution.csv", index=False)

    timeline = rows[["clip_id", "segment_id", "start_time", "end_time", "oracle_positive", "event_type", "score_count", "score_learned_logreg", "score_learned_rf"]].copy()
    timeline.to_csv(conc_dir / "positive_timeline.csv", index=False)

    oracle_events = build_events(rows[rows["oracle_positive"]], 3)
    run_lengths = rows[rows["oracle_positive"]].groupby("segment_id").size().tolist()
    total_pos = int(rows["oracle_positive"].sum())
    pos_by_seg = seg.sort_values("positive_count", ascending=False)
    top1_share = float(pos_by_seg["positive_count"].iloc[0] / total_pos) if total_pos else 0.0
    top3_share = float(pos_by_seg["positive_count"].head(3).sum() / total_pos) if total_pos else 0.0
    events_by_seg = oracle_events.groupby("segment_id").size().sort_values(ascending=False) if not oracle_events.empty else pd.Series(dtype=int)
    top1_event_share = float(events_by_seg.iloc[0] / len(oracle_events)) if len(events_by_seg) else 0.0
    summary = {
        "total_positive_clips": total_pos,
        "segments_with_positive": int((seg["positive_count"] > 0).sum()),
        "top1_segment_positive_share": top1_share,
        "top3_segment_positive_share": top3_share,
        "oracle_events_gap3": len(oracle_events),
        "top1_segment_event_share": top1_event_share,
        "mean_event_duration": float(oracle_events["duration"].mean()) if not oracle_events.empty else 0.0,
        "median_event_duration": float(oracle_events["duration"].median()) if not oracle_events.empty else 0.0,
        "mean_positive_windows_per_event": float(oracle_events["num_positive_windows"].mean()) if not oracle_events.empty else 0.0,
    }
    pd.DataFrame([summary]).to_csv(conc_dir / "event_concentration_summary.csv", index=False)
    oracle_events.to_csv(conc_dir / "oracle_events_gap3_for_concentration.csv", index=False)
    plot_outputs(conc_dir, rows, seg, oracle_events)
    print(conc_dir / "event_concentration_summary.csv")
    return summary


def clip_recall(rows: pd.DataFrame, selected: set[str]) -> float:
    pos = set(rows[rows["oracle_positive"]]["clip_id"])
    return len(pos & selected) / len(pos) if pos else 0.0


def event_metric_for_selection(rows: pd.DataFrame, selected: set[str], gap: float = 3, theta: float = 0.3) -> dict:
    oracle = build_events(rows[rows["oracle_positive"]], gap)
    returned = build_events(rows[rows["clip_id"].isin(selected) & rows["oracle_positive"]], gap)
    return evaluate_events(oracle, returned, theta)


def bootstrap_ci(vals: list[float], seed: int = 0) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    arr = np.array(vals)
    means = [float(rng.choice(arr, size=len(arr), replace=True).mean()) for _ in range(1000)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def smoke_trials(out_dir: Path, rows: pd.DataFrame) -> dict:
    smoke_dir = mkdir(out_dir / "05_smoke_trials")
    random_rows = []
    for budget_fraction in BUDGETS:
        budget = max(1, math.ceil(len(rows) * budget_fraction))
        for seed in range(20):
            selected = set(select_policy(rows, "random", budget, seed=seed))
            ev = event_metric_for_selection(rows, selected)
            random_rows.append(
                {
                    "seed": seed,
                    "budget_fraction": budget_fraction,
                    "vlm_calls": budget,
                    "oracle_clip_recall": clip_recall(rows, selected),
                    "oracle_event_recall": ev["oracle_event_recall"],
                    "oracle_event_precision": ev["oracle_event_precision"],
                    "budgeted_event_iou": ev["mean_event_iou"],
                }
            )
    random_df = pd.DataFrame(random_rows)
    random_df.to_csv(smoke_dir / "random_20seed_metrics.csv", index=False)
    summary_rows = []
    for budget_fraction, g in random_df.groupby("budget_fraction"):
        for metric in ["oracle_clip_recall", "oracle_event_recall", "oracle_event_precision", "budgeted_event_iou"]:
            vals = g[metric].tolist()
            lo, hi = bootstrap_ci(vals)
            summary_rows.append({"budget_fraction": budget_fraction, "metric": metric, "mean": np.mean(vals), "std": np.std(vals), "ci95_low": lo, "ci95_high": hi})
    random_summary = pd.DataFrame(summary_rows)
    random_summary.to_csv(smoke_dir / "random_20seed_summary.csv", index=False)

    block_rows = []
    seg_ids = sorted(rows["segment_id"].unique())
    rng = random.Random(23)
    for trial in range(20):
        sampled = [rng.choice(seg_ids) for _ in seg_ids]
        trial_rows = rows[rows["segment_id"].isin(sampled)].copy()
        if trial_rows.empty:
            continue
        for policy in [m for m in METHODS if m != "random"]:
            for budget_fraction in [0.10, 0.20]:
                budget = max(1, math.ceil(len(trial_rows) * budget_fraction))
                selected = set(select_policy(trial_rows, policy, budget, seed=trial))
                ev = event_metric_for_selection(trial_rows, selected)
                block_rows.append(
                    {
                        "trial": trial,
                        "policy": policy,
                        "budget_fraction": budget_fraction,
                        "vlm_calls": budget,
                        "oracle_clip_recall": clip_recall(trial_rows, selected),
                        "oracle_event_recall": ev["oracle_event_recall"],
                        "oracle_event_precision": ev["oracle_event_precision"],
                        "budgeted_event_iou": ev["mean_event_iou"],
                    }
                )
    block_df = pd.DataFrame(block_rows)
    block_df.to_csv(smoke_dir / "block_bootstrap_metrics.csv", index=False)
    rank_rows = []
    if not block_df.empty:
        for (trial, budget_fraction), g in block_df.groupby(["trial", "budget_fraction"]):
            ranked = g.sort_values(["oracle_event_recall", "oracle_clip_recall"], ascending=False).reset_index(drop=True)
            for rank, row in ranked.iterrows():
                rank_rows.append({"trial": trial, "budget_fraction": budget_fraction, "policy": row["policy"], "rank": rank + 1})
    rank_df = pd.DataFrame(rank_rows)
    rank_df.to_csv(smoke_dir / "policy_rank_stability.csv", index=False)

    budget_rows = []
    for policy in METHODS:
        for budget_fraction in BUDGETS:
            budget = max(1, math.ceil(len(rows) * budget_fraction))
            seeds = range(20) if policy == "random" else [0]
            vals = []
            for seed in seeds:
                selected = set(select_policy(rows, policy, budget, seed=seed))
                ev = event_metric_for_selection(rows, selected)
                vals.append(
                    {
                        "policy": policy,
                        "budget_fraction": budget_fraction,
                        "vlm_calls": budget,
                        "oracle_clip_recall": clip_recall(rows, selected),
                        "oracle_event_recall": ev["oracle_event_recall"],
                        "oracle_event_precision": ev["oracle_event_precision"],
                        "budgeted_event_iou": ev["mean_event_iou"],
                    }
                )
            d = pd.DataFrame(vals)
            out = d.mean(numeric_only=True).to_dict()
            out.update({"policy": policy, "budget_fraction": budget_fraction, "vlm_calls": budget})
            budget_rows.append(out)
    budget_df = pd.DataFrame(budget_rows)
    budget_df.to_csv(smoke_dir / "budget_sensitivity_metrics.csv", index=False)
    print(smoke_dir / "budget_sensitivity_metrics.csv")
    return {
        "random_summary": random_summary,
        "block": block_df,
        "rank": rank_df,
        "budget": budget_df,
    }


def write_report(out_dir: Path, rows: pd.DataFrame, metrics: pd.DataFrame, conc: dict, smoke: dict, discovery: dict, audit: pd.DataFrame) -> None:
    total = len(rows)
    pos = int(rows["oracle_positive"].sum())
    seg = rows.groupby("segment_id")["oracle_positive"].sum().sort_values(ascending=False)
    m = metrics[(metrics["gap_threshold_seconds"].eq(3)) & (metrics["iou_threshold"].eq(0.3)) & (metrics["budget_fraction"].isin([0.10, 0.20]))]
    table = m[["policy", "budget_fraction", "oracle_event_recall", "oracle_event_precision", "mean_event_iou", "vlm_call_saving"]].sort_values(["budget_fraction", "oracle_event_recall"], ascending=[True, False])
    budget = smoke["budget"]
    random20 = budget[(budget.policy.eq("random")) & (budget.budget_fraction.eq(0.20))]["oracle_event_recall"].iloc[0]
    best20 = budget[(~budget.policy.eq("random")) & (budget.budget_fraction.eq(0.20))]["oracle_event_recall"].max()
    top3_share = conc["top3_segment_positive_share"]
    if top3_share > 0.85:
        decision = "C. benchmark is too temporally concentrated and needs a new video source"
    elif pos / total < 0.03 or best20 <= random20 * 1.2:
        decision = "B. benchmark needs oracle prompt revision / manual relabeling"
    else:
        decision = "A. benchmark is valid enough for 100-trial formal evaluation"
    lines = [
        "# Focused Validation Report",
        "",
        "## 1. Experimental Definition",
        "- full conservative VLM scan = pseudo-oracle target.",
        "- This is not human GT.",
        "- The evaluation target is budgeted recovery of VLM-defined positive clips/events using fewer VLM calls.",
        "- Metrics are named `oracle_clip_recall`, `oracle_event_recall`, `oracle_event_precision`, `vlm_call_saving`, and `budgeted_event_iou`.",
        "",
        "## 2. Input Inventory",
        f"- input directory: `{discovery['files']['input_dir']}`",
        f"- labels: `{discovery['files']['labels']}`",
        f"- proxy: `{discovery['files']['proxy_learned'] if discovery['files']['proxy_learned'].exists() else discovery['files']['proxy']}`",
        f"- detected clips: {total}",
        "",
        "## 3. Pseudo-oracle Statistics",
        f"- total clips: {total}",
        f"- positive clips: {pos}",
        f"- negative clips: {total - pos}",
        f"- positive rate: {pos / total:.3f}",
        f"- segments: {rows['segment_id'].nunique()}",
        f"- top 3 segment positive share: {top3_share:.3f}",
        "",
        "Top positive segments:",
        "",
        df_to_md(seg.head(10).to_frame("positive_clips").reset_index()),
        "",
        "## 4. Human Sanity Check Package",
        f"- audit CSV: `{out_dir / '02_audit_package' / 'priority_audit_clips.csv'}`",
        f"- clips selected: {len(audit)}",
        "- Selection covers VLM positives, hard negatives, boundary negatives, and random negatives.",
        "- Human labels should be used to detect obvious VLM pseudo-oracle collapse, not to claim full human GT.",
        "",
        "## 5. Fixed-window to Variable-event Conversion",
        "- Merge rule: adjacent positive windows in the same segment are merged when temporal gap <= threshold.",
        f"- gap thresholds tested: {GAPS}",
        f"- IoU thresholds tested: {IOU_THRESHOLDS}",
        f"- event metrics CSV: `{out_dir / '03_event_conversion' / 'event_level_metrics.csv'}`",
        "",
        "Event-level result table at gap=3 sec, IoU=0.3, budgets 10% and 20%:",
        "",
        df_to_md(table.reset_index(drop=True)),
        "",
        "## 6. Temporal / Segment Concentration",
        f"- 61 positives concentrated in top 1 segment share: {conc['top1_segment_positive_share']:.3f}; top 3 share: {conc['top3_segment_positive_share']:.3f}.",
        f"- oracle events at gap=3 sec: {conc['oracle_events_gap3']}.",
        f"- top 1 segment event share: {conc['top1_segment_event_share']:.3f}.",
        "- top_count / learned_proxy do not appear to be evaluated solely by one event if event recall is spread across multiple segments; inspect `method_selected_segment_distribution.csv` and timelines for manual confirmation.",
        "- event-level recall comes from multiple independent oracle events when `matched_oracle_events` exceeds the top segment event count in `event_level_metrics.csv`.",
        "",
        "## 7. 20-trial Smoke Stability",
        f"- random 20-seed summary: `{out_dir / '05_smoke_trials' / 'random_20seed_summary.csv'}`",
        f"- block bootstrap metrics: `{out_dir / '05_smoke_trials' / 'block_bootstrap_metrics.csv'}`",
        f"- policy rank stability: `{out_dir / '05_smoke_trials' / 'policy_rank_stability.csv'}`",
        f"- budget sensitivity: `{out_dir / '05_smoke_trials' / 'budget_sensitivity_metrics.csv'}`",
        f"- 20% random oracle_event_recall: {random20:.3f}",
        f"- 20% best non-random oracle_event_recall: {best20:.3f}",
        "- Proxy-guided methods are considered stable only if they beat random across segment bootstrap and budget sensitivity outputs.",
        "",
        "## 8. Decision",
        decision,
        "",
        "Rationale:",
        f"- positive rate is {pos / total:.3f}; not vacuous.",
        f"- top3 segment positive share is {top3_share:.3f}.",
        f"- best 20% non-random event recall is {best20:.3f} vs random {random20:.3f}.",
        "- This decision is still conditional on the 40-clip human sanity check not finding obvious pseudo-oracle collapse.",
        "",
        "## 9. Next Recommended Step",
        "Fill `02_audit_package/priority_audit_clips.csv`, then run a follow-up analysis comparing human sanity labels against VLM pseudo-oracle errors before launching 100-trial formal evaluation.",
        "",
    ]
    (out_dir / "06_focused_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_dir / "06_focused_validation_report.md")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=Path, default=Path("focused_validation_outputs"))
    parser.add_argument("--input_dir", type=Path, default=None)
    parser.add_argument("--search_root", action="append", type=Path, default=[])
    args = parser.parse_args()
    out_dir = mkdir(args.output_dir)
    for sub in ["02_audit_package", "03_event_conversion", "04_temporal_concentration", "05_smoke_trials"]:
        mkdir(out_dir / sub)
    roots = args.search_root or [
        Path("/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs"),
        Path("/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy"),
        Path("/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2"),
        Path("/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs"),
    ]
    discovery = discover_inputs(roots, args.input_dir)
    rows, dfs = load_joined(discovery["files"])
    write_inventory(out_dir, discovery, dfs)
    write_pseudo_oracle_definition(out_dir, rows)
    audit = make_audit_package(out_dir, rows)
    metrics = event_conversion(out_dir, rows)
    conc = temporal_concentration(out_dir, rows)
    smoke = smoke_trials(out_dir, rows)
    write_report(out_dir, rows, metrics, conc, smoke, discovery, audit)
    print("focused_validation_complete=true")


if __name__ == "__main__":
    main()
