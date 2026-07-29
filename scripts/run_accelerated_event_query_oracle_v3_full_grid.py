#!/usr/bin/env python3
"""Validate, initialize, or execute one sealed V3 full-grid worker."""

import argparse
import json

from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import (
    emergency_global_stop,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_package import EXECUTION
from garc_eval.accelerated_event_query.oracle_v3_full_grid_runner import (
    initialize_execution,
    run_worker,
    validate_worker_inputs,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--validate-worker")
    modes.add_argument("--initialize-execution", action="store_true")
    modes.add_argument("--execute-worker")
    parser.add_argument("--declared-physical-gpus")
    parser.add_argument("--redecode", action="store_true")
    parser.add_argument("--reprocess", action="store_true")
    args = parser.parse_args()
    if args.validate_worker:
        result = validate_worker_inputs(
            args.validate_worker,
            redecode=args.redecode,
            reprocess=args.reprocess,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if args.initialize_execution:
        print(json.dumps(initialize_execution(), indent=2, sort_keys=True))
        return
    if not args.declared_physical_gpus:
        raise SystemExit("--declared-physical-gpus is required for execution")
    try:
        run_worker(
            args.execute_worker,
            [int(token) for token in args.declared_physical_gpus.split(",")],
        )
    except Exception as exc:
        emergency_global_stop(
            EXECUTION, "authentication_mismatch",
            f"sealed_cli:{args.execute_worker}:{type(exc).__name__}:{exc}",
        )
        raise


if __name__ == "__main__":
    main()
