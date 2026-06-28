# Roadclip V2 Final Acceleration Report

STATUS: PASS_PRELIMINARY_ACCELERATION

These VLM labels are conservative Qwen3-VL pseudo-GT, not human ground truth.

## Dataset

1. road-driving segments: 11
2. valid road-driving duration sec: 3970.0
3. clip pool size: 500
4. conservative positive rate: 39 / 500 = 0.078
5. positive events: 39
6. average positive run length: 1.000
7. positive density sufficient: yes
8. better than old 102-clip smoke set: yes

## Low-Budget Acceleration

9. 5%-20% best clip recall method: `top_count` = 0.462
10. 5%-20% best event recall method: `top_count` = 0.462
11. random clip recall avg: 0.121; best non-random gain: 3.83x by `top_count`
12. random event recall avg: 0.121; best non-random gain: 3.83x by `top_count`
13. budget needed to reach 0.8 event recall: `top_count` at 0.50 budget; approximate VLM call saving 0.500

## Method Interpretation

- top_count avg clip recall: 0.462
- top_naive avg clip recall: 0.090
- ensemble_count_naive avg clip recall: 0.276
- top_kinematic avg clip recall: 0.096
- temporal_nms_count avg event recall: 0.462
- temporal_nms_naive avg event recall: 0.090
- proxy_then_expansion_count avg clip recall: 0.365

## Policy Sweep Summary

- 0.10 budget: best clip `temporal_nms_count` recall=0.487; best event `temporal_nms_count` event_recall=0.487
- 0.20 budget: best clip `temporal_nms_count` recall=0.667; best event `temporal_nms_count` event_recall=0.667
- 0.30 budget: best clip `proxy_then_expansion_count` recall=0.769; best event `proxy_then_expansion_count` event_recall=0.769

## Decision

- Current evidence supports preliminary semantic clip query acceleration under conservative VLM pseudo-GT.
- Next step: expand to more videos and run human audit on the audit package.
