# TODO: Exact 102-Clip VLM32B Labels

The cleanest next step is to run the same 32B VLM prompt directly on the 102 clips in:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/proxy_scores.csv
```

Expected output schema:

```text
clip_id,start_time,end_time,clip_path,vlm_label,vlm_risk_level,vlm_affected_ego,vlm_reason
```

Why this matters:

- The current pseudo labels come from 67 original 6s stride3 VLM windows.
- They are mapped onto 102 5s stride2 proxy clips by temporal overlap.
- This preliminary mapping can duplicate one VLM decision across neighboring proxy clips.
- Exact clip_id-level labels would remove the main alignment ambiguity and make clip-level budget curves cleaner.

Do not treat the current overlap-mapped labels as final ground truth.
