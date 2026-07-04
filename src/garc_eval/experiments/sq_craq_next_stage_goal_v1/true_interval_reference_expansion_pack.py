from __future__ import annotations

import pandas as pd

from common_io import (
    OUT,
    SMOKE,
    SYN,
    TIEBREAK,
    V2,
    canonical_candidates,
    event_subsets,
    md_table,
    write_df,
    write_text,
)

PART = OUT / "true_interval_reference_expansion_v1"


def existing_reference() -> pd.DataFrame:
    ev = event_subsets().copy()
    summ = ev.groupby("event_subset").agg(event_count=("event_id", "count"), mean_duration=("duration", "mean"), min_duration=("duration", "min"), max_duration=("duration", "max")).reset_index()
    write_df(summ, PART / "existing_reference_summary.csv")
    write_text(
        PART / "existing_reference_summary.md",
        f"""# Existing Reference Summary

Current reference is insufficient for interval-IoU evaluation because only `{int((ev['event_subset'] == 'interval_eval').sum())}` events qualify as true interval events.

{md_table(summ)}

Point-anchor events must be excluded from main interval TP counts.
""",
    )
    return ev


def add_review(rows: list[dict], seen: set[tuple], video_id: str, t_start: float, t_end: float, source: str, priority: int, score_fields: str = "", label: str = "") -> None:
    key = (round(float(t_start), 1), round(float(t_end), 1), source)
    if key in seen:
        return
    seen.add(key)
    rows.append(
        {
            "review_id": f"tir_{len(rows)+1:04d}",
            "video_id": video_id,
            "t_start": float(t_start),
            "t_end": float(t_end),
            "suggested_context_start": max(0.0, float(t_start) - 5.0),
            "suggested_context_end": float(t_end) + 5.0,
            "candidate_source": source,
            "score_fields": score_fields,
            "current_label_if_any": label,
            "duration": float(t_end) - float(t_start),
            "proposed_event_type": "enter_ego_path_or_near_conflict",
            "review_priority": priority,
            "needs_video_review": True,
            "human_label": "",
            "corrected_start": "",
            "corrected_end": "",
            "boundary_confidence": "",
            "keep_for_interval_eval": "",
            "notes": "DIAGNOSTIC_QUEUE_ONLY; no human label fabricated",
        }
    )


def review_queue(ev: pd.DataFrame) -> pd.DataFrame:
    rows, seen = [], set()
    for r in ev.itertuples(index=False):
        add_review(rows, seen, r.video_id, r.t_start, r.t_end, f"existing_{r.event_subset}", 100 if r.event_subset == "interval_eval" else 80, label=r.event_subset)
    cand = canonical_candidates()
    high = cand.sort_values(["active_score", "duration"], ascending=[False, True]).head(80)
    for r in high.itertuples(index=False):
        add_review(rows, seen, getattr(r, "video_id", "realcartest"), r.t_start, r.t_end, "high_active_score_candidate", 70, f"active_score={getattr(r, 'active_score', '')};max_score={getattr(r, 'max_score', '')}", "candidate")
    topbin_path = TIEBREAK / "top_p_answer_bin_candidates.csv"
    if topbin_path.exists():
        topbin = pd.read_csv(topbin_path).head(120)
        for r in topbin.itertuples(index=False):
            source = "top_p_answer_bin_false_positive" if not bool(getattr(r, "answer_iou_0_3", False)) else "top_p_answer_bin_candidate"
            add_review(rows, seen, "realcartest", r.t_start, r.t_end, source, 90 if source.endswith("candidate") else 75, f"p_answer={getattr(r, 'p_answer', '')};active_score={getattr(r, 'active_score', '')}", "candidate")
    smoke_path = SMOKE / "smoke_selected_intervals.csv"
    if smoke_path.exists():
        smoke = pd.read_csv(smoke_path).head(80)
        for r in smoke.itertuples(index=False):
            add_review(rows, seen, "realcartest", r.t_start, r.t_end, "smoke_selected_interval", 65, "from smoke_selected_intervals", "candidate")
    outside_path = OUT / "audited_interval_envelope_mvp_v1/outside_audit_replay.csv"
    if outside_path.exists():
        outside = pd.read_csv(outside_path)
        # This file is aggregate-level in v1; use candidate lattice positives as a proxy queue source.
        missed = cand[(cand["answer_iou_0_3"].astype(bool)) & (cand["active_score"] < cand["active_score"].median())].head(80)
        for r in missed.itertuples(index=False):
            add_review(rows, seen, getattr(r, "video_id", "realcartest"), r.t_start, r.t_end, "outside_audit_high_risk_interval_proxy", 85, f"active_score={getattr(r, 'active_score', '')}", "candidate")
    queue = pd.DataFrame(rows).sort_values(["review_priority", "duration"], ascending=[False, False]).reset_index(drop=True)
    queue["review_id"] = [f"tir_{i+1:04d}" for i in range(len(queue))]
    write_df(queue, PART / "true_interval_review_queue.csv")
    return queue


