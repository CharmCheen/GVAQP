# GRANULARITY_PHASE_DIAGRAM (GEOMETRIC_CEILING_ONLY)

Scope: this phase is purely geometric/representability. No 2s/5s semantic
outcomes exist in the repository; the only available reference (model-relative
full-grid C1 over 10s units) is itself 10s-quantized.

## Findings

- **Reference events are structurally >=10s and 10s-quantized** (all boundaries
  multiples of 10) for every cluster; the <2s / 2-5s / 5-10s duration bins are
  EMPTY by construction for both queries. Short-event coverage at 2s/5s
  therefore cannot be evaluated against any local reference.
- **Boundary-IoU ceiling**: median ceiling of a G2/G5/G10 grid cell against the
  reference events is identical for all three strides (the 10s grid already
  contains the full event); G_granularity (geometric) = 0.0 by
  construction.
- **WUHAN 5s proxy-level evidence exists** (693 clips, motion/count features):
  {"video": "WUHAN", "n_5s_clips": 693, "n_reference_events": 32, "events_with_5s_proxy_evidence": 32, "fraction": 1.0}. This proves fine-grained PROXY evidence is feasible,
  but there is no fine-grained VERIFIER output; nothing here measures semantic
  quality at 5s.
- **Adaptive-granularity oracle**: NOT COMPUTABLE (no multi-granularity
  semantic outcomes). Marked GEOMETRIC_CEILING_ONLY.

## Granularity gate (preregistered thresholds)

- G_granularity (semantic) = NOT_ESTIMABLE (missing 2s/5s semantic outcomes;
  reference 10s-quantized).
- Route: **FIXED_GRANULARITY_ONLY + BLOCKED_GPU_MULTIGRANULARITY (semantic 2s/5s outcomes absent; reference 10s-quantized)**.
- Caveat: for a FUTURE independent (human) reference with continuous
  boundaries, the 10s-grid quantization error is unknown and cannot be
  bounded locally -> the granularity question for human events remains open
  and is a GPU+human-labels experiment, not a CPU-answerable one.
