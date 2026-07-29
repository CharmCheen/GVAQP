#!/usr/bin/env python3
"""Run the frozen V3 full-grid analyzer after an authorized physical run."""

import json

from garc_eval.accelerated_event_query.oracle_v3_full_grid_analyzer import analyze_execution


def main() -> None:
    metrics, _ = analyze_execution(allow_mock=False)
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
