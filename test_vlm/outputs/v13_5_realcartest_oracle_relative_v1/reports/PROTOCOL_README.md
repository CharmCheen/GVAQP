# V13.5 Protocol Confirmation

## Documents Read

1. **CASQ_CODEX_BRIEF_V12_1.md**: `/qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md` — governing brief, Phase 1+ protocol sections enforced.
2. **REALCARTEST_ORACLE_RELATIVE_VALIDATION_V13_5.md**: `/qiuyeqing/llama_prl/G-ARC/docs/clip_aqp/REALCARTEST_ORACLE_RELATIVE_VALIDATION_V13_5.md` — V13.5 realcartest-specific protocol.

## Protocol Hierarchy

V13.5 is subordinate to V12.1. V12.1 global restrictions apply:
- No model training
- No large dataset downloads
- No certificate simulation (V13.5 explicit)
- No human-truth claims
- No VLM labels during candidate generation
- Full VLM scanning allowed only for offline benchmark construction on this one video

## Stages

```
Stage 0: Protocol and filesystem setup           ← CURRENT
Stage 1: Video preflight
Stage 2: Full-video cheap proxy feature extraction
Stage 3: VLM oracle pilot (100 clips)
Stage 4: Conditional full coarse VLM oracle construction
Stage 5: Conditional boundary refinement
Stage 6: Conditional candidate evaluation
```

## Hard Invariants

- `uses_oracle_annotation_for_generation` = false
- `uses_event_boundary_for_generation` = false
- Proxy features contain no VLM labels
- All VLM labels are `VLM_ORACLE_RELATIVE`
- No human-truth claims
