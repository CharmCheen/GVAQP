#!/usr/bin/env python3
"""Held-out entry point with authorization and protocol gates before seed access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "outputs/psvr_rollout_preimplementation/UPDATED_H_ROLLOUT1A_PREREGISTRATION.json"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run frozen H-ROLLOUT1A held-out comparison")
    value.add_argument("--preregistration", type=Path, default=DEFAULT_PREREG)
    value.add_argument("--confirm-heldout", action="store_true", help="explicitly authorize opening the held-out seed file")
    return value


def main() -> None:
    args = parser().parse_args()
    if not args.confirm_heldout:
        raise SystemExit("refusing held-out access without --confirm-heldout")
    prereg = json.loads(args.preregistration.read_text(encoding="utf-8"))
    if prereg.get("status") != "FROZEN_REBOUND" or not prereg.get("execution_authorized", False):
        raise SystemExit("preregistration is not execution-authorized; held-out seeds were not opened")
    # The held-out seed file must be opened only below this gate after D3/D4 repair.
    raise SystemExit("BLOCKED_INTERNAL_INCONSISTENCY: held-out implementation is not frozen")


if __name__ == "__main__":
    main()

