#!/usr/bin/env python3
"""Validate and summarize the frozen Hangzhou 8B/32B physical probe."""

from __future__ import annotations

import hashlib
import json
import os
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/binary_smdp_value_v1/hangzhou_physical"


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def atomic_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    protocol = json.loads((OUT / "PROBE_PROTOCOL.json").read_text(encoding="utf-8"))
    results = {
        key: json.loads((OUT / f"{key}_results.json").read_text(encoding="utf-8"))
        for key in ("8b", "32b")
    }
    protocol_hash = hashlib.sha256((OUT / "PROBE_PROTOCOL.json").read_bytes()).hexdigest()
    for key, result in results.items():
        if result["probe_status"] != "COMPLETE" or result["protocol_sha256"] != protocol_hash:
            raise RuntimeError(f"{key} result is not bound to the current completed protocol")
        if len(result["calls"]) != 4 or any(call["parse_status"] != "ok" for call in result["calls"]):
            raise RuntimeError(f"{key} probe does not contain four successfully parsed calls")

    for index in range(4):
        left = results["8b"]["calls"][index]
        right = results["32b"]["calls"][index]
        for field in ("clip_id", "repeat_index", "decoded_frame_content_sha256", "model_input_shapes"):
            if left[field] != right[field]:
                raise RuntimeError(f"cross-model input mismatch at call {index}: {field}")

    unique = {key: result["calls"][:3] for key, result in results.items()}
    agreement = [
        left["parsed"]["label"] == right["parsed"]["label"]
        for left, right in zip(unique["8b"], unique["32b"])
    ]
    repeat_stability = {
        key: result["calls"][1]["raw_sha256"] == result["calls"][3]["raw_sha256"]
        for key, result in results.items()
    }
    inference = {
        key: [call["stage_seconds"]["inference"] for call in result["calls"]]
        for key, result in results.items()
    }
    summary = {
        "status": "COMPLETE_PHYSICAL_COST_AGREEMENT_PROBE",
        "not_established": [
            "human-ground-truth accuracy",
            "candidate-pipeline recall",
            "closed-loop controller improvement",
            "physical validation gate",
        ],
        "clips": [clip["clip_id"] for clip in protocol["clips"]],
        "input_identity_equal_across_models": True,
        "parse_success": {"8b": "4/4", "32b": "4/4"},
        "formal_call_failure_rate": {"8b": 0.0, "32b": 0.0},
        "mean_inference_seconds": {
            key: statistics.mean(values) for key, values in inference.items()
        },
        "inference_seconds": inference,
        "throughput_clips_per_second": {
            key: 1.0 / statistics.mean(values) for key, values in inference.items()
        },
        "load_seconds": {key: result["runtime"]["load_seconds"] for key, result in results.items()},
        "memory": {
            "8b_peak_allocated_bytes_one_gpu": results["8b"]["runtime"]["peak_allocated_bytes"],
            "32b_peak_allocated_bytes_two_gpus": results["32b"]["runtime"][
                "peak_allocated_bytes_by_visible_device"
            ],
        },
        "labels": {
            key: {call["clip_id"]: call["parsed"]["label"] for call in calls}
            for key, calls in unique.items()
        },
        "cross_model_label_agreement": {
            "agreed_clips": int(sum(agreement)),
            "total_clips": len(agreement),
            "fraction": sum(agreement) / len(agreement),
            "disagreement_clips": [
                unique["8b"][index]["clip_id"] for index, agrees in enumerate(agreement) if not agrees
            ],
        },
        "identical_raw_repeat": repeat_stability,
        "manual_contact_sheet_audit": {
            "scope": "qualitative 1-fps contact-sheet review, not human annotation",
            "HZ_2800": "visible cross-traffic supports an entering-vehicle interpretation",
            "HZ_4200": (
                "no pedestrian crossing from the left into the ego lane is visible at the "
                "32B-claimed 5-6 second interval; the 32B positive is not visually supported"
            ),
        },
        "deployment_observation": (
            "the local 32B FP8 checkpoint cannot execute FP8 on A100 (SM 8.0); "
            "Transformers dequantized it and required two A100s after BF16 dtype normalization"
        ),
        "policy_comparison": "NOT_RUN_HEADROOM_GATE_FAILED",
    }
    atomic_json(OUT / "summary.json", summary)
    atomic_json(OUT / "POLICY_COMPARISON_STATUS.json", {
        "status": "NOT_RUN_HEADROOM_GATE_FAILED",
        "required_policies": ["R4", "shielded binary SMDP", "best fixed"],
        "reason": "the frozen oracle headroom gate did not authorize a learned controller",
    })
    report = f"""# Hangzhou physical VLM probe

Status: `COMPLETE_PHYSICAL_COST_AGREEMENT_PROBE`
Policy comparison: `NOT_RUN_HEADROOM_GATE_FAILED`

## Observed physical evidence

The frozen content-blind subset contains three 10-second clips sampled at 2
fps. Both models received identical decoded-frame hashes and model-input tensor
shapes. All eight formal calls parsed successfully; the repeated middle clip
produced byte-identical raw output for each model.

| Model | Valid labels (1400 / 2800 / 4200) | Mean inference | Throughput | Peak allocated memory |
|---|---|---:|---:|---:|
| Qwen3-VL 8B | negative / positive / negative | {summary['mean_inference_seconds']['8b']:.3f} s | {summary['throughput_clips_per_second']['8b']:.4f} clips/s | {summary['memory']['8b_peak_allocated_bytes_one_gpu'] / 2**30:.2f} GiB on 1 A100 |
| Qwen3-VL 32B-FP8 checkpoint | negative / positive / positive | {summary['mean_inference_seconds']['32b']:.3f} s | {summary['throughput_clips_per_second']['32b']:.4f} clips/s | {summary['memory']['32b_peak_allocated_bytes_two_gpus'][0] / 2**30:.2f} + {summary['memory']['32b_peak_allocated_bytes_two_gpus'][1] / 2**30:.2f} GiB on 2 A100s |

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

The 8B model is the only plausible online verifier of the two on this A100
host: it is about {summary['mean_inference_seconds']['32b'] / summary['mean_inference_seconds']['8b']:.2f}x faster per clip and uses one GPU. The 32B checkpoint is an expensive offline
reviewer and shows a concrete unsupported positive in this small sample. With
only three content-blind clips and no human labels, neither accuracy nor event
prevalence is estimated.

No R4/controller/best-fixed physical comparison was run. The preregistered
oracle headroom gate failed before controller training, so running a purported
learned-policy comparison would not test a frozen learned controller and would
violate the stop rule. These results therefore establish physical runtime,
input stability and verifier disagreement only—not binary-SMDP headroom.
"""
    atomic_text(OUT / "HANGZHOU_PHYSICAL_REPORT.md", report)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
