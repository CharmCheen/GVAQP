# Claims Ledger

## Supported

### Claim: probe_set_v1 media package exists

- allowed_wording: `probe_set_v1 contains 25 probes with exported clips, center frames, and contact sheets.`
- evidence: `outputs/probe_set_v1/`
- feature_design_informed_by_6event_reference: no

### Claim: probe rows are frozen/read-only for modeling

- allowed_wording: `Probe rows are marked as frozen/read-only and not for tuning.`
- evidence: `outputs/probe_set_v1/probe_set_manifest.csv`
- feature_design_informed_by_6event_reference: no

### Claim: fallback time axis

- allowed_wording: `The fallback time axis uses local_to_media_offset_seconds=2000.0.`
- evidence: `outputs/probe_set_v1/probe_set_manifest.csv`
- feature_design_informed_by_6event_reference: no

### Claim: cheap_signal_v2 diagnostic metrics are 6-event-only

- allowed_wording: `cheap_signal_v2 metrics were emitted only for dataset_source=6_event_reference and should be treated as diagnostic design targets.`
- evidence: `outputs/cheap_signal_v2/signal_upgrade_within_bin_metrics.csv`
- feature_design_informed_by_6event_reference: yes

### Claim: 6-event diagnostic design target AUCs

- allowed_wording: `On 6_event_reference within the existing top p_answer bin, diagnostic_design_target AUCs were: existing signal 0.695, track-interaction signal 0.744, inside/outside contrast signal 0.818.`
- evidence: `outputs/cheap_signal_v2/signal_upgrade_within_bin_metrics.csv`
- feature_design_informed_by_6event_reference: yes

### Claim: probe feature-table coverage

- allowed_wording: `Current cheap-signal feature tables fully cover 20 of 25 probe intervals and do not cover 5 of 25 probe intervals.`
- evidence: `outputs/cheap_signal_v2/probe_feature_coverage_audit.csv`
- feature_design_informed_by_6event_reference: uncertain

### Claim: VLM oracle labels exist for probe_set_v1

- allowed_wording: `probe_set_v1 has 25 local Qwen3-VL-32B oracle judgments with 25/25 parse_status=ok. These labels are VLM-oracle-relative, not human ground truth.`
- evidence: `outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`
- feature_design_informed_by_6event_reference: no

### Claim: VLM oracle positive count

- allowed_wording: `Relative to the VLM oracle judgment, probe_set_v1 contains 7 oracle-positive probes: 6 true_interval and 1 point_anchor.`
- evidence: `outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`
- feature_design_informed_by_6event_reference: no

### Claim: VLM human spotcheck table is ready

- allowed_wording: `A 12-probe random human spotcheck table is ready for VLM agreement audit.`
- evidence: `outputs/probe_set_v1/vlm_human_agreement_spotcheck.csv`; `outputs/probe_set_v1/vlm_human_agreement_spotcheck.meta.json`
- feature_design_informed_by_6event_reference: no

### Claim: probe_set_v1 VLM-oracle-relative signal evaluation completed

- allowed_wording: `A small probe_set_v1 signal evaluation relative to the VLM oracle judgment has been completed over the 20 probes covered by cheap_signal_v2 features. Track-interaction representative features did not collapse; inside/outside representative features were weak or inconsistent on this probe set.`
- evidence: `outputs/agent_loop_v1/probe_eval_after_vlm_oracle/probe_signal_metrics.csv`; `outputs/agent_loop_v1/probe_eval_after_vlm_oracle/probe_positive_rank_cases.csv`
- feature_design_informed_by_6event_reference: yes

### Claim: probe_set_v1 evaluation scope limitation

- allowed_wording: `The probe_set_v1 signal evaluation is limited to 20/25 scored probes because current cheap_signal_v2 feature coverage ends at local 1200s; the five unscored probes are VLM-oracle-negative but should not be used to claim full-set signal performance.`
- evidence: `outputs/agent_loop_v1/probe_eval_after_vlm_oracle/probe_unscored_cases.csv`
- feature_design_informed_by_6event_reference: uncertain

