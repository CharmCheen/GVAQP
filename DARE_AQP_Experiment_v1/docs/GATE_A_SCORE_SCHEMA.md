# Gate A score-file contract

Inference and evaluation are separated to prevent evaluator leakage.  The
inference process receives only the video, frozen units, text prompt, and model
configuration.  It writes one row per `(signal_id, unit_id)`:

```text
signal_id,unit_id,score,model_id,model_revision,prompt_id
```

Required `signal_id` values for the final run are `current_proxy`,
`image_text`, `video_text`, and `rank_fusion`.  Every signal must cover all 347
units exactly once and contain finite numeric scores.  Fusion is constructed
from ranks before reference labels are joined.

Runtime accounting is stored separately because it is per inference job:

```text
signal_id,cold_index_seconds,warm_query_seconds,cpu_seconds,gpu_seconds,
frames_decoded,peak_memory_mb,device,software_versions
```

`evaluate_gate_a.py` joins reference events only after validating score
coverage.  It emits ranking metrics and reruns the original fixed-stage Gate B
certificate for every frozen ranking.  A ranking metric alone cannot pass the
gate.

