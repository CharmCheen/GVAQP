#!/usr/bin/env python3
"""Analyze the sealed AEQ V3 preflight after authorized execution."""

import json

from garc_eval.accelerated_event_query.oracle_v3_analyzer import BASE, analyze
from garc_eval.accelerated_event_query.oracle_v3_manifest import write_json_once


def main() -> None:
    result = analyze()
    destination = BASE / "preflight/V3_SCHEMA_PREFLIGHT_METRICS.json"
    write_json_once(destination, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
