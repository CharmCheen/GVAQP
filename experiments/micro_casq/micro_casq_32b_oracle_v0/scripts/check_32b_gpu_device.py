#!/usr/bin/env python3
"""Verify that Qwen3-VL-32B is actually resident on CUDA, with no CPU offload."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT_DIR = ROOT / "test_vlm/outputs/micro_casq_32b_oracle_v0"
TABLES_DIR = OUT_DIR / "tables"
REPORTS_DIR = OUT_DIR / "reports"
MODEL_DIR = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
MODEL_NAME = "Qwen3-VL-32B-Instruct"


def run_cmd(cmd: list[str], timeout: int = 30) -> str:
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout, check=False)
        return result.stdout.strip()
    except Exception as exc:
        return f"ERROR: {exc}"


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]).replace("\n", "<br>") for c in df.columns) + " |")
    return "\n".join(lines)


def classify_device_status(cuda_available: bool, parameter_devices: list[str], device_map: Any) -> tuple[str, str]:
    if not cuda_available:
        return "GPU_NOT_AVAILABLE", "torch.cuda.is_available() is false"
    if not parameter_devices or all(d == "cpu" for d in parameter_devices):
        return "MODEL_ON_CPU", "all inspected model parameters are on CPU"
    if any(d == "cpu" or d.startswith("disk") for d in parameter_devices):
        return "CPU_OFFLOAD_DETECTED", f"inspected model parameter devices include CPU/disk: {parameter_devices}"
    if isinstance(device_map, dict) and any(str(v).startswith("cpu") or str(v).startswith("disk") for v in device_map.values()):
        return "CPU_OFFLOAD_DETECTED", f"hf_device_map contains CPU/disk placement: {device_map}"
    if all(d.startswith("cuda") for d in parameter_devices):
        return "GPU_VERIFIED", "inspected model parameters are on CUDA and no CPU/disk offload was detected"
    return "CODE_REVIEW_NEEDED", f"unexpected parameter devices: {parameter_devices}"


def main() -> int:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

    rows: list[dict[str, Any]] = []
    def add(check: str, value: Any) -> None:
        rows.append({"check": check, "value": value})
        print(f"{check}: {value}", flush=True)

    add("python_executable", sys.executable)
    import torch
    add("torch_version", torch.__version__)
    try:
        import transformers
        add("transformers_version", getattr(transformers, "__version__", "unknown"))
    except Exception as exc:
        add("transformers_version", f"unavailable: {exc}")
    add("CUDA_VISIBLE_DEVICES", os.environ.get("CUDA_VISIBLE_DEVICES", ""))
    cuda_available = bool(torch.cuda.is_available())
    add("torch_cuda_is_available", cuda_available)
    device_count = int(torch.cuda.device_count()) if cuda_available else 0
    add("torch_cuda_device_count", device_count)
    for i in range(device_count):
        add(f"torch_cuda_get_device_name_{i}", torch.cuda.get_device_name(i))
        try:
            free, total = torch.cuda.mem_get_info(i)
            add(f"torch_cuda_mem_get_info_{i}", f"free={free / (1024**3):.3f}GiB total={total / (1024**3):.3f}GiB")
        except Exception as exc:
            add(f"torch_cuda_mem_get_info_{i}", f"unavailable: {exc}")
    nvidia_smi = run_cmd(["nvidia-smi"], timeout=30) if shutil.which("nvidia-smi") else "nvidia-smi unavailable"
    add("nvidia_smi", nvidia_smi)

    if not cuda_available:
        df = pd.DataFrame(rows)
        df.to_csv(TABLES_DIR / "gpu_device_diagnostic.csv", index=False)
        write_report(df, "GPU_NOT_AVAILABLE", "torch.cuda.is_available() is false")
        return 2

    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    before_alloc = torch.cuda.memory_allocated() / (1024**3)
    before_reserved = torch.cuda.memory_reserved() / (1024**3)
    add("gpu_memory_allocated_before_loading_gb", f"{before_alloc:.3f}")
    add("gpu_memory_reserved_before_loading_gb", f"{before_reserved:.3f}")
    t0 = time.time()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(MODEL_DIR),
        dtype=torch.bfloat16,
        device_map={"": "cuda:0"},
        attn_implementation="sdpa",
        local_files_only=True,
    )
    _ = AutoProcessor.from_pretrained(str(MODEL_DIR), local_files_only=True)
    load_seconds = time.time() - t0
    add("model_name", MODEL_NAME)
    add("model_dir", str(MODEL_DIR))
    add("model_load_seconds", f"{load_seconds:.3f}")
    add("model_dtype", str(getattr(model, "dtype", "unknown")))
    device_map = getattr(model, "hf_device_map", {})
    add("hf_device_map", json.dumps(device_map, default=str, sort_keys=True))
    parameter_devices: list[str] = []
    parameter_names: list[str] = []
    for idx, (name, param) in enumerate(model.named_parameters()):
        if idx < 12:
            parameter_names.append(name)
            parameter_devices.append(str(param.device))
    add("inspected_parameter_names", json.dumps(parameter_names))
    add("inspected_parameter_devices", json.dumps(parameter_devices))
    try:
        first_device = str(next(model.parameters()).device)
    except Exception as exc:
        first_device = f"ERROR: {exc}"
    add("next_model_parameters_device", first_device)
    after_alloc = torch.cuda.memory_allocated() / (1024**3)
    after_reserved = torch.cuda.memory_reserved() / (1024**3)
    peak_alloc = torch.cuda.max_memory_allocated() / (1024**3)
    add("gpu_memory_allocated_after_loading_gb", f"{after_alloc:.3f}")
    add("gpu_memory_reserved_after_loading_gb", f"{after_reserved:.3f}")
    add("gpu_peak_memory_allocated_after_loading_gb", f"{peak_alloc:.3f}")
    status, reason = classify_device_status(cuda_available, parameter_devices + [first_device], device_map)
    add("cpu_only_fallback_occurred", status in {"MODEL_ON_CPU", "CPU_OFFLOAD_DETECTED"})
    add("gpu_device_diagnostic_decision", status)
    add("gpu_device_diagnostic_reason", reason)

    df = pd.DataFrame(rows)
    df.to_csv(TABLES_DIR / "gpu_device_diagnostic.csv", index=False)
    write_report(df, status, reason)
    return 0 if status == "GPU_VERIFIED" else 3


def write_report(df: pd.DataFrame, status: str, reason: str) -> None:
    decision_map = {
        "GPU_VERIFIED": "MICRO_CASQ_32B_ORACLE_DECISION: GPU_VERIFIED",
        "GPU_NOT_AVAILABLE": "MICRO_CASQ_32B_ORACLE_DECISION: GPU_NOT_AVAILABLE",
        "MODEL_ON_CPU": "MICRO_CASQ_32B_ORACLE_DECISION: MODEL_ON_CPU",
        "CPU_OFFLOAD_DETECTED": "MICRO_CASQ_32B_ORACLE_DECISION: CPU_OFFLOAD_DETECTED",
    }
    report = [
        "# GPU Device Diagnostic Report",
        "",
        "This diagnostic explicitly verifies the actual Qwen3-VL-32B model parameter devices after loading. It does not rely only on successful model loading.",
        "",
        f"- Diagnostic status: `{status}`",
        f"- Reason: `{reason}`",
        "",
        md_table(df),
        "",
        decision_map.get(status, "MICRO_CASQ_32B_ORACLE_DECISION: CODE_REVIEW_NEEDED"),
        "",
    ]
    (REPORTS_DIR / "GPU_DEVICE_DIAGNOSTIC_REPORT.md").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
