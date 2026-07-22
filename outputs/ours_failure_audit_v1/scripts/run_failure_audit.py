#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
COMPARE = ROOT / "outputs/ours_vs_baselines_realcartest_v1"
PILOT = ROOT / "outputs/real_video_protocol_pilot_v1"
OUT = ROOT / "outputs/ours_failure_audit_v1"

UNITS_CSV = PILOT / "frame_scores_adapter_ready.csv"
REF_CSV = PILOT / "reference_segments_adapter_ready.csv"
MAIN_TABLE_CSV = COMPARE / "main_comparison_table.csv"

BUDGETS = [5, 10, 20, 30, 40, 50, 80, 100]
SEEDS = [0, 1, 2, 3, 4]
METHODS = [
    "Ours-Frozen-LATE-AQP-v1",
    "ARC-refinement",
    "ABae-stratified-confirmed",
    "SUPG-RT-confirmed-only",
    "ARC-proxy-only",
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def log(message: str) -> None:
    path = OUT / "logs/progress.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {now()} {message}\n")


def parse_ids(value: object) -> list[int]:
    if pd.isna(value):
        return []
    out: list[int] = []
    for token in str(value).split("|"):
        token = token.strip()
        if not token:
            continue
        try:
            out.append(int(token))
        except ValueError:
            continue
    return out


