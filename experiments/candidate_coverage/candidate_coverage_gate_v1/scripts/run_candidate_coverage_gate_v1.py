#!/usr/bin/env python3
"""Candidate coverage gate v1 for VLM-defined pseudo-events.

This experiment estimates reachable pseudo-event coverage from cheap candidate
proposal primitives. It does not optimize scheduling and does not run VLM.
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
DEFAULT_OUT = PROJECT_ROOT / "test_vlm/outputs/candidate_coverage_gate_v1"
DEFAULT_PROXY = PROJECT_ROOT / "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores.csv"
DEFAULT_PROXY_LEARNED = PROJECT_ROOT / "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores_with_learned.csv"
DEFAULT_LABELS = PROJECT_ROOT / "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv"
EVENT_DIR = PROJECT_ROOT / "test_vlm/outputs/event_budget_gate_v2/tables"
EVENT_FILES = {
    0.0: EVENT_DIR / "pseudo_events_gap_0p0.csv",
    4.0: EVENT_DIR / "pseudo_events_gap_4p0.csv",
    8.0: EVENT_DIR / "pseudo_events_gap_8p0.csv",
}

K_GRID_FULL = [5, 10, 20, 50, 100, 200, 500]
K_GRID_SMOKE = [20, 100, 500]
RANDOM_SEEDS_FULL = 100
RANDOM_SEEDS_SMOKE = 10
MAIN_METHODS = [
    "top_count",
    "temporal_nms_count",
    "top_kinematic",
    "top_ego_path",
    "rule_like_conjunction",
    "rank_fusion_proxy",
    "score_union_proxy",
]
LEARNED_METHODS = ["top_learned_logreg", "top_learned_rf"]
ALL_METHODS = ["random", *MAIN_METHODS, *LEARNED_METHODS, "cheap_union_upper_bound"]
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


def append_progress(out_dir: Path, checkpoint: str, command: str, result: str, failure: str = "", fix: str = "", next_action: str = "") -> None:
    progress = out_dir / "logs/progress.md"
    progress.parent.mkdir(parents=True, exist_ok=True)
    with progress.open("a", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    f"## {now()}",
                    f"- checkpoint: {checkpoint}",
                    f"- commands run: `{command}`",
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


def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def as_positive(value) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "positive"}


def normalize(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)
    lo, hi = float(values.min()), float(values.max())
    if hi <= lo:
        return pd.Series(np.zeros(len(values)), index=series.index)
    return (values - lo) / (hi - lo)


def reciprocal_rank_score(df: pd.DataFrame, cols: list[str], k: float = 60.0) -> pd.Series:
    score = pd.Series(np.zeros(len(df)), index=df.index, dtype=float)
    for col in cols:
        ranks = df[col].rank(method="min", ascending=False)
        score += 1.0 / (k + ranks)
    return score


def entropy(values: list[int]) -> float:
    total = sum(values)
    if total <= 0:
        return 0.0
    probs = [v / total for v in values if v > 0]
    return -sum(p * math.log(p, 2) for p in probs)


def hhi(values: list[int]) -> float:
    total = sum(values)
    if total <= 0:
        return 0.0
    return sum((v / total) ** 2 for v in values if v > 0)


def infer_stride(rows: pd.DataFrame) -> float:
    diffs: list[float] = []
    for _, group in rows.sort_values(["source_video", "start_time"]).groupby("source_video"):
        starts = group["start_time"].to_numpy(dtype=float)
        if len(starts) > 1:
            diffs.extend(np.diff(starts).round(6).tolist())
    diffs = [d for d in diffs if d > 0]
    if not diffs:
        return 4.0
    return float(pd.Series(diffs).mode().iloc[0])


def load_inputs(proxy_csv: Path, labels_csv: Path, learned_csv: Path | None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    proxy = pd.read_csv(proxy_csv)
    labels = pd.read_csv(labels_csv)
    required_proxy = {"clip_id", "video_id", "segment_id", "start_time", "end_time", "score_count", "score_kinematic"}
    required_labels = {"clip_id", "conservative_positive"}
    missing = sorted((required_proxy - set(proxy.columns)) | (required_labels - set(labels.columns)))
    if missing:
        raise SystemExit(f"missing required input columns: {missing}")

    rows = proxy.copy()
    rows["source_video"] = rows["segment_id"].astype(str)
    for col in [
        "start_time",
        "end_time",
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
    ]:
        if col not in rows.columns:
            rows[col] = 0.0
        rows[col] = rows[col].map(safe_float)
    for col in [
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
    ]:
        rows[f"{col}_norm"] = normalize(rows[col])
    rows["ego_path_score"] = (
        rows["max_ego_path_overlap_norm"]
        + rows["max_predicted_entry_norm"]
        + rows["max_lateral_toward_ego_path_norm"]
    ) / 3.0
    rows["rank_fusion_score"] = reciprocal_rank_score(
        rows,
        [
            "score_count",
            "score_kinematic",
            "max_predicted_entry",
            "max_lateral_toward_ego_path",
            "max_temporal_persistence",
        ],
    )
    rows = rows.sort_values(["source_video", "start_time", "clip_id"]).reset_index(drop=True)

    learned = None
    if learned_csv and learned_csv.exists():
        learned_raw = pd.read_csv(learned_csv)
        keep = [c for c in ["clip_id", "score_learned_logreg", "score_learned_rf"] if c in learned_raw.columns]
        if {"clip_id", "score_learned_logreg", "score_learned_rf"} <= set(keep):
            learned = rows[["clip_id"]].merge(learned_raw[keep], on="clip_id", how="left")
            learned["score_learned_logreg"] = learned["score_learned_logreg"].map(safe_float)
            learned["score_learned_rf"] = learned["score_learned_rf"].map(safe_float)
            learned = rows[["clip_id", "source_video", "start_time"]].merge(learned, on="clip_id", how="left")
    return rows, labels, learned


def runtime_selection_view(rows: pd.DataFrame) -> pd.DataFrame:
    forbidden = [c for c in rows.columns if c in LABEL_LIKE_COLUMNS or c.endswith("_label")]
    view = rows.drop(columns=forbidden, errors="ignore").copy()
    if any(c in view.columns for c in LABEL_LIKE_COLUMNS):
        raise RuntimeError("selection view contains label-like columns")
    return view


def top_by(rows: pd.DataFrame, score_col: str) -> list[str]:
    return rows.assign(_score=rows[score_col].map(safe_float)).sort_values(
        ["_score", "source_video", "start_time", "clip_id"], ascending=[False, True, True, True]
    )["clip_id"].tolist()


def temporal_nms_count(rows: pd.DataFrame, gap: float) -> list[str]:
    selected_rows = []
    selected = []
    ordered = rows.assign(_score=rows["score_count"].map(safe_float)).sort_values(
        ["_score", "source_video", "start_time", "clip_id"], ascending=[False, True, True, True]
    )
    for _, row in ordered.iterrows():
        src, st = row["source_video"], float(row["start_time"])
        if all(src != old["source_video"] or abs(st - float(old["start_time"])) > gap for old in selected_rows):
            selected.append(row["clip_id"])
            selected_rows.append(row)
    return unique_fill(selected, ordered["clip_id"].tolist())


def rule_like_conjunction(rows: pd.DataFrame) -> list[str]:
    q_kin = rows["score_kinematic"].quantile(0.75)
    q_entry = rows["max_predicted_entry"].quantile(0.75)
    q_lateral = rows["max_lateral_toward_ego_path"].quantile(0.75)
    med_stable = rows["stable_track_count"].median()
    mask = ((rows["score_kinematic"] >= q_kin) & (rows["max_predicted_entry"] >= q_entry)) | (
        (rows["max_lateral_toward_ego_path"] >= q_lateral) & (rows["stable_track_count"] >= med_stable)
    )
    candidates = rows[mask].copy()
    candidates["_score"] = candidates["score_count_norm"] + candidates["score_kinematic_norm"]
    first = candidates.sort_values(["_score", "source_video", "start_time", "clip_id"], ascending=[False, True, True, True])["clip_id"].tolist()
    return unique_fill(first, top_by(rows, "score_count"))


def rank_fusion_proxy(rows: pd.DataFrame) -> list[str]:
    return top_by(rows, "rank_fusion_score")


def score_union_proxy(rows: pd.DataFrame, k: int, nms_gap: float) -> list[str]:
    chunk = max(1, math.ceil(k / 4))
    pieces = [
        top_by(rows, "score_count")[:chunk],
        temporal_nms_count(rows, nms_gap)[:chunk],
        top_by(rows, "score_kinematic")[:chunk],
        top_by(rows, "ego_path_score")[:chunk],
    ]
    first = [cid for piece in pieces for cid in piece]
    return unique_fill(first, rank_fusion_proxy(rows))[:k]


def random_order(rows: pd.DataFrame, seed: int) -> list[str]:
    ids = rows["clip_id"].tolist()
    random.Random(seed).shuffle(ids)
    return ids


def unique_fill(first: list[str], fallback: list[str]) -> list[str]:
    out, seen = [], set()
    for cid in first + fallback:
        if cid not in seen:
            out.append(cid)
            seen.add(cid)
    return out


def proposal(rows: pd.DataFrame, method: str, k: int, nms_gap: float, seed: int = 0, learned: pd.DataFrame | None = None) -> list[str]:
    if method == "random":
        return random_order(rows, seed)[:k]
    if method == "top_count":
        return top_by(rows, "score_count")[:k]
    if method == "temporal_nms_count":
        return temporal_nms_count(rows, nms_gap)[:k]
    if method == "top_kinematic":
        return top_by(rows, "score_kinematic")[:k]
    if method == "top_ego_path":
        return top_by(rows, "ego_path_score")[:k]
    if method == "rule_like_conjunction":
        return rule_like_conjunction(rows)[:k]
    if method == "rank_fusion_proxy":
        return rank_fusion_proxy(rows)[:k]
    if method == "score_union_proxy":
        return score_union_proxy(rows, k, nms_gap)
    if method in LEARNED_METHODS:
        if learned is None:
            return top_by(rows, "score_count")[:k]
        score = "score_learned_logreg" if method == "top_learned_logreg" else "score_learned_rf"
        ordered = learned.assign(_score=learned[score].map(safe_float)).sort_values(
            ["_score", "source_video", "start_time", "clip_id"], ascending=[False, True, True, True]
        )["clip_id"].tolist()
        return unique_fill(ordered, top_by(rows, "score_count"))[:k]
    raise ValueError(f"unknown method: {method}")


def load_events() -> dict[float, pd.DataFrame]:
    events: dict[float, pd.DataFrame] = {}
    for gap, path in EVENT_FILES.items():
        if not path.exists():
            raise SystemExit(f"missing event file: {path}")
        df = pd.read_csv(path)
        required = {"event_id", "source_video", "positive_clip_ids"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise SystemExit(f"event file {path} missing columns: {missing}")
        events[gap] = df
    return events


def event_members(events: pd.DataFrame) -> tuple[dict[str, set[str]], dict[str, str], dict[str, str]]:
    eid_to_clips = {}
    clip_to_event = {}
    event_to_source = {}
    for row in events.itertuples(index=False):
        clips = {x for x in str(row.positive_clip_ids).split(";") if x}
        eid_to_clips[row.event_id] = clips
        event_to_source[row.event_id] = row.source_video
        for cid in clips:
            clip_to_event[cid] = row.event_id
    return eid_to_clips, clip_to_event, event_to_source


def source_tail_sources(event_to_source: dict[str, str]) -> set[str]:
    counts = pd.Series(list(event_to_source.values())).value_counts().sort_values(kind="stable")
    if counts.empty:
        return set()
    n_tail = max(1, math.ceil(len(counts) / 2))
    return set(counts.head(n_tail).index)


def evaluate_candidate_set(
    selected: list[str],
    rows: pd.DataFrame,
    labels: pd.DataFrame,
    events: pd.DataFrame,
    method: str,
    k_requested: int,
    event_gap: float,
    seed: int | None,
    learned_reference: bool,
) -> dict:
    selected = list(dict.fromkeys(selected))
    selected_set = set(selected)
    eid_to_clips, clip_to_event, event_to_source = event_members(events)
    positives = set(labels.loc[labels["conservative_positive"].map(as_positive), "clip_id"])
    found_events = {clip_to_event[cid] for cid in selected if cid in clip_to_event}
    event_sources = set(event_to_source.values())
    found_sources = {event_to_source[eid] for eid in found_events if eid in event_to_source}

    source_coverages = []
    for source in sorted(event_sources):
        source_events = {eid for eid, src in event_to_source.items() if src == source}
        if source_events:
            source_coverages.append(len(source_events & found_events) / len(source_events))
    tail_sources = source_tail_sources(event_to_source)
    tail_coverages = []
    for source in sorted(tail_sources):
        source_events = {eid for eid, src in event_to_source.items() if src == source}
        if source_events:
            tail_coverages.append(len(source_events & found_events) / len(source_events))

    selected_sources = rows.set_index("clip_id").loc[selected, "source_video"] if selected else pd.Series(dtype=object)
    source_counts = selected_sources.value_counts()
    top1 = int(source_counts.iloc[0]) if len(source_counts) else 0
    top3 = int(source_counts.head(3).sum()) if len(source_counts) else 0
    values = source_counts.astype(int).tolist()

    return {
        "event_gap_sec": event_gap,
        "method": method,
        "seed": "" if seed is None else seed,
        "learned_reference": learned_reference,
        "k_requested": k_requested,
        "k_actual": len(selected),
        "k_fraction": len(selected) / len(rows) if len(rows) else np.nan,
        "micro_event_coverage": len(found_events) / len(eid_to_clips) if eid_to_clips else np.nan,
        "micro_positive_clip_coverage": len(selected_set & positives) / len(positives) if positives else np.nan,
        "unique_events_found": len(found_events),
        "positive_clips_found": len(selected_set & positives),
        "macro_source_event_coverage": float(np.mean(source_coverages)) if source_coverages else np.nan,
        "tail_source_event_coverage": float(np.mean(tail_coverages)) if tail_coverages else np.nan,
        "min_source_event_coverage": float(np.min(source_coverages)) if source_coverages else np.nan,
        "candidate_positive_rate": len(selected_set & positives) / len(selected) if selected else np.nan,
        "event_source_coverage": len(found_sources) / len(event_sources) if event_sources else np.nan,
        "candidate_source_top1_share": top1 / len(selected) if selected else np.nan,
        "candidate_source_top3_share": top3 / len(selected) if selected else np.nan,
        "candidate_source_entropy": entropy(values),
        "candidate_source_hhi": hhi(values),
        "event_ids_found": ";".join(sorted(found_events)),
        "clip_ids": ";".join(selected),
    }


def run_coverage(out_dir: Path, rows: pd.DataFrame, labels: pd.DataFrame, learned: pd.DataFrame | None, smoke: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    select_rows = runtime_selection_view(rows)
    events_by_gap = load_events()
    stride = infer_stride(select_rows)
    nms_gap = 1.5 * stride
    k_grid = K_GRID_SMOKE if smoke else K_GRID_FULL
    seeds = RANDOM_SEEDS_SMOKE if smoke else RANDOM_SEEDS_FULL
    raw_rows = []
    candidate_sets: dict[tuple[float, int, str, int | None], list[str]] = {}

    for k0 in k_grid:
        k = min(k0, len(select_rows))
        for method in ["random", *MAIN_METHODS, *LEARNED_METHODS]:
            method_seeds = range(seeds) if method == "random" else [None]
            for seed in method_seeds:
                selected = proposal(select_rows, method, k, nms_gap, seed or 0, learned)
                if len(selected) != len(set(selected)):
                    raise RuntimeError(f"duplicate candidate clip for method={method}, k={k}, seed={seed}")
                if len(selected) != k:
                    raise RuntimeError(f"candidate set size mismatch for method={method}, k={k}, actual={len(selected)}")
                for gap, events in events_by_gap.items():
                    candidate_sets[(gap, k, method, seed)] = selected
                    raw_rows.append(
                        evaluate_candidate_set(
                            selected,
                            rows,
                            labels,
                            events,
                            method,
                            k0,
                            gap,
                            seed,
                            learned_reference=method in LEARNED_METHODS,
                        )
                    )

        for gap, events in events_by_gap.items():
            union_ids = []
            for method in MAIN_METHODS:
                union_ids.extend(candidate_sets[(gap, k, method, None)])
            union_ids = list(dict.fromkeys(union_ids))
            raw_rows.append(
                evaluate_candidate_set(
                    union_ids,
                    rows,
                    labels,
                    events,
                    "cheap_union_upper_bound",
                    k0,
                    gap,
                    None,
                    learned_reference=False,
                )
            )

    raw = pd.DataFrame(raw_rows)
    raw.to_csv(out_dir / ("tables/smoke_candidate_coverage_raw.csv" if smoke else "tables/candidate_coverage_raw.csv"), index=False)
    summary = summarize_coverage(raw)
    summary.to_csv(out_dir / ("tables/smoke_candidate_coverage_summary.csv" if smoke else "tables/candidate_coverage_summary.csv"), index=False)
    source = source_coverage_table(raw)
    source.to_csv(out_dir / ("tables/smoke_source_coverage_by_method_k.csv" if smoke else "tables/source_coverage_by_method_k.csv"), index=False)
    comp = complementarity_table(raw)
    comp.to_csv(out_dir / ("tables/smoke_candidate_union_complementarity.csv" if smoke else "tables/candidate_union_complementarity.csv"), index=False)
    return raw, summary, comp


def summarize_coverage(raw: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "micro_event_coverage",
        "micro_positive_clip_coverage",
        "macro_source_event_coverage",
        "tail_source_event_coverage",
        "min_source_event_coverage",
        "candidate_positive_rate",
        "event_source_coverage",
        "candidate_source_top1_share",
        "candidate_source_top3_share",
        "candidate_source_entropy",
        "candidate_source_hhi",
    ]
    rows = []
    group_cols = ["event_gap_sec", "method", "learned_reference", "k_requested", "k_actual", "k_fraction"]
    for key, group in raw.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, key))
        for metric in metrics:
            vals = pd.to_numeric(group[metric], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            row[f"{metric}_mean"] = vals.mean() if len(vals) else np.nan
            row[f"{metric}_std"] = vals.std(ddof=0) if len(vals) else np.nan
            row[f"{metric}_ci95"] = 1.96 * row[f"{metric}_std"] / math.sqrt(len(vals)) if len(vals) else np.nan
        row["repeats"] = len(group)
        rows.append(row)
    return pd.DataFrame(rows)


def source_coverage_table(raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    event_files = load_events()
    for r in raw.itertuples(index=False):
        events = event_files[float(r.event_gap_sec)]
        selected_events = set(str(r.event_ids_found).split(";")) if isinstance(r.event_ids_found, str) and r.event_ids_found else set()
        for source, group in events.groupby("source_video"):
            event_ids = set(group["event_id"])
            rows.append(
                {
                    "event_gap_sec": r.event_gap_sec,
                    "method": r.method,
                    "seed": r.seed,
                    "k_requested": r.k_requested,
                    "k_actual": r.k_actual,
                    "source_video": source,
                    "source_events": len(event_ids),
                    "source_events_found": len(event_ids & selected_events),
                    "source_event_coverage": len(event_ids & selected_events) / len(event_ids) if event_ids else np.nan,
                    "learned_reference": r.learned_reference,
                }
            )
    return pd.DataFrame(rows)


def parse_set(value: str) -> set[str]:
    if not isinstance(value, str) or not value:
        return set()
    return {x for x in value.split(";") if x}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    denom = len(a | b)
    return len(a & b) / denom if denom else 0.0


def complementarity_table(raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    det = raw[(raw["seed"].astype(str).isin(["", "nan"])) & (raw["method"].isin(MAIN_METHODS))]
    for (gap, k), group in det.groupby(["event_gap_sec", "k_requested"]):
        method_rows = {r.method: r for r in group.itertuples(index=False)}
        for i, m1 in enumerate(MAIN_METHODS):
            for m2 in MAIN_METHODS[i + 1 :]:
                if m1 not in method_rows or m2 not in method_rows:
                    continue
                r1, r2 = method_rows[m1], method_rows[m2]
                rows.append(
                    {
                        "event_gap_sec": gap,
                        "k_requested": k,
                        "kind": "pairwise",
                        "method": f"{m1}__vs__{m2}",
                        "candidate_jaccard": jaccard(parse_set(r1.clip_ids), parse_set(r2.clip_ids)),
                        "event_hit_jaccard": jaccard(parse_set(r1.event_ids_found), parse_set(r2.event_ids_found)),
                        "unique_events_contributed": "",
                    }
                )
        all_events_by_method = {m: parse_set(r.event_ids_found) for m, r in method_rows.items()}
        for method, events in all_events_by_method.items():
            others = set()
            for other, other_events in all_events_by_method.items():
                if other != method:
                    others |= other_events
            rows.append(
                {
                    "event_gap_sec": gap,
                    "k_requested": k,
                    "kind": "unique_contribution",
                    "method": method,
                    "candidate_jaccard": "",
                    "event_hit_jaccard": "",
                    "unique_events_contributed": len(events - others),
                }
            )
    return pd.DataFrame(rows)


def static_label_access_check() -> pd.DataFrame:
    functions = [
        top_by,
        temporal_nms_count,
        rule_like_conjunction,
        rank_fusion_proxy,
        score_union_proxy,
        random_order,
        proposal,
    ]
    rows = []
    for fn in functions:
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        touched = sorted((names | constants) & LABEL_LIKE_COLUMNS)
        rows.append({"function": fn.__name__, "label_like_references": ";".join(touched), "passes": not touched})
    return pd.DataFrame(rows)


def sanity_checks(out_dir: Path, rows: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    checks = []
    select_rows = runtime_selection_view(rows)
    stride = infer_stride(select_rows)
    nms_gap = 1.5 * stride
    max_k = len(select_rows)
    events = load_events()
    labels = pd.read_csv(DEFAULT_LABELS)
    full_rows = []
    for method in MAIN_METHODS:
        selected = proposal(select_rows, method, max_k, nms_gap)
        full_rows.append(evaluate_candidate_set(selected, rows, labels, events[4.0], method, max_k, 4.0, None, False))
    full_df = pd.DataFrame(full_rows)
    checks.append(
        {
            "check": "full_candidate_pool_recall_one",
            "passes": bool((full_df["micro_event_coverage"] >= 0.999).all() and (full_df["micro_positive_clip_coverage"] >= 0.999).all()),
            "detail": f"min_event={full_df['micro_event_coverage'].min():.6f}; min_clip={full_df['micro_positive_clip_coverage'].min():.6f}",
        }
    )
    event_counts = [len(events[gap]) for gap in sorted(events)]
    checks.append(
        {
            "check": "event_count_nonincreasing_with_gap",
            "passes": all(event_counts[i] >= event_counts[i + 1] for i in range(len(event_counts) - 1)),
            "detail": f"counts={event_counts}",
        }
    )
    checks.append(
        {
            "check": "temporal_nms_no_suppression_matches_top_count",
            "passes": temporal_nms_count(select_rows, gap=-1.0) == top_by(select_rows, "score_count"),
            "detail": "gap=-1 disables suppression",
        }
    )
    size_failures = []
    for row in raw.itertuples(index=False):
        if row.method == "cheap_union_upper_bound":
            continue
        if int(row.k_actual) != min(int(row.k_requested), len(select_rows)):
            size_failures.append((row.method, row.k_requested, row.k_actual))
    checks.append(
        {
            "check": "candidate_sets_unique_and_match_k",
            "passes": not size_failures,
            "detail": f"failures={size_failures[:5]}",
        }
    )
    union_failures = []
    for (gap, k), group in raw.groupby(["event_gap_sec", "k_requested"]):
        union = group[group["method"].eq("cheap_union_upper_bound")]
        if union.empty:
            continue
        union_cov = float(union.iloc[0]["micro_event_coverage"])
        for method in MAIN_METHODS:
            sub = group[group["method"].eq(method)]
            if not sub.empty and union_cov + 1e-12 < float(sub.iloc[0]["micro_event_coverage"]):
                union_failures.append((gap, k, method))
    checks.append(
        {
            "check": "union_coverage_not_below_components",
            "passes": not union_failures,
            "detail": f"failures={union_failures[:5]}",
        }
    )
    static = static_label_access_check()
    static.to_csv(out_dir / "tables/static_label_access_check.csv", index=False)
    checks.append(
        {
            "check": "static_candidate_functions_do_not_reference_labels",
            "passes": bool(static["passes"].all()),
            "detail": "; ".join(f"{r.function}:{r.label_like_references or 'none'}" for r in static.itertuples()),
        }
    )
    checks.append(
        {
            "check": "runtime_selection_view_has_no_label_columns",
            "passes": not any(c in runtime_selection_view(rows).columns for c in LABEL_LIKE_COLUMNS),
            "detail": "selection view checked",
        }
    )
    learned_main = raw[(raw["learned_reference"].eq(True)) & (raw["method"].isin(LEARNED_METHODS))]
    checks.append(
        {
            "check": "learned_methods_marked_reference_only",
            "passes": bool(not learned_main.empty and learned_main["learned_reference"].all()),
            "detail": "learned scores were trained from pseudo-labels; excluded from decision",
        }
    )
    out = pd.DataFrame(checks)
    out.to_csv(out_dir / "tables/sanity_checks.csv", index=False)
    return out


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


def write_audit(out_dir: Path, rows: pd.DataFrame, labels: pd.DataFrame, learned: pd.DataFrame | None, smoke: bool) -> None:
    events = load_events()
    positives = int(labels["conservative_positive"].map(as_positive).sum())
    input_rows = [
        {"role": "main_proxy_scores", "path": str(DEFAULT_PROXY), "exists": DEFAULT_PROXY.exists(), "rows": len(rows)},
        {"role": "conservative_vlm_labels", "path": str(DEFAULT_LABELS), "exists": DEFAULT_LABELS.exists(), "rows": len(labels)},
        {"role": "learned_scores_reference", "path": str(DEFAULT_PROXY_LEARNED), "exists": DEFAULT_PROXY_LEARNED.exists(), "rows": len(learned) if learned is not None else ""},
    ]
    for gap, path in EVENT_FILES.items():
        input_rows.append({"role": f"pseudo_events_gap_{gap:g}", "path": str(path), "exists": path.exists(), "rows": len(events[gap])})
    pd.DataFrame(input_rows).to_csv(out_dir / "data_manifest/input_files.tsv", sep="\t", index=False)
    write_yaml(
        out_dir / "config/schema_mapping.yaml",
        {
            "clip_id": "clip_id",
            "source_video": "segment_id",
            "start_time": "start_time",
            "end_time": "end_time",
            "pseudo_oracle_label": "conservative_positive (evaluation only)",
            "main_scores": ["score_count", "score_naive", "score_kinematic", "ego_path_score", "rank_fusion_score"],
            "learned_scores": "reference only, excluded from decision",
        },
    )
    write_yaml(
        out_dir / "config/candidate_coverage_gate_v1.yaml",
        {
            "mode": "smoke" if smoke else "full",
            "k_grid": K_GRID_SMOKE if smoke else K_GRID_FULL,
            "random_seeds": RANDOM_SEEDS_SMOKE if smoke else RANDOM_SEEDS_FULL,
            "event_gaps_sec": sorted(events),
            "temporal_nms_gap_sec": 1.5 * infer_stride(rows),
            "labels_policy": "evaluation_only",
            "learned_policy": "development_reference_only",
        },
    )
    lines = [
        "# Candidate Coverage Gate V1 Asset Audit",
        "",
        "This audit is for a cheap candidate proposal coverage experiment over VLM-defined pseudo-events. It is not a human-ground-truth benchmark.",
        "",
        "## Inputs",
        "",
        f"- main proxy CSV: `{DEFAULT_PROXY}` rows={len(rows)}",
        f"- conservative labels CSV: `{DEFAULT_LABELS}` rows={len(labels)} positives={positives}",
        f"- learned score CSV: `{DEFAULT_PROXY_LEARNED}` reference_only={learned is not None}",
        f"- event files: `{EVENT_DIR}` gaps={sorted(events)}",
        "",
        "## Candidate Construction Fields",
        "",
        "- `top_count`: `score_count`",
        "- `temporal_nms_count`: `score_count`, `source_video`, `start_time`",
        "- `top_kinematic`: `score_kinematic`",
        "- `top_ego_path`: normalized `max_ego_path_overlap`, `max_predicted_entry`, `max_lateral_toward_ego_path`",
        "- `rule_like_conjunction`: quantiles of `score_kinematic`, `max_predicted_entry`, `max_lateral_toward_ego_path`, `stable_track_count`",
        "- `rank_fusion_proxy`: reciprocal rank fusion over count, kinematic, predicted-entry, lateral, persistence",
        "- `score_union_proxy`: union of count, temporal NMS, kinematic, and ego-path candidate lists",
        "",
        "## Data Shape",
        "",
        f"- clips: {len(rows)}",
        f"- source videos/groups: {rows['source_video'].nunique()}",
        f"- inferred stride seconds: {infer_stride(rows):g}",
        f"- proxy columns: `{list(rows.columns)}`",
        "",
        "## Leakage Risk",
        "",
        "- Main methods read `proxy_scores.csv`, which does not include conservative labels.",
        "- Conservative labels and pseudo-events are used only for evaluation.",
        "- Learned scores are loaded only as reference methods because they were previously trained from conservative pseudo-labels with GroupKFold.",
    ]
    (out_dir / "reports/00_asset_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_figures(out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    summary = pd.read_csv(out_dir / "tables/candidate_coverage_summary.csv")
    comp = pd.read_csv(out_dir / "tables/candidate_union_complementarity.csv")
    primary_gap = 4.0
    methods = ["top_count", "temporal_nms_count", "top_kinematic", "top_ego_path", "rule_like_conjunction", "rank_fusion_proxy", "score_union_proxy", "cheap_union_upper_bound", "random"]

    def plot_metric(metric: str, ylabel: str, filename: str) -> None:
        fig, ax = plt.subplots(figsize=(10, 6))
        for method in methods:
            sub = summary[(summary["event_gap_sec"].eq(primary_gap)) & (summary["method"].eq(method))].sort_values("k_requested")
            if sub.empty:
                continue
            y = sub[f"{metric}_mean"]
            ax.plot(sub["k_requested"], y, marker="o", label=method)
            if method == "random":
                ci = sub[f"{metric}_ci95"]
                ax.fill_between(sub["k_requested"], y - ci, y + ci, alpha=0.18)
        ax.set_xlabel("Candidate pool size K")
        ax.set_ylabel(ylabel)
        ax.set_xscale("log")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        fig.savefig(out_dir / f"figures/{filename}")
        plt.close(fig)

    plot_metric("micro_event_coverage", "Micro pseudo-event coverage", "micro_event_coverage_vs_k.pdf")
    plot_metric("macro_source_event_coverage", "Macro source-video event coverage", "macro_source_coverage_vs_k.pdf")
    plot_metric("tail_source_event_coverage", "Tail-source event coverage", "tail_source_coverage_vs_k.pdf")

    fig, ax = plt.subplots(figsize=(10, 6))
    for method in methods:
        sub = summary[(summary["event_gap_sec"].eq(primary_gap)) & (summary["method"].eq(method))].sort_values("k_requested")
        if sub.empty:
            continue
        ax.plot(sub["k_requested"], sub["candidate_source_hhi_mean"], marker="o", label=method)
    ax.set_xlabel("Candidate pool size K")
    ax.set_ylabel("Candidate source HHI")
    ax.set_xscale("log")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "figures/source_concentration_vs_k.pdf")
    plt.close(fig)

    pairwise = comp[(comp["kind"].eq("pairwise")) & (comp["event_gap_sec"].eq(primary_gap)) & (comp["k_requested"].isin([50, 100, 200]))].copy()
    fig, ax = plt.subplots(figsize=(10, 6))
    if not pairwise.empty:
        pairwise["event_hit_jaccard"] = pd.to_numeric(pairwise["event_hit_jaccard"], errors="coerce")
        means = pairwise.groupby("k_requested")["event_hit_jaccard"].mean()
        ax.bar([str(k) for k in means.index], means.values)
    ax.set_xlabel("K")
    ax.set_ylabel("Mean pairwise event-hit Jaccard")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(out_dir / "figures/candidate_union_complementarity.pdf")
    plt.close(fig)


def markdown_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in df.itertuples(index=False):
        values = []
        for value in row:
            if isinstance(value, float):
                values.append(f"{value:.3f}")
            else:
                values.append(str(value).replace("|", "/"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def decide(summary: pd.DataFrame) -> tuple[str, list[str]]:
    reasons = []
    nonlearned = [m for m in MAIN_METHODS if m != "top_count"]
    wins = 0
    points = 0
    union_complements = 0
    for gap in sorted(summary["event_gap_sec"].unique()):
        for k in [50, 100, 200]:
            group = summary[(summary["event_gap_sec"].eq(gap)) & (summary["k_requested"].eq(k))]
            if group.empty:
                continue
            top_count = group[group["method"].eq("top_count")]
            temporal = group[group["method"].eq("temporal_nms_count")]
            union = group[group["method"].eq("cheap_union_upper_bound")]
            proposals = group[group["method"].isin(nonlearned)]
            if top_count.empty or temporal.empty or union.empty or proposals.empty:
                continue
            best = proposals.sort_values("micro_event_coverage_mean", ascending=False).iloc[0]
            top = top_count.iloc[0]
            temp = temporal.iloc[0]
            uni = union.iloc[0]
            top_delta = float(best["micro_event_coverage_mean"]) - float(top["micro_event_coverage_mean"])
            macro_delta = float(best["macro_source_event_coverage_mean"]) - float(top["macro_source_event_coverage_mean"])
            tail_delta = float(best["tail_source_event_coverage_mean"]) - float(top["tail_source_event_coverage_mean"])
            union_delta = float(uni["micro_event_coverage_mean"]) - max(float(top["micro_event_coverage_mean"]), float(temp["micro_event_coverage_mean"]))
            points += 1
            wins += int(top_delta >= 0.05 and (macro_delta > 0 or tail_delta > 0))
            union_complements += int(union_delta >= 0.05)
            reasons.append(
                f"gap={gap:g}, K={k}: best={best['method']} top_delta={top_delta:.3f}, macro_delta={macro_delta:.3f}, tail_delta={tail_delta:.3f}, union_delta_vs_best_count_or_nms={union_delta:.3f}"
            )
    if points and wins >= max(3, math.ceil(points * 0.5)) and union_complements >= max(2, math.ceil(points * 0.33)):
        return "GO", reasons
    if wins > 0 or union_complements > 0:
        return "WEAK GO", reasons
    return "NO-GO", reasons


def write_report(out_dir: Path, rows: pd.DataFrame, labels: pd.DataFrame, sanity: pd.DataFrame, elapsed: float) -> str:
    summary = pd.read_csv(out_dir / "tables/candidate_coverage_summary.csv")
    decision, reasons = decide(summary)
    primary = summary[
        (summary["event_gap_sec"].eq(4.0))
        & (summary["k_requested"].isin([50, 100, 200]))
        & (summary["method"].isin(["top_count", "temporal_nms_count", "top_kinematic", "top_ego_path", "rule_like_conjunction", "rank_fusion_proxy", "score_union_proxy", "cheap_union_upper_bound", "random"]))
    ].copy()
    keep = [
        "method",
        "k_requested",
        "k_actual",
        "micro_event_coverage_mean",
        "macro_source_event_coverage_mean",
        "tail_source_event_coverage_mean",
        "candidate_source_hhi_mean",
    ]
    primary = primary[keep].sort_values(["k_requested", "method"])
    sanity_table = sanity[["check", "passes", "detail"]].copy()
    positives = int(labels["conservative_positive"].map(as_positive).sum())
    lines = [
        "# Candidate Coverage Gate V1 Report",
        "",
        "This is a VLM-defined pseudo-event development experiment. Conservative VLM labels are used only for evaluation.",
        "",
        "## Inputs",
        "",
        f"- clips: {len(rows)}",
        f"- conservative VLM positives: {positives}",
        f"- source video groups: {rows['source_video'].nunique()}",
        f"- full runtime seconds: {elapsed:.2f}",
        f"- K grid: {K_GRID_FULL}",
        f"- random seeds: {RANDOM_SEEDS_FULL}",
        "",
        "## Primary Gap 4s Results",
        "",
        markdown_table(primary),
        "",
        "## Sanity Checks",
        "",
        markdown_table(sanity_table),
        "",
        "## Interpretation",
        "",
        "- Main candidate construction uses only `proxy_scores.csv` and source/time metadata.",
        "- Learned proxy rows are reference-only because the existing learned scores were trained from conservative pseudo-labels.",
        "- Micro coverage measures event reachability; macro and tail coverage diagnose source-video concentration.",
        "- `cheap_union_upper_bound` is the union of non-learned proposal primitives and estimates reachable coverage from the current cheap family.",
        "",
        "## Decision Evidence",
        "",
        *[f"- {reason}" for reason in reasons],
        "",
        f"## Decision: {decision}",
        "",
        "- `GO`: strong non-learned coverage gains over `top_count`, better macro/tail coverage, and complementary union coverage at practical K.",
        "- `WEAK GO`: gains exist but are source-concentrated, gap-sensitive, or require large K.",
        "- `NO-GO`: `top_count`/`temporal_nms_count` already matches the cheap union or tail coverage remains poor.",
        "",
        "This decision is pseudo-oracle development evidence only; it is not evidence of true risk-event ground-truth recovery.",
    ]
    (out_dir / "reports/FINAL_CANDIDATE_COVERAGE_GATE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out_dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--proxy_csv", type=Path, default=DEFAULT_PROXY)
    parser.add_argument("--labels_csv", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--learned_csv", type=Path, default=DEFAULT_PROXY_LEARNED)
    parser.add_argument("--mode", choices=["smoke", "full"], default="full")
    args = parser.parse_args()

    start = time.time()
    ensure_dirs(args.out_dir)
    append_progress(args.out_dir, f"{args.mode}:start", "python run_candidate_coverage_gate_v1.py", "started", next_action="load inputs")
    rows, labels, learned = load_inputs(args.proxy_csv, args.labels_csv, args.learned_csv)
    write_audit(args.out_dir, rows, labels, learned, smoke=args.mode == "smoke")
    raw, summary, comp = run_coverage(args.out_dir, rows, labels, learned, smoke=args.mode == "smoke")
    append_progress(args.out_dir, f"{args.mode}:coverage", "run_coverage", f"raw_rows={len(raw)}", next_action="sanity checks")
    if args.mode == "full":
        sanity = sanity_checks(args.out_dir, rows, raw)
        if not bool(sanity["passes"].all()):
            append_progress(args.out_dir, "full:sanity_failed", "sanity_checks", "failed", failure=sanity[~sanity["passes"]].to_dict("records"), next_action="fix implementation")
            raise SystemExit("sanity checks failed; see tables/sanity_checks.csv")
        write_figures(args.out_dir)
        decision = write_report(args.out_dir, rows, labels, sanity, time.time() - start)
        append_progress(args.out_dir, "full:complete", "sanity_checks; write_figures; write_report", f"completed decision={decision}", next_action="inspect outputs")
    else:
        append_progress(args.out_dir, "smoke:complete", "smoke run", f"completed in {time.time() - start:.2f}s", next_action="run full")


if __name__ == "__main__":
    main()
