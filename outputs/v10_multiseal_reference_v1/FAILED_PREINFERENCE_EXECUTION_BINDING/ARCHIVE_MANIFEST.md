# Failed Pre-Inference Execution-Binding Archive

This archived V10-MS single-GPU shadow seal failed before model loading,
generation, parsing, or raw-output persistence. It produced zero semantic
outputs and is therefore a pure execution-binding failure, not a semantic
attempt. The faulty worker read historical V3 GPU-pair metadata rather than
the then-current V10-MS seal topology. It is preserved for provenance and is
not reused by the successor single-GPU amendment.