def protocol_and_plan(queue: pd.DataFrame, ev: pd.DataFrame) -> None:
    write_text(
        PART / "annotation_protocol.md",
        """# Annotation Protocol

This protocol is for human or semi-human review only. It does not create labels automatically.

- True interval event: a temporally extended object interaction where an object starts outside the ego future path and enters/overlaps it, creating a meaningful spatial conflict or attention demand.
- Point-anchor event: a timestamp-like or very short event (duration <= 2s) whose boundaries are not meaningful enough for interval IoU main evaluation.
- Start boundary: first frame/time where the object begins the entering or conflict trajectory.
- End boundary: time when the conflict is resolved, leaves the path, or no longer requires ego attention.
- Atomic conditions: cut-in, near-conflict, abnormal interaction, pedestrian/cyclist/vehicle entering ego path.
- Boundary confidence: high if start/end are visually clear, medium if approximate, low if only an anchor is visible.
- Ambiguous cases: keep notes and do not include in interval-IoU main set unless corrected boundaries are credible.
- Multi-event overlap: create separate rows only when two objects/events have separable start/end semantics.
- IoU evaluation applies only to `keep_for_interval_eval=true` true interval events.
""",
    )
    write_text(
        PART / "reference_expansion_plan.md",
        f"""# Reference Expansion Plan

- Current interval events: `{int((ev['event_subset'] == 'interval_eval').sum())}`.
- Target: at least 20 true interval events for a minimal reference gate; preferably 30 for more stable diagnostics.
- Review queue rows: `{len(queue)}`.
- Priority: existing interval events for consistency, top p_answer/high-score candidates, outside-audit high-risk proxies, and hard false positives.
- After review, write corrected rows back as a new independent reference table; do not overwrite `reference_events.csv`.
""",
    )


def final_report(queue: pd.DataFrame, ev: pd.DataFrame) -> None:
    point = int((ev["event_subset"] == "point_anchor").sum())
    interval = int((ev["event_subset"] == "interval_eval").sum())
    write_text(
        PART / "FINAL_REPORT.md",
        f"""# True Interval Reference Expansion V1

## Answers

1. Current reference is insufficient because it has only `{interval}` true interval events and `{point}` point-anchor events.
2. Expand to at least 20 true interval events; 30 is preferable for diagnostics.
3. Priority review candidates: existing interval events, top p_answer/high-score candidates, hard false positives, and outside-audit high-risk intervals.
4. Existing point-anchor events should be excluded from interval-IoU main evaluation.
5. Human review should produce a new independent corrected reference table consumed by later SQ-CRAQ replay; do not overwrite existing artifacts.

Review queue: `{len(queue)}` rows. No human labels were fabricated.
""",
    )


def main() -> None:
    PART.mkdir(parents=True, exist_ok=True)
    ev = existing_reference()
    queue = review_queue(ev)
    protocol_and_plan(queue, ev)
    final_report(queue, ev)


if __name__ == "__main__":
    main()
