#!/usr/bin/env python3
from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from common_review import (
    OUT,
    REF_DUR,
    SMOKE,
    SQ,
    SQ_ENV,
    SQ_REF,
    SYN,
    TARGET_QUEUE_SIZE,
    TIEBREAK,
    V2,
    REQUESTED_VIDEO,
    append_progress,
    ensure_dirs,
    input_inventory,
    md_table,
    minimal_xlsx,
    normalize,
    legal_values_report,
    reference_events,
    safe_float,
    temporal_iou,
    video_source,
    write_df,
    write_text,
)


def add_candidate(rows: list[dict], source: str, video_id: str, t_start, t_end, **kwargs) -> None:
    t0 = safe_float(t_start)
    t1 = safe_float(t_end)
    if t1 <= t0:
        return
    context_start = max(0.0, t0 - kwargs.pop("context_pad_before", 8.0))
    context_end = t1 + kwargs.pop("context_pad_after", 8.0)
    rows.append(
        {
            "candidate_id": f"cand_{len(rows)+1:05d}",
            "source": source,
            "video_id": video_id or "realcartest",
            "t_start": t0,
            "t_end": t1,
            "duration": t1 - t0,
            "context_start": context_start,
            "context_end": context_end,
            "method": kwargs.get("method", ""),
            "source_signal": kwargs.get("source_signal", ""),
            "active_score": kwargs.get("active_score", math.nan),
            "max_score": kwargs.get("max_score", math.nan),
            "mean_score": kwargs.get("mean_score", math.nan),
            "p_answer_if_available": kwargs.get("p_answer_if_available", math.nan),
            "current_label_if_available": kwargs.get("current_label_if_available", ""),
            "matched_event_id_if_available": kwargs.get("matched_event_id_if_available", ""),
            "failure_type_if_available": kwargs.get("failure_type_if_available", ""),
            "review_priority": int(kwargs.get("review_priority", 30)),
            "review_reason": kwargs.get("review_reason", source),
            "duplicate_group_id": "",
            "needs_clip_export": True,
            "needs_contact_sheet": True,
            "candidate_suggestion_only": True,
        }
    )


def source_existing_reference(rows: list[dict]) -> None:
    ref = reference_events()
    for r in ref.itertuples(index=False):
        label = getattr(r, "duration_stratum")
        priority = 95 if label == "true_interval" else 100 if label == "ambiguous" else 58
        add_candidate(
            rows,
            f"existing_reference_{label}",
            r.video_id,
            r.t_start,
            r.t_end,
            current_label_if_available=label,
            matched_event_id_if_available=r.event_id,
            method="reference_event",
            source_signal="vlm_defined_existing_reference",
            review_priority=priority,
            review_reason="positive_sanity_example" if label == "true_interval" else "point_anchor_or_ambiguous_may_need_boundary_review",
        )


def source_prior_queue(rows: list[dict]) -> None:
    path = SQ_REF / "true_interval_review_queue.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    for r in df.itertuples(index=False):
        add_candidate(
            rows,
            "prior_sq_craq_review_queue",
            getattr(r, "video_id", "realcartest"),
            r.t_start,
            r.t_end,
            current_label_if_available=getattr(r, "current_label_if_any", ""),
            review_priority=int(safe_float(getattr(r, "review_priority", 50), 50)),
            review_reason=f"prior_queue:{getattr(r, 'candidate_source', '')}",
        )


def source_top_bin(rows: list[dict]) -> None:
    path = TIEBREAK / "top_p_answer_bin_candidates.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    for r in df.itertuples(index=False):
        label = "top_bin_existing_tp" if bool(getattr(r, "answer_iou_0_3", False)) else "top_bin_unconfirmed_or_false_positive"
        add_candidate(
            rows,
            "top_p_answer_bin",
            "realcartest",
            r.t_start,
            r.t_end,
            method=getattr(r, "method", ""),
            source_signal=getattr(r, "source_signal", ""),
            active_score=getattr(r, "active_score", math.nan),
            max_score=getattr(r, "max_score", math.nan),
            mean_score=getattr(r, "mean_score", math.nan),
            p_answer_if_available=getattr(r, "p_answer", math.nan),
            current_label_if_available=label,
            matched_event_id_if_available=getattr(r, "matched_event_id", ""),
            review_priority=90 if safe_float(getattr(r, "duration", 0)) >= 5 else 74,
            review_reason="high p_answer top-bin candidate; includes hard false positives and possible missed intervals",
        )


