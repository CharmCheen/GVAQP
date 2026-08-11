# Judge Model Audit

## Selected

- Judge A: `HuggingFaceTB/SmolVLM2-500M-Video-Instruct` (`SmolVLMForConditionalGeneration`), revision `7b375e1b73b11138ff12fe22c8f2822d8fe03467`.
- Weight SHA256: `b9bfd456c9472c0acd5719d6e514c4b859891af205ee1a736552fd3497b8b0c3`.
- Family relationship to original Qwen3-VL-32B model-relative reference: **CROSS_FAMILY**.
- Local artifact: fully cached 2.03GB `model.safetensors`; CUDA A100 hardware is available.

## Alternatives audited

- Local Qwen3-VL-8B is runnable but is Qwen family and was not used as a consensus judge, to avoid obscuring the cross-family interpretation.
- No second cached cross-family video-generative VLM was found. The protocol therefore freezes a single cross-family judge rather than delaying the study or fabricating a dual design.

## Evidence limitation

This 500M VLM is materially smaller than the original reference oracle. It is independent-family, blinded semantic corroboration only; it is not human ground truth and cannot settle all circularity concerns.