### Claim: Phase 3 minimal AQP selector smoke completed

- allowed_wording: `The first executable AQP selector/budget smoke has been completed using existing CSV artifacts only. It produced budgeted returned interval sets for uniform_random, existing_signal, track_interaction, inside_outside, and simple_fused selectors at B=5,10,20,40.`
- evidence: `outputs/agent_loop_v1/phase3_selector_smoke_v1/selector_budget_summary.csv`; `outputs/agent_loop_v1/phase3_selector_smoke_v1/selected_intervals.csv`; `scripts/phase3/run_minimal_selector_smoke.py`
- feature_design_informed_by_6event_reference: yes

### Claim: Phase 3 selector smoke negative result

- allowed_wording: `In the Phase 3 diagnostic smoke, current fixed cheap-signal selectors did not convert signal-level diagnostics into better budgeted return-set coverage. At B=40, uniform_random averaged 0.153 event_recall_iou_0_3 across 50 seeds, while the best deterministic cheap-signal selector reached 0.050.`
- evidence: `outputs/agent_loop_v1/phase3_selector_smoke_v1/selector_budget_summary.csv`; `outputs/agent_loop_v1/phase3_selector_smoke_v1/phase3_selector_smoke_report.md`
- feature_design_informed_by_6event_reference: yes

## Not Supported

### Claim: true recall or ground truth recall

- disallowed_wording: `true recall`, `ground truth recall`, `human ground truth recall`
- reason: `probe_set_v1 labels are currently Qwen3-VL-32B oracle judgments, not human ground truth.`
- feature_design_informed_by_6event_reference: no

### Claim: improved full-video recall or precision

- disallowed_wording: `improved full-video recall`, `improved full-video precision`
- reason: `Only a diagnostic selector smoke has run, and its deterministic cheap-signal selector result is negative at the current B=40 snapshot.`
- feature_design_informed_by_6event_reference: uncertain

### Claim: expanded_reference result

- disallowed_wording: `expanded_reference validates the signal`
- reason: `expanded_reference is empty.`
- feature_design_informed_by_6event_reference: no

### Claim: formal guarantee or certificate

- disallowed_wording: `formal guarantee`, `certificate`, `statistical bound`
- reason: `No certificate or formal guarantee computation was run.`
- feature_design_informed_by_6event_reference: no

### Claim: full historical realcartest coverage

- disallowed_wording: `current probe media covers the full 66-minute realcartest video`
- reason: `Current probe media uses fallback dataset3 coverage, not full historical realcartest coverage.`
- feature_design_informed_by_6event_reference: no

### Claim: selector replacement

- disallowed_wording: `new signal should replace the default selector`
- reason: `A minimal selector/budget smoke has run, but it did not support replacing the selector; deterministic cheap-signal selectors underperformed the 50-seed uniform random baseline at B=40 event_recall_iou_0_3.`
- feature_design_informed_by_6event_reference: uncertain

### Claim: probe frozen evaluation metrics

- disallowed_wording: `probe AUC`, `probe precision@k`, `probe recall`
- reason: `Probe metrics now exist only as VLM-oracle-relative diagnostics over the feature-covered 20-probe scope. They must not be presented as human-ground-truth metrics or as statistically significant signal superiority.`
- feature_design_informed_by_6event_reference: uncertain

### Claim: statistically significant signal superiority

- disallowed_wording: `signal X is significantly better than signal Y`, `validated signal superiority`, `confirmed generalization`
- reason: `probe_set_v1 has only 7 VLM-oracle positives and wide bootstrap intervals; the completed Phase 3 selector/budget smoke is diagnostic and negative for the current deterministic cheap-signal selectors.`
- feature_design_informed_by_6event_reference: uncertain