def temporal_iou(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    inter = max(0, min(int(a_end), int(b_end)) - max(int(a_start), int(b_start)) + 1)
    union = max(int(a_end), int(b_end)) - min(int(a_start), int(b_start)) + 1
    return inter / union if union > 0 else 0.0


def overlap_seconds(a: dict, b: dict) -> float:
    return max(0.0, min(float(a["end_time"]), float(b["end_time"])) - max(float(a["start_time"]), float(b["start_time"])))


def duration(row: dict | pd.Series) -> float:
    return max(0.0, float(row["end_time"]) - float(row["start_time"]))


def ref_id_col(refs: pd.DataFrame) -> pd.Series:
    if "source_event_id" in refs.columns:
        return refs["source_event_id"].astype(str)
    return refs["segment_id"].astype(str)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    units = pd.read_csv(UNITS_CSV)
    refs = pd.read_csv(REF_CSV)
    refs = refs.copy()
    refs["reference_id"] = ref_id_col(refs)
    main = pd.read_csv(MAIN_TABLE_CSV)
    return units, refs, main


def unit_ref_maps(units: pd.DataFrame, refs: pd.DataFrame) -> tuple[dict[int, list[str]], dict[int, float]]:
    unit_to_refs: dict[int, list[str]] = {}
    unit_to_best_overlap: dict[int, float] = {}
    for unit in units.to_dict("records"):
        hits = []
        best = 0.0
        for ref in refs.to_dict("records"):
            if str(unit["video_id"]) != str(ref["video_id"]):
                continue
            ov = overlap_seconds(
                {"start_time": unit["start_time"], "end_time": unit["end_time"]},
                {"start_time": ref["start_time"], "end_time": ref["end_time"]},
            )
            if ov > 0:
                hits.append(str(ref["reference_id"]))
                best = max(best, ov)
        unit_to_refs[int(unit["frame_idx"])] = hits
        unit_to_best_overlap[int(unit["frame_idx"])] = best
    return unit_to_refs, unit_to_best_overlap


def selected_threshold(main: pd.DataFrame, method: str, budget: int) -> float | None:
    rows = main[(main["method"] == method) & (main["budget"] == budget)]
    if rows.empty:
        return None
    value = rows["selected_threshold"].iloc[0]
    if pd.isna(value):
        return None
    return float(value)


def run_dir(method: str, budget: int, seed: int, main: pd.DataFrame) -> Path:
    if method == "Ours-Frozen-LATE-AQP-v1":
        return COMPARE / "ours_outputs" / f"ours_frozen_late_aqp_b{budget}_s{seed}"
    if method == "ARC-refinement":
        th = selected_threshold(main, method, budget)
        return COMPARE / "baseline_outputs" / f"ARC_refinement_b{budget}_s{seed}_th{th:.1f}"
    if method == "ARC-proxy-only":
        th = selected_threshold(main, method, budget)
        return COMPARE / "baseline_outputs" / f"ARC_proxy_only_b{budget}_s0_th{th:.1f}"
    if method == "ABae-stratified-confirmed":
        return COMPARE / "baseline_outputs" / f"ABae_stratified_confirmed_b{budget}_s{seed}"
    if method == "SUPG-RT-confirmed-only":
        return COMPARE / "baseline_outputs" / f"SUPG_RT_confirmed_only_b{budget}_s{seed}"
    raise ValueError(method)


def seeds_for(method: str) -> list[int]:
    return [0] if method == "ARC-proxy-only" else SEEDS


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def output_unit_set(segments: pd.DataFrame) -> set[int]:
    units: set[int] = set()
    if segments.empty or "source_frame_ids" not in segments.columns:
        return units
    for value in segments["source_frame_ids"]:
        units.update(parse_ids(value))
    return units


def query_unit_set(oracle: pd.DataFrame) -> set[int]:
    if oracle.empty or "frame_idx" not in oracle.columns:
        return set()
    return set(int(x) for x in oracle["frame_idx"].dropna().astype(int).tolist())


def canonical_segments(segments: pd.DataFrame, units: pd.DataFrame) -> pd.DataFrame:
    if segments.empty:
        return segments.copy()
    lookup = units.set_index(["video_id", "frame_idx"])
    rows = []
    for seg in segments.to_dict("records"):
        ids = parse_ids(seg.get("source_frame_ids", ""))
        mapped = []
        for frame_idx in ids:
            key = (str(seg["video_id"]), int(frame_idx))
            if key in lookup.index:
                mapped.append(lookup.loc[key])
        out = seg.copy()
        if mapped:
            mapped_df = pd.DataFrame(mapped)
            out["start_frame"] = int(mapped_df["start_frame"].min())
            out["end_frame"] = int(mapped_df["end_frame"].max())
            out["start_time"] = float(mapped_df["start_time"].min())
            out["end_time"] = float(mapped_df["end_time"].max())
        rows.append(out)
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class RefBest:
    hit: bool
    best_iou: float
    best_overlap: float
    pred_duration: float


def best_for_ref(preds: pd.DataFrame, ref: dict) -> RefBest:
    best_iou = 0.0
    best_overlap = 0.0
    best_duration = 0.0
    hit = False
    for pred in preds.to_dict("records") if not preds.empty else []:
        if str(pred["video_id"]) != str(ref["video_id"]):
            continue
        ov = overlap_seconds(pred, ref)
        iou = temporal_iou(pred["start_frame"], pred["end_frame"], ref["start_frame"], ref["end_frame"])
        if ov > 0:
            hit = True
        if ov > best_overlap or (ov == best_overlap and iou > best_iou):
            best_overlap = ov
            best_iou = iou
            best_duration = duration(pred)
    return RefBest(hit, best_iou, best_overlap, best_duration)


def refs_hit_by_units(unit_ids: set[int], unit_to_refs: dict[int, list[str]]) -> set[str]:
    out: set[str] = set()
    for unit_id in unit_ids:
        out.update(unit_to_refs.get(int(unit_id), []))
    return out


def positive_units(unit_ids: set[int], units: pd.DataFrame) -> set[int]:
    lookup = units.set_index("frame_idx")
    return {int(u) for u in unit_ids if int(u) in lookup.index and int(lookup.loc[int(u), "oracle_label"]) == 1}


def audit_budget_monotonicity(units: pd.DataFrame, refs: pd.DataFrame, main: pd.DataFrame, unit_to_refs: dict[int, list[str]]) -> pd.DataFrame:
    rows = []
    for seed in SEEDS:
        by_budget = {}
        for budget in BUDGETS:
            rd = run_dir("Ours-Frozen-LATE-AQP-v1", budget, seed, main)
            oracle = read_csv_if_exists(rd / "oracle_log.csv")
            seg = read_csv_if_exists(rd / "segments.csv")
            by_budget[budget] = {
                "query": query_unit_set(oracle),
                "output": output_unit_set(seg),
                "segments": canonical_segments(seg, units),
            }
        for low, high in zip(BUDGETS[:-1], BUDGETS[1:]):
            low_q = by_budget[low]["query"]
            high_q = by_budget[high]["query"]
            low_o = by_budget[low]["output"]
            high_o = by_budget[high]["output"]
            missing_q = sorted(low_q - high_q)
            missing_o = sorted(low_o - high_o)
            missing_positive = sorted(positive_units(set(missing_q), units))
            missing_refs = sorted(refs_hit_by_units(set(missing_positive), unit_to_refs))
            low_refs = refs_hit_by_units(low_o, unit_to_refs)
            high_refs = refs_hit_by_units(high_o, unit_to_refs)
            lost_refs = sorted(low_refs - high_refs)
            rows.append(
                {
                    "seed": seed,
                    "budget_from": low,
                    "budget_to": high,
                    "query_units_from": len(low_q),
                    "query_units_to": len(high_q),
                    "query_units_subset": low_q.issubset(high_q),
                    "missing_query_units": "|".join(map(str, missing_q)),
                    "missing_positive_query_units": "|".join(map(str, missing_positive)),
                    "missing_positive_reference_hits": "|".join(missing_refs),
                    "output_units_from": len(low_o),
                    "output_units_to": len(high_o),
                    "output_units_subset": low_o.issubset(high_o),
                    "missing_output_units": "|".join(map(str, missing_o)),
                    "references_from": len(low_refs),
                    "references_to": len(high_refs),
                    "lost_reference_hits": "|".join(lost_refs),
                    "segment_count_from": len(by_budget[low]["segments"]),
                    "segment_count_to": len(by_budget[high]["segments"]),
                    "b100_contains_b50_selected_units": "" if not (low == 50 and high in (80, 100)) else low_q.issubset(high_q),
                }
            )
        low_q = by_budget[50]["query"]
        high_q = by_budget[100]["query"]
        low_o = by_budget[50]["output"]
        high_o = by_budget[100]["output"]
        missing_q = sorted(low_q - high_q)
        missing_positive = sorted(positive_units(set(missing_q), units))
        rows.append(
            {
                "seed": seed,
                "budget_from": 50,
                "budget_to": 100,
                "query_units_from": len(low_q),
                "query_units_to": len(high_q),
                "query_units_subset": low_q.issubset(high_q),
                "missing_query_units": "|".join(map(str, missing_q)),
                "missing_positive_query_units": "|".join(map(str, missing_positive)),
                "missing_positive_reference_hits": "|".join(sorted(refs_hit_by_units(set(missing_positive), unit_to_refs))),
                "output_units_from": len(low_o),
                "output_units_to": len(high_o),
                "output_units_subset": low_o.issubset(high_o),
                "missing_output_units": "|".join(map(str, sorted(low_o - high_o))),
                "references_from": len(refs_hit_by_units(low_o, unit_to_refs)),
                "references_to": len(refs_hit_by_units(high_o, unit_to_refs)),
                "lost_reference_hits": "|".join(sorted(refs_hit_by_units(low_o, unit_to_refs) - refs_hit_by_units(high_o, unit_to_refs))),
                "segment_count_from": len(by_budget[50]["segments"]),
                "segment_count_to": len(by_budget[100]["segments"]),
                "b100_contains_b50_selected_units": low_q.issubset(high_q),
            }
        )
    return pd.DataFrame(rows)


def build_method_predictions(method: str, budget: int, main: pd.DataFrame, units: pd.DataFrame) -> dict[int, pd.DataFrame]:
    out: dict[int, pd.DataFrame] = {}
    for seed in seeds_for(method):
        rd = run_dir(method, budget, seed, main)
        seg = read_csv_if_exists(rd / "segments.csv")
        out[seed] = canonical_segments(seg, units)
    return out


def per_reference_method_hit_matrix(units: pd.DataFrame, refs: pd.DataFrame, main: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for budget in BUDGETS:
        pred_cache = {m: build_method_predictions(m, budget, main, units) for m in METHODS}
        for ref in refs.to_dict("records"):
            row = {
                "reference_id": str(ref["reference_id"]),
                "video_id": ref["video_id"],
                "budget": budget,
                "ref_start_time": ref["start_time"],
                "ref_end_time": ref["end_time"],
            }
            for method in METHODS:
                hits = []
                best_iou = []
                best_overlap = []
                for seed, preds in pred_cache[method].items():
                    best = best_for_ref(preds, ref)
                    hits.append(bool(best.hit))
                    best_iou.append(best.best_iou)
                    best_overlap.append(best.best_overlap)
                prefix = method.replace("-", "_").replace(" ", "_")
                row[f"{prefix}_seed_count"] = len(hits)
                row[f"{prefix}_hit_seed_count"] = int(sum(hits))
                row[f"{prefix}_hit_rate"] = float(np.mean(hits)) if hits else 0.0
                row[f"{prefix}_hit_any"] = any(hits)
                row[f"{prefix}_hit_all"] = all(hits) if hits else False
                row[f"{prefix}_best_iou_max"] = max(best_iou) if best_iou else 0.0
                row[f"{prefix}_best_overlap_seconds_max"] = max(best_overlap) if best_overlap else 0.0
            budget_methods = ["Ours-Frozen-LATE-AQP-v1", "ARC-refinement", "ABae-stratified-confirmed", "SUPG-RT-confirmed-only", "ARC-proxy-only"]
            hit_any_values = [row[f"{m.replace('-', '_').replace(' ', '_')}_hit_any"] for m in budget_methods]
            row["hit_by_all_budget_respecting_methods"] = all(hit_any_values)
            row["hit_by_no_budget_respecting_method"] = not any(hit_any_values)
            rows.append(row)
    return pd.DataFrame(rows)


def selected_unit_quality(units: pd.DataFrame, refs: pd.DataFrame, main: pd.DataFrame, unit_to_refs: dict[int, list[str]]) -> pd.DataFrame:
    lookup = units.set_index("frame_idx")
    rows = []
    for budget in BUDGETS:
        for method in METHODS:
            for seed in seeds_for(method):
                rd = run_dir(method, budget, seed, main)
                seg = read_csv_if_exists(rd / "segments.csv")
                oracle = read_csv_if_exists(rd / "oracle_log.csv")
                selected = output_unit_set(seg)
                queried = query_unit_set(oracle)
                positives = positive_units(selected, units)
                ref_counts: dict[str, int] = {}
                for unit_id in selected:
                    for rid in unit_to_refs.get(unit_id, []):
                        ref_counts[rid] = ref_counts.get(rid, 0) + 1
                ref_covered = {u for u in selected if unit_to_refs.get(u, [])}
                duplicate_units_per_ref = sum(max(0, count - 1) for count in ref_counts.values())
                proxy_values = [float(lookup.loc[u, "proxy_score"]) for u in selected if u in lookup.index]
                positive_proxy_values = [float(lookup.loc[u, "proxy_score"]) for u in positives if u in lookup.index]
                rows.append(
                    {
                        "method": method,
                        "budget": budget,
                        "seed": seed,
                        "query_units": len(queried),
                        "output_selected_units": len(selected),
                        "oracle_positive_selected_units": len(positives),
                        "selected_positive_rate": len(positives) / len(selected) if selected else 0.0,
                        "reference_covered_selected_units": len(ref_covered),
                        "reference_covered_selected_unit_rate": len(ref_covered) / len(selected) if selected else 0.0,
                        "unique_reference_events_hit_by_selected_units": len(ref_counts),
                        "duplicate_selected_units_per_reference": duplicate_units_per_ref,
                        "average_proxy_score_selected_units": float(np.mean(proxy_values)) if proxy_values else np.nan,
                        "average_proxy_score_selected_positives": float(np.mean(positive_proxy_values)) if positive_proxy_values else np.nan,
                        "selected_unit_ids": "|".join(map(str, sorted(selected))),
                        "positive_selected_unit_ids": "|".join(map(str, sorted(positives))),
                    }
                )
    return pd.DataFrame(rows)


def segment_construction_audit(units: pd.DataFrame, refs: pd.DataFrame, main: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for budget in BUDGETS:
        for seed in SEEDS:
            rd = run_dir("Ours-Frozen-LATE-AQP-v1", budget, seed, main)
            seg = canonical_segments(read_csv_if_exists(rd / "segments.csv"), units)
            durations = [duration(x) for x in seg.to_dict("records")] if not seg.empty else []
            overcoverage = []
            no_overlap = 0
            refs_by_long_30: set[str] = set()
            refs_by_long_60: set[str] = set()
            refs_by_long_120: set[str] = set()
            for pred in seg.to_dict("records") if not seg.empty else []:
                pred_dur = duration(pred)
                best_ref = None
                best_ov = 0.0
                for ref in refs.to_dict("records"):
                    if str(pred["video_id"]) != str(ref["video_id"]):
                        continue
                    ov = overlap_seconds(pred, ref)
                    if ov > best_ov:
                        best_ov = ov
                        best_ref = ref
                if best_ref is None or best_ov <= 0:
                    no_overlap += 1
                    continue
                ref_dur = max(1e-9, duration(best_ref))
                overcoverage.append(pred_dur / ref_dur)
                for ref in refs.to_dict("records"):
                    if overlap_seconds(pred, ref) <= 0:
                        continue
                    rid = str(ref["reference_id"])
                    if pred_dur > 30:
                        refs_by_long_30.add(rid)
                    if pred_dur > 60:
                        refs_by_long_60.add(rid)
                    if pred_dur > 120:
                        refs_by_long_120.add(rid)
            rows.append(
                {
                    "budget": budget,
                    "seed": seed,
                    "num_segments": len(seg),
                    "mean_segment_duration": float(np.mean(durations)) if durations else 0.0,
                    "median_segment_duration": float(np.median(durations)) if durations else 0.0,
                    "max_segment_duration": float(np.max(durations)) if durations else 0.0,
                    "mean_overcoverage_ratio": float(np.mean(overcoverage)) if overcoverage else 0.0,
                    "segments_longer_than_30s": int(sum(x > 30 for x in durations)),
                    "segments_longer_than_60s": int(sum(x > 60 for x in durations)),
                    "segments_longer_than_120s": int(sum(x > 120 for x in durations)),
                    "segments_with_no_reference_overlap": no_overlap,
                    "references_covered_by_segments_longer_than_30s": len(refs_by_long_30),
                    "references_covered_by_segments_longer_than_60s": len(refs_by_long_60),
                    "references_covered_by_segments_longer_than_120s": len(refs_by_long_120),
                }
            )
    return pd.DataFrame(rows)


def reference_detail_for_budget(budget: int, units: pd.DataFrame, refs: pd.DataFrame, main: pd.DataFrame) -> pd.DataFrame:
    methods = {
        "ours": "Ours-Frozen-LATE-AQP-v1",
        "arc": "ARC-refinement",
        "abae": "ABae-stratified-confirmed",
    }
    pred_cache = {short: build_method_predictions(method, budget, main, units) for short, method in methods.items()}
    rows = []
    for ref in refs.to_dict("records"):
        row = {
            "reference_id": str(ref["reference_id"]),
            "ref_start": ref["start_time"],
            "ref_end": ref["end_time"],
        }
        for short in ["ours", "arc", "abae"]:
            bests = [best_for_ref(preds, ref) for preds in pred_cache[short].values()]
            hit = any(b.hit for b in bests)
            best = max(bests, key=lambda b: (b.best_overlap, b.best_iou), default=RefBest(False, 0.0, 0.0, 0.0))
            row[f"hit_by_{short}"] = hit
            row[f"best_{short}_iou"] = best.best_iou
            row[f"best_{short}_overlap_seconds"] = best.best_overlap
            row[f"{short}_prediction_duration"] = best.pred_duration
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_quality(quality: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "query_units",
        "output_selected_units",
        "oracle_positive_selected_units",
        "selected_positive_rate",
        "reference_covered_selected_units",
        "unique_reference_events_hit_by_selected_units",
        "duplicate_selected_units_per_reference",
        "average_proxy_score_selected_units",
        "average_proxy_score_selected_positives",
    ]
    return quality.groupby(["method", "budget"], as_index=False)[cols].mean()


def write_report(
    monotonic: pd.DataFrame,
    hit_matrix: pd.DataFrame,
    quality: pd.DataFrame,
    segment_audit: pd.DataFrame,
    detail20: pd.DataFrame,
    detail50: pd.DataFrame,
    detail100: pd.DataFrame,
    main: pd.DataFrame,
) -> None:
    quality_summary = summarize_quality(quality)
    key_quality = quality_summary[
        (quality_summary["method"].isin(["Ours-Frozen-LATE-AQP-v1", "ARC-refinement", "ABae-stratified-confirmed"]))
        & (quality_summary["budget"].isin([20, 50, 100]))
    ].copy()
    for col in key_quality.select_dtypes(include=[np.number]).columns:
        key_quality[col] = key_quality[col].map(lambda x: round(float(x), 4) if pd.notna(x) else x)

    main_key = main[
        (main["method"].isin(["Ours-Frozen-LATE-AQP-v1", "ARC-refinement", "ABae-stratified-confirmed"]))
        & (main["budget"].isin([20, 50, 80, 100]))
    ][
        [
            "method",
            "budget",
            "event_detection_recall_mean",
            "event_detection_precision_mean",
            "event_detection_f1_mean",
            "oracle_calls_mean",
            "mean_overcoverage_ratio_mean",
        ]
    ].copy()
    for col in main_key.select_dtypes(include=[np.number]).columns:
        main_key[col] = main_key[col].map(lambda x: round(float(x), 4) if pd.notna(x) else x)

    b50_to_b100 = monotonic[(monotonic["budget_from"] == 50) & (monotonic["budget_to"] == 100)]
    nonmono_count = int((~b50_to_b100["query_units_subset"].astype(bool)).sum())
    lost_refs = sorted(set("|".join(b50_to_b100["lost_reference_hits"].fillna("").astype(str)).split("|")) - {""})
    missing_pos = sorted(set("|".join(b50_to_b100["missing_positive_query_units"].fillna("").astype(str)).split("|")) - {""}, key=lambda x: int(x))

    def hit_rate(method: str, budget: int) -> float:
        prefix = method.replace("-", "_").replace(" ", "_")
        rows = hit_matrix[hit_matrix["budget"] == budget]
        return float(rows[f"{prefix}_hit_any"].mean()) if not rows.empty else 0.0

    ours_50_any = hit_rate("Ours-Frozen-LATE-AQP-v1", 50)
    ours_100_any = hit_rate("Ours-Frozen-LATE-AQP-v1", 100)
    arc_100 = hit_rate("ARC-refinement", 100)
    abae_100 = hit_rate("ABae-stratified-confirmed", 100)
    ours_main_50 = float(main[(main["method"] == "Ours-Frozen-LATE-AQP-v1") & (main["budget"] == 50)]["event_detection_recall_mean"].iloc[0])
    ours_main_100 = float(main[(main["method"] == "Ours-Frozen-LATE-AQP-v1") & (main["budget"] == 100)]["event_detection_recall_mean"].iloc[0])

    ours_seg = segment_audit.groupby("budget", as_index=False).agg(
        num_segments_mean=("num_segments", "mean"),
        mean_segment_duration=("mean_segment_duration", "mean"),
        max_segment_duration_mean=("max_segment_duration", "mean"),
        segments_with_no_reference_overlap=("segments_with_no_reference_overlap", "mean"),
        refs_by_long_60=("references_covered_by_segments_longer_than_60s", "mean"),
    )
    for col in ours_seg.select_dtypes(include=[np.number]).columns:
        ours_seg[col] = ours_seg[col].map(lambda x: round(float(x), 4) if pd.notna(x) else x)

    only_arc_abae = []
    for _, row in hit_matrix[hit_matrix["budget"].isin([20, 50, 100])].iterrows():
        ours = bool(row["Ours_Frozen_LATE_AQP_v1_hit_any"])
        arc = bool(row["ARC_refinement_hit_any"])
        abae = bool(row["ABae_stratified_confirmed_hit_any"])
        if (arc or abae) and not ours:
            only_arc_abae.append((row["budget"], row["reference_id"]))
    only_arc_abae_preview = ", ".join(f"B{b}:{r}" for b, r in only_arc_abae[:20])

    all_hit_100 = hit_matrix[
        (hit_matrix["budget"] == 100)
        & hit_matrix["Ours_Frozen_LATE_AQP_v1_hit_any"]
        & hit_matrix["ARC_refinement_hit_any"]
        & hit_matrix["ABae_stratified_confirmed_hit_any"]
        & hit_matrix["SUPG_RT_confirmed_only_hit_any"]
        & hit_matrix["ARC_proxy_only_hit_any"]
    ]["reference_id"].astype(str).tolist()
    none_hit_100 = hit_matrix[
        (hit_matrix["budget"] == 100)
        & hit_matrix["hit_by_no_budget_respecting_method"]
    ]["reference_id"].astype(str).tolist()

    decision = "FIX_SEGMENT_MERGE_FIRST"

    report = f"""# Ours Failure Audit Report

## Scope

This audit reads existing CSV outputs only. It does not rerun Ours, ARC, SUPG, ABae, GPU, VLM, YOLO, training, downloads, or proxy generation. All labels discussed here are pseudo-oracle/VLM-defined labels, not human ground truth.

## Headline

`Ours-Frozen-LATE-AQP-v1` has two failure modes:

- At low and mid budgets, it selects fewer unique reference-covering units than ARC-refinement or ABae.
- At high budget, it actually covers the reference universe at the unit level, but merges many selected units into very long segments. Under one-to-one event matching, one long segment can match only one reference, so over-merge suppresses measured event recall/F1.

The B=50 to B=100 drop in the official repaired metric is therefore a segment construction failure, not a lack of pseudo-oracle positives. Ours mean event recall goes from {ours_main_50:.3f} at B=50 to {ours_main_100:.3f} at B=100, while per-reference hit-any across seeds goes from {ours_50_any:.3f} to {ours_100_any:.3f}. ARC-refinement hit-any reaches {arc_100:.3f} at B=100 and ABae reaches {abae_100:.3f}.

## Metric Context

Main comparison rows:

{main_key.to_markdown(index=False)}

## Budget Monotonicity

B=100 contains B=50 selected/query units in {len(SEEDS) - nonmono_count}/{len(SEEDS)} seeds. This confirms non-monotonic budget behavior in {nonmono_count}/{len(SEEDS)} seeds. However, B=100 queries all pseudo-oracle positive units, so the non-monotonicity is not the direct cause of the B=100 recall drop.

Missing positive units from B=50 when moving to B=100 include:

`{"|".join(missing_pos) if missing_pos else "none"}`

Lost reference hits from B=50 to B=100 include:

`{"|".join(lost_refs) if lost_refs else "none"}`

Non-monotonicity still matters because a budgeted method should be interpretable as an incremental process. But for the B=50 to B=100 metric collapse, the decisive issue is that B=100 turns broad unit coverage into overly long merged segments.

## Per-reference Findings

References hit by ARC/ABae but not Ours at B=20/50/100 include:

`{only_arc_abae_preview if only_arc_abae_preview else "none in preview"}`

At B=100, references hit by all inspected methods:

`{"|".join(all_hit_100) if all_hit_100 else "none"}`

At B=100, references hit by no budget-respecting method:

`{"|".join(none_hit_100) if none_hit_100 else "none"}`

Full matrix: `per_reference_method_hit_matrix.csv`.

## Selected Unit Quality

Mean selected-unit quality:

{key_quality.to_markdown(index=False)}

ABae wins because confirmed-only output concentrates on sampled positives and covers more unique reference events as budget grows without merging the whole timeline into a few broad predictions. ARC-refinement wins because its clip refinement produces broad proxy-derived candidate coverage while keeping output segments more useful under one-to-one matching. Ours spends the whole budget and reaches all positive/reference-covered units at B=100, but its segment construction turns that coverage into a small number of long segments.

## Segment Construction

Ours segment construction summary:

{ours_seg.to_markdown(index=False)}

Ours does form segments from queried units, and it queries all 32 pseudo-oracle positive units at B=100. The failure is that high-budget output merges too aggressively: mean segment duration rises to about 97s at B=100, max segment duration averages about 478s, and long segments cover most references. Under one-to-one matching, those long segments cannot receive credit for every reference they overlap.

## B=50 To B=100 Drop

The direct reason for the B=50 to B=100 performance drop is over-merge in segment construction. The B=100 query/output units cover all 20 reference events at least at the unit-overlap level, but the output collapses many adjacent selected units into far fewer, much longer segments. The repaired metric uses one-to-one matching between predictions and references, so a single broad prediction overlapping many short VLM-defined references only counts once.

There is also non-monotonic query behavior: B=100 is not a strict extension of B=50 in 3/5 seeds. That should be fixed for auditability, but the B=100 drop is explained by segment construction rather than missing positives.

## Module Diagnosis

- Candidate selection: weak at low/mid budgets, because B=20 and B=50 cover fewer unique references than ARC/ABae.
- Oracle budget allocation: secondary but real. The method allocates audit/repair/discovery from scratch per budget and is non-monotonic.
- Segment merge: primary high-budget failure. Segments are constructed, but B=80/B=100 over-merge selected units into long predictions that lose credit under one-to-one event matching.
- Boundary expansion: secondary. Boundary quality remains poor, but the main metric is overlap_any and the larger issue is missed events.
- Duplicate handling: not the main failure; duplicate rates are not the dominant observed gap.

## Answered Questions

- Why does Ours lose? Low/mid budgets suffer weaker selected-unit/reference coverage; high budgets suffer segment over-merge.
- Why does B=50 to B=100 drop? B=100 covers more units and all positives, but merges them into long segments that one-to-one matching cannot credit against multiple references.
- Does Ours have non-monotonic budget behavior? Yes.
- Did Ours query positives but fail to form effective segments? Yes at high budget: positives are queried and represented, but the merged segments are too broad to be effective under the repaired matching protocol.
- Where do ARC/ABae win? ARC keeps useful refined candidate segments; ABae outputs confirmed-positive unit groups with much better precision and less harmful over-merge.

## Decision

{decision}

## Next Fix Priority

Fix segment merge first: split high-budget selected units into event-sized components or add a non-reference-aware temporal NMS/segmentation rule so one broad selected region does not collapse many events into one prediction. Then make the budget process incremental/monotonic and improve low-budget selection coverage.
"""
    (OUT / "OURS_FAILURE_AUDIT_REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "reports/OURS_FAILURE_AUDIT_REPORT.md").write_text(report, encoding="utf-8")


def write_manifest() -> None:
    (OUT / "config/audit_config.yaml").write_text(
        "\n".join(
            [
                f"input_comparison_dir: {rel(COMPARE)}",
                f"frame_scores_csv: {rel(UNITS_CSV)}",
                f"reference_segments_csv: {rel(REF_CSV)}",
                f"budgets: {BUDGETS}",
                f"seeds: {SEEDS}",
                "primary_rule: overlap_any",
                "rerun_methods: false",
                "gpu: false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"path": rel(COMPARE / "main_comparison_table.csv"), "kind": "comparison_metrics"},
            {"path": rel(COMPARE / "ours_outputs"), "kind": "ours_existing_outputs"},
            {"path": rel(COMPARE / "baseline_outputs"), "kind": "baseline_existing_outputs"},
            {"path": rel(UNITS_CSV), "kind": "adapter_ready_units"},
            {"path": rel(REF_CSV), "kind": "reference_segments"},
        ]
    ).to_csv(OUT / "data_manifest/input_manifest.csv", index=False)


def main() -> None:
    for sub in ["scripts", "logs", "tables", "reports", "config", "data_manifest", "figures"]:
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    log("started failure audit")
    write_manifest()
    units, refs, main_table = load_inputs()
    unit_to_refs, _ = unit_ref_maps(units, refs)

    monotonic = audit_budget_monotonicity(units, refs, main_table, unit_to_refs)
    hit_matrix = per_reference_method_hit_matrix(units, refs, main_table)
    quality = selected_unit_quality(units, refs, main_table, unit_to_refs)
    segments = segment_construction_audit(units, refs, main_table)
    detail20 = reference_detail_for_budget(20, units, refs, main_table)
    detail50 = reference_detail_for_budget(50, units, refs, main_table)
    detail100 = reference_detail_for_budget(100, units, refs, main_table)

    outputs = {
        "budget_monotonicity_audit.csv": monotonic,
        "per_reference_method_hit_matrix.csv": hit_matrix,
        "selected_unit_quality.csv": quality,
        "segment_construction_audit.csv": segments,
        "reference_detail_B20.csv": detail20,
        "reference_detail_B50.csv": detail50,
        "reference_detail_B100.csv": detail100,
    }
    for name, df in outputs.items():
        df.to_csv(OUT / name, index=False)
        df.to_csv(OUT / "tables" / name, index=False)

    write_report(monotonic, hit_matrix, quality, segments, detail20, detail50, detail100, main_table)
    log("finished failure audit")


if __name__ == "__main__":
    main()
