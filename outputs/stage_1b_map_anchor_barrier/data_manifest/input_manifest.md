# Stage 1B Input Manifest

| path                                                                      | role                                                                           |
|:--------------------------------------------------------------------------|:-------------------------------------------------------------------------------|
| outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv       | unit CSV with proxy_score and oracle_label revealed only after simulated query |
| outputs/real_video_protocol_pilot_v1/reference_segments_adapter_ready.csv | reference events for evaluation only                                           |
| outputs/ours_vs_baselines_realcartest_v1                                  | native and baseline oracle logs / segments                                     |
| outputs/stage_0_7_minimal_operator_compression                            | final K3 BB-EM reference output                                                |
| outputs/stage_1a_map_anchor_only                                          | Stage 1A MAP-anchor-only comparison and preservation checks                    |
| outputs/stage_1a_diagnostic_native_arc_vs_map_bbem                        | Stage 1A native ARC diagnostic context                                         |
