#!/usr/bin/env python3
"""Freeze H003 selected directional-motion preview before execution."""
from __future__ import annotations
import hashlib, json, shutil
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/scan_innovation_agentic_loop_v1"
EXP = OUT / "preview_experiments/YGS-H003"

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1<<20): h.update(chunk)
    return h.hexdigest()

def main() -> None:
    EXP.mkdir(parents=True, exist_ok=True)
    source = OUT / "preview_experiments/YGS-H002/selected_regions.csv"
    target = EXP / "selected_regions.csv"
    shutil.copyfile(source, target)
    selection = pd.read_csv(target)
    value = {
        "hypothesis_id":"YGS-H003", "frozen_before_execution":True,
        "single_changed_mechanism":"selected-region 5-FPS directional residual optical flow",
        "selection_inherited_exactly_from":"YGS-H002 Q1 20%-cost boundary uncertainty selection",
        "selection_hash":sha256(target), "selected_region_count":len(selection),
        "operator":{"rate_fps":5.0,"resolution":"320x180","algorithm":"Farneback",
                    "subtract_global_median_flow":True,"region_state_reset":True,"repeat_count":2,
                    "features":["residual flow magnitude","lateral/vertical balance","signed lateral flow",
                                "positive divergence","center/lower-center residual flow","frame difference"]},
        "input_contract":"FROZEN_SELECTION_CSV_AND_SOURCE_VIDEO_BYTES_ONLY",
        "total_preview_cost_ratio_cap":0.10,
        "value_model_protocol":"same frozen nested LOVO families and Gate as H002",
        "freeze_script_hash":sha256(Path(__file__)),
    }
    path=OUT/'contracts/YGS-H003.json'; tmp=path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n'); tmp.replace(path)
    print(json.dumps(value,indent=2))

if __name__=='__main__': main()
