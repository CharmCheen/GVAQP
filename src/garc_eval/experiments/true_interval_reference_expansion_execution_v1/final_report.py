#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from common_review import OUT, append_progress, md_table, write_text


def main() -> None:
    queue = pd.read_csv(OUT / "true_interval_review_queue.csv") if (OUT / "true_interval_review_queue.csv").exists() else pd.DataFrame()
    media = pd.read_csv(OUT / "media_manifest.csv") if (OUT / "media_manifest.csv").exists() else pd.DataFrame()
    source_summary = queue.groupby(["priority", "source"]).size().reset_index(name="count").sort_values(["priority", "count"], ascending=[True, False]) if not queue.empty else pd.DataFrame()
    media_ok = bool(not media.empty and (media.get("clip_export_status", pd.Series(dtype=str)) == "OK").any())
    clip_ok = int((media.get("clip_export_status", pd.Series(dtype=str)) == "OK").sum()) if not media.empty else 0
    sheet_ok = int((media.get("sheet_export_status", pd.Series(dtype=str)) == "OK").sum()) if not media.empty else 0
    validation = (OUT / "review_validation_report.md").read_text(encoding="utf-8") if (OUT / "review_validation_report.md").exists() else "Validation not run."
    write_text(
        OUT / "FINAL_REPORT.md",
        f"""# True Interval Reference Expansion Execution V1

## 1. Why Current Reference Is A Hard Blocker

The current reference mixes point-anchor events and true interval events. Only about six events are usable for interval-IoU main evaluation, so CILS, SQ-CRAQ envelope, and synthetic-signal conclusions remain diagnostic until the true interval reference is expanded.

## 2. Review Candidate Count

- Review candidates generated: `{len(queue)}`
- Target range: `80-150`

## 3. Candidate Sources And Priority Distribution

{md_table(source_summary, 80)}

## 4. Media Export Status

- Media export successful: `{media_ok}`
- Clips exported OK: `{clip_ok}` / `{len(media)}`
- Contact sheets exported OK: `{sheet_ok}` / `{len(media)}`

If the requested `try_or_no/videos/realcartest.mp4` was missing, the scripts used the corresponding fallback full video when available and recorded the local-to-media offset in `media_manifest.csv`.

## 5. How Humans Should Annotate

Open `human_review_sheet.csv` or `human_review_sheet.xlsx`. Fill only the human/final fields: `human_event_type`, `human_is_true_interval`, `human_is_point_anchor`, `human_is_negative`, `corrected_start`, `corrected_end`, `boundary_confidence`, `keep_for_interval_eval`, `exclusion_reason`, and `notes`.

Existing labels and candidate suggestions are context; they are not final reviewed labels.

## 6. Validation And Merge

After annotation:

```bash
python src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/validate_review_sheet.py --sheet src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/human_review_sheet.csv
python src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/merge_human_review.py
```

Validation status excerpt:

{validation}

## 7. After Reaching 20-30 True Interval Events

Create `reference_events_expanded_v1.csv`, then rerun SQ-CRAQ / audited envelope using the expanded true-interval-only reference. Recompute interval_eval recall, point-anchor exclusions, envelope miss-risk estimates, and selector value-add.

## 8. Still Diagnostic Before Expansion

Until human review produces at least 20-30 true interval events, all prior CILS, envelope, synthetic-signal, and value-add conclusions remain diagnostic only. No formal guarantee is established.

## Decision

`GO_FOR_HUMAN_REVIEW_PACKAGE`
""",
    )
    append_progress("final_report", f"queue_rows={len(queue)} media_ok={media_ok}")


if __name__ == "__main__":
    main()
