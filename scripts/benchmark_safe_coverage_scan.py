#!/usr/bin/env python3
"""Print the frozen replay/physical evidence for safe coverage choices."""
from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
def main()->None:
    path=ROOT/'outputs/scan_innovation_agentic_loop_v1/controls/layer0_per_video_winners.csv'
    data=pd.read_csv(path)
    columns=['video_id','full_horizon_winner','full_horizon_auc','auc60_winner','auc60','physical_auc60_winner_among_tested','physical_auc60','offline_oracle_full_auc','remaining_full_auc_headroom']
    print(data[columns].to_csv(index=False),end='')
if __name__=='__main__': main()
