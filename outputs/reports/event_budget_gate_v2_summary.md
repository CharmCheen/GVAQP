# Event Budget Gate V2 Summary

Full output directory:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/event_budget_gate_v2`

Final report:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/event_budget_gate_v2/reports/FINAL_EVENT_BUDGET_GATE_REPORT.md`

This is a VLM-defined pseudo-oracle development experiment. Conservative VLM full-scan labels were used only for evaluation. No human audit package or new large-scale VLM inference was run.

Decision: `WEAK GO`.

Reason: event-aware scheduling shows partial gains at some pseudo-event gaps, but it is not stable against `temporal_nms_count` across 0s, 4s, and 8s merge gaps, and source-video concentration remains a material risk.
