"""Frozen finite H1B compute and planning grids."""
from __future__ import annotations

COMPUTE_CONFIGURATIONS = ((4, 4), (16, 16), (64, 64), (256, 256))
PRIMARY_CONFIGURATION = (64, 64)
PLANNING_TICKS = (0, 2, 5, 10, 20)
ERROR_MAGNITUDES = (0.0, 0.05, 0.10, 0.20)

def require_budget(worlds: int, trajectories: int, planning_ticks: int) -> None:
    if (worlds, trajectories) not in COMPUTE_CONFIGURATIONS or planning_ticks not in PLANNING_TICKS:
        raise ValueError("value is outside frozen H1B grid")
