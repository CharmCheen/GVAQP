#!/usr/bin/python3
"""Controlled exception source for public/private error-redaction tests."""

from __future__ import annotations

import json
import sys
import traceback


PROTOCOL = "partial-scan-policy-jsonl-v2"
PRIVATE_MARKER = (
    "SYNTHETIC_REFERENCE_MARKER:/synthetic-private/evaluator-only.py"
)


def read_object() -> dict:
    value = json.loads(sys.stdin.readline())
    if not isinstance(value, dict):
        raise ValueError("synthetic protocol object required")
    return value


def main() -> int:
    initialize = read_object()
    sys.stdout.write(
        json.dumps(
            {
                "type": "initialized",
                "run_id": initialize["run_id"],
                "protocol_version": PROTOCOL,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    sys.stdout.flush()
    read_object()
    try:
        raise RuntimeError(PRIVATE_MARKER)
    except RuntimeError:
        traceback.print_exc(file=sys.stderr)
        sys.stdout.write(
            json.dumps(
                {"error_code": "POLICY_PROTOCOL_ERROR"},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        sys.stdout.flush()
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