def source_smoke(rows: list[dict]) -> None:
    path = SMOKE / "smoke_selected_intervals.csv"
    if not path.exists():
        return
    df = pd.read_csv(path).drop_duplicates("interval_id")
    for r in df.itertuples(index=False):
        add_candidate(
            rows,
            "smoke_selected_interval",
            "realcartest",
            r.t_start,
            r.t_end,
            p_answer_if_available=getattr(r, "p_answer", math.nan),
            current_label_if_available="smoke_selected_existing_tp" if bool(getattr(r, "answer_iou_0_3", False)) else "smoke_selected_unconfirmed",
            matched_event_id_if_available=getattr(r, "matched_event_id", ""),
            review_priority=88,
            review_reason="selected by calibration repair smoke / CILS-like replay",
        )


def source_synthetic_predictions(rows: list[dict]) -> None:
    for rel, source, priority in [
        ("predictions_cils_synthetic_downstream.csv", "synthetic_cils_selected_diagnostic", 72),
        ("predictions_synthetic_score_topk.csv", "synthetic_topk_selected_diagnostic", 68),
    ]:
        path = SYN / rel
        if not path.exists():
            continue
        usecols = ["interval_id", "t_start", "t_end", "duration", "synthetic_signal_name", "seed", "budget", "rank", "answer_iou_0_3", "matched_true_interval_event_id_iou_0_3"]
        df = pd.read_csv(path, usecols=lambda c: c in usecols)
        df = df[(df.get("budget", 0) >= 80) & (df.get("rank", 999) <= 20)].drop_duplicates("interval_id").head(120)
        for r in df.itertuples(index=False):
            add_candidate(
                rows,
                source,
                "realcartest",
                r.t_start,
                r.t_end,
                current_label_if_available="synthetic_label_derived_tp" if bool(getattr(r, "answer_iou_0_3", False)) else "synthetic_selected_unconfirmed",
                matched_event_id_if_available=getattr(r, "matched_true_interval_event_id_iou_0_3", ""),
                review_priority=priority,
                review_reason=f"selected in label-derived synthetic diagnostic; signal={getattr(r, 'synthetic_signal_name', '')}",
            )


def source_envelope(rows: list[dict]) -> None:
    cand_path = SQ_ENV / "envelope_candidates.csv"
    if cand_path.exists():
        df = pd.read_csv(cand_path)
        df = df.sort_values(["answer_iou_0_3", "rank"], ascending=[False, True]).drop_duplicates("interval_id").head(160)
        lattice = lattice_lookup()
        df = df.merge(lattice, on="interval_id", how="left", suffixes=("", "_lat"))
        for r in df.itertuples(index=False):
            add_candidate(
                rows,
                "audited_envelope_candidate",
                "realcartest",
                r.t_start,
                r.t_end,
                method=getattr(r, "method", ""),
                source_signal=getattr(r, "source_signal", ""),
                active_score=getattr(r, "active_score", math.nan),
                max_score=getattr(r, "max_score", math.nan),
                mean_score=getattr(r, "mean_score", math.nan),
                current_label_if_available="envelope_candidate_existing_tp" if bool(getattr(r, "answer_iou_0_3", False)) else "envelope_candidate_unconfirmed",
                review_priority=84 if bool(getattr(r, "answer_iou_0_3", False)) else 70,
                review_reason=f"audited interval envelope candidate baseline={getattr(r, 'envelope_baseline', '')}",
            )
    repair_path = SQ_ENV / "envelope_repair_trace.csv"
    if repair_path.exists():
        repair = pd.read_csv(repair_path).drop_duplicates("interval_id")
        lattice = lattice_lookup()
        repair = repair.merge(lattice, on="interval_id", how="left")
        for r in repair.head(120).itertuples(index=False):
            if pd.isna(getattr(r, "t_start", np.nan)):
                continue
            add_candidate(
                rows,
                "envelope_repair_high_risk",
                "realcartest",
                r.t_start,
                r.t_end,
                method=getattr(r, "method", ""),
                source_signal=getattr(r, "source_signal", ""),
                active_score=getattr(r, "active_score", math.nan),
                max_score=getattr(r, "max_score", math.nan),
                mean_score=getattr(r, "mean_score", math.nan),
                current_label_if_available="diagnostic_repair_candidate",
                review_priority=92 if bool(getattr(r, "diagnostic_repair", False)) else 76,
                review_reason="outside-envelope repair/high-risk diagnostic candidate",
            )


