#!/usr/bin/env python3
"""Development-only smoke runner; fail closed while preregistration is blocked."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_rollout_preimplementation"


def main() -> None:
    prereg = json.loads((OUT / "UPDATED_H_ROLLOUT1A_PREREGISTRATION.json").read_text(encoding="utf-8"))
    if prereg.get("status") != "FROZEN_REBOUND" or not prereg.get("execution_authorized", False):
        raise SystemExit("BLOCKED_INTERNAL_INCONSISTENCY: development smoke not run")
    # The development seed file is intentionally opened only after the protocol gate.
    raise SystemExit("runner requires reissued D3/D4 implementation")


if __name__ == "__main__":
    main()

