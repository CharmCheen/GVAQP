# V7 Runtime Evidence

## Verified processor identity

The sealed V7 manifest binds Python 3.13.2, torch 2.10.0+cu129, transformers 5.9.0, qwen-vl-utils 0.0.14, NumPy 2.4.6, Pillow 12.1.1, and OpenCV 4.13.0.  These are exactly the fields returned by `runtime_environment_identity()` and fail-closed by the V7 runner.

## Current compatibility evidence

Current versions differ only for transformers, NumPy and OpenCV among those fields.  A processor-only replay of unit zero from each independent video reconstructed the exact frozen tensor SHA-256 in all three cases.  This verifies decoded-frame identity, prompt rendering, processor class, token IDs/tensor bytes for three cells; it does **not** verify generated semantic text because no checkpoint was loaded.

## Model / processor

The bound local checkpoint is `models/Qwen3-VL-32B-Instruct-FP8`, content hash `3febe26ff0cee468bf48dc733e4bca559c8f13f8fe09f931a1e0808ba7c58873`. `AutoProcessor.from_pretrained(..., trust_remote_code=True, local_files_only=True)` is used.  Processor/tokenizer/chat-template hashes are in `V7_RUNTIME_RECOVERY.json`. No Hugging Face repository revision is recorded for this local FP8 copy; model repo/revision is therefore `UNKNOWN_FROM_REPOSITORY`.

## Package-lock limit

No V7 requirements lock, conda lock, Docker image digest, pip-freeze, or frozen CUDA driver record was found. The V7 semantic processor identity is fully recorded; the complete installation dependency graph is not. `environment_v7_frozen.yml` is an evidence-derived isolated specification, not a claim of a complete historical lock.

## Scan/proxy evidence

The only V3 scan artifact is `scan_candidates/STATUS.md`, created with the explicit state `NOT_RUN — FROZEN_SCAN_EXECUTION_PENDING`. The repository contains historical YOLO configurations, but their own provenance is for other queries/references and the V3 status explicitly forbids promoting them. Thus no frozen V3 scan/proxy contract can be recovered.
