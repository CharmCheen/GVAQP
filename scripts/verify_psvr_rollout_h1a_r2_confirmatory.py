#!/usr/bin/env python3
"""Independent E1 raw-layer verifier; never treats aggregate files as truth."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from garc_eval.psvr_rollout_toy.r2e1_verifier import verify_attempt

def main():
 p=argparse.ArgumentParser(description="Verify R2 E1 raw confirmatory artifacts")
 p.add_argument("root",type=Path); a=p.parse_args()
 report=verify_attempt(a.root)
 print(json.dumps(report,sort_keys=True))
if __name__=="__main__": main()
