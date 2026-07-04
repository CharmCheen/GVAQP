#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from common_review import OUT, append_progress, legal_values_report, safe_float, write_df, write_text


TRUE_INTERVAL_COLUMNS = [
    "event_id",
    "video_id",
    "event_type",
    "t_start",
    "t_end",
    "duration",
    "source_review_id",
    "boundary_confidence",
    "keep_for_interval_eval",
    "annotation_version",
    "notes",
]
POINT_COLUMNS = ["review_id", "video_id", "t_start", "t_end", "notes"]
AMBIGUOUS_COLUMNS = ["review_id", "video_id", "t_start", "t_end", "notes"]
ISSUE_COLUMNS = ["review_id", "issue", "value"]


def load_sheet(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path, sheet_name="review_queue")
    return pd.read_csv(path)


def blank(v) -> bool:
    return pd.isna(v) or str(v).strip() == ""


def clean(v) -> str:
    if pd.isna(v):
        return ""
    text = str(v).strip().lower()
    return "" if text == "nan" else text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet", type=Path, default=OUT / "human_review_sheet.csv")
    args = parser.parse_args()
    if not args.sheet.exists():
        write_text(OUT / "review_validation_report.md", "# Review Validation Report\n\nHuman review sheet does not exist yet.")
        return
    df = load_sheet(args.sheet)
    legal_conf = {"high", "medium", "low", "review", ""}
    legal_keep = {"yes", "no", "review", ""}
    issues = []
    true_rows, point_rows, amb_rows = [], [], []
    human_started = False
    for r in df.itertuples(index=False):
        h_true = clean(getattr(r, "human_is_true_interval", ""))
        h_point = clean(getattr(r, "human_is_point_anchor", ""))
        h_neg = clean(getattr(r, "human_is_negative", ""))
        keep = clean(getattr(r, "keep_for_interval_eval", ""))
        conf = clean(getattr(r, "boundary_confidence", ""))
        if any(x in {"yes", "no", "review"} for x in [h_true, h_point, h_neg, keep]) or conf in {"high", "medium", "low", "review"}:
            human_started = True
        if keep not in legal_keep:
            issues.append({"review_id": r.review_id, "issue": "illegal_keep_for_interval_eval", "value": keep})
        if conf not in legal_conf:
            issues.append({"review_id": r.review_id, "issue": "illegal_boundary_confidence", "value": conf})
        cs = getattr(r, "corrected_start", "")
        ce = getattr(r, "corrected_end", "")
        if h_true == "yes":
            if blank(cs) or blank(ce):
                issues.append({"review_id": r.review_id, "issue": "true_interval_missing_corrected_boundary", "value": ""})
                continue
            start, end = safe_float(cs), safe_float(ce)
            if start >= end:
                issues.append({"review_id": r.review_id, "issue": "corrected_start_not_less_than_end", "value": f"{start},{end}"})
                continue
            dur = end - start
            if dur < 2.0:
                issues.append({"review_id": r.review_id, "issue": "true_interval_duration_under_2s_check", "value": dur})
            if keep == "yes" and dur < 5.0:
                issues.append({"review_id": r.review_id, "issue": "interval_eval_duration_under_5s_check", "value": dur})
            true_rows.append({
                "event_id": f"expanded_event_{len(true_rows)+1:04d}",
                "video_id": getattr(r, "video_id", "realcartest"),
                "event_type": getattr(r, "human_event_type", ""),
                "t_start": start,
                "t_end": end,
                "duration": dur,
                "source_review_id": r.review_id,
                "boundary_confidence": conf,
                "keep_for_interval_eval": keep,
                "annotation_version": "human_review_v1",
                "notes": getattr(r, "notes", ""),
            })
        elif h_point == "yes":
            point_rows.append({"review_id": r.review_id, "video_id": getattr(r, "video_id", "realcartest"), "t_start": getattr(r, "t_start", ""), "t_end": getattr(r, "t_end", ""), "notes": getattr(r, "notes", "")})
        elif str(getattr(r, "human_event_type", "")).strip().lower() == "ambiguous" or keep == "review":
            amb_rows.append({"review_id": r.review_id, "video_id": getattr(r, "video_id", "realcartest"), "t_start": getattr(r, "t_start", ""), "t_end": getattr(r, "t_end", ""), "notes": getattr(r, "notes", "")})
    true_df = pd.DataFrame(true_rows, columns=TRUE_INTERVAL_COLUMNS)
    point_df = pd.DataFrame(point_rows, columns=POINT_COLUMNS)
    amb_df = pd.DataFrame(amb_rows, columns=AMBIGUOUS_COLUMNS)
    issue_df = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
    write_df(true_df, OUT / "validated_true_interval_reference.csv")
    write_df(point_df, OUT / "validated_point_anchor_reference.csv")
    write_df(amb_df, OUT / "validated_ambiguous_reference.csv")
    write_df(issue_df, OUT / "review_validation_issues.csv")
    status = "PENDING_HUMAN_REVIEW" if not human_started else "VALIDATION_HAS_ISSUES" if not issue_df.empty else "VALIDATION_OK"
    write_text(
        OUT / "review_validation_report.md",
        f"""# Review Validation Report

- Status: `{status}`
- Human fields started: `{human_started}`
- Validated true interval rows: `{len(true_df)}`
- Validated point-anchor rows: `{len(point_df)}`
- Validated ambiguous rows: `{len(amb_df)}`
- Issue rows: `{len(issue_df)}`
- Target true interval count: `20-30`

If human review has not been filled, this is expected: the validation template and empty output CSVs are generated without failing.
""",
    )
    append_progress("validate_review_sheet", status)


if __name__ == "__main__":
    main()