def lattice_lookup() -> pd.DataFrame:
    cols = ["interval_id", "t_start", "t_end", "duration", "method", "source_signal", "active_score", "max_score", "mean_score", "score_persistence", "boundary_left_drop", "boundary_right_drop", "signal_disagreement", "matched_event_id", "answer_iou_0_3", "answer_iou_0_5"]
    df = pd.read_csv(V2 / "interval_lattice_v2_clean.csv", usecols=lambda c: c in cols)
    return df


def source_lattice(rows: list[dict]) -> None:
    df = lattice_lookup()
    df = df[df["duration"].between(3, 60)].copy()
    df["active_norm"] = normalize(df["active_score"])
    df["boundary_contrast"] = normalize(df.get("boundary_left_drop", 0) + df.get("boundary_right_drop", 0))
    df["persistence_norm"] = normalize(df.get("score_persistence", 0))
    df["candidate_score"] = 0.55 * df["active_norm"] + 0.25 * df["boundary_contrast"] + 0.20 * df["persistence_norm"]
    bins = [
        ("lattice_high_score", df.sort_values("active_score", ascending=False).head(120), 62, "high active_score lattice representative"),
        ("lattice_high_boundary_contrast", df.sort_values("boundary_contrast", ascending=False).head(80), 60, "high boundary contrast lattice representative"),
        ("lattice_medium_duration_high_score", df[df["duration"].between(8, 25)].sort_values("candidate_score", ascending=False).head(100), 64, "moderate duration and high cheap score"),
        ("lattice_low_density_blindspot", df[df["active_score"] < df["active_score"].quantile(0.35)].sort_values("boundary_contrast", ascending=False).head(80), 52, "low-score blindspot / contrast candidate"),
    ]
    for source, sub, priority, reason in bins:
        for r in sub.itertuples(index=False):
            add_candidate(
                rows,
                source,
                "realcartest",
                r.t_start,
                r.t_end,
                method=getattr(r, "method", ""),
                source_signal=getattr(r, "source_signal", ""),
                active_score=getattr(r, "active_score", math.nan),
                max_score=getattr(r, "max_score", math.nan),
                mean_score=getattr(r, "mean_score", math.nan),
                current_label_if_available="lattice_existing_tp" if bool(getattr(r, "answer_iou_0_3", False)) else "lattice_unconfirmed",
                matched_event_id_if_available=getattr(r, "matched_event_id", ""),
                review_priority=priority,
                review_reason=reason,
            )


