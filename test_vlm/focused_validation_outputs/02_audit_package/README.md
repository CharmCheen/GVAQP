# Priority Audit Clips

This is a sanity-check package for the VLM pseudo-oracle. It is not intended to create full human GT.

Fill:

human_label:
  yes
  possible
  no
  invalid

human_event_type:
  true_ego_conflict
  possible_ego_conflict
  dense_traffic_only
  normal_following
  roadside_static
  ambiguous
  invalid_or_osd

error_type:
  vlm_false_positive
  vlm_false_negative
  proxy_false_positive
  proxy_false_negative
  boundary_error
  ambiguous_definition
