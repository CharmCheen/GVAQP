# GVAQP P1 shadow VLM-direct reference result

## Decision

`SHADOW_P1_POTENTIAL = LOW`

The frozen 198-pair, anchor-assigned analysis gives macro video-query coverage effect `+0.003193` and distinct-event effect `+0.045041`. Only `2/6` clusters are positive (`2` zero, `2` negative), although `2/3` source-video coverage means are positive. Proxy directions conflict: YOLO `-0.004974`, optical flow `+0.009136`. The exact-pair anchor coverage mean is `+0.002354` and overlap-any sensitivity is `+0.000487`.

Yield-only ridge LOVO is R² `-0.018627`, MAE `0.016358`; yield+public-geometry is R² `0.071054`, MAE `0.015693`. Geometry improves MAE by only `0.000665`. Frozen C1's matched-pair F1 effect is `-0.001026`, so the weak primary positive is not a C1-only artifact; C1 does not corroborate it.

## Reference-quality boundary

The final study uses two isolated sessions/prompts of the same Qwen3-VL-8B checkpoint after the cross-family SmolVLM2 and Qwen32 alternatives failed schema/runtime feasibility. A has `176` events, B `73`; global matched-event fraction is `0.313`. The deterministic unmatched-event union yields `210` shadow events. This low agreement and same-checkpoint dependence are major confounds. Parse failures were retained as empty uncertain windows, never semantically retried.

## Claim boundary

This is evidence of **low success potential under this VLM-direct shadow ontology**, not a formal P1 failure and not human validation. It does not replace independent annotations, change `P1_EVENT_EVIDENCE_GEOMETRY = WAITING_HUMAN_REFERENCE`, authorize P2, support Claim B, or reopen controller work.

```json
{
  "c1_dependence": "NOT_C1_DEPENDENT",
  "c1_pair_mean_delta_f1": -0.0010256152353429106,
  "claim_boundary": "VLM-direct ontology feasibility only; not human confirmation",
  "controller_reopen": false,
  "exact_yield_pairs": 198,
  "formal_p1_status": "WAITING_HUMAN_REFERENCE",
  "geometry_mae_added_value": 0.0006645109254492104,
  "negative_clusters": 2,
  "overlap_any_pair_mean_delta_event_coverage": 0.00048690411875051514,
  "p2_authorized": false,
  "parse_status_counts": {
    "VLM_A": {
      "JSON_SCHEMA_VALID": 591,
      "PARSE_FAILURE_COERCED_EMPTY_UNCERTAIN": 3
    },
    "VLM_B": {
      "JSON_SCHEMA_VALID": 586,
      "PARSE_FAILURE_COERCED_EMPTY_UNCERTAIN": 8
    }
  },
  "positive_clusters": 2,
  "positive_source_videos": 2,
  "primary_mean_delta_distinct_events": 0.04504118566618567,
  "primary_mean_delta_event_coverage": 0.0031930658928194544,
  "primary_pair_mean_delta_event_coverage": 0.002353900068015785,
  "proxy_effects": {
    "PROXY_A_YOLOV8N_OBJECT_MOTION": -0.004974346673241924,
    "PROXY_B_OPTICAL_FLOW_VISUAL_DYNAMICS": 0.009136154005980012
  },
  "shadow_events": 210,
  "shadow_p1_potential": "LOW",
  "shadow_reference_type": "VLM_DIRECT",
  "vlm_agreement": {
    "event_existence_agreement": 0.8333333333333334,
    "global_matched_event_fraction_iou_gt_0": 0.3132530120481928,
    "median_abs_end_difference": 1.0,
    "median_abs_start_difference": 0.0,
    "median_matched_temporal_iou": 0.75,
    "shadow_events": 210,
    "vlm_a_events": 176,
    "vlm_b_events": 73
  },
  "vlm_annotators": [
    "Qwen3-VL-8B session A",
    "Qwen3-VL-8B independent session/prompt B"
  ],
  "yield_only_lovo": {
    "MAE": 0.016357754750135452,
    "R2": -0.01862739242662907
  },
  "yield_plus_geometry_lovo": {
    "MAE": 0.015693243824686242,
    "R2": 0.07105416802298903
  },
  "zero_clusters": 2
}
```
