#!/usr/bin/env python3
"""Install the saved producer-faithful proxy observations without rerunning GPU work."""

import importlib.util
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_stage0b_physical_profile"
spec = importlib.util.spec_from_file_location("stage0b_profiler_merge", ROOT / "scripts/psvr_stage0b_physical_profile.py")
assert spec and spec.loader
p = importlib.util.module_from_spec(spec); sys.modules[spec.name] = p; spec.loader.exec_module(p)
old = pd.read_csv(OUT / "operator_observations.csv")
new = pd.read_csv(OUT / "proxy_reprofile_observations.csv")
proxy_named = old.operator.astype(str).str.startswith((
    "proxy_", "motion_", "sequential_decode", "coarse_scan", "full_proxy", "video_open", "decode_seek"
))
merged = pd.concat([old.loc[~proxy_named], new], ignore_index=True)
merged.to_csv(OUT / "operator_observations.csv", index=False)
p.summarize(merged.to_dict("records")).to_csv(OUT / "operator_latency_summary.csv", index=False)
