# Hangzhou physical VLM probe

Status: `COMPLETE_PHYSICAL_COST_AGREEMENT_PROBE`
Policy comparison: `NOT_RUN_HEADROOM_GATE_FAILED`

## Observed physical evidence

The frozen content-blind subset contains three 10-second clips sampled at 2
fps. Both models received identical decoded-frame hashes and model-input tensor
shapes. All eight formal calls parsed successfully; the repeated middle clip
produced byte-identical raw output for each model.

| Model | Valid labels (1400 / 2800 / 4200) | Mean inference | Throughput | Peak allocated memory |
|---|---|---:|---:|---:|
| Qwen3-VL 8B | negative / positive / negative | 8.281 s | 0.1208 clips/s | 17.93 GiB on 1 A100 |
| Qwen3-VL 32B-FP8 checkpoint | negative / positive / positive | 24.726 s | 0.0404 clips/s | 58.95 + 61.95 GiB on 2 A100s |

Cross-model label agreement is 2/3 (66.7%). At HZ_4200 the 8B output is
negative, while 32B claims that a pedestrian crosses from the left at 5-6 s.
A direct 1-fps contact-sheet audit of that interval shows the divided road,
vehicles remaining in lanes and pedestrians on the right sidewalk, but no such
crossing. This is qualitative negative evidence, not a human ground-truth
annotation; it makes the 32B output unsuitable as an unquestioned teacher.

## Runtime qualification and failures

The local 32B checkpoint is FP8, but A100 has compute capability 8.0 and the
installed Transformers stack requires at least 8.9 for that FP8 path. It
dequantized to BF16. A single A100 then OOMed at 78.97 GiB process memory. A
two-A100 balanced load still required explicit normalization of residual FP32
ignored layers to BF16; the completed run peaked at the values above. The full
failed-attempt history is retained in `ATTEMPT_LOG.json` rather than discarded.

The current environment also required `qwen-vl-utils==0.0.14`, `av==18.0.0`
and `opencv-python-headless==4.13.0.92`. Compatibility probes showed that
Qwen3-VL temporal metadata must be passed explicitly; earlier outputs without
correct 2-fps metadata are excluded.

## Supported interpretation

Of the two tested paths, the 8B model is the more plausible online-verifier
candidate on this A100 host: it is about 2.99x faster per clip and uses one GPU. The 32B checkpoint is an expensive offline
reviewer and shows a concrete unsupported positive in this small sample. With
only three content-blind clips and no human labels, neither accuracy nor event
prevalence is estimated.

No R4/controller/best-fixed physical comparison was run. The preregistered
oracle headroom gate failed before controller training, so running a purported
learned-policy comparison would not test a frozen learned controller and would
violate the stop rule. These results therefore establish physical runtime,
input stability and verifier disagreement only—not binary-SMDP headroom.
