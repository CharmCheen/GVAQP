# True Interval Reference Expansion Execution V1

## 1. Why Current Reference Is A Hard Blocker

The current reference mixes point-anchor events and true interval events. Only about six events are usable for interval-IoU main evaluation, so CILS, SQ-CRAQ envelope, and synthetic-signal conclusions remain diagnostic until the true interval reference is expanded.

## 2. Review Candidate Count

- Review candidates generated: `120`
- Target range: `80-150`

## 3. Candidate Sources And Priority Distribution

| priority | source | count |
| --- | --- | --- |
| Priority 1 | top_p_answer_bin | 50 |
| Priority 1 | prior_sq_craq_review_queue | 22 |
| Priority 1 | envelope_repair_high_risk | 9 |
| Priority 2 | envelope_repair_high_risk | 19 |
| Priority 2 | audited_envelope_candidate | 11 |
| Priority 2 | prior_sq_craq_review_queue | 9 |

## 4. Media Export Status

- Media export successful: `True`
- Clips exported OK: `120` / `120`
- Contact sheets exported OK: `120` / `120`

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

# Review Validation Report

- Status: `PENDING_HUMAN_REVIEW`
- Human fields started: `False`
- Validated true interval rows: `0`
- Validated point-anchor rows: `0`
- Validated ambiguous rows: `0`
- Issue rows: `0`
- Target true interval count: `20-30`

If human review has not been filled, this is expected: the validation template and empty output CSVs are generated without failing.


## 7. After Reaching 20-30 True Interval Events

Create `reference_events_expanded_v1.csv`, then rerun SQ-CRAQ / audited envelope using the expanded true-interval-only reference. Recompute interval_eval recall, point-anchor exclusions, envelope miss-risk estimates, and selector value-add.

## 8. Still Diagnostic Before Expansion

Until human review produces at least 20-30 true interval events, all prior CILS, envelope, synthetic-signal, and value-add conclusions remain diagnostic only. No formal guarantee is established.

## Decision

`GO_FOR_HUMAN_REVIEW_PACKAGE`
