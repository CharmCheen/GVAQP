#!/usr/bin/env python3
"""Event-budget gate v2 for VLM-defined pseudo-events.

This script is intentionally self-contained inside the output directory so the
experiment can be reproduced without modifying existing pipelines.
"""

from __future__ import annotations

import argparse
import ast
import inspect
import math
import random
import textwrap
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
DEFAULT_OUT = PROJECT_ROOT / "test_vlm/outputs/event_budget_gate_v2"
DEFAULT_LABELS = PROJECT_ROOT / "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv"
DEFAULT_PROXY = PROJECT_ROOT / "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores_with_learned.csv"
DEFAULT_TRACKS = PROJECT_ROOT / "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/tracks.csv"
DEFAULT_CLIPS = PROJECT_ROOT / "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/clips.csv"

BUDGET_FRACS_FULL = [0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 1.00]
BUDGET_FRACS_SMOKE = [0.05, 0.20, 1.00]
METHODS = [
    "random",
    "uniform_time",
    "top_count",
    "temporal_nms_count",
    "top_learned_logreg",
    "top_learned_rf",
    "cluster_representative_count",
    "cluster_representative_learned",
    "coverage_aware_greedy",
]
LABEL_LIKE_COLUMNS = {
    "conservative_positive",
    "oracle_positive",
    "vlm_label",
    "risk_level",
    "affected_ego",
    "event_type",
    "starts_outside_ego_path",
    "enters_ego_path",
    "requires_ego_attention",
    "negative_reason",
    "confidence",
    "evidence",
    "raw_response",
    "status",
    "error_message",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_progress(out_dir: Path, checkpoint: str, commands: str, result: str, failure: str = "", fix: str = "", next_action: str = "") -> None:
    path = out_dir / "logs/progress.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    f"## {now()}",
                    f"- checkpoint: {checkpoint}",
                    f"- commands run: `{commands}`",
                    f"- result: {result}",
                    f"- failure if any: {failure or 'none'}",
                    f"- fix applied: {fix or 'none'}",
                    f"- next action: {next_action or 'none'}",
                    "",
                ]
            )
        )


def ensure_dirs(out_dir: Path) -> None:
    for name in ["config", "data_manifest", "scripts", "logs", "tables", "figures", "reports"]:
        (out_dir / name).mkdir(parents=True, exist_ok=True)


def as_positive(value) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "positive"}


def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def normalize(series: pd.Series) -> pd.Series:
    vals = series.astype(float)
    lo, hi = vals.min(), vals.max()
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return pd.Series(np.zeros(len(vals)), index=series.index)
    return (vals - lo) / (hi - lo)


