# Limitations

The algorithm-selection evidence covers two development videos and two queries per video, uses frozen pseudo-reference events, and relies on measured-action replay. It does not establish human-ground-truth completeness, cross-domain generalization, physical hard-deadline safety, or a globally optimal 25:75 ratio.

Largest-Gap optimizes geometric coverage, not semantic value. Frontier scores and replay CONFIRM outcomes must be supplied by the caller; this repository deliberately contains no model weights, Oracle client, raw media, or production decoder. Sparse perceptual signatures can detect some overlap but cannot prove independence. The input Gate requires both content checks and credible provenance.
