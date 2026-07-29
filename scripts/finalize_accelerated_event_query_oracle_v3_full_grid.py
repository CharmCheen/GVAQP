#!/usr/bin/env python3
"""Run the frozen V3 full-grid finalizer and complete-only release gate."""

import json

from garc_eval.accelerated_event_query.oracle_v3_full_grid_finalizer import finalize_execution


def main() -> None:
    print(json.dumps(finalize_execution(allow_mock=False), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