def dedupe(pool: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pool = pool.sort_values(["review_priority", "duration", "active_score"], ascending=[False, False, False]).reset_index(drop=True)
    reps: list[dict] = []
    group_ids = []
    duplicate_of = []
    for r in pool.itertuples(index=False):
        group = None
        for idx, rep in enumerate(reps):
            iou = temporal_iou(float(r.t_start), float(r.t_end), float(rep["t_start"]), float(rep["t_end"]))
            c1 = (float(r.t_start) + float(r.t_end)) / 2.0
            c2 = (float(rep["t_start"]) + float(rep["t_end"])) / 2.0
            if iou > 0.7 or abs(c1 - c2) < 2.0:
                group = idx
                break
        if group is None:
            reps.append(r._asdict())
            group = len(reps) - 1
            duplicate_of.append("")
        else:
            duplicate_of.append(reps[group]["candidate_id"])
        group_ids.append(f"dup_{group+1:04d}")
    merged = pool.copy()
    merged["duplicate_group_id"] = group_ids
    merged["duplicate_of_candidate_id"] = duplicate_of
    keep = merged[merged["duplicate_of_candidate_id"].eq("")].copy()
    keep = keep.sort_values(["review_priority", "duration", "active_score"], ascending=[False, False, False]).head(TARGET_QUEUE_SIZE).reset_index(drop=True)
    keep["candidate_id"] = [f"cand_dedup_{i+1:04d}" for i in range(len(keep))]
    return merged, keep


def build_review_queue(deduped: pd.DataFrame) -> pd.DataFrame:
    q = deduped.copy()
    q["review_id"] = [f"review_{i+1:04d}" for i in range(len(q))]
    q["priority"] = np.select(
        [q["review_priority"] >= 85, q["review_priority"] >= 60],
        ["Priority 1", "Priority 2"],
        default="Priority 3",
    )
    q["suggested_event_type"] = "enter_ego_path_or_near_conflict"
    q["human_event_type"] = ""
    q["human_is_true_interval"] = ""
    q["human_is_point_anchor"] = ""
    q["human_is_negative"] = ""
    q["corrected_start"] = ""
    q["corrected_end"] = ""
    q["boundary_confidence"] = ""
    q["keep_for_interval_eval"] = ""
    q["exclusion_reason"] = ""
    q["notes"] = ""
    q["final_reviewed_label"] = ""
    cols = [
        "review_id",
        "candidate_id",
        "priority",
        "review_reason",
        "video_id",
        "t_start",
        "t_end",
        "duration",
        "context_start",
        "context_end",
        "source",
        "current_label_if_available",
        "suggested_event_type",
        "human_event_type",
        "human_is_true_interval",
        "human_is_point_anchor",
        "human_is_negative",
        "corrected_start",
        "corrected_end",
        "boundary_confidence",
        "keep_for_interval_eval",
        "exclusion_reason",
        "notes",
        "final_reviewed_label",
        "method",
        "source_signal",
        "active_score",
        "max_score",
        "mean_score",
        "p_answer_if_available",
        "matched_event_id_if_available",
        "failure_type_if_available",
        "duplicate_group_id",
        "needs_clip_export",
        "needs_contact_sheet",
    ]
    return q[cols]


def write_inventory() -> None:
    inv = input_inventory()
    video, video_status, offset = video_source()
    inv.loc[len(inv)] = {
        "path": "video_source_resolution",
        "exists": video is not None,
        "row_count_if_csv": None,
        "column_names_if_csv": "",
        "role": "resolved video source",
        "limitations": f"status={video_status}; path={video}; local_to_media_offset_seconds={offset}",
    }
    write_df(inv, OUT / "artifact_inventory.csv")
    write_text(
        OUT / "artifact_inventory.md",
        "# Artifact Inventory\n\n"
        + "- Existing `reference_duration_stratified_eval_v1/`: **{}**\n".format(REF_DUR.exists())
        + "- Requested `try_or_no/videos/realcartest.mp4`: **{}**\n".format(REQUESTED_VIDEO.exists())
        + "- Video source resolution is recorded in the table.\n\n"
        + md_table(inv, 80),
    )


def main() -> None:
    ensure_dirs()
    write_text(OUT / "config/experiment_config.yaml", "experiment: true_interval_reference_expansion_execution_v1\ndiagnostic_only: true\nmodel_calls: false\nautomatic_labeling: false\nreview_queue_target_size: 120\n")
    write_text(OUT / "reproducible_commands.md", "```bash\nbash src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/run_all.sh\n```")
    write_inventory()
    rows: list[dict] = []
    source_existing_reference(rows)
    source_prior_queue(rows)
    source_top_bin(rows)
    source_smoke(rows)
    source_synthetic_predictions(rows)
    source_envelope(rows)
    source_lattice(rows)
    pool = pd.DataFrame(rows)
    if pool.empty:
        raise RuntimeError("No review candidates could be built from available artifacts.")
    merged, deduped = dedupe(pool)
    queue = build_review_queue(deduped)
    write_df(merged, OUT / "candidate_pool_merged.csv")
    write_df(deduped, OUT / "candidate_pool_deduped.csv")
    write_df(queue, OUT / "true_interval_review_queue.csv")
    write_df(queue, OUT / "human_review_sheet.csv")
    label_legend = legal_values_report()
    protocol_summary = pd.DataFrame(
        [
            {"topic": "true_interval_event", "definition": "Sustained event with reviewable start/end boundaries suitable for interval IoU."},
            {"topic": "point_anchor_event", "definition": "Instantaneous or anchor-like evidence without reliable duration; exclude from interval IoU main evaluation."},
            {"topic": "negative", "definition": "Candidate does not contain the target event."},
            {"topic": "ambiguous", "definition": "Requires second review or boundary is uncertain."},
            {"topic": "do_not_fabricate", "definition": "Human columns must remain blank until a human reviewer fills them."},
        ]
    )
    current_ref = reference_events()[["event_id", "video_id", "t_start", "t_end", "duration", "duration_stratum", "keep_for_interval_eval_existing"]].copy()
    minimal_xlsx(
        OUT / "human_review_sheet.xlsx",
        {
            "review_queue": queue,
            "label_legend": label_legend,
            "protocol_summary": protocol_summary,
            "current_reference_summary": current_ref,
        },
    )
    source_summary = pool.groupby("source").size().reset_index(name="raw_candidate_count").sort_values("raw_candidate_count", ascending=False)
    priority_summary = queue.groupby(["priority", "source"]).size().reset_index(name="review_count").sort_values(["priority", "review_count"], ascending=[True, False])
    write_text(
        OUT / "candidate_sources_summary.md",
        "# Candidate Sources Summary\n\nRaw candidates before deduplication:\n\n"
        + md_table(source_summary, 80)
        + "\n\nSelected review queue by priority/source:\n\n"
        + md_table(priority_summary, 80),
    )
    write_text(
        OUT / "review_queue_summary.md",
        f"""# Review Queue Summary

- Raw candidate rows: `{len(pool)}`
- Deduplicated candidate rows: `{len(deduped)}`
- Final review queue rows: `{len(queue)}`
- Target range: `80-150`
- Human label placeholders are intentionally blank.
- Existing labels and candidate suggestions are separated from human/final label columns.

Priority/source distribution:

{md_table(priority_summary, 80)}
""",
    )
    write_text(
        OUT / "annotation_protocol.md",
        """# Annotation Protocol

## Core Labels

### true interval event

A true interval event is a sustained process with a meaningful start and end time. It is suitable for interval IoU evaluation because a reviewer can mark when the event semantics begin and end.

### point-anchor event

A point-anchor event is a local, instantaneous, or single-frame-neighborhood cue. It may be useful context, but it should not enter the main interval IoU evaluation.

### negative

The candidate window does not contain the target event.

### ambiguous

The candidate needs second review, or event boundaries cannot be reliably determined.

## Required Human Fields

- `human_event_type`: one of cut-in, near-conflict, abnormal vehicle interaction, pedestrian crossing, cyclist crossing, blocked, overtaking, being overtaken, other, negative, ambiguous.
- `corrected_start`: event semantic start time in local video seconds.
- `corrected_end`: event semantic end time in local video seconds.
- `boundary_confidence`: high / medium / low.
- `keep_for_interval_eval`: yes / no / review.
- `exclusion_reason`: required when excluding a visible candidate from interval IoU evaluation.

## Atomic Conditions

- cut-in: an object moves into the ego path from an adjacent/outside region.
- near-conflict: spatial interaction requires ego attention or creates potential conflict.
- abnormal vehicle interaction: unusual merge, stop, encroachment, or trajectory conflict.
- pedestrian / cyclist crossing: vulnerable road user enters or crosses the ego path.
- blocked / overtaking / being overtaken: include only when the target event has sustained ego-path interaction semantics.

## Boundary Rules

- `start_time`: earliest time where the event semantics begin.
- `end_time`: time where the event semantics end or the scene stabilizes.
- Do not use a single center anchor as an interval boundary.
- If the event is too short and has no sustained process, mark point-anchor.
- If boundary is uncertain, use `boundary_confidence=low` and `keep_for_interval_eval=review`.

Existing labels are context only. Candidate suggestions are not human labels. Final reviewed labels must come from filled human fields.
""",
    )
    write_text(
        OUT / "human_review_workbook_report.md",
        f"""# Human Review Workbook Report

- CSV workbook path: `src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/human_review_sheet.csv`
- XLSX workbook path: `src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/human_review_sheet.xlsx`
- Sheets: `review_queue`, `label_legend`, `protocol_summary`, `current_reference_summary`
- Review rows: `{len(queue)}`
- Human label columns are blank placeholders.
""",
    )
    append_progress("build_review_queue", f"queue_rows={len(queue)} raw_rows={len(pool)}")


if __name__ == "__main__":
    main()
