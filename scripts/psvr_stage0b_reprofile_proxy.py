#!/usr/bin/env python3
"""Replace only proxy observations with a producer-faithful physical rerun."""

from __future__ import annotations

import gc
import importlib.util
import json
import math
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_stage0b_physical_profile"
PROFILER = ROOT / "scripts/psvr_stage0b_physical_profile.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("stage0b_profiler", PROFILER); assert spec and spec.loader
    p = importlib.util.module_from_spec(spec); sys.modules[spec.name] = p; spec.loader.exec_module(p)
    import torch
    from ultralytics import YOLO

    rows: list[dict] = []
    fps, frame_count, duration = p.video_info(); batch_size = 4
    start = p.ns(); model = YOLO(str(p.PROXY_MODEL)); p.add(rows, "proxy_model_initialization", "cold", p.elapsed_s(start), 0, invocation="physical_proxy")
    coarse_seconds = [min(duration - 1/fps, 15.0 + 30.0*i) for i in range(int(math.ceil(duration/30.0)))]
    for _ in range(3):
        p.run_grid_proxy(model, torch, coarse_seconds[:batch_size], batch_size, rows, "warmup")
    coarse_total, coarse_scores = p.run_grid_proxy(model, torch, coarse_seconds, batch_size, rows, "warm_coarse")
    p.add(rows, "coarse_scan", "warm", coarse_total, 0, invocation="physical_proxy", coverage_fraction=1.0, temporal_stride_seconds=30.0)
    full_total, full_scores = p.run_full_proxy(model, torch, fps, frame_count, duration, batch_size, rows)
    p.add(rows, "full_proxy", "warm", full_total, 0, invocation="physical_proxy", coverage_fraction=1.0, temporal_stride_seconds=5.0)
    del model; gc.collect(); torch.cuda.empty_cache()

    new = pd.DataFrame(rows); new.to_csv(OUT / "proxy_reprofile_observations.csv", index=False)
    old = pd.read_csv(OUT / "operator_observations.csv")
    proxy_named = old.operator.astype(str).str.startswith(("proxy_", "motion_", "sequential_decode", "coarse_scan", "full_proxy", "video_open", "decode_seek"))
    merged = pd.concat([old.loc[~proxy_named], new], ignore_index=True)
    merged.to_csv(OUT / "operator_observations.csv", index=False)
    p.summarize(merged.to_dict("records")).to_csv(OUT / "operator_latency_summary.csv", index=False)
    meta = {"producer_faithful": True, "manual_pre_resize": False, "batch_size": batch_size,
            "coarse_seconds": coarse_total, "full_seconds": full_total,
            "coarse_samples": len(coarse_scores), "full_samples": len(full_scores)}
    (OUT / "proxy_reprofile.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
