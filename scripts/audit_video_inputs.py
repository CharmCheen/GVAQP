#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from garc.audit import audit_video_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description="RESEARCH_SUPPORT: non-semantic selected-Frontier input Gate")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--required-count", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(audit_video_inputs(args.input_dir, args.output_dir, required_count=args.required_count), indent=2))


if __name__ == "__main__":
    main()
