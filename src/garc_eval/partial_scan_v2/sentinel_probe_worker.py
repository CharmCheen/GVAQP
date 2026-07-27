#!/usr/bin/python3
"""Fixed-path negative-capability probe for synthetic evaluator sentinels.

The paths are frozen in this source. The worker accepts no path input, performs
no enumeration, traversal, import probing, shell execution, or network access,
and returns only normalized capability results.
"""

from __future__ import annotations

import json
import sys


SENTINEL_PATHS = {
    "reference_sentinel": "/hidden-test/reference_sentinel.json",
    "future_cost_sentinel": "/hidden-test/future_cost_sentinel.json",
    "unscanned_output_sentinel": (
        "/hidden-test/unscanned_output_sentinel.json"
    ),
    "candidate_map_sentinel": "/hidden-test/candidate_map_sentinel.json",
}


def fixed_probe(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            handle.read(1)
    except FileNotFoundError:
        return "NOT_PRESENT"
    except PermissionError:
        return "ACCESS_DENIED"
    except OSError:
        return "ACCESS_DENIED"
    return "UNEXPECTEDLY_ACCESSIBLE"


def main() -> int:
    result = {
        name: fixed_probe(path) for name, path in SENTINEL_PATHS.items()
    }
    sys.stdout.write(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
    )
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
