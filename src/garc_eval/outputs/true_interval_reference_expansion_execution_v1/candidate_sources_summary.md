# Candidate Sources Summary

Raw candidates before deduplication:

| source | raw_candidate_count |
| --- | --- |
| prior_sq_craq_review_queue | 208 |
| audited_envelope_candidate | 160 |
| envelope_repair_high_risk | 120 |
| lattice_high_score | 120 |
| synthetic_topk_selected_diagnostic | 120 |
| synthetic_cils_selected_diagnostic | 120 |
| lattice_medium_duration_high_score | 100 |
| top_p_answer_bin | 87 |
| lattice_high_boundary_contrast | 80 |
| lattice_low_density_blindspot | 80 |
| existing_reference_point_anchor | 14 |
| existing_reference_true_interval | 6 |
| smoke_selected_interval | 1 |

Selected review queue by priority/source:

| priority | source | review_count |
| --- | --- | --- |
| Priority 1 | top_p_answer_bin | 50 |
| Priority 1 | prior_sq_craq_review_queue | 22 |
| Priority 1 | envelope_repair_high_risk | 9 |
| Priority 2 | envelope_repair_high_risk | 19 |
| Priority 2 | audited_envelope_candidate | 11 |
| Priority 2 | prior_sq_craq_review_queue | 9 |
