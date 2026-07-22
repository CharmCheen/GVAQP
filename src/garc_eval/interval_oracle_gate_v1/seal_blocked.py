#!/usr/bin/env python3
"""Seal the Phase-0 contract-blocked package; performs no inference."""

import hashlib
from pathlib import Path
import pandas as pd

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "DARE_AQP_Experiment_v1").is_dir())
OUT = ROOT / "DARE_AQP_Experiment_v1/outputs/gate_c0_physical_interval_operator_v1"

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()

rows = []
for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "FILE_MANIFEST.csv"):
    rows.append({"path": str(path.relative_to(ROOT)), "size_bytes": path.stat().st_size, "sha256": sha256(path)})
pd.DataFrame(rows).to_csv(OUT / "FILE_MANIFEST.csv", index=False)
print(OUT / "FILE_MANIFEST.csv")