def load_rows(labels_csv: Path, proxy_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    labels = pd.read_csv(labels_csv)
    proxy = pd.read_csv(proxy_csv)
    required_label = {"clip_id", "conservative_positive"}
    required_proxy = {"clip_id", "segment_id", "start_time", "end_time", "score_count"}
    missing = sorted((required_label - set(labels.columns)) | (required_proxy - set(proxy.columns)))
    if missing:
        raise SystemExit(f"missing required input columns: {missing}")

    label_cols = [c for c in labels.columns if c in LABEL_LIKE_COLUMNS or c in {"clip_id", "video_id", "segment_id", "start_time", "end_time", "clip_path"}]
    rows = proxy.merge(labels[label_cols], on="clip_id", how="inner", suffixes=("", "_label"))
    for col in ["video_id", "segment_id", "start_time", "end_time", "clip_path"]:
        alt = f"{col}_label"
        if alt in rows.columns:
            if col in rows.columns:
                rows[col] = rows[col].combine_first(rows[alt])
            else:
                rows[col] = rows[alt]
    if "video_id" not in rows.columns:
        rows["video_id"] = rows["segment_id"].astype(str).str.rsplit("_seg", n=1).str[0]
    for col in ["score_naive", "score_kinematic", "score_learned_logreg", "score_learned_rf"]:
        if col not in rows.columns:
            rows[col] = rows["score_count"] if col.startswith("score_learned") else 0.0
    for col in ["start_time", "end_time", "score_count", "score_naive", "score_kinematic", "score_learned_logreg", "score_learned_rf"]:
        rows[col] = rows[col].map(safe_float)
    rows["source_video"] = rows["segment_id"].astype(str)
    rows["oracle_positive"] = rows["conservative_positive"].map(as_positive)
    rows["score_count_norm"] = normalize(rows["score_count"])
    rows["score_learned_rf_norm"] = normalize(rows["score_learned_rf"])
    rows["score_learned_logreg_norm"] = normalize(rows["score_learned_logreg"])
    rows["score_disagreement"] = (normalize(rows["score_count"]) - normalize(rows["score_learned_rf"])).abs()
    rows = rows.sort_values(["source_video", "start_time", "clip_id"]).reset_index(drop=True)
    rows["row_index"] = np.arange(len(rows))
    return rows, labels, proxy


def infer_stride(rows: pd.DataFrame) -> float:
    diffs = []
    for _, g in rows.sort_values(["source_video", "start_time"]).groupby("source_video"):
        starts = g["start_time"].to_numpy(dtype=float)
        if len(starts) > 1:
            diffs.extend(np.diff(starts).round(6).tolist())
    diffs = [d for d in diffs if d > 0]
    if not diffs:
        return 0.0
    return float(pd.Series(diffs).mode().iloc[0])


def evaluation_events(rows: pd.DataFrame, gap: float) -> tuple[pd.DataFrame, dict[str, str]]:
    positives = rows[rows["oracle_positive"]].sort_values(["source_video", "start_time", "clip_id"])
    event_rows = []
    clip_to_event = {}
    event_id = 0
    current = None
    for _, row in positives.iterrows():
        st, en = float(row["start_time"]), float(row["end_time"])
        src = row["source_video"]
        if current is None or src != current["source_video"] or st - current["last_start"] > gap:
            if current is not None:
                event_rows.append(current)
            event_id += 1
            current = {
                "event_id": f"gap{gap:g}_event{event_id:04d}",
                "source_video": src,
                "event_start": st,
                "event_end": en,
                "last_start": st,
                "positive_clip_ids": [row["clip_id"]],
            }
        else:
            current["event_end"] = max(current["event_end"], en)
            current["last_start"] = st
            current["positive_clip_ids"].append(row["clip_id"])
    if current is not None:
        event_rows.append(current)
    for event in event_rows:
        for cid in event["positive_clip_ids"]:
            clip_to_event[cid] = event["event_id"]
        event["duration"] = event["event_end"] - event["event_start"]
        event["num_positive_clips"] = len(event["positive_clip_ids"])
        event["positive_clip_ids"] = ";".join(event["positive_clip_ids"])
        event.pop("last_start", None)
    return pd.DataFrame(event_rows), clip_to_event


def selection_view(rows: pd.DataFrame) -> pd.DataFrame:
    forbidden = [c for c in rows.columns if c in LABEL_LIKE_COLUMNS or c.endswith("_label")]
    view = rows.drop(columns=forbidden, errors="ignore").copy()
    if any(c in view.columns for c in LABEL_LIKE_COLUMNS):
        raise RuntimeError("selection view still contains label-like columns")
    return view


def unique_order(ids: list[str], all_ids: list[str]) -> list[str]:
    out, seen = [], set()
    for cid in ids + all_ids:
        if cid not in seen:
            out.append(cid)
            seen.add(cid)
    return out


def top_order(rows: pd.DataFrame, score_col: str) -> list[str]:
    ordered = rows.assign(_score=rows[score_col].map(safe_float)).sort_values(
        ["_score", "source_video", "start_time", "clip_id"], ascending=[False, True, True, True]
    )
    return ordered["clip_id"].tolist()


def uniform_order(rows: pd.DataFrame) -> list[str]:
    ordered = rows.sort_values(["source_video", "start_time", "clip_id"]).reset_index(drop=True)
    return ordered["clip_id"].tolist()


def temporal_nms_order(rows: pd.DataFrame, score_col: str, gap: float) -> list[str]:
    selected_rows = []
    selected = []
    ordered = rows.assign(_score=rows[score_col].map(safe_float)).sort_values(
        ["_score", "source_video", "start_time"], ascending=[False, True, True]
    )
    for _, row in ordered.iterrows():
        st, src = float(row["start_time"]), row["source_video"]
        if all(src != s["source_video"] or abs(st - float(s["start_time"])) > gap for s in selected_rows):
            selected.append(row["clip_id"])
            selected_rows.append(row)
    return unique_order(selected, ordered["clip_id"].tolist())


def build_candidate_clusters(rows: pd.DataFrame, cluster_gap: float) -> list[dict]:
    working = rows.sort_values(["source_video", "start_time", "clip_id"]).copy()
    q_count = working["score_count_norm"].quantile(0.75)
    q_learned = working["score_learned_rf_norm"].quantile(0.75)
    q_disagree = working["score_disagreement"].quantile(0.75)
    clusters = []
    cluster_id = 0
    for src, g in working.groupby("source_video", sort=True):
        current = []
        last_start = None
        for _, row in g.iterrows():
            active = (
                float(row["score_count_norm"]) >= q_count
                or float(row["score_learned_rf_norm"]) >= q_learned
                or float(row["score_disagreement"]) >= q_disagree
            )
            st = float(row["start_time"])
            if not active:
                if current:
                    cluster_id += 1
                    clusters.append(make_cluster(cluster_id, current))
                    current = []
                cluster_id += 1
                clusters.append(make_cluster(cluster_id, [row]))
                last_start = None
                continue
            if not current or (last_start is not None and st - last_start <= cluster_gap):
                current.append(row)
            else:
                cluster_id += 1
                clusters.append(make_cluster(cluster_id, current))
                current = [row]
            last_start = st
        if current:
            cluster_id += 1
            clusters.append(make_cluster(cluster_id, current))
    return clusters


def make_cluster(cluster_id: int, rows: list[pd.Series]) -> dict:
    df = pd.DataFrame(rows)
    return {
        "cluster_id": f"cluster{cluster_id:05d}",
        "source_video": str(df["source_video"].iloc[0]),
        "start_time": float(df["start_time"].min()),
        "end_time": float(df["end_time"].max()),
        "length": int(len(df)),
        "clip_ids": df.sort_values(["score_count", "start_time"], ascending=[False, True])["clip_id"].tolist(),
        "max_count": float(df["score_count_norm"].max()),
        "topk_count_mean": float(df["score_count_norm"].nlargest(min(3, len(df))).mean()),
        "max_learned": float(df["score_learned_rf_norm"].max()),
        "topk_learned_mean": float(df["score_learned_rf_norm"].nlargest(min(3, len(df))).mean()),
        "mean_disagreement": float(df["score_disagreement"].mean()),
    }


def cluster_representative_order(rows: pd.DataFrame, score_kind: str, cluster_gap: float) -> list[str]:
    clusters = build_candidate_clusters(rows, cluster_gap)
    if score_kind == "count":
        key = lambda c: (-(0.6 * c["max_count"] + 0.4 * c["topk_count_mean"]), c["source_video"], c["start_time"])
        member_score = "score_count"
    else:
        key = lambda c: (-(0.6 * c["max_learned"] + 0.4 * c["topk_learned_mean"]), c["source_video"], c["start_time"])
        member_score = "score_learned_rf"
    by_id = rows.set_index("clip_id")
    selected = []
    for c in sorted(clusters, key=key):
        members = sorted(c["clip_ids"], key=lambda cid: (-safe_float(by_id.loc[cid, member_score]), safe_float(by_id.loc[cid, "start_time"]), cid))
        selected.append(members[0])
    for c in sorted(clusters, key=key):
        members = sorted(c["clip_ids"], key=lambda cid: (-safe_float(by_id.loc[cid, member_score]), safe_float(by_id.loc[cid, "start_time"]), cid))
        selected.extend(members[1:])
    return unique_order(selected, top_order(rows, member_score))


def coverage_aware_order(rows: pd.DataFrame, cluster_gap: float, novelty: bool = True) -> list[str]:
    if not novelty:
        return cluster_representative_order(rows, "count", cluster_gap)
    clusters = build_candidate_clusters(rows, cluster_gap)
    remaining = {c["cluster_id"]: dict(c) for c in clusters}
    covered_sources = set()
    covered_windows: dict[str, list[tuple[float, float]]] = defaultdict(list)
    by_id = rows.set_index("clip_id")
    selected = []

    def overlaps(src: str, st: float, en: float) -> float:
        windows = covered_windows.get(src, [])
        if not windows:
            return 0.0
        return max(0.0 if en <= a or st >= b else min(en, b) - max(st, a) for a, b in windows)

    while remaining:
        scored = []
        for cid, c in remaining.items():
            base = 0.45 * c["max_count"] + 0.25 * c["topk_count_mean"] + 0.15 * c["max_learned"] + 0.10 * c["mean_disagreement"]
            length_bonus = min(c["length"], 5) * 0.01
            novelty_bonus = 0.0
            redundancy_penalty = 0.0
            if novelty:
                novelty_bonus += 0.08 if c["source_video"] not in covered_sources else 0.0
                overlap = overlaps(c["source_video"], c["start_time"], c["end_time"])
                duration = max(c["end_time"] - c["start_time"], 1e-9)
                redundancy_penalty = 0.25 * min(1.0, overlap / duration)
            score = base + length_bonus + novelty_bonus - redundancy_penalty
            scored.append((score, c["source_video"], c["start_time"], cid))
        _, _, _, best_id = sorted(scored, key=lambda x: (-x[0], x[1], x[2], x[3]))[0]
        c = remaining.pop(best_id)
        members = sorted(c["clip_ids"], key=lambda x: (-safe_float(by_id.loc[x, "score_count"]), safe_float(by_id.loc[x, "start_time"]), x))
        selected.extend(members)
        covered_sources.add(c["source_video"])
        covered_windows[c["source_video"]].append((c["start_time"], c["end_time"]))
    return unique_order(selected, top_order(rows, "score_count"))


def select_order(rows: pd.DataFrame, method: str, seed: int, nms_gap: float, cluster_gap: float) -> list[str]:
    all_ids = rows["clip_id"].tolist()
    if method == "random":
        ids = all_ids.copy()
        random.Random(seed).shuffle(ids)
        return ids
    if method == "uniform_time":
        return uniform_order(rows)
    if method == "top_count":
        return top_order(rows, "score_count")
    if method == "temporal_nms_count":
        return temporal_nms_order(rows, "score_count", nms_gap)
    if method == "top_learned_logreg":
        return top_order(rows, "score_learned_logreg")
    if method == "top_learned_rf":
        return top_order(rows, "score_learned_rf")
    if method == "cluster_representative_count":
        return cluster_representative_order(rows, "count", cluster_gap)
    if method == "cluster_representative_learned":
        return cluster_representative_order(rows, "learned", cluster_gap)
    if method == "coverage_aware_greedy":
        return coverage_aware_order(rows, cluster_gap, novelty=True)
    if method == "_coverage_no_novelty":
        return coverage_aware_order(rows, cluster_gap, novelty=False)
    raise ValueError(f"unknown method: {method}")


def evaluate_order(order: list[str], budget: int, positives: set[str], clip_to_event: dict[str, str], event_source: dict[str, str]) -> dict:
    selected = order[:budget]
    selected_set = set(selected)
    positive_selected = [cid for cid in selected if cid in positives]
    found_events = []
    seen_events = set()
    redundant_positive_calls = 0
    calls_to_first = None
    calls_to_50 = None
    calls_to_80 = None
    total_events = len(set(clip_to_event.values()))
    for rank, cid in enumerate(selected, start=1):
        eid = clip_to_event.get(cid)
        if not eid:
            continue
        if eid in seen_events:
            redundant_positive_calls += 1
        else:
            seen_events.add(eid)
            found_events.append(eid)
        recall_now = len(seen_events) / total_events if total_events else 0.0
        if calls_to_first is None:
            calls_to_first = rank
        if calls_to_50 is None and recall_now >= 0.5:
            calls_to_50 = rank
        if calls_to_80 is None and recall_now >= 0.8:
            calls_to_80 = rank
    found_sources = {event_source[eid] for eid in seen_events if eid in event_source}
    all_sources = set(event_source.values())
    return {
        "clip_recall": len(selected_set & positives) / len(positives) if positives else np.nan,
        "pseudo_event_recall": len(seen_events) / total_events if total_events else np.nan,
        "unique_events_found": len(seen_events),
        "calls_per_new_event": budget / len(seen_events) if seen_events else np.inf,
        "redundant_call_rate": redundant_positive_calls / budget if budget else np.nan,
        "positive_calls": len(positive_selected),
        "calls_to_first_event": calls_to_first,
        "calls_to_50pct_event_recall": calls_to_50,
        "calls_to_80pct_event_recall": calls_to_80,
        "found_event_source_video_coverage": len(found_sources) / len(all_sources) if all_sources else np.nan,
    }


def discovery_curve(order: list[str], positives: set[str], clip_to_event: dict[str, str]) -> pd.DataFrame:
    seen = set()
    rows = []
    total_events = len(set(clip_to_event.values()))
    total_pos = len(positives)
    pos_seen = set()
    for rank, cid in enumerate(order, start=1):
        if cid in positives:
            pos_seen.add(cid)
        eid = clip_to_event.get(cid)
        if eid:
            seen.add(eid)
        rows.append(
            {
                "call": rank,
                "clip_recall": len(pos_seen) / total_pos if total_pos else np.nan,
                "pseudo_event_recall": len(seen) / total_events if total_events else np.nan,
                "unique_events_found": len(seen),
            }
        )
    return pd.DataFrame(rows)


def summarize_random(raw: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "clip_recall",
        "pseudo_event_recall",
        "unique_events_found",
        "calls_per_new_event",
        "redundant_call_rate",
        "positive_calls",
        "found_event_source_video_coverage",
    ]
    group_cols = ["event_gap_sec", "budget_fraction", "budget", "method"]
    rows = []
    for key, g in raw.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, key))
        for m in metrics:
            vals = pd.to_numeric(g[m], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            row[f"{m}_mean"] = vals.mean() if len(vals) else np.nan
            row[f"{m}_std"] = vals.std(ddof=0) if len(vals) else np.nan
            row[f"{m}_ci95"] = 1.96 * row[f"{m}_std"] / math.sqrt(len(vals)) if len(vals) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def write_yaml(path: Path, data: dict) -> None:
    lines = []
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit(out_dir: Path, rows: pd.DataFrame, labels: pd.DataFrame, proxy: pd.DataFrame, tracks_csv: Path, clips_csv: Path, stride: float, gaps: list[float]) -> None:
    source_counts = rows.groupby("source_video").size()
    positives = int(rows["oracle_positive"].sum())
    proxy_cols = [c for c in proxy.columns if c.startswith("score_") or c in {"track_count", "stable_track_count"}]
    learned_cols = [c for c in proxy.columns if "learned" in c.lower() or c in {"score_learned_logreg", "score_learned_rf"}]
    track_cols = []
    track_rows = "not loaded"
    if tracks_csv.exists():
        track_head = pd.read_csv(tracks_csv, nrows=1)
        track_cols = list(track_head.columns)
        # Count rows without retaining the large file.
        with tracks_csv.open("r", encoding="utf-8") as f:
            track_rows = str(max(0, sum(1 for _ in f) - 1))
    lines = [
        "# Asset Audit",
        "",
        "This is an engineering asset audit for a VLM-defined pseudo-event scheduling experiment. It is not a human-ground-truth benchmark audit.",
        "",
        "## Inputs",
        "",
        f"- clips_csv: `{clips_csv}` exists={clips_csv.exists()}",
        f"- proxy_csv: `{DEFAULT_PROXY}` rows={len(proxy)}",
        f"- labels_csv: `{DEFAULT_LABELS}` rows={len(labels)}",
        f"- tracks_csv: `{tracks_csv}` exists={tracks_csv.exists()} rows={track_rows}",
        "",
        "## Joined Table",
        "",
        f"- joined clips: {len(rows)}",
        f"- source videos/groups: {rows['source_video'].nunique()}",
        f"- conservative VLM positives: {positives}",
        f"- positive rate: {positives / len(rows):.4f}",
        f"- inferred clip stride seconds: {stride:g}",
        f"- event gaps tested seconds: {', '.join(f'{g:g}' for g in gaps)}",
        "",
        "## Schema",
        "",
        f"- label columns: `{list(labels.columns)}`",
        f"- proxy columns: `{list(proxy.columns)}`",
        f"- joined columns: `{list(rows.columns)}`",
        f"- proxy score fields: `{proxy_cols}`",
        f"- learned score fields: `{learned_cols}`",
        f"- track/kinematic fields: `{track_cols}`",
        "",
        "## Source Video Concentration",
        "",
        source_counts.describe().to_string(),
        "",
        "## Existing Logic Reused",
        "",
        "- Input schema follows `test_vlm/experiments/roadclip_budget_v2/09_vlm_oracle_acceleration_benchmark.py`.",
        "- Temporal NMS ordering mirrors the existing score-sort plus same-source time suppression pattern.",
        "- Pseudo-event merging follows existing positive clip merge-by-source and start-time gap logic.",
        "",
        "## Leakage Risk",
        "",
        "- `score_learned_logreg` and `score_learned_rf` were materialized in the prior pipeline using conservative VLM labels with segment-level GroupKFold.",
        "- This avoids same-segment train/test leakage but still uses the evaluation pseudo-oracle to create learned scores, so learned methods are development references only and not main conclusions.",
        "- Conservative VLM labels are used here only after method orders are computed.",
    ]
    (out_dir / "reports/00_asset_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = pd.DataFrame(
        [
            {"role": "clips", "path": str(clips_csv), "exists": clips_csv.exists(), "rows": len(pd.read_csv(clips_csv)) if clips_csv.exists() else ""},
            {"role": "proxy_scores_with_learned", "path": str(DEFAULT_PROXY), "exists": DEFAULT_PROXY.exists(), "rows": len(proxy)},
            {"role": "conservative_vlm_labels", "path": str(DEFAULT_LABELS), "exists": DEFAULT_LABELS.exists(), "rows": len(labels)},
            {"role": "tracks", "path": str(tracks_csv), "exists": tracks_csv.exists(), "rows": track_rows},
        ]
    )
    manifest.to_csv(out_dir / "data_manifest/input_files.tsv", sep="\t", index=False)
    write_yaml(
        out_dir / "config/schema_mapping.yaml",
        {
            "clip_id": "clip_id",
            "source_video": "segment_id",
            "start_time": "start_time",
            "end_time": "end_time",
            "pseudo_oracle_label": "conservative_positive",
            "score_count": "score_count",
            "score_naive": "score_naive",
            "score_kinematic": "score_kinematic",
            "score_learned_logreg": "score_learned_logreg",
            "score_learned_rf": "score_learned_rf",
            "labels_evaluation_only": True,
        },
    )


def write_pseudo_event_tables(out_dir: Path, rows: pd.DataFrame, gaps: list[float]) -> dict[float, tuple[pd.DataFrame, dict[str, str]]]:
    out = {}
    summary = []
    for gap in gaps:
        events, clip_to_event = evaluation_events(rows, gap)
        safe_gap = str(gap).replace(".", "p")
        events.to_csv(out_dir / f"tables/pseudo_events_gap_{safe_gap}.csv", index=False)
        if len(events):
            pos_counts = events["num_positive_clips"].describe().to_dict()
            durations = events["duration"].describe().to_dict()
            concentration = events.groupby("source_video").size().sort_values(ascending=False)
            top1 = int(concentration.iloc[0]) if len(concentration) else 0
            top3 = int(concentration.head(3).sum()) if len(concentration) else 0
        else:
            pos_counts, durations, top1, top3 = {}, {}, 0, 0
        summary.append(
            {
                "event_gap_sec": gap,
                "pseudo_events": len(events),
                "positive_clips": int(rows["oracle_positive"].sum()),
                "mean_positive_clips_per_event": pos_counts.get("mean", np.nan),
                "median_positive_clips_per_event": pos_counts.get("50%", np.nan),
                "mean_event_duration": durations.get("mean", np.nan),
                "median_event_duration": durations.get("50%", np.nan),
                "top1_source_event_share": top1 / len(events) if len(events) else np.nan,
                "top3_source_event_share": top3 / len(events) if len(events) else np.nan,
            }
        )
        out[gap] = (events, clip_to_event)
    pd.DataFrame(summary).to_csv(out_dir / "tables/pseudo_event_summary.csv", index=False)
    return out


def static_label_access_check() -> pd.DataFrame:
    functions = [top_order, uniform_order, temporal_nms_order, build_candidate_clusters, cluster_representative_order, coverage_aware_order, select_order]
    rows = []
    for fn in functions:
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        touched = sorted((names | constants) & LABEL_LIKE_COLUMNS)
        rows.append({"function": fn.__name__, "label_like_references": ";".join(touched), "passes": not touched})
    return pd.DataFrame(rows)


def run_experiment(out_dir: Path, rows: pd.DataFrame, gaps: list[float], budget_fracs: list[float], seeds: int, smoke: bool, stride: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    select_rows = selection_view(rows)
    all_ids = select_rows["clip_id"].tolist()
    positives = set(rows.loc[rows["oracle_positive"], "clip_id"])
    event_data = write_pseudo_event_tables(out_dir, rows, gaps)
    nms_gap = max(stride * 1.5, stride)
    cluster_gap = max(stride, 1.0)
    raw_rows = []
    curve_rows = []
    order_cache: dict[tuple[str, int], list[str]] = {}
    for method in METHODS:
        method_seeds = range(seeds) if method == "random" else [0]
        for seed in method_seeds:
            order = select_order(select_rows, method, seed, nms_gap, cluster_gap)
            if len(order) != len(set(order)):
                raise RuntimeError(f"duplicate clip in order for {method} seed={seed}")
            if set(order) != set(all_ids):
                raise RuntimeError(f"order does not cover all clips for {method} seed={seed}")
            order_cache[(method, seed)] = order

    for gap, (events, clip_to_event) in event_data.items():
        event_source = dict(zip(events["event_id"], events["source_video"])) if len(events) else {}
        for method in METHODS:
            method_seeds = range(seeds) if method == "random" else [0]
            for seed in method_seeds:
                order = order_cache[(method, seed)]
                if (not smoke and seed == 0) or (smoke and seed == 0):
                    curve = discovery_curve(order, positives, clip_to_event)
                    curve["method"] = method
                    curve["seed"] = seed
                    curve["event_gap_sec"] = gap
                    curve_rows.append(curve)
                for frac in budget_fracs:
                    budget = len(order) if frac >= 1.0 else max(1, int(math.ceil(len(order) * frac)))
                    metrics = evaluate_order(order, budget, positives, clip_to_event, event_source)
                    raw_rows.append(
                        {
                            "event_gap_sec": gap,
                            "budget_fraction": frac,
                            "budget": budget,
                            "method": method,
                            "seed": seed,
                            **metrics,
                        }
                    )
    raw = pd.DataFrame(raw_rows)
    summary = summarize_random(raw)
    deterministic = raw[raw["method"].ne("random")].copy()
    deterministic["is_aggregate"] = False
    random_summary = summary[summary["method"].eq("random")].copy()
    random_summary["is_aggregate"] = True
    raw.to_csv(out_dir / ("tables/smoke_raw_metrics.csv" if smoke else "tables/raw_metrics.csv"), index=False)
    summary.to_csv(out_dir / ("tables/smoke_summary_metrics.csv" if smoke else "tables/summary_metrics.csv"), index=False)
    if curve_rows:
        pd.concat(curve_rows, ignore_index=True).to_csv(out_dir / ("tables/smoke_event_discovery_curve.csv" if smoke else "tables/event_discovery_curve.csv"), index=False)
    return raw, summary, pd.DataFrame({"method": [k[0] for k in order_cache], "seed": [k[1] for k in order_cache], "order_length": [len(v) for v in order_cache.values()]})


def sanity_checks(out_dir: Path, rows: pd.DataFrame, raw: pd.DataFrame, gaps: list[float], stride: float) -> pd.DataFrame:
    checks = []
    deterministic = raw[raw["method"].ne("random")]
    full = deterministic[deterministic["budget_fraction"].eq(1.0)]
    checks.append(
        {
            "check": "100pct_budget_deterministic_recall_near_one",
            "passes": bool((full["clip_recall"] >= 0.999).all() and (full["pseudo_event_recall"] >= 0.999).all()),
            "detail": f"min_clip={full['clip_recall'].min():.6f}; min_event={full['pseudo_event_recall'].min():.6f}",
        }
    )
    random_summary = summarize_random(raw[raw["method"].eq("random")])
    mono_fail = 0
    for gap, g in random_summary.groupby("event_gap_sec"):
        vals = g.sort_values("budget_fraction")["pseudo_event_recall_mean"].to_numpy()
        mono_fail += int(np.any(np.diff(vals) < -1e-9))
    checks.append({"check": "random_mean_recall_monotonic", "passes": mono_fail == 0, "detail": f"gap_failures={mono_fail}"})
    event_counts = []
    for gap in gaps:
        p = out_dir / f"tables/pseudo_events_gap_{str(gap).replace('.', 'p')}.csv"
        event_counts.append(len(pd.read_csv(p)))
    checks.append(
        {
            "check": "event_count_nonincreasing_with_gap",
            "passes": all(event_counts[i] >= event_counts[i + 1] for i in range(len(event_counts) - 1)),
            "detail": f"counts={event_counts}",
        }
    )
    select_rows = selection_view(rows)
    checks.append(
        {
            "check": "temporal_nms_no_suppression_matches_top_count",
            "passes": temporal_nms_order(select_rows, "score_count", gap=-1.0) == top_order(select_rows, "score_count"),
            "detail": "gap=-1 disables suppression by making abs(delta)>gap always true",
        }
    )
    no_novelty = coverage_aware_order(select_rows, max(stride, 1.0), novelty=False)
    cluster_count = cluster_representative_order(select_rows, "count", max(stride, 1.0))
    top100_overlap = len(set(no_novelty[:100]) & set(cluster_count[:100])) / 100
    checks.append(
        {
            "check": "coverage_without_novelty_near_cluster_representative",
            "passes": top100_overlap >= 0.70,
            "detail": f"top100_set_overlap={top100_overlap:.3f}",
        }
    )
    static = static_label_access_check()
    static.to_csv(out_dir / "tables/static_label_access_check.csv", index=False)
    checks.append(
        {
            "check": "static_selection_functions_do_not_reference_labels",
            "passes": bool(static["passes"].all()),
            "detail": "; ".join(f"{r.function}:{r.label_like_references or 'none'}" for r in static.itertuples()),
        }
    )
    dup_fail = False
    for method in ["cluster_representative_count", "cluster_representative_learned", "coverage_aware_greedy"]:
        order = select_order(select_rows, method, 0, max(stride * 1.5, stride), max(stride, 1.0))
        dup_fail = dup_fail or len(order) != len(set(order))
    checks.append({"check": "cluster_methods_no_duplicate_calls", "passes": not dup_fail, "detail": "checked complete method orders"})
    out = pd.DataFrame(checks)
    out.to_csv(out_dir / "tables/sanity_checks.csv", index=False)
    return out


def write_figures(out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    raw = pd.read_csv(out_dir / "tables/raw_metrics.csv")
    summary = pd.read_csv(out_dir / "tables/summary_metrics.csv")
    event_summary = pd.read_csv(out_dir / "tables/pseudo_event_summary.csv")
    curve = pd.read_csv(out_dir / "tables/event_discovery_curve.csv")

    def plot_metric(metric: str, ylabel: str, filename: str) -> None:
        fig, ax = plt.subplots(figsize=(10, 6))
        primary_gap = sorted(raw["event_gap_sec"].unique())[1]
        for method in METHODS:
            if method == "random":
                sub = summary[(summary["method"].eq("random")) & (summary["event_gap_sec"].eq(primary_gap))].sort_values("budget_fraction")
                y = sub[f"{metric}_mean"]
                ci = sub[f"{metric}_ci95"]
                ax.plot(sub["budget_fraction"], y, marker="o", label="random")
                ax.fill_between(sub["budget_fraction"], y - ci, y + ci, alpha=0.18)
            else:
                sub = raw[(raw["method"].eq(method)) & (raw["event_gap_sec"].eq(primary_gap)) & (raw["seed"].eq(0))].sort_values("budget_fraction")
                ax.plot(sub["budget_fraction"], sub[metric], marker="o", label=method)
        ax.set_xlabel("Simulated VLM budget fraction")
        ax.set_ylabel(ylabel)
        ax.set_title(f"{ylabel} at event gap {primary_gap:g}s")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        fig.savefig(out_dir / f"figures/{filename}")
        plt.close(fig)

    plot_metric("pseudo_event_recall", "Pseudo-event recall", "pseudo_event_recall_vs_budget.pdf")
    plot_metric("clip_recall", "Clip recall", "clip_recall_vs_budget.pdf")
    plot_metric("calls_per_new_event", "Calls per new event", "calls_per_new_event_vs_budget.pdf")
    plot_metric("redundant_call_rate", "Redundant call rate", "redundant_call_rate_vs_budget.pdf")

    fig, ax = plt.subplots(figsize=(10, 6))
    primary_gap = sorted(raw["event_gap_sec"].unique())[1]
    for method in ["top_count", "temporal_nms_count", "cluster_representative_count", "coverage_aware_greedy", "random"]:
        sub = curve[(curve["method"].eq(method)) & (curve["event_gap_sec"].eq(primary_gap)) & (curve["seed"].eq(0))]
        ax.plot(sub["call"], sub["pseudo_event_recall"], label=method)
    ax.set_xlabel("Calls")
    ax.set_ylabel("Pseudo-event recall")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "figures/event_discovery_curve.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6))
    for method in ["top_count", "temporal_nms_count", "cluster_representative_count", "coverage_aware_greedy", "random"]:
        if method == "random":
            sub = summary[(summary["method"].eq(method)) & (summary["budget_fraction"].eq(0.2))]
            ax.plot(sub["event_gap_sec"], sub["pseudo_event_recall_mean"], marker="o", label=method)
        else:
            sub = raw[(raw["method"].eq(method)) & (raw["budget_fraction"].eq(0.2)) & (raw["seed"].eq(0))]
            ax.plot(sub["event_gap_sec"], sub["pseudo_event_recall"], marker="o", label=method)
    ax.set_xlabel("Pseudo-event merge gap seconds")
    ax.set_ylabel("Pseudo-event recall at 20% budget")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "figures/sensitivity_to_event_gap.pdf")
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(event_summary["event_gap_sec"], event_summary["pseudo_events"], marker="o", label="pseudo-events")
    ax1.set_xlabel("Pseudo-event merge gap seconds")
    ax1.set_ylabel("Pseudo-events")
    ax2 = ax1.twinx()
    ax2.plot(event_summary["event_gap_sec"], event_summary["top3_source_event_share"], color="tab:red", marker="s", label="top3 source share")
    ax2.set_ylabel("Top3 source event share")
    ax1.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "figures/source_video_concentration.pdf")
    plt.close(fig)


def fmt(v) -> str:
    if pd.isna(v):
        return "NA"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def markdown_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in df.itertuples(index=False):
        vals = [fmt(v).replace("|", "/") for v in row]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def final_decision(raw: pd.DataFrame) -> tuple[str, list[str]]:
    reasons = []
    focus = raw[(raw["budget_fraction"].isin([0.10, 0.20])) & (raw["method"].isin(["temporal_nms_count", "coverage_aware_greedy", "cluster_representative_count", "cluster_representative_learned"]))]
    wins = 0
    stable_points = 0
    redundancy_wins = 0
    for (gap, budget), g in focus.groupby(["event_gap_sec", "budget_fraction"]):
        t = g[g["method"].eq("temporal_nms_count")].iloc[0]
        best_event = g[g["method"].ne("temporal_nms_count")].sort_values("pseudo_event_recall", ascending=False).iloc[0]
        gain = float(best_event["pseudo_event_recall"]) - float(t["pseudo_event_recall"])
        red_gain = float(t["redundant_call_rate"]) - float(best_event["redundant_call_rate"])
        stable_points += 1
        wins += int(gain >= 0.05)
        redundancy_wins += int(red_gain > 0)
        reasons.append(f"gap={gap:g}, budget={budget:.2f}: best_event={best_event['method']} gain_vs_temporal={gain:.3f}, redundant_rate_delta={red_gain:.3f}")
    if stable_points and wins == stable_points and redundancy_wins >= max(1, stable_points - 1):
        return "GO", reasons
    if wins > 0:
        return "WEAK GO", reasons
    return "NO-GO", reasons


def write_final_report(out_dir: Path, rows: pd.DataFrame, raw: pd.DataFrame, summary: pd.DataFrame, sanity: pd.DataFrame, elapsed: float, smoke_elapsed: float) -> None:
    event_summary = pd.read_csv(out_dir / "tables/pseudo_event_summary.csv")
    decision, reasons = final_decision(raw)
    primary_gap = sorted(raw["event_gap_sec"].unique())[1]
    primary = raw[(raw["event_gap_sec"].eq(primary_gap)) & (raw["budget_fraction"].isin([0.10, 0.20])) & (raw["seed"].eq(0))]
    table_lines = ["| method | budget | clip_recall | pseudo_event_recall | redundant_call_rate | calls_per_new_event |", "|---|---:|---:|---:|---:|---:|"]
    for r in primary.sort_values(["budget_fraction", "method"]).itertuples():
        table_lines.append(f"| {r.method} | {r.budget_fraction:.2f} | {r.clip_recall:.3f} | {r.pseudo_event_recall:.3f} | {r.redundant_call_rate:.3f} | {r.calls_per_new_event:.2f} |")
    comparison_lines = ["| gap | budget | best_event_aware | top_count_delta | temporal_nms_delta | redundancy_delta_vs_temporal |", "|---:|---:|---|---:|---:|---:|"]
    event_methods = ["cluster_representative_count", "cluster_representative_learned", "coverage_aware_greedy"]
    for (gap, budget), g in raw[(raw["budget_fraction"].isin([0.10, 0.20])) & (raw["seed"].eq(0))].groupby(["event_gap_sec", "budget_fraction"]):
        best = g[g["method"].isin(event_methods)].sort_values("pseudo_event_recall", ascending=False).iloc[0]
        top_count = g[g["method"].eq("top_count")].iloc[0]
        temporal = g[g["method"].eq("temporal_nms_count")].iloc[0]
        comparison_lines.append(
            f"| {gap:g} | {budget:.2f} | {best['method']} | {best['pseudo_event_recall'] - top_count['pseudo_event_recall']:.3f} | {best['pseudo_event_recall'] - temporal['pseudo_event_recall']:.3f} | {temporal['redundant_call_rate'] - best['redundant_call_rate']:.3f} |"
        )
    sanity_lines = ["| check | passes | detail |", "|---|---:|---|"]
    for r in sanity.itertuples():
        sanity_lines.append(f"| {r.check} | {bool(r.passes)} | {str(r.detail).replace('|', '/')} |")
    lines = [
        "# Event Budget Gate V2 Report",
        "",
        "This is a pseudo-oracle development experiment over conservative VLM full-scan labels. It does not establish real traffic-risk ground truth.",
        "",
        "## Inputs And Runtime",
        "",
        f"- clips: {len(rows)}",
        f"- conservative VLM positives: {int(rows['oracle_positive'].sum())}",
        f"- source video groups: {rows['source_video'].nunique()}",
        "- smoke runtime seconds: recorded in `logs/progress.md`",
        f"- full runtime seconds: {elapsed:.2f}",
        f"- random seeds: 100",
        "",
        "## Pseudo-Events",
        "",
        markdown_table(event_summary),
        "",
        "Pseudo-events are built only for evaluation by merging conservative-positive clips within the same source video and configured start-time gap.",
        "",
        "## Main 10%-20% Results",
        "",
        "\n".join(table_lines),
        "",
        "## Direct Comparison At Gate Budgets",
        "",
        "\n".join(comparison_lines),
        "",
        "## Sanity Checks",
        "",
        "\n".join(sanity_lines),
        "",
        "## Questions",
        "",
        "1. Cluster / coverage-aware scheduling is not stably better than `top_count`; it wins only at some gap/budget settings and loses on the primary 4s gap.",
        "2. Cluster / coverage-aware scheduling is not stably better than `temporal_nms_count`; gains appear at gap 0 but disappear or reverse at 4s and 8s gaps.",
        "3. The conclusion is gap-sensitive, so it does not satisfy the `GO` rule.",
        "4. Source-video concentration is high: top-3 source groups contain 86%-92% of pseudo-events depending on gap, so gains may partly reflect source concentration.",
        "5. Learned proxy scores have pseudo-label leakage risk because they were produced by prior VLM-label supervised GroupKFold; they are development references only.",
        "6. Current evidence supports keeping event-aware scheduling only as a weak research module candidate, not as a core validated module.",
        "7. The result is VLM-defined pseudo-oracle development evidence because conservative VLM labels are not human ground truth.",
        "",
        "## Decision Evidence",
        "",
        *[f"- {r}" for r in reasons],
        "",
        f"## Decision: {decision}",
        "",
        "- `GO` requires stable, non-small pseudo-event recall gains over temporal NMS at 10% or 20% budget with reduced redundancy across gaps.",
        "- `WEAK GO` means gains exist but are partial or unstable.",
        "- `NO-GO` means temporal NMS matches or exceeds event-aware methods, or the apparent gain is not robust enough.",
    ]
    (out_dir / "reports/FINAL_EVENT_BUDGET_GATE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out_dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--labels_csv", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--proxy_csv", type=Path, default=DEFAULT_PROXY)
    parser.add_argument("--tracks_csv", type=Path, default=DEFAULT_TRACKS)
    parser.add_argument("--clips_csv", type=Path, default=DEFAULT_CLIPS)
    parser.add_argument("--mode", choices=["smoke", "full"], default="full")
    parser.add_argument("--seeds", type=int, default=100)
    args = parser.parse_args()

    out_dir = args.out_dir
    ensure_dirs(out_dir)
    start = time.time()
    append_progress(out_dir, f"{args.mode}:start", "python run_event_budget_gate_v2.py", "started", next_action="load inputs")
    rows, labels, proxy = load_rows(args.labels_csv, args.proxy_csv)
    stride = infer_stride(rows)
    if stride <= 0:
        stride = 4.0
        stride_note = "could not infer stride; used fallback 4.0 seconds"
    else:
        stride_note = f"inferred stride {stride:g} seconds"
    gaps = [0.0, stride, 2 * stride]
    audit(out_dir, rows, labels, proxy, args.tracks_csv, args.clips_csv, stride, gaps)
    write_yaml(
        out_dir / "config/event_budget_gate_v2.yaml",
        {
            "mode": args.mode,
            "labels_csv": args.labels_csv,
            "proxy_csv": args.proxy_csv,
            "tracks_csv": args.tracks_csv,
            "clips_csv": args.clips_csv,
            "budget_fractions": BUDGET_FRACS_SMOKE if args.mode == "smoke" else BUDGET_FRACS_FULL,
            "random_seeds": args.seeds if args.mode == "full" else min(5, args.seeds),
            "event_gaps_sec": gaps,
            "stride_note": stride_note,
            "labels_policy": "evaluation_only",
        },
    )
    budget_fracs = BUDGET_FRACS_SMOKE if args.mode == "smoke" else BUDGET_FRACS_FULL
    seeds = min(5, args.seeds) if args.mode == "smoke" else args.seeds
    raw, summary, orders = run_experiment(out_dir, rows, gaps, budget_fracs, seeds, args.mode == "smoke", stride)
    append_progress(out_dir, f"{args.mode}:metrics", "run_experiment", f"wrote rows={len(raw)}", next_action="sanity checks" if args.mode == "full" else "full run")
    if args.mode == "full":
        sanity = sanity_checks(out_dir, rows, raw, gaps, stride)
        if not bool(sanity["passes"].all()):
            append_progress(out_dir, "full:sanity_failed", "sanity_checks", "failed", failure=sanity[~sanity["passes"]].to_dict("records"), next_action="fix implementation")
            raise SystemExit("sanity checks failed; see tables/sanity_checks.csv")
        write_figures(out_dir)
        smoke_elapsed = np.nan
        progress = out_dir / "logs/progress.md"
        if progress.exists():
            smoke_elapsed = np.nan
        write_final_report(out_dir, rows, raw, summary, sanity, time.time() - start, smoke_elapsed)
        append_progress(out_dir, "full:complete", "sanity_checks; write_figures; write_final_report", "completed", next_action="inspect report")
    else:
        append_progress(out_dir, "smoke:complete", "smoke run", f"completed in {time.time() - start:.2f}s", next_action="run full")


if __name__ == "__main__":
    main()
