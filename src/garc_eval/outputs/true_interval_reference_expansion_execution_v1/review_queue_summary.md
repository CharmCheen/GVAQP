# Review Queue Summary

- Raw candidate rows: `1216`
- Deduplicated candidate rows: `120`
- Final review queue rows: `120`
- Target range: `80-150`
- Human label placeholders are intentionally blank.
- Existing labels and candidate suggestions are separated from human/final label columns.

Priority/source distribution:

| priority | source | review_count |
| --- | --- | --- |
| Priority 1 | top_p_answer_bin | 50 |
| Priority 1 | prior_sq_craq_review_queue | 22 |
| Priority 1 | envelope_repair_high_risk | 9 |
| Priority 2 | envelope_repair_high_risk | 19 |
| Priority 2 | audited_envelope_candidate | 11 |
| Priority 2 | prior_sq_craq_review_queue | 9 |
