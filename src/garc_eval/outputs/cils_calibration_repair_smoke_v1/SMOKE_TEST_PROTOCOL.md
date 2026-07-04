# CILS Calibration Repair Smoke V1 Protocol

This is a preregistered clean no-leak smoke test, not a policy search and not final algorithm validation.

- pilot_policy: `answer_quality_proxy_top`
- calibration_model: `beta_bin_strata_lower`
- selector: `clean_v2_cils_selector`
- tau_p: `[0.5, 0.6, 0.7, 0.8, 0.9]`
- budgets: `[5, 10, 20, 40, 80]`
- seeds: `0..99` (`100` seeds)
- primary evaluation subset: `interval_eval` events (`duration >= 5s`)
- point-anchor handling: excluded from interval IoU main claim; reported separately by any-overlap, center-hit, and containment
- no model reruns; no new proposal families; clean v2 outputs are read-only
