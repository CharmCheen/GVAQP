#!/usr/bin/env python3
"""Generate a causal SCAN order using the selected safe coverage package."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from garc_eval.scan_headroom.trusted_policies import PublicScanState, PublicUnit
from garc_eval.scan_scheduler import SafeCoverageConfig, SafeCoveragePolicy

def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--video-id',required=True)
    parser.add_argument('--timeline',type=Path,default=ROOT/'benchmarks/partial_scan_pilot_v1/immutable/timeline_units.csv')
    parser.add_argument('--config',type=Path,default=ROOT/'configs/safe_coverage_scan.yaml')
    parser.add_argument('--policy',choices=['SEQUENTIAL','UNIFORM_PREFIX','ANYTIME_LARGEST_GAP','MACRO_REGION_LARGEST_GAP'])
    parser.add_argument('--max-actions',type=int,default=20)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    raw=yaml.safe_load(args.config.read_text()); policy_id=args.policy or raw['policy_id']
    policy=SafeCoveragePolicy(SafeCoverageConfig(policy_id, int(raw['macro_region_size_units'])))
    frame=pd.read_csv(args.timeline).query('video_id == @args.video_id').sort_values('unit_index')
    if frame.empty: raise SystemExit(f'unknown video_id: {args.video_id}')
    units=tuple(PublicUnit(r.unit_id,float(r.start_sec),float(r.end_sec)) for r in frame.itertuples())
    scanned=[]; rows=[]
    for action in range(min(args.max_actions,len(units))):
        state=PublicScanState(units,tuple(scanned),scanned[-1] if scanned else None,float('inf'),())
        unit_id=policy.choose_next_unit(state); scanned.append(unit_id); unit=next(u for u in units if u.unit_id==unit_id)
        rows.append({'action_index':action+1,'policy_id':policy.policy_id,'video_id':args.video_id,'unit_id':unit_id,'start_sec':unit.start_sec,'end_sec':unit.end_sec})
    result=pd.DataFrame(rows)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True); result.to_csv(args.output,index=False)
    else: print(result.to_csv(index=False),end='')

if __name__=='__main__': main()
