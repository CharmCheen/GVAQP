#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from common_review import OUT, append_progress, write_df, write_text
from validate_review_sheet import TRUE_INTERVAL_COLUMNS


def read_csv_or_empty(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    try:
        return pd.read_csv(path)
    except EmptyDataError:
        return pd.DataFrame(columns=columns or [])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validated-true", type=Path, default=OUT / "validated_true_interval_reference.csv")
    args = parser.parse_args()
    true_df = read_csv_or_empty(args.validated_true, TRUE_INTERVAL_COLUMNS)
    expanded = true_df.copy()
    if expanded.empty:
        expanded = pd.DataFrame(columns=TRUE_INTERVAL_COLUMNS)
    write_df(expanded, OUT / "reference_events_expanded_v1.csv")
    point = read_csv_or_empty(OUT / "validated_point_anchor_reference.csv", ["review_id", "video_id", "t_start", "t_end", "notes"])
    amb = read_csv_or_empty(OUT / "validated_ambiguous_reference.csv", ["review_id", "video_id", "t_start", "t_end", "notes"])
    write_df(point, OUT / "excluded_point_anchor_events.csv")
    write_df(amb, OUT / "ambiguous_events_for_second_review.csv")
    status = "PENDING_HUMAN_REVIEW" if expanded.empty else "EXPANDED_REFERENCE_READY"
    write_text(
        OUT / "reference_events_expanded_v1_summary.md",
        f"""# Expanded Reference Summary

- Status: `{status}`
- Expanded true interval events: `{len(expanded)}`
- Excluded point-anchor events: `{len(point)}`
- Ambiguous events for second review: `{len(amb)}`

If status is `PENDING_HUMAN_REVIEW`, fill `human_review_sheet.csv`, rerun validation, then rerun merge.
""",
    )
    append_progress("merge_human_review", status)


if __name__ == "__main__":
    main()
